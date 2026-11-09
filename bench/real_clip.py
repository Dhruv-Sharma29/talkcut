"""Real-recording check: how many fillers the transcript keeps, and whether cuts damage the
words next to them.

    uv run python bench/real_clip.py samples/episode.mp3 --start 600 --length 300

Nobody listens here, so Whisper is the judge. For every cut, the kept word just before it and
just after it should still be in the export, at the time the cut plan predicts. Each export is
transcribed again and those neighbour words are looked up (same text, within 0.75 s).

Whole-transcript diffs are no good for this: removing audio shifts Whisper's 30 s windows, so
words far from any cut get heard differently ("Matt Dominick" -> "Mathematica"). The baseline
is the same lookup on an export with no cuts, which measures how often Whisper hears those
exact words differently on its own.
"""

import argparse
import os
import re
import subprocess
import time

import numpy as np

from talkcut import edit
from talkcut.transcribe import load_audio, transcribe


def norm(s):
    return re.sub(r"[^\w]", "", s.lower())


def neighbours(words, deleted, cuts):
    """The kept word right before and right after each cut."""
    kept = [w for i, w in enumerate(words) if i not in deleted]
    out = []
    for a, b in cuts:
        before = [w for w in kept if w["end"] <= a + 0.15]
        after = [w for w in kept if w["start"] >= b - 0.15]
        out += before[-1:] + after[:1]
    return out


def shifted(t, cuts):
    """Where time t of the source lands in the export."""
    return t - sum(min(b, t) - a for a, b in cuts if a < t)


def survived(words, cuts, again):
    return sum(
        any(norm(x["text"]) == norm(w["text"]) and abs(x["start"] - shifted(w["start"], cuts)) < 0.75
            for x in again)
        for w in words
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--length", type=float, default=300)
    ap.add_argument("--model", default="base")
    args = ap.parse_args()

    base = os.path.splitext(args.media)[0] + f".clip{int(args.start)}"
    clip = base + ".wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(args.start), "-t", str(args.length),
                    "-i", args.media, "-ac", "1", clip], check=True)

    t = time.time()
    a = transcribe(clip, args.model)
    t_a = time.time() - t
    plain = transcribe(clip, args.model, verbatim=False)
    fillers = edit.find_fillers(a["words"])
    levels = edit.frame_levels(load_audio(clip))
    quiet = levels < 0.05 * np.percentile(levels, 95)
    voiced = sum(
        1 - quiet[int(a["words"][i]["start"] * 100) : int(a["words"][i]["end"] * 100) + 1].mean() > 0.3
        for i in fillers
    )
    print(f"clip {args.length:.0f}s from {args.start:.0f}s, model {args.model}: "
          f"{len(a['words'])} words, transcribed in {t_a:.1f}s")
    print(f"fillers found: {len(fillers)} verbatim ({voiced} with sound under them), "
          f"{len(edit.find_fillers(plain['words']))} plain")

    project = dict(a, deleted=fillers)
    snapped = edit.final_cuts(project, levels)
    planned = edit.final_cuts(project, None)
    nbrs = neighbours(a["words"], set(fillers), snapped)

    print("\n| Export | Cuts | Length | Neighbour words found | Fillers left |")
    print("| --- | --- | --- | --- | --- |")
    for name, deleted, lv, cuts in [
        ("no cuts (baseline)", [], levels, []),
        ("fillers, snapped", fillers, levels, snapped),
        ("fillers, not snapped", fillers, None, planned),
    ]:
        out = f"{base}.{name.split(',')[-1].split()[0]}.wav"
        length = edit.export(dict(a, deleted=deleted), clip, out, lv)
        again = transcribe(out, args.model)["words"]
        found = survived(nbrs, cuts, again)
        print(f"| {name} | {len(cuts)} | {length:.1f}s | {found} of {len(nbrs)} | "
              f"{len(edit.find_fillers(again))} |")


if __name__ == "__main__":
    main()
