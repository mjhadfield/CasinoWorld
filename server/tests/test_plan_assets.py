"""The floor plan's asset library (plan_assets.py): the built-in furniture, uploads, edits, and deletes refused while
a room uses them."""
import io
import json

from PIL import Image

from casino_server import plan
from tests.conftest import enter, recv_until


def png(w=40, h=60, colour=(200, 40, 40, 255)) -> bytes:
    im = Image.new("RGBA", (w + 8, h + 8))
    im.paste(Image.new("RGBA", (w, h), colour), (4, 4))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def test_the_built_in_furniture_is_in_the_catalogue_and_the_manifest(client):
    cat = client.get("/api/plan/catalogue").json()
    assert {"fountain", "reception_desk", "plant_tall", "rug_red_large", "banner_red"} <= set(cat["assets"])
    f = cat["assets"]["fountain"]
    assert f["category"] == "Statues & fountains" and f["mount"] == "floor" and f["body"][3] > 0
    assert cat["assets"]["rug_red"]["mount"] == "flat" and cat["assets"]["rug_red"]["body"] is None
    assert set(cat["assets"]["armchair"]["facings"]) == {"down", "up", "left", "right"} and cat["assets"]["armchair"]["facings"]["right"]["mirror"]
    assert {"carpet", "plain", "herringbone", "marble_tiles"} <= set(cat["floors"])
    man = client.get("/api/plan/art").json()
    url = man["assets"]["fountain"]["facings"]["down"]["url"]
    assert url.startswith("/plan-art/fountain.png?v=") and man["floors"]["marble_tiles"].startswith("/plan-art/floors/")
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get("/plan-art/../catalogue.json").status_code == 404


def test_furniture_on_the_plan_is_checked_by_its_footprint():
    p = {"rev": 1, "spawn": "lobby/spawn", "rooms": [plan.lobby()]}
    lobby = p["rooms"][0]
    lobby["items"] = [{"id": "i1", "asset": "a:fountain", "x": 512, "y": 300, "facing": "down", "props": {}},
                      {"id": "i2", "asset": "a:reception_desk", "x": 520, "y": 310, "facing": "down", "props": {}},
                      {"id": "i3", "asset": "a:rug_red_large", "x": 512, "y": 300, "facing": "down", "props": {}}]
    found = [x["message"] for x in plan.problems(p)]
    assert "Lobby: the fountain overlaps the reception desk." in found
    assert not any("rug" in m for m in found)   # (a rug lies under everything)
    lobby["items"].pop(1)
    assert plan.problems(p) == []


def test_upload_edit_turn_and_delete_an_asset(client):
    r = client.put("/api/plan-assets/My_Slot-Sign.png", content=png())
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert aid == "u_my_slot_sign"
    a = client.get("/api/plan/catalogue").json()["assets"][aid]
    assert a["name"] == "My slot sign" and a["category"] == "Uploads" and a["rect"] == [-20, -60, 40, 60]   # (trimmed)
    # edit it: a wall piece, then back on the floor with its own footprint and anchor
    r = client.patch(f"/api/plan-assets/{aid}", json={"name": "Sign", "category": "Decor", "mount": "wall"})
    assert r.status_code == 200 and r.json()["mount"] == "wall" and r.json()["body"] is None
    r = client.patch(f"/api/plan-assets/{aid}", json={"mount": "floor", "anchor": [20, 50], "body": [-18, -12, 36, 12]})
    assert r.json()["rect"] == [-20, -50, 40, 60] and r.json()["body"] == [-18, -12, 36, 12]
    # another way it faces, and one mirrored
    r = client.put(f"/api/plan-assets/{aid}/facings/left", content=png(20, 60))
    assert r.status_code == 200 and r.json()["by_facing"]["left"]["rect"] == [-10, -60, 20, 60]
    r = client.patch(f"/api/plan-assets/{aid}", json={"mirror": {"right": "left"}})
    assert r.json()["facings"]["right"]["mirror"]
    # used in a room: it can't be deleted
    draft = client.get("/api/plan").json()["draft"]
    draft["rooms"][0]["items"].append({"asset": "a:" + aid, "x": 900, "y": 1100, "facing": "left"})
    client.put("/api/plan/draft", json=draft)
    r = client.delete(f"/api/plan-assets/{aid}")
    assert r.status_code == 400 and "Classic floor uses it" in r.json()["detail"]
    draft = client.get("/api/plan").json()["draft"]
    draft["rooms"][0]["items"].pop()
    client.put("/api/plan/draft", json=draft)
    assert client.delete(f"/api/plan-assets/{aid}").status_code == 200
    assert aid not in client.get("/api/plan/catalogue").json()["assets"]
    # built-ins stay
    assert client.delete("/api/plan-assets/fountain").status_code == 400
    assert client.patch("/api/plan-assets/fountain", json={"name": "x"}).status_code == 400


def test_floor_textures_upload_and_bad_pictures_are_refused(client):
    r = client.put("/api/plan-assets/velvet.png?kind=floor", content=png(32, 32))
    assert r.status_code == 200 and "u_velvet" in client.get("/api/plan/catalogue").json()["floors"]
    assert client.put("/api/plan-assets/huge.png", content=png(600, 20)).status_code == 400
    assert client.put("/api/plan-assets/nothing.png", content=b"not a picture").status_code == 400
    clear = io.BytesIO()
    Image.new("RGBA", (10, 10)).save(clear, "PNG")
    assert "see-through" in client.put("/api/plan-assets/clear.png", content=clear.getvalue()).json()["detail"]


def test_players_are_told_when_the_art_changes(client):
    with client.websocket_connect("/ws") as ws:
        enter(ws, hello=True)
        recv_until(ws, "entity_spawn")
        client.put("/api/plan-assets/lamp.png", content=png())
        assert recv_until(ws, "plan_art_changed")["version"] > 0


def test_a_screen_reaches_the_game_and_survives_edits(tmp_path):
    """The Modern lobby's jackpot board is an upload (tools/build_modern_pieces.py) whose screen the game draws on."""
    from casino_server.plan_assets import AssetLibrary
    lib_dir = tmp_path / "plan_assets"
    lib_dir.mkdir()
    (lib_dir / "modern_board.png").write_bytes(png(108, 34))
    (lib_dir / "uploads.json").write_text(json.dumps({"assets": {"modern_board": {
        "name": "Jackpot display", "category": "Wall decor", "mount": "wall", "credit": "",
        "facings": {"down": {"file": "modern_board.png", "anchor": [54, 34]}}, "rect": [-54, -34, 108, 34], "body": None,
        "screen": {"show": "jackpot", "rect": [4, 13, 100, 15]}}}, "floors": {}}))
    lib = AssetLibrary(tmp_path)
    assert lib.manifest()["assets"]["modern_board"]["screen"] == {"show": "jackpot", "rect": [4, 13, 100, 15]}
    assert "screen" not in lib.manifest()["assets"]["fountain"]
    lib.update("modern_board", {"name": "Board"})
    assert lib.manifest()["assets"]["modern_board"]["screen"]["show"] == "jackpot"
    lib.delete("modern_board", [])
    assert "modern_board" not in plan.ASSETS


def test_the_modern_wall_styles_are_kept():
    p = plan.clean({"spawn": "lobby/spawn", "rooms": [{**plan.lobby(), "walls": {"style": "onyx", "sign": "LOBBY"}}]},
                       {"rooms": [], "next": {}})
    assert p["rooms"][0]["walls"]["style"] == "onyx" and "travertine" in plan.WALL_STYLES
