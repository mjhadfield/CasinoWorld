"""The Blackjack table machine, driven directly with explicit times -- no sleeping.

Rigged shoes list cards in the order they come out: each box's first card
(first base first), the dealer's up-card, each box's second card, the
dealer's hole card, then hits, splits and doubles, then the dealer's draws.
"""
import random

import pytest

from casino_server.engines import blackjack as bj
from casino_server.tables.blackjack import SHOE_CARDS, BlackjackMachine, Timings
from casino_server.tables.base import TableError

from conftest import RiggedDeck
from test_machine import FakeJackpot, FakeParticipant

FILLER = ["2c"] * 30  # so a rigged shoe never runs dry


def timings(**over):
    """Instant, except long insurance and turn windows so players get to act."""
    t = Timings.instant()
    t.insurance = t.turn = 100.0
    for k, v in over.items():
        setattr(t, k, v)
    return t


def machine(codes, **kw):
    m = BlackjackMachine("bj_test", 6, kw.pop("timings", timings()), kw.pop("jackpot", FakeJackpot()),
                         deck_factory=lambda: RiggedDeck(list(codes) + FILLER), **kw)
    return m


def kinds(events):
    return [e["kind"] for e in events]


def deal(m, *players, bets=None, now=0.0):
    """Seat these players (seat 0, 1, ...), bet, Ready, and run the deal."""
    events = []
    for i, p in enumerate(players):
        m.sit(i, p, now)
        m.set_bets(i, bets[i] if bets else {"bet": 1_000}, now)
        events += m.ready(i, now)
    return events + m.tick(now)


def test_stand_dealer_draws_to_17_and_pays_the_winner():
    p = FakeParticipant("Mike")
    m = machine(["10h", "6c", "9d", "10s", "2d"])
    events = deal(m, p)
    assert kinds(events)[-1] == "turn" and m.turn == (0, 0)
    dealt = next(e for e in events if e["kind"] == "dealt")
    assert dealt["cards"] == {"0": ["10h", "9d"]} and dealt["dealer_up"] == "6c" and dealt["labels"] == {"0": "19"}
    assert m.snapshot(None, 0)["dealer"]["cards"] == ["6c", "??"]  # the hole card stays hidden
    events = m.play_action(0, "stand", 1) + m.tick(1)
    assert kinds(events)[:6] == ["action", "dealer_reveal", "dealer_draw", "dealer_done", "say", "settle_seat"]
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert settle["hands"] == [{"hand": 0, "outcome": "Win", "label": "19", "action": "pay", "amount": 1_000, "payout": 1_000}]
    assert p.balance == 101_000
    assert m.phase == "betting"


def test_natural_blackjack_is_paid_3_to_2_at_once_and_skips_the_turn():
    p = FakeParticipant("Mike")
    m = machine(["As", "9c", "Kd", "7h", "5s"])
    events = deal(m, p)
    paid = next(e for e in events if e["kind"] == "blackjacks_paid")
    assert paid["seats"] == [{"seat": 0, "hand": 0, "amount": 1_000, "payout": 1_500}]
    assert "turn" not in kinds(events) and "settle_seat" not in kinds(events)
    assert "dealer_draw" not in kinds(events)  # nobody left to beat
    assert p.balance == 101_500


def test_with_a_10_showing_blackjacks_are_paid_after_the_peek_and_before_play():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = machine(["Ah", "9d", "Kc", "Kd", "8s", "7c"])  # A: Blackjack; B: 9+8; dealer K up, 7 down
    events = deal(m, a, b)
    order = kinds(events)
    assert order.index("peek") < order.index("blackjacks_paid") < order.index("turn")
    assert a.balance == 101_500 and m.turn == (1, 0)
    assert m.snapshot(None, 0)["seats"][0]["hands"][0]["gone"]


def test_a_blackjack_pushes_against_a_dealer_blackjack():
    p = FakeParticipant("Mike")
    m = machine(["As", "Ac", "Kd", "Kh"])
    events = deal(m, p)
    m.insure(0, False, 1)
    events = m.tick(1)
    assert "blackjacks_paid" not in kinds(events)
    assert next(e for e in events if e["kind"] == "settle_seat")["hands"][0]["outcome"] == "Push"
    assert p.balance == 100_000


