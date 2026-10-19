"""
Ultimate Texas Hold'em engine, ported from Casino v2's
games/ultimate_texas_holdem/logic.py.

Same rules and paytables as v2, with these changes:
  - Money is integer pence; a Jackpot share is a fraction the table takes
    from the pool (Jackpot.take).
  - A table deals every seat two cards from one deck, with one dealer hand
    and one board of five community cards for everyone.
  - The last decision comes after the river, as at a real table (v2, one
    player, offered it after the turn). The maths is unchanged.
  - NPC play: the Wizard of Odds' simple strategy (`preflop_bet`,
    `flop_bet`, `river_bet`), which v2 didn't have.

The game: Ante and an equal Blind (Trips and the £1 Jackpot are optional).
Before the flop a player may bet 4x or 3x the Ante as their Play bet, or
check; after the flop, 2x or check; after the river, 1x or fold. Once a Play
bet is made there are no more decisions. The dealer qualifies with a pair:
  - Beat a qualifying dealer: Ante and Play pay 1:1. A dealer who doesn't
    qualify pushes the Ante (Play still pays on a win).
  - Win with a Straight or better and the Blind pays (Royal 500:1, Straight
    Flush 50:1, Quads 10:1, Full House 3:1, Flush 3:2, Straight 1:1); any
    other win pushes it. Lose: Ante, Blind and Play lose. Tie: all push.
  - A fold forfeits Ante, Blind, Trips and the Jackpot.
Trips (on the player's own final hand, whatever the dealer has): Royal 50:1,
Straight Flush 40:1, Quads 20:1, Full House 7:1, Flush 6:1, Straight 5:1,
Trips 3:1. The £1 Jackpot is judged on the two hole cards plus the flop
only: Royal 100% of the pool, Straight Flush 10%, Quads £300, Full House
£50, Flush £40, Straight £30, Trips £9.
"""
from collections import Counter
from dataclasses import dataclass
from itertools import combinations

from casino_server.engines.hand_evaluator import (
    FIVE_CARD_FLUSH, FIVE_CARD_HIGH_CARD, FIVE_CARD_STRAIGHT, FIVE_CARD_STRAIGHT_FLUSH, FIVE_CARD_THREE_OF_A_KIND,
    FOUR_OF_A_KIND, FULL_HOUSE, ONE_PAIR, TWO_PAIR, compare_hands, evaluate_five_card_hand,
)

GAME_KEY = "ultimate_texas_holdem"
GAME_LABEL = "Ultimate Texas Hold'em"
JACKPOT_BET = 100

TRIPS_PAYTABLE = {FIVE_CARD_THREE_OF_A_KIND: 3, FIVE_CARD_STRAIGHT: 5, FIVE_CARD_FLUSH: 6, FULL_HOUSE: 7, FOUR_OF_A_KIND: 20}
TRIPS_STRAIGHT_FLUSH, TRIPS_ROYAL = 40, 50
BLIND_PAYTABLE = {FIVE_CARD_STRAIGHT: (1, 1), FIVE_CARD_FLUSH: (3, 2), FULL_HOUSE: (3, 1), FOUR_OF_A_KIND: (10, 1)}
BLIND_STRAIGHT_FLUSH, BLIND_ROYAL = (50, 1), (500, 1)
JACKPOT_FIXED = {FOUR_OF_A_KIND: 30_000, FULL_HOUSE: 5_000, FIVE_CARD_FLUSH: 4_000,
                 FIVE_CARD_STRAIGHT: 3_000, FIVE_CARD_THREE_OF_A_KIND: 900}
JACKPOT_STRAIGHT_FLUSH_SHARE = 0.10
ACE = 14
NAMES = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}


def best_hand(cards):
    """The best 5-card hand from 5-7 cards: (eval, the five cards)."""
    best = best_cards = None
    for combo in combinations(cards, 5):
        ev = evaluate_five_card_hand(combo)
        if best is None or compare_hands(ev, best) > 0:
            best, best_cards = ev, list(combo)
    return best, best_cards


def is_royal(ev) -> bool:
    return ev[0] == FIVE_CARD_STRAIGHT_FLUSH and ev[2][0] == ACE


def trips_multiplier(ev) -> int:
    if ev[0] == FIVE_CARD_STRAIGHT_FLUSH:
        return TRIPS_ROYAL if is_royal(ev) else TRIPS_STRAIGHT_FLUSH
    return TRIPS_PAYTABLE.get(ev[0], 0)


