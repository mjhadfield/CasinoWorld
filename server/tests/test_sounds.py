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


def test_the_final_reel_stop_plays_the_reel_stop_until_it_has_its_own(tmp_path):
    board = sounds.SoundBoard(tmp_path)
    assert board.resolve(ARM, "reel_stop_last") == board.resolve(ARM, "reel_stop")
    row = board.row(ARM, "reel_stop_last")
    assert row["as"] == "reel_stop" and not row["own"] and row["from"] == ARM
    # Given a sound in Default, every machine's last reel plays that, even one with its own reel stop.
    board.saved = {"slots": {"reel_stop_last": {"files": ["pops/cogitollc-pop1.ogg"], "gain_db": 0.0}}}
    assert board.resolve(ARM, "reel_stop_last") == ({"files": ["pops/cogitollc-pop1.ogg"], "gain_db": 0.0}, "slots")
    assert "as" not in board.row(ARM, "reel_stop_last")
    # Muted, it stays silent rather than falling back.
    board.saved = {ARM: {"reel_stop_last": {"files": [], "gain_db": 0.0}}}
    assert board.resolve(ARM, "reel_stop_last") == ({"files": [], "gain_db": 0.0}, ARM)

def test_every_moment_has_a_factory_sound_at_home_and_every_file_exists():
    for key, m in sounds.MOMENTS.items():
        assert m["section"] in sounds.SECTIONS, key
        assert key in sounds.FACTORY[m["home"]] or key in sounds.FALLBACK, key
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


def test_a_moment_can_be_silenced_without_the_set_above_filling_in(client, tmp_path):
    row = client.put(f"/api/sounds/{ARM}/reel_spin", json={"files": [], "gain_db": 0}).json()
    assert row["own"] and row["files"] == [] and row["changed"]
    assert client.get("/api/sounds/manifest").json()["sets"][ARM]["moments"]["reel_spin"]["files"] == []
    assert sounds.SoundBoard(tmp_path).resolve(ARM, "reel_spin") == ({"files": [], "gain_db": 0.0}, ARM)
    # ...but a choice whose files have all left the library falls back to the set above.
    board = sounds.SoundBoard(tmp_path)
    board.saved[ARM]["reel_spin"] = {"files": ["gone/nowhere.ogg"], "gain_db": 0.0}
    assert board.resolve(ARM, "reel_spin")[1] == "slots"


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


def test_bonus_games_have_their_own_sets_which_every_machine_plays(client, tmp_path):
    assert sounds.shows("bonus.trail", "trail_hop") and not sounds.shows("slots", "trail_hop") and not sounds.shows(ARM, "battle_boom")
    assert sounds.shows(ARM, "bonus_trigger") and sounds.shows(ARM, "free_spin") and not sounds.shows("bonus.trail", "click")
    r = client.put(f"/api/sounds/{ARM}/trail_hop", json={"files": ["pops/cogitollc-pop3.ogg"], "gain_db": 0})
    assert r.status_code == 400 and "doesn't use" in r.json()["detail"]
    row = client.put("/api/sounds/bonus.battle/battle_boom", json={"files": ["pops/cogitollc-pop3.ogg"], "gain_db": 0}).json()
    assert row["own"] and not row["can_inherit"]
    manifest = client.get("/api/sounds/manifest").json()
    assert "bonus.battle" not in manifest["sets"]           # the game finds them in Default's, at the end of every chain
    assert manifest["sets"]["slots"]["moments"]["battle_boom"]["files"][0].startswith("/sound-files/pops/cogitollc-pop3.ogg")
    assert "trail_hop" in manifest["sets"]["slots"]["moments"]


