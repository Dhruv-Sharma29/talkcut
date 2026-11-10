# Security

## Reporting a vulnerability

Please don't open a public issue for a security problem. Use GitHub's private reporting: the
**Security** tab of this repository, then **Report a vulnerability**. You'll get a reply within
a week.

## What's in scope

talkcut runs on your own machine. The parts where a security bug would matter:

- **The editor's local HTTP server** (`talkcut/server.py`). It binds to `127.0.0.1`, but other
  software on the same machine, including web pages open in your browser, can try to reach it.
  Anything that lets a web page read your transcript or audio, change your edits, or write files
  through the server is in scope.
- **File handling**: anything that makes talkcut write somewhere other than the project file
  next to the media or the chosen export path, or modify the source media.
- **ffmpeg invocation**: anything that lets a crafted file name or project file inject arguments.

Out of scope: vulnerabilities in ffmpeg, faster-whisper or Python themselves (report those
upstream), and attacks that already require running code as your user.

## Supported versions

Only the latest commit on `main` is supported until there are releases.
