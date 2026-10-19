"""
Hand evaluation utilities -- copied verbatim from Casino v2 (core/hand_evaluator.py).

Currently implements 3-card poker hand ranking. Kept in its own module,
separate from game flow/UI, so a future game that needs a different
evaluator (e.g. standard 5-card poker) can be added alongside this one
without touching Three Card Poker's logic.

3-card poker hand ranking (highest to lowest) -- note Flush outranks
Straight here, the opposite of 5-card poker, because there are fewer
possible 3-card flushes than 3-card straights:
    Straight Flush > Three of a Kind > Straight > Flush > Pair > High Card
"""
from collections import Counter
from typing import Optional, Tuple

# (rank_value, rank_name, tiebreaker_tuple) -- see evaluate_three_card_hand.
HandEval = Tuple[int, str, Tuple[int, ...]]

STRAIGHT_FLUSH = 6
THREE_OF_A_KIND = 5
STRAIGHT = 4
FLUSH = 3
PAIR = 2
HIGH_CARD = 1

HAND_NAMES = {
    STRAIGHT_FLUSH: "Straight Flush",
    THREE_OF_A_KIND: "Three of a Kind",
    STRAIGHT: "Straight",
    FLUSH: "Flush",
    PAIR: "Pair",
    HIGH_CARD: "High Card",
}

DEALER_QUALIFY_MIN_VALUE = 12  # Queen high or better qualifies the dealer


def _check_straight(values) -> Tuple[bool, Optional[int]]:
    """values: list of the 3 card numeric values. Returns (is_straight, high_card)
    -- high_card is only ever None when is_straight is False."""
    unique_values = sorted(set(values))
    if len(unique_values) != 3:
        return False, None
    if unique_values[2] - unique_values[1] == 1 and unique_values[1] - unique_values[0] == 1:
        return True, unique_values[2]
    # Ace-low straight: A-2-3 (Ace plays low here; the "high" card is the 3)
    if set(unique_values) == {14, 3, 2}:
        return True, 3
    return False, None


def evaluate_three_card_hand(cards) -> HandEval:
    """Returns (rank_value, rank_name, tiebreaker_tuple) for a 3-card hand.
    A hand with a higher rank_value wins; ties are broken by comparing
    tiebreaker_tuple element-by-element (higher wins)."""
    if len(cards) != 3:
        raise ValueError("Three card poker hands must contain exactly 3 cards.")

    values = sorted((c.value for c in cards), reverse=True)
    is_flush = len({c.suit for c in cards}) == 1
    is_straight, straight_high = _check_straight(values)
    counts = Counter(values)
    count_sizes = sorted(counts.values(), reverse=True)

    if is_straight and is_flush:
        assert straight_high is not None  # _check_straight always pairs True with a value
        return (STRAIGHT_FLUSH, HAND_NAMES[STRAIGHT_FLUSH], (straight_high,))
    if count_sizes[0] == 3:
        return (THREE_OF_A_KIND, HAND_NAMES[THREE_OF_A_KIND], (values[0],))
    if is_straight:
        assert straight_high is not None  # _check_straight always pairs True with a value
        return (STRAIGHT, HAND_NAMES[STRAIGHT], (straight_high,))
    if is_flush:
        return (FLUSH, HAND_NAMES[FLUSH], tuple(values))
    if count_sizes[0] == 2:
        pair_value = next(v for v, c in counts.items() if c == 2)
        kicker = next(v for v, c in counts.items() if c == 1)
        return (PAIR, HAND_NAMES[PAIR], (pair_value, kicker))
    return (HIGH_CARD, HAND_NAMES[HIGH_CARD], tuple(values))


def compare_hands(hand_eval_a: HandEval, hand_eval_b: HandEval) -> int:
    """Returns 1 if a beats b, -1 if b beats a, 0 for a tie."""
    rank_a, _, tie_a = hand_eval_a
    rank_b, _, tie_b = hand_eval_b
    if rank_a != rank_b:
        return 1 if rank_a > rank_b else -1
    if tie_a != tie_b:
        return 1 if tie_a > tie_b else -1
    return 0


def dealer_qualifies(dealer_eval: HandEval) -> bool:
    """Dealer qualifies with Queen-high or better."""
    rank_value, _, tiebreak = dealer_eval
    if rank_value > HIGH_CARD:
        return True  # a pair or anything stronger always qualifies
    return tiebreak[0] >= DEALER_QUALIFY_MIN_VALUE


# ---------------------------------------------------------------------------
# Standard 5-card poker hand ranking -- added for Pai Gow Poker (the "back"/
# 5-card hand, and the House Way setter that decides it), kept in its own
# section with its own rank scale rather than reusing the 3-card constants
# above: a 3-card Flush outranks a 3-card Straight (fewer 3-card flushes are
# possible), but the reverse is true at 5 cards, so the two scales genuinely
# can't be shared. `compare_hands`/`HandEval`'s own (rank, name, tiebreak)
# shape is generic over either scale and is reused as-is.
#
# Deliberately still knows nothing about Pai Gow Poker itself -- no Joker
# handling, no 7-card/best-of-7 search, no House Way. Those all live in
# games/pai_gow_poker/logic.py, built on top of this.
FIVE_CARD_STRAIGHT_FLUSH = 8
FOUR_OF_A_KIND = 7
FULL_HOUSE = 6
FIVE_CARD_FLUSH = 5
FIVE_CARD_STRAIGHT = 4
FIVE_CARD_THREE_OF_A_KIND = 3
TWO_PAIR = 2
ONE_PAIR = 1
FIVE_CARD_HIGH_CARD = 0

