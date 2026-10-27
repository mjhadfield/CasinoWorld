"""Card tables' limits: each table's main and side bet minimum and maximum, from the floor plan (plan.py), kept by
the table machines (tables/base.py) and by the NPCs (npc.py). The other tests play under conftest's OPEN_LIMITS;
these set real ones."""
import pytest

from casino_server import plan
from casino_server.tables import base
from casino_server.tables.baccarat import BaccaratMachine
from casino_server.tables.baccarat import Timings as BacTimings
from casino_server.tables.base import DEFAULT_LIMITS, TableError
from casino_server.tables.let_it_ride import LetItRideMachine
from casino_server.tables.let_it_ride import Timings as LirTimings
from casino_server.tables.roulette import RouletteMachine
from casino_server.tables.roulette import Timings as RouTimings

from conftest import CLASSIC_PLAN
from test_machine import FakeParticipant, find, kinds, machine
from test_npc import simulate

LIMITS = {"main": (500, 50_000), "side": (100, 5_000)}   # (the real defaults, set on each machine here)


def tcp(limits=LIMITS):
    m = machine()
    m.limits = limits
    return m


# ------------------------------------------------------------------ the floor plan
def test_the_defaults_are_five_to_five_hundred_and_one_to_fifty():
    assert DEFAULT_LIMITS == {"main": (500, 50_000), "side": (100, 5_000)}


def test_the_plan_cleans_a_tables_limits(monkeypatch):
    monkeypatch.setattr(plan, "DEFAULT_LIMITS", DEFAULT_LIMITS)
    assert plan._clean_limits(None, "T") == {"main": [500, 50_000], "side": [100, 5_000]}
    assert plan._clean_limits({"main": [1_000, 100_000]}, "T") == {"main": [1_000, 100_000], "side": [100, 5_000]}
    for bad, says in [({"main": [550, 1_000]}, "whole pounds"), ({"side": [5_000, 100]}, "minimum is more"),
                      ({"main": [100, 2_000_000]}, "out of range"), ({"main": [0, 500]}, "out of range"),
                      ({"main": ["x", 500]}, "isn't a number")]:
        with pytest.raises(plan.PlanError, match=says):
            plan._clean_limits(bad, "T")


def test_card_tables_carry_their_limits_to_the_floor_and_the_clients():
    tables = plan.tables_of(CLASSIC_PLAN)
    card = [t for t, cfg in tables.items() if cfg["game"] in plan.LIMITED_GAMES]
    others = [t for t, cfg in tables.items() if cfg["game"] not in plan.LIMITED_GAMES]
    assert card and others
    assert all("limits" in tables[t] for t in card) and not any("limits" in tables[t] for t in others)
    items = [it for room in plan.world(CLASSIC_PLAN)["rooms"] for it in room["items"] if it.get("game")]
    assert all(("limits" in it) == (it["game"] in plan.LIMITED_GAMES) for it in items)


def test_a_published_change_of_limits_reaches_the_table(client):
    casino = client.app.state.casino
    table_id = next(t for t, cfg in casino.floor.tables.items() if cfg["game"] == "three_card_poker")
    casino.floor.tables[table_id]["limits"] = {"main": [2_500, 10_000], "side": [500, 1_000]}
    casino.broadcast_world(casino.floor)
    assert casino.tables[table_id].machine.limits == {"main": (2_500, 10_000), "side": (500, 1_000)}


# ------------------------------------------------------------------ the table
def test_over_the_maximum_is_refused_at_the_chip():
    m = tcp()
    m.sit(0, FakeParticipant("Ann", balance=1_000_000), 0)
    with pytest.raises(TableError, match="maximum on main bets is £500"):
        m.set_bets(0, {"ante": 50_100}, 0)
    with pytest.raises(TableError, match="maximum on side bets is £50"):
        m.set_bets(0, {"ante": 500, "pair_plus": 5_100}, 0)
    m.set_bets(0, {"ante": 50_000, "pair_plus": 5_000, "jackpot": 100}, 0)   # (the flat £1 Jackpot isn't limited)


def test_under_the_minimum_is_built_up_but_ready_is_refused():
    m = tcp()
    m.sit(0, FakeParticipant("Ann"), 0)
    m.set_bet(0, "ante", 100, 0)
    m.set_bet(0, "ante", 300, 0)   # (a £5 Ante from £1 chips: fine on the way)
    with pytest.raises(TableError, match="minimum on main bets is £5"):
        m.ready(0, 0)
    m.set_bet(0, "ante", 500, 0)
    m.ready(0, 0)


