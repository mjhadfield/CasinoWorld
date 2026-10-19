"""The Ultimate Texas Hold'em and Let It Ride table machines, driven with explicit times."""
import pytest

from casino_server.engines.cards import Card
from casino_server.tables.base import TableError
from casino_server.tables.let_it_ride import LetItRideMachine
from casino_server.tables.let_it_ride import Timings as LirTimings
from casino_server.tables.ultimate_texas_holdem import Timings as UthTimings
from casino_server.tables.ultimate_texas_holdem import UltimateTexasHoldemMachine

from test_machine import FakeParticipant
from test_pai_gow_machine import PoolJackpot


class Rigged:
    """Deals these card lists in order, one list per deal() call."""
    def __init__(self, *packets):
        self.queue = [[Card.from_code(c) for c in p] for p in packets]

    def deal(self, n):
        return self.queue.pop(0)


def kinds(events):
    return [e["kind"] for e in events]


def uth_machine(*packets):
    t = UthTimings.instant()
    t.decide = 100.0
    return UltimateTexasHoldemMachine("uth_test", 6, t, PoolJackpot(), deck_factory=lambda: Rigged(*packets))


def lir_machine(*packets):
    t = LirTimings.instant()
    t.decide = 100.0
    return LetItRideMachine("lir_test", 6, t, PoolJackpot(), deck_factory=lambda: Rigged(*packets))


def start(m, players, bets):
    events = []
    for seat, (p, b) in enumerate(zip(players, bets)):
        m.sit(seat, p, 0)
        m.set_bets(seat, b, 0)
        events += m.ready(seat, 0)
    return events + m.tick(0)


# ---------------------------------------------------------------------- Ultimate Texas Hold'em
def test_holdem_blind_follows_the_ante_and_a_4x_bet_ends_your_decisions():
    mike, nora = FakeParticipant("Mike"), FakeParticipant("Nora")
    # Mike: A-A. Nora: 7-2. Dealer: K-Q. Board: A-K-5-9-2 (Mike trips, dealer a pair of Kings).
    m = uth_machine(["Ah", "Ad"], ["7c", "2d"], ["Kc", "Qd"], ["As", "Ks", "5h", "9c", "2h"])
    m.sit(0, mike, 0)
    events = m.set_bet(0, "blind", 500, 0)  # either spot sets both
    assert events[0]["bets"]["ante"] == 500 and events[0]["bets"]["blind"] == 500
    m.set_bet(0, "trips", 100, 0)
    m.sit(1, nora, 0)
    m.set_bets(1, {"ante": 100}, 0)
    m.ready(0, 0)
    m.ready(1, 0)
    events = m.tick(0)
    assert m.phase == "deciding" and m.stage == 0
    with pytest.raises(TableError):
        m.play_action(0, "bet2", 1)
    m.play_action(0, "bet4", 1)
    events = m.play_action(1, "check", 1) + m.tick(1)
    assert next(e for e in events if e["kind"] == "community")["cards"] == ["As", "Ks", "5h"]
    assert next(e for e in events if e["kind"] == "decisions_open")["seats"] == [1]  # Mike's done
    m.play_action(1, "check", 2)
    events = m.tick(2)
    assert next(e for e in events if e["kind"] == "community")["cards"] == ["9c", "2h"]
    events = m.play_action(1, "bet1", 3) + m.tick(3)
    reveal = next(e for e in events if e["kind"] == "dealer_reveal")
    assert reveal["hand"] == "Pair of Kings" and reveal["qualified"]
    settles = {e["seat"]: e for e in events if e["kind"] == "settle_seat"}
    assert settles[0]["outcome"] == "win" and settles[0]["hand"] == "Three of a Kind"
    # Ante 1:1, Play (£20) 1:1, Blind pushes (trips is below a Straight), Trips 3:1.
    assert mike.balance == 100_000 - 1_100 - 2_000 + 1_000 + 500 + 4_000 + 400
    assert settles[1]["outcome"] == "lose" and settles[1]["hand"] == "Pair of 2s"  # Nora: 2s lose to Kings
    assert nora.balance == 100_000 - 300  # Ante, Blind and the 1x Play
    assert "round_end" in kinds(events)


