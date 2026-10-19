"""
Parity with Casino v2's Ultimate Texas Hold'em and Let It Ride engines: every
bet's return must match to the penny over thousands of random hands. Plus the
NPC strategies, spot-checked. The parity part is skipped if ~/Projects/Casino
isn't on this machine.
"""
import random
import sys
from pathlib import Path

import pytest

from casino_server.engines import let_it_ride as lir
from casino_server.engines import ultimate_texas_holdem as uth
from casino_server.engines.cards import Card, Deck

V2_ROOT = Path.home() / "Projects" / "Casino"
needs_v2 = pytest.mark.skipif(not (V2_ROOT / "games" / "let_it_ride" / "logic.py").exists(),
                              reason="Casino v2 not present")


@pytest.fixture(scope="module")
def v2():
    sys.path.insert(0, str(V2_ROOT))
    try:
        from core import cards as v2_cards
        from games.let_it_ride import logic as v2_lir
        from games.ultimate_texas_holdem import logic as v2_uth
        yield v2_cards, v2_uth, v2_lir
    finally:
        sys.path.remove(str(V2_ROOT))


def to_v2(v2_cards, cards):
    return [v2_cards.Card(c.rank, v2_cards.Suit[c.suit.name]) for c in cards]


def cards(*codes):
    return [Card.from_code(c) for c in codes]


@needs_v2
def test_holdem_returns_match_v2(v2):
    v2_cards, v2_uth, _ = v2
    rng = random.Random(31)
    deck = Deck(rng=rng)
    pool = 800.0
    outcomes = set()
    for _ in range(8_000):
        deck.reset()
        hole, dealer, board = deck.deal(2), deck.deal(2), deck.deal(5)
        ante, trips, jackpot = rng.choice([1, 5, 25]), rng.choice([0, 0, 1, 5]), rng.choice([0, 1])
        folded = rng.random() < 0.15
        play = 0 if folded else rng.choice([4, 3, 2, 1])
        game = v2_uth.UltimateTexasHoldemGame()
        game.deal(float(ante), float(trips), float(jackpot))
        r = game.result
        r.player_cards, r.dealer_cards, r.community_cards = (to_v2(v2_cards, x) for x in (hole, dealer, board))
        game.reveal_flop()
        game.reveal_turn()
        game.reveal_river()
        if folded:
            game.fold()
        else:
            game.bet_play(play)
        v = game.settle(pool)
        ours = uth.settle(hole, dealer, board, uth.Bets(ante * 100, trips * 100, jackpot * 100, play * ante * 100), folded)
        assert ours.outcome == v.outcome
        assert (ours.ante_return, ours.blind_return, ours.play_return, ours.trips_return) == \
            tuple(round(x * 100) for x in (v.ante_return, v.blind_return, v.play_return, v.trips_return))
        if ours.jackpot_share:
            assert round(pool * ours.jackpot_share * 100) == round(v.jackpot_return * 100)
        else:
            assert ours.jackpot_fixed == round(v.jackpot_return * 100)
        outcomes.add(ours.outcome)
    assert outcomes == {"win", "lose", "push", "fold"}


@needs_v2
def test_let_it_ride_returns_match_v2(v2):
    v2_cards, _, v2_lir = v2
    rng = random.Random(41)
    deck = Deck(rng=rng)
    pool = 800.0
    for _ in range(10_000):
        deck.reset()
        hand, community = deck.deal(3), deck.deal(2)
        unit = rng.choice([1, 5, 25])
        bonus, three, jackpot = rng.choice([0, 1]), rng.choice([0, 0, 1, 5]), rng.choice([0, 1])
        ride1, ride2 = rng.random() < 0.6, rng.random() < 0.6
        game = v2_lir.LetItRideGame()
        game.deal(float(unit), float(bonus), float(three), float(jackpot))
        game.result.player_cards, game.result.community_cards = to_v2(v2_cards, hand), to_v2(v2_cards, community)
        refund = game.decide_bet1(ride1)
        game.reveal_first_card()
        refund += game.decide_bet2(ride2)
        game.reveal_second_card()
        v = game.settle(pool)
        ours = lir.settle(hand, community, lir.Bets(unit * 100, bonus * 100, three * 100, jackpot * 100, ride1, ride2))
        assert ours.base_returns["ante"] == round(v.ante_return * 100)
        if ride1:
            assert ours.base_returns["bet1"] == round(v.bet1_return * 100)
        if ride2:
            assert ours.base_returns["bet2"] == round(v.bet2_return * 100)
        assert ours.bonus_return == round(v.bonus_return * 100)
        assert ours.three_card_return == round(v.three_card_return * 100)
        if ours.jackpot_share:
            assert round(pool * ours.jackpot_share * 100) == round(v.jackpot_return * 100)
        else:
            assert ours.jackpot_fixed == round(v.jackpot_return * 100)


