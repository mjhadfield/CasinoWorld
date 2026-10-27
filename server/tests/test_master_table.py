"""The Master Table (tables/master.py): blank until someone asks for a game, then that game's own machine, changed
between hands with a vote, queued mid-hand, seats renumbered 6<->5, and back to blank once nobody's sitting."""
import copy
import sys

import pytest
from fastapi.testclient import TestClient

from casino_server import plan
from casino_server.app import app
from casino_server.casino import MACHINES
from casino_server.npc import reserved_seats
from casino_server.tables import master
from casino_server.tables.base import TableError
from casino_server.tables.master import MasterMachine, remap

from conftest import CLASSIC_PLAN, demo_plan_dir, enter, recv_until
from test_machine import FakeJackpot, FakeParticipant


def make(game, n):
    cls = MACHINES[game]
    t = sys.modules[cls.__module__].Timings.instant()
    t.betting = t.betting_npc_only = 30.0
    for name in ("decide", "insurance", "turn", "setting"):
        if hasattr(t, name):
            setattr(t, name, 30.0)
    return cls("mt_1", n, t, FakeJackpot())


def table(**kw):
    t = master.Timings(vote=10.0, revert=60.0, hold=0.5)
    return MasterMachine("mt_1", 6, t, FakeJackpot(), make=make, **kw)


def kinds(events):
    return [e["kind"] for e in events]


def change(m, now):
    """Run the change through: the hold, then betting opens."""
    assert m.phase == "changing"
    return m.tick(m.changing_until + 0.01)


# ------------------------------------------------------------------ the blank table
def test_blank_table_seats_people_only_and_asks_them_for_a_game():
    m = table()
    assert m.free_seats() == [] and m.phase == "idle" and m.current == ""
    with pytest.raises(TableError):
        m.sit(0, FakeParticipant("npc", human=False), 0)
    ev = m.sit(2, FakeParticipant("ann"), 0)
    assert kinds(ev)[0] == "seated" and "say" in kinds(ev)
    snap = m.snapshot(2, 0)
    assert snap["master"]["game"] == "" and snap["seats"][2]["name"] == "ann"
    with pytest.raises(TableError):
        m.set_bet(2, "ante", 100, now=0)   # no game yet


def test_choosing_a_game_alone_changes_at_once():
    m, ann = table(anim="sweep", speed=2.0), FakeParticipant("ann")
    m.sit(2, ann, 0)
    ev = m.choose_game(2, "three_card_poker", 1.0)
    ch = next(e for e in ev if e["kind"] == "master_change")
    assert ch["game"] == "three_card_poker" and ch["anim"] == "sweep" and ch["speed"] == 2.0
    assert ch["seconds"] == pytest.approx(master.MORPH["sweep"] / 2 + 0.5)
    assert ch["_remap"] == {"e-ann": 2} and ch["_resnap"]
    assert m.phase == "changing" and m.current == "three_card_poker"
    with pytest.raises(TableError):
        m.set_bet(2, "ante", 100, now=1.0)   # not while it's changing
    ev = change(m, 1.0)
    assert "betting_open" in kinds(ev) and m.phase == "betting"
    assert m.seat_of(ann) == 2
    m.set_bet(2, "ante", 500, now=5.0)
    assert m.seats[2].bets["ante"] == 500


def test_the_same_game_and_unknown_games_are_refused():
    m = table()
    m.sit(0, FakeParticipant("ann"), 0)
    with pytest.raises(TableError):
        m.choose_game(0, "roulette", 0)
    m.choose_game(0, "baccarat", 0)
    change(m, 0)
    with pytest.raises(TableError):
        m.choose_game(0, "baccarat", 5)


# ------------------------------------------------------------------ six seats and five
def test_remap_drops_the_empty_seat_that_moves_people_least_and_keeps_the_order():
    occupied = [True, False, True, True, False, True]
    mapping = remap(occupied, 5)
    assert len(mapping) == 5 and -1 not in mapping
    assert [j for j in mapping if occupied[j]] == [0, 2, 3, 5]   # same order
    back = remap([True, True, True, True, True], 6)
    assert back.count(-1) == 1 and [j for j in back if j >= 0] == [0, 1, 2, 3, 4]
    with pytest.raises(TableError):
        remap([True] * 6, 5)


