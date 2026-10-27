"""Several casinos (casinos.py): the registry, moving a single-casino data dir to Demo, and table-id settings kept by
qualified id."""
import json
import random

import pytest
from fastapi.testclient import TestClient

from casino_server import casinos, plan, roster
from casino_server.app import app
from casino_server.resort import Resort
from casino_server.store import Store

from conftest import CLASSIC_PLAN, demo_plan_dir, enter, recv_until


def test_a_single_casino_data_dir_becomes_demo(tmp_path):
    data = tmp_path / "old"
    for name in ("live.json", "draft.json"):
        plan._write(plan.plan_dir(data) / name, CLASSIC_PLAN)
    plan._write(plan.plan_dir(data) / "history" / "20261001-000000-r3.json", CLASSIC_PLAN)
    store = Store(data / "casino.sqlite")
    store.set_json("npc_settings", {"population": 9})
    store.set_json("seating", {"styles": {}, "tables": {"tcp_1": "lounge"}})
    store.set_json("table_styles_roulette", {"styles": {}, "tables": {"rou_1": "green"}, "default": "house"})
    roster.seed(store)
    punter = store.npcs("punter")[0]
    store.update_npc(punter["id"], {"settings": {**punter["settings"], "avoid_table": "bj_2"}})

    registry = casinos.migrate(data, store)
    assert registry == [{"id": "demo", "name": "Demo", "blurb": "", "open": True, "order": 0, "population": 9}]
    assert json.loads(casinos.registry_path(data).read_text()) == registry
    assert not plan.plan_dir(data).exists() and plan.load_live(casinos.casino_dir(data, "demo")) == CLASSIC_PLAN
    assert (demo_plan_dir(data) / "history" / "20261001-000000-r3.json").is_file()
    backup = [p for p in data.iterdir() if p.name.startswith("plan-single-casino-")]
    assert len(backup) == 1 and (backup[0] / "live.json").is_file()
    assert store.get_json("seating", {})["tables"] == {"demo/tcp_1": "lounge"}
    assert store.get_json("table_styles_roulette", {})["tables"] == {"demo/rou_1": "green"}
    assert store.npc(punter["id"])["settings"]["avoid_table"] == "demo/bj_2"
    # and again changes nothing
    assert casinos.migrate(data, store) == registry
    assert store.get_json("seating", {})["tables"] == {"demo/tcp_1": "lounge"}
    assert store.npc(punter["id"])["settings"]["avoid_table"] == "demo/bj_2"


def test_no_data_at_all_seeds_demo_with_the_first_plan(tmp_path):
    data = tmp_path / "fresh"
    registry = casinos.migrate(data, Store(tmp_path / "c.sqlite"))
    assert [c["id"] for c in registry] == ["demo"] and registry[0]["population"] == roster.DEFAULT_SETTINGS["population"]
    live = plan.load_live(casinos.casino_dir(data, "demo"))
    assert [r["id"] for r in live["rooms"] if r["placed"]] == ["lobby"]


def test_each_casino_sends_its_own_tables_by_plain_id():
    keyed = {"demo/tcp_1": "a", "boulevard/tcp_1": "b", "demo/rou_1": "c"}
    assert casinos.own(keyed, "demo") == {"tcp_1": "a", "rou_1": "c"}
    assert casinos.own(keyed, "boulevard") == {"tcp_1": "b"}


def test_the_plan_api_takes_a_casino(client):
    assert client.get("/api/plan").json()["draft"]["rooms"] == client.get("/api/plan?casino=demo").json()["draft"]["rooms"]
    assert client.get("/api/plan?casino=nowhere").status_code == 404
    assert client.post("/api/plan/publish?casino=nowhere").status_code == 404


