"""
Baccarat engine (Punto Banco), ported from Casino v2's games/baccarat/logic.py.

Same rules and paytables as v2, with these changes:
  - Money is integer pence (the Banker's 5% commission rounds down to the penny).
  - One coup is dealt for the whole table; every seat's bets ride on it.

Card points: Ace 1, 2-9 face value, 10/J/Q/K 0; a hand's total is the sum
mod 10. Player and Banker get two cards each; a natural (8 or 9 on two cards)
on either side stands both. Otherwise the Player draws on 0-5, and the
Banker draws by the standard table (on 0-5 if the Player stood). The higher
total wins:
  Player 1:1; Banker 1:1 less 5% commission; both push on a tie.
  Tie 8:1 (loses otherwise).
  Dragon Bonus (Player Dragon / Banker Dragon): your side's natural win pays
  1:1; a natural tie pushes; otherwise a win by 9 pays 30:1, 8 10:1, 7 6:1,
  6 4:1, 5 2:1, 4 1:1 -- anything less, or a loss, loses.
  5 Treasures (judged on the coup alone): Fortune 7 (Banker three-card 7)
  40:1, Golden 8 (Player three-card 8) 25:1, Heavenly 9 (both three-card 9s
  75:1, either 10:1), Blazing 7s (both three-card 7s 200:1, both two-card
  7s 50:1), Cover All (any of those) 6:1.
"""
from dataclasses import dataclass, field

GAME_KEY = "baccarat"
GAME_LABEL = "Baccarat"
MAIN_SPOTS = ("player", "banker", "tie")
DRAGON_SPOTS = ("player_dragon", "banker_dragon")
TREASURE_SPOTS = ("fortune_7", "golden_8", "heavenly_9", "blazing_7s", "cover_all")
ALL_SPOTS = MAIN_SPOTS + DRAGON_SPOTS + TREASURE_SPOTS
POINTS = {**{r: int(r) for r in "23456789"}, "10": 0, "J": 0, "Q": 0, "K": 0, "A": 1}
_ALL = set(range(10))
BANKER_DRAWS = {0: _ALL, 1: _ALL, 2: _ALL, 3: _ALL - {8}, 4: {2, 3, 4, 5, 6, 7}, 5: {4, 5, 6, 7}, 6: {6, 7}, 7: set()}
DRAGON_MARGIN = {9: 30, 8: 10, 7: 6, 6: 4, 5: 2, 4: 1}


def points(card) -> int:
    return POINTS[card.rank]


def total(cards) -> int:
    return sum(points(c) for c in cards) % 10


@dataclass
class Coup:
    player: list
    banker: list
    player_natural: bool
    banker_natural: bool
    order: list = field(default_factory=list)  # ["player"|"banker", ...] in the order the cards came out

    @property
    def player_total(self) -> int:
        return total(self.player)

    @property
    def banker_total(self) -> int:
        return total(self.banker)

    @property
    def outcome(self) -> str:
        p, b = self.player_total, self.banker_total
        return "player" if p > b else "banker" if b > p else "tie"

    @property
    def natural_tie(self) -> bool:
        return self.outcome == "tie" and self.player_natural and self.banker_natural


def deal_coup(deck) -> Coup:
    """Player, Banker, Player, Banker, then any third cards by the tableau."""
    player, banker = deck.deal(1), deck.deal(1)
    player += deck.deal(1)
    banker += deck.deal(1)
    order = ["player", "banker", "player", "banker"]
    p0, b0 = total(player), total(banker)
    coup = Coup(player, banker, p0 in (8, 9), b0 in (8, 9), order)
    if coup.player_natural or coup.banker_natural:
        return coup
    third = None
    if p0 <= 5:
        third = deck.deal(1)[0]
        player.append(third)
        order.append("player")
    banker_draws = b0 <= 5 if third is None else points(third) in BANKER_DRAWS[b0]
    if banker_draws:
        banker += deck.deal(1)
        order.append("banker")
    return coup


