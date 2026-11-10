# AGENTS.md

Instructions for AI coding agents working in this repository. Humans: see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Commands

```bash
uv sync                                                    # install
uv run pytest                                              # all tests, seconds, no network
uv run talkcut file.mp3 --no-browser                       # editor server on 127.0.0.1:8765
uv run talkcut file.mp3 --remove-fillers -o out.mp3        # headless
uv run python bench/real_clip.py file.mp3 --start 600      # filler count + cut damage
uv run python bench/stability.py file.mp3 --start 600      # filler stability
```

ffmpeg 7+ must be on PATH. Benchmarks download a Whisper model on first run and take minutes.

## Layout

| Path | Role |
| --- | --- |
| `talkcut/edit.py` | Filler detection, cut planning, snapping to pauses, ffmpeg render. Pure functions except the ffmpeg calls |
| `talkcut/transcribe.py` | ffmpeg decode, faster-whisper, project file load and atomic save |
| `talkcut/server.py` | Stdlib HTTP server: page, media with range requests, JSON API, background transcription |
| `talkcut/cli.py` | Argument parsing; editor mode or headless |
| `talkcut/web/index.html` | The whole editor. Plain HTML/CSS/JS, no build step |
| `tests/test_edit.py` | Unit tests; synthetic audio only |
| `bench/` | Real-recording measurements; their output is what the README quotes |
| `docs/` | Design record. `01-architecture.md` explains the rules below |

## Invariants: don't break these

- Never write to the source media file. Edits go to `<media>.talkcut.json`, exports to
  `edit.edited_path(media)`.
- `edit.final_cuts` is the only code that turns edits into time ranges. Don't compute cuts or the
  filler list in JavaScript; the page receives both from the server.
- Saves are atomic: write a temp file, then `os.replace`.
- The server binds to `127.0.0.1` only. No network calls besides faster-whisper's model download.
- Snapping never moves a cut edge far enough to keep more than 0.1 s of a deleted word
  (`test_snapping_never_brings_back_a_deleted_word`).

## Things that will surprise you

- **Whisper word timestamps are off by up to ~220 ms.** That's why cut edges snap to measured
  pauses. Don't cut at raw timestamps.
- **Whisper drops fillers** unless asked. `transcribe.HOTWORDS` keeps them in every 30 s
  window; an `initial_prompt` only affects the first window.
- **Transcription is deterministic but fragile.** Same samples, same words. Inaudibly different
  audio shifts the 30 s windows and changes which fillers appear.
- **`load_audio` decodes with ffmpeg on purpose**, not PyAV: faster-whisper 1.2.1 passes an
  argument PyAV 19 removed.
- **`render` opens the source once per kept range.** macOS shells allow 256 open files;
  `_allow_open_files` raises the limit. `uv run` raises it too, hiding failures; test with
  `.venv/bin/python` under `ulimit -n 256`.
- **The filter graph goes in a file** (`-/filter_complex`, ffmpeg 7+) so hundreds of cuts don't
  hit argument-length limits.

## Conventions

- Standard library first. Don't add a dependency without an issue that agrees to it.
- A behaviour change in `edit.py` needs a test. Tests must not download models or need real
  recordings.
- Numbers in README or docs must come from a run you actually did, with the machine and clip
  named, and a `bench/` script that reproduces them. Never estimate and present it as measured;
  mark unchecked claims **[verify]**.
- Never commit audio or `*.talkcut.json` files.
- Keep docs plain and short, in the style already there.
