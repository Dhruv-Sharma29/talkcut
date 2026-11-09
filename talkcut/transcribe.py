"""Local transcription with word timestamps, and the project file that holds the edits.

The project file sits next to the media as `<file>.talkcut.json`. It is the whole project:
transcript, deleted word indices, and the model used. The media file itself is never written.
"""

import json
import os
import subprocess

# Whisper tends to tidy speech up and leave out "um"/"uh". Priming it with disfluent text
# makes it keep them more often. How much more is an open question for M3.
VERBATIM_PROMPT = "Umm, let me think like, hmm... Okay, here's what I'm, like, thinking."


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


def transcribe(media, model="base", language=None, on_progress=None):
    from faster_whisper import WhisperModel  # slow import; only pay for it when transcribing

    whisper = WhisperModel(model, device="auto", compute_type="int8")
    segments, info = whisper.transcribe(
        load_audio(media), word_timestamps=True, initial_prompt=VERBATIM_PROMPT,
        language=language,
    )
    words = []
    for seg in segments:  # a generator: transcription happens as we iterate
        words += [
            {"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
            for w in seg.words
        ]
        if on_progress:
            on_progress(min(seg.end / info.duration, 1.0))
    return {
        "media": os.path.basename(media),
        "duration": round(info.duration, 3),
        "language": info.language,
        "model": model,
        "words": words,
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
