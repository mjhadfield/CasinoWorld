"""The Mississippi Stud table machine, driven directly with explicit times -- no sleeping.

Rigged decks give each seat's two cards in seat order, then the three community cards.
"""
import pytest

from casino_server.engines.cards import Card
from casino_server.jackpot import JACKPOT_FLOOR
from casino_server.tables.base import TableError
from casino_server.tables.mississippi_stud import MississippiStudMachine, Timings

from test_machine import FakeParticipant
from test_pai_gow_machine import PoolJackpot


class Rigged:
    def __init__(self, hands, community):
        self.queue = [[Card.from_code(c) for c in h] for h in hands] + [[Card.from_code(c) for c in community]]

    def deal(self, n):
        return self.queue.pop(0)


def machine(hands, community, jackpot=None):
    t = Timings.instant()
    t.decide = 100.0
    return MississippiStudMachine("ms_test", 6, t, jackpot or PoolJackpot(), deck_factory=lambda: Rigged(hands, community))


def kinds(events):
    return [e["kind"] for e in events]


def start(m, *players, bets):
    events = []
    for seat, (p, b) in enumerate(zip(players, bets)):
        m.sit(seat, p, 0)
        m.set_bets(seat, b, 0)
        events += m.ready(seat, 0)
    return events + m.tick(0)


def test_a_full_round_every_street_pays_the_same_multiplier():
    mike, npc = FakeParticipant("Mike"), FakeParticipant("Nora", human=False)
    m = machine([["Jh", "Jd"], ["2c", "7d"]], ["Js", "4c", "9h"])
    events = start(m, mike, npc, bets=[{"ante": 500, "bonus": 100}, {"ante": 500}])
    assert m.phase == "deciding" and m.street == 0
    dealt = next(e for e in events if e["kind"] == "dealt")
    assert dealt["_private"][0]["cards"] == ["Jh", "Jd"] and dealt["_private"][0]["hand"] == "Pair of Jacks"
    with pytest.raises(TableError):
        m.play_action(0, "bet4", 1)
    m.play_action(0, "bet3", 1)
    events = m.play_action(1, "fold", 1) + m.tick(1)
    sweep = next(e for e in events if e["kind"] == "fold_sweep")
    assert sweep["seats"] == [{"seat": 1, "steps": [{"spot": "ante", "amount": 500}]}]
    assert next(e for e in events if e["kind"] == "community")["cards"] == ["Js"]
    assert m.street == 1 and m.phase == "deciding"  # 4th Street: only Mike is still in
    assert next(e for e in events if e["kind"] == "decisions_open")["seats"] == [0]
    m.play_action(0, "bet2", 2)
    events = m.tick(2)
    m.play_action(0, "bet1", 3)
    events = m.tick(3)
    settle = next(e for e in events if e["kind"] == "settle_seat")
    # Trip Jacks: 3 to 1 on Ante £5 + streets £15, £10, £5. The Bonus (J-4-9) loses.
    assert settle["hand"] == "Three of a Kind" and settle["multiplier"] == 3
    assert {s["spot"]: s.get("payout") for s in settle["steps"]} == \
        {"bonus": None, "ante": 1_500, "third": 4_500, "fourth": 3_000, "fifth": 1_500}
    assert mike.balance == 100_000 - 600 - 3_000 + 3_500 * 4
    assert npc.balance == 100_000 - 500 and "round_end" in kinds(events)


def test_a_fold_keeps_its_bonus_in_action_but_loses_the_jackpot():
    mike = FakeParticipant("Mike")
    m = machine([["2c", "7d"]], ["Qs", "Qh", "Qd"])
    start(m, mike, bets=[{"ante": 500, "bonus": 100, "jackpot": 100}])
    events = m.play_action(0, "fold", 1) + m.tick(1)
    community = [e for e in events if e["kind"] == "community"]
    assert [c for e in community for c in e["cards"]] == ["Qs", "Qh", "Qd"]  # all turned for the Bonus
    sweep = next(e for e in events if e["kind"] == "fold_sweep")
    assert {s["spot"] for s in sweep["seats"][0]["steps"]} == {"ante", "jackpot"}
    bonus = next(e for e in events if e["kind"] == "bonus_settle")  # every folded Bonus at once
    assert bonus["bonus_hand"] == "Three of a Kind" and "settle_seat" not in kinds(events)
    assert bonus["seats"] == [{"seat": 0, "steps": [{"spot": "bonus", "action": "pay", "amount": 100, "payout": 3_000}],
                               "total_returned": 3_100}]
    assert mike.balance == 100_000 - 700 + 3_100


def test_everyone_folding_with_no_bonus_just_ends_the_hand():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = machine([["2c", "7d"], ["3h", "8s"]], ["Qs", "Qh", "Qd"])
    start(m, a, b, bets=[{"ante": 100}, {"ante": 100}])
    m.play_action(0, "fold", 1)
    events = m.play_action(1, "fold", 1) + m.tick(1)
    assert "community" not in kinds(events)  # nothing riding on the cards: they stay face down
    assert "bonus_settle" not in kinds(events) and "settle_seat" not in kinds(events) and "round_end" in kinds(events)


def test_out_of_time_folds_and_a_royal_takes_the_whole_jackpot():
    mike, gone = FakeParticipant("Mike"), FakeParticipant("Away")
    pot = PoolJackpot(800_000)
    m = machine([["As", "Ks"], ["2c", "3d"]], ["Qs", "Js", "10s"], jackpot=pot)
    start(m, mike, gone, bets=[{"ante": 100, "jackpot": 100}, {"ante": 100}])
    for street in range(3):
        m.play_action(0, "bet1", street + 1)
        events = m.tick(street + 1) if street else m.tick(200)  # 3rd Street: Away runs out of time
        if street == 0:
            assert {"kind": "street_bet", "seat": 1, "street": 0, "times": 0, "reason": "timeout"} in events
    won = next(e for e in events if e["kind"] == "jackpot_won")
    assert won["amount"] == 800_000 and pot.amount == JACKPOT_FLOOR  # the whole pool, reset to the floor
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert settle["hand"] == "Royal Flush" and settle["multiplier"] == 500
    assert mike.balance == 100_000 - 200 - 300 + 400 * 501 + 800_000


def test_others_never_see_your_cards_or_the_unturned_community_cards():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = machine([["Ah", "Kh"], ["2c", "3d"]], ["4s", "5s", "6s"])
    start(m, a, b, bets=[{"ante": 100}, {"ante": 100}])
    snap = m.snapshot(1, 0)
    assert snap["seats"][0]["cards"] == ["??", "??"] and snap["seats"][1]["cards"] == ["2c", "3d"]
    assert snap["community"] == ["??", "??", "??"]
    m.play_action(0, "bet1", 1)
    m.play_action(1, "bet1", 1)
    m.tick(1)
    assert m.snapshot(None, 1)["community"] == ["4s", "??", "??"]


def test_you_need_ten_antes_to_sit_a_hand():
    poor = FakeParticipant("Poor", balance=900)
    m = machine([], [])
    m.sit(0, poor, 0)
    with pytest.raises(TableError, match="ten times"):
        m.set_bets(0, {"ante": 100}, 0)
