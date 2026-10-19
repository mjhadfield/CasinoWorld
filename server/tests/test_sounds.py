"""The sound maintenance page's API: pick sounds per moment, upload, and tell the games."""
import pytest

from casino_server import sounds

from conftest import recv_until
from test_ws import join


def test_defaults_are_the_picks_and_every_file_exists(client):
    overview = client.get("/api/sounds").json()
    assert [m["key"] for m in overview["moments"]] == list(sounds.MOMENTS)
    for m in overview["moments"]:
        assert m["is_default"] and m["files"] == sounds.DEFAULTS[m["key"]]["files"], m["key"]
    manifest = client.get("/api/sounds/manifest").json()
    url = manifest["moments"]["flip"]["files"][0]
    assert url.startswith("/sound-files/kenney-casino/card-place-2.ogg?v=")
    assert client.get(url).content[:4] == b"OggS"
    assert len(overview["library"]) > 150 and client.get("/maintenance").status_code == 200


def test_changing_a_moment_saves_it_and_tells_the_games(client, tmp_path):
    with client.websocket_connect("/ws") as ws:
        join(ws)
        r = client.put("/api/sounds/bet", json={"files": ["pops/cogitollc-pop3.ogg", "pops/cogitollc-pop3.ogg"], "gain_db": -40})
        assert r.status_code == 200 and r.json() == {"files": ["pops/cogitollc-pop3.ogg"], "gain_db": -30.0}  # deduped, clamped
        changed = recv_until(ws, "sounds_changed")
    assert changed["version"] == 1
    assert client.get("/api/sounds/manifest").json()["moments"]["bet"]["gain_db"] == -30.0
    # It survives a restart (a fresh board reading the same data dir).
    assert sounds.SoundBoard(tmp_path).choice("bet")["files"] == ["pops/cogitollc-pop3.ogg"]
    assert client.delete("/api/sounds/bet").json()["files"] == sounds.DEFAULTS["bet"]["files"]


def test_bad_requests_are_refused_with_a_reason(client):
    assert client.put("/api/sounds/nope", json={"files": ["pops/cogitollc-pop3.ogg"]}).status_code == 400
    r = client.put("/api/sounds/bet", json={"files": ["../../casino_server/app.py"]})
    assert r.status_code == 400 and "Not in the library" in r.json()["detail"]
    assert client.put("/api/sounds/bet", json={"files": []}).status_code == 400
    assert client.get("/sound-files/../casino_server/app.py").status_code == 404
    assert client.get("/sound-files/%2e%2e/casino_server/app.py").status_code == 404


def test_uploads_can_be_used_and_deleted_once_unused(client):
    ogg = (sounds.LIBRARY_DIR / "pops" / "cogitollc-pop1.ogg").read_bytes()
    r = client.put("/api/sound-uploads/My Chip!.ogg", content=ogg)
    assert r.status_code == 200 and r.json()["id"] == "uploads/My-Chip.ogg"
    assert client.put("/api/sound-uploads/notes.txt", content=b"hello").status_code == 400
    client.put("/api/sounds/payout", json={"files": ["uploads/My-Chip.ogg"], "gain_db": 0})
    r = client.delete("/api/sound-uploads/My-Chip.ogg")
    assert r.status_code == 400 and "Winnings paid" in r.json()["detail"]
    client.delete("/api/sounds/payout")
    assert client.delete("/api/sound-uploads/My-Chip.ogg").status_code == 200
    assert client.delete("/api/sound-uploads/..%2Fsounds.json").status_code != 200  # a slash never reaches the route...


def test_the_board_never_reaches_outside_the_library(tmp_path):
    board = sounds.SoundBoard(tmp_path)
    (tmp_path / "sounds.json").write_text("{}")
    for bad in ["uploads/../sounds.json", "../casino_server/app.py", "/etc/passwd", "uploads/..\\sounds.json"]:
        assert board.file_path(bad) is None, bad
    with pytest.raises(sounds.SoundError):
        board.delete_upload("uploads/../sounds.json")  # ...and the board refuses it anyway
    assert (tmp_path / "sounds.json").exists()


def test_every_moment_and_library_folder_has_a_category():
    from casino_server import sounds
    assert set(sounds.CATEGORIES) == set(sounds.MOMENTS)
    for cat in sounds.CATEGORIES.values():
        assert cat in ("ui", "global") or cat.split(":")[1] in sounds.GAME_NAMES
    folders = {p.name for p in sounds.LIBRARY_DIR.iterdir() if p.is_dir()}
    assert folders <= set(sounds.LIBRARY_GROUPS), folders - set(sounds.LIBRARY_GROUPS)
