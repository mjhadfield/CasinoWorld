"""
Mississippi Stud engine, ported from Casino v2's games/mississippi_stud/logic.py.

Same rules and paytables as v2, with three changes:
  - Money is integer pence (v2 used float pounds); a Jackpot share is a
    fraction the table takes from the pool (Jackpot.take).
  - A table deals every seat two cards from one deck, with one set of three
    community cards for everyone; v2 dealt one player.
  - NPC play: Joseph Kisenwether's strategy (`strategy`), which v2 didn't have.

The game: an Ante deals each player 2 cards; 3 community cards are dealt face
down. On 3rd, 4th and 5th Street each player folds or bets 1x, 2x or 3x the
Ante, and after each street the dealer turns the next community card. A fold
forfeits the Ante and every street bet so far. The final hand is the player's
2 cards plus the 3 community cards, and every bet still in play pays the same
multiplier:
    Royal Flush 500:1, Straight Flush 100:1, Four of a Kind 40:1,
    Full House 10:1, Flush 6:1, Straight 4:1, Three of a Kind 3:1,
    Two Pair 2:1, Jacks or better 1:1, a Pair of 6s-10s pushes.
3 Card Bonus (on the 3 community cards alone, still in action after a fold):
    Mini-Royal (A-K-Q suited) 50:1, Straight Flush 40:1, Three of a Kind 30:1,
    Straight 6:1, Flush 3:1, Pair 1:1.
£1 Jackpot (on the final hand; never after a fold): Royal Flush 100% of the
pool, Straight Flush 10% of it, Four of a Kind £300, Full House £50,
Flush £40, Straight £30, Three of a Kind £9.
"""
from collections import Counter
from dataclasses import dataclass, field

from casino_server.engines.hand_evaluator import (
    FIVE_CARD_FLUSH, FIVE_CARD_HIGH_CARD, FIVE_CARD_STRAIGHT, FIVE_CARD_STRAIGHT_FLUSH, FIVE_CARD_THREE_OF_A_KIND,
    FLUSH, FOUR_OF_A_KIND, FULL_HOUSE, ONE_PAIR, PAIR, STRAIGHT, STRAIGHT_FLUSH, THREE_OF_A_KIND, TWO_PAIR,
    evaluate_five_card_hand, evaluate_three_card_hand,
)

GAME_KEY = "mississippi_stud"
GAME_LABEL = "Mississippi Stud"
STREETS = ("third", "fourth", "fifth")
JACKPOT_BET = 100  # £1, flat

MAIN_PAYTABLE = {FOUR_OF_A_KIND: 40, FULL_HOUSE: 10, FIVE_CARD_FLUSH: 6, FIVE_CARD_STRAIGHT: 4,
                 FIVE_CARD_THREE_OF_A_KIND: 3, TWO_PAIR: 2}
STRAIGHT_FLUSH_PAYS, ROYAL_FLUSH_PAYS, JACKS_OR_BETTER_PAYS = 100, 500, 1
JACKS = 11      # a pair of these or better wins...
PUSH_PAIR = 6   # ...a pair of 6s-10s pushes; lower loses

BONUS_PAYTABLE = {THREE_OF_A_KIND: 30, STRAIGHT: 6, FLUSH: 3, PAIR: 1}
BONUS_STRAIGHT_FLUSH, BONUS_MINI_ROYAL = 40, 50

JACKPOT_FIXED = {FOUR_OF_A_KIND: 30_000, FULL_HOUSE: 5_000, FIVE_CARD_FLUSH: 4_000,
                 FIVE_CARD_STRAIGHT: 3_000, FIVE_CARD_THREE_OF_A_KIND: 900}
JACKPOT_STRAIGHT_FLUSH_SHARE = 0.10
ACE = 14


def is_royal(ev) -> bool:
    return ev[0] == FIVE_CARD_STRAIGHT_FLUSH and ev[2][0] == ACE


def main_multiplier(ev) -> tuple[int, str]:
    """(multiplier, "win" | "push" | "lose") for a final 5-card hand."""
    rank, _, tiebreak = ev
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return (ROYAL_FLUSH_PAYS if is_royal(ev) else STRAIGHT_FLUSH_PAYS), "win"
    if rank == ONE_PAIR:
        if tiebreak[0] >= JACKS:
            return JACKS_OR_BETTER_PAYS, "win"
        return 0, ("push" if tiebreak[0] >= PUSH_PAIR else "lose")
    if rank in MAIN_PAYTABLE:
        return MAIN_PAYTABLE[rank], "win"
    return 0, "lose"


