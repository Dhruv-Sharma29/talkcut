import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from talkcut.server import State, make_handler


@pytest.fixture
def server(tmp_path):
    media = tmp_path / "a.wav"
    media.write_bytes(b"RIFF")
    state = State(str(media), "base")
    state.project = {"media": "a.wav", "duration": 2.0, "words": [
        {"text": "So", "start": 0.0, "end": 0.5}, {"text": "um,", "start": 0.6, "end": 1.0},
    ], "deleted": []}
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], state
    srv.shutdown()
    srv.server_close()


def request(port, method, path, host=None, body=None, **headers):
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.putrequest(method, path, skip_host=True)
    c.putheader("Host", host or f"127.0.0.1:{port}")
    for k, v in headers.items():
        c.putheader(k.replace("_", "-"), v)
    data = (body or "").encode()
    c.putheader("Content-Length", str(len(data)))
    c.endheaders(data)
    return c.getresponse().status


EDIT = json.dumps({"deleted": [1]})
JSON = {"Content_Type": "application/json"}


def test_the_editor_page_can_read_and_edit(server):
    port, state = server
    assert request(port, "GET", "/api/project") == 200
    assert request(port, "GET", "/api/project", host=f"localhost:{port}") == 200
    assert request(port, "POST", "/api/edits", body=EDIT,
                   Origin=f"http://127.0.0.1:{port}", **JSON) == 200
    assert state.project["deleted"] == [1]


def test_requests_another_site_could_forge_are_refused(server):
    port, state = server
    # DNS rebinding: a hostile domain pointed at 127.0.0.1 reads the transcript as same-origin.
    assert request(port, "GET", "/api/project", host=f"evil.example:{port}") == 403
    assert request(port, "GET", "/media", host=f"evil.example:{port}") == 403
    # A page on another site posting edits. Plain cross-site fetch carries its Origin...
    assert request(port, "POST", "/api/edits", body=EDIT, Origin="https://evil.example", **JSON) == 403
    assert request(port, "POST", "/api/edits", body=EDIT, Origin="null", **JSON) == 403
    # ...and a text/plain body is what a page can send without a CORS preflight.
    assert request(port, "POST", "/api/edits", body=EDIT, Content_Type="text/plain") == 415
    assert request(port, "POST", "/api/export", body="{}", Content_Type="text/plain") == 415
    assert state.project["deleted"] == []
