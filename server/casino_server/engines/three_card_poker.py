"""
Three Card Poker engine (UK casino payout rules), ported from Casino v2's
games/three_card_poker/logic.py.

Same rules and paytables as v2, with three changes:
  - Money is integer pence (v2 used float pounds).
  - A round deals any number of seats plus one shared dealer hand from a
    single deck (ThreeCardPokerRound); v2 dealt one player against the dealer.
  - Settling one hand is a pure function, settle_hand(), so it can be tested
    against v2 card-for-card (see tests/test_three_card_poker_parity.py).

Payout rules:
  Main game (Ante & Play):
    - Player beats dealer (dealer qualifies): Ante 1:1, Play 1:1
    - Dealer doesn't qualify (below Queen-high): Ante 1:1, Play pushes
    - Dealer beats player: Ante and Play both lost
    - Tie: both push
  Ante Bonus (paid regardless of dealer's hand, forfeited on fold):
    - Straight Flush 5:1, Three of a Kind 4:1, Straight 1:1
  Pair Plus (player's hand alone, unaffected by fold):
    - Pair 1:1, Flush 4:1, Straight 6:1, Three of a Kind 33:1, Straight Flush 35:1
  Prime (UK, suit colour, unaffected by fold):
    - All 3 player cards same colour 3:1; all 6 cards same colour 4:1 (supersedes)
  Jackpot (flat £1, player's hand alone, unaffected by fold):
    - Straight £6, Three of a Kind £60, Straight Flush (not Ace-high) £100,
      Royal Flush (Q-K-A suited) not spades £500,
      Royal Flush in spades: 100% of the progressive jackpot.
"""
from dataclasses import dataclass, field

from casino_server.engines.cards import Card, Deck, Suit
from casino_server.engines.hand_evaluator import (
    HAND_NAMES,
    HIGH_CARD,
    STRAIGHT,
    STRAIGHT_FLUSH,
    THREE_OF_A_KIND,
    HandEval,
    compare_hands,
    dealer_qualifies,
    evaluate_three_card_hand,
)

GAME_KEY = "three_card_poker"
GAME_LABEL = "Three Card Poker"

ANTE_BONUS_MULTIPLIERS = {
    STRAIGHT_FLUSH: 5,
    THREE_OF_A_KIND: 4,
    STRAIGHT: 1,
}

PAIR_PLUS_MULTIPLIERS = {
    "Pair": 1,
    "Flush": 4,
    "Straight": 6,
    "Three of a Kind": 33,
    "Straight Flush": 35,
}

PRIME_SAME_COLOUR_3_MULTIPLIER = 3
PRIME_SAME_COLOUR_6_MULTIPLIER = 4

# Jackpot side bet: always exactly this amount if played (an on/off toggle, not a chip stack).
JACKPOT_BET = 100  # pence

JACKPOT_STRAIGHT_PAYOUT = 600
JACKPOT_THREE_OF_A_KIND_PAYOUT = 6_000
JACKPOT_STRAIGHT_FLUSH_PAYOUT = 10_000    # excluding the Ace-high "Royal"
JACKPOT_ROYAL_NON_SPADES_PAYOUT = 50_000  # Q-K-A suited, any suit but spades
# Q-K-A of spades pays 100% of the progressive jackpot -- see jackpot_payout().

_ROYAL_HIGH_CARD = 14

# Q-6-4 or better should be played -- the statistically correct cutoff
# (only the Ante/Play paytable affects it; side bets pay the same either way).
Q64_THRESHOLD: HandEval = (HIGH_CARD, HAND_NAMES[HIGH_CARD], (12, 6, 4))


def _is_royal(player_eval: HandEval) -> bool:
    rank, _, tiebreak = player_eval
    return rank == STRAIGHT_FLUSH and tiebreak[0] == _ROYAL_HIGH_CARD


def should_play(player_eval: HandEval) -> bool:
    """True if `player_eval` is Q-6-4 or better -- basic strategy's Play decision."""
    return compare_hands(player_eval, Q64_THRESHOLD) >= 0


def hand_label(player_eval: HandEval) -> str:
    """The hand's rank name, with a Royal Flush broken out from a Straight Flush."""
    return "Royal Flush" if _is_royal(player_eval) else player_eval[1]


def jackpot_payout(player_eval: HandEval, player_cards, jackpot_amount: int) -> tuple[int, bool]:
    """(payout, hits_jackpot) for the £1 jackpot bet. `hits_jackpot` is True only
    for the spades Royal Flush, which pays `jackpot_amount` in full -- the caller
    resets the progressive pool afterwards."""
    rank = player_eval[0]
    if rank == STRAIGHT_FLUSH:
        if _is_royal(player_eval):
            if player_cards[0].suit == Suit.SPADES:  # a flush, so any card's suit says it all
                return jackpot_amount, True
            return JACKPOT_ROYAL_NON_SPADES_PAYOUT, False
        return JACKPOT_STRAIGHT_FLUSH_PAYOUT, False
    if rank == THREE_OF_A_KIND:
        return JACKPOT_THREE_OF_A_KIND_PAYOUT, False
    if rank == STRAIGHT:
        return JACKPOT_STRAIGHT_PAYOUT, False
    return 0, False


