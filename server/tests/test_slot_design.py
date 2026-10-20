"""The admin page's Slot design board: variants, choices, counts, linked references, New symbols and
generating (with FLUX faked: it draws an orange disc on magenta)."""
import io
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from casino_server import slot_design_art as art
from casino_server.app import app


def _fake_flux(*_):
    im = Image.new("RGB", (512, 512), (230, 20, 200))
    ImageDraw.Draw(im).ellipse((140, 100, 380, 420), fill=(240, 150, 60), outline=(20, 10, 5), width=6)
    return im


def _png(colour=(200, 30, 30), size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def board(tmp_path, monkeypatch):
    """A scratch design: an object with a favourite and a hidden take, and a framed character."""
    d = tmp_path / "slot_designs" / "demo"
    for sub in ("ref", "cut", "raw", "chars"):
        (d / sub).mkdir(parents=True)
    for name in ("ref/ship.png", "ref/hero.png", "cut/ship_1.png", "cut/ship_2.png", "cut/ship_4.png", "raw/ship_4.png",
                 "raw/bust_hero_1.png", *(f"chars/hero_1_{h}.png" for h in art.HUES)):
        (d / name).write_bytes(_png())
    (d / "design.json").write_text(json.dumps({"name": "Demo", "categories": [
        {"id": "set1", "title": "Characters", "required": 2, "kind": "character"},
        {"id": "set2", "title": "Objects", "required": 4, "kind": "object"},
        {"id": "bonus", "title": "Bonus screens", "required": None, "kind": "object"}],
        "symbols": [
            {"id": "ship", "name": "Ship", "category": "set2", "kind": "object", "refs": ["ref/ship.png"],
             "favourite": "cut/ship_1.png", "hidden": ["cut/ship_2.png"]},
            {"id": "hero", "name": "Hero", "category": "set1", "kind": "character", "refs": ["ref/hero.png"], "hue": "blue"}],
        "jobs": []}))
    monkeypatch.setenv("CASINO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CASINO_DESIGNS_DIR", str(tmp_path / "slot_designs"))
    monkeypatch.setenv("CASINO_SLOT_BUILDS_DIR", str(tmp_path / "slot_builds"))
    monkeypatch.setenv("CASINO_NPCS", "0")
    monkeypatch.setattr(art, "image_model", lambda last=None: "FLUX.2-klein-4B")
    monkeypatch.setattr(art, "flux_edit", _fake_flux)
    monkeypatch.setattr(art, "flux_generate", _fake_flux)
    with TestClient(app) as c:
        yield c, d


@pytest.mark.parametrize("listed, model", [
    (b'{"data":[{"id":"Qwen-Image-2.1","object":"model"}]}', "Qwen-Image-2.1"),  # any model will do, not just FLUX
    (b'{"data":[{"id":"FLUX.2-klein-4B"}]}', "FLUX.2-klein-4B"),
    (b'{"data":[]}', None),
    (b'{"error":"Model not loaded"}', None),
    (b"not json", None),
])
def test_any_loaded_image_model_is_ready(monkeypatch, listed, model):
    monkeypatch.setattr(art, "_docker", lambda *a, **k: listed)
    assert art.image_model() == model and art.flux_ready() is (model is not None)


def test_a_busy_image_model_is_still_loaded(monkeypatch):
    def busy(*a, **k):
        raise art.FluxBusy("busy")
    monkeypatch.setattr(art, "_docker", busy)
    assert art.image_model("Qwen-Image-2.1") == "Qwen-Image-2.1" and art.image_model() is None
    def gone(*a, **k):
        raise art.FluxError("connection refused")
    monkeypatch.setattr(art, "_docker", gone)
    assert art.image_model("Qwen-Image-2.1") is None


def test_status_names_the_model(board):
    c, _ = board
    st = c.get("/api/slot-design/demo/status").json()
    assert st["flux"] is True and st["model"] == "FLUX.2-klein-4B"


def _overview(c):
    return c.get("/api/slot-design/demo").json()


def _sym(o, sid):
    return next(s for s in o["symbols"] if s["id"] == sid)


def test_variants_come_from_the_files(board):
    c, _ = board
    assert c.get("/api/slot-design").json()["designs"] == [{"id": "demo", "name": "Demo"}]
    o = _overview(c)
    ship, hero = _sym(o, "ship"), _sym(o, "hero")
    assert [v["id"] for v in ship["variants"]] == ["cut/ship_1.png", "cut/ship_4.png"]  # favourite first, take 2 hidden
    assert ship["variants"][0]["fav"] and ship["file"] == "cut/ship_1.png"
    assert hero["variants"][0]["id"] == "bust/hero_1" and set(hero["variants"][0]["hues"]) == set(art.HUES)
    assert hero["file"] == "chars/hero_1_blue.png"
    assert [(k["id"], k["count"], k["in_set"], k["required"]) for k in o["categories"]] == \
        [("set1", 1, 0, 2), ("set2", 1, 0, 4), ("bonus", 0, 0, None)]


def test_choices_counts_and_category_needs(board):
    c, d = board
    assert c.patch("/api/slot-design/demo/symbols/ship", json={"choice": "cut/ship_4.png", "keep": True}).status_code == 200
    assert c.patch("/api/slot-design/demo/symbols/hero", json={"hue": "gold"}).status_code == 200
    o = _overview(c)
    assert _sym(o, "ship")["file"] == "cut/ship_4.png" and _sym(o, "hero")["file"] == "chars/hero_1_gold.png"
    assert next(k for k in o["categories"] if k["id"] == "set2")["in_set"] == 1
    assert c.patch("/api/slot-design/demo/symbols/ship", json={"choice": "cut/ship_2.png"}).status_code == 400  # hidden
    assert c.patch("/api/slot-design/demo/symbols/hero", json={"hue": "pink"}).status_code == 400
    assert c.patch("/api/slot-design/demo/categories/set2", json={"required": 5}).status_code == 200
    assert c.patch("/api/slot-design/demo/categories/set2", json={"required": -1}).status_code == 400
    saved = json.loads((d / "design.json").read_text())
    assert saved["categories"][1]["required"] == 5 and saved["symbols"][0]["keep"] is True


def test_linking_reference_images(board):
    c, _ = board
    path = c.put("/api/slot-design/demo/links/My Ref.png", content=_png(size=(2000, 1000))).json()["path"]
    assert path == "links/my_ref.png"
    assert Image.open(io.BytesIO(c.get(f"/slot-design/demo/{path}").content)).size == (1024, 512)
    assert c.put("/api/slot-design/demo/links/x.png", content=b"not an image").status_code == 400
    assert c.patch("/api/slot-design/demo/symbols/ship", json={"add_ref": path, "base": path}).status_code == 200
    # another symbol's art can be linked too (bonus screens reuse what's been made)
    assert c.patch("/api/slot-design/demo/symbols/hero", json={"add_ref": "cut/ship_4.png"}).status_code == 200
    assert c.patch("/api/slot-design/demo/symbols/hero", json={"add_ref": "../design.json"}).status_code == 400
    assert c.patch("/api/slot-design/demo/symbols/hero", json={"base": "links/nope.png"}).status_code == 400
    assert _sym(_overview(c), "ship")["refs"] == ["ref/ship.png", path]
    assert c.get("/slot-design/demo/../design.json").status_code == 404
    assert c.get("/slot-design/demo/raw/ship_4.png").status_code == 404  # raw FLUX output isn't served
    assert c.post("/api/slot-design/demo/links", json={"url": "file:///etc/passwd"}).status_code == 400


def test_new_symbols_stack_and_only_added_ones_delete(board):
    c, _ = board
    a = c.post("/api/slot-design/demo/symbols", json={"name": "Bonus wheel", "category": "bonus", "prompt": "a prize wheel"}).json()["id"]
    b = c.post("/api/slot-design/demo/symbols", json={"name": "Bonus wheel", "category": "bonus", "ref": "ref/ship.png"}).json()["id"]
    assert (a, b) == ("bonus_wheel", "bonus_wheel_2")
    assert c.post("/api/slot-design/demo/symbols", json={"name": "Empty", "category": "bonus"}).status_code == 400
    assert c.post("/api/slot-design/demo/symbols", json={"name": "X", "category": "nope", "prompt": "x"}).status_code == 400
    o = _overview(c)
    assert o["pending"] == 2 and next(k for k in o["categories"] if k["id"] == "bonus")["count"] == 2
    assert c.delete(f"/api/slot-design/demo/symbols/{b}").status_code == 200
    assert c.delete("/api/slot-design/demo/symbols/ship").status_code == 400


def _wait_idle(c, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if not c.get("/api/slot-design/demo/status").json()["busy"]:
            return
        time.sleep(0.2)
    raise AssertionError("the jobs didn't finish")


def test_generate_makes_three_takes_per_job(board):
    c, d = board
    c.patch("/api/slot-design/demo/symbols/ship", json={"choice": "cut/ship_4.png", "reiterate": True, "note": "bluer"})
    c.patch("/api/slot-design/demo/symbols/hero", json={"reiterate": True})
    new = c.post("/api/slot-design/demo/symbols", json={"name": "Moon", "category": "set2", "prompt": "a cratered moon"}).json()["id"]
    assert c.post("/api/slot-design/demo/generate").json()["queued"] == 3
    o = _overview(c)
    assert o["pending"] == 0 and not _sym(o, "ship")["reiterate"]
    _wait_idle(c)
    o = _overview(c)
    assert [v["id"] for v in _sym(o, "ship")["variants"]][-3:] == ["cut/ship_5.png", "cut/ship_6.png", "cut/ship_7.png"]
    assert [v["id"] for v in _sym(o, "hero")["variants"]] == ["bust/hero_1", "bust/hero_2", "bust/hero_3", "bust/hero_4"]
    assert len(_sym(o, new)["variants"]) == 3
    for hue in art.HUES:
        assert Image.open(d / f"chars/hero_4_{hue}.png").size == (512, 512)
    saved = json.loads((d / "design.json").read_text())
    jobs = {j["symbol"]: j for j in saved["jobs"]}
    assert jobs["ship"]["src"] == "raw/ship_4.png" and jobs["ship"]["how"] == "variation" and jobs["ship"]["text"] == "bluer"
    assert jobs["hero"]["src"] == "raw/bust_hero_1.png" and jobs["hero"]["out"] == "character"
    assert jobs[new]["how"] == "text" and all(j["status"] == "done" for j in jobs.values())


def test_prompts_panel_sets_first_takes_and_rewrites_styles(board, monkeypatch):
    c, _ = board
    o = _overview(c)
    assert o["prompts"]["first_takes"] == 3 and o["prompts"]["text"] == o["default_prompts"]["text"]
    assert c.patch("/api/slot-design/demo/prompts", json={"first_takes": 4}).status_code == 400
    assert c.patch("/api/slot-design/demo/prompts", json={"text": {"5": "x"}}).status_code == 400
    c.patch("/api/slot-design/demo/prompts", json={"first_takes": 2, "text": {"1": "chunky pixel art"}, "bust": "a tiny sketch."})
    p = _overview(c)["prompts"]
    assert p["first_takes"] == 2 and p["text"][1] == "chunky pixel art" and p["text"][0] == art.TEXT_STYLES[1]
    prompts = []
    monkeypatch.setattr(art, "flux_generate", lambda prompt, size="1024x1024": prompts.append(prompt) or _fake_flux())
    sid = c.post("/api/slot-design/demo/symbols", json={"name": "Moon", "category": "set2", "prompt": "a cratered moon"}).json()["id"]
    c.post("/api/slot-design/demo/generate")
    _wait_idle(c)
    assert len(_sym(_overview(c), sid)["variants"]) == 2 and len(prompts) == 2
    assert art.TEXT_STYLES[1] in prompts[0] and "chunky pixel art" in prompts[1]
    # emptied (or set back to the default) drops the rewrite
    c.patch("/api/slot-design/demo/prompts", json={"text": {"1": ""}, "bust": art.BUST})
    p = _overview(c)["prompts"]
    assert p["text"][1] == art.TEXT_STYLES[2] and p["bust"] == art.BUST


def test_first_generate_on_any_card(board, monkeypatch):
    c, _ = board
    o = _overview(c)
    assert not _sym(o, "ship")["pending_new"] and _sym(o, "ship")["first_takes"] == 3
    assert c.patch("/api/slot-design/demo/symbols/ship", json={"first": 4}).status_code == 400
    # marking one clears the other
    c.patch("/api/slot-design/demo/symbols/ship", json={"reiterate": True})
    c.patch("/api/slot-design/demo/symbols/ship", json={"first": 2})
    s = _sym(_overview(c), "ship")
    assert s["pending_new"] and s["first_takes"] == 2 and not s["reiterate"]
    c.patch("/api/slot-design/demo/symbols/ship", json={"reiterate": True})
    assert not _sym(_overview(c), "ship")["pending_new"]
    c.patch("/api/slot-design/demo/symbols/ship", json={"first": 2})
    # it redraws the reference in the first two styles, not a variation of the chosen take
    prompts = []
    monkeypatch.setattr(art, "flux_edit", lambda im, p: prompts.append(p) or _fake_flux())
    before = len(_sym(_overview(c), "ship")["variants"])
    assert c.post("/api/slot-design/demo/symbols/ship/queue", json={}).json()["queued"] == 1
    _wait_idle(c)
    s = _sym(_overview(c), "ship")
    assert len(s["variants"]) == before + 2 and not s["pending_new"]
    assert art.STYLES[1] in prompts[0] and art.STYLES[2] in prompts[1]
    c.patch("/api/slot-design/demo/symbols/ship", json={"first": 1})
    c.patch("/api/slot-design/demo/symbols/ship", json={"first": 0})
    assert _overview(c)["pending"] == 0


def test_reiterating_from_a_reference_uses_the_description(board):
    c, _ = board
    sid = c.post("/api/slot-design/demo/symbols", json={"name": "Wheel", "category": "bonus", "prompt": "a prize wheel"}).json()["id"]
    c.post("/api/slot-design/demo/generate")
    _wait_idle(c)
    c.patch(f"/api/slot-design/demo/symbols/{sid}", json={"add_ref": "ref/ship.png", "base": "ref/ship.png", "reiterate": True,
                                                         "prompt": "a prize wheel, keep the word BONUS", "note": "more gold"})
    c.post("/api/slot-design/demo/generate")
    job = _sym(_overview(c), sid)["job"]
    assert job["how"] == "redraw" and job["text"] == "a prize wheel, keep the word BONUS. more gold."
    _wait_idle(c)


def test_a_failed_job_can_be_retried(board, monkeypatch):
    c, _ = board
    def broken(*_):
        raise art.FluxError("out of memory")
    monkeypatch.setattr(art, "flux_edit", broken)
    c.patch("/api/slot-design/demo/symbols/ship", json={"reiterate": True})
    c.post("/api/slot-design/demo/generate")
    _wait_idle(c)
    job = _sym(_overview(c), "ship")["job"]
    assert job["status"] == "failed" and "out of memory" in job["error"]
    monkeypatch.setattr(art, "flux_edit", _fake_flux)
    assert c.post(f"/api/slot-design/demo/jobs/{job['id']}/retry").status_code == 200
    _wait_idle(c)
    assert _sym(_overview(c), "ship")["job"] is None



def test_reiterate_makes_one_three_or_five_takes(board):
    c, _ = board
    assert c.patch("/api/slot-design/demo/symbols/ship", json={"reiterate": True, "takes": 4}).status_code == 400
    c.patch("/api/slot-design/demo/symbols/ship", json={"choice": "cut/ship_4.png", "reiterate": True, "takes": 5})
    c.patch("/api/slot-design/demo/symbols/hero", json={"reiterate": True, "takes": 1})
    assert _sym(_overview(c), "ship")["takes"] == 5
    c.post("/api/slot-design/demo/generate")
    _wait_idle(c)
    o = _overview(c)
    assert [v["id"] for v in _sym(o, "ship")["variants"]][2:] == [f"cut/ship_{n}.png" for n in range(5, 10)]
    assert [v["id"] for v in _sym(o, "hero")["variants"]] == ["bust/hero_1", "bust/hero_2"]
    assert _sym(o, "ship")["takes"] == 5  # remembered for next time
    # a card's Queue sends that symbol alone, and its Reiterate goes back to No
    c.patch("/api/slot-design/demo/symbols/ship", json={"reiterate": True, "takes": 1})
    c.patch("/api/slot-design/demo/symbols/hero", json={"reiterate": True, "takes": 1})
    assert c.post("/api/slot-design/demo/symbols/ship/queue", json={}).json()["queued"] == 1
    o = _overview(c)
    assert not _sym(o, "ship")["reiterate"] and _sym(o, "hero")["reiterate"] and o["pending"] == 1
    _wait_idle(c)
    assert len(_sym(_overview(c), "ship")["variants"]) == 8


def test_cancel_all_stops_the_running_job_and_drops_its_picture(board, monkeypatch):
    import threading
    c, d = board
    drawing, go = threading.Event(), threading.Event()
    def slow(*a):
        drawing.set()
        go.wait(10)
        return _fake_flux()
    monkeypatch.setattr(art, "flux_edit", slow)
    c.patch("/api/slot-design/demo/symbols/ship", json={"choice": "cut/ship_4.png", "reiterate": True})
    c.patch("/api/slot-design/demo/symbols/hero", json={"reiterate": True})
    c.post("/api/slot-design/demo/generate")
    assert drawing.wait(10)
    o = _overview(c)
    assert o["art_jobs"] == 2 and o["running"]["status"] == "running"
    assert c.delete("/api/slot-design/demo/jobs").json()["cancelled"] == 2
    go.set()
    _wait_idle(c)
    o = _overview(c)
    assert o["art_jobs"] == 0 and all(s["job"] is None for s in o["symbols"])
    assert not (d / "cut/ship_5.png").exists() and not (d / "raw/bust_hero_2.png").exists()
    # one job on its own, running, can be cancelled too
    drawing.clear(); go.clear()
    c.patch("/api/slot-design/demo/symbols/ship", json={"reiterate": True, "takes": 3})
    c.post("/api/slot-design/demo/generate")
    assert drawing.wait(10)
    job = _sym(_overview(c), "ship")["job"]
    assert c.delete(f"/api/slot-design/demo/jobs/{job['id']}").status_code == 200
    go.set()
    _wait_idle(c)
    assert not (d / "cut/ship_5.png").exists()


def test_hiding_symbols_not_in_use_and_moving_sections(board):
    c, d = board
    c.post("/api/slot-design/demo/symbols", json={"name": "Moon", "category": "set2", "prompt": "a cratered moon"})
    c.patch("/api/slot-design/demo/symbols/ship", json={"keep": True})
    o = _overview(c)
    assert _sym(o, "ship")["in_use"] and not _sym(o, "hero")["in_use"]
    assert c.patch("/api/slot-design/demo/symbols/ship", json={"hide": True}).status_code == 400
    # Hide unused skips what's in use and what's waiting to be made (the new Moon)
    assert c.post("/api/slot-design/demo/hide-unused").json()["hidden"] == 1
    o = _overview(c)
    assert _sym(o, "hero")["hide"] and not _sym(o, "moon")["hide"]
    assert next(k for k in o["categories"] if k["id"] == "set1")["hidden"] == 1
    assert c.patch("/api/slot-design/demo/symbols/hero", json={"hide": False}).status_code == 200
    assert not _sym(_overview(c), "hero")["hide"]
    c.patch("/api/slot-design/demo/symbols/hero", json={"hide": True})
    c.patch("/api/slot-design/demo/symbols/hero", json={"keep": True})  # into the set: back on the board
    assert not _sym(_overview(c), "hero")["hide"]
    # an art slot following a symbol puts it in use
    c.patch("/api/slot-design/demo/symbols/moon", json={"category": "bonus"})
    c.put("/api/slot-design/demo/art-slots/armadillo", json={"value": "sym:moon"})
    o = _overview(c)
    assert _sym(o, "moon")["in_use"] and _sym(o, "moon")["category"] == "bonus"
    assert [(k["id"], k["count"]) for k in o["categories"]] == [("set1", 1), ("set2", 1), ("bonus", 1)]
    assert c.patch("/api/slot-design/demo/symbols/moon", json={"category": "nope"}).status_code == 400

def test_keying_and_the_shared_frame():
    tiles = art.compose_character(_fake_flux())
    assert set(tiles) == set(art.HUES) and all(t.size == (512, 512) for t in tiles.values())
    corner = tiles["gold"].getpixel((2, 2))
    assert corner[3] == 0  # outside the frame is clear
    sym = art.symbol(_fake_flux())
    assert sym.size == (512, 512) and sym.getpixel((256, 256))[:3] == (240, 150, 60)


# ------------------------------------------------------------------ the wizard (Phase 1)
def test_old_designs_are_migrated(board):
    c, d = board
    o = _overview(c)
    assert o["concept"]["tiers"] == {"high": 2, "mid": 4, "low": 4} and o["concept"]["target_rtp"] == 91.5
    assert [s["id"] for s in o["steps"]][:3] == ["concept", "art", "ladder"] and len(o["steps"]) == 11
    assert {s["id"]: s["status"] for s in o["steps"]}["art"] == "doing"
    ship = _sym(o, "ship")
    assert [v["id"] for v in ship["binned"]] == ["cut/ship_2.png"]  # round 1's hidden takes are in the Bin
    saved = json.loads((d / "design.json").read_text())
    assert "hidden" not in saved["symbols"][0]
    assert {k["id"]: k["role"] for k in saved["categories"]} == {"set1": "high", "set2": "mid", "bonus": None}


def test_new_design_and_the_concept(board):
    c, _ = board
    did = c.post("/api/slot-design", json={"name": "Pirate Gold", "brief": "pirates of the Caribbean"}).json()["id"]
    assert did == "pirate_gold" and c.post("/api/slot-design", json={"name": " "}).status_code == 400
    o = c.get(f"/api/slot-design/{did}").json()
    assert o["concept"]["brief"] == "pirates of the Caribbean"
    royals = [s["id"] for s in o["symbols"] if s["category"] == "royals"]
    assert royals == ["a", "k", "q", "j"] and o["pending"] == 7  # four royals and three specials wait for Generate
    assert c.patch(f"/api/slot-design/{did}/concept", json={"tiers": {"high": 3, "mid": 4, "low": 5}}).status_code == 200
    req = {k["role"]: k["required"] for k in c.get(f"/api/slot-design/{did}").json()["categories"]}
    assert req == {"low": 5, "high": 3, "mid": 4, "specials": 3, None: None}
    assert c.patch(f"/api/slot-design/{did}/concept", json={"tiers": {"high": 0, "mid": 4, "low": 5}}).status_code == 400
    assert c.patch(f"/api/slot-design/{did}/concept", json={"target_rtp": 120}).status_code == 400
    assert c.put(f"/api/slot-design/{did}/steps/concept", json={"status": "done"}).status_code == 200
    assert c.put(f"/api/slot-design/{did}/steps/concept", json={"status": "nearly"}).status_code == 400
    assert c.get("/api/slot-design").json()["designs"][1]["name"] == "Pirate Gold"


def test_the_sheet_cutter(board, monkeypatch):
    c, d = board
    sheet = c.put("/api/slot-design/demo/sources/My Sheet.png", content=_png(size=(400, 200))).json()["path"]
    assert sheet == "source/my_sheet.png" and _overview(c)["sources"] == [sheet]
    made = c.post("/api/slot-design/demo/cuts", json={"sheet": sheet, "boxes": [
        {"x": 0, "y": 0, "w": 200, "h": 200, "name": "Moon", "category": "set2"},
        {"x": 200, "y": 0, "w": 200, "h": 100, "name": "Ship", "category": "set1", "key": "green"}]}).json()["made"]
    assert made == ["moon", "ship_2"]
    assert Image.open(d / "ref/ship_2.png").size == (1024, 1024)
    o = _overview(c)
    assert _sym(o, "ship_2")["kind"] == "character" and _sym(o, "ship_2")["key"] == "green" and o["pending"] == 2
    bad = {"sheet": sheet, "boxes": [{"x": 0, "y": 0, "w": 8, "h": 8, "name": "Tiny", "category": "set2"}]}
    assert c.post("/api/slot-design/demo/cuts", json=bad).status_code == 400
    assert c.post("/api/slot-design/demo/cuts", json={"sheet": "ref/ship.png", "boxes": bad["boxes"]}).status_code == 400
    # Generate makes one take of a cut, the faithful redraw
    prompts = []
    monkeypatch.setattr(art, "flux_edit", lambda im, p: prompts.append(p) or _fake_flux())
    c.post("/api/slot-design/demo/generate")
    _wait_idle(c)
    o = _overview(c)
    assert len(_sym(o, "moon")["variants"]) == 1 and len(_sym(o, "ship_2")["variants"]) == 1
    assert len(prompts) == 2 and art.STYLES[1] in prompts[0]


def test_split_a_take_into_its_own_symbol(board):
    c, d = board
    c.patch("/api/slot-design/demo/symbols/ship", json={"choice": "cut/ship_4.png", "keep": True})
    new = c.post("/api/slot-design/demo/symbols/ship/split", json={"variant": "cut/ship_4.png"}).json()["id"]
    o = _overview(c)
    s, ship = _sym(o, new), _sym(o, "ship")
    assert s["name"] == "Ship 2" and s["category"] == "set2" and s["added"] and not s["keep"]
    assert [v["id"] for v in s["variants"]] == [f"cut/{new}_1.png"] and s["file"] == f"cut/{new}_1.png"
    assert (d / f"raw/{new}_1.png").exists() and s["refs"] == ["ref/ship.png"]
    assert "cut/ship_4.png" in [v["id"] for v in ship["binned"]] and ship["choice"] == "cut/ship_1.png"
    assert [x["id"] for x in o["symbols"]][:2] == ["ship", new]  # right after the original
    hero = c.post("/api/slot-design/demo/symbols/hero/split", json={"variant": "bust/hero_1", "name": " Captain "}).json()["id"]
    assert hero == "captain" and _sym(_overview(c), hero)["name"] == "Captain"
    h = _sym(_overview(c), hero)
    assert h["kind"] == "character" and h["variants"][0]["id"] == f"bust/{hero}_1" and set(h["variants"][0]["hues"]) == set(art.HUES)
    assert h["file"] == f"chars/{hero}_1_blue.png"
    assert c.post("/api/slot-design/demo/symbols/hero/split", json={"variant": "bust/nope"}).status_code == 400


def test_bin_and_restore(board):
    c, _ = board
    assert c.post("/api/slot-design/demo/symbols/ship/bin", json={"variant": "cut/ship_4.png"}).status_code == 200
    ship = _sym(_overview(c), "ship")
    assert [v["id"] for v in ship["variants"]] == ["cut/ship_1.png"]
    assert [v["id"] for v in ship["binned"]] == ["cut/ship_2.png", "cut/ship_4.png"]
    assert c.post("/api/slot-design/demo/symbols/ship/restore", json={"variant": "cut/ship_2.png"}).status_code == 200
    assert [v["id"] for v in _sym(_overview(c), "ship")["variants"]] == ["cut/ship_1.png", "cut/ship_2.png"]
    assert c.post("/api/slot-design/demo/symbols/ship/restore", json={"variant": "cut/ship_1.png"}).status_code == 400
    assert c.post("/api/slot-design/demo/symbols/ship/bin", json={"variant": "cut/nope.png"}).status_code == 400


def test_refine_is_one_targeted_take_led_by_the_theme(board, monkeypatch):
    c, _ = board
    prompts = []
    monkeypatch.setattr(art, "flux_edit", lambda im, p: prompts.append(p) or _fake_flux())
    c.patch("/api/slot-design/demo/concept", json={"brief": "Deep-space salvage crews"})
    job = c.post("/api/slot-design/demo/symbols/ship/refine", json={"variant": "cut/ship_4.png", "instruction": "paint it red"}).json()["job"]
    assert job["count"] == 1 and job["src"] == "raw/ship_4.png"
    assert c.post("/api/slot-design/demo/symbols/ship/refine", json={"variant": "cut/ship_4.png", "instruction": ""}).status_code == 400
    _wait_idle(c)
    ship = _sym(_overview(c), "ship")
    assert ship["variants"][-1] == {"id": "cut/ship_5.png", "label": "Take 4, refined", "src": "cut/ship_5.png"}
    assert prompts[0].startswith("Theme: Deep-space salvage crews. Keep this slot machine symbol exactly") and "paint it red" in prompts[0]


def test_fit_previews_and_saves_a_new_take(board):
    c, d = board
    (d / "raw/ship_4.png").write_bytes(io.BytesIO(_png()).getvalue())
    _fake_flux().save(d / "raw/ship_4.png")
    r = c.post("/api/slot-design/demo/symbols/ship/fit-preview", json={"variant": "cut/ship_4.png", "fit": {"scale": 0.6}})
    assert r.headers["content-type"] == "image/png" and Image.open(io.BytesIO(r.content)).size == (512, 512)
    new = c.post("/api/slot-design/demo/symbols/ship/fit", json={"variant": "cut/ship_4.png", "fit": {"scale": 0.6, "dx": 500}}).json()["variant"]
    assert new == "cut/ship_5.png"
    ship = _sym(_overview(c), "ship")
    assert ship["choice"] == new and ship["fits"][new] == {"src": "raw/ship_4.png", "fit": {"scale": 0.6, "dx": 160.0, "dy": 0.0, "rot": 0.0}}
    assert ship["variants"][-1]["label"] == "Take 4, fitted"
    # a Fit of a Fit starts again from the original picture
    again = c.post("/api/slot-design/demo/symbols/ship/fit", json={"variant": new, "fit": {"scale": 1.2}}).json()["variant"]
    assert _sym(_overview(c), "ship")["fits"][again]["src"] == "raw/ship_4.png"
    # characters are refitted inside the frame, in every colour
    _fake_flux().save(d / "raw/bust_hero_1.png")
    hero = c.post("/api/slot-design/demo/symbols/hero/fit", json={"variant": "bust/hero_1", "fit": {"scale": 0.8, "dy": 20}}).json()["variant"]
    assert hero == "bust/hero_2" and all((d / f"chars/hero_2_{h}.png").exists() for h in art.HUES)


# ------------------------------------------------------------------ Value ladder and Scene (Phase 2)
def test_the_value_ladder(board):
    c, _ = board
    lad = _overview(c)["ladder"]
    assert lad["tiers"][:5] == ["W", "BS", "FS", "H1", "H2"] and len(lad["tiers"]) == 13 and not lad["complete"]
    assert lad["pays"]["H1"] == [20, 40, 120] and lad["upgrades"]["L1"] == "M3"
    r = c.put("/api/slot-design/demo/ladder", json={"slots": {"H1": "hero", "M1": "ship"}})
    assert r.status_code == 200 and r.json()["slots"] == {"H1": "hero", "M1": "ship"}
    assert c.put("/api/slot-design/demo/ladder", json={"slots": {"H1": "hero", "H2": "hero"}}).status_code == 400
    assert c.put("/api/slot-design/demo/ladder", json={"slots": {"L9": "hero"}}).status_code == 400
    assert c.put("/api/slot-design/demo/ladder", json={"slots": {}, "upgrades": {"H1": "L1"}}).status_code == 400  # downgrade
    assert c.put("/api/slot-design/demo/ladder", json={"slots": {}, "upgrades": {"L1": "W"}}).status_code == 400
    ok = c.put("/api/slot-design/demo/ladder", json={"slots": {"H2": "hero"}, "upgrades": {"L1": "H1"}}).json()
    assert ok["upgrades"] == {"L1": "H1"} and ok["slots"] == {"H2": "hero"}
    # a bigger tier shape gets more tiers, and the defaults stretch to them
    c.patch("/api/slot-design/demo/concept", json={"tiers": {"high": 2, "mid": 4, "low": 5}})
    lad = _overview(c)["ladder"]
    assert lad["tiers"][-1] == "L5" and lad["pays"]["L5"] == [4, 8, 20]


def test_the_scene(board, monkeypatch):
    c, d = board
    monkeypatch.setattr(art, "flux_generate", lambda prompt, size="1024x1024": Image.new("RGB", (1344, 768), (20, 30, 90)))
    job = c.post("/api/slot-design/demo/scene/backgrounds", json={"description": "a starfield"}).json()["job"]
    assert job["out"] == "background" and job["symbol"] is None
    _wait_idle(c)
    sc = _overview(c)["scene"]
    assert sc["backgrounds"] == ["scene/bg_1.png", "scene/bg_2.png", "scene/bg_3.png"] and sc["background"] == "scene/bg_1.png"
    assert Image.open(d / "scene/bg_1.png").size == (1280, 720)
    up = c.put("/api/slot-design/demo/scene/backgrounds/mine.jpg", content=_png(size=(800, 800))).json()["path"]
    assert up == "scene/bg_4.png" and Image.open(d / up).size == (1280, 720)
    assert c.patch("/api/slot-design/demo/scene", json={"background": "scene/bg_2.png"}).status_code == 200
    assert c.patch("/api/slot-design/demo/scene", json={"background": "cut/ship_1.png"}).status_code == 400
    logo = c.post("/api/slot-design/demo/scene/logo", json={"lines": ["DEMO", "SLOT"], "font": "Cinzel-SemiBold.ttf"}).json()["path"]
    assert logo == "scene/logo_1.png" and Image.open(d / logo).mode == "RGBA"
    assert _overview(c)["scene"]["logo"]["lines"] == ["DEMO", "SLOT"]
    assert c.post("/api/slot-design/demo/scene/logo", json={"lines": ["X"], "top": "gold"}).status_code == 400
    assert c.post("/api/slot-design/demo/scene/logo", json={"lines": [], "font": "Cinzel-SemiBold.ttf"}).status_code == 400
    assert c.patch("/api/slot-design/demo/scene", json={"frame": {"style": "neon", "colour": "#33ccff"}}).status_code == 200
    assert c.patch("/api/slot-design/demo/scene", json={"frame": {"style": "lace", "colour": "#33ccff"}}).status_code == 400
    assert _overview(c)["scene"]["deck"] == {"style": "frame", "colour": None}   # the deck follows the frame until changed
    assert c.patch("/api/slot-design/demo/scene", json={"deck": {"style": "metal", "colour": "#224466"}}).status_code == 200
    assert c.patch("/api/slot-design/demo/scene", json={"deck": {"style": "frame", "colour": None}}).status_code == 200
    assert c.patch("/api/slot-design/demo/scene", json={"deck": {"style": "lace", "colour": None}}).status_code == 400
    assert c.patch("/api/slot-design/demo/scene", json={"deck": {"style": "wood", "colour": "brown"}}).status_code == 400
    # the Bin: binning hides a background or logo (the one in use is dropped), restoring brings it back; nothing is deleted
    assert c.post("/api/slot-design/demo/scene/bin", json={"path": "scene/bg_2.png"}).status_code == 200
    assert c.post("/api/slot-design/demo/scene/bin", json={"path": logo}).status_code == 200
    sc = _overview(c)["scene"]
    assert sc["backgrounds"] == ["scene/bg_1.png", "scene/bg_3.png", "scene/bg_4.png"] and sc["background"] is None
    assert sc["logos"] == [] and "file" not in sc["logo"] and sc["logo"]["lines"] == ["DEMO", "SLOT"]
    assert sc["bin"] == {"backgrounds": ["scene/bg_2.png"], "logos": [logo]} and (d / "scene/bg_2.png").is_file()
    assert c.patch("/api/slot-design/demo/scene", json={"background": "scene/bg_2.png"}).status_code == 400
    assert c.post("/api/slot-design/demo/scene/bin", json={"path": "cut/ship_1.png"}).status_code == 400
    assert c.post("/api/slot-design/demo/scene/restore", json={"path": "scene/bg_3.png"}).status_code == 400
    assert c.post("/api/slot-design/demo/scene/restore", json={"path": "scene/bg_2.png"}).status_code == 200
    assert _overview(c)["scene"]["backgrounds"] == ["scene/bg_1.png", "scene/bg_2.png", "scene/bg_3.png", "scene/bg_4.png"]
    assert c.patch("/api/slot-design/demo/scene", json={"background": "scene/bg_2.png"}).status_code == 200
    assert c.put("/api/slot-design/demo/fonts/bad.ttf", content=b"nope").status_code == 400
    assert c.put("/api/slot-design/demo/fonts/notes.txt", content=b"nope").status_code == 400
    assert c.get("/slot-design-ui/slots_math.js").status_code == 200
    assert c.get("/slot-design-ui/../app.py").status_code == 404


# ------------------------------------------------------------------ Features and Bonus games (Phase 4)
def test_features(board):
    c, _ = board
    f = _overview(c)["features"]
    assert f["enabled"] == f["library"] and f["rates"]["wilds"] == 0.07 and f["tables"]["multipliers"][0] == [2, 50]
    ok = c.patch("/api/slot-design/demo/features", json={"enabled": ["instant", "wilds"], "rates": {"wilds": 0.1},
                                                         "tables": {"multipliers": [[2, 1], [10, 1]]}})
    assert ok.status_code == 200
    f = _overview(c)["features"]
    assert f["enabled"] == ["wilds", "instant"] and f["rates"]["wilds"] == 0.1 and f["tables"]["multipliers"] == [[2, 1], [10, 1]]
    bad = [{"enabled": ["teleport"]}, {"rates": {"wilds": 1.5}}, {"tables": {"multipliers": [[1, 10]]}},
           {"tables": {"instants": [[5, 0]]}}, {"enabled": []}, {"enabled": ["repeat"]}]
    for body in bad:
        assert c.patch("/api/slot-design/demo/features", json=body).status_code == 400, body


def test_bonuses(board):
    c, _ = board
    b = _overview(c)["bonuses"]
    assert b["trail"]["prizepot"] == 2000 and b["trail"]["counts"]["snake"] == 20 and b["free"]["games"] == 3 and b["buy"]["cost"] == 45
    assert c.patch("/api/slot-design/demo/bonuses", json={"trail": {"name": "Warp Trail", "prizepot": 3000, "counts": {"snake": 10}},
                                                          "free": {"games": 5}, "buy": {"enabled": False}}).status_code == 200
    b = _overview(c)["bonuses"]
    assert (b["trail"]["name"], b["trail"]["prizepot"], b["trail"]["counts"]["snake"], b["trail"]["counts"]["heart"]) == ("Warp Trail", 3000, 10, 2)
    assert b["free"]["games"] == 5 and b["buy"]["enabled"] is False
    for body in [{"trail": {"length": 10}}, {"trail": {"counts": {"snake": 40, "crate": 40}}}, {"trail": {"coins": "lots"}},
                 {"free": {"games": 0}}, {"buy": {"cost": 5}}]:
        assert c.patch("/api/slot-design/demo/bonuses", json=body).status_code == 400, body


def test_bonus_switches_and_ways_in(board):
    """Each bonus can be switched off, started by either scatter or neither, and given by Buy Bonus. Bonuses on the
    same way in play one at random; a scatter that starts nothing comes off the reels and the Value ladder."""
    from casino_server.slots.variants.armadillo import VARIANT as A
    c, _ = board
    api = "/api/slot-design/demo/bonuses"
    b = _overview(c)["bonuses"]
    assert b["routes"] == {"BS": ["trail"], "FS": ["free"], "buy": ["trail"]} and b["unused_scatters"] == []
    tiers = _overview(c)["ladder"]["tiers"]
    counts = [{t: strip.count(t) for t in tiers} for strip in A.strips]
    assert c.patch("/api/slot-design/demo/maths", json={"counts": counts}).status_code == 200
    # the free games move onto the bonus scatter: three of it play either; the free-spins scatter leaves the reels
    assert c.patch(api, json={"free": {"scatter": "BS"}}).status_code == 200
    o = _overview(c)
    assert o["bonuses"]["routes"] == {"BS": ["trail", "free"], "FS": [], "buy": ["trail"]} and o["bonuses"]["unused_scatters"] == ["FS"]
    assert "FS" not in o["ladder"]["tiers"] and all(r["FS"] == 0 for r in o["maths"]["counts"])
    assert any("or 3 combo free games, at random" in line for line in o["signoff"]["rules"])
    # the page leaves the scatter out of the reel counts it saves: it's filled in at 0
    assert c.patch("/api/slot-design/demo/maths", json={"counts": [{k: v for k, v in r.items() if k != "FS"} for r in counts]}).status_code == 200
    assert all(r["FS"] == 0 for r in _overview(c)["maths"]["counts"])
    # back on their own scatter, which gets Armadillo's counts back
    assert c.patch(api, json={"free": {"scatter": "FS"}}).status_code == 200
    o = _overview(c)
    assert [r["FS"] for r in o["maths"]["counts"]] == [s.count("FS") for s in A.strips] and "FS" in o["ladder"]["tiers"]
    # Buy Bonus only, and buyable: Buy plays either
    assert c.patch(api, json={"free": {"scatter": None, "buyable": True}}).status_code == 200
    assert _overview(c)["bonuses"]["routes"] == {"BS": ["trail"], "FS": [], "buy": ["trail", "free"]}
    # every bonus that's on needs a way in, and one stays on; a refused change leaves things as they were
    before = _overview(c)["bonuses"]
    for body in [{"buy": {"enabled": False}}, {"free": {"buyable": False}}, {"trail": {"enabled": False}, "free": {"enabled": False}},
                 {"free": {"scatter": "XX"}}]:
        assert c.patch(api, json=body).status_code == 400, body
        assert _overview(c)["bonuses"] == before, body
    # the trail switched off: its pictures aren't needed (the mascot still is, for Wild Reels)
    assert c.patch(api, json={"trail": {"enabled": False}}).status_code == 200
    o = _overview(c)
    assert o["bonuses"]["routes"] == {"BS": [], "FS": [], "buy": ["free"]} and o["bonuses"]["unused_scatters"] == ["BS", "FS"]
    assert not o["art"]["t_coin"]["used"] and o["art"]["armadillo"]["used"]


def test_battle_bonus(board):
    """The wave battle is off until switched on (and then shares the bonus scatter); its settings are checked, and
    switching it on or changing it changes what a freeze measured."""
    from casino_server import slot_design_steps as steps
    c, _ = board
    api = "/api/slot-design/demo/bonuses"
    b = _overview(c)["bonuses"]
    assert not b["battle"]["enabled"] and b["battle"]["name"] == "RED ALERT" and b["battle"]["waves"] == [4, 5, 6, 7, 8]
    assert not _overview(c)["art"]["b_hero"]["used"]
    assert c.patch(api, json={"battle": {"enabled": True}, "trail": {"enabled": False}}).status_code == 200
    o = _overview(c)
    assert o["bonuses"]["routes"] == {"BS": ["battle"], "FS": ["free"], "buy": ["battle"]} and o["art"]["b_enemy"]["used"]
    assert any("RED ALERT" in line for line in o["signoff"]["rules"])
    assert c.patch(api, json={"battle": {"name": "Red Alert!", "enemy": "Bird of Prey", "waves": [3, 4, 5], "return_fire": [0.1, 0.2, 0.3],
                                         "clear": [1, 2, 50], "spins": [[2, 1]], "boss_hits": 4}}).status_code == 200
    bt = _overview(c)["bonuses"]["battle"]
    assert (bt["name"], bt["enemy"], bt["waves"], bt["clear"], bt["boss_hits"]) == ("Red Alert!", "Bird of Prey", [3, 4, 5], [1, 2, 50], 4)
    before = _overview(c)["bonuses"]
    for body in [{"waves": [4, 5]}, {"waves": [0]}, {"return_fire": [0.95, 0.1, 0.1]}, {"shields": 0}, {"spins": [[1.5, 1]]},
                 {"prizes": "lots"}, {"boss_hits": 50}, {"clear": [1, 2, -3]}]:
        assert c.patch(api, json={"battle": body}).status_code == 400, body
        assert _overview(c)["bonuses"] == before, body
    assert steps.battle_maths(bt)["waves"] == [3, 4, 5] and "name" not in steps.battle_maths(bt)


def test_voyage_bonus(board):
    """The island voyage is off until switched on (then shares the bonus scatter); its words and settings are
    checked, and switching it on changes what a freeze measured."""
    from casino_server import slot_design_steps as steps
    c, _ = board
    api = "/api/slot-design/demo/bonuses"
    b = _overview(c)["bonuses"]
    assert not b["voyage"]["enabled"] and b["voyage"]["name"] == "DEAD MAN'S MAP" and b["voyage"]["legs"] == 6
    assert b["voyage"]["artefacts"] == ["COMPASS", "MEDALLION", "SPYGLASS", "CUTLASS"]
    assert not _overview(c)["art"]["v_ship"]["used"]
    assert c.patch(api, json={"voyage": {"enabled": True}, "trail": {"enabled": False}}).status_code == 200
    o = _overview(c)
    assert o["bonuses"]["routes"] == {"BS": ["voyage"], "FS": ["free"], "buy": ["voyage"]} and o["art"]["v_art4"]["used"]
    assert any("DEAD MAN'S MAP" in line for line in o["signoff"]["rules"])
    assert c.patch(api, json={"voyage": {"name": "Treasure Hunt", "artefacts": ["Key", "", "Map", "Idol"], "legs": 4, "coves": 2,
                                         "sink": 0.3, "parts": [1, 2, 3, 40], "relics": [[1, 1], [4, 1]]}}).status_code == 200
    vy = _overview(c)["bonuses"]["voyage"]
    assert (vy["name"], vy["artefacts"], vy["legs"], vy["coves"], vy["parts"]) == ("Treasure Hunt", ["Key", "MEDALLION", "Map", "Idol"], 4, 2, [1, 2, 3, 40])
    before = _overview(c)["bonuses"]
    for body in [{"legs": 1}, {"coves": 4}, {"sink": 0.95}, {"parts": [1, 2, 3]}, {"relics": [[1.5, 1]]}, {"artefacts": ["a"]},
                 {"kinds": [["treasure", 1], ["wreck", 1]]}, {"kinds": [["treasure", 0], ["wreck", 0], ["skull", 0], ["port", 5]]},
                 {"artefact_price": 0}, {"treasure": "lots"}]:
        assert c.patch(api, json={"voyage": body}).status_code == 400, body
        assert _overview(c)["bonuses"] == before, body
    assert steps.voyage_maths(vy)["legs"] == 4 and "name" not in steps.voyage_maths(vy) and "artefacts" not in steps.voyage_maths(vy)


def test_art_slots_and_specs(board):
    c, _ = board
    a = _overview(c)["art"]
    assert a["armadillo"]["step"] == "features" and a["t_coin"]["step"] == "bonuses" and a["barrel"]["file"] is None
    assert c.put("/api/slot-design/demo/art-slots/armadillo", json={"value": "sym:hero"}).status_code == 200
    assert _overview(c)["art"]["armadillo"]["file"] == "chars/hero_1_blue.png"   # follows Hero's chosen take
    c.patch("/api/slot-design/demo/symbols/hero", json={"hue": "red"})
    assert _overview(c)["art"]["armadillo"]["file"] == "chars/hero_1_red.png"
    assert c.put("/api/slot-design/demo/art-slots/barrel", json={"value": "ref/ship.png"}).status_code == 200
    assert c.put("/api/slot-design/demo/art-slots/barrel", json={"value": "ref/none.png"}).status_code == 400
    assert c.put("/api/slot-design/demo/art-slots/teapot", json={"value": None}).status_code == 400
    # adjustments: baked into adj/ (the game and mockup get the tweaked picture), clamped, and cleared by null
    assert c.put("/api/slot-design/demo/art-slots/barrel", json={"adjust": {"mirror": True, "scale": 9}}).status_code == 200
    b = _overview(c)["art"]["barrel"]
    assert b["src"] == "ref/ship.png" and b["file"].startswith("adj/barrel_") and b["adjust"]["mirror"] and b["adjust"]["scale"] == 2.0
    baked = Image.open(io.BytesIO(c.get(f"/slot-design/demo/{b['file']}").content))
    assert baked.size == Image.open(io.BytesIO(c.get("/slot-design/demo/ref/ship.png").content)).size
    assert c.put("/api/slot-design/demo/art-slots/barrel", json={"value": b["file"]}).status_code == 400   # not a source
    assert c.put("/api/slot-design/demo/art-slots/barrel", json={"adjust": {"scale": "big"}}).status_code == 400
    assert c.put("/api/slot-design/demo/art-slots/barrel", json={"adjust": None}).status_code == 200
    b = _overview(c)["art"]["barrel"]
    assert b["file"] == "ref/ship.png" and not b["adjust"]["mirror"]
    assert c.put("/api/slot-design/demo/art-slots/barrel", json={"value": None}).status_code == 200
    spec = c.post("/api/slot-design/demo/specs", json={"kind": "feature", "name": "Red Alert", "description": "All reels flash red..."}).json()
    assert spec["status"] == "spec" and _overview(c)["features"]["specs"][0]["name"] == "Red Alert"
    assert c.post("/api/slot-design/demo/specs", json={"kind": "feature", "name": "X"}).status_code == 400
    assert c.delete(f"/api/slot-design/demo/specs/{spec['id']}").status_code == 200 and not _overview(c)["features"]["specs"]


# ------------------------------------------------------------------ Sprites and Sounds (Phase 5)
def test_own_colours_get_a_shade_and_accent_shadow_of_their_own(board):
    """A design with its own colours gets the ones it never picked from its edge and accent, not Armadillo's."""
    from casino_server.slot_design import Design
    _, d = board
    data = json.loads((d / "design.json").read_text())
    data["sprites"] = {"colours": {"edge": "#4aa9d9", "gold": "#30494f"}}
    (d / "design.json").write_text(json.dumps(data))
    cols = Design(d).data["sprites"]["colours"]
    assert cols["shade"] == "#09141a" and cols["goldLo"] == "#1d2c2f" and cols["ink"] == "#0d1e27"
    assert cols["goldHi"] == "#cbd2d3" and cols["cream"] == "#e9f5fa" and "alert" not in cols


def test_sprites(board):
    c, _ = board
    sp = _overview(c)["sprites"]
    assert sp["win"]["high"]["preset"] == "shine" and sp["colours"]["gold"] == "#f4c94f" and sp["fonts"]["display"] == "Rye-Regular.ttf"
    assert sp["cabinet"]["lines"] == ["DEMO"] and "Cinzel-SemiBold.ttf" in sp["font_list"]
    assert c.patch("/api/slot-design/demo/sprites", json={"win": {"high": {"preset": "bounce", "strength": 1.5, "colour": "#33ccff"}},
        "colours": {"gold": "#33ccff"}, "fonts": {"display": "Cinzel-SemiBold.ttf"},
        "cabinet": {"trim": "#00aaff", "lines": ["star", "trek"]}}).status_code == 200
    sp = _overview(c)["sprites"]
    assert sp["win"]["high"] == {"preset": "bounce", "strength": 1.5, "colour": "#33ccff"} and sp["colours"]["gold"] == "#33ccff"
    assert sp["cabinet"]["lines"] == ["STAR", "TREK"] and sp["cabinet"]["trim"] == "#00aaff" and sp["fonts"]["display"] == "Cinzel-SemiBold.ttf"
    for body in [{"win": {"high": {"preset": "wobble"}}}, {"win": {"high": {"strength": 9}}}, {"colours": {"teal": "#000000"}},
                 {"colours": {"gold": "gold"}}, {"fonts": {"display": "Comic.ttf"}}, {"cabinet": {"lines": ["A", "B", "C"]}}]:
        assert c.patch("/api/slot-design/demo/sprites", json=body).status_code == 400, body
    assert c.get("/slot-design-font/demo/Cinzel-SemiBold.ttf").status_code == 200
    assert c.get("/slot-design-font/demo/..%2Fapp.py").status_code in (400, 404)


def test_sounds(board):
    c, _ = board
    rows = {r["key"]: r for r in _overview(c)["sounds"]["moments"]}
    assert "reel_stop" in rows and rows["reel_stop"]["own"] is None and rows["reel_stop"]["inherited"]["from"] in ("slots", "casino")
    some = c.get("/api/sounds").json()["library"][0]["id"]
    assert c.put("/api/slot-design/demo/sounds/reel_stop", json={"files": [some], "gain_db": -3}).status_code == 200
    assert {r["key"]: r for r in _overview(c)["sounds"]["moments"]}["reel_stop"]["own"] == {"files": [some], "gain_db": -3.0}
    assert c.put("/api/slot-design/demo/sounds/deal", json={"files": [some]}).status_code == 400          # a card table's
    assert c.put("/api/slot-design/demo/sounds/reel_stop", json={"files": ["nope.ogg"]}).status_code == 400
    assert c.put("/api/slot-design/demo/sounds/reel_stop", json={"files": [], "gain_db": 40}).status_code == 400
    assert c.delete("/api/slot-design/demo/sounds/reel_stop").status_code == 200
    assert {r["key"]: r for r in _overview(c)["sounds"]["moments"]}["reel_stop"]["own"] is None


# ------------------------------------------------------------------ Maths & payouts (Phase 6)
MATH_JS = Path(__file__).resolve().parents[2] / "docs/slots/mockup/slots_math.js"
SAMPLE_JS = """
const M = require(process.argv[1]), A = M.ARMADILLO, sample = [];
for (let s = 1; s <= 200; s++) { const bet = M.LADDER[s % 9], o = M.spinOutcome(A, bet, M.mulberry32(s)); sample.push({seed: s, bet, stops: o.stops, total: o.total}); }
console.log(JSON.stringify({counts: A.counts, big_counts: A.bigCounts, strips: A.strips, free_strips: A.freeStrips, big_strip: A.bigStrip,
                            sample, exact: 100 * M.exactLineRtp(A.strips, A.pays)}));
"""


def test_maths_save_and_freeze(board):
    import shutil, subprocess
    if not shutil.which("node"):
        pytest.skip("needs node")
    c, _ = board
    m = _overview(c)["maths"]
    assert m["counts"] is None and not m["frozen"] and m["target"] == 91.5 and m["pays"]["H1"] == [20, 40, 120]
    assert c.patch("/api/slot-design/demo/maths", json={"pays": {"H1": [40, 20, 10]}}).status_code == 400     # must not fall
    assert c.patch("/api/slot-design/demo/maths", json={"pays": {"BS": [1, 2, 3]}}).status_code == 400       # scatters pay nothing
    js = json.loads(subprocess.run(["node", "-e", SAMPLE_JS, str(MATH_JS)], capture_output=True, text=True, check=True).stdout)
    bad_counts = [dict(r) for r in js["counts"]]; bad_counts[0]["BS"] = 5
    assert c.patch("/api/slot-design/demo/maths", json={"counts": bad_counts}).status_code == 400
    assert c.post("/api/slot-design/demo/maths/freeze", json=js).status_code == 400                             # counts not saved
    assert c.patch("/api/slot-design/demo/maths", json={"counts": js["counts"], "big_counts": js["big_counts"]}).status_code == 200
    tampered = {**js, "sample": [{**js["sample"][0], "total": js["sample"][0]["total"] + 1}] + js["sample"][1:]}
    assert c.post("/api/slot-design/demo/maths/freeze", json=tampered).status_code == 400
    assert not _overview(c)["maths"]["frozen"]
    wrong = {**js, "strips": [js["strips"][1]] + js["strips"][1:]}
    assert c.post("/api/slot-design/demo/maths/freeze", json=wrong).status_code == 400
    r = c.post("/api/slot-design/demo/maths/freeze", json={**js, "report": {"rtp": {"game": 87.5}}})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["frozen"] and not m["stale"] and m["check"]["sample"] == 200 and m["report"]["rtp"]["game"] == 87.5
    assert m["strips"] == js["strips"]
    # a later change to what the maths measured makes the freeze stale; a change to the pays or reels drops it
    c.patch("/api/slot-design/demo/features", json={"rates": {"wilds": 0.2}})
    assert _overview(c)["maths"]["stale"]
    c.patch("/api/slot-design/demo/maths", json={"pays": {"L1": [5, 10, 25]}})
    assert not _overview(c)["maths"]["frozen"]


# ------------------------------------------------------------------ Mockup & sign-off (Phase 7)
def _complete(c, d):
    """Fill the demo design's ladder with symbols that have art, and freeze Armadillo's maths for it."""
    import shutil, subprocess
    if not shutil.which("node"):
        pytest.skip("needs node")
    tiers = _overview(c)["ladder"]["tiers"]
    slots = {}
    for t in tiers:
        sid = c.post("/api/slot-design/demo/symbols", json={"name": f"Sym {t}", "category": "set2", "prompt": "x"}).json()["id"]
        _fake_flux().save(d / f"cut/{sid}_1.png")
        slots[t] = sid
    assert c.put("/api/slot-design/demo/ladder", json={"slots": slots}).json()["complete"]
    js = json.loads(subprocess.run(["node", "-e", SAMPLE_JS, str(MATH_JS)], capture_output=True, text=True, check=True).stdout)
    c.patch("/api/slot-design/demo/maths", json={"counts": js["counts"], "big_counts": js["big_counts"]})
    assert c.post("/api/slot-design/demo/maths/freeze", json={**js, "report": {"rtp": {"game": 87.5}}}).status_code == 200


def test_sign_off_locks_how_it_pays(board):
    c, d = board
    so = _overview(c)["signoff"]
    assert not so["ready"] and so["rules"][0].startswith("W stands in")
    assert {x["id"]: x["ok"] for x in so["checklist"]}["ladder"] is False
    assert c.post("/api/slot-design/demo/sign-off").status_code == 400
    _complete(c, d)
    so = _overview(c)["signoff"]
    assert so["ready"] and "Sym W stands in for everything except Sym BS and Sym FS" in so["rules"][0]
    assert c.put("/api/slot-design/demo/rules", json={"lines": ["Line one", "Line two"]}).status_code == 200
    assert _overview(c)["signoff"]["rules"] == ["Line one", "Line two"]
    r = c.post("/api/slot-design/demo/sign-off")
    assert r.status_code == 200 and r.json()["signed_off"]["at"]
    assert {s["id"]: s["status"] for s in _overview(c)["steps"]}["mockup"] == "done"
    for call in [lambda: c.patch("/api/slot-design/demo/maths", json={"pays": {"L1": [5, 10, 25]}}),
                 lambda: c.patch("/api/slot-design/demo/features", json={"rates": {"wilds": 0.2}}),
                 lambda: c.patch("/api/slot-design/demo/bonuses", json={"free": {"games": 4}}),
                 lambda: c.put("/api/slot-design/demo/ladder", json={"slots": {}})]:
        assert call().status_code == 400
    assert c.patch("/api/slot-design/demo/sprites", json={"colours": {"gold": "#33ccff"}}).status_code == 200   # looks aren't locked
    assert c.post("/api/slot-design/demo/reopen").status_code == 200
    assert c.patch("/api/slot-design/demo/features", json={"rates": {"wilds": 0.2}}).status_code == 200
    assert c.put("/api/slot-design/demo/rules", json={"lines": None}).status_code == 200
    assert not _overview(c)["signoff"]["rules_custom"]


# ------------------------------------------------------------------ Build (Phase 8)
def test_bank_shapes():
    from casino_server import slot_builds as sb
    assert {k: len(b["cabinets"]) for k, b in sb.BANKS.items()} == {"single": 1, "double": 2, "quad": 4, "full": 10}
    for k in ("single", "double", "quad"):   # one row, the seats on the camera's side
        assert {f for _, _, f in sb.BANKS[k]["cabinets"]} == {"down"}
    assert [f for _, _, f in sb.BANKS["full"]["cabinets"]].count("up") == 4
    assert sb.cabinet_spots("above_armadillo", "double") == [(1633, 810, "down"), (1667, 810, "down")]
    # a build from before the shapes (a cabinet count) gets the shape of that size
    assert sb.bank_of({"count": 2}) == "double" and sb.bank_of({"bank": "full"}) == "full" and sb.bank_of({"count": 7}) is None


def test_build_and_the_built_slot_joins_the_casino(board, tmp_path, monkeypatch):
    from casino_server import floor, slot_builds, sounds
    from casino_server.slots.variant import from_json
    from casino_server.slots.variants import VARIANTS
    c, d = board
    assert c.post("/api/slot-design/demo/build", json={"spot": "above_armadillo", "bank": "quad"}).status_code == 400  # not signed off
    _complete(c, d)
    c.put("/api/slot-design/demo/sounds/reel_stop", json={"files": [c.get("/api/sounds").json()["library"][0]["id"]]})
    c.post("/api/slot-design/demo/specs", json={"kind": "feature", "name": "Red Alert", "description": "Reels flash red."})
    assert c.post("/api/slot-design/demo/sign-off").status_code == 200
    assert c.post("/api/slot-design/demo/build", json={"spot": "the_roof", "bank": "quad"}).status_code == 400
    assert c.post("/api/slot-design/demo/build", json={"spot": "above_armadillo", "count": 4}).status_code == 400  # a shape, not a size
    r = c.post("/api/slot-design/demo/build", json={"spot": "above_armadillo", "bank": "quad"})
    assert r.status_code == 200, r.text
    assert r.json()["built"]["spot"] == "above_armadillo" and r.json()["built"]["bank"] == "quad" and not r.json()["built"]["loaded"]
    out = tmp_path / "slot_builds" / "demo"
    v = from_json(out / "variant.json")
    assert v.name == "Demo" and v.symbols["H1"] == "Sym H1" and v.theme["frame"]["style"] in ("metal", "wood", "neon", "glass") \
        and v.theme["deck"]["style"] == v.theme["frame"]["style"]
    assert {p.stem for p in (out / "art").glob("*.png")} >= set(v.pays) | {"BS", "FS", "armadillo", "t_coin"}
    assert sorted(p.name for p in (out / "fonts").iterdir()) == ["display.ttf", "ui.ttf"]
    assert "Red Alert" in (out / "IDEAS.md").read_text()
    assert c.post("/api/slot-design/demo/install").status_code == 400   # a test instance: restart it by hand
    # a second design can't take the same spot
    other = c.post("/api/slot-design", json={"name": "Other"}).json()["id"]
    assert other == "other"
    # restarting loads it: its cabinets, its sound set, its art and fonts
    with TestClient(app) as c2:
        assert "demo" in VARIANTS and [t for t in floor.TABLES if t.startswith("demo_")] == ["demo_1", "demo_2", "demo_3", "demo_4"]
        assert "slots.demo" in sounds.SETS and sounds.FACTORY["slots.demo"]["reel_stop"]["files"]
        man = c2.get("/api/slots/art/manifest").json()
        assert set(man["variants"]["demo"]) >= {"H1", "BS", "armadillo"} and set(man["fonts"]["demo"]) == {"display", "ui"}
        assert c2.get(man["variants"]["demo"]["H1"]).headers["content-type"] == "image/png"
        assert c2.get(man["fonts"]["demo"]["ui"]).headers["content-type"] == "font/ttf"
        cab = slot_builds.cabinets()
        # a quad is one row facing the camera
        assert [x["id"] for x in cab] == ["demo_1", "demo_2", "demo_3", "demo_4"] and (cab[0]["x"], cab[0]["y"]) == (1599, 810)
        assert {x["facing"] for x in cab} == {"down"}
        m = c2.app.state.casino.tables["demo_1"].machine
        rules = m.rules()
        assert rules["variant"] == "demo" and rules["theme"]["texts"]["trail"] == "TRAIL BONUS" and rules["pays"]["H1"] == [20, 40, 120]
        from casino_server.slots import jackpots
        from casino_server.slots.rng import mulberry32
        from casino_server.tables.slot_machine import SlotMachine, Timings
        from tests.test_machine import FakeParticipant
        from tests.test_slot_machine import FakeStore
        cab_m = SlotMachine("demo_t", 1, Timings.instant(), variant="demo", progressives=jackpots.SlotProgressives(FakeStore()), rng=mulberry32(3))
        cab_m.sit(0, FakeParticipant("Ann", balance=100_000), 0.0)
        assert cab_m.spin(0, 100, now=0.0)[0]["kind"] == "spin"
        with c2.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "hello"
            ws.send_json({"type": "join", "token": ""})
            welcome = next(m for m in iter(ws.receive_json, None) if m.get("type") == "welcome")
            assert [x["id"] for x in welcome["cabinets"]] == ["demo_1", "demo_2", "demo_3", "demo_4"]
    # another design asking for the taken spot is refused (it doesn't get as far as needing a sign-off)
    assert c.get(f"/api/slot-design/{other}").json()["build"]["spots"][0]["taken_by"] == "Demo"
    slot_builds.install(tmp_path / "nothing")   # leave the module state as the other tests expect
