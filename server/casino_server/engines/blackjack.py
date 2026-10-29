"""
Blackjack engine (8-deck shoe, UK casino payout rules), ported from Casino v2's
games/blackjack/logic.py and games/blackjack/strategy.py.

Same rules, paytables and basic strategy as v2, with these changes:
  - Money is integer pence (v2 used float pounds).
  - The pieces are pure functions over cards and bets (hand_value,
    side_bet_returns, settle_hand, recommend), so the table machine can deal
    any number of seats from one persistent shoe, and each piece can be
    tested against v2 card-for-card (see tests/test_blackjack_parity.py).
  - Insurance is always exactly half the main bet (v2 allowed up to half).

House rules:
  - 3:2 for a natural Blackjack, 8 decks dealt from a shoe.
  - American-style hole card with a peek: an Ace or 10-value up-card checks
    the hole card at once, and a Dealer Blackjack ends the round before
    anyone can Hit, Double or Split. Insurance is offered on an Ace, pays 2:1.
  - Double on any first two cards, including after a split. Split any equal-
    value pair (J+Q counts), up to 4 splits (5 hands). Split Aces get one card
    each and stand. A 21 on a split hand is just 21, not a Blackjack.
  - The dealer stands on all 17s, soft or hard.
  - Player Blackjack 3:2 (pushes against a Dealer Blackjack); bust loses;
    otherwise the higher total wins 1:1 and equal totals push.

Side bets, all settled straight after the deal off the player's first two
cards and the dealer's up-card (a three-card poker hand):
  Super Pairs (the two cards only): Any Pair 5:1, Prime Pair (same colour)
    10:1, Suited Pair 25:1, Suited Trips (with the up-card) 50:1.
  21+3: Flush or better pays 9:1.
  Top 3 (only with 21+3): Three of a Kind Suited 270:1, Straight Flush 180:1,
    Three of a Kind 90:1.
  Jackpot (flat £1, shares Three Card Poker's progressive pool): suited
    Three of a Kind A/K/Q -> the whole pool (split if more than one box hits
    it in a round); suited Three of a Kind £625; Straight Flush £125; Three of
    a Kind £100; Straight £30; Flush £10.
"""
from dataclasses import dataclass, field

from casino_server.engines.cards import Card
from casino_server.engines.hand_evaluator import (
    FLUSH,
    STRAIGHT,
    STRAIGHT_FLUSH,
    THREE_OF_A_KIND,
    evaluate_three_card_hand,
)

GAME_KEY = "blackjack"
GAME_LABEL = "Blackjack"

DECK_COUNT = 8
INSURANCE_MULTIPLIER = 2          # 2:1
MAX_SPLITS = 4                    # 5 hands from one box

SUPER_PAIRS = {"any": 5, "prime": 10, "suited": 25, "suited_trips": 50}
TWENTY_ONE_PLUS_THREE_MULTIPLIER = 9
TOP_THREE = {"trips": 90, "straight_flush": 180, "suited_trips": 270}

JACKPOT_BET = 100  # pence, flat
JACKPOT_FLUSH = 1_000
JACKPOT_STRAIGHT = 3_000
JACKPOT_TRIPS = 10_000
JACKPOT_STRAIGHT_FLUSH = 12_500
JACKPOT_SUITED_TRIPS = 62_500
_JACKPOT_POOL_RANKS = {"A", "K", "Q"}

SIDE_BETS = ("super_pairs", "twenty_one_plus_three", "top_three", "jackpot")


def card_value(card: Card) -> int:
    """Ace 11 (dropped to 1 by hand_value as needed), J/Q/K 10, else the rank."""
    if card.rank == "A":
        return 11
    if card.rank in ("J", "Q", "K"):
        return 10
    return int(card.rank)


def hand_value(cards) -> tuple[int, bool]:
    """(best total, soft): the highest total <= 21 counting each Ace as 1 or
    11 (or the all-low total if they all bust); soft if an Ace still counts 11."""
    total = sum(card_value(c) for c in cards)
    soft_aces = sum(1 for c in cards if c.rank == "A")
    while total > 21 and soft_aces > 0:
        total -= 10
        soft_aces -= 1
    return total, soft_aces > 0


def is_blackjack(cards) -> bool:
    return len(cards) == 2 and hand_value(cards)[0] == 21