def bonus_multiplier(ev3) -> int:
    """The 3 Card Bonus multiplier for the community cards (0: it loses)."""
    if ev3[0] == STRAIGHT_FLUSH:
        return BONUS_MINI_ROYAL if ev3[2][0] == ACE else BONUS_STRAIGHT_FLUSH
    return BONUS_PAYTABLE.get(ev3[0], 0)


def jackpot_payout(ev) -> tuple[int, float]:
    """(fixed pence, share of the pool) for the £1 Jackpot on a final hand.
    A share of 1.0 is the whole pool (the table resets it)."""
    if ev[0] == FIVE_CARD_STRAIGHT_FLUSH:
        return (0, 1.0) if is_royal(ev) else (0, JACKPOT_STRAIGHT_FLUSH_SHARE)
    return JACKPOT_FIXED.get(ev[0], 0), 0.0


def hand_label(ev) -> str:
    """'Royal Flush', 'Pair of Queens', 'King high' -- for the felt and the dealer."""
    names = {14: "Aces", 13: "Kings", 12: "Queens", 11: "Jacks"}
    rank, name, tiebreak = ev
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return "Royal Flush" if is_royal(ev) else "Straight Flush"
    if rank == ONE_PAIR:
        return f"Pair of {names.get(tiebreak[0], str(tiebreak[0]) + 's')}"
    if rank == FIVE_CARD_HIGH_CARD:
        high = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}.get(tiebreak[0], str(tiebreak[0]))
        return f"{high} high"
    return name


def bonus_label(ev3) -> str:
    if ev3[0] == STRAIGHT_FLUSH and ev3[2][0] == ACE:
        return "Mini-Royal"
    return ev3[1]


@dataclass
class Bets:
    ante: int
    bonus: int = 0
    jackpot: int = 0
    streets: list = field(default_factory=lambda: [0, 0, 0])  # 3rd, 4th, 5th Street, as played


@dataclass
class Result:
    outcome: str                 # win | push | lose | fold
    final_eval: tuple | None     # None after a fold
    bonus_eval: tuple | None     # None without a Bonus bet
    multiplier: int = 0
    main_return: int = 0         # Ante + street bets back (stakes included)
    ante_return: int = 0
    street_returns: list = field(default_factory=lambda: [0, 0, 0])
    bonus_return: int = 0
    jackpot_fixed: int = 0       # a fixed Jackpot payout...
    jackpot_share: float = 0.0   # ...or this share of the pool (1.0: all of it)

    @property
    def total_returned(self) -> int:  # the Jackpot share is added by the table, which knows the pool
        return self.main_return + self.bonus_return + self.jackpot_fixed


def settle(hole, community, bets: Bets, folded: bool) -> Result:
    """Every bet's return. The Bonus is settled on the community cards whether
    or not the hand was folded; the Jackpot only on a hand played to the end."""
    bonus_eval = evaluate_three_card_hand(community) if bets.bonus else None
    bonus_return = 0
    if bonus_eval is not None:
        m = bonus_multiplier(bonus_eval)
        bonus_return = bets.bonus * (m + 1) if m else 0
    if folded:
        return Result("fold", None, bonus_eval, bonus_return=bonus_return)
    final = evaluate_five_card_hand(list(hole) + list(community))
    multiplier, outcome = main_multiplier(final)
    factor = multiplier + 1 if outcome == "win" else 1 if outcome == "push" else 0
    ante_return = bets.ante * factor
    street_returns = [b * factor for b in bets.streets]
    fixed, share = jackpot_payout(final) if bets.jackpot else (0, 0.0)
    return Result(outcome, final, bonus_eval, multiplier, ante_return + sum(street_returns), ante_return,
                  street_returns, bonus_return, fixed, share)


# ---------------------------------------------------------------------- strategy
# Joseph Kisenwether's strategy. Card points: J-A 2, 6-10 1, 2-5 0.
def points(cards) -> int:
    return sum(2 if c.value >= 11 else 1 if c.value >= 6 else 0 for c in cards)


def _gaps(values) -> int | None:
    """For distinct ranks that fit inside one 5-card straight, how many ranks
    are missing between the lowest and highest (an Ace may play low); None if
    they can't make a straight together."""
    best = None
    for vals in (values, [1 if v == ACE else v for v in values]):
        vals = sorted(set(vals))
        if len(vals) != len(values):
            continue
        span = vals[-1] - vals[0]
        if span <= 4:
            gaps = span - (len(vals) - 1)
            best = gaps if best is None else min(best, gaps)
    return best