# ------------------------------------------------------------------ two casinos side by side
@pytest.fixture
def two(tmp_path, monkeypatch):
    """Demo and a hidden second casino on the same classic plan, so their table ids clash (tcp_1 in both)."""
    for name in ("live.json", "draft.json"):
        plan._write(plan.plan_dir(casinos.casino_dir(tmp_path, "second")) / name, CLASSIC_PLAN)
    casinos.save(tmp_path, [casinos.entry("demo", "Demo"), casinos.entry("second", "Second", "Upstairs", open_=False)])
    monkeypatch.setenv("CASINO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CASINO_DESIGNS_DIR", str(tmp_path / "slot_designs"))
    monkeypatch.setenv("CASINO_SLOT_BUILDS_DIR", str(tmp_path / "slot_builds"))
    monkeypatch.setenv("CASINO_NPCS", "0")
    with TestClient(app) as c:
        c.app.state.resort.store.set_json("bank_settings", {"start_hand": 1000})
        yield c


def test_two_casinos_share_the_jackpots_but_not_their_tables(two):
    resort = two.app.state.resort
    demo, second = resort.casinos["demo"], resort.casinos["second"]
    assert demo.tables["tcp_1"] is not second.tables["tcp_1"] and demo.floor is not second.floor
    assert demo.jackpot is second.jackpot is resort.jackpot and demo.slot_jackpots is second.slot_jackpots
    assert demo.store is second.store and demo.claims is second.claims


def test_choose_enter_leave_and_enter_the_other(two):
    with two.websocket_connect("/ws") as ws:
        _, welcome = enter(ws, hello=True)
        assert welcome["casino"] == {"id": "demo", "name": "Demo"} and welcome["sound_sets"]["slot_1"] == "slots.armadillo"
        ws.send_json({"type": "leave_casino"})
        assert recv_until(ws, "casino_left")["reason"] == "leave"
        listing = recv_until(ws, "casinos")
        assert [c["id"] for c in listing["list"]] == ["demo"] and listing["last"] == "demo"   # (Second's hidden)
        assert listing["list"][0]["tables"] == 15 and listing["list"][0]["players"] == 0
        ws.send_json({"type": "sit", "table": "tcp_1", "seat": 0})
        assert recv_until(ws, "error")["message"] == "Choose a casino first."
        ws.send_json({"type": "enter_casino", "casino": "second"})   # (a hidden one, by its id)
        assert recv_until(ws, "welcome")["casino"]["id"] == "second"
        assert two.app.state.resort.where(welcome["player"]["id"]) == "second"
        ws.send_json({"type": "leave_casino"})
        assert recv_until(ws, "casinos")["last"] == "second"   # (now it lists Second too: the one you were last in)
        ws.send_json({"type": "enter_casino", "casino": "nowhere"})
        assert recv_until(ws, "error")["message"] == "There's no such casino."


def test_you_only_see_and_hear_your_own_casino(two):
    with two.websocket_connect("/ws") as a, two.websocket_connect("/ws") as b:
        _, wa = enter(a, hello=True, name="Ann")
        _, wb = enter(b, hello=True, name="Bob", casino="second")
        a.send_json({"type": "sit", "table": "tcp_1", "seat": 0})
        recv_until(a, "seated")
        a.send_json({"type": "bet", "spot": "ante", "amount": 500})
        recv_until(a, "table_event", "bet_changed")
        b.send_json({"type": "ping", "t": 1})
        seen = []
        while (msg := b.receive_json())["type"] != "pong":
            seen.append(msg)
        assert not [m for m in seen if m["type"] == "table_event"
                    or (m["type"].startswith("entity_") and m.get("entity", m).get("id") != wb["entity_id"])], seen
        assert two.app.state.resort.casinos["second"].tables["tcp_1"].machine.seats[0].participant is None


def test_a_reconnect_resumes_in_the_same_casino(two):
    with two.websocket_connect("/ws") as ws:
        account, welcome = enter(ws, hello=True, casino="second")
    pid = welcome["player"]["id"]
    with two.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "token": account["token"]})
        recv_until(ws, "account")
        ws.send_json({"type": "pick_character", "id": pid, "resume": True})   # (last_casino, when the client has none)
        assert recv_until(ws, "welcome")["casino"]["id"] == "second"
    with two.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "token": account["token"]})
        recv_until(ws, "account")
        ws.send_json({"type": "pick_character", "id": pid, "resume": True, "casino": "demo"})
        assert recv_until(ws, "welcome")["casino"]["id"] == "demo"


