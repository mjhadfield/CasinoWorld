"""
NPC slips: the mistakes a real player might make, so the regulars don't all play
the chart perfectly but nobody does anything daft. npc.py rolls a punter's
mistake chance (roster.profile) and, where one of these returns a play, makes it;
where it returns None the decision is clear-cut and they play it right.

Blackjack slips depend on the archetype:
  Casual   timid: stands on a stiff against a high card, hits 12 against a 4-6,
           hits instead of doubling, stands on a soft 17/18 against a 9-A,
           doesn't split (8s against a 10 or Ace stand on 16)
  Gambler  reckless: splits 10s against a 5 or 6, doubles a soft 19 against a
           3-5 or a hard 8 against a 5 or 6
Never: hit a hard 17+, stand on 11 or less, double a hard 12+, split 5s, or play
a pair of Aces as anything but a split.

The other games slip only on close calls, either way, and never fold or pull a
hand that already pays (a Gambler, who plays on with anything, doesn't slip there).
"""
from collections import Counter

from casino_server.engines import blackjack as bj
from casino_server.engines import high_card_flush as hcf
from casino_server.engines import let_it_ride as lir
from casino_server.engines import mississippi_stud as ms
from casino_server.engines import ultimate_texas_holdem as uth
from casino_server.engines.hand_evaluator import HIGH_CARD, ONE_PAIR

# How often a punter takes insurance (or even money) without a count behind it
INSURANCE = {"grinder": 0.0, "casual": 0.15, "gambler": 0.08}


def blackjack(cards, up, right: str, can_double: bool, can_split: bool, archetype: str) -> str | None:
    total, soft = bj.hand_value(cards)
    u = bj.card_value(up)
    two = len(cards) == 2
    if archetype == "gambler":
        if two and can_split and bj.card_value(cards[0]) == bj.card_value(cards[1]) == 10 and u in (5, 6):
            return "split"
        if two and can_double and right == "stand" and soft and total == 19 and 3 <= u <= 5:
            return "double"
        if two and can_double and right == "hit" and not soft and total == 8 and u in (5, 6):
            return "double"
        return None
    if archetype != "casual":
        return None
    if right == "split":
        if cards[0].rank == "A":
            return None
        alt = bj.recommend(cards, up, can_double, False)
        return "stand" if alt == "hit" and total >= 12 else alt
    if right == "double":
        return "stand" if soft and total >= 18 else "hit"
    if soft:
        return "stand" if total in (17, 18) and right == "hit" else None
    if 12 <= total <= 16:
        if right == "hit" and u >= 7:
            return "stand"     # "I don't want to bust"
        if right == "stand" and total == 12 and 4 <= u <= 6:
            return "hit"
    return None


def three_card_poker(hand_eval, play: bool, aggressive: bool) -> bool | None:
    """A Jack- or Queen-high hand, either side of Q-6-4."""
    if aggressive or hand_eval[0] != HIGH_CARD or hand_eval[2][0] not in (11, 12):
        return None
    return not play


def mississippi_backs(seen) -> bool:
    """A hand someone would push to 3x though the chart says 1x: anything before 5th Street; on 5th Street
    (four cards seen) only a low pair, an open-ended straight draw or three high cards -- never a gutshot
    or a couple of picture cards."""
    if len(seen) < 4:
        return True
    values = [c.value for c in seen]
    open_ended = len(set(values)) == 4 and ms._gaps(values) == 0 and ms.ACE not in values
    return ms._low_pair(seen) or open_ended or sum(v >= 11 for v in values) >= 3


def mississippi(seen, raise_by: int, rng) -> int | None:
    """One step off the chart (never 3x on a hand the chart folds, or on a 5th Street hand nobody would
    back), and a made hand is always played right."""
    if ms._made(seen):
        return None
    if raise_by == 3:
        return 1
    if raise_by == 1:
        return rng.choice((0, 3)) if mississippi_backs(seen) else 0
    return 1 if ms.points(seen) else None


def holdem(stage: int, hole, board, right: bool) -> bool | None:
    """Before the flop, hands near the line (J/Q/K-high, a weak Ace, a small pair); on the flop, one pair; after
    the river, a hand without a hidden pair or a made straight or flush whose dealer outs are near the 21 line."""
    if stage == 0:
        a, b = sorted((c.value for c in hole), reverse=True)
        close = a <= 5 if a == b else a in (11, 12, 13) or (a == uth.ACE and b <= 5)
    elif stage == 1:
        close = uth.best_hand(list(hole) + list(board))[0][0] == ONE_PAIR
    else:
        ev, _ = uth.best_hand(list(hole) + list(board))
        if uth._hidden_pair_or_better(hole, board) or ev[0] >= uth.FIVE_CARD_STRAIGHT:
            return None
        close = 14 <= uth.dealer_outs(hole, board) < 28
    return not right if close else None


def let_it_ride(seen, stage: int, ride: bool, aggressive: bool) -> bool | None:
    """Pulls a draw the chart rides, or rides a small pair or a near-draw. A paying hand always rides."""
    if aggressive or lir._paying(seen):
        return None
    if ride:
        return False
    values = [c.value for c in seen]
    small_pair = any(n == 2 for n in Counter(values).values())
    if stage == 0:
        close = small_pair or len({c.suit for c in seen}) == 1
    else:
        close = small_pair or (len(set(values)) == 4 and lir._straight_spread(values) is not None)
    return True if close else None


def high_card_flush(cards, times: int, aggressive: bool) -> int | None:
    """A 3-card flush 9- to Jack-high, either side of 10-8-6. A 4+ card flush is always raised."""
    if aggressive:
        return None
    length, values, _ = hcf.best_flush(cards)
    if length != 3 or values[0] not in (9, 10, 11):
        return None
    return 0 if times else hcf.max_raise(3)
