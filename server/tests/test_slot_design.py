"""The admin page's Slot design board: variants, choices, counts, linked references, New symbols and
generating (with FLUX faked: it draws an orange disc on magenta)."""
import io
import json
import time

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
    monkeypatch.setenv("CASINO_NPCS", "0")
    monkeypatch.setattr(art, "flux_ready", lambda: True)
    monkeypatch.setattr(art, "flux_edit", _fake_flux)
    monkeypatch.setattr(art, "flux_generate", _fake_flux)
    with TestClient(app) as c:
        yield c, d


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


def test_keying_and_the_shared_frame():
    tiles = art.compose_character(_fake_flux())
    assert set(tiles) == set(art.HUES) and all(t.size == (512, 512) for t in tiles.values())
    corner = tiles["gold"].getpixel((2, 2))
    assert corner[3] == 0  # outside the frame is clear
    sym = art.symbol(_fake_flux())
    assert sym.size == (512, 512) and sym.getpixel((256, 256))[:3] == (240, 150, 60)
