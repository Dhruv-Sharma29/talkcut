"""Deleted words -> cut ranges -> rendered audio.

All cut decisions live here. The editor only sends the indices of deleted words, so preview
and export can never disagree about what gets removed.
"""

import bisect
import os
import re
import subprocess
import tempfile

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "erm", "er", "ah", "hmm", "mm", "mhm"}
PAD = 0.05  # seconds of silence kept next to a surviving word, so cuts don't clip it
FADE = 0.01  # fade at each joint; hides the click a hard cut makes
FRAME = 0.01  # seconds per loudness frame used for snapping


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


def frame_levels(samples, sr=16000):
    """RMS loudness per FRAME of mono samples."""
    import numpy as np

    hop = int(sr * FRAME)
    n = len(samples) // hop
    return np.sqrt((samples[: n * hop].reshape(n, hop) ** 2).mean(axis=1))


def snap_to_silence(cuts, levels, words=(), pad=PAD, min_pause=0.04, max_shift=0.3,
                    tolerance=0.1):
    """Move cut edges that land in sound to the nearest pause in the audio.

    Whisper's word timestamps are often 100-250 ms off, so a cut planned from them can clip
    the start or end of a word that should survive. An edge next to a kept word is moved
    into the nearest run of at least `min_pause` quiet frames, `pad` seconds from the speech,
    and never more than `max_shift` seconds from where it was planned.

    Snapping must not undo the edit: with `words` given, an edge never moves so far that it
    would keep more than `tolerance` seconds of a deleted word's timestamped span. When words
    run together with no usable pause, the planned edge wins.
    """
    import numpy as np

    n = len(levels)
    if not n:
        return cuts
    mids = [(x["start"] + x["end"]) / 2 for x in words]
    # ponytail: "quiet" is relative to the loud end of the file. Fine for clean podcast audio;
    # noisy rooms need a noise-floor estimate instead (M3).
    quiet = levels < 0.05 * np.percentile(levels, 95)
    run, lim = round(min_pause / FRAME), round(max_shift / FRAME)

    def is_pause(k):  # frames k .. k+run-1 are all quiet
        return k >= 0 and k + run <= n and bool(quiet[k : k + run].all())

    out = []
    for a, b in cuts:
        ka, kb = round(a / FRAME), round(b / FRAME)
        inside = words[bisect.bisect_right(mids, a) : bisect.bisect_left(mids, b)]  # deleted
        a_max = round((inside[0]["start"] + tolerance) / FRAME) if inside else kb
        b_min = round((inside[-1]["end"] - tolerance) / FRAME) if inside else ka
        if ka > 0 and not is_pause(ka):  # kept word still sounding at the cut start
            for k in range(ka + 1, min(ka + lim, kb, a_max) + 1):
                if is_pause(k):
                    e = k
                    while e < n and quiet[e]:
                        e += 1
                    a = min(k * FRAME + pad, e * FRAME)
                    break
        if kb < n and not is_pause(kb - run):  # next kept word already started
            for k in range(kb - 1, max(kb - lim, ka, b_min) - 1, -1):
                if is_pause(k - run):
                    s = k - run
                    while s > 0 and quiet[s - 1]:
                        s -= 1
                    b = max(k * FRAME - pad, s * FRAME)
                    break
        if b > a:
            out.append((round(a, 3), round(b, 3)))
    return out


def final_cuts(project, levels=None):
    """The cuts preview and export both use: planned from words, snapped to pauses."""
    words = project["words"]
    cuts = plan_cuts(words, project["deleted"], project["duration"])
    return snap_to_silence(cuts, levels, words) if levels is not None else cuts


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


def edited_path(media):
    base, ext = os.path.splitext(media)
    return f"{base}.edited{ext}"


def export(project, media, dst, levels=None):
    """Render a project's edits. Returns the length of the result in seconds."""
    keep = keep_ranges(final_cuts(project, levels), project["duration"])
    render(media, dst, keep)
    return sum(b - a for a, b in keep)


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
