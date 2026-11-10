# Contributing to talkcut

Thanks for looking. talkcut is small on purpose: one Python package, one HTML page, no build
step. Most useful contributions are either a measurement or a focused change to one module.

## Where to start

- Issues labelled [`good first issue`](https://github.com/Dhruv-Sharma29/talkcut/labels/good%20first%20issue)
  are scoped and say what "done" means.
- Issues labelled [`measurement`](https://github.com/Dhruv-Sharma29/talkcut/labels/measurement)
  need a number, not code: a timing, a labelled clip, a test report. You don't need to know the
  codebase for these.
- Running talkcut on your own recording and reporting what happened is one of the most useful
  things you can do right now. Use the **Recording report** issue form.

Comment on an issue before starting so two people don't build the same thing. For anything not
covered by an issue, open one first and describe the problem before the solution.

## Setup

Requires Python 3.11–3.13, [uv](https://docs.astral.sh/uv/) and **ffmpeg 7 or newer** (render
passes its filter graph with `-/filter_complex`, added in ffmpeg 7).

```bash
brew install ffmpeg        # macOS; on Linux use a static build if your distro's ffmpeg is older than 7
uv sync
uv run pytest              # 15 tests, a few seconds, no model download
uv run talkcut some.mp3    # first run downloads the Whisper model (~140 MB for base)
```

One test checks behaviour above the open-file limit. `uv run` raises that limit itself, so to
see the real macOS default run it without uv: `ulimit -n 256; .venv/bin/python -m pytest`.

## How the code is laid out

Read [docs/01-architecture.md](docs/01-architecture.md) first; it is short. The rules a pull
request must keep:

1. **The source file is never written.** Edits live in `<file>.talkcut.json`; exports go to a
   new file.
2. **One place decides cuts.** `talkcut/edit.py` turns deleted word indices into time ranges.
   The browser never computes cuts, so preview and export can't disagree.
3. **Edits are saved as they happen**, atomically (temp file, then `os.replace`).
4. **Local only.** The server binds to `127.0.0.1` and refuses requests other sites could
   forge; no telemetry, no uploads.

## What a good pull request looks like

- **One issue, one change.** Small diffs get reviewed quickly.
- **Tests for behaviour.** A change to `edit.py` comes with a test in `tests/test_edit.py`.
  Unit tests must not download a model or need a real recording; synthesise audio with numpy
  as the existing tests do.
- **Numbers come with their source.** Any measured claim in the README or docs names the
  machine and the clip, and can be reproduced with a script in `bench/`. A claim you haven't
  checked gets marked **[verify]**.
- **No new dependencies** without discussing it in the issue first. Standard library and ffmpeg
  come first; the editor stays plain HTML, CSS and JS.
- **Say how you tested it** in the pull request: commands run, and for audio changes, what you
  listened to.

AI-assisted contributions are fine. You are responsible for every line: understand it, run the
tests, and never paste numbers you didn't measure.

## Recordings

Never commit audio. `samples/` is gitignored for that reason. If an issue needs a recording,
link to a public-domain or openly licensed source, or describe your own without attaching it.
Don't share recordings of other people without their permission.

## Commit messages

Short and plain: what changed and why, in the first line. `feat:`, `fix:`, `perf:` and `docs:`
prefixes are used here but not required.

## Licence

talkcut is MIT licensed. By contributing, you agree your contribution is released under the same
licence.

## Conduct

Be decent. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
