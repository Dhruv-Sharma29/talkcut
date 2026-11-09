# talkcut — brief

## Objective

Build an offline editor for spoken audio where the transcript is the timeline: transcribe locally,
delete words in the text, and get an audio file with those stretches removed. Test whether this
core loop can run well enough on an ordinary laptop to replace a paid cloud editor for podcast
cleanup.

## Why this

Text-based editing is a proven product. Descript sells it on subscription (plans listed at
roughly $16–50 per person per month, **[verify]** on descript.com before quoting). The open
alternatives are young and split:

| Project | Stars (GitHub API, 2026-11-09) | Notes |
| --- | --- | --- |
| [wassgha/rescript](https://github.com/wassgha/rescript) | 1,050 | Created 2026-07-26. Browser-based, video-first, licence unclear |
| [bugbakery/audapolis](https://github.com/bugbakery/audapolis) | 1,907 | AGPL, spoken-word audio, slower development |
| [OpenCut-app/OpenCut](https://github.com/OpenCut-app/OpenCut) | 97,862 | General video editor. Has transcript generation; transcript *editing* is an open request (issue #487) |

rescript going from zero to about a thousand stars in three and a half months is the clearest
demand signal found. OpenCut adding transcript editing is the main risk.

The gap talkcut aims at: **audio first, fully local, fast on a laptop**, with filler-word removal
and a headless mode for scripts.

## Minimum viable scope

- Local transcription with word-level timestamps (faster-whisper).
- A browser editor served from localhost: select words, delete, undo, preview that skips cuts.
- Export to a new audio file through ffmpeg. The source file is never modified.
- Filler-word marking, and a headless `--remove-fillers` mode.

## Stack

Python with faster-whisper for transcription, the standard library for the local server, ffmpeg
for rendering, and one plain HTML/JS page for the editor. No framework, no build step.

```text
audio file -> Whisper (word timestamps) -> transcript JSON -> browser editor
                                                 ^                |
                                                 |      deleted word indices
                                                 +--- cut planner <+
                                                          |
                                                    ffmpeg render -> edited file
```

## Implementation stages

1. **Core loop:** transcribe, delete words, preview, export audio.
2. **Long episodes:** 60-minute files, progress while transcribing, editor stays responsive.
3. **Edit quality:** measure filler recall and cut audibility; shorten long pauses.
4. **Video and hand-off:** cut video too, export an edit list for Resolve/Premiere, packaging.

## Evaluation

Report on a fixed set of clips: transcription speed as a real-time factor per Whisper model,
filler recall against a hand-labelled clip, export time against cut count, and a listening check
for clicks at joints. Record the machine for every number.

## Important tests

- Cut planning: deletions at the start, middle and end, adjacent runs, everything deleted, padding
  that would overlap.
- Filler detection ignores case and punctuation.
- A rendered file's duration equals the sum of the kept ranges.
- Edits are saved as they are made, so a crash or reload loses nothing.