def test_insurance_pays_2_to_1_on_a_dealer_blackjack():
    p = FakeParticipant("Mike")
    m = machine(["10c", "As", "9c", "Kh"])
    events = deal(m, p)
    opened = next(e for e in events if e["kind"] == "insurance_open")
    assert opened["costs"] == {"0": 500} and m.phase == "insurance"
    events = m.insure(0, True, 1) + m.tick(1)
    assert "peek" in kinds(events)
    reveal = next(e for e in events if e["kind"] == "dealer_reveal")
    assert reveal["blackjack"] and reveal["cards"] == ["As", "Kh"]
    settled = next(e for e in events if e["kind"] == "insurance_settled")
    assert settled["seats"] == [{"seat": 0, "action": "pay", "amount": 500, "payout": 1_000}]
    assert next(e for e in events if e["kind"] == "settle_seat")["hands"][0]["outcome"] == "Lose"
    assert p.balance == 100_000  # lost the 10, won the insurance


def test_no_dealer_blackjack_takes_the_insurance_and_play_goes_on():
    p = FakeParticipant("Mike")
    m = machine(["10c", "Ah", "9c", "5c", "2d"])
    deal(m, p)
    events = m.insure(0, True, 1) + m.tick(1)
    assert next(e for e in events if e["kind"] == "insurance_settled")["seats"][0]["action"] == "collect"
    assert m.phase == "playing" and m.turn == (0, 0)
    events = m.play_action(0, "stand", 2) + m.tick(2)
    assert next(e for e in events if e["kind"] == "dealer_done")["total"] == 18  # soft 16, draws a 2, stands on 18
    assert p.balance == 100_000 - 1_000 - 500 + 2_000


def test_split_double_and_dealer_bust():
    p = FakeParticipant("Mike")
    m = machine(["8s", "6h", "8d", "10c", "3c", "2h", "10d", "9s", "10h"])
    deal(m, p)
    events = m.play_action(0, "split", 1)
    split = next(e for e in events if e["kind"] == "action")
    assert split["hands"] == [["8s", "3c"], ["8d", "2h"]] and split["amount"] == 1_000
    assert kinds(events)[-1] == "turn"
    events = m.play_action(0, "double", 2) + m.tick(2)  # 11 doubles to 21
    assert next(e for e in events if e["kind"] == "action")["total"] == "21"
    assert m.turn == (0, 1)
    m.play_action(0, "hit", 3)  # 10 + 9
    events = m.play_action(0, "stand", 4) + m.tick(4)
    assert next(e for e in events if e["kind"] == "dealer_done")["bust"]
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert [(h["outcome"], h["amount"]) for h in settle["hands"]] == [("Win", 2_000), ("Win", 1_000)]
    assert p.balance == 100_000 - 3_000 + 6_000


def test_a_bust_is_swept_and_the_dealer_doesnt_draw_against_nobody():
    p = FakeParticipant("Mike")
    m = machine(["10s", "9h", "6d", "5c", "10c"])
    deal(m, p)
    events = m.play_action(0, "hit", 1) + m.tick(1)
    assert kinds(events)[:2] == ["action", "bust"]
    assert "dealer_draw" not in kinds(events) and "settle_seat" not in kinds(events)
    assert p.balance == 99_000


def test_side_bets_settle_straight_after_the_deal():
    p = FakeParticipant("Mike")
    m = machine(["7h", "7h", "7h", "10c"])
    bets = {"bet": 1_000, "super_pairs": 100, "twenty_one_plus_three": 100, "top_three": 100, "jackpot": 100}
    events = deal(m, p, bets=[bets])
    side = next(e for e in events if e["kind"] == "side_bets")
    returns = {s["spot"]: s["payout"] for s in side["seats"][0]["steps"]}
    assert returns == {"super_pairs": 5_000, "twenty_one_plus_three": 900, "top_three": 27_000, "jackpot": 62_500}
    assert side["seats"][0]["returned"] == 5_100 + 1_000 + 27_100 + 62_500
    m.play_action(0, "stand", 1)
    m.tick(1)  # 14 loses to 17
    assert p.balance == 100_000 - 1_400 + 95_700


