"""
Let It Ride engine, ported from Casino v2's games/let_it_ride/logic.py.

Same rules and paytables as v2, with these changes:
  - Money is integer pence; a Jackpot share is a fraction the table takes
    from the pool (Jackpot.take).
  - A table deals every seat three cards from one deck, with the dealer's two
    community cards shared by everyone.
  - NPC play: the Wizard of Odds' strategy (`ride_first`, `ride_second`),
    which v2 didn't have.

The game: three equal bets (1, 2 and $). After seeing their three cards a
player may pull back bet 1; after the first community card, bet 2; the $
always plays. The final hand is the player's three cards plus the two
community cards, and every bet still up pays the same, on a pair of 10s or
better: Royal 500:1, Straight Flush 100:1, Quads 25:1, Full House 15:1,
Flush 10:1, Straight 5:1, Trips 3:1, Two Pair 2:1, 10s or better 1:1.
Side bets: the £1 Bonus on the final hand (Royal 10,000:1, Straight Flush
2,000:1, Quads 400:1, Full House 200:1, Flush 50:1, Straight 25:1, Trips
5:1); the 3 Card Bonus on the player's own three cards (Straight Flush 40:1,
Trips 30:1, Straight 6:1, Flush 4:1, Pair 1:1); and the £1 Jackpot on the
final hand (Royal 100% of the pool, Straight Flush 10%, Quads £300, Full
House £50, Flush £40, Straight £30, Trips £9).
"""
from collections import Counter
from dataclasses import dataclass

from casino_server.engines.hand_evaluator import (
    FIVE_CARD_FLUSH, FIVE_CARD_STRAIGHT, FIVE_CARD_STRAIGHT_FLUSH, FIVE_CARD_THREE_OF_A_KIND, FLUSH, FOUR_OF_A_KIND,
    FULL_HOUSE, ONE_PAIR, PAIR, STRAIGHT, STRAIGHT_FLUSH, THREE_OF_A_KIND, TWO_PAIR,
    evaluate_five_card_hand, evaluate_three_card_hand,
)

GAME_KEY = "let_it_ride"
GAME_LABEL = "Let It Ride"
BASE_SPOTS = ("bet1", "bet2", "ante")   # 1, 2 and $
BONUS_BET = JACKPOT_BET = 100

BASE_PAYS = {"royal_flush": 500, "straight_flush": 100, "four_of_a_kind": 25, "full_house": 15, "flush": 10,
             "straight": 5, "three_of_a_kind": 3, "two_pair": 2, "pair_tens_or_better": 1}
BONUS_PAYS = {"royal_flush": 10_000, "straight_flush": 2_000, "four_of_a_kind": 400, "full_house": 200,
              "flush": 50, "straight": 25, "three_of_a_kind": 5}
THREE_CARD_PAYS = {"straight_flush": 40, "three_of_a_kind": 30, "straight": 6, "flush": 4, "pair": 1}
JACKPOT_FIXED = {"four_of_a_kind": 30_000, "full_house": 5_000, "flush": 4_000, "straight": 3_000,
                 "three_of_a_kind": 900}
JACKPOT_STRAIGHT_FLUSH_SHARE = 0.10
TIER_LABELS = {"royal_flush": "Royal Flush", "straight_flush": "Straight Flush", "four_of_a_kind": "Four of a Kind",
               "full_house": "Full House", "flush": "Flush", "straight": "Straight",
               "three_of_a_kind": "Three of a Kind", "two_pair": "Two Pair", "pair_tens_or_better": "10s or better",
               "low_pair": "Low pair", "high_card": "No pair"}


def five_card_tier(ev) -> str:
    rank, _, tiebreak = ev
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return "royal_flush" if tiebreak[0] == 14 else "straight_flush"
    return {FOUR_OF_A_KIND: "four_of_a_kind", FULL_HOUSE: "full_house", FIVE_CARD_FLUSH: "flush",
            FIVE_CARD_STRAIGHT: "straight", FIVE_CARD_THREE_OF_A_KIND: "three_of_a_kind",
            TWO_PAIR: "two_pair"}.get(rank) or \
        ("pair_tens_or_better" if rank == ONE_PAIR and tiebreak[0] >= 10 else "low_pair" if rank == ONE_PAIR
         else "high_card")


def three_card_tier(ev) -> str:
    return {STRAIGHT_FLUSH: "straight_flush", THREE_OF_A_KIND: "three_of_a_kind", STRAIGHT: "straight",
            FLUSH: "flush", PAIR: "pair"}.get(ev[0], "high_card")


def jackpot_payout(tier: str) -> tuple[int, float]:
    if tier == "royal_flush":
        return 0, 1.0
    if tier == "straight_flush":
        return 0, JACKPOT_STRAIGHT_FLUSH_SHARE
    return JACKPOT_FIXED.get(tier, 0), 0.0


def hand_label(ev) -> str:
    tier = five_card_tier(ev)
    if tier in ("pair_tens_or_better", "low_pair"):
        v = ev[2][0]
        return "Pair of " + {14: "Aces", 13: "Kings", 12: "Queens", 11: "Jacks"}.get(v, f"{v}s")
    return TIER_LABELS[tier]


