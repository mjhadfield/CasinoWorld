"""The admin page and its API: NPCs, looks, settings, players, sound sets."""
import re
from pathlib import Path

from conftest import recv_until  # noqa: F401  (the client fixture lives in conftest)

ADMIN_WEB = Path(__file__).resolve().parents[1] / "casino_server" / "admin_web"


def test_the_admin_page_and_every_file_it_names_are_served(client):
    page = client.get("/admin")
    assert page.status_code == 200 and "/admin-ui/shell.js" in page.text
    assert client.get("/maintenance").text == page.text
    assert client.get("/admin/next", follow_redirects=False).headers["location"] == "/admin"
    named = {m for f in ADMIN_WEB.rglob("*") if f.suffix in (".js", ".html", ".css")
             for m in re.findall(r"/admin-ui/[\w./-]+\.\w+", f.read_text())}
    assert len(named) > 10
    for url in sorted(named):
        assert client.get(url).status_code == 200, url


def test_the_roster_is_seeded_and_listed(client):
    data = client.get("/api/npcs").json()
    roles = [n["role"] for n in data["npcs"]]
    assert roles.count("punter") == 20 and roles.count("dealer") == 20
    assert all(n["look_url"] for n in data["npcs"])         # every look is built at startup
    assert data["settings"]["population"] == 6
    sheet = client.get(data["npcs"][0]["look_url"])
    assert sheet.status_code == 200 and sheet.headers["content-type"] == "image/png"


def test_create_edit_and_delete_an_npc(client):
    opts = client.get("/api/npc-options").json()
    assert {s["slot"] for s in opts["slots"]} >= {"hair", "top", "bottom"} and "whale" in opts["modifiers"]
    look = {"body": "female", "skin": "olive", "hair": ["bob", "black"], "top": ["tshirt", "teal"],
            "bottom": ["pants", "navy"], "shoes": ["shoes", "black"]}
    r = client.post("/api/npcs", json={"name": "Wendy", "role": "punter", "look": look, "archetype": "gambler",
                                       "traits": ["whale", "vip"], "settings": {"budget_min": 100_000, "budget_max": 500_000}})
    assert r.status_code == 200, r.text
    npc = r.json()
    assert npc["traits"] == ["whale", "vip"] and npc["look_url"].startswith("/looks/x_")
    r = client.put(f"/api/npcs/{npc['id']}", json={"look": {**look, "glasses": ["round", "gold"]}, "traits": ["chaser"]})
    assert r.status_code == 200 and r.json()["look_id"] != npc["look_id"] and r.json()["traits"] == ["chaser"]
    assert client.put(f"/api/npcs/{npc['id']}", json={"look": {**look, "top": ["formal", "white"]}}).status_code == 400  # no female fit
    assert client.post("/api/npcs", json={"name": "", "look": look}).status_code == 400
    assert client.delete(f"/api/npcs/{npc['id']}").status_code == 400   # only from the archive
    assert client.post(f"/api/npcs/{npc['id']}/archive").status_code == 200
    assert client.delete(f"/api/npcs/{npc['id']}").status_code == 200
    assert client.get(f"/api/npcs/{npc['id']}").status_code == 404


def test_bring_in_and_send_home(client):
    npc = next(n for n in client.get("/api/npcs").json()["npcs"] if n["role"] == "punter")
    r = client.post(f"/api/npcs/{npc['id']}/bring-in")
    assert r.status_code == 200 and r.json()["on_floor"]["state"] in ("walking", "loitering")
    assert client.post(f"/api/npcs/{npc['id']}/send-home").status_code == 200
    detail = client.get(f"/api/npcs/{npc['id']}").json()
    assert detail["visits"] and detail["visits"][0]["reason"] == "admin"


def test_settings_and_players(client):
    r = client.put("/api/npc-settings", json={"population": 9, "cooldown_min": [10, 20], "dealer_shift_min": 15})
    assert r.status_code == 200 and r.json()["population"] == 9 and r.json()["cooldown_min"] == [10, 20]
    assert client.put("/api/npc-settings", json={"population": 99}).status_code == 400
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "token": ""})
        recv_until(ws, "welcome")
    players = client.get("/api/players").json()["players"]
    assert players and players[0]["wagered"] == 0 and "net" in players[0]