@pytest.mark.parametrize("hole, expected", [
    (["3c", "3d"], 4), (["2c", "2d"], 0), (["Ac", "2d"], 4), (["Kc", "2c"], 4), (["Kc", "4d"], 0), (["Kc", "5d"], 4),
    (["Qc", "6c"], 4), (["Qc", "5c"], 0), (["Qc", "8d"], 4), (["Qc", "7d"], 0), (["Jc", "8c"], 4), (["Jc", "7c"], 0),
    (["Jc", "10d"], 4), (["Jc", "9d"], 0), (["10c", "9c"], 0),
])
def test_holdem_preflop(hole, expected):
    assert uth.preflop_bet(cards(*hole)) == expected


@pytest.mark.parametrize("hole, flop, expected", [
    (["7c", "4d"], ["7h", "Kd", "2s"], 2),     # hidden pair
    (["2c", "2d"], ["7h", "Kd", "9s"], 0),     # pocket 2s: check
    (["9c", "4d"], ["Kh", "Kd", "2s"], 0),     # the pair's on the board
    (["Ac", "5c"], ["8c", "2c", "Kh"], 2),     # four to a flush with a hidden Ace of the suit
    (["9c", "5c"], ["8c", "2c", "Kh"], 0),     # ...but not with only a hidden 9
    (["Kc", "Qd"], ["Jh", "10d", "9s"], 2),    # a made straight
])
def test_holdem_flop(hole, flop, expected):
    assert uth.flop_bet(cards(*hole), cards(*flop)) == expected


def test_holdem_river():
    assert uth.river_bet(cards("7c", "4d"), cards("7h", "Kd", "2s", "9c", "Jh")) == 1   # hidden pair
    # Playing the board K-K-Q-Q-J: only an Ace, King or Queen beats it (8 outs; a Jack ties) -- bet.
    assert uth.dealer_outs(cards("3c", "4d"), cards("Kh", "Kd", "Qs", "Qc", "Jh")) == 8
    assert uth.river_bet(cards("3c", "4d"), cards("Kh", "Kd", "Qs", "Qc", "Jh")) == 1
    # 4-high kickers on K-Q-9-7-2: any pairing card (15) or 5+ (24) beats you -- fold.
    assert uth.river_bet(cards("3c", "4d"), cards("Kh", "Qd", "9s", "7c", "2h")) == 0
    outs = uth.dealer_outs(cards("Ac", "Kd"), cards("2h", "5d", "8s", "9c", "Jh"))
    assert 0 < outs < 21 and uth.river_bet(cards("Ac", "Kd"), cards("2h", "5d", "8s", "9c", "Jh")) == 1


@pytest.mark.parametrize("hand, expected", [
    (["10c", "10d", "2s"], True), (["9c", "9d", "2s"], False), (["10h", "Jh", "Qh"], True),
    (["5h", "6h", "7h"], True), (["2h", "3h", "4h"], False), (["Ah", "2h", "3h"], False),
    (["9h", "10h", "Qh"], True), (["5h", "6h", "8h"], False), (["8h", "10h", "Qh"], True), (["7h", "9h", "Jh"], False),
])
def test_let_it_ride_first(hand, expected):
    assert lir.ride_first(cards(*hand)) is expected


@pytest.mark.parametrize("hand, expected", [
    (["10c", "10d", "2s", "5h"], True), (["2h", "6h", "9h", "Kh"], True), (["5c", "6d", "7s", "8h"], True),
    (["Ac", "2d", "3s", "4h"], False), (["5c", "6d", "8s", "9h"], False), (["10c", "Jd", "Ks", "Ah"], True),
    (["Jc", "Qd", "Ks", "Ah"], True), (["3c", "3d", "5s", "Kh"], False), (["3c", "3d", "5s", "5h"], True),
])
def test_let_it_ride_second(hand, expected):
    assert lir.ride_second(cards(*hand)) is expected
