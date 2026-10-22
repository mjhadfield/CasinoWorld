"""The floor plan (plan.py): rooms and what's in them, the checks, ids, publishing, previews, and the NPCs and
settings that live off it."""
import copy
import json
import random

import pytest

from casino_server import floor, plan, table_styles
from casino_server.casino import Casino
from casino_server.store import Store
from tests.conftest import CLASSIC_PLAN, recv_until


def lobby_only() -> dict:
    p = plan.first_plan()
    return {**p, "rooms": [r for r in p["rooms"] if r["id"] == "lobby"]}


def room(p: dict, rid: str) -> dict:
    return next(r for r in p["rooms"] if r["id"] == rid)


def messages(p: dict) -> list[str]:
    return [x["message"] for x in plan.problems(p)]


# ------------------------------------------------------------------ the first plan
def test_first_run_seeds_the_lobby_live_and_the_classic_floor_in_the_library(tmp_path):
    tmp_path = tmp_path / "fresh"
    live = plan.load_live(tmp_path)
    assert [(r["id"], r["placed"]) for r in live["rooms"]] == [("lobby", True), ("classic_floor", False), ("classic_pit", False)]
    assert (plan.plan_dir(tmp_path) / "draft.json").is_file() and live["spawn"] == "lobby/spawn"
    lobby = room(live, "lobby")
    assert (lobby["w"], lobby["h"]) == (1024, 640) and lobby["doors"] == [{"id": "d1", "side": "top", "at": 512, "width": 64, "kind": "door"}]
    assert not [p for p in plan.problems(live) if p["placed"]]
    plan.install(live)
    assert floor.TABLES == {} and floor.SPAWN == "lobby/spawn" and floor.arrivals() == ["lobby/arrival"]
    # the classic tables are kept, by their ids, in the library
    assert {"tcp_1", "bj_5", "crp_1"} <= set(plan.tables_of(live, placed_only=False))
    # and new ones never take their ids
    assert live["next"]["bj"] == 6 and live["next"]["tcp"] == 2


def test_the_classic_plan_is_clean_and_puts_every_table_on_the_floor():
    assert plan.problems(CLASSIC_PLAN) == []
    assert len([t for t, c in floor.TABLES.items() if c["game"] != "slots"]) == 15
    assert floor.TABLES["lir_1"]["seats"] == 5 and floor.TABLES["slot_3"] == {"game": "slots", "variant": "armadillo", "name": "Armadillo Goes West", "seats": 1}
    # the archway between the floor and the pit belongs to both rooms
    ops, probs = plan.openings([r for r in CLASSIC_PLAN["rooms"] if r["placed"]])
    assert probs == []
    assert [(o["side"], o["to"], o["kind"]) for o in ops["classic_floor"]] == [("bottom", None, "door"), ("right", "classic_pit", "archway")]
    assert [(o["side"], o["at"], o["to"]) for o in ops["classic_pit"]] == [("left", 830, "classic_floor")]


# ------------------------------------------------------------------ ids
def test_ids_are_given_by_the_server_and_never_given_again():
    old = lobby_only()
    raw = copy.deepcopy(old)
    room(raw, "lobby")["items"] = [{"asset": "table:blackjack", "x": 300, "y": 300}, {"asset": "slot", "x": 700, "y": 300, "props": {"variant": "armadillo"}},
                                   {"asset": "podium", "x": 500, "y": 500}]
    p = plan.clean(raw, old)
    ids = [i["id"] for i in room(p, "lobby")["items"]]
    assert ids == ["bj_6", "slot_1", "i3"] and room(p, "lobby")["items"][0]["props"]["label"] == "Blackjack"
    # take the table away and put another down: it's a new table
    raw = copy.deepcopy(p)
    room(raw, "lobby")["items"][0] = {"asset": "table:blackjack", "x": 300, "y": 300}
    p2 = plan.clean(raw, p)
    assert room(p2, "lobby")["items"][0]["id"] == "bj_7"
    # an id kept moves with its thing; one claiming another game's id is a new table
    raw = copy.deepcopy(p2)
    room(raw, "lobby")["items"][0]["x"] = 320
    room(raw, "lobby")["items"][1]["asset"] = "table:roulette"
    p3 = plan.clean(raw, p2)
    assert [i["id"] for i in room(p3, "lobby")["items"][:2]] == ["bj_7", "rou_2"]