@dataclass
class Bets:
    unit: int                 # each of 1, 2 and $
    bonus: int = 0
    three_card: int = 0
    jackpot: int = 0
    bet1: bool = True         # still up (not pulled back)
    bet2: bool = True


@dataclass
class Result:
    tier: str
    three_tier: str | None
    qualified: bool
    multiplier: int
    base_returns: dict        # spot -> return, for the spots still up
    bonus_return: int = 0
    three_card_return: int = 0
    jackpot_fixed: int = 0
    jackpot_share: float = 0.0

    @property
    def total_returned(self) -> int:
        return sum(self.base_returns.values()) + self.bonus_return + self.three_card_return + self.jackpot_fixed


def settle(cards, community, bets: Bets) -> Result:
    tier = five_card_tier(evaluate_five_card_hand(list(cards) + list(community)))
    m = BASE_PAYS.get(tier, 0)
    up = ["ante"] + (["bet1"] if bets.bet1 else []) + (["bet2"] if bets.bet2 else [])
    base = {spot: bets.unit * (m + 1) if m else 0 for spot in up}
    r = Result(tier, None, m > 0, m, base)
    if bets.bonus:
        b = BONUS_PAYS.get(tier, 0)
        r.bonus_return = bets.bonus * (b + 1) if b else 0
    if bets.three_card:
        r.three_tier = three_card_tier(evaluate_three_card_hand(list(cards)))
        t = THREE_CARD_PAYS.get(r.three_tier, 0)
        r.three_card_return = bets.three_card * (t + 1) if t else 0
    if bets.jackpot:
        r.jackpot_fixed, r.jackpot_share = jackpot_payout(tier)
    return r


# ---------------------------------------------------------------------- strategy
# The Wizard of Odds' strategy for Let It Ride.
def _straight_spread(values) -> tuple[int, int] | None:
    """(spread, high card count) for distinct ranks that fit in one straight
    -- spread is highest minus lowest + 1 (an Ace may play low); None if not."""
    best = None
    for vals in (values, [1 if v == 14 else v for v in values]):
        vals = sorted(set(vals))
        if len(vals) != len(values) or vals[-1] - vals[0] > 4:
            continue
        spread = vals[-1] - vals[0] + 1
        if best is None or spread < best:
            best = spread
    return best


def _paying(cards) -> bool:
    counts = Counter(c.value for c in cards)
    pairs = [v for v, n in counts.items() if n >= 2]
    return any(n >= 3 for n in counts.values()) or len(pairs) >= 2 or any(v >= 10 for v in pairs)


def ride_first(cards) -> bool:
    """After three cards: let it ride with a paying hand (10s or better, trips);
    three to a royal flush; three suited in a row (not 2-3-4 or A-2-3); three to
    a straight flush with a spread of 4 and a high card (10+), or a spread of 5
    and two high cards."""
    if _paying(cards):
        return True
    values = [c.value for c in cards]
    if len({c.suit for c in cards}) != 1 or len(set(values)) != 3:
        return False
    high = sum(v >= 10 for v in values)
    if all(v >= 10 for v in values):
        return True  # three to a royal
    spread = _straight_spread(values)
    if spread == 3:
        return sorted(values) not in ([2, 3, 4], [2, 3, 14])
    if spread == 4:
        return high >= 1
    if spread == 5:
        return high >= 2
    return False


def ride_second(cards) -> bool:
    """After four cards: let it ride with a paying hand; four to a flush; four to
    an outside straight; four to an inside straight with four high cards (10+)."""
    if _paying(cards):
        return True
    if len({c.suit for c in cards}) == 1:
        return True
    values = [c.value for c in cards]
    if len(set(values)) != 4:
        return False
    spread = _straight_spread(values)
    if spread == 4 and 14 not in values:
        return True  # outside straight (open at both ends)
    if spread is not None and all(v >= 10 for v in values):
        return True  # inside straight, all high cards (J-Q-K-A included)
    return False


# ---------------------------------------------------------------------- paytable
def rules() -> dict:
    lab = TIER_LABELS
    return {"game": GAME_KEY, "title": GAME_LABEL,
            "sections": [{"title": "Every bet still up", "rows": [[lab[t], f"{m:,}:1"] for t, m in BASE_PAYS.items()]},
                         {"title": "Bonus (£1)", "rows": [[lab[t], f"{m:,}:1"] for t, m in BONUS_PAYS.items()]},
                         {"title": "3 Card Bonus", "rows": [[("Pair" if t == "pair" else lab[t]), f"{m}:1"]
                                                           for t, m in THREE_CARD_PAYS.items()]},
                         {"title": "Jackpot (£1)", "rows": [["Royal Flush", "100%"],
                                                           ["Straight Flush", "10%"]] +
                          [[lab[t], f"£{p // 100:,}"] for t, p in JACKPOT_FIXED.items()]}],
            "notes": ["Three equal bets: 1, 2 and $. You get three cards; two community cards are turned one at a time.",
                      "After your three cards you may pull back bet 1; after the first community card, bet 2.",
                      "The $ always plays. Your three cards plus the two community cards make your hand.",
                      "A pair of 10s or better pays every bet still up."]}
