"""
Card-for-card parity with Casino v2's Blackjack engine and basic strategy: the
same cards and bets must give the same totals, outcomes, side-bet returns
(v2 float pounds x 100 == our pence) and strategy calls. Skipped if
~/Projects/Casino isn't on this machine.
"""
import random
import sys
from pathlib import Path

import pytest

from casino_server.engines import blackjack as bj
from casino_server.engines.cards import Card, Deck

V2_ROOT = Path.home() / "Projects" / "Casino"
pytestmark = pytest.mark.skipif(not (V2_ROOT / "games" / "blackjack" / "logic.py").exists(),
                                reason="Casino v2 not present")


@pytest.fixture(scope="module")
def v2():
    sys.path.insert(0, str(V2_ROOT))
    try:
        from core import cards as v2_cards
        from games.blackjack import logic, strategy
        yield v2_cards, logic, strategy
    finally:
        sys.path.remove(str(V2_ROOT))


def to_v2(v2_cards, cards):
    return [v2_cards.Card(c.rank, v2_cards.Suit[c.suit.name]) for c in cards]


def test_totals_and_settling_match_v2(v2):
    v2_cards, logic, _ = v2
    rng = random.Random(21)
    deck = Deck(num_decks=8, rng=rng)
    for _ in range(20_000):
        if deck.cards_remaining() < 20:
            deck.reset()
        cards = deck.deal(rng.choice([2, 2, 3, 4]))
        dealer = deck.deal(rng.choice([2, 3, 4]))
        bet = rng.choice([100, 500, 2_500])
        from_split = rng.random() < 0.15
        assert bj.hand_value(cards) == logic.hand_value(to_v2(v2_cards, cards))
        ours = bj.Hand(list(cards), bet=bet, from_split=from_split)
        theirs = logic.Hand(to_v2(v2_cards, cards), bet=bet / 100, from_split=from_split)
        dealer_total, _ = bj.hand_value(dealer)
        dealer_bj = bj.is_blackjack(dealer)
        outcome, ret = bj.settle_hand(ours, dealer_total, dealer_total > 21, dealer_bj)
        v2_outcome, v2_ret = logic._settle_hand(theirs, dealer_total, dealer_total > 21, dealer_bj)
        assert (outcome, ret) == (v2_outcome, round(v2_ret * 100))


def v2_side_bets(v2, cards, up, bets, jackpot_pence):
    v2_cards, logic, _ = v2
    game = logic.BlackjackGame()
    game.dealer_cards = to_v2(v2_cards, [up])
    box = logic.Box(main_bet=bets["bet"] / 100, **{f"{k}_bet": bets[k] / 100 for k in bj.SIDE_BETS})
    box.hands = [logic.Hand(to_v2(v2_cards, cards), bet=box.main_bet)]
    game.boxes = [box]
    game._resolve_side_bets(jackpot_pence / 100)
    return {k: round(v * 100) for k, v in box.side_bet_results.items()}, game.jackpot_pool_won


def test_side_bets_match_v2(v2):
    rng = random.Random(33)
    deck = Deck(num_decks=8, rng=rng)
    for _ in range(20_000):
        if deck.cards_remaining() < 10:
            deck.reset()
        cards, up = deck.deal(2), deck.deal(1)[0]
        bets = {"bet": 500, "super_pairs": rng.choice([0, 100, 500]), "twenty_one_plus_three": rng.choice([0, 100, 500]),
                "top_three": 0, "jackpot": rng.choice([0, 100])}
        if bets["twenty_one_plus_three"]:
            bets["top_three"] = rng.choice([0, 100])
        ours = bj.side_bet_returns(cards, up, {k: bets[k] for k in bj.SIDE_BETS if bets[k]})
        theirs, pool = v2_side_bets(v2, cards, up, bets, 712_345)
        if ours.hits_pool:
            ours.returns["jackpot"] = 712_345
        assert ours.returns == theirs
        assert ours.hits_pool == pool


@pytest.mark.parametrize("cards,up", [(["As", "Ks"], "Qs"), (["Qh", "Qh"], "Qh"), (["7d", "7d"], "2c"),
                                      (["8c", "8s"], "8c"), (["5h", "6h"], "7h"), (["Ah", "Ah"], "Ah")])
def test_special_side_bets_match_v2(v2, cards, up):
    cards, up = [Card.from_code(c) for c in cards], Card.from_code(up)
    bets = {"bet": 1_000, "super_pairs": 500, "twenty_one_plus_three": 500, "top_three": 100, "jackpot": 100}
    ours = bj.side_bet_returns(cards, up, {k: bets[k] for k in bj.SIDE_BETS})
    theirs, pool = v2_side_bets(v2, cards, up, bets, 1_234_567)
    if ours.hits_pool:
        ours.returns["jackpot"] = 1_234_567
    assert (ours.returns, ours.hits_pool) == (theirs, pool)


def test_basic_strategy_matches_v2(v2):
    v2_cards, _, strategy = v2
    rng = random.Random(7)
    deck = Deck(num_decks=8, rng=rng)
    actions = {"H": "hit", "S": "stand", "P": "split", "Dh": "double", "Ds": "double"}
    for _ in range(20_000):
        if deck.cards_remaining() < 10:
            deck.reset()
        cards = deck.deal(rng.choice([2, 2, 2, 3]))
        up = deck.deal(1)[0]
        if bj.hand_value(cards)[0] >= 21:
            continue
        can_double, can_split = rng.random() < 0.8, rng.random() < 0.8
        _, _, _, effective = strategy.recommend(to_v2(v2_cards, cards), to_v2(v2_cards, [up])[0], can_double, can_split)
        assert bj.recommend(cards, up, can_double, can_split) == actions[effective]