def test_a_machine_follows_a_preset_and_tweaks_on_top(client, tmp_path):
    r = client.post("/api/sound-presets", json={"name": "  Neon   Nights "})
    key = r.json()["key"]
    assert key == "preset.neon-nights"
    assert client.post("/api/sound-presets", json={"name": "neon nights"}).status_code == 400   # names are unique
    assert client.post("/api/sound-presets", json={"name": "Default"}).status_code == 400
    # A fresh preset plays Default's; giving it a sound reaches the machines on it, except where they have their own.
    client.put(f"/api/sounds/{key}/reel_tease", json={"files": ["pops/cogitollc-pop1.ogg"], "gain_db": 0})
    client.put(f"/api/sounds/{key}/reel_stop", json={"files": ["pops/cogitollc-pop1.ogg"], "gain_db": 0})
    assert client.put(f"/api/sound-machines/{ARM}", json={"preset": key}).status_code == 200
    board = sounds.SoundBoard(tmp_path)
    assert board.sets()[ARM]["parent"] == key and board.sets()[key]["parent"] == "slots"
    assert board.resolve(ARM, "reel_tease")[1] == key          # the preset's
    assert board.resolve(ARM, "reel_stop")[1] == ARM           # Armadillo's own tweak stays on top
    assert board.resolve(ARM, "win_end")[1] == ARM and board.resolve(ARM, "jackpot_win")[1] == "slots"
    data = client.get("/api/sounds").json()
    sets = {s["key"]: s for s in data["sets"]}
    assert sets[ARM]["preset"] == key and sets[key]["used_by"] == [ARM] and sets[key]["group"] == "Slot presets"
    assert [s["key"] for s in data["sets"]].index(key) == [s["key"] for s in data["sets"]].index("slots") + 1
    assert client.get("/api/sounds/manifest").json()["sets"][ARM]["parent"] == key
    # Dropping the tweaks plays the preset as it is; deleting the preset puts the machine back on Default.
    assert client.post(f"/api/sounds/{ARM}/inherit-all").status_code == 200
    assert sounds.SoundBoard(tmp_path).resolve(ARM, "reel_stop")[1] == key
    assert client.patch(f"/api/sound-presets/{key}", json={"name": "Neon"}).status_code == 200
    assert client.delete(f"/api/sound-presets/{key}").json()["moved"] == ["Armadillo Goes West"]
    board = sounds.SoundBoard(tmp_path)
    assert board.presets == {} and board.preset_of(ARM) == "slots" and board.resolve(ARM, "reel_stop")[1] == "slots"


def test_a_machine_can_be_saved_as_a_preset_and_sounds_the_same(client, tmp_path):
    before = {k: sounds.SoundBoard(tmp_path).resolve(ARM, k)[0] for k in sounds.MOMENTS if sounds.shows(ARM, k)}
    key = client.post("/api/sound-presets", json={"name": "Wild West", "from": ARM}).json()["key"]
    board = sounds.SoundBoard(tmp_path)
    assert board.preset_of(ARM) == key and not any(board.row(ARM, k)["own"] for k in before)
    assert {k: board.resolve(ARM, k)[0] for k in before} == before
    assert board.resolve(key, "win_small")[1] == key and board.resolve(key, "win_small")[0] == before["win_small"]
    # A copy of a preset starts with its sounds, and follows nothing.
    copy = client.post("/api/sound-presets", json={"name": "Wild West 2", "from": key}).json()["key"]
    assert sounds.SoundBoard(tmp_path).resolve(copy, "win_small")[1] == copy
    assert client.post("/api/sound-presets", json={"name": "X", "from": "casino"}).status_code == 400


def test_bonus_sounds_saved_for_every_slot_machine_move_to_the_bonus_game(tmp_path):
    (tmp_path / "sounds.json").write_text(json.dumps({"version": 9, "sets": {
        "slots": {"trail_hop": {"files": ["pops/cogitollc-pop1.ogg"], "gain_db": -2.0}},
        ARM: {"battle_boom": {"files": ["pops/cogitollc-pop1.ogg"], "gain_db": 0.0}}}}))
    board = sounds.SoundBoard(tmp_path)
    assert board.resolve("bonus.trail", "trail_hop") == ({"files": ["pops/cogitollc-pop1.ogg"], "gain_db": -2.0}, "bonus.trail")
    assert ARM not in board.saved     # a machine's own bonus sounds are dropped
