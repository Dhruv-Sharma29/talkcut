"""CPU vs Apple GPU (MPS) transcription: speed, and whether the GPU transcript loses words.

    uv run --with "ctranslate2>=4.9" python bench/device.py samples/episode.mp3 --start 600

MPS needs ctranslate2 4.9 or newer (experimental there). Prints each device's time and word
count, then every stretch where the two transcripts disagree by four words or more.
"""

import argparse
import difflib
import re
import time

from faster_whisper import WhisperModel

from talkcut.edit import find_fillers
from talkcut.transcribe import HOTWORDS, load_audio


def run(audio, model, device, compute_type):
    whisper = WhisperModel(model, device=device, compute_type=compute_type)
    t = time.time()
    segments, _ = whisper.transcribe(audio, word_timestamps=True, hotwords=HOTWORDS,
                                     condition_on_previous_text=False)
    words = [(w.word.strip(), w.start) for s in segments for w in s.words]
    return words, time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--length", type=float, default=300)
    ap.add_argument("--model", default="base")
    args = ap.parse_args()

    audio = load_audio(args.media)[int(args.start * 16000):int((args.start + args.length) * 16000)]
    out = {}
    for device, ct in (("cpu", "int8"), ("mps", "float16")):
        words, took = run(audio, args.model, device, ct)
        fillers = len(find_fillers([{"text": w} for w, _ in words]))
        print(f"{device}/{ct}: {took:.1f} s, {len(words)} words, {fillers} fillers", flush=True)
        out[device] = words

    a, b = out["cpu"], out["mps"]
    key = lambda words: [re.sub(r"[^\w]", "", w.lower()) for w, _ in words]  # ignore punctuation
    sm = difflib.SequenceMatcher(None, key(a), key(b), autojunk=False)
    print(f"\nword agreement {sm.ratio():.1%}; stretches that differ by 4+ words:")
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal" and (i2 - i1) + (j2 - j1) >= 4:
            at = args.start + (a[i1][1] if i1 < len(a) else b[j1][1])
            print(f"  {at:7.1f} s  cpu {i2 - i1:3d} words: {' '.join(w for w, _ in a[i1:i2])[:80]}")
            print(f"  {'':9s}  mps {j2 - j1:3d} words: {' '.join(w for w, _ in b[j1:j2])[:80]}")


if __name__ == "__main__":
    main()
