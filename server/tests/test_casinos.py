"""Several casinos (casinos.py): the registry, moving a single-casino data dir to Demo, and table-id settings kept by
qualified id."""
import json

from casino_server import casinos, plan, roster
from casino_server.store import Store

from conftest import CLASSIC_PLAN, demo_plan_dir


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