def test_holdem_out_of_time_checks_then_folds_and_a_fold_loses_everything():
    away = FakeParticipant("Away")
    m = uth_machine(["7c", "2d"], ["Kc", "Qd"], ["As", "Ks", "5h", "9c", "3h"])
    start(m, [away], [{"ante": 100, "trips": 100, "jackpot": 100}])
    events = m.tick(200) + m.tick(400) + m.tick(600)
    actions = [(e["stage"], e["action"], e.get("reason")) for e in events if e["kind"] == "uth_action"]
    assert actions == [(0, "check", "timeout"), (1, "check", "timeout"), (2, "fold", "timeout")]
    sweep = next(e for e in events if e["kind"] == "fold_sweep")
    assert {s["spot"] for s in sweep["seats"][0]["steps"]} == {"ante", "blind", "trips", "jackpot"}
    assert "dealer_reveal" not in kinds(events) and away.balance == 100_000 - 400


def test_holdem_others_never_see_your_cards_or_the_dealers():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = uth_machine(["Ah", "Kh"], ["2c", "3d"], ["Qc", "Qd"], ["4s", "5s", "6s", "7d", "8d"])
    start(m, [a, b], [{"ante": 100}, {"ante": 100}])
    snap = m.snapshot(1, 0)
    assert snap["seats"][0]["cards"] == ["??", "??"] and snap["seats"][1]["cards"] == ["2c", "3d"]
    assert snap["dealer"]["cards"] == ["??", "??"] and snap["community"] == ["??"] * 5


# ---------------------------------------------------------------------- Let It Ride
def test_let_it_ride_three_equal_bets_and_pulling_back():
    mike, nora = FakeParticipant("Mike"), FakeParticipant("Nora")
    # Mike: 10-10-4, rides both; Nora: 2-7-9, pulls both back. Community: 10, K -> Mike trips.
    m = lir_machine(["10h", "10d", "4c"], ["2c", "7d", "9s"], ["10s", "Kd"])
    m.sit(0, mike, 0)
    events = m.set_bet(0, "bet2", 500, 0)  # any of 1, 2, $ sets all three
    assert {k: v for k, v in events[0]["bets"].items() if k in ("bet1", "bet2", "ante")} == \
        {"bet1": 500, "bet2": 500, "ante": 500}
    m.set_bet(0, "three_card", 100, 0)
    m.sit(1, nora, 0)
    m.set_bets(1, {"ante": 100}, 0)
    m.ready(0, 0)
    m.ready(1, 0)
    m.tick(0)
    m.play_action(0, "ride", 1)
    events = m.play_action(1, "pull", 1) + m.tick(1)
    pull = next(e for e in events if e["kind"] == "lir_decision" and e["seat"] == 1)
    assert pull["spot"] == "bet1" and pull["amount"] == 100 and nora.balance == 100_000 - 300 + 100
    assert next(e for e in events if e["kind"] == "community")["cards"] == ["10s"]
    m.play_action(0, "ride", 2)
    m.play_action(1, "pull", 2)
    events = m.tick(2)
    settles = {e["seat"]: e for e in events if e["kind"] == "settle_seat"}
    assert settles[0]["hand"] == "Three of a Kind" and settles[0]["multiplier"] == 3
    assert settles[0]["three_card"] == "Pair"
    assert mike.balance == 100_000 - 1_600 + 3 * 2_000 + 200
    assert settles[1]["outcome"] == "lose" and nora.balance == 100_000 - 100  # only the $ was left, and lost


def test_let_it_ride_out_of_time_pulls_back():
    away = FakeParticipant("Away")
    m = lir_machine(["2c", "7d", "9s"], ["3h", "Kd"])
    start(m, [away], [{"ante": 100}])
    events = m.tick(200) + m.tick(400)
    pulls = [e for e in events if e["kind"] == "lir_decision"]
    assert [(e["spot"], e["ride"], e["reason"]) for e in pulls] == [("bet1", False, "timeout"), ("bet2", False, "timeout")]
    assert away.balance == 100_000 - 100