def test_a_short_main_bet_goes_back_and_the_seat_sits_out():
    m = tcp()
    ann, bob = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0), m.sit(2, bob, 0)
    m.set_bets(2, {"ante": 300, "pair_plus": 500}, 0)   # (an NPC doesn't press Ready)
    m.set_bets(0, {"ante": 500}, 0)
    m.ready(0, 0)
    events = m.tick(1)
    short = find(events, "bet_under_min")
    assert short == [{"kind": "bet_under_min", "seat": 2, "spots": ["ante"], "main": True,
                      "text": "Under the £5 table minimum: your bets went back and you sit this hand out."}]
    assert kinds(events).index("bet_under_min") < kinds(events).index("bets_closed")
    assert bob.balance == 100_000 and 2 not in m.round and 0 in m.round


def test_a_short_side_bet_goes_back_and_the_hand_plays():
    m = tcp({"main": (500, 50_000), "side": (500, 5_000)})
    ann, bob = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0), m.sit(2, bob, 0)
    m.set_bets(2, {"ante": 1_000, "pair_plus": 200, "jackpot": 100}, 0)
    m.set_bets(0, {"ante": 500}, 0)
    m.ready(0, 0)
    events = m.tick(1)
    assert find(events, "bet_under_min")[0]["spots"] == ["pair_plus"]
    assert 2 in m.round and bob.balance == 100_000 - 1_100   # (the Ante and the £1 Jackpot)


def test_a_rebet_that_no_longer_fits_is_refused_and_auto_rebet_goes_off():
    m = tcp({"main": (100, 50_000), "side": (100, 5_000)})
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    m.seats[0].last_bets = {"ante": 200, "pair_plus": 0, "prime": 0, "jackpot": 0}
    m.limits = LIMITS
    with pytest.raises(TableError, match="minimum on main bets is £5"):
        m.rebet(0, 0)
    m.seats[0].auto_rebet = True
    events = m._reopen_betting(1)
    assert {"kind": "auto_rebet", "seat": 0, "on": False, "reason": "The table minimum on main bets is £5."} in events


def test_what_counts_as_a_main_bet():
    bac = BaccaratMachine("bac", 6, BacTimings.instant(), None)
    assert [bac.limit_of(s)[0] for s in ("player", "banker", "tie", "player_dragon")] == ["main", "main", "side", "side"]
    lir = LetItRideMachine("lir", 6, LirTimings.instant(), None)
    assert [lir.limit_of(s)[0] for s in ("bet1", "bet2", "ante", "three_card")] == ["main", "main", "main", "side"]
    assert lir.limit_of("bonus") is None and lir.limit_of("jackpot") is None   # (flat bets)
    rou = RouletteMachine("rou", 6, RouTimings.instant(), None)
    assert rou.limit_of("red") is None   # (Roulette keeps its own limits)


def test_a_master_table_hands_its_limits_to_each_game():
    from test_master_table import change, table
    m = table()
    m.limits = {"main": (1_000, 2_000), "side": (100, 500)}
    m.sit(0, FakeParticipant("Ann"), 0)
    m.choose_game(0, "three_card_poker", 0)
    change(m, 0)
    assert m.inner is not None and m.inner.limits == {"main": (1_000, 2_000), "side": (100, 500)}
    m.limits = LIMITS
    assert m.inner.limits == LIMITS


# ------------------------------------------------------------------ the NPCs
def test_npcs_bet_within_the_limits(tmp_path, monkeypatch):
    limits = {"main": (1_000, 2_500), "side": (200, 500)}
    monkeypatch.setattr(plan, "DEFAULT_LIMITS", limits)
    monkeypatch.setattr(base, "DEFAULT_LIMITS", limits)
    seen = {"main": [], "side": []}

    def watch(casino):
        for runner in casino.tables.values():
            m = runner.machine
            if not getattr(m, "LIMITED", False):
                continue
            for s in m.seats:
                for spot, amount in (s.bets or {}).items():
                    lim = m.limit_of(spot)
                    if amount and lim:
                        seen[lim[0]].append(amount)
        return False
    simulate(tmp_path, 900, population=10, until=watch)
    assert seen["main"] and all(1_000 <= a <= 2_500 for a in seen["main"])
    assert all(200 <= a <= 500 for a in seen["side"])