def test_preview_and_credits(client):
    look = {"body": "male", "skin": "brown", "hair": ["afro", "black"], "top": ["formal", "white"],
            "over": ["vest", "black"], "neck": ["bowtie", "black"], "bottom": ["formal", "black"], "shoes": ["shoes", "black"]}
    r = client.post("/api/looks/preview", json={"look": look})
    assert r.status_code == 200 and client.get(r.json()["url"]).status_code == 200
    assert client.post("/api/looks/preview", json={"look": {"body": "male"}}).status_code == 400
    assert "LPC" in client.get("/credits").text


def test_sound_sets_group_the_games(client):
    data = client.get("/api/sounds").json()
    groups = {s["key"]: s["group"] for s in data["sets"]}
    assert groups["casino"] == "" and groups["roulette"] == "Table games" and groups["slots.armadillo"] == "Slot machines"
    assert data["moments"]["ball_spin"]["home"] == "roulette" and data["moments"]["reel_spin"]["loop"]
    assert {s["group"] for s in data["library"]} >= {"kenney-casino", "slots", "western"}


def test_bulk_generate_then_create(client):
    before = {n["name"] for n in client.get("/api/npcs").json()["npcs"]}
    r = client.post("/api/npcs/generate", json={"count": 10, "role": "punter", "archetype": "casual"})
    assert r.status_code == 200, r.text
    drafts = r.json()["drafts"]
    assert len(drafts) == 10 and all(d["archetype"] == "casual" and d["traits"] == [] for d in drafts)
    names = [d["name"] for d in drafts]
    assert len(set(names)) == 10 and not set(names) & before                  # fresh names, no repeats
    assert all(client.get(d["look_url"]).status_code == 200 for d in drafts)  # previews are built
    assert client.get("/api/npcs").json()["npcs"].__len__() == len(before)    # nothing saved yet
    more = client.post("/api/npcs/generate", json={"count": 5, "role": "dealer", "body": "female", "taken": names}).json()["drafts"]
    assert all(d["look"]["body"] == "female" and d["look"]["neck"] == ["bowtie", "black"] and d["archetype"] == "" for d in more)
    assert not {d["name"] for d in more} & set(names)
    seeded = client.post("/api/npcs/generate", json={"count": 3, "traits": ["superstitious", "regular"]}).json()["drafts"]
    assert all(d["traits"] == ["superstitious", "regular"] and d["settings"]["lucky_numbers"] for d in seeded)
    assert {d["archetype"] for d in seeded} <= {"grinder", "casual", "gambler"}
    # review: tweak one, then accept them all
    drafts[0]["traits"] = ["whale"]
    drafts[1]["name"] = "Bulky"
    r = client.post("/api/npcs/bulk", json={"npcs": drafts + more})
    assert r.status_code == 200, r.text
    made = r.json()["npcs"]
    assert len(made) == 15 and made[0]["traits"] == ["whale"] and made[1]["name"] == "Bulky"
    assert len(client.get("/api/npcs").json()["npcs"]) == len(before) + 15


def test_bulk_create_is_all_or_nothing(client):
    count = len(client.get("/api/npcs").json()["npcs"])
    drafts = client.post("/api/npcs/generate", json={"count": 3}).json()["drafts"]
    drafts[2]["name"] = drafts[0]["name"]
    r = client.post("/api/npcs/bulk", json={"npcs": drafts})
    assert r.status_code == 400 and "already someone" in r.json()["detail"]
    drafts[2]["name"] = "Fine"
    drafts[1]["traits"] = ["telepath"]
    assert client.post("/api/npcs/bulk", json={"npcs": drafts}).status_code == 400
    assert len(client.get("/api/npcs").json()["npcs"]) == count
    assert client.post("/api/npcs/generate", json={"count": 31}).status_code == 400
    assert client.post("/api/npcs/generate", json={"count": 2, "archetype": "maniac"}).status_code == 400


def test_names_never_run_out():
    import random
    from casino_server import roster
    taken = set()
    for _ in range(6):
        for d in roster.generate(30, body="male", taken=taken, rng=random.Random(len(taken))):
            assert d["name"] not in taken
            taken.add(d["name"])
    assert len(taken) == 180
