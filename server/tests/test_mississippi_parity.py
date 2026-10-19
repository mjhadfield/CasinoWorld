"""
Parity with Casino v2's Mississippi Stud engine: every bet's return must match
to the penny over thousands of random hands, folds and street bets included.
Plus Kisenwether's strategy chart, line by line. Skipped (the parity part) if
~/Projects/Casino isn't on this machine.
"""
import random
import sys
from pathlib import Path

import pytest

from casino_server.engines import mississippi_stud as ms
from casino_server.engines.cards import Card, Deck

V2_ROOT = Path.home() / "Projects" / "Casino"
needs_v2 = pytest.mark.skipif(not (V2_ROOT / "games" / "mississippi_stud" / "logic.py").exists(),
                              reason="Casino v2 not present")


@pytest.fixture(scope="module")
def v2():
    sys.path.insert(0, str(V2_ROOT))
    try:
        from core import cards as v2_cards
        from games.mississippi_stud import logic
        yield v2_cards, logic
    finally:
        sys.path.remove(str(V2_ROOT))


def to_v2(v2_cards, cards):
    return [v2_cards.Card(c.rank, v2_cards.Suit[c.suit.name]) for c in cards]


def cards(*codes):
    return [Card.from_code(c) for c in codes]


@needs_v2
def test_every_return_matches_v2(v2):
    v2_cards, logic = v2
    rng = random.Random(2026)
    deck = Deck(rng=rng)
    pool = 800.0  # v2's jackpot meter in pounds
    wins = folds = 0
    for _ in range(20_000):
        deck.reset()
        hole, community = deck.deal(2), deck.deal(3)
        ante = rng.choice([1, 5, 25])
        bonus = rng.choice([0, 0, 1, 5])
        jackpot = rng.choice([0, 1])
        fold_at = rng.choice([None, None, None, 3, 4, 5])
        streets = [0, 0, 0]

        game = logic.MississippiStudGame()
        game.deal(float(ante), float(bonus), float(jackpot))
        game.result.player_cards, game.result.community_cards = to_v2(v2_cards, hole), to_v2(v2_cards, community)
        for street in (3, 4, 5):
            if street == fold_at:
                game.fold(street)
                if bonus:
                    game.reveal_remaining_for_bonus()
                break
            times = rng.choice([1, 2, 3])
            game.bet_street(street, times)
            streets[street - 3] = ante * 100 * times
        v2r = game.settle(pool)

        ours = ms.settle(hole, community, ms.Bets(ante * 100, bonus * 100, jackpot * 100, streets), fold_at is not None)
        assert ours.outcome == v2r.outcome
        assert ours.ante_return == round(v2r.ante_return * 100)
        assert ours.street_returns == [round(v2r.third_street_return * 100), round(v2r.fourth_street_return * 100),
                                       round(v2r.fifth_street_return * 100)]
        assert ours.bonus_return == round(v2r.bonus_return * 100)
        if ours.jackpot_share:
            assert round(pool * ours.jackpot_share * 100) == round(v2r.jackpot_return * 100)
            assert (ours.jackpot_share == 1.0) == v2r.jackpot_won
        else:
            assert ours.jackpot_fixed == round(v2r.jackpot_return * 100)
        wins += ours.outcome == "win"
        folds += ours.outcome == "fold"
    assert wins > 1_000 and folds > 5_000  # the sample really covered both


def test_the_paytables_spot_check():
    royal = ms.settle(cards("As", "Ks"), cards("Qs", "Js", "10s"), ms.Bets(100, 100, 100, [300, 300, 300]), False)
    assert royal.outcome == "win" and royal.multiplier == 500 and royal.main_return == 1_000 * 501
    assert royal.jackpot_share == 1.0 and royal.bonus_return == 100 * 41  # Q-J-10 suited: a 3-card straight flush
    push = ms.settle(cards("9h", "9d"), cards("2c", "5s", "Kd"), ms.Bets(500, streets=[500, 500, 500]), False)
    assert push.outcome == "push" and push.main_return == 2_000
    folded = ms.settle(cards("2h", "7d"), cards("Kc", "Kd", "Ks"), ms.Bets(500, 100, 100, [500, 0, 0]), True)
    assert folded.outcome == "fold" and folded.total_returned == 100 * 31 and folded.jackpot_fixed == 0


@pytest.mark.parametrize("hand, raised, expected", [
    # 2 cards
    (["7h", "7d"], False, 3), (["Kc", "2d"], False, 1), (["9c", "8d"], False, 1), (["6s", "5s"], False, 1),
    (["6s", "5d"], False, 0), (["9c", "2d"], False, 0), (["5s", "4s"], False, 0),
    # 3 cards
    (["6c", "6d", "2s"], False, 3), (["10h", "Jh", "Qh"], False, 3), (["5d", "6d", "7d"], False, 3),
    (["3d", "4d", "5d"], False, 1), (["9s", "Js", "Ks"], False, 3), (["8s", "10s", "Qs"], False, 1),
    (["7c", "8c", "10c"], False, 1), (["8c", "9c", "Jc"], False, 3), (["2h", "7h", "Kh"], False, 1),
    (["2c", "2d", "Ks"], False, 1), (["Jc", "8d", "3s"], False, 1), (["4c", "5d", "6s"], False, 1),
    (["3c", "4d", "5s"], False, 0), (["6c", "7d", "9s"], False, 1), (["2c", "3d", "Ks"], False, 0),
    # 4 cards
    (["7c", "7d", "2s", "Kh"], False, 3), (["2h", "6h", "9h", "Qh"], False, 3), (["5c", "6d", "7s", "8h"], False, 3),
    (["10c", "Jd", "Qs", "Kh"], False, 3), (["4c", "5d", "6s", "7h"], False, 1), (["Jc", "Qd", "Ks", "Ah"], False, 1),
    (["5c", "6d", "8s", "9h"], False, 1), (["2c", "2d", "3s", "Kh"], False, 1), (["Kc", "Qd", "2s", "3h"], False, 1),
    (["2c", "3d", "9s", "Qh"], False, 0), (["6c", "8d", "10s", "2h"], True, 1), (["6c", "8d", "10s", "2h"], False, 0),
    (["3c", "3d", "4s", "4h"], False, 3),  # two pair is a made hand
])
def test_kisenwether_strategy(hand, raised, expected):
    assert ms.strategy(cards(*hand), raised) == expected
