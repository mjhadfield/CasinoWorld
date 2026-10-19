"""The sounds API: sets that inherit from the one above, picks per moment, uploads, and telling the games."""
import json

import pytest

from casino_server import floor, sounds

from conftest import recv_until
from test_ws import join

ARM = "slots.armadillo"


def test_the_sets_follow_the_floor():
    assert sounds.SETS["casino"]["parent"] is None
    assert sounds.SETS["blackjack"]["parent"] == "casino" and sounds.SETS[ARM]["parent"] == "slots"
    assert set(sounds.TABLE_SETS) == set(floor.TABLES)
    assert sounds.TABLE_SETS["slot_1"] == ARM and sounds.TABLE_SETS["rou_1"] == "roulette"
    # Who can change what: cards at card tables, reels at slot machines, the room only casino-wide.
    assert sounds.shows("blackjack", "deal") and not sounds.shows("roulette", "deal")
    assert sounds.shows(ARM, "reel_stop") and sounds.shows("slots", "reel_stop") and not sounds.shows("casino", "reel_stop")
    assert sounds.shows(ARM, "click") and not sounds.shows(ARM, "room") and not sounds.shows("blackjack", "ball_spin")


def test_every_moment_has_a_factory_sound_at_home_and_every_file_exists():
    for key, m in sounds.MOMENTS.items():
        assert m["section"] in sounds.SECTIONS, key
        assert key in sounds.FACTORY[m["home"]], key
    for set_key, moments in sounds.FACTORY.items():
        for key, choice in moments.items():
            assert sounds.shows(set_key, key), (set_key, key)
            for f in choice["files"]:
                assert (sounds.LIBRARY_DIR / f).is_file(), f
            assert choice["gain_db"] <= 2.0, (set_key, key)   # the files peak at -3 dB: more would clip
    folders = {p.name for p in sounds.LIBRARY_DIR.iterdir() if p.is_dir()}
    assert folders <= set(sounds.FOLDERS), folders - set(sounds.FOLDERS)


def test_overview_and_manifest(client):
    data = client.get("/api/sounds").json()
    sets = {s["key"]: s for s in data["sets"]}
    arm = {r["key"]: r for r in sets[ARM]["moments"]}
    assert arm["reel_stop"]["own"] and arm["reel_stop"]["from"] == ARM and not arm["reel_stop"]["changed"]
    assert not arm["reel_tease"]["own"] and arm["reel_tease"]["from"] == "slots"
    assert arm["click"]["from"] == "casino"
    assert len(data["library"]) > 500 and data["folders"]["western"]["label"]
    manifest = client.get("/api/sounds/manifest").json()
    assert manifest["tables"]["slot_3"] == ARM and manifest["sets"][ARM]["parent"] == "slots"
    assert "reel_tease" not in manifest["sets"][ARM]["moments"]          # it comes from the set above
    url = manifest["sets"]["casino"]["moments"]["flip"]["files"][0]
    assert url.startswith("/sound-files/kenney-casino/card-place-2.ogg?v=")
    assert client.get(url).content[:4] == b"OggS"
    assert client.get("/maintenance").status_code == 200


def test_a_set_can_have_its_own_sound_or_use_the_one_above(client, tmp_path):
    with client.websocket_connect("/ws") as ws:
        join(ws)
        r = client.put(f"/api/sounds/{ARM}/reel_tease", json={"files": ["pops/cogitollc-pop3.ogg"] * 2, "gain_db": -40})
        assert r.status_code == 200
        row = r.json()
        assert row["own"] and row["changed"] and row["files"] == ["pops/cogitollc-pop3.ogg"] and row["gain_db"] == -30.0
        assert recv_until(ws, "sounds_changed")["version"] == 1
    # It survives a restart (a fresh board reading the same data dir).
    board = sounds.SoundBoard(tmp_path)
    assert board.resolve(ARM, "reel_tease") == ({"files": ["pops/cogitollc-pop3.ogg"], "gain_db": -30.0}, ARM)
    # A moment the factory gave its own sound can hand it back to the set above...
    row = client.post(f"/api/sounds/{ARM}/reel_stop/inherit").json()
    assert not row["own"] and row["from"] == "slots" and row["changed"]
    assert "reel_stop" not in client.get("/api/sounds/manifest").json()["sets"][ARM]["moments"]
    # ...and reset brings the factory's back.
    row = client.delete(f"/api/sounds/{ARM}/reel_stop").json()
    assert row["own"] and not row["changed"] and row["files"] == sounds.FACTORY[ARM]["reel_stop"]["files"]
    # Changing the parent reaches every child that doesn't set it.
    client.put("/api/sounds/slots/win_repeat", json={"files": ["pops/cogitollc-pop1.ogg"], "gain_db": 0})
    client.post(f"/api/sounds/{ARM}/win_repeat/inherit")
    assert sounds.SoundBoard(tmp_path).resolve(ARM, "win_repeat")[0]["files"] == ["pops/cogitollc-pop1.ogg"]
    # Reset one set, then everything.
    assert client.post("/api/sounds-reset", json={"set": ARM}).status_code == 200
    assert sounds.SoundBoard(tmp_path).resolve(ARM, "reel_tease")[1] == "slots"
    assert client.post("/api/sounds-reset").status_code == 200
    assert sounds.SoundBoard(tmp_path).saved == {}