def blind_odds(ev) -> tuple[int, int] | None:
    """(to, for) for a winning hand's Blind; None: it pushes."""
    if ev[0] == FIVE_CARD_STRAIGHT_FLUSH:
        return BLIND_ROYAL if is_royal(ev) else BLIND_STRAIGHT_FLUSH
    return BLIND_PAYTABLE.get(ev[0])


def jackpot_payout(ev) -> tuple[int, float]:
    if ev[0] == FIVE_CARD_STRAIGHT_FLUSH:
        return (0, 1.0) if is_royal(ev) else (0, JACKPOT_STRAIGHT_FLUSH_SHARE)
    return JACKPOT_FIXED.get(ev[0], 0), 0.0


def hand_label(ev) -> str:
    rank, name, tiebreak = ev
    if rank == FIVE_CARD_STRAIGHT_FLUSH:
        return "Royal Flush" if is_royal(ev) else "Straight Flush"
    if rank == ONE_PAIR:
        return f"Pair of {NAMES.get(tiebreak[0], str(tiebreak[0]))}s"
    if rank == FIVE_CARD_HIGH_CARD:
        return f"{NAMES.get(tiebreak[0], str(tiebreak[0]))} high"
    return name


@dataclass
class Bets:
    ante: int
    trips: int = 0
    jackpot: int = 0
    play: int = 0

    @property
    def blind(self) -> int:
        return self.ante


@dataclass
class Result:
    outcome: str                  # win | lose | push | fold
    player_eval: tuple | None
    dealer_eval: tuple | None
    dealer_qualified: bool = False
    ante_return: int = 0
    blind_return: int = 0
    play_return: int = 0
    trips_return: int = 0
    jackpot_fixed: int = 0
    jackpot_share: float = 0.0

    @property
    def total_returned(self) -> int:
        return self.ante_return + self.blind_return + self.play_return + self.trips_return + self.jackpot_fixed


def settle(hole, dealer, board, bets: Bets, folded: bool) -> Result:
    if folded:
        return Result("fold", None, None)
    player_eval, _ = best_hand(list(hole) + list(board))
    dealer_eval, _ = best_hand(list(dealer) + list(board))
    qualified = dealer_eval[0] >= ONE_PAIR
    cmp = compare_hands(player_eval, dealer_eval)
    outcome = "win" if cmp > 0 else "lose" if cmp < 0 else "push"
    r = Result(outcome, player_eval, dealer_eval, qualified)
    if outcome == "win":
        r.ante_return = bets.ante * 2 if qualified else bets.ante
        r.play_return = bets.play * 2
        odds = blind_odds(player_eval)
        r.blind_return = bets.blind + bets.blind * odds[0] // odds[1] if odds else bets.blind
    elif outcome == "push":
        r.ante_return, r.play_return, r.blind_return = bets.ante, bets.play, bets.blind
    elif not qualified:
        r.ante_return = bets.ante  # a dealer who doesn't qualify pushes the Ante, even on a loss
    if bets.trips:
        m = trips_multiplier(player_eval)
        r.trips_return = bets.trips * (m + 1) if m else 0
    if bets.jackpot:
        jackpot_eval, _ = best_hand(list(hole) + list(board[:3]))
        r.jackpot_fixed, r.jackpot_share = jackpot_payout(jackpot_eval)
    return r


# ---------------------------------------------------------------------- strategy
# The Wizard of Odds' simple strategy for Ultimate Texas Hold'em.
def preflop_bet(hole) -> int:
    """4 (bet 4x) or 0 (check): any pair of 3s or better; any Ace; King with
    any suited card or 5+ offsuit; Queen with 6+ suited or 8+ offsuit; Jack
    with 8+ suited or 10 offsuit."""
    a, b = sorted((c.value for c in hole), reverse=True)
    suited = hole[0].suit == hole[1].suit
    if a == b:
        return 4 if a >= 3 else 0
    if a == ACE:
        return 4
    if a == 13:
        return 4 if suited or b >= 5 else 0
    if a == 12:
        return 4 if b >= (6 if suited else 8) else 0
    if a == 11:
        return 4 if b >= (8 if suited else 10) else 0
    return 0


def _counts(cards):
    return Counter(c.value for c in cards)


