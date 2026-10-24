"""
High Card Flush engine, ported from Casino v2's games/high_card_flush/logic.py.

Same rules and paytables as v2, with these changes:
  - Money is integer pence; a Jackpot share is a fraction the table takes
    from the pool (Jackpot.take).
  - A table deals every seat seven cards from one deck, with one dealer hand.
  - NPC play: Mousseau's near-optimal strategy (`raise_by`), which v2 didn't have.

The game: a hand's strength is its longest flush -- more cards in one suit
always wins; equal length compares the flush cards high to low. After seeing
their seven cards a player folds (losing the Ante) or raises: 1x the Ante,
or up to 2x with a 5-card flush and 3x with 6 or 7. The dealer qualifies
with a 3-card flush, 9-high or better (any 4+ card flush qualifies):
  - Dealer doesn't qualify: the Ante pays 1:1, the Raise pushes.
  - Otherwise: a win pays both 1:1, a loss loses both, a tie pushes both.
Side bets, on the player's own seven cards and paid even after a fold:
  Flush: 7 cards 250:1, 6 100:1, 5 10:1, 4 1:1.
  Straight Flush: 7 cards 500:1, 6 200:1, 5 100:1, 4 60:1, 3 8:1.
  £1 Jackpot (on the straight flush length): 7 cards 100% of the pool,
  6 cards 50% of it, 5 £250, 4 £50, 3 £5.
"""
from collections import defaultdict
from dataclasses import dataclass

from casino_server.engines.cards import Suit

GAME_KEY = "high_card_flush"
GAME_LABEL = "High Card Flush"
JACKPOT_BET = 100
FLUSH_PAYS = {7: 250, 6: 100, 5: 10, 4: 1}
STRAIGHT_FLUSH_PAYS = {7: 500, 6: 200, 5: 100, 4: 60, 3: 8}
JACKPOT_FIXED = {5: 25_000, 4: 5_000, 3: 500}
JACKPOT_SHARES = {7: 1.0, 6: 0.5}
NAMES = {14: "A", 13: "K", 12: "Q", 11: "J"}


def best_flush(cards) -> tuple[int, tuple, list]:
    """(length, values high to low, the cards) of the best one-suit group."""
    by_suit = defaultdict(list)
    for c in cards:
        by_suit[c.suit].append(c)
    best_key, best_cards = (-1, ()), []
    for suited in by_suit.values():
        ordered = sorted(suited, key=lambda c: c.value, reverse=True)
        key = (len(ordered), tuple(c.value for c in ordered))
        if key > best_key:
            best_key, best_cards = key, ordered
    return best_key[0], best_key[1], best_cards


def best_straight_flush(cards) -> int:
    """The longest run of consecutive ranks in one suit (an Ace may play low)."""
    best = 0
    for suit in Suit:
        values = {c.value for c in cards if c.suit == suit}
        if 14 in values:
            values.add(1)
        run = 0
        for v in range(1, 15):
            run = run + 1 if v in values else 0
            best = max(best, run)
    return best


def straight_flush_cards(cards, skip_suit=None) -> list:
    """The cards of the longest one-suit run (an Ace may play low), leaving out
    `skip_suit` if given; [] for none."""
    best: list = []
    for suit in Suit:
        if suit == skip_suit:
            continue
        by_value = {c.value: c for c in cards if c.suit == suit}
        if 14 in by_value:
            by_value[1] = by_value[14]
        run: list = []
        for v in range(1, 15):
            if v in by_value:
                run.append(by_value[v])
                if len(run) > len(best):
                    best = list(run)
            else:
                run = []
    return best


def dealer_qualifies(length: int, top: int) -> bool:
    return length > 3 or (length == 3 and top >= 9)


def max_raise(length: int) -> int:
    return 3 if length >= 6 else 2 if length == 5 else 1


