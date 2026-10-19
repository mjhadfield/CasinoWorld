"""
Parity with Casino v2's Pai Gow engines -- and the one place we deliberately
differ: v2's House Way never paired the Joker with a real Ace. Every other
hand must be set identically, and the bonus tiers and Ante results must
match to the penny. Skipped if ~/Projects/Casino isn't on this machine.
"""
import random
import sys
from pathlib import Path

import pytest

from casino_server.engines import pai_gow as pg
from casino_server.engines.cards import Card, Deck

V2_ROOT = Path.home() / "Projects" / "Casino"
pytestmark = pytest.mark.skipif(not (V2_ROOT / "games" / "pai_gow_poker" / "logic.py").exists(),
                                reason="Casino v2 not present")


@pytest.fixture(scope="module")
def v2():
    sys.path.insert(0, str(V2_ROOT))
    try:
        from core import cards as v2_cards
        from games.pai_gow_poker import logic
        from games.pai_gow_poker_face_up import logic as face_up
        yield v2_cards, logic, face_up
    finally:
        sys.path.remove(str(V2_ROOT))


def to_v2(v2_cards, cards):
    return [v2_cards.Card("Joker") if c.is_joker else v2_cards.Card(c.rank, v2_cards.Suit[c.suit.name]) for c in cards]


def codes(cards):
    return sorted(c.code for c in cards)


def joker_with_ace(cards):
    return any(c.is_joker for c in cards) and any(not c.is_joker and c.rank == "A" for c in cards)


def has_quads(cards):
    ranks = [c.rank for c in cards if not c.is_joker]
    return any(ranks.count(r) == 4 for r in ranks)


def test_house_way_matches_v2_except_joker_with_an_ace(v2):
    v2_cards, logic, _ = v2
    rng = random.Random(77)
    deck = Deck(include_joker=True, rng=rng)
    checked = fixed = 0
    for _ in range(6_000):
        deck.reset()
        hand = deck.deal(7)
        front, back = pg.house_way_set(hand)
        assert not pg.is_foul(front, back)
        if joker_with_ace(hand):
            # The fix: a Joker with a real Ace stays with it as a pair of Aces --
            # unless it's better used completing a Straight or Flush in the back.
            joker = next(c for c in hand if c.is_joker)
            side = front if joker in front else back
            with_ace = any(not c.is_joker and c.rank == "A" for c in side)
            assert with_ace or pg.evaluate_five(back)[0] >= pg.FIVE_CARD_STRAIGHT
            fixed += 1
            continue
        if has_quads(hand):
            continue  # v2 called the chart's quad splits fouls (see test_quads_split_as_the_chart_says)
        v2_front, v2_back = logic.house_way_set(to_v2(v2_cards, hand))
        assert codes(front) == sorted(_v2_code(c) for c in v2_front)
        assert codes(back) == sorted(_v2_code(c) for c in v2_back)
        checked += 1
    assert checked > 4_000 and fixed > 100


def _v2_code(card):
    if card.is_joker:
        return "Jkr"
    return f"{card.rank}{card.suit.name[0].lower()}"


def test_bonus_tiers_match_v2(v2):
    v2_cards, logic, _ = v2
    rng = random.Random(5)
    deck = Deck(include_joker=True, rng=rng)
    for _ in range(6_000):
        deck.reset()
        hand = deck.deal(7)
        assert pg.classify_seven_card_bonus(hand) == logic.classify_seven_card_bonus(to_v2(v2_cards, hand))


def test_ante_settles_like_v2(v2):
    v2_cards, logic, face_up = v2
    rng = random.Random(11)
    deck = Deck(include_joker=True, rng=rng)
    for _ in range(3_000):
        deck.reset()
        player, dealer = deck.deal(7), deck.deal(7)
        if joker_with_ace(player) or joker_with_ace(dealer):
            continue  # set differently by design (see above)
        front, back = pg.house_way_set(player)
        d_front, d_back = pg.house_way_set(dealer)
        for module, commission in ((logic, True), (face_up, False)):
            game = module.PaiGowPokerGame() if module is logic else module.PaiGowFaceUpGame()
            result = game._make_result()
            result.ante_bet = 10.0
            result.player_front, result.player_back = to_v2(v2_cards, front), to_v2(v2_cards, back)
            result.dealer_front, result.dealer_back = to_v2(v2_cards, d_front), to_v2(v2_cards, d_back)
            if module is face_up:
                result.dealer_front_eval = logic.evaluate_two_card_hand(result.dealer_front)
                result.dealer_back_eval = logic.best_five_card_eval_with_joker(result.dealer_back)
            game.result = result
            game.settle()
            ours = pg.settle_ante(front, back, d_front, d_back, 1_000, commission)
            assert ours.outcome == result.outcome
            assert ours.returned == round(result.ante_return * 100)


def test_the_reported_face_up_bug_is_fixed(v2):
    """Joker + Ace + five unpaired cards is a pair of Aces -- v2 split them and
    called it an Ace-high Pai Gow, pushing every Ante at Face Up."""
    v2_cards, logic, face_up = v2
    hand = [Card("Joker")] + [Card.from_code(c) for c in ("As", "Kd", "9c", "7h", "5s", "3d")]
    v2_front, v2_back = logic.house_way_set(to_v2(v2_cards, hand))
    assert face_up.is_ace_high_pai_gow(logic.evaluate_two_card_hand(v2_front),
                                       logic.best_five_card_eval_with_joker(v2_back))  # v2: wrongly a push
    front, back = pg.house_way_set(hand)
    assert not pg.is_ace_high_pai_gow(hand)
    assert pg.five_card_label(pg.evaluate_five(back)) == "Pair of Aces"
    assert codes(front) == ["9c", "Kd"]
    # A Joker with no Ace really is an Ace-high Pai Gow.
    assert pg.is_ace_high_pai_gow([Card("Joker")] + [Card.from_code(c) for c in ("Qs", "Kd", "9c", "7h", "5s", "3d")])


def test_quads_split_as_the_chart_says():
    """Four 9s with no King up front split into a pair each way -- legal, as the
    5-card pair has kickers. v2's foul check rejected it."""
    hand = [Card.from_code(c) for c in ("9s", "9h", "9d", "9c", "Qh", "7d", "4s")]
    front, back = pg.house_way_set(hand)
    assert sorted(c.rank for c in front) == ["9", "9"]
    assert pg.five_card_label(pg.evaluate_five(back)) == "Pair of 9s"
    assert not pg.is_foul(front, back)
    # Four Aces made with the Joker and no pair to go with them: Aces split too.
    hand = [Card("Joker")] + [Card.from_code(c) for c in ("Ad", "Ac", "Ah", "9d", "Ks", "4h")]
    front, back = pg.house_way_set(hand)
    assert sorted(c.rank for c in front) == ["A", "A"] and not pg.is_foul(front, back)
    # Real fouls are still fouls.
    assert pg.is_foul([Card.from_code("Ks"), Card.from_code("Kd")],
                      [Card.from_code(c) for c in ("Qs", "Qd", "9c", "7h", "2s")])
    assert pg.is_foul([Card.from_code("As"), Card.from_code("Kd")],
                      [Card.from_code(c) for c in ("Ac", "Qd", "9c", "7h", "2s")])