def test_changing_to_a_five_seat_game_renumbers_the_seats():
    m = table()
    people = {s: FakeParticipant(f"p{s}") for s in (0, 2, 3, 5)}
    for s, p in people.items():
        m.sit(s, p, 0)
    ev = m.choose_game(0, "let_it_ride", 0)
    assert ev[0]["kind"] == "master_vote"   # (the others are asked first)
    for s in (2, 3, 5):
        ev = m.game_vote(s, True, 1)
    ch = next(e for e in ev if e["kind"] == "master_change")
    assert ch["seats"] == 5 and len(m.seats) == 5
    order = [s.participant.name for s in m.seats if s.participant]
    assert order == ["p0", "p2", "p3", "p5"]
    assert ch["_remap"] == {p.entity_id: m.seat_of(p) for p in people.values()}
    change(m, 1)
    m.choose_game(m.seat_of(people[0]), "blackjack", 50)
    for p in (people[2], people[3], people[5]):
        m.game_vote(m.seat_of(p), True, 51)
    assert len(m.seats) == 6 and [s.participant.name for s in m.seats if s.participant] == order


def test_a_five_seat_game_needs_a_free_seat():
    m = table()
    for s in range(6):
        m.sit(s, FakeParticipant(f"p{s}"), 0)
    with pytest.raises(TableError, match="seats 5"):
        m.choose_game(0, "high_card_flush", 0)


# ------------------------------------------------------------------ asking the others
def test_a_no_keeps_the_game_and_a_yes_from_everyone_changes_it():
    m, a, b = table(), FakeParticipant("a"), FakeParticipant("b")
    m.sit(0, a, 0)
    m.sit(1, b, 0)
    ev = m.choose_game(0, "blackjack", 0)
    assert ev[0]["kind"] == "master_vote" and ev[0]["voters"] == [1] and m.current == ""   # b hasn't answered
    ev = m.game_vote(1, False, 1)
    assert ev[0] == {"kind": "master_vote_end", "ok": False, "game": "blackjack", "seat": 1, "name": "b"}
    assert m.current == "" and m.vote is None
    m.choose_game(1, "blackjack", 2)
    ev = m.game_vote(0, True, 3)
    assert kinds(ev)[:3] == ["master_vote_cast", "master_vote_end", "master_change"] and m.current == "blackjack"


def test_no_answer_is_a_yes():
    m = table()
    m.sit(0, FakeParticipant("a"), 0)
    m.sit(1, FakeParticipant("b"), 0)
    m.choose_game(0, "baccarat", 0)
    assert m.next_deadline == pytest.approx(10.0)
    ev = m.tick(10.0)
    assert {"kind": "master_vote_end", "ok": True, "game": "baccarat"} in ev and m.current == "baccarat"


def test_npcs_dont_vote_and_those_who_dont_like_the_game_leave():
    stays = FakeParticipant("stays", human=False)
    goes = FakeParticipant("goes", human=False)
    m = table(leavers=lambda ps, game: [p for p in ps if p is not stays])
    ann = FakeParticipant("ann")
    m.sit(0, ann, 0)
    m.choose_game(0, "three_card_poker", 0)
    change(m, 0)
    m.sit(1, stays, 5)
    m.sit(2, goes, 5)
    ev = m.choose_game(0, "blackjack", 6)   # no vote: NPCs don't get one
    assert {"kind": "stood", "seat": 2, "entity": "e-goes", "reason": "game_change"} in ev
    assert m.seat_of(stays) is not None and m.seat_of(goes) is None and m.current == "blackjack"