@dataclass
class Hand:
    """One hand in a box: a box starts with one and splits into up to five."""
    cards: list
    bet: int
    doubled: bool = False
    from_split: bool = False
    split_aces: bool = False
    done: bool = False
    outcome: str | None = None  # Bust | Lose | Push | Win | Blackjack, once settled
    returned: int = 0           # pence back for this hand, once settled

    def __post_init__(self):
        if self.total == 21:
            self.done = True

    @property
    def total(self) -> int:
        return hand_value(self.cards)[0]

    @property
    def soft(self) -> bool:
        return hand_value(self.cards)[1]

    @property
    def bust(self) -> bool:
        return self.total > 21

    @property
    def natural(self) -> bool:
        return not self.from_split and is_blackjack(self.cards)

    @property
    def can_double(self) -> bool:
        return len(self.cards) == 2 and not self.done and not self.split_aces

    def can_split(self, split_count: int) -> bool:
        if self.done or len(self.cards) != 2 or self.split_aces or split_count >= MAX_SPLITS:
            return False
        return card_value(self.cards[0]) == card_value(self.cards[1])

    def label(self) -> str:
        """'Blackjack', 'Bust', 'Soft 17', '20'."""
        if self.natural:
            return "Blackjack"
        if self.bust:
            return "Bust"
        return f"Soft {self.total}" if self.soft and self.total < 21 else str(self.total)


# ---------------------------------------------------------------------- side bets
def super_pairs_multiplier(c1: Card, c2: Card, up: Card) -> int:
    if c1.rank != c2.rank:
        return 0
    if c1.suit == c2.suit:
        if up.rank == c1.rank and up.suit == c1.suit:
            return SUPER_PAIRS["suited_trips"]
        return SUPER_PAIRS["suited"]
    if c1.color == c2.color:
        return SUPER_PAIRS["prime"]
    return SUPER_PAIRS["any"]


def top_three_multiplier(three_eval, three) -> int:
    rank = three_eval[0]
    if rank == THREE_OF_A_KIND:
        return TOP_THREE["suited_trips"] if len({c.suit for c in three}) == 1 else TOP_THREE["trips"]
    if rank == STRAIGHT_FLUSH:
        return TOP_THREE["straight_flush"]
    return 0


def jackpot_tier(three_eval, three) -> tuple[int, bool]:
    """(fixed payout in pence, hits the pool). Only a suited Three of a Kind of
    Aces, Kings or Queens takes the progressive pool."""
    rank = three_eval[0]
    if rank == THREE_OF_A_KIND:
        suited = len({c.suit for c in three}) == 1
        if suited and three[0].rank in _JACKPOT_POOL_RANKS:
            return 0, True
        return (JACKPOT_SUITED_TRIPS if suited else JACKPOT_TRIPS), False
    if rank == STRAIGHT_FLUSH:
        return JACKPOT_STRAIGHT_FLUSH, False
    if rank == STRAIGHT:
        return JACKPOT_STRAIGHT, False
    if rank == FLUSH:
        return JACKPOT_FLUSH, False
    return 0, False


@dataclass
class SideBetResult:
    returns: dict = field(default_factory=dict)  # spot -> pence back (stake + winnings), 0 if lost
    hits_pool: bool = False                      # the Jackpot bet took the progressive pool
    hand: str = ""                               # the three-card hand, for the dealer's line


def side_bet_returns(cards, up: Card, bets: dict) -> SideBetResult:
    """What each side bet on this box returns. A Jackpot that hits the pool
    returns 0 here; the table shares the pool between every box that hit it."""
    c1, c2 = cards[0], cards[1]
    three = [c1, c2, up]
    result = SideBetResult()
    if bets.get("super_pairs", 0) > 0:
        mult = super_pairs_multiplier(c1, c2, up)
        result.returns["super_pairs"] = bets["super_pairs"] * (mult + 1) if mult else 0
    if any(bets.get(k, 0) > 0 for k in ("twenty_one_plus_three", "top_three", "jackpot")):
        three_eval = evaluate_three_card_hand(three)
        result.hand = three_eval[1]
        if bets.get("twenty_one_plus_three", 0) > 0:
            win = three_eval[0] >= FLUSH
            result.returns["twenty_one_plus_three"] = bets["twenty_one_plus_three"] * (TWENTY_ONE_PLUS_THREE_MULTIPLIER + 1) if win else 0
        if bets.get("top_three", 0) > 0:
            mult = top_three_multiplier(three_eval, three)
            result.returns["top_three"] = bets["top_three"] * (mult + 1) if mult else 0
        if bets.get("jackpot", 0) > 0:
            amount, pool = jackpot_tier(three_eval, three)
            result.returns["jackpot"] = amount
            result.hits_pool = pool
    return result


