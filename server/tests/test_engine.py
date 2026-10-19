import random

import pytest

from casino_server.engines import three_card_poker as tcp
from casino_server.engines.cards import Card, Deck


def cards(*codes):
    return [Card.from_code(c) for c in codes]


def test_card_codes_round_trip():
    for card in Deck()._all_cards:
        assert Card.from_code(card.code) == card


def test_spades_royal_wins_whole_jackpot_other_royals_dont():
    bets = tcp.Bets(ante=100, jackpot=100)
    spades = tcp.settle_hand(cards("Qs", "Ks", "As"), cards("2c", "5d", "9h"), bets, False, 777_777)
    assert spades.jackpot_won and spades.jackpot_return == 777_777
    hearts = tcp.settle_hand(cards("Qh", "Kh", "Ah"), cards("2c", "5d", "9h"), bets, False, 777_777)
    assert not hearts.jackpot_won and hearts.jackpot_return == tcp.JACKPOT_ROYAL_NON_SPADES_PAYOUT


def test_bets_validation_and_worst_case_cost():
    with pytest.raises(ValueError):
        tcp.Bets.from_dict({"ante": 0, "pair_plus": 500})
    with pytest.raises(ValueError):
        tcp.Bets.from_dict({"ante": 100, "jackpot": 500})
    with pytest.raises(ValueError):
        tcp.Bets.from_dict({"ante": 100, "prime": -5})
    with pytest.raises(ValueError):
        tcp.Bets.from_dict({"ante": "lots"})
    bets = tcp.Bets.from_dict({"ante": 500, "pair_plus": 100, "prime": 100, "jackpot": 100})
    assert bets.upfront == 800 and bets.max_cost == 1_300


def test_multi_seat_round_deals_distinct_cards_and_settles_each_seat():
    rnd = tcp.ThreeCardPokerRound({0: tcp.Bets(ante=100), 2: tcp.Bets(ante=500)}, deck=Deck(rng=random.Random(5)))
    dealt = rnd.hands[0] + rnd.hands[2] + rnd.dealer_cards
    assert len(set(dealt)) == 9
    rnd.decide(0, play=True)
    with pytest.raises(ValueError):
        rnd.decide(0, play=False)
    assert not rnd.all_decided
    rnd.decide(2, play=False)
    results = rnd.settle()
    assert set(results) == {0, 2}
    assert results[2].outcome == "fold" and results[2].net == -500
    assert results[0].dealer_cards == results[2].dealer_cards


def test_should_play_threshold_is_q64():
    from casino_server.engines.hand_evaluator import evaluate_three_card_hand as ev
    assert tcp.should_play(ev(cards("Qs", "6d", "4h")))
    assert not tcp.should_play(ev(cards("Qs", "6d", "3h")))
    assert tcp.should_play(ev(cards("2s", "2d", "3h")))


def test_rules_paytable_reads_engine_constants():
    rules = tcp.rules()
    pair_plus = next(s for s in rules["sections"] if s["title"] == "Pair Plus")
    assert pair_plus["rows"][0] == ["Straight Flush", "35:1"]
    assert rules["jackpot_bet"] == tcp.JACKPOT_BET