@dataclass
class Bets:
    ante: int = 0
    pair_plus: int = 0
    prime: int = 0
    jackpot: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Bets":
        try:
            bets = cls(**{k: int(data.get(k, 0)) for k in ("ante", "pair_plus", "prime", "jackpot")})
        except (TypeError, ValueError):
            raise ValueError("Bets must be whole numbers of pence.")
        bets.validate()
        return bets

    def validate(self):
        if self.ante <= 0:
            raise ValueError("An Ante bet is required to deal.")
        if min(self.pair_plus, self.prime) < 0:
            raise ValueError("Bets can't be negative.")
        if self.jackpot not in (0, JACKPOT_BET):
            raise ValueError(f"The Jackpot bet is exactly £{JACKPOT_BET // 100} if played.")

    @property
    def upfront(self) -> int:
        """Taken when the cards are dealt."""
        return self.ante + self.pair_plus + self.prime + self.jackpot

    @property
    def max_cost(self) -> int:
        """Worst case for the round: the upfront bets plus a Play bet matching the
        Ante. A casino won't take an Ante you couldn't back with a Play bet, so
        bets are checked against this, not just the upfront total."""
        return self.upfront + self.ante

    def to_dict(self) -> dict:
        return {"ante": self.ante, "pair_plus": self.pair_plus, "prime": self.prime, "jackpot": self.jackpot}


@dataclass
class HandResult:
    """Outcome of one seat's hand. Every amount is pence; *_return includes the stake."""
    player_cards: list
    dealer_cards: list
    player_eval: HandEval
    dealer_eval: HandEval
    bets: Bets
    folded: bool = False
    dealer_qualified: bool = False
    outcome: str = ""  # "win" | "lose" | "push" | "dealer_no_qualify" | "fold"
    play_bet: int = 0
    ante_return: int = 0
    play_return: int = 0
    ante_bonus_return: int = 0
    pair_plus_return: int = 0
    prime_return: int = 0
    jackpot_return: int = 0
    jackpot_won: bool = False
    summary: str = ""

    @property
    def total_wagered(self) -> int:
        return self.bets.upfront + self.play_bet

    @property
    def total_returned(self) -> int:
        return (self.ante_return + self.play_return + self.ante_bonus_return
                + self.pair_plus_return + self.prime_return + self.jackpot_return)

    @property
    def net(self) -> int:
        return self.total_returned - self.total_wagered

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "summary": self.summary,
            "hand": hand_label(self.player_eval),
            "dealer_hand": hand_label(self.dealer_eval),
            "dealer_qualified": self.dealer_qualified,
            "bets": {**self.bets.to_dict(), "play": self.play_bet},
            "returns": {
                "ante": self.ante_return,
                "play": self.play_return,
                "ante_bonus": self.ante_bonus_return,
                "pair_plus": self.pair_plus_return,
                "prime": self.prime_return,
                "jackpot": self.jackpot_return,
            },
            "jackpot_won": self.jackpot_won,
            "total_wagered": self.total_wagered,
            "total_returned": self.total_returned,
            "net": self.net,
        }