# ------------------------------------------------------------------ between hands only
def test_asked_mid_hand_it_waits_for_the_hand_to_end():
    m, ann = table(), FakeParticipant("ann")
    m.sit(0, ann, 0)
    m.choose_game(0, "baccarat", 0)
    change(m, 0)
    m.inner.timings = sys.modules[type(m.inner).__module__].Timings()   # (real timings: the coup takes a while)
    m.set_bet(0, "banker", 500, now=1)
    m.ready(0, now=1)
    m.tick(m.next_deadline)   # betting closes; the coup's being dealt
    assert m.inner.phase != "betting"
    now = m.next_deadline - 0.1
    ev = m.choose_game(0, "blackjack", now)
    assert ev[0] == {"kind": "master_queued", "game": "blackjack"} and m.current == "baccarat"
    for _ in range(200):
        if m.current == "blackjack":
            break
        now = max(now + 0.01, m.next_deadline or now + 1)
        m.tick(now)
    assert m.current == "blackjack" and m.phase == "changing"


def test_cancelling_a_queued_change():
    m, ann = table(), FakeParticipant("ann")
    m.sit(0, ann, 0)
    m.choose_game(0, "baccarat", 0)
    change(m, 0)
    m.inner.timings = sys.modules[type(m.inner).__module__].Timings()   # (real timings: the coup takes a while)
    m.set_bet(0, "banker", 500, now=1)
    m.ready(0, now=1)
    m.tick(m.next_deadline)
    m.choose_game(0, "blackjack", m.next_deadline - 0.1)
    ev = m.cancel_queued(0, m.next_deadline - 0.1)
    assert ev[0] == {"kind": "master_queued", "game": None} and m.queued is None


def test_bets_on_the_felt_go_back_when_it_changes():
    m, ann = table(), FakeParticipant("ann")
    m.sit(0, ann, 0)
    m.choose_game(0, "three_card_poker", 0)
    change(m, 0)
    m.set_bet(0, "ante", 500, now=1)
    ev = m.choose_game(0, "blackjack", 2)
    assert {"kind": "bet_changed", "seat": 0, "bets": {"ante": 0, "pair_plus": 0, "prime": 0, "jackpot": 0}} in ev
    assert ann.balance == 100_000   # (nothing's taken until betting closes)


# ------------------------------------------------------------------ back to blank
def test_with_nobody_sitting_it_goes_back_to_blank_and_the_npcs_leave():
    m, ann, npc = table(), FakeParticipant("ann"), FakeParticipant("npc", human=False)
    m.sit(0, ann, 0)
    m.choose_game(0, "three_card_poker", 0)
    change(m, 0)
    m.sit(3, npc, 2)
    ev = m.stand(0, 10)
    assert {"kind": "master_revert", "seconds": 60.0} in ev
    m.sit(0, ann, 20)          # sitting again stops it
    assert m.revert_at is None
    m.stand(0, 30)
    ev = m.tick(90)
    assert {"kind": "stood", "seat": 3, "entity": "e-npc", "reason": "closing"} in ev
    assert any(e["kind"] == "master_change" and e["game"] == "" for e in ev)
    change(m, 90)
    assert m.current == "" and m.phase == "idle" and len(m.seats) == 6


# ------------------------------------------------------------------ the floor plan
def test_the_plan_keeps_its_animation_and_speed_and_both_seatings():
    p = copy.deepcopy(CLASSIC_PLAN)
    room = next(r for r in p["rooms"] if r["placed"])
    room["items"].append({"asset": "table:master_table", "x": 300, "y": 300, "props": {"anim": "dust", "speed": 0.5}})
    room["items"].append({"asset": "table:master_table", "x": 300, "y": 600, "props": {"anim": "bogus", "speed": 3}})
    clean = plan.clean(p, {"rev": 0, "next": {}, "rooms": []})
    items = [i for r in clean["rooms"] for i in r["items"] if i["asset"] == "table:master_table"]
    assert [i["props"]["anim"] for i in items] == ["dust", "cloth"]
    assert [i["props"]["speed"] for i in items] == [0.5, 1.0]
    assert all(i["id"].startswith("mt_") for i in items)
    tables = plan.tables_of(clean)
    cfg = tables[items[0]["id"]]
    assert cfg["game"] == "master_table" and len(cfg["stands"]["6"]) == 6 and len(cfg["stands"]["5"]) == 5