FIVE_CARD_HAND_NAMES = {
    FIVE_CARD_STRAIGHT_FLUSH: "Straight Flush",
    FOUR_OF_A_KIND: "Four of a Kind",
    FULL_HOUSE: "Full House",
    FIVE_CARD_FLUSH: "Flush",
    FIVE_CARD_STRAIGHT: "Straight",
    FIVE_CARD_THREE_OF_A_KIND: "Three of a Kind",
    TWO_PAIR: "Two Pair",
    ONE_PAIR: "One Pair",
    FIVE_CARD_HIGH_CARD: "High Card",
}


def _check_straight_five(values) -> Tuple[bool, Optional[int]]:
    """values: the 5 card numeric values (any order, may repeat). Returns
    (is_straight, high_card) -- high_card only ever None when is_straight is
    False. A straight needs 5 *distinct* ranks -- any repeat (which would
    already be a pair/trips/etc, ranked separately) rules it out immediately,
    same principle as the 3-card evaluator's own _check_straight."""
    unique_values = sorted(set(values))
    if len(unique_values) != 5:
        return False, None
    if unique_values[-1] - unique_values[0] == 4:
        return True, unique_values[-1]
    # Ace-low "wheel": A-2-3-4-5 (Ace plays low; the "high" card is the 5) --
    # the lowest straight, per the rules doc this was built against.
    if set(unique_values) == {14, 2, 3, 4, 5}:
        return True, 5
    return False, None


def evaluate_five_card_hand(cards) -> HandEval:
    """Returns (rank_value, rank_name, tiebreaker_tuple) for a standard
    5-card poker hand -- Straight Flush > Four of a Kind > Full House >
    Flush > Straight > Three of a Kind > Two Pair > One Pair > High Card.
    Every card must have a real suit (no Joker) -- callers needing Joker
    support (Pai Gow Poker) resolve it to a real substitute card first."""
    if len(cards) != 5:
        raise ValueError("Five card poker hands must contain exactly 5 cards.")

    values = sorted((c.value for c in cards), reverse=True)
    is_flush = len({c.suit for c in cards}) == 1
    is_straight, straight_high = _check_straight_five(values)
    counts = Counter(values)
    # Highest count first; among equal counts, the higher-value group first
    # (e.g. distinguishes Kings-full-of-Twos from Twos-full-of-Kings).
    by_count = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    count_sizes = [c for _, c in by_count]

    if is_straight and is_flush:
        assert straight_high is not None
        return (FIVE_CARD_STRAIGHT_FLUSH, FIVE_CARD_HAND_NAMES[FIVE_CARD_STRAIGHT_FLUSH], (straight_high,))
    if count_sizes[0] == 4:
        quad_value = by_count[0][0]
        kicker = by_count[1][0]
        return (FOUR_OF_A_KIND, FIVE_CARD_HAND_NAMES[FOUR_OF_A_KIND], (quad_value, kicker))
    if count_sizes[0] == 3 and count_sizes[1] == 2:
        return (FULL_HOUSE, FIVE_CARD_HAND_NAMES[FULL_HOUSE], (by_count[0][0], by_count[1][0]))
    if is_flush:
        return (FIVE_CARD_FLUSH, FIVE_CARD_HAND_NAMES[FIVE_CARD_FLUSH], tuple(values))
    if is_straight:
        assert straight_high is not None
        return (FIVE_CARD_STRAIGHT, FIVE_CARD_HAND_NAMES[FIVE_CARD_STRAIGHT], (straight_high,))
    if count_sizes[0] == 3:
        trip_value = by_count[0][0]
        kickers = tuple(v for v, c in by_count[1:])
        return (FIVE_CARD_THREE_OF_A_KIND, FIVE_CARD_HAND_NAMES[FIVE_CARD_THREE_OF_A_KIND], (trip_value,) + kickers)
    if count_sizes[0] == 2 and count_sizes[1] == 2:
        # by_count is already sorted (count, then value) descending, so the
        # higher pair leads and the kicker trails, no further sorting needed.
        return (TWO_PAIR, FIVE_CARD_HAND_NAMES[TWO_PAIR], (by_count[0][0], by_count[1][0], by_count[2][0]))
    if count_sizes[0] == 2:
        pair_value = by_count[0][0]
        kickers = tuple(v for v, c in by_count[1:])
        return (ONE_PAIR, FIVE_CARD_HAND_NAMES[ONE_PAIR], (pair_value,) + kickers)
    return (FIVE_CARD_HIGH_CARD, FIVE_CARD_HAND_NAMES[FIVE_CARD_HIGH_CARD], tuple(values))
