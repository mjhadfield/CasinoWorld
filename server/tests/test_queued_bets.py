"""Sitting down mid-hand: bets go down at once, queued for the next hand."""
import pytest

from casino_server.tables.base import TableError
from casino_server.tables.baccarat import BaccaratMachine
from casino_server.tables.baccarat import Timings as BacTimings
from casino_server.tables.roulette import RouletteMachine
from casino_server.tables.roulette import Timings as RouTimings

from test_machine import FakeParticipant
from test_roulette import Fixed


def nonzero(bets: dict) -> dict:
    return {k: v for k, v in bets.items() if v}


def finish(m, now: float) -> list:
    """Run the clock until betting opens again."""
    events = []
    for k in range(20):
        events += m.tick(now + k * 10)
        if m.phase == "betting":
            break
    return events


def baccarat_mid_hand():
    """A Baccarat table with Nora in a coup that's still being dealt."""
    t = BacTimings.instant()
    t.first_card = 100.0  # the coup stays in progress until we say
    t.betting = t.betting_npc_only = 500.0
    m = BaccaratMachine("bac_test", 6, t, None)
    nora = FakeParticipant("Nora")
    m.sit(0, nora, 0)
    m.set_bets(0, {"banker": 1_000}, 0)
    m.ready(0, 0)
    m.tick(0)
    assert m.phase == "dealing" and m._in_round(0)
    return m, nora


def test_a_newcomer_bets_at_once_for_the_next_hand():
    m, nora = baccarat_mid_hand()
    mike = FakeParticipant("Mike")
    m.sit(1, mike, 1.0)
    ev = m.set_bet(1, "player", 500, 1.0)
    assert len(ev) == 1 and ev[0]["kind"] == "bet_changed" and ev[0]["queued"] is True
    assert nonzero(ev[0]["bets"]) == {"player": 500}
    m.set_bet(1, "player", 1_500, 1.5)              # chips add up (the casino sends relative adds)
    m.set_bet(1, "tie", 100, 1.6)
    assert m.working_bets(1)["player"] == 1_500
    assert mike.balance == 100_000                    # nothing's taken yet
    assert nonzero(m.snapshot(1, 2.0)["seats"][1]["queued"]) == {"player": 1_500, "tie": 100}
    assert 1 not in m.round                           # and they're not in this coup
    events = finish(m, 1_000.0)                       # the coup plays out; betting opens
    kinds = [e["kind"] for e in events]
    opened = kinds.index("betting_open")
    queued = next(e for e in events[opened:] if e["kind"] == "bet_changed" and e["seat"] == 1)
    assert nonzero(queued["bets"]) == {"player": 1_500, "tie": 100} and "queued" not in queued
    assert "betting_timer" in kinds[opened:]          # the countdown starts, as for any first bet
    assert m.phase == "betting" and m.seats[1].queued is None
    assert m.seats[1].bets["player"] == 1_500


def test_a_player_in_the_hand_still_waits():
    m, _ = baccarat_mid_hand()
    with pytest.raises(TableError, match="closed"):
        m.set_bet(0, "banker", 500, 1.0)


def test_queued_bets_that_cant_be_covered_are_dropped_with_a_reason():
    m, _ = baccarat_mid_hand()
    mike = FakeParticipant("Mike", balance=2_000)
    m.sit(1, mike, 1.0)
    m.set_bet(1, "player", 2_000, 1.0)
    mike._balance = 500                               # spent elsewhere meanwhile
    events = finish(m, 1_000.0)
    dropped = next(e for e in events if e["kind"] == "queued_dropped")
    assert dropped["seat"] == 1 and "balance" in dropped["reason"]
    assert m.seats[1].bets["player"] == 0


def test_clearing_and_rebet_work_on_queued_bets_and_standing_drops_them():
    m, _ = baccarat_mid_hand()
    mike = FakeParticipant("Mike")
    m.sit(1, mike, 1.0)
    m.set_bet(1, "player", 500, 1.0)
    m.clear_bets(1, 1.1)
    assert m.seats[1].queued is None
    m.set_bet(1, "banker", 500, 1.2)
    m.stand(1, 1.3)
    m.sit(1, FakeParticipant("Ray"), 1.4)
    assert m.seats[1].queued is None


def test_roulette_is_the_exception_late_bets_while_spinning_then_wait_for_the_next_spin():
    t = RouTimings.instant()
    t.spin_open, t.ball_track, t.result = 4.0, 7.6, 1.0
    t.betting = t.betting_npc_only = 500.0
    m = RouletteMachine("rou_test", 6, t, rng=Fixed(*([0] * 12 + [17, 5])))
    nora, mike = FakeParticipant("Nora"), FakeParticipant("Mike")
    m.sit(0, nora, 0)
    m.set_bets(0, {"n17": 100}, 0)
    m.ready(0, 0)
    m.tick(0)
    m.sit(1, mike, 1.0)
    assert "queued" not in m.set_bet(1, "red", 500, 1.0)[0]   # spinning: a late bet, for this spin
    m.tick(4.0)                                                 # no more bets
    ray = FakeParticipant("Ray")
    m.sit(2, ray, 5.0)
    with pytest.raises(TableError, match="closed"):            # no queueing at the wheel
        m.set_bet(2, "n5", 100, 5.0)
    finish(m, 1_000.0)
    assert m.phase == "betting"
    m.set_bet(2, "n5", 100, 1_100.0)                            # the next spin's betting is open
    assert m.seats[2].bets["n5"] == 100