def _low_card(values) -> int:
    """The lowest rank of a straight draw (an Ace counts low only in a wheel draw)."""
    if ACE in values and max(v for v in values if v != ACE) <= 5:
        return 1
    return min(values)


def _made(cards) -> bool:
    """A pair of 6s or better, two pair, trips or better -- the hand already pays or pushes."""
    counts = Counter(c.value for c in cards)
    pairs = [v for v, n in counts.items() if n >= 2]
    return any(n >= 3 for n in counts.values()) or len(pairs) >= 2 or any(v >= PUSH_PAIR for v in pairs)


def _low_pair(cards) -> bool:
    counts = Counter(c.value for c in cards)
    return any(n == 2 and v < PUSH_PAIR for v, n in counts.items())


def strategy(cards, raised_3x_before: bool = False) -> int:
    """Kisenwether's raise for the cards seen so far -- 2 (3rd Street), 3 (4th)
    or 4 (5th): 3 (bet 3x), 1 (bet 1x) or 0 (fold). `raised_3x_before` is
    whether this hand has already bet 3x on an earlier street."""
    values = [c.value for c in cards]
    suited = len({c.suit for c in cards}) == 1
    distinct = len(set(values)) == len(values)
    pts = points(cards)
    high = sum(v >= 11 for v in values)
    mid = sum(6 <= v <= 10 for v in values)
    if len(cards) == 2:
        if values[0] == values[1]:
            return 3
        if pts >= 2:
            return 1
        if suited and sorted(values) == [5, 6]:
            return 1
        return 0
    if len(cards) == 3:
        if _made(cards):
            return 3
        gaps = _gaps(values) if distinct else None
        if suited and distinct:
            if all(v >= 10 for v in values):
                return 3  # royal flush draw
            if gaps is not None:
                if gaps == 0 and _low_card(values) >= 5:
                    return 3
                if gaps == 1 and high >= 1:
                    return 3
                if gaps == 2 and high >= 2:
                    return 3
            return 1  # any other three suited cards
        if _low_pair(cards) or pts >= 3:
            return 1
        if gaps == 0 and _low_card(values) >= 4:
            return 1
        if gaps == 1 and mid >= 2:
            return 1
        return 0
    if len(cards) == 4:
        if _made(cards):
            return 3
        if suited:
            return 3  # four to a flush
        gaps = _gaps(values) if distinct else None
        if gaps == 0 and ACE not in values and 8 <= max(values) <= 13:
            return 3  # four to an outside straight, 8 high or better
        if gaps is not None:
            return 1  # any other straight draw
        if _low_pair(cards) or pts >= 4:
            return 1
        if mid >= 3 and raised_3x_before:
            return 1
        return 0
    raise ValueError("Strategy is for 2, 3 or 4 cards.")


# ---------------------------------------------------------------------- paytable
def rules() -> dict:
    names = {FOUR_OF_A_KIND: "Four of a Kind", FULL_HOUSE: "Full House", FIVE_CARD_FLUSH: "Flush",
             FIVE_CARD_STRAIGHT: "Straight", FIVE_CARD_THREE_OF_A_KIND: "Three of a Kind", TWO_PAIR: "Two Pair"}
    main = [["Royal Flush", "500 to 1"], ["Straight Flush", "100 to 1"]] \
        + [[names[r], f"{m} to 1"] for r, m in MAIN_PAYTABLE.items()] \
        + [["Jacks or better", "1 to 1"], ["Pair of 6s-10s", "Push"]]
    bonus = [["Mini-Royal (A-K-Q suited)", "50 to 1"], ["Straight Flush", "40 to 1"], ["Three of a Kind", "30 to 1"],
             ["Straight", "6 to 1"], ["Flush", "3 to 1"], ["Pair", "1 to 1"]]
    jackpot = [["Royal Flush", "100% of the Jackpot"], ["Straight Flush", "10% of the Jackpot"]] \
        + [[names[r], f"£{p // 100:,}"] for r, p in JACKPOT_FIXED.items()]
    return {"game": GAME_KEY, "title": GAME_LABEL,
            "sections": [{"title": "Every bet in play", "rows": main},
                         {"title": "3 Card Bonus", "rows": bonus},
                         {"title": "Jackpot (£1)", "rows": jackpot}],
            "notes": ["You get 2 cards; 3 community cards are turned one at a time.",
                      "On 3rd, 4th and 5th Street: fold, or bet 1x, 2x or 3x your Ante.",
                      "Your 2 cards plus the 3 community cards make your hand; every bet in play pays the same.",
                      "Folding loses your Ante and street bets, and the Jackpot.",
                      "The 3 Card Bonus pays on the community cards alone, even if you fold."]}
