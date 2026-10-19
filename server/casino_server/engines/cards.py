"""
Playing card primitives, ported from Casino v2's core/cards.py.

Changes from v2: Deck takes an optional `rng` (a random.Random) so tests can
seed it -- the default is SystemRandom, since the server is the only place a
shuffle ever happens -- and every Card has a short `code` ("Qs", "10h") used
on the wire to the client.
"""
import random
from enum import Enum


class Suit(Enum):
    HEARTS = "Hearts"
    DIAMONDS = "Diamonds"
    CLUBS = "Clubs"
    SPADES = "Spades"


SUIT_CODES = {Suit.HEARTS: "h", Suit.DIAMONDS: "d", Suit.CLUBS: "c", Suit.SPADES: "s"}

SUIT_COLORS = {
    Suit.HEARTS: "red",
    Suit.DIAMONDS: "red",
    Suit.CLUBS: "black",
    Suit.SPADES: "black",
}

# Ace-high ordering used by most casino card games.
RANK_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANK_ORDER)}

JOKER = "Joker"


class Card:
    __slots__ = ("rank", "suit")

    def __init__(self, rank: str, suit: "Suit | None" = None):
        # The Joker (Pai Gow Poker's 53rd card) carries no suit; its value is
        # resolved by whichever hand evaluator is looking at it.
        if rank == JOKER:
            self.rank = rank
            self.suit = None
            return
        if rank not in RANK_VALUES:
            raise ValueError(f"Invalid rank: {rank}")
        if suit is None:
            raise ValueError("A non-Joker card needs a suit.")
        self.rank = rank
        self.suit = suit

    @classmethod
    def from_code(cls, code: str) -> "Card":
        """Inverse of `code` -- handy for tests: Card.from_code("10h")."""
        if code == "Jkr":
            return cls(JOKER)
        suit = next(s for s, c in SUIT_CODES.items() if c == code[-1])
        return cls(code[:-1], suit)

    @property
    def is_joker(self) -> bool:
        return self.rank == JOKER

    @property
    def value(self) -> int:
        """Numeric rank value, 2-14 (Ace high)."""
        return RANK_VALUES[self.rank]

    @property
    def color(self) -> str:
        return SUIT_COLORS[self.suit]

    @property
    def code(self) -> str:
        return "Jkr" if self.is_joker else f"{self.rank}{SUIT_CODES[self.suit]}"

    def __repr__(self):
        return f"Card({self.code})"

    def __eq__(self, other):
        return isinstance(other, Card) and self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))


class Deck:
    """A shuffled 52-card deck, or a shoe of `num_decks` decks; `include_joker`
    adds one Joker (Pai Gow Poker's 53-card deck)."""

    def __init__(self, num_decks: int = 1, include_joker: bool = False, rng: random.Random | None = None):
        self.num_decks = num_decks
        self.rng = rng or random.SystemRandom()
        self._all_cards = [
            Card(rank, suit)
            for _ in range(num_decks)
            for suit in Suit
            for rank in RANK_ORDER
        ]
        if include_joker:
            self._all_cards.append(Card(JOKER))
        self.cards = []
        self.reset()

    def reset(self):
        """Return every card to the deck and shuffle -- call at the start of each round."""
        self.cards = list(self._all_cards)
        self.rng.shuffle(self.cards)

    def deal(self, count: int = 1):
        if count > len(self.cards):
            raise ValueError("Not enough cards left in the deck.")
        dealt, self.cards = self.cards[:count], self.cards[count:]
        return dealt

    def cards_remaining(self) -> int:
        return len(self.cards)