def test_new_rooms_get_ids_from_their_names():
    raw = lobby_only()
    raw["rooms"].append({"name": "The Bar!", "x": 0, "y": -600, "w": 800, "h": 600})
    raw["rooms"].append({"name": "The Bar!", "x": 0, "y": -1200, "w": 800, "h": 600})
    p = plan.clean(raw, lobby_only())
    assert [r["id"] for r in p["rooms"]] == ["lobby", "the_bar", "the_bar_2"]


def test_floor_patches_keep_their_look_and_fall_back_to_plain():
    raw = lobby_only()
    raw["rooms"][0]["patches"] = [
        {"x": 100, "y": 200, "w": 160, "h": 96, "texture": "carpet", "tint": "#ffffff", "shape": "oval",
         "pattern": {"kind": "diamonds", "colour": "#102030", "size": 24, "opacity": 45},
         "border": {"style": "inlay", "colour": "#aa8844", "width": 10}},
        {"x": 0, "y": 0, "w": 64, "h": 64, "shape": "star", "pattern": {"kind": "paisley"}, "border": "gold"},
        {"x": 0, "y": 0, "w": 64, "h": 64}]   # (from before patches had a look)
    rugs = plan.clean(raw, lobby_only())["rooms"][0]["patches"]
    assert rugs[0]["shape"] == "oval" and rugs[0]["tint"] == "#ffffff"
    assert rugs[0]["pattern"] == {"kind": "diamonds", "colour": "#102030", "size": 24, "opacity": 45}
    assert rugs[0]["border"] == {"style": "inlay", "colour": "#aa8844", "width": 10}
    for rug in rugs[1:]:
        assert (rug["shape"], rug["pattern"]["kind"], rug["border"]["style"]) == ("rect", "none", "none")
    raw["rooms"][0]["patches"] = [{"x": 0, "y": 0, "w": 64, "h": 64, "pattern": {"kind": "dots", "size": 2}}]
    with pytest.raises(plan.PlanError):   # (a pattern that fine would be thousands of shapes)
        plan.clean(raw, lobby_only())


def test_malformed_plans_are_refused():
    old = lobby_only()
    for bad in ({}, {"rooms": [{"name": "x", "w": 10, "h": 10}]}, {"rooms": [{"name": "x", "w": 800, "h": 600, "doors": [{"side": "up"}]}]},
                {"rooms": [{"name": "x", "w": 800, "h": 600, "items": [{"asset": "table:poker", "x": 1, "y": 1}]}]}):
        with pytest.raises(plan.PlanError):
            plan.clean(bad, old)


# ------------------------------------------------------------------ the checks
def test_things_in_each_others_way_off_the_floor_or_out_of_reach():
    p = lobby_only()
    lobby = room(p, "lobby")
    lobby["items"] = [{"id": "bj_6", "asset": "table:blackjack", "rot": 0, "x": 300, "y": 300, "props": {"label": "Blackjack"}},
                      {"id": "bj_7", "asset": "table:blackjack", "rot": 0, "x": 450, "y": 300, "props": {"label": "Blackjack"}},
                      {"id": "rou_2", "asset": "table:roulette", "rot": 0, "x": 990, "y": 400, "props": {"label": "Roulette"}}]
    found = messages(p)
    assert "Lobby: Blackjack (bj_6) overlaps Blackjack (bj_7)." in found
    assert "Lobby: Roulette (rou_2) is off the floor." in found
    # a table walled in by a block zone: nobody can get to its seats
    lobby["items"] = [lobby["items"][0]]
    lobby["paths"]["zones"] = [{"x": 100, "y": 330, "w": 420, "h": 60, "kind": "block"}]
    assert "Lobby: players can't reach Blackjack (bj_6)." in messages(p)
    # an NPC-only zone keeps NPCs out but lets players by
    lobby["paths"]["zones"][0]["kind"] = "npc_block"
    found = messages(p)
    assert "Lobby: NPCs can't reach Blackjack (bj_6)." in found and "Lobby: players can't reach Blackjack (bj_6)." not in found


def test_slot_cabinets_may_stand_back_to_back_but_not_on_each_other():
    p = lobby_only()
    lobby = room(p, "lobby")
    cab = {"asset": "slot", "props": {"variant": "armadillo"}}
    lobby["items"] = [{**cab, "id": "slot_1", "x": 500, "y": 300, "facing": "up"}, {**cab, "id": "slot_2", "x": 500, "y": 326, "facing": "down"}]
    assert messages(p) == []
    lobby["items"][1]["y"] = 305
    assert messages(p) == ["Lobby: the slot cabinet slot_1 overlaps the slot cabinet slot_2."]