# ---------------------------------------------------------------------- settling
def blackjack_return(bet: int) -> int:
    """Stake plus 3:2. Bets are whole chips, so this is always whole pence."""
    return bet + bet * 3 // 2


def settle_hand(hand: Hand, dealer_total: int, dealer_bust: bool, dealer_blackjack: bool) -> tuple[str, int]:
    """(outcome, pence returned) for one finished hand."""
    if hand.bust:
        return "Bust", 0
    if hand.natural:
        if dealer_blackjack:
            return "Push", hand.bet
        return "Blackjack", blackjack_return(hand.bet)
    if dealer_blackjack:
        return "Lose", 0
    if dealer_bust or hand.total > dealer_total:
        return "Win", hand.bet * 2
    if hand.total == dealer_total:
        return "Push", hand.bet
    return "Lose", 0


def insurance_return(insurance: int, dealer_blackjack: bool) -> int:
    return insurance * (INSURANCE_MULTIPLIER + 1) if dealer_blackjack else 0


def dealer_should_hit(cards) -> bool:
    """The dealer draws to 17 and stands on all 17s."""
    return hand_value(cards)[0] < 17


def peeks(up: Card) -> bool:
    """An Ace or a 10-value up-card: the dealer checks for Blackjack."""
    return up.rank == "A" or card_value(up) == 10


