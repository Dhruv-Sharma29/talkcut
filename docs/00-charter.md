# 00 — Charter

## The problem

Cleaning up a spoken recording means finding the "um"s, false starts and long pauses and cutting
them out. In a waveform editor that is slow: you hunt by ear. Transcript editors fix this by
letting you delete words in text, and the audio follows. The best-known ones run in the cloud on
a subscription, upload your recordings, and cap hours per plan.

The question this project asks:

> Can a fully local transcript editor on a 16 GB Apple-silicon laptop make clean edits to an
> hour-long podcast fast enough to replace a paid cloud editor for that job? (PLAN.md)

"Clean" and "fast enough" are made concrete in the success criteria below.

## What it does

**Input:** an audio file.

**Output:**
1. A transcript with word timestamps, saved next to the file as `<name>.talkcut.json`. The edits
   live in the same file.
2. A new audio file with the deleted words removed. The original is never touched.

## Scope

### In
- Audio: anything ffmpeg can decode.
- Local transcription with faster-whisper; the model is downloaded once and then runs offline.
- Word-level deletion, undo, preview that skips cuts, filler marking, export.
- A headless mode for batch filler removal.

### Out (for now)
- **Video.** M4. The cut plan is media-agnostic, so this is rendering work, not a redesign.
- **Overdub / voice cloning.** A different product with different risks.
- **Multitrack and speaker separation.** Single-track recordings only.
- **Cloud anything.** No accounts, no upload, no telemetry.

## Success criteria (targets until measured)

| Criterion | Target | Measured by |
| --- | --- | --- |
| Transcription speed on the M4, `base` model | 60 min episode in under 10 min | **Met:** 59 min in 180 s (README) |
| Export time | under 30 s for 60 min with 300 cuts | M2 timing run |
| Joints | no audible clicks in a blind listen | M3 listening test |
| Filler recall | reported, with and without hotwords | M3 labelled clip |
| No data loss | edits survive reload and crash | test + manual check |
