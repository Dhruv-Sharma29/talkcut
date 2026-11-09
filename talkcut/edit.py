"""Deleted words -> cut ranges -> rendered audio.

All cut decisions live here. The editor only sends the indices of deleted words, so preview
and export can never disagree about what gets removed.
"""

import os
import re
import subprocess
import tempfile

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "erm", "er", "ah", "hmm", "mm", "mhm"}
PAD = 0.05  # seconds of silence kept next to a surviving word, so cuts don't clip it
FADE = 0.01  # fade at each joint; hides the click a hard cut makes


def find_fillers(words):
    """Indices of words that are filler sounds, ignoring case and punctuation."""
    return [i for i, w in enumerate(words) if re.sub(r"[^\w]", "", w["text"].lower()) in FILLERS]


def plan_cuts(words, deleted, duration, pad=PAD):
    """Turn deleted word indices into (start, end) ranges to remove, in seconds.

    Each run of adjacent deleted words becomes one cut, which also takes the silence around
    it. `pad` seconds of that silence are left next to the surviving neighbours, but the pad
    never reaches into a deleted word: if the gap is tighter than the pad, the cut starts or
    ends exactly at the deleted word.
    """
    deleted = set(deleted)
    cuts = []
    i, n = 0, len(words)
    while i < n:
        if i not in deleted:
            i += 1
            continue
        j = i
        while j < n and j in deleted:
            j += 1
        start = min(words[i - 1]["end"] + pad, words[i]["start"]) if i > 0 else 0.0
        end = max(words[j]["start"] - pad, words[j - 1]["end"]) if j < n else duration
        if end > start:
            cuts.append((round(start, 3), round(end, 3)))
        i = j
    return cuts


def keep_ranges(cuts, duration):
    """The complement of `cuts` within [0, duration]."""
    keep, t = [], 0.0
    for a, b in cuts:
        if a > t:
            keep.append((t, a))
        t = max(t, b)
    if t < duration:
        keep.append((t, duration))
    return keep


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def render(src, dst, keep, fade=FADE):
    """Write the `keep` ranges of `src` back to back into `dst`, fading each joint.

    The output format follows dst's extension. Needs ffmpeg 7 or newer (the graph is passed
    as a file with `-/filter_complex`, so hundreds of cuts don't hit argument-length limits).
    """
    # ponytail: one atrim branch per segment; fine for hundreds of cuts, measure in M2 before
    # assuming it holds for thousands.
    parts, labels = [], []
    for k, (a, b) in enumerate(keep):
        d = b - a
        if d < 2 * fade:
            continue
        parts.append(
            f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={fade},afade=t=out:st={d - fade:.3f}:d={fade}[a{k}]"
        )
        labels.append(f"[a{k}]")
    if not labels:
        raise ValueError("nothing left to export: every word is deleted")
    graph = ";".join(parts) + f";{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]"

    with tempfile.NamedTemporaryFile("w", suffix=".ffgraph", delete=False) as f:
        f.write(graph)
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", src, "-/filter_complex", f.name,
             "-map", "[out]", dst],
            capture_output=True, text=True,
        )
    finally:
        os.unlink(f.name)
    if r.returncode:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.strip()}")
