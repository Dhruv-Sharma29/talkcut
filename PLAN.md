# talkcut: execution plan

Brief: [SPEC.md](SPEC.md). Question:

> Can a fully local transcript editor on a 16 GB Apple-silicon laptop make clean edits to an
> hour-long podcast fast enough to replace a paid cloud editor for that job?

## Progress (2026-11-09)

| Milestone | State |
| --- | --- |
| M1 core loop | **In progress.** |
| M2 long episodes | Not started |
| M3 edit quality | Not started |
| M4 video and hand-off | Not started |

## Layout

```text
talkcut/
  talkcut/
    edit.py        deleted words -> cut ranges; filler detection; ffmpeg render
    transcribe.py  faster-whisper -> transcript JSON with word timestamps
    server.py      localhost server: editor page, media with range requests, JSON API
    cli.py         `talkcut file` opens the editor; `--remove-fillers -o out` runs headless
    web/index.html the editor
  tests/  docs/
```

## Milestones

### M1 — Core loop
- [ ] Cut planner: runs of deleted words become cut ranges, padded and clamped.
- [ ] ffmpeg render with short fades at each joint; output length matches the plan.
- [ ] Transcription with word timestamps, cached next to the media file.
- [ ] Editor: select and delete, undo, preview skips cuts, export.
- [ ] Edits saved on every change.
- [ ] Headless filler removal.
- [ ] End-to-end run on a real clip, with timings recorded.

### M2 — Long episodes
- [ ] 60-minute episode: real-time factor for `tiny`, `base`, `small` on the M4.
- [ ] Transcription progress in the UI instead of a blocking request.
- [ ] Editor stays responsive with ~10k words.

### M3 — Edit quality
- [ ] Hand-label fillers in one clip; measure recall with and without the verbatim prompt.
- [ ] Listening test: fades vs crossfades at joints.
- [ ] Optional pause shortening (cap silences at N ms).

### M4 — Video and hand-off
- [ ] Cut video with the same plan.
- [ ] Export an edit list (EDL or FCPXML) instead of rendering.
- [ ] Install with one command (pipx/uv tool, Homebrew later).