def flush_label(length: int, values: tuple) -> str:
    if length <= 1:
        return "No flush"
    return f"{length}-card flush, " + "-".join(NAMES.get(v, str(v)) for v in values[:3]) + ("..." if length > 3 else "")


@dataclass
class Bets:
    ante: int
    flush: int = 0
    straight_flush: int = 0
    jackpot: int = 0
    raise_bet: int = 0


@dataclass
class Result:
    outcome: str                  # win | lose | push | no_qualify | fold
    flush: tuple                  # (length, values)
    dealer_flush: tuple
    dealer_qualified: bool
    straight_flush: int
    ante_return: int = 0
    raise_return: int = 0
    flush_return: int = 0
    straight_flush_return: int = 0
    jackpot_fixed: int = 0
    jackpot_share: float = 0.0

    @property
    def total_returned(self) -> int:
        return self.ante_return + self.raise_return + self.flush_return + self.straight_flush_return + self.jackpot_fixed


def settle(cards, dealer, bets: Bets, folded: bool) -> Result:
    length, values, _ = best_flush(cards)
    d_length, d_values, _ = best_flush(dealer)
    qualified = dealer_qualifies(d_length, d_values[0] if d_values else 0)
    sf = best_straight_flush(cards)
    r = Result("fold", (length, values), (d_length, d_values), qualified, sf)
    if not folded:
        mine, theirs = (length, values), (d_length, d_values)
        if not qualified:
            r.outcome, r.ante_return, r.raise_return = "no_qualify", bets.ante * 2, bets.raise_bet
        elif mine > theirs:
            r.outcome, r.ante_return, r.raise_return = "win", bets.ante * 2, bets.raise_bet * 2
        elif mine < theirs:
            r.outcome = "lose"
        else:
            r.outcome, r.ante_return, r.raise_return = "push", bets.ante, bets.raise_bet
    if bets.flush:
        m = FLUSH_PAYS.get(length, 0)
        r.flush_return = bets.flush * (m + 1) if m else 0
    if bets.straight_flush:
        m = STRAIGHT_FLUSH_PAYS.get(sf, 0)
        r.straight_flush_return = bets.straight_flush * (m + 1) if m else 0
    if bets.jackpot:
        r.jackpot_share = JACKPOT_SHARES.get(sf, 0.0) if sf >= 6 else 0.0
        r.jackpot_fixed = JACKPOT_FIXED.get(sf, 0)
    return r


# ---------------------------------------------------------------------- strategy
def raise_by(cards) -> int:
    """Mousseau's strategy: raise any 4+ card flush, or a 3-card flush of
    10-8-6 or better, always by the most allowed; otherwise fold (0)."""
    length, values, _ = best_flush(cards)
    if length >= 4 or (length == 3 and values >= (10, 8, 6)):
        return max_raise(length)
    return 0


def rules() -> dict:
    return {"game": GAME_KEY, "title": GAME_LABEL,
            "sections": [{"title": "Flush", "rows": [[f"{n}-card flush", f"{m}:1"] for n, m in FLUSH_PAYS.items()]},
                         {"title": "Straight Flush", "rows": [[f"{n}-card straight flush", f"{m}:1"]
                                                              for n, m in STRAIGHT_FLUSH_PAYS.items()]},
                         {"title": "Jackpot (£1, straight flush length)",
                          "rows": [["7 cards", "100%"], ["6 cards", "50%"]] +
                          [[f"{n} cards", f"£{p // 100:,}"] for n, p in JACKPOT_FIXED.items()]}],
            "notes": ["Seven cards each. Your hand is your longest flush; equal lengths compare high cards.",
                      "Fold, or raise 1x the Ante (2x with a 5-card flush, 3x with 6 or 7).",
                      "Dealer qualifies with a 3-card flush, 9-high. If not: Ante pays 1:1, Raise pushes.",
                      "Beat a qualifying dealer: Ante and Raise pay 1:1.",
                      "Flush, Straight Flush and Jackpot pay on your cards even if you fold."]}