def test_doors_must_join_rooms_squarely():
    p = lobby_only()
    bar = {"id": "bar", "name": "Bar", "placed": True, "x": 256, "y": -400, "w": 512, "h": 400, "floor": {"texture": "carpet", "tint": "#ffffff"},
           "patches": [], "walls": {"style": "navy", "sign": "BAR", "sign_at": 256}, "doors": [], "items": [],
           "paths": {"points": [{"name": "stool", "x": 256, "y": 300, "kind": "wander", "weight": 1, "linger": 5}], "zones": []}}
    p["rooms"].append(bar)
    # the lobby's top door (x 480..544) opens into the bar's front wall: they're joined, and the bar can be reached
    assert messages(p) == []
    ops, _ = plan.openings([r for r in p["rooms"] if r["placed"]])
    assert ops["lobby"][0]["to"] == "bar" and ops["bar"] == [{**ops["lobby"][0], "side": "bottom", "at": 256, "to": "lobby"}]
    # the bar placed so the door's only half under it
    bar["x"] = 520
    assert "Lobby: a door half opens onto Bar." in messages(p)
    # both rooms with a door there, of different kinds
    bar["x"] = 256
    bar["doors"] = [{"id": "d9", "side": "bottom", "at": 256, "width": 64, "kind": "archway"}]
    assert "Lobby and Bar have different doors in the same place." in messages(p)
    bar["doors"][0]["kind"] = "door"   # the same door, kept once
    assert messages(p) == [] and len(plan.openings([r for r in p["rooms"] if r["placed"]])[0]["lobby"]) == 1
    # rooms overlapping on the plan; nobody reaching the bar through a wall
    bar["doors"], bar["y"] = [], -390
    found = messages(p)
    assert "Lobby overlaps Bar on the plan." in found


def test_a_plan_needs_somewhere_for_players_to_appear():
    p = lobby_only()
    room(p, "lobby")["paths"]["points"] = [pt for pt in room(p, "lobby")["paths"]["points"] if pt["kind"] != "spawn"]
    assert "Players have nowhere to appear: give a placed room a spawn point." in messages(p)


# ------------------------------------------------------------------ the page: save, publish, discard, roll back
def test_save_publish_and_roll_back(client, tmp_path):
    view = client.get("/api/plan").json()
    draft = view["draft"]
    assert view["pending"] == [] and not view["restart"] and view["can_publish"]
    # moving a table needs no restart: the floor changes at once
    room(draft, "classic_floor")["items"][0]["x"] += 10
    r = client.put("/api/plan/draft", json={**draft, "base_rev": draft["rev"]})
    assert r.status_code == 200 and r.json()["pending"] == ["Classic floor"] and not r.json()["restart"]
    # saving over a newer draft (another tab) is refused
    assert client.put("/api/plan/draft", json={**draft, "base_rev": draft["rev"]}).status_code == 409
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "join", "token": ""})
        recv_until(ws, "entity_spawn")
        r = client.post("/api/plan/publish")
        assert r.status_code == 200 and not r.json()["restart"] and r.json()["message"] == "Published: the floor has changed."
        world = recv_until(ws, "world")["world"]
        assert [i["x"] for i in room(world, "classic_floor")["items"] if i["id"] == "tcp_1"] == [310]
    assert json.loads((plan.plan_dir(tmp_path) / "live.json").read_text())["rooms"][0]["items"][0]["x"] == 310
    # adding a table does: a test instance says so instead
    draft = client.get("/api/plan").json()["draft"]
    room(draft, "classic_floor")["items"].append({"asset": "table:baccarat", "x": 1500, "y": 1040})
    view = client.put("/api/plan/draft", json={**draft, "base_rev": draft["rev"]}).json()
    assert view["restart"] and not view["can_publish"]   # (it doesn't fit there)
    assert client.post("/api/plan/publish").status_code == 400
    # throw the draft away: back to the live floor
    view = client.post("/api/plan/discard").json()
    assert view["pending"] == [] and len(room(view["draft"], "classic_floor")["items"]) == len(room(CLASSIC_PLAN, "classic_floor")["items"])
    # the publish before is in the history, and can be put back in the draft
    hist = client.get("/api/plan/history").json()
    assert len(hist) == 1 and hist[0]["tables"] == 25
    view = client.post(f"/api/plan/rollback/{hist[0]['id']}").json()
    assert view["pending"] == ["Classic floor"] and room(view["draft"], "classic_floor")["items"][0]["x"] == 300
    assert client.post("/api/plan/rollback/nonsense").status_code == 400