# ------------------------------------------------------------------ over the wire
@pytest.fixture
def master_client(tmp_path, monkeypatch):
    p = copy.deepcopy(CLASSIC_PLAN)
    room = next(r for r in p["rooms"] if r["placed"])
    room["items"].append({"id": "mt_1", "asset": "table:master_table", "x": 950, "y": 1040, "props": {"anim": "cloth", "speed": 2.0}})
    p["next"] = {**p.get("next", {}), "mt": 2}
    for name in ("live.json", "draft.json"):
        plan._write(demo_plan_dir(tmp_path) / name, p)
    monkeypatch.setenv("CASINO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CASINO_DESIGNS_DIR", str(tmp_path / "slot_designs"))
    monkeypatch.setenv("CASINO_SLOT_BUILDS_DIR", str(tmp_path / "slot_builds"))
    monkeypatch.setenv("CASINO_NPCS", "0")
    with TestClient(app) as c:
        m = c.app.state.resort.casinos["demo"].tables["mt_1"].machine
        m.timings = master.Timings(vote=10.0, revert=60.0, hold=0.0)
        m.make = lambda g, n, _m=m: _fast(c.app.state.resort.casinos["demo"]._make_machine("mt_1", g, n))
        yield c


def _fast(machine):
    t = type(machine.timings).instant()
    t.betting = t.betting_npc_only = 30.0
    machine.timings = t
    return machine


def test_choosing_over_the_websocket(master_client):
    with master_client.websocket_connect("/ws") as ws:
        enter(ws)
        ws.send_json({"type": "sit", "table": "mt_1", "seat": 3})
        seated = recv_until(ws, "seated")
        state = recv_until(ws, "table_state", where=lambda m: m["table"] == "mt_1")
        assert state["master"]["game"] == "" and seated["seat"] == 3
        ws.send_json({"type": "choose_game", "game": "let_it_ride"})
        ev = recv_until(ws, "table_event", "master_change")["event"]
        assert ev["game"] == "let_it_ride" and ev["seats"] == 5 and "_remap" not in ev
        state = recv_until(ws, "table_state", where=lambda m: m["table"] == "mt_1")
        assert state["game"] == "let_it_ride" and state["master"]["game"] == "let_it_ride"
        mine = state["my_seat"]
        assert state["seats"][mine]["name"] and len(state["seats"]) == 5
        fl = master_client.app.state.resort.casinos["demo"].floor
        assert fl.seats["mt_1"] == plan.tables_of(fl.plan)["mt_1"]["stands"]["5"]
        ws.send_json({"type": "choose_game", "game": "craps"})
        assert "can't set" in recv_until(ws, "error")["message"]


# ------------------------------------------------------------------ with NPCs
def npc_master(tmp_path):
    """A floor with just a Master Table and twelve NPCs on a fake clock, me sitting at it playing Three Card Poker.
    Returns (casino, runner, machine, me, run(seconds))."""
    import random

    from casino_server.casino import Casino
    from casino_server.store import Store
    p = copy.deepcopy(CLASSIC_PLAN)
    room = next(r for r in p["rooms"] if r["placed"])
    room["items"] = [{"id": "mt_1", "asset": "table:master_table", "x": 950, "y": 1040, "props": {}}]   # (its only table)
    for other in p["rooms"]:
        if other is not room:
            other["placed"] = False
    fl = plan.install(plan.clean(p, {"rev": 0, "next": {}, "rooms": []}))
    assert list(fl.tables) == ["mt_1"]
    now = [1_000_000.0]
    store = Store(tmp_path / "npc.sqlite")
    casino = Casino(store, fl, npc_population=12, rng=random.Random(5), clock=lambda: now[0], wall=lambda: now[0])
    runner = casino.tables["mt_1"]
    m = runner.machine
    m.timings = master.Timings(vote=10.0, revert=600.0, hold=0.5)
    me = FakeParticipant("me")
    runner.act("sit", 2, me)
    runner.act("choose_game", 2, "three_card_poker")

    def run(seconds: float, each=None):
        for _ in range(int(seconds * 4)):
            now[0] += 0.25
            casino.npcs.tick(now[0])
            for r in casino.tables.values():
                r.publish(r.machine.tick(now[0]))
            mine = m.seat_of(me)
            if mine is not None:
                m.seats[mine].sat_out = 0   # (I watch: the table doesn't stand me up for sitting out)
            if each:
                each()

    return casino, runner, m, me, run