def test_an_npc_is_never_in_two_casinos_at_once(tmp_path):
    for cid in ("demo", "second"):
        for name in ("live.json", "draft.json"):
            plan._write(plan.plan_dir(casinos.casino_dir(tmp_path, cid)) / name, CLASSIC_PLAN)
    registry = [casinos.entry("demo", "Demo", population=12), casinos.entry("second", "Second", population=12)]
    now = [1_000_000.0]
    store = Store(tmp_path / "c.sqlite")
    resort = Resort(store, tmp_path, registry=registry, rng=random.Random(4), clock=lambda: now[0], wall=lambda: now[0])
    punters = len(store.npcs("punter"))
    both = list(resort.casinos.values())
    most = 0
    for _ in range(1500):
        now[0] += 0.5
        for casino in both:
            casino.npcs.tick(now[0])
        here = [{n.npc_id for n in c.npcs.npcs.values()} | set(c.dealers.status()) for c in both]
        assert not here[0] & here[1]
        assert {n: c for n, c in resort.claims.by_npc.items()} == {n: c.id for c in both for n in here[both.index(c)]}
        most = max(most, sum(c.npcs.here() for c in both))
    assert most > min(12, punters // 2)   # (both casinos had visitors)
    assert all(c.dealers.status() for c in both)   # (and their own dealers)


def test_a_jackpot_won_in_one_casino_reaches_the_other(two):
    with two.websocket_connect("/ws") as a, two.websocket_connect("/ws") as b:
        enter(a, hello=True, name="Ann")
        enter(b, hello=True, name="Bob", casino="second")
        two.app.state.resort.casinos["demo"].tables["tcp_1"]._side_effects({"kind": "jackpot_won", "seat": 0, "amount": 100})
        assert recv_until(a, "jackpot", where=lambda m: "table" in m)["table"] == "tcp_1"
        b.send_json({"type": "ping", "t": 3})
        pots = [m for m in _until_pong(b) if m["type"] == "jackpot"]
        assert len(pots) == 2 and "table" not in pots[1]   # (the one on entering, then the win: their tcp_1 is another table)


def test_publishing_new_tables_reloads_only_that_casino(two):
    resort = two.app.state.resort
    old_demo, second = resort.casinos["demo"], resort.casinos["second"]
    second_tasks = list(second._tasks)
    with two.websocket_connect("/ws") as a, two.websocket_connect("/ws") as b:
        _, wa = enter(a, hello=True, name="Ann")
        enter(b, hello=True, name="Bob", casino="second")
        draft = two.get("/api/plan?casino=demo").json()["draft"]
        room = next(r for r in draft["rooms"] if r["placed"])
        room["items"] = [i for i in room["items"] if i["id"] != "tcp_1"]
        assert two.put("/api/plan/draft?casino=demo", json=draft).json()["restart"]
        r = two.post("/api/plan/publish?casino=demo").json()
        assert r.get("restart") and "reopened" in r["message"], r
        assert recv_until(a, "casino_left")["reason"] == "reload"
        again = recv_until(a, "welcome")
        assert again["casino"]["id"] == "demo" and again["player"] == wa["player"]
        new_demo = resort.casinos["demo"]
        assert new_demo is not old_demo and "tcp_1" not in new_demo.tables and not old_demo._tasks
        assert resort.boards["demo"].floor is new_demo.floor
        assert second is resort.casinos["second"] and second._tasks == second_tasks
        assert not any(t.done() for t in second_tasks) and "tcp_1" in second.tables
        b.send_json({"type": "ping", "t": 2})
        assert not [m for m in _until_pong(b) if m["type"] in ("casino_left", "welcome")]   # (Bob carried on)
        a.send_json({"type": "sit", "table": "bj_1", "seat": 0})
        assert recv_until(a, "seated")["table"] == "bj_1"


def _until_pong(ws) -> list:
    seen = []
    while (msg := ws.receive_json())["type"] != "pong":
        seen.append(msg)
    return seen


def test_the_admin_page_makes_changes_and_deletes_casinos(two):
    resort = two.app.state.resort
    r = two.post("/api/casinos", json={"name": "  The   Boulevard ", "blurb": "Big and new", "start": "lobby"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    new = next(c for c in r.json()["casinos"] if c["id"] == cid)
    assert cid == "the_boulevard" and new["name"] == "The Boulevard" and not new["open"] and new["population"] == 0
    assert [rm["id"] for rm in resort.boards[cid].floor.plan["rooms"]] == ["lobby"] and resort.casinos[cid].floor.spawn
    copied = two.post("/api/casinos", json={"name": "Second", "start": "copy:second"}).json()["id"]
    assert copied == "second_2" and set(resort.casinos[copied].tables) == set(resort.casinos["second"].tables)
    assert two.post("/api/casinos", json={"name": "", "start": "lobby"}).status_code == 400
    assert two.post("/api/casinos", json={"name": "X", "start": "copy:nowhere"}).status_code == 400
    with two.websocket_connect("/ws") as ws:
        enter(ws, hello=True)
        ws.send_json({"type": "leave_casino"})
        recv_until(ws, "casinos")
        r = two.put(f"/api/casinos/{cid}", json={"open": True, "population": 4, "order": 0, "name": "Boulevard"})
        assert r.status_code == 200 and r.json()["casinos"][0]["id"] == cid
        assert [c["id"] for c in recv_until(ws, "casinos")["list"]] == [cid, "demo"]   # (the chooser hears)
        assert resort.casinos[cid].population() == 4
        assert two.put(f"/api/casinos/{cid}", json={"population": 99}).status_code == 400
        ws.send_json({"type": "enter_casino", "casino": cid})
        recv_until(ws, "welcome")
        assert two.delete(f"/api/casinos/{cid}").status_code == 400   # (someone's in it)
    assert two.delete(f"/api/casinos/{cid}").status_code == 200
    assert cid not in resort.casinos and cid not in two.app.state.boards
    assert [c["id"] for c in two.get("/api/casinos").json()["casinos"]] == ["demo", "second", copied]
    assert two.get(f"/api/plan?casino={cid}").status_code == 404
    two.delete(f"/api/casinos/{copied}")
    two.delete("/api/casinos/second")
    assert two.delete("/api/casinos/demo").status_code == 400   # (the last one)


def test_a_hidden_casino_leaves_the_dealers_to_the_open_ones(tmp_path):
    for cid in ("demo", "site"):
        for name in ("live.json", "draft.json"):
            plan._write(plan.plan_dir(casinos.casino_dir(tmp_path, cid)) / name, CLASSIC_PLAN)
    registry = [casinos.entry("demo", "Demo", population=0), casinos.entry("site", "Site", open_=False, population=0)]
    now = [1_000_000.0]
    resort = Resort(Store(tmp_path / "c.sqlite"), tmp_path, registry=registry, rng=random.Random(2),
                    clock=lambda: now[0], wall=lambda: now[0])
    demo, site = resort.casinos["demo"], resort.casinos["site"]
    for _ in range(3):
        now[0] += 60 * 60   # (shifts end: reliefs come from the free dealers)
        for casino in (demo, site):
            for runner in casino.tables.values():
                runner.machine.phase = "betting"
            casino.dealers.tick(now[0])
    assert site.dealers.status() == {} and len(demo.dealers.status()) == 15
    resort.change_casino("site", {"open": True})   # (opened: named dealers come on at the next reliefs)
    now[0] += 60 * 60
    for runner in site.tables.values():
        runner.machine.phase = "betting"
    site.dealers.tick(now[0])
    assert site.dealers.status() and not set(site.dealers.status()) & set(demo.dealers.status())