def settle_hand(player_cards, dealer_cards, bets: Bets, folded: bool, jackpot_amount: int = 0) -> HandResult:
    """Settles one hand against the dealer -- v2's ThreeCardPokerGame.resolve(),
    in pence. When playing, the Play bet equals the Ante (standard rule)."""
    player_eval = evaluate_three_card_hand(player_cards)
    dealer_eval = evaluate_three_card_hand(dealer_cards)
    r = HandResult(player_cards, dealer_cards, player_eval, dealer_eval, bets, folded=folded)
    r.play_bet = 0 if folded else bets.ante
    r.dealer_qualified = dealer_qualifies(dealer_eval)

    # --- Jackpot: player's hand alone, regardless of fold ---
    if bets.jackpot > 0:
        r.jackpot_return, r.jackpot_won = jackpot_payout(player_eval, player_cards, jackpot_amount)

    # --- Pair Plus: player's hand alone, regardless of fold ---
    if bets.pair_plus > 0:
        multiplier = PAIR_PLUS_MULTIPLIERS.get(player_eval[1], 0)
        r.pair_plus_return = bets.pair_plus * (multiplier + 1) if multiplier else 0

    # --- Prime (UK): suit colour, regardless of fold ---
    if bets.prime > 0:
        player_colours = {c.color for c in player_cards}
        all_colours = {c.color for c in (player_cards + dealer_cards)}
        if len(all_colours) == 1:
            r.prime_return = bets.prime * (PRIME_SAME_COLOUR_6_MULTIPLIER + 1)
        elif len(player_colours) == 1:
            r.prime_return = bets.prime * (PRIME_SAME_COLOUR_3_MULTIPLIER + 1)

    # --- Ante Bonus: regardless of dealer's hand, forfeited on fold ---
    if not folded:
        multiplier = ANTE_BONUS_MULTIPLIERS.get(player_eval[0], 0)
        r.ante_bonus_return = bets.ante * multiplier

    # --- Main Ante / Play ---
    if folded:
        r.outcome = "fold"
        r.summary = "You folded and forfeited your Ante."
    elif not r.dealer_qualified:
        r.outcome = "dealer_no_qualify"
        r.ante_return = bets.ante * 2  # stake back + 1:1
        r.play_return = r.play_bet     # push
        r.summary = "Dealer doesn't qualify (below Queen-high). Ante pays 1:1, Play pushes."
    else:
        comparison = compare_hands(player_eval, dealer_eval)
        if comparison > 0:
            r.outcome = "win"
            r.ante_return = bets.ante * 2
            r.play_return = r.play_bet * 2
            r.summary = "You beat the dealer! Ante and Play both pay 1:1."
        elif comparison < 0:
            r.outcome = "lose"
            r.summary = "Dealer's hand wins. Ante and Play are lost."
        else:
            r.outcome = "push"
            r.ante_return = bets.ante
            r.play_return = r.play_bet
            r.summary = "Push! Hands are equal, stakes returned."
    return r


@dataclass
class ThreeCardPokerRound:
    """One round at a table: every betting seat gets 3 cards, the dealer gets 3,
    all from one deck. Seats then Play or Fold; settle() once all have decided."""
    seat_bets: dict  # seat index -> Bets
    deck: Deck = field(default_factory=Deck)
    hands: dict = field(default_factory=dict)      # seat -> [Card]
    decisions: dict = field(default_factory=dict)  # seat -> folded (bool)
    dealer_cards: list = field(default_factory=list)

    def __post_init__(self):
        if not self.seat_bets:
            raise ValueError("A round needs at least one seat with bets.")
        self.deck.reset()
        for seat in sorted(self.seat_bets):
            self.hands[seat] = self.deck.deal(3)
        self.dealer_cards = self.deck.deal(3)

    def decide(self, seat: int, play: bool):
        if seat not in self.hands:
            raise ValueError("That seat isn't in this round.")
        if seat in self.decisions:
            raise ValueError("You've already decided this hand.")
        self.decisions[seat] = not play

    @property
    def all_decided(self) -> bool:
        return len(self.decisions) == len(self.hands)

    def hand_name(self, seat: int) -> str:
        return hand_label(evaluate_three_card_hand(self.hands[seat]))

    def settle(self, jackpot_amount: int = 0) -> dict:
        """seat -> HandResult. Only one spades Royal Flush exists per deck, so at
        most one seat can win the progressive jackpot."""
        assert self.all_decided, "settle() called before every seat decided"
        return {
            seat: settle_hand(cards, self.dealer_cards, self.seat_bets[seat],
                              self.decisions[seat], jackpot_amount)
            for seat, cards in self.hands.items()
        }


def rules() -> dict:
    """Paytable for the client to display -- read from the constants above so it
    can't drift from what's actually paid."""
    def odds(m):
        return f"{m}:1"
    return {
        "sections": [
            {"title": "Ante Bonus", "rows": [
                [HAND_NAMES[STRAIGHT_FLUSH], odds(5)], [HAND_NAMES[THREE_OF_A_KIND], odds(4)],
                [HAND_NAMES[STRAIGHT], odds(1)]]},
            {"title": "Pair Plus", "rows": [[name, odds(m)] for name, m in reversed(PAIR_PLUS_MULTIPLIERS.items())]},
            {"title": "Prime", "rows": [
                ["6 Cards Same Colour", odds(PRIME_SAME_COLOUR_6_MULTIPLIER)],
                ["3 Cards Same Colour", odds(PRIME_SAME_COLOUR_3_MULTIPLIER)]]},
            {"title": "Jackpot (£1)", "rows": [
                ["Royal Flush (spades)", "JACKPOT"],
                ["Royal Flush", f"£{JACKPOT_ROYAL_NON_SPADES_PAYOUT // 100}"],
                ["Straight Flush", f"£{JACKPOT_STRAIGHT_FLUSH_PAYOUT // 100}"],
                ["Three of a Kind", f"£{JACKPOT_THREE_OF_A_KIND_PAYOUT // 100}"],
                ["Straight", f"£{JACKPOT_STRAIGHT_PAYOUT // 100}"]]},
        ],
        "notes": ["Dealer qualifies with Queen-high or better.", "Play bet equals your Ante."],
        "jackpot_bet": JACKPOT_BET,
    }
