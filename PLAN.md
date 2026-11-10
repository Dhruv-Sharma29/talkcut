# talkcut: execution plan

Brief: [SPEC.md](SPEC.md). Question:

> Can a fully local transcript editor on a 16 GB Apple-silicon laptop make clean edits to an
> hour-long podcast fast enough to replace a paid cloud editor for that job?

## Progress (2026-11-09)

| Milestone | State |
| --- | --- |
| M1 core loop | **Done.** Transcribe, edit, preview, export, headless filler removal, snapping to pauses; checked on a real 59-min podcast |
| M2 long episodes | **Mostly done.** 59 min: transcribe 153 s, editor responsive at 10,755 words, export 16.8 s. Other model sizes not timed |
| M3 edit quality | **Started.** Hotwords: 3 → 17 fillers on a 5-min excerpt; cut-neighbour check 31/34 snapped vs 28/34 unsnapped; detection deterministic but window-sensitive (8 of 21 spots stable). No labelled ground truth yet |
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
- [x] Cut planner: runs of deleted words become cut ranges, padded and clamped.
- [x] ffmpeg render with short fades at each joint; output length matches the plan.
- [x] Transcription with word timestamps, cached next to the media file.
- [x] Editor: select and delete, undo, preview skips cuts, export.
- [x] Edits saved on every change (checked: survive a page reload).
- [x] Headless filler removal.
- [x] Snap cut edges to pauses; never bring back a deleted word. *Added: not in the original
      plan. Whisper timestamps were up to ~220 ms off and clipped surviving words.*
- [x] End-to-end run on a synthetic clip (macOS `say`), timings in README.
- [x] End-to-end run on a real recording (NASA podcast ep. 440, README).

### M2 — Long episodes
- [x] 60-minute episode, `base`: 180 s for 59 min, 2.5 GB peak.
- [ ] Same for `tiny` and `small`.
- [x] Transcription progress in the UI instead of a blocking request (background thread + polling).
- [x] Editor stays responsive with ~10k words. *Selection was 4.2 s for 2,000 words; now 0.2 ms.*
- [x] Export an hour with ~100 cuts: 16.8 s. *Was 72 s; one seeked input per range.*

### M3 — Edit quality
- [x] Filler counts: plain 0, initial prompt 3, hotwords 17 on the same 5-min excerpt.
      *The prompt only conditions the first 30 s window; replaced by hotwords.*
- [x] Cut-neighbour check (`bench/real_clip.py`): snapped 31/34, unsnapped 28/34.
- [ ] Hand-label fillers in one clip to measure recall and precision properly.
- [x] Find out why the same excerpt gave 17 fillers, then 23. *Not randomness: the same
      samples always give the same transcript. Inaudible changes shift Whisper's 30 s windows;
      six such versions found 21 spots, only 8 by all (`bench/stability.py`).*
- [ ] Decide on two-pass union detection, once the labelled clip says whether the extra spots
      are real.
- [ ] Listening test: fades vs crossfades at joints.
- [ ] Optional pause shortening (cap silences at N ms).

### M4 — Video and hand-off
- [ ] Cut video with the same plan.
- [ ] Export an edit list (EDL or FCPXML) instead of rendering.
- [ ] Install with one command (pipx/uv tool, Homebrew later).
