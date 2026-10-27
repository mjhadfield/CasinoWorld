"""Sending each session only the tables near it (Floor.tables_near, Casino.look): their states and events, and for the
rest who sits where (`table_seats`)."""
from casino_server import floor as floor_module, plan
from casino_server.floor import KEEP, VIEW   # (imported before conftest widens it)

from conftest import classic_floor, enter, recv_until


def room(id_, x, w=100):
    return {"id": id_, "x": x, "y": 0, "w": w, "h": 100}


def test_a_room_sees_its_archways_rooms_and_one_door_on():
    # a =arch= b -door- c -door- d, and a lift (NPCs only) through a door from a
    placed = [room("a", 0), room("b", 100), room("c", 200), room("d", 300), {**room("lift", -100), "npc_only": True}]
    ops = {"a": [{"kind": "archway", "to": "b"}, {"kind": "door", "to": "lift"}],
           "b": [{"kind": "archway", "to": "a"}, {"kind": "door", "to": "c"}],
           "c": [{"kind": "door", "to": "b"}, {"kind": "door", "to": "d"}, {"kind": "door", "to": None}],
           "d": [{"kind": "door", "to": "c"}], "lift": [{"kind": "door", "to": "a"}]}
    tables = {f"t_{r}": {"room": r} for r in "abcd"}
    near = plan.near_tables(placed, ops, tables)
    assert near["a"] == near["b"] == {"t_a", "t_b", "t_c"}
    assert near["c"] == {"t_a", "t_b", "t_c", "t_d"}
    assert near["d"] == {"t_c", "t_d"}
    assert near["lift"] == {"t_a", "t_b"}


def test_the_classic_floor_sees_every_table_near_enough(monkeypatch):
    monkeypatch.setattr(floor_module, "VIEW", VIEW)   # (the real one: conftest's sees everything)
    floor = classic_floor()
    assert floor.tables_near("classic_floor") == floor.tables_near("classic_pit") == set(floor.tables)
    assert floor.room_at(700, 1060) == "classic_floor" and floor.room_at(2000, 500) == "classic_pit"
    assert floor.room_at(-5, 0) is None
    assert floor.tables_near(None) == set(floor.tables)   # (off the plan: everything)

    x, y = floor.at["rou_1"]
    gone = (x - VIEW[0] - 100, y)   # just out of range of the roulette table...
    assert "rou_1" in floor.tables_near("classic_floor", (x, y))
    assert "rou_1" not in floor.tables_near("classic_floor", gone)
    assert "rou_1" in floor.tables_near("classic_floor", gone, sent=frozenset({"rou_1"}))   # ...unless it's been sent
    assert "rou_1" not in floor.tables_near("classic_floor", (x - VIEW[0] - KEEP - 1, y), sent=frozenset({"rou_1"}))


def _split(client):
    """Demo with the pit's Blackjack tables out of sight of the classic floor (they're one archway apart there)."""
    casino = client.app.state.resort.casinos["demo"]
    pit = {t for t in casino.floor.tables if t.startswith("bj_")}
    casino.floor.near = {"classic_floor": frozenset(set(casino.floor.tables) - pit),
                         "classic_pit": frozenset(casino.floor.tables)}
    casino.floor.at = {}   # (by room only: no distance)
    return casino, pit


def _entered(ws, name):
    enter(ws, name=name, hello=True)
    states, seats = set(), None
    while seats is None:
        msg = ws.receive_json()
        if msg["type"] == "table_state":
            states.add(msg["table"])
        elif msg["type"] == "table_seats":
            seats = msg["tables"]
    return states, seats


def test_far_tables_send_only_who_sits_there(client):
    casino, pit = _split(client)
    with client.websocket_connect("/ws") as far, client.websocket_connect("/ws") as near:
        states, seats = _entered(far, "Far")
        assert pit.isdisjoint(states) and "tcp_1" in states and set(seats) == pit
        assert seats["bj_1"] == [None] * len(casino.tables["bj_1"].machine.seats)

        _entered(near, "Near")
        near.send_json({"type": "move", "x": 2000, "y": 500, "dir": "down", "anim": "walk"})
        assert recv_until(near, "table_state", where=lambda m: m["table"] == "bj_1")["phase"] == "betting"
        near.send_json({"type": "sit", "table": "bj_1", "seat": 2})
        recv_until(near, "seated")

        sat = recv_until(far, "table_seats")["tables"]["bj_1"]
        assert sat[2]["name"] == "Near" and sat[2]["human"] is True and sat[0] is None
        near.send_json({"type": "stand"})
        recv_until(near, "table_event", "stood")
        assert recv_until(far, "table_seats")["tables"]["bj_1"][2] is None

        # Nothing else of the pit's came the far player's way; walking in, its tables arrive.
        far.send_json({"type": "move", "x": 2000, "y": 500, "dir": "down", "anim": "walk"})
        seen = []
        while (msg := far.receive_json())["type"] != "table_state" or msg["table"] not in pit:
            seen.append(msg)
        assert not [m for m in seen if m["type"] == "table_event" and m["table"] in pit]
        far.send_json({"type": "move", "x": 2010, "y": 500, "dir": "down", "anim": "walk"})   # (same room: no resend)
        far.send_json({"type": "resync"})
        recv_until(far, "resync")
        assert not [m for m in _until_world_snapshot(far) if m["type"] == "table_state"]


def _until_world_snapshot(ws):
    out = []
    while (msg := ws.receive_json())["type"] != "world_snapshot":
        out.append(msg)
    return out


def test_sitting_at_a_far_table_sends_its_neighbours_and_standing_up_tells_you(client):
    casino = client.app.state.resort.casinos["demo"]
    pit = {t for t in casino.floor.tables if t.startswith("bj_")}
    lobby = frozenset(set(casino.floor.tables) - pit)
    casino.floor.near = {"classic_floor": lobby, "classic_pit": frozenset(pit)}   # (each room sees only its own)
    casino.floor.at = {}
    with client.websocket_connect("/ws") as ws:
        states, seats = _entered(ws, "Sitter")
        assert pit.isdisjoint(states)
        ws.send_json({"type": "sit", "table": "bj_1", "seat": 0})   # (from the lobby: not something the game does)
        recv_until(ws, "seated")
        casino.floor.at = {"bj_1": (2000, 500)}   # (where it stands, so its room's tables come in view)
        ws.send_json({"type": "stand"})
        assert recv_until(ws, "table_event", "stood", where=lambda m: m["table"] == "bj_1")["event"]["seat"] == 0
