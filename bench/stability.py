"""How much do tiny changes to the audio change which fillers Whisper writes down?

    uv run python bench/stability.py samples/episode.mp3 --start 600 --length 300

Transcription itself is deterministic: the same samples give the same words every time. But
an export with no cuts (identical except a 10 ms fade at each end) gave 23 fillers where the
original clip gave 17. This transcribes a few near-identical versions of one clip and groups
the fillers found by time, to show which spots every version agrees on and which come and go.
"""

import argparse

import numpy as np

from talkcut import edit
from talkcut.transcribe import HOTWORDS, load_audio

SR = 16000


def variants(clip):
    """(name, samples, offset in seconds) for versions a listener couldn't tell apart."""
    faded = clip.copy()
    n = int(edit.FADE * SR)
    faded[:n] *= np.linspace(0, 1, n, dtype=np.float32)
    faded[-n:] *= np.linspace(1, 0, n, dtype=np.float32)
    noise = np.random.default_rng(0).normal(0, 1e-4, len(clip)).astype(np.float32)
    out = [("original", clip, 0.0), ("10 ms fade at each end", faded, 0.0),
           ("noise at -80 dB", clip + noise, 0.0)]
    out += [(f"starts {s} s later", clip[int(s * SR):], s) for s in (0.5, 1.0, 2.0)]
    return out


def fillers_in(whisper, samples, offset):
    segments, _ = whisper.transcribe(samples, word_timestamps=True, hotwords=HOTWORDS,
                                     condition_on_previous_text=False)
    words = [{"text": w.word.strip(), "start": w.start + offset, "end": w.end + offset}
             for s in segments for w in s.words]
    return [words[i] for i in edit.find_fillers(words)]


def main():
    from faster_whisper import WhisperModel

    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--length", type=float, default=300)
    ap.add_argument("--model", default="base")
    args = ap.parse_args()

    audio = load_audio(args.media)
    clip = audio[int(args.start * SR):int((args.start + args.length) * SR)]
    quiet = (lambda lv: lv < 0.05 * np.percentile(lv, 95))(edit.frame_levels(clip))
    whisper = WhisperModel(args.model, device="auto", compute_type="int8")

    spots = []  # fillers from different versions within 0.4 s are the same spot
    vs = variants(clip)
    for name, samples, offset in vs:
        found = fillers_in(whisper, samples, offset)
        print(f"{name:24s} {len(found):3d} fillers", flush=True)
        for w in found:
            s = next((s for s in spots if abs(s["t"] - w["start"]) < 0.4), None)
            if s is None:
                spots.append(s := {"t": w["start"], "in": set(), "text": set()})
            s["in"].add(name)
            s["text"].add(w["text"].strip(",.?!").lower())

    print("\n| At | Versions that find it | Heard as | Sound under it |")
    print("| --- | --- | --- | --- |")
    for s in sorted(spots, key=lambda s: s["t"]):
        i = int(s["t"] * 100)
        sound = 1 - quiet[i:i + 30].mean()
        print(f"| {args.start + s['t']:.1f} s | {len(s['in'])} of {len(vs)} | "
              f"{'/'.join(sorted(s['text']))} | {sound:.0%} |")
    every = sum(len(s["in"]) == len(vs) for s in spots)
    print(f"\n{len(spots)} spots; {every} found by every version, {len(spots) - every} by some")


if __name__ == "__main__":
    main()