def test_a_preview_shows_the_draft_and_has_no_body(client):
    draft = client.get("/api/plan").json()["draft"]
    draft["rooms"].append({"name": "Bar", "x": 0, "y": -600, "w": 800, "h": 500,
                           "paths": {"points": [{"name": "in", "x": 400, "y": 400, "kind": "wander"}]}})
    client.put("/api/plan/draft", json=draft)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "join", "token": "", "preview": "bar"})
        welcome = recv_until(ws, "welcome")
        assert welcome["preview"] == "bar" and [r["id"] for r in welcome["world"]["rooms"]] == ["bar"]
        assert welcome["world"]["start"] == {"x": 400, "y": -200}
        assert client.app.state.casino.joined_sessions() == [] and client.app.state.casino.world.entities == {}
        # saving the draft shows it again
        draft = client.get("/api/plan").json()["draft"]
        room(draft, "bar")["w"] = 900
        client.put("/api/plan/draft", json=draft)
        assert room(recv_until(ws, "world")["world"], "bar")["w"] == 900
        ws.send_json({"type": "sit", "table": "tcp_1", "seat": 0})   # (looking only: nothing happens)
        ws.send_json({"type": "ping", "t": 1})
        assert recv_until(ws, "pong")["t"] == 1


# ------------------------------------------------------------------ NPCs and settings
def test_nobody_visits_an_empty_floor(tmp_path):
    plan.install(lobby_only())
    now = [1000.0]
    casino = Casino(Store(tmp_path / "c.sqlite"), npc_population=6, rng=random.Random(1), clock=lambda: now[0], wall=lambda: now[0])
    for _ in range(100):
        now[0] += 0.5
        casino.npcs.tick(now[0])
    assert casino.npcs.npcs == {}


def test_npcs_wander_to_one_point_and_walk_as_far_as_the_doors_take_them(tmp_path):
    p = copy.deepcopy(CLASSIC_PLAN)
    for r in p["rooms"]:   # one wander point left (the director once chose from nothing)
        r["paths"]["points"] = [x for x in r["paths"]["points"] if x["kind"] != "wander" or x["name"] == "pit_n"]
    plan.install(p)
    now = [1000.0]
    casino = Casino(Store(tmp_path / "c.sqlite"), npc_population=0, rng=random.Random(2), clock=lambda: now[0], wall=lambda: now[0])
    from casino_server import roster
    npc = casino.npcs.spawn(casino.store.npcs("punter")[0], now[0])
    for step in range(3):
        npc.plan = ["wander"]
        npc.state = "loitering"
        casino.npcs._next_step(npc, now[0])
    assert npc.target in ("point:classic_pit/pit_n", "") and npc.door == "classic_floor/entrance"
    # entrance -> pit: through the archway, ~2500px at an easy pace
    npc.at = floor.position("point:classic_floor/entrance")
    casino.npcs._walk(npc, "point:classic_pit/pit_n", now[0])
    assert 20 < npc.until - now[0] < 45
    npc.at = floor.position("point:classic_pit/pit_n")
    casino.npcs._walk(npc, "point:classic_pit/pit_s", now[0])
    assert 8 < npc.until - now[0] < 16


def test_a_tables_style_outlives_its_room_leaving_the_floor(client):
    store = client.app.state.casino.store
    table_styles.assign(store, {"tables": {"tcp_1": "grand"}})
    draft = client.get("/api/plan").json()["draft"]
    for r in draft["rooms"]:
        r["placed"] = r["id"] == "classic_pit"
    draft["rooms"].append(plan.lobby())
    draft["spawn"] = "lobby/spawn"
    client.put("/api/plan/draft", json=draft)
    plan.install(client.get("/api/plan").json()["draft"])   # (as a restart would)
    assert "tcp_1" not in floor.TABLES
    table_styles.assign(store, {"tables": {"bj_2": "monte"}})   # saving another table's style...
    assert table_styles.load(store)["tables"] == {"tcp_1": "grand", "bj_2": "monte"}   # ...keeps tcp_1's