def test_setting_a_moment_back_to_the_factory_choice_clears_the_change(client):
    factory = sounds.FACTORY["casino"]["bet"]
    client.put("/api/sounds/casino/bet", json={"files": ["pops/cogitollc-pop3.ogg"], "gain_db": 0})
    row = client.put("/api/sounds/casino/bet", json=factory).json()
    assert row["own"] and not row["changed"]


def test_bad_requests_are_refused_with_a_reason(client):
    assert client.put("/api/sounds/casino/nope", json={"files": ["pops/cogitollc-pop3.ogg"]}).status_code == 400
    assert client.put("/api/sounds/nowhere/bet", json={"files": ["pops/cogitollc-pop3.ogg"]}).status_code == 400
    r = client.put("/api/sounds/roulette/deal", json={"files": ["pops/cogitollc-pop3.ogg"]})
    assert r.status_code == 400 and "doesn't use" in r.json()["detail"]
    r = client.post("/api/sounds/casino/bet/inherit")
    assert r.status_code == 400 and "nothing above" in r.json()["detail"]
    r = client.put("/api/sounds/casino/bet", json={"files": ["../../casino_server/app.py"]})
    assert r.status_code == 400 and "Not in the library" in r.json()["detail"]
    assert client.put("/api/sounds/casino/bet", json={"files": []}).status_code == 400
    assert client.put("/api/sounds/casino/bet", json=["not", "a", "dict"]).status_code == 400
    assert client.get("/sound-files/../casino_server/app.py").status_code == 404
    assert client.get("/sound-files/%2e%2e/casino_server/app.py").status_code == 404


def test_uploads_can_be_used_and_deleted_once_unused(client):
    ogg = (sounds.LIBRARY_DIR / "pops" / "cogitollc-pop1.ogg").read_bytes()
    r = client.put("/api/sound-uploads/My Chip!.ogg", content=ogg)
    assert r.status_code == 200 and r.json()["id"] == "uploads/My-Chip.ogg"
    assert client.put("/api/sound-uploads/notes.txt", content=b"hello").status_code == 400
    client.put(f"/api/sounds/{ARM}/cash_out", json={"files": ["uploads/My-Chip.ogg"], "gain_db": 0})
    r = client.delete("/api/sound-uploads/My-Chip.ogg")
    assert r.status_code == 400 and "Cash out (Armadillo Goes West)" in r.json()["detail"]
    client.delete(f"/api/sounds/{ARM}/cash_out")
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


def test_picks_saved_before_sets_move_to_each_moments_home(tmp_path):
    (tmp_path / "sounds.json").write_text(json.dumps({"version": 35, "moments": {
        "payout": {"files": ["kenney-casino/chips-handle-6.ogg"], "gain_db": 0.0},
        "ball_spin": {"files": ["roulette/f_ilippo_59194-spin.ogg"], "gain_db": -16.5},
        "gone": {"files": ["pops/cogitollc-pop1.ogg"], "gain_db": 0.0}}}))
    board = sounds.SoundBoard(tmp_path)
    assert board.version == 35
    assert board.resolve("blackjack", "payout") == ({"files": ["kenney-casino/chips-handle-6.ogg"], "gain_db": 0.0}, "casino")
    assert board.resolve("roulette", "ball_spin")[0]["gain_db"] == -16.5
    assert board.row("roulette", "ball_spin")["changed"]
