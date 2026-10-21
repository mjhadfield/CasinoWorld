"""Serving the web export's engine: the brotli or gzip copy when the browser takes it and it's up to date,
and a 304 on a reload (docs/performance.md)."""
import gzip
import os

import pytest

from casino_server import app as app_module


@pytest.fixture
def web(tmp_path, monkeypatch):
    d = tmp_path / "web"
    d.mkdir()
    (d / "index.wasm").write_bytes(b"\0asm plain")
    (d / "index.wasm.br").write_bytes(b"brotli bytes")
    (d / "index.wasm.gz").write_bytes(gzip.compress(b"\0asm plain"))
    (d / "index.js").write_text("// loader")
    monkeypatch.setattr(app_module, "WEB_EXPORT_DIR", d)
    return d


def test_engine_is_sent_compressed_when_taken(client, web):
    r = client.get("/index.wasm", headers={"Accept-Encoding": "gzip, br"})
    assert r.status_code == 200
    assert r.headers["content-encoding"] == "br"
    assert r.headers["content-type"] == "application/wasm"
    assert r.headers["cache-control"] == "no-cache"
    r = client.get("/index.wasm", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip"
    assert r.content == b"\0asm plain"   # (the test client unpacks it)


def test_plain_when_not_taken_or_no_copy(client, web):
    r = client.get("/index.wasm", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in r.headers
    assert r.content == b"\0asm plain"
    r = client.get("/index.js", headers={"Accept-Encoding": "br"})   # (no compressed copy of it)
    assert "content-encoding" not in r.headers
    assert r.text == "// loader"


def test_a_stale_copy_is_not_sent(client, web):
    """Mid-export the file is newer than its copies: the plain file goes out until they're redone."""
    later = os.stat(web / "index.wasm.br").st_mtime + 10
    os.utime(web / "index.wasm", (later, later))
    r = client.get("/index.wasm", headers={"Accept-Encoding": "br, gzip"})
    assert "content-encoding" not in r.headers
    assert r.content == b"\0asm plain"


def test_a_reload_gets_304(client, web):
    first = client.get("/index.wasm", headers={"Accept-Encoding": "br"})
    again = client.get("/index.wasm", headers={"Accept-Encoding": "br", "If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    assert again.content == b""


def test_index_page_is_revalidated(client, web):
    (web / "index.html").write_text("<html></html>")
    assert client.get("/").headers["cache-control"] == "no-cache"