# ---------------------------------------------------------------------- basic strategy
# The standard 8-deck, stands-on-soft-17, double-after-split, no-surrender
# chart (v2's games/blackjack/strategy.py). Columns: dealer up-card 2..10, A.
# "H" hit, "S" stand, "P" split, "Dh"/"Ds" double if allowed, else hit/stand.
HARD_TOTALS = {
    9:  ["H", "Dh", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    10: ["Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "Dh", "H", "H"],
    11: ["Dh"] * 10,
    12: ["H", "H", "S", "S", "S", "H", "H", "H", "H", "H"],
    13: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
    14: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
    15: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
    16: ["S", "S", "S", "S", "S", "H", "H", "H", "H", "H"],
}
SOFT_TOTALS = {
    13: ["H", "H", "H", "Dh", "Dh", "H", "H", "H", "H", "H"],
    14: ["H", "H", "H", "Dh", "Dh", "H", "H", "H", "H", "H"],
    15: ["H", "H", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    16: ["H", "H", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    17: ["H", "Dh", "Dh", "Dh", "Dh", "H", "H", "H", "H", "H"],
    18: ["Ds", "Ds", "Ds", "Ds", "Ds", "S", "S", "H", "H", "H"],
    19: ["S", "S", "S", "S", "Ds", "S", "S", "S", "S", "S"],
    20: ["S"] * 10,
}
PAIRS = {
    "A": ["P"] * 10,
    10: ["S"] * 10,
    9:  ["P", "P", "P", "P", "P", "S", "P", "P", "S", "S"],
    8:  ["P"] * 10,
    7:  ["P", "P", "P", "P", "P", "P", "H", "H", "H", "H"],
    6:  ["P", "P", "P", "P", "P", "H", "H", "H", "H", "H"],
    5:  None,  # never split: played as a hard 10
    4:  ["H", "H", "H", "P", "P", "H", "H", "H", "H", "H"],
    3:  ["P", "P", "P", "P", "P", "P", "H", "H", "H", "H"],
    2:  ["P", "P", "P", "P", "P", "P", "H", "H", "H", "H"],
}
ACTIONS = {"H": "hit", "S": "stand", "P": "split", "Dh": "double", "Ds": "double"}


def recommend(cards, up: Card, can_double: bool, can_split: bool) -> str:
    """The basic-strategy play for this hand: hit | stand | double | split."""
    col = card_value(up) - 2
    total, soft = hand_value(cards)
    code = None
    if len(cards) == 2 and card_value(cards[0]) == card_value(cards[1]) and can_split:
        row = PAIRS.get(cards[0].rank if cards[0].rank == "A" else card_value(cards[0]))
        if row is not None:
            code = row[col]
    if code is None:
        if soft:
            row = SOFT_TOTALS.get(total, ["H"] * 10 if total < 13 else ["S"] * 10)
        else:
            row = HARD_TOTALS.get(total, ["H"] * 10 if total <= 8 else ["S"] * 10)
        code = row[col]
    if code == "Dh" and not can_double:
        code = "H"
    elif code == "Ds" and not can_double:
        code = "S"
    return ACTIONS[code]


# ---------------------------------------------------------------------- counting
# Hi-Lo: 2-6 count +1, 7-9 nothing, tens and Aces -1, so a whole shoe sums to 0. The true count is the running
# count over the decks still to come.
HILO = {"2": 1, "3": 1, "4": 1, "5": 1, "6": 1, "7": 0, "8": 0, "9": 0, "10": -1, "J": -1, "Q": -1, "K": -1, "A": -1}

# The plays a Hi-Lo counter changes with the count: the Illustrious 18 lines these rules have (stands on all 17s,
# no surrender; insurance at +3 is the director's, and 11 against an Ace is a double on the chart already).
# (hard total, up-card value) -> (play, index, above): the play at a true count of `index` or more if `above`,
# below it if not.
HARD_DEVIATIONS = {
    (16, 10): ("stand", 0, True),
    (15, 10): ("stand", 4, True),
    (16, 9): ("stand", 5, True),
    (12, 3): ("stand", 2, True),
    (12, 2): ("stand", 3, True),
    (12, 4): ("hit", 0, False),
    (12, 5): ("hit", -2, False),
    (12, 6): ("hit", -1, False),
    (13, 2): ("hit", -1, False),
    (13, 3): ("hit", -2, False),
    (10, 10): ("double", 4, True),
    (10, 11): ("double", 4, True),
    (9, 2): ("double", 1, True),
    (9, 7): ("double", 3, True),
}
SPLIT_TENS = {5: 5, 6: 4}   # a pair of tens is split against a 5 at +5, a 6 at +4


def hilo(card: Card) -> int:
    return HILO.get(card.rank, 0)


def deviation(cards, up: Card, true_count: float, can_double: bool, can_split: bool) -> str | None:
    """The play a counter makes instead of the chart's at this true count, or None to play the chart."""
    total, soft = hand_value(cards)
    upv = card_value(up)
    pair = len(cards) == 2 and card_value(cards[0]) == card_value(cards[1])
    if pair and can_split and total == 20 and upv in SPLIT_TENS:
        return "split" if true_count >= SPLIT_TENS[upv] else None
    if soft or (pair and can_split and recommend(cards, up, can_double, can_split) == "split"):
        return None
    line = HARD_DEVIATIONS.get((total, upv))
    if line is None:
        return None
    play, index, above = line
    if (true_count >= index) != above or (play == "double" and not can_double):
        return None
    return play


# ---------------------------------------------------------------------- paytable
def rules() -> dict:
    return {
        "game": GAME_KEY,
        "title": GAME_LABEL,
        "sections": [
            {"title": "Blackjack", "rows": [["Blackjack", "3:2"], ["Win", "1:1"], ["Insurance", "2:1"]]},
            {"title": "Super Pairs", "rows": [["Suited Trips", "50:1"], ["Suited Pair", "25:1"],
                                              ["Prime Pair", "10:1"], ["Any Pair", "5:1"]]},
            {"title": "21+3", "rows": [["Flush or better", "9:1"]]},
            {"title": "Top 3", "rows": [["Suited Three of a Kind", "270:1"], ["Straight Flush", "180:1"],
                                        ["Three of a Kind", "90:1"]]},
            {"title": "Jackpot (£1)", "rows": [["Suited A-A-A / K-K-K / Q-Q-Q", "Jackpot"],
                                              ["Suited Three of a Kind", "£625"], ["Straight Flush", "£125"],
                                              ["Three of a Kind", "£100"], ["Straight", "£30"], ["Flush", "£10"]]},
        ],
        "notes": [
            "8 decks dealt from a shoe; it's shuffled when the cut card comes out.",
            "Dealer stands on all 17s and checks for Blackjack with an Ace or 10 showing.",
            "Double on any two cards, also after splitting. Split pairs up to 4 times; split Aces get one card each.",
            "Side bets use your first two cards and the dealer's up-card. Top 3 needs a 21+3 bet.",
        ],
    }
