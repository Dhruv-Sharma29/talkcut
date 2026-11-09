"""Localhost server for the editor: the page, the media file, and a small JSON API.

GET  /              the editor
GET  /media         the source file, with HTTP range support so the browser can seek
GET  /api/project   {"status": "transcribing", "progress"} | {"status": "ready", "project", "cuts"}
POST /api/edits     {"deleted": [word indices]} -> saved immediately; returns the new cuts
POST /api/export    renders to <name>.edited.<ext> next to the source
"""

import json
import mimetypes
import os
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from . import edit
from .transcribe import load_audio, load_or_transcribe, project_path, save


class State:
    def __init__(self, media, model):
        self.media, self.model = media, model
        self.project, self.levels, self.progress, self.error = None, None, 0.0, None
        self.lock = threading.Lock()

    def start_transcription(self):
        def work():
            try:
                project = load_or_transcribe(
                    self.media, self.model, on_progress=lambda p: setattr(self, "progress", p)
                )
                self.levels = edit.frame_levels(load_audio(self.media))
                self.project = project  # last: the page treats a project as ready to edit
            except Exception as e:  # shown in the page instead of dying in a thread
                self.error = f"{type(e).__name__}: {e}"

        threading.Thread(target=work, daemon=True).start()

    def cuts(self):
        return edit.final_cuts(self.project, self.levels)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send_json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            if self.path == "/":
                body = files("talkcut").joinpath("web/index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/media":
                self.send_media()
            elif self.path == "/api/project":
                if state.error:
                    self.send_json({"status": "error", "error": state.error})
                elif state.project is None:
                    self.send_json({"status": "transcribing", "progress": state.progress})
                else:
                    with state.lock:
                        self.send_json({
                            "status": "ready", "project": state.project, "cuts": state.cuts(),
                            "fillers": edit.find_fillers(state.project["words"]),
                        })
            else:
                self.send_error(404)

        def do_POST(self):
            if state.project is None:
                return self.send_json({"error": "still transcribing"}, 409)
            if self.path == "/api/edits":
                deleted = self.read_json().get("deleted")
                n = len(state.project["words"])
                if not isinstance(deleted, list) or not all(
                    isinstance(i, int) and 0 <= i < n for i in deleted
                ):
                    return self.send_json({"error": "deleted must be a list of word indices"}, 400)
                with state.lock:
                    state.project["deleted"] = sorted(set(deleted))
                    save(state.project, project_path(state.media))
                    self.send_json({"cuts": state.cuts()})
            elif self.path == "/api/export":
                dst = edit.edited_path(state.media)
                try:
                    with state.lock:
                        length = edit.export(state.project, state.media, dst, state.levels)
                except (RuntimeError, ValueError) as e:
                    return self.send_json({"error": str(e)}, 500)
                self.send_json({"path": dst, "duration": round(length, 2)})
            else:
                self.send_error(404)

        def send_media(self):
            size = os.path.getsize(state.media)
            start, end = 0, size - 1
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            if m and (m[1] or m[2]):
                if m[1]:
                    start = int(m[1])
                    end = min(int(m[2]), size - 1) if m[2] else size - 1
                else:  # suffix range: the last N bytes
                    start = max(size - int(m[2]), 0)
                if start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    return self.end_headers()
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(200)
            kind = mimetypes.guess_type(state.media)[0] or "application/octet-stream"
            self.send_header("Content-Type", kind)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            try:
                with open(state.media, "rb") as f:
                    f.seek(start)
                    left = end - start + 1
                    while left > 0:
                        chunk = f.read(min(1 << 16, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser cancels range requests all the time while seeking

    return Handler


def serve(media, model="base", port=8765, open_browser=True):
    state = State(media, model)
    state.start_transcription()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    url = f"http://127.0.0.1:{port}/"
    print(f"talkcut: editing {os.path.basename(media)} at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
