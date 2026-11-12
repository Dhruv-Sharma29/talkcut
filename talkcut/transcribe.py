"""Local transcription with word timestamps, and the project file that holds the edits.

The project file sits next to the media as `<file>.talkcut.json`. It is the whole project:
transcript, deleted word indices, and the model used. The media file itself is never written.
"""

import json
import os
import subprocess

# Whisper tidies speech up and leaves out "um"/"uh". An initial prompt full of fillers only
# conditions the first 30 s window, and on a real 59-minute podcast it found 1 filler in 10,685
# words. Hotwords are added to every window; with per-window decoding they found 17 fillers in a
# 5-minute excerpt where the prompt found 3, and 16 of the 17 had sound under them (README).
HOTWORDS = "Um, uh, hmm, er, ah"


def project_path(media):
    return media + ".talkcut.json"


def load_audio(media, sr=16000):
    """Decode to mono float32 at Whisper's rate with ffmpeg.

    faster-whisper's own decoder goes through PyAV, and faster-whisper 1.2.1 passes an
    argument PyAV 19 removed. ffmpeg is required for export anyway, so decoding with it drops
    that dependency and means transcription and export read the file the same way.
    """
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", media, "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def speech_gaps(words, speech, duration, slack=0.5, min_speech=1.0, bridge=1.0, frame=0.01):
    """Stretches of detected speech with no transcribed word within `slack` seconds.

    `speech` is a list of (start, end) from a voice detector. Gaps closer than `bridge` seconds
    are joined, and a gap counts only if it holds at least `min_speech` seconds of speech.
    """
    import numpy as np

    n = int(duration / frame) + 1
    gap = np.zeros(n, bool)
    for a, b in speech:
        gap[int(a / frame):int(b / frame)] = True
    for w in words:
        gap[max(0, int((w["start"] - slack) / frame)):int((w["end"] + slack) / frame) + 1] = False
    out, k, join = [], 0, int(bridge / frame)
    while k < n:
        if not gap[k]:
            k += 1
            continue
        e = k
        while e < n and gap[e:e + join].any():
            e += 1
        while not gap[e - 1]:  # don't end on the bridged silence
            e -= 1
        if gap[k:e].sum() * frame >= min_speech:
            out.append((round(k * frame, 2), round(e * frame, 2)))
        k = e
    return out


def fill_gaps(whisper, audio, words, speech, sr=16000, context=0.3, **options):
    """Transcribe speech the main pass skipped, and merge those words in.

    Whisper sometimes jumps over a stretch of speech without a trace: on a 59-minute podcast it
    skipped 9 stretches, about 73 s of speech (README). Each gap is transcribed on its own, with
    `context` seconds either side, and only words centred inside the gap are kept.
    """
    added = []
    for a, b in speech_gaps(words, speech, len(audio) / sr):
        lo = max(0.0, a - context)
        segments, _ = whisper.transcribe(
            audio[int(lo * sr):int((b + context) * sr)], word_timestamps=True, **options
        )
        added += [
            w for w in (
                {"text": x.word.strip(), "start": round(x.start + lo, 3), "end": round(x.end + lo, 3)}
                for s in segments for x in s.words
            )
            if a <= (w["start"] + w["end"]) / 2 <= b
        ]
    return sorted(words + added, key=lambda w: w["start"]), len(added)


def transcribe(media, model="base", language=None, on_progress=None, verbatim=True):
    from faster_whisper import WhisperModel  # slow import; only pay for it when transcribing
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    whisper = WhisperModel(model, device="auto", compute_type="int8")
    options = dict(language=language)
    if verbatim:
        options.update(hotwords=HOTWORDS, condition_on_previous_text=False)
    audio = load_audio(media)
    segments, info = whisper.transcribe(audio, word_timestamps=True, **options)
    words = []
    for seg in segments:  # a generator: transcription happens as we iterate
        words += [
            {"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
            for w in seg.words
        ]
        if on_progress:
            on_progress(0.9 * min(seg.end / info.duration, 1.0))
    vad = VadOptions(min_silence_duration_ms=300, speech_pad_ms=100)
    speech = [(v["start"] / 16000, v["end"] / 16000) for v in get_speech_timestamps(audio, vad)]
    words, recovered = fill_gaps(whisper, audio, words, speech, **options)
    if on_progress:
        on_progress(1.0)
    return {
        "media": os.path.basename(media),
        "duration": round(info.duration, 3),
        "language": info.language,
        "model": model,
        "words": words,
        "recovered": recovered,  # words from speech the main pass skipped (fill_gaps)
        "deleted": [],
    }


def save(project, path):
    """Write atomically, so a crash mid-write can't corrupt the user's edits."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(project, f, indent=1)
    os.replace(tmp, path)


def load_or_transcribe(media, model="base", on_progress=None):
    path = project_path(media)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    project = transcribe(media, model, on_progress=on_progress)
    save(project, path)
    return project
