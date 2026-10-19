"""
The dealer's lines, read from dealer_lines.toml (edit it to add or reword
lines; changes are picked up on the next line said, no restart needed).

DealerLines.say(section, key, **values) picks a random line from a list and
fills in its placeholders, skipping lines that need a value it wasn't given.
announce() builds what the dealer says as a player's hand is turned over:
"Pair of Kings, wins." plus, sometimes, a reaction by how strong the hand was.
"""
import random
import tomllib
from pathlib import Path

from casino_server.engines import three_card_poker as tcp
from casino_server.engines.hand_evaluator import FLUSH, PAIR, STRAIGHT, THREE_OF_A_KIND

LINES_FILE = Path(__file__).with_name("dealer_lines.toml")
_RANK_NAMES = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}


def hand_phrase(hand_eval) -> str:
    """'Queen high', 'Pair of 7s', 'Straight', 'Royal Flush'."""
    _, name, tiebreak = hand_eval
    if name == "High Card":
        return f"{_RANK_NAMES.get(tiebreak[0], tiebreak[0])} high"
    if name == "Pair":
        return f"Pair of {_RANK_NAMES.get(tiebreak[0], tiebreak[0])}s"
    return tcp.hand_label(hand_eval)


class DealerLines:
    def __init__(self, path: Path = LINES_FILE, rng: random.Random | None = None):
        self.path = path
        self.rng = rng or random.Random()
        self._data: dict = {}
        self._mtime = None

    def _lines(self) -> dict:
        try:
            mtime = self.path.stat().st_mtime
            if mtime != self._mtime:
                self._data = tomllib.loads(self.path.read_text())
                self._mtime = mtime
        except (OSError, tomllib.TOMLDecodeError) as e:
            if not self._data:
                print(f"dealer lines unavailable ({e}); the dealer will be quiet")
        return self._data

    def say(self, section: str, key: str, **values) -> str:
        options = self._lines().get(section, {}).get(key, [])
        usable = []
        for line in options if isinstance(options, list) else []:
            try:
                usable.append(str(line).format(**values))
            except (KeyError, IndexError, ValueError):
                continue  # needs a placeholder we don't have here
        return self.rng.choice(usable) if usable else ""

    def chance(self, key: str, default: float) -> float:
        try:
            return float(self._lines().get("chance", {}).get(key, default))
        except (TypeError, ValueError):
            return default

    def announce(self, result: tcp.HandResult, name: str, held: bool) -> str:
        """What the dealer says as a player's hand is turned over."""
        hand = hand_phrase(result.player_eval)
        if held:  # a fold kept alive by a winning Prime
            colour = "All red" if result.player_cards[0].color == "red" else "All black"
            return self.say("announce", "prime", hand=hand, name=name, colour=colour)
        rank = result.player_eval[0]
        if result.outcome == "win":
            text = self.say("announce", "win", hand=hand, name=name)
            tier = "monster" if rank >= THREE_OF_A_KIND else "strong" if rank in (STRAIGHT, FLUSH) else "ordinary"
            return self._react(text, "win", tier, name)
        if result.outcome == "lose":
            text = self.say("announce", "lose", hand=hand, name=name)
            return self._react(text, "lose", "strong" if rank >= PAIR else "ordinary", name)
        key = "no_qualify" if result.outcome == "dealer_no_qualify" else "push"
        return self.say("announce", key, hand=hand, name=name)

    def _react(self, text: str, section: str, tier: str, name: str) -> str:
        if self.rng.random() < self.chance(f"{section}_{tier}", 0.0):
            reaction = self.say(section, tier, name=name)
            if reaction:
                return f"{text} {reaction}" if text else reaction
        return text
