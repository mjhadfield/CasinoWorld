"""
Card-for-card parity with Casino v2's engine: the same hands, bets and
Play/Fold decisions must return exactly the same money (v2 float pounds x 100
== our pence). Skipped if ~/Projects/Casino isn't on this machine.
"""
import random
import sys
from pathlib import Path

import pytest

from casino_server.engines import three_card_poker as tcp
from casino_server.engines.cards import Card, Deck

V2_ROOT = Path.home() / "Projects" / "Casino"
pytestmark = pytest.mark.skipif(not (V2_ROOT / "games" / "three_card_poker" / "logic.py").exists(),
                                reason="Casino v2 not present")


@pytest.fixture(scope="module")
def v2():
    sys.path.insert(0, str(V2_ROOT))
    try:
        from core import cards as v2_cards
        from core.hand_evaluator import evaluate_three_card_hand
        from games.three_card_poker import logic
        yield v2_cards, evaluate_three_card_hand, logic
    finally:
        sys.path.remove(str(V2_ROOT))


def to_v2(v2_cards, card: Card):
    return v2_cards.Card(card.rank, v2_cards.Suit[card.suit.name])


def v2_resolve(v2, player, dealer, bets: tcp.Bets, folded, jackpot_pence):
    v2_cards, evaluate, logic = v2
    game = logic.ThreeCardPokerGame()
    result = game.play_round(bets.ante / 100, bets.pair_plus / 100, bets.prime / 100, bets.jackpot / 100)
    result.player_cards = [to_v2(v2_cards, c) for c in player]
    result.dealer_cards = [to_v2(v2_cards, c) for c in dealer]
    result.player_eval = evaluate(result.player_cards)
    result.dealer_eval = evaluate(result.dealer_cards)
    return game.resolve(folded, jackpot_pence / 100)


def assert_same(v2r, ours: tcp.HandResult):
    pairs = [("ante_return", "ante_return"), ("play_return", "play_return"),
             ("ante_bonus_return", "ante_bonus_return"), ("pair_plus_return", "pair_plus_return"),
             ("prime_return", "prime_return"), ("jackpot_return", "jackpot_return"),
             ("total_returned", "total_returned"), ("total_wagered", "total_wagered")]
    for v2_field, our_field in pairs:
        assert round(getattr(v2r, v2_field) * 100) == getattr(ours, our_field), v2_field
    assert round(v2r.net_result * 100) == ours.net
    assert v2r.outcome == ours.outcome
    assert v2r.jackpot_won == ours.jackpot_won
    assert v2r.dealer_qualified == ours.dealer_qualified


def test_random_rounds_match_v2(v2):
    rng = random.Random(1234)
    deck = Deck(rng=rng)
    for _ in range(20_000):
        deck.reset()
        player, dealer = deck.deal(3), deck.deal(3)
        bets = tcp.Bets(ante=rng.choice([100, 500, 2_500]), pair_plus=rng.choice([0, 0, 100, 500]),
                        prime=rng.choice([0, 0, 100, 2_500]), jackpot=rng.choice([0, 100]))
        folded = rng.random() < 0.3
        ours = tcp.settle_hand(player, dealer, bets, folded, 712_345)
        assert_same(v2_resolve(v2, player, dealer, bets, folded, 712_345), ours)


@pytest.mark.parametrize("player", [["Qs", "Ks", "As"], ["Qh", "Kh", "Ah"], ["2c", "3c", "4c"],
                                    ["7d", "7s", "7h"], ["Ac", "2d", "3s"], ["2h", "4h", "9h"]])
@pytest.mark.parametrize("dealer", [["Jc", "8d", "3h"], ["Kd", "Kc", "2s"], ["Qd", "5c", "2d"]])
@pytest.mark.parametrize("folded", [False, True])
def test_special_hands_match_v2(v2, player, dealer, folded):
    p, d = [Card.from_code(c) for c in player], [Card.from_code(c) for c in dealer]
    bets = tcp.Bets(ante=1_000, pair_plus=500, prime=500, jackpot=100)
    ours = tcp.settle_hand(p, d, bets, folded, 1_234_567)
    assert_same(v2_resolve(v2, p, d, bets, folded, 1_234_567), ours)
