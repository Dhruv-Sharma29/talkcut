# 01 — Architecture

## Data flow

```text
file.mp3 ──ffmpeg──> 16 kHz mono samples ──> faster-whisper ──> words + timestamps
                              │                                       │
                              └──> loudness per 10 ms                 v
                                          │                  file.mp3.talkcut.json
                                          │                  (words, deleted, duration)
                                          v                           │
              plan_cuts(words, deleted) ──> snap_to_silence ──> cuts ─┼──> preview (browser)
                                                                      └──> render (ffmpeg)
```

## Design rules

**Rule 1: the source file is never written.** The project is a sidecar JSON file next to the
media; exports go to a new `file.edited.ext`. A bug in talkcut can lose edits, never recordings.

**Rule 2: one place decides cuts.** `edit.final_cuts` is the only function that turns edits into
time ranges. The browser sends deleted word indices and receives cuts back; it never computes
them. The filler list lives in Python too, and the page receives filler indices. This is what
keeps preview and export identical.

**Rule 3: edits are saved as they happen.** Every change POSTs the full deleted set, and the
server writes it atomically (temp file, then `os.replace`). Reloading the page or killing the
server loses at most the change in flight.

**Rule 4: local only.** The server binds to `127.0.0.1`. The only network access is the
one-time model download done by faster-whisper.

Binding to `127.0.0.1` keeps other machines out, not other web pages: any site open in the
browser can send requests to localhost. Before this was handled, a page on another origin could
overwrite the edits and trigger an export with a plain `text/plain` POST (checked in a browser).
So the server refuses:

- requests whose `Host` isn't `127.0.0.1:<port>` or `localhost:<port>` (DNS rebinding, where a
  hostile domain resolves to 127.0.0.1 and reads the transcript as if same-origin);
- requests with an `Origin` from anywhere else;
- POSTs that aren't `application/json`. That type needs a CORS preflight, and the server never
  approves one.

## Components

| File | Role |
| --- | --- |
| `talkcut/edit.py` | Filler detection, cut planning, snapping, render. Pure functions apart from the ffmpeg calls |
| `talkcut/transcribe.py` | ffmpeg decode, faster-whisper, the project file (load, atomic save) |
| `talkcut/server.py` | Stdlib HTTP server: page, media with range requests, JSON API; transcribes in a background thread |
| `talkcut/cli.py` | Argument parsing; editor mode or headless `--remove-fillers` |
| `talkcut/web/index.html` | The editor. Plain HTML, CSS and JS; no build step |

## Cut planning

Each run of adjacent deleted words becomes one cut, and the cut also takes the silence around
the run. `PAD` (50 ms) of that silence is left next to each surviving neighbour, but the pad
never reaches into a deleted word: in tight speech the cut starts or ends exactly at the deleted
word's timestamp. A run at the start or end of the file cuts to the file edge.

## Snapping to pauses

Whisper's word timestamps are approximate. On the test clip they were up to ~220 ms off, enough
to clip a surviving word (README, "What has been measured"). So after planning:

1. Loudness is measured per 10 ms frame. A frame is *quiet* below 5% of the 95th-percentile
   frame level.
2. A **pause** is at least 40 ms of consecutive quiet frames.
3. If a cut's start lands in sound (the kept word before it is still going), the start moves
   forward to the next pause, `PAD` into it.
4. If a cut's end has sound just before it (the kept word after it already started), the end
   moves back to the previous pause, `PAD` before the speech.
5. No edge moves more than 300 ms.
6. **No edge moves far enough to keep more than 100 ms of a deleted word's timestamped span.**
   When words run together with no usable pause, the planned edge wins.

Rule 6 exists because of a real failure: deleting "the first" in "the first one", with 50 ms gaps
around "first", let step 4 walk back to the gap between "the" and "first" and keep "first".
`test_snapping_never_brings_back_a_deleted_word` reproduces it.

Known weak spots: the quiet threshold is relative, so steady background noise can hide pauses;
40 ms is close to the length of a stop consonant's closure (the silent moment inside "open"), so
a pause can be found inside a word. Both are M3 measurements.

## Rendering

Each kept range is its own ffmpeg input, seeked with `-ss`/`-t`, so every part of the file is
decoded once. Each gets a 10 ms fade in and out, then `concat` joins them. The graph is passed as
a file (`-/filter_complex`, ffmpeg 7+) so hundreds of cuts don't hit argument-length limits.

The first version used one input and one `atrim` branch per range. ffmpeg then hands every
decoded frame to every branch, so cost grows with ranges × duration: 72 s for a 57-minute export
with 93 ranges, against 17 s now. One input per range means one open file per range, and macOS
shells default to 256 open files; `render` raises the soft limit toward the hard limit before
calling ffmpeg. `uv run` raises it on its own, which hides the problem in development. Fades rather than crossfades: simpler, and a crossfade would
shorten the output by the overlap. Whether fades are enough to make joints inaudible is the M3
listening test.

## Preview

The browser plays the original file and jumps over cuts. A `requestAnimationFrame` loop checks the
position every frame while the tab is visible; `timeupdate` covers background tabs, where browsers
pause rAF, at about 4 checks a second. The server answers HTTP range requests so the audio element
can seek.