def _hidden_pair_or_better(hole, board) -> bool:
    """A pair (or better) that uses at least one hole card."""
    board_counts = _counts(board)
    all_counts = _counts(list(hole) + list(board))
    hole_values = {c.value for c in hole}
    if hole[0].value == hole[1].value:
        return True
    return any(all_counts[v] > board_counts.get(v, 0) and all_counts[v] >= 2 for v in hole_values)


def flop_bet(hole, flop) -> int:
    """2 (bet 2x) or 0 (check): two pair or better (using a hole card); a hidden
    pair, except pocket 2s; four to a flush with a hidden 10 or better of that suit."""
    ev, _ = best_hand(list(hole) + list(flop))
    if ev[0] >= TWO_PAIR and _hidden_pair_or_better(hole, flop):
        return 2
    if ev[0] in (FIVE_CARD_STRAIGHT, FIVE_CARD_FLUSH, FIVE_CARD_STRAIGHT_FLUSH):
        return 2
    pocket_twos = hole[0].value == hole[1].value == 2
    if _hidden_pair_or_better(hole, flop) and not pocket_twos:
        return 2
    suits = Counter(c.suit for c in list(hole) + list(flop))
    for suit, n in suits.items():
        if n >= 4 and any(c.suit == suit and c.value >= 10 for c in hole):
            return 2
    return 0


def dealer_outs(hole, board) -> float:
    """How many of the unseen cards would, as one of the dealer's hole cards
    (with the board), beat the player's hand. A tie isn't an out (it pushes)."""
    from casino_server.engines.cards import Card, RANK_ORDER, Suit
    seen = {c.code for c in list(hole) + list(board)}
    mine, _ = best_hand(list(hole) + list(board))
    outs = 0.0
    for suit in Suit:
        for rank in RANK_ORDER:
            card = Card(rank, suit)
            if card.code in seen:
                continue
            theirs, _ = best_hand([card] + list(board))
            c = compare_hands(theirs, mine)
            outs += 1.0 if c > 0 else 0.0
    return outs


def river_bet(hole, board) -> int:
    """1 (bet 1x) or 0 (fold): a hidden pair or better, or fewer than 21 dealer outs."""
    if _hidden_pair_or_better(hole, board):
        return 1
    ev, _ = best_hand(list(hole) + list(board))
    board_ev, _ = best_hand(list(board))
    if compare_hands(ev, board_ev) > 0 and ev[0] >= FIVE_CARD_STRAIGHT:
        return 1  # a straight or flush made with a hole card
    return 1 if dealer_outs(hole, board) < 21 else 0


# ---------------------------------------------------------------------- paytable
def rules() -> dict:
    names = {FOUR_OF_A_KIND: "Four of a Kind", FULL_HOUSE: "Full House", FIVE_CARD_FLUSH: "Flush",
             FIVE_CARD_STRAIGHT: "Straight", FIVE_CARD_THREE_OF_A_KIND: "Three of a Kind"}
    blind = [["Royal Flush", "500 to 1"], ["Straight Flush", "50 to 1"], ["Four of a Kind", "10 to 1"],
             ["Full House", "3 to 1"], ["Flush", "3 to 2"], ["Straight", "1 to 1"], ["Any other win", "Push"]]
    trips = [["Royal Flush", "50 to 1"], ["Straight Flush", "40 to 1"]] + \
        [[names[r], f"{m} to 1"] for r, m in sorted(TRIPS_PAYTABLE.items(), key=lambda x: -x[1])]
    jackpot = [["Royal Flush", "100% of the Jackpot"], ["Straight Flush", "10% of the Jackpot"]] + \
        [[names[r], f"£{p // 100:,}"] for r, p in JACKPOT_FIXED.items()]
    return {"game": GAME_KEY, "title": GAME_LABEL,
            "sections": [{"title": "Blind (on a win)", "rows": blind}, {"title": "Trips", "rows": trips},
                         {"title": "Jackpot (£1, hole cards + flop)", "rows": jackpot}],
            "notes": ["Ante and an equal Blind. Before the flop: bet 4x or 3x the Ante, or check.",
                      "After the flop: bet 2x or check. After the river: bet 1x or fold.",
                      "Dealer qualifies with a pair. Beat the dealer: Ante and Play pay 1 to 1.",
                      "Dealer doesn't qualify: the Ante pushes.",
                      "Folding loses the Ante, Blind, Trips and Jackpot."]}