def test_suited_aces_take_the_whole_jackpot_pool():
    p, pot = FakeParticipant("Mike"), FakeJackpot(700_000)
    m = machine(["Ah", "Ah", "Ah", "9c"], jackpot=pot)
    events = deal(m, p, bets=[{"bet": 1_000, "jackpot": 100}])
    won = next(e for e in events if e["kind"] == "jackpot_won")
    assert won["amount"] == 700_000 and pot.wins == 1


def test_top_3_needs_a_21_plus_3_bet():
    m = machine([])
    m.sit(0, FakeParticipant("Mike"), 0)
    with pytest.raises(TableError, match="21\\+3"):
        m.set_bets(0, {"bet": 500, "top_three": 100}, 0)


def test_out_of_time_stands():
    p = FakeParticipant("Mike")
    m = machine(["10h", "6c", "9d", "10s", "2d"], timings=timings(turn=5.0))
    deal(m, p)
    events = m.tick(5.0)
    assert next(e for e in events if e["kind"] == "action") == {
        "kind": "action", "seat": 0, "hand": 0, "action": "stand", "reason": "timeout", "total": "19", "done": True}


def test_cannot_act_out_of_turn_or_double_after_hitting():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = machine(["5h", "6s", "6c", "2d", "4h", "10s", "3c"])
    deal(m, a, b)
    with pytest.raises(TableError, match="turn"):
        m.play_action(1, "hit", 1)
    m.play_action(0, "hit", 1)
    with pytest.raises(TableError, match="first two cards"):
        m.play_action(0, "double", 2)


def test_getting_up_mid_turn_stands_and_still_settles():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = machine(["10h", "10d", "6c", "9s", "8d", "7c", "5h"])
    deal(m, a, b)
    assert m.turn == (0, 0)
    m.stand(0, 1)
    m.tick(1)
    assert m.turn == (1, 0)
    m.play_action(1, "stand", 2)
    m.tick(2)  # dealer 13 draws 5 -> 18; A's 20 wins, B's 18 pushes
    assert a.balance == 101_000 and b.balance == 100_000


def test_the_cut_card_brings_a_shuffle_after_the_hand():
    p = FakeParticipant("Mike")
    m = BlackjackMachine("bj_test", 6, timings(), FakeJackpot(), rng=random.Random(5))
    assert m.shoe.total == SHOE_CARDS and 0.2 * SHOE_CARDS <= m.shoe.cut_at <= 0.3 * SHOE_CARDS
    m.shoe.cut_at = m.shoe.remaining - 2  # the cut card comes out during this deal
    events = deal(m, p)
    assert "cut_card" in kinds(events)
    if m.phase == "insurance":
        events += m.insure(0, False, 1) + m.tick(1)
    while m.phase == "playing":
        events += m.play_action(0, "stand", 1) + m.tick(1)
    assert "shuffle" in kinds(events) and "shoe_loaded" in kinds(events)
    assert m.shoe.remaining == SHOE_CARDS and not m.shoe.cut_out and m.phase == "betting"


def test_the_shoe_carries_on_between_hands():
    p = FakeParticipant("Mike")
    m = BlackjackMachine("bj_test", 6, timings(), FakeJackpot(), rng=random.Random(9))
    before = m.shoe.remaining
    deal(m, p)
    if m.phase == "insurance":
        m.insure(0, False, 1)
        m.tick(1)
    while m.phase == "playing":
        m.play_action(0, "stand", 1)
        m.tick(1)
    assert m.phase == "betting" and m.shoe.remaining < before - 3  # no reshuffle every hand
    assert m.snapshot(0, 2)["discards"] == before - m.shoe.remaining


def test_basic_strategy_npc_call():
    from casino_server.engines.cards import Card
    cards = [Card.from_code("8s"), Card.from_code("8d")]
    assert bj.recommend(cards, Card.from_code("10h"), True, True) == "split"
    assert bj.recommend([Card.from_code("10s"), Card.from_code("6d")], Card.from_code("10h"), True, False) == "hit"