def seated_npcs(casino):
    return [n for n in casino.npcs.npcs.values() if n.table == "mt_1" and n.state == "seated"]


def test_about_one_npc_gets_up_at_a_change_and_never_more_than_two(tmp_path):
    from types import SimpleNamespace

    from casino_server.npc import LEAVE_CHANCE

    casino, *_ = npc_master(tmp_path)

    def npc(name, favourites=(), counter=False):
        prof = SimpleNamespace(favourite_games=list(favourites), card_counter=counter)
        return SimpleNamespace(name=name, npc=SimpleNamespace(prof=prof))

    five = [npc(f"n{i}") for i in range(5)]
    counts = [len(casino.npcs.leavers(five, "baccarat")) for _ in range(4000)]
    assert max(counts) == 2 and min(counts) == 0
    assert 0.9 < sum(counts) / len(counts) < 1.1, LEAVE_CHANCE
    fan, counter = npc("fan", ["baccarat"]), npc("counter", counter=True)
    assert all(fan not in casino.npcs.leavers([fan, counter], "baccarat") for _ in range(200))
    assert casino.npcs.leavers([counter], "baccarat") == [counter]
    assert casino.npcs.leavers([counter], "blackjack") == []


def test_npcs_keep_their_seats_through_six_to_five_and_back(tmp_path):
    """NPCs playing at a Master Table on a fake clock while a person keeps changing its game between six seats
    and five: every NPC that thinks it's sitting there is in the seat it thinks, and none is lost."""
    casino, runner, m, me, run = npc_master(tmp_path)
    games = ["let_it_ride", "blackjack", "high_card_flush", "baccarat"]
    changes, npcs_seen, step, due = 0, set(), [0], [False]

    def check():
        nonlocal changes
        step[0] += 1
        for n in seated_npcs(casino):
            assert m.seats[n.seat].participant is n.participant, (step[0], n.name, n.seat)
            npcs_seen.add(n.entity_id)
        due[0] |= step[0] % 400 == 0   # (a change every 100s, at the next betting phase)
        if due[0] and m.phase == "betting" and m.vote is None:
            due[0] = False
            game = games[changes % len(games)]
            try:
                runner.act("choose_game", m.seat_of(me), game)
                changes += 1
            except TableError:
                pass   # (every seat taken: no five-seat game for now)

    run(2000, check)
    assert changes >= 6 and npcs_seen and m.seat_of(me) is not None


def test_npcs_who_stay_for_the_new_game_play_it(tmp_path):
    """An NPC still sitting once the game has changed bets in the new game (not the old game's bets, refused)."""
    casino, runner, m, me, run = npc_master(tmp_path)
    run(300)
    played = {}
    for game in ("blackjack", "baccarat", "let_it_ride", "three_card_poker"):
        while not (m.phase == "betting" and m.vote is None):
            run(0.25)
        stayers = {n.entity_id for n in seated_npcs(casino)}
        runner.act("choose_game", m.seat_of(me), game)
        reserved = reserved_seats(game, len(m.seats))   # (one left in a seat kept for players moves first)
        stayers &= {n.entity_id for n in seated_npcs(casino) if n.seat not in reserved}
        rounds = {n.entity_id: n.games.get(game, 0) for n in seated_npcs(casino)}
        run(90)   # (a round with four NPCs at the table)
        for n in seated_npcs(casino):
            if n.entity_id in stayers:
                played[game] = played.get(game, 0) + 1
                assert n.games.get(game, 0) > rounds[n.entity_id], (game, n.name)
    assert len(played) >= 2   # (about one leaves at a change: most stay for most games)
