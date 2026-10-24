"""NPC slips: believable mistakes on close calls, never anything daft."""
import itertools
import random

from casino_server import npc_slips
from casino_server.engines import blackjack as bj
from casino_server.engines import high_card_flush as hcf
from casino_server.engines import let_it_ride as lir
from casino_server.engines import mississippi_stud as ms
from casino_server.engines import three_card_poker as tcp
from casino_server.engines import ultimate_texas_holdem as uth
from casino_server.engines.cards import Card
from casino_server.engines.hand_evaluator import evaluate_three_card_hand

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = "hdcs"


def cards(*codes):
    return [Card.from_code(c) for c in codes]


def bj_hands():
    """Every two-card hand, and every three-card hand of 21 or under, with the up-card."""
    one = [Card.from_code(r + "h") for r in RANKS]
    for up in [Card.from_code(r + "s") for r in RANKS]:
        for a, b in itertools.combinations_with_replacement(one, 2):
            yield [a, b], up
            for c in one:
                if bj.hand_value([a, b, c])[0] <= 21:
                    yield [a, b, c], up


def test_blackjack_slips_are_never_daft():
    seen = set()
    for hand, up in bj_hands():
        two = len(hand) == 2
        for arch in ("casual", "gambler", "grinder"):
            right = bj.recommend(hand, up, two, two)
            slip = npc_slips.blackjack(hand, up, right, two, two, arch)
            if slip is None:
                continue
            total, soft = bj.hand_value(hand)
            pair = two and bj.card_value(hand[0]) == bj.card_value(hand[1])
            assert arch != "grinder"
            assert slip != right
            assert not (slip == "hit" and total >= 17 and not soft), (hand, up, slip)
            assert not (slip == "hit" and total >= 19), (hand, up, slip)
            assert not (slip == "stand" and total <= 11), (hand, up, slip)
            assert not (slip == "double" and total >= 12 and not soft), (hand, up, slip)
            assert not (slip == "split" and (not pair or total == 10)), (hand, up, slip)
            assert not (hand[0].rank == hand[1].rank == "A" and two), (hand, up, slip)
            seen.add((arch, slip))
    assert {("casual", "stand"), ("casual", "hit"), ("gambler", "split"), ("gambler", "double")} <= seen


def test_blackjack_slips_by_archetype():
    ten = Card.from_code("10s")
    assert npc_slips.blackjack(cards("Kh", "Qd"), ten, "stand", True, True, "casual") is None   # the 20 Arlo hit
    assert npc_slips.blackjack(cards("Kh", "Qd"), ten, "stand", True, True, "gambler") is None
    assert npc_slips.blackjack(cards("Kh", "Qd"), Card.from_code("6s"), "stand", True, True, "gambler") == "split"
    assert npc_slips.blackjack(cards("10h", "6d"), ten, "hit", True, False, "casual") == "stand"
    assert npc_slips.blackjack(cards("8h", "8d"), ten, "split", True, True, "casual") == "stand"
    assert npc_slips.blackjack(cards("6h", "5d"), ten, "double", True, False, "casual") == "hit"
    assert npc_slips.blackjack(cards("Ah", "7d"), ten, "hit", True, False, "casual") == "stand"
    assert npc_slips.blackjack(cards("Ah", "8d"), Card.from_code("4s"), "stand", True, False, "gambler") == "double"


def test_three_card_poker_slips_only_on_jack_or_queen_high():
    for hand in itertools.combinations(cards(*[r + s for r in RANKS for s in "hd"]), 3):
        ev = evaluate_three_card_hand(list(hand))
        play = tcp.should_play(ev)
        slip = npc_slips.three_card_poker(ev, play, False)
        if slip is not None:
            assert ev[0] == 1 and ev[2][0] in (11, 12)   # high card only: a pair or better is always played
        assert npc_slips.three_card_poker(ev, play, True) is None


def test_mississippi_never_folds_a_made_hand_or_jumps_to_3x():
    rng = random.Random(1)
    deck = cards(*[r + s for r in RANKS for s in SUITS])
    for _ in range(3000):
        seen = rng.sample(deck, rng.choice((2, 3, 4)))
        right = ms.strategy(seen)
        slip = npc_slips.mississippi(seen, right, rng)
        if ms._made(seen):
            assert slip is None
        if right == 0:
            assert slip in (1, None)
        if slip is not None:
            assert abs(slip - right) <= 2 and slip != right


def test_holdem_never_folds_a_hidden_pair_at_the_river():
    rng = random.Random(2)
    deck = cards(*[r + s for r in RANKS for s in SUITS])
    for _ in range(300):
        dealt = rng.sample(deck, 7)
        hole, board = dealt[:2], dealt[2:]
        right = bool(uth.river_bet(hole, board))
        slip = npc_slips.holdem(2, hole, board, right)
        if uth._hidden_pair_or_better(hole, board):
            assert slip is None
    assert npc_slips.holdem(0, cards("Ah", "Ad"), [], True) is None
    assert npc_slips.holdem(0, cards("7h", "2d"), [], False) is None
    assert npc_slips.holdem(0, cards("Kh", "4d"), [], False) is True


def test_let_it_ride_never_pulls_a_paying_hand():
    rng = random.Random(3)
    deck = cards(*[r + s for r in RANKS for s in SUITS])
    for _ in range(2000):
        stage = rng.choice((0, 1))
        seen = rng.sample(deck, 3 + stage)
        ride = lir.ride_first(seen) if stage == 0 else lir.ride_second(seen)
        slip = npc_slips.let_it_ride(seen, stage, ride, False)
        if lir._paying(seen):
            assert slip is None


def test_high_card_flush_never_folds_four_to_a_flush():
    rng = random.Random(4)
    deck = cards(*[r + s for r in RANKS for s in SUITS])
    for _ in range(2000):
        hand = rng.sample(deck, 7)
        times = hcf.raise_by(hand)
        slip = npc_slips.high_card_flush(hand, times, False)
        if hcf.best_flush(hand)[0] >= 4:
            assert slip is None