def _dragon(bet: int, won: bool, natural: bool, coup: Coup) -> int:
    if bet <= 0:
        return 0
    if coup.outcome == "tie":
        return bet if coup.natural_tie else 0
    if not won:
        return 0
    if natural:
        return bet * 2
    m = DRAGON_MARGIN.get(abs(coup.player_total - coup.banker_total), 0)
    return bet * (m + 1) if m else 0


def treasures(coup: Coup) -> dict:
    """Each 5 Treasures spot's multiplier for this coup (0: no hit)."""
    pn, bn, pt, bt = len(coup.player), len(coup.banker), coup.player_total, coup.banker_total
    fortune = 40 if bn == 3 and bt == 7 else 0
    golden = 25 if pn == 3 and pt == 8 else 0
    p9, b9 = pn == 3 and pt == 9, bn == 3 and bt == 9
    heavenly = 75 if p9 and b9 else 10 if p9 or b9 else 0
    blazing = 200 if pn == bn == 3 and pt == bt == 7 else 50 if pn == bn == 2 and pt == bt == 7 else 0
    cover = 6 if fortune or golden or heavenly or blazing else 0
    return {"fortune_7": fortune, "golden_8": golden, "heavenly_9": heavenly, "blazing_7s": blazing, "cover_all": cover}


def settle(coup: Coup, bets: dict) -> dict:
    """Each spot's return (stake included) for one seat's bets on this coup."""
    out = dict.fromkeys(ALL_SPOTS, 0)
    o = coup.outcome
    if bets.get("player"):
        out["player"] = bets["player"] * 2 if o == "player" else bets["player"] if o == "tie" else 0
    if bets.get("banker"):
        b = bets["banker"]
        out["banker"] = b + b * 95 // 100 if o == "banker" else b if o == "tie" else 0
    if bets.get("tie"):
        out["tie"] = bets["tie"] * 9 if o == "tie" else 0
    out["player_dragon"] = _dragon(bets.get("player_dragon", 0), o == "player", coup.player_natural, coup)
    out["banker_dragon"] = _dragon(bets.get("banker_dragon", 0), o == "banker", coup.banker_natural, coup)
    for spot, m in treasures(coup).items():
        if bets.get(spot):
            out[spot] = bets[spot] * (m + 1) if m else 0
    return out


def describe(coup: Coup) -> str:
    """'Banker wins, 7 over 4' / 'Player wins with a natural 9' / 'Tie, 6 each'."""
    p, b = coup.player_total, coup.banker_total
    if coup.outcome == "tie":
        return f"Tie, {p} each" + (" -- a natural tie" if coup.natural_tie else "")
    winner = "Player" if coup.outcome == "player" else "Banker"
    natural = coup.player_natural if coup.outcome == "player" else coup.banker_natural
    hi, lo = max(p, b), min(p, b)
    return f"{winner} wins with a natural {hi}" if natural else f"{winner} wins, {hi} over {lo}"


def rules() -> dict:
    return {"game": GAME_KEY, "title": GAME_LABEL,
            "sections": [{"title": "Main bets", "rows": [["Player", "1:1"], ["Banker", "1:1 less 5%"],
                                                          ["Tie", "8:1"]]},
                         {"title": "Dragon Bonus", "rows": [["Natural win", "1:1"], ["Win by 9", "30:1"],
                                                             ["Win by 8", "10:1"], ["Win by 7", "6:1"],
                                                             ["Win by 6", "4:1"], ["Win by 5", "2:1"],
                                                             ["Win by 4", "1:1"], ["Natural tie", "Push"]]}],
            "notes": ["One coup for the whole table: back the Player, the Banker, or a Tie.",
                      "Aces count 1, tens and pictures 0; a total is the last digit of the sum.",
                      "A natural 8 or 9 stands. Otherwise the Player draws on 0-5 and the Banker by the tableau.",
                      "Player and Banker push on a tie.",
                      "Dragon Bonus: back a side to win by a margin, or with a natural."]}
