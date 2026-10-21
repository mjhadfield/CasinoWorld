"""
Craps, Vegas rules: the bet catalogue, how a roll decides every bet, and the
dice's choreographed throw, in integer pence. Signed off on Mike's Craps
mockup (v1).

Every bet has an id (the "spot" its chips are on):

  pass, dont_pass            Pass Line / Don't Pass Bar 12            1 to 1
  pass_odds, dont_odds       odds behind them once the point is on   true odds
  come, dont_come            the same for a new point, any roll after the come-out
  come_N, dcome_N            a come / don't come bet that has travelled to N
  come_odds_N, dcome_odds_N  odds on those                            true odds
  place_N                    4/10 9 to 5, 5/9 7 to 5, 6/8 7 to 6
  buy_N                      true odds; the vig (5% of the bet) comes out of a win
  lay_N                      true odds against; the vig (5% of the win) is paid up front
  field                      3, 4, 9, 10, 11 even money; 2 double, 12 triple
  big6, big8                 even money
  hard4 .. hard10            4/10 7 to 1, 6/8 9 to 1
  any7, any_craps, two, three, eleven, twelve, horn, ce   one-roll props

N is a point number (4, 5, 6, 8, 9, 10). Odds go up to 3-4-5x (lay odds 6x).
Place and buy bets, hardways and come odds are off on the come-out unless the
player marks them working; lay bets, Big 6/8 and the props always work.
Winning bets stay up and only the winnings come back -- except come bets and
odds, which come back with them.

The house pays in whole chips, as a casino does: a payout that isn't whole
pounds is paid down to the pound and the change stays with the house. Bets made
in their proper units (unit()) never lose anything that way; the client steps
your chips in them, and the NPCs bet in them. The vig is whole pounds too: £1
for every £20, rounded down, and never less than £1 (vig()). A buy bet's comes
out of the win; a lay bet's is paid with the bet, up front, and once it's won
the next one comes out of the win to keep it up -- so either way each decision
costs one vig.

There's no craps in Casino v2, so this is checked against the arithmetic (see
the tests: every bet's exact house edge against the published one).
"""
import math
import random
from dataclasses import dataclass

GAME_KEY = "craps"
GAME_LABEL = "Craps"

NUMBERS = (4, 5, 6, 8, 9, 10)
ODDS_X = {4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3}   # 3-4-5x odds
LAY_ODDS_X = 6                                   # (lay odds win at most 3-4-5x too)
MIN_MAIN = 500                                   # £5 on the line, come, field, Big 6/8, place, buy, lay
MIN_PROP = 100                                   # £1 on the hardways and props
MAX_FLAT = 50_000
MAX_PROP = 10_000
HARDWAYS = ("hard4", "hard6", "hard8", "hard10")
PROPS = ("any7", "any_craps", "two", "three", "eleven", "twelve", "horn", "ce")
SPOTS = (("pass", "pass_odds", "dont_pass", "dont_odds", "come", "dont_come", "field", "big6", "big8")
         + tuple(f"{kind}_{n}" for kind in ("place", "buy", "lay", "come", "come_odds", "dcome", "dcome_odds")
                 for n in NUMBERS)
         + HARDWAYS + PROPS)
WORDS = {2: "Aces", 3: "Ace-deuce", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
         10: "Ten", 11: "Yo-leven", 12: "Twelve"}


def money(pence: int) -> str:
    return f"£{pence // 100:,}" if pence % 100 == 0 else f"£{pence / 100:,.2f}"


def number_of(spot: str) -> int | None:
    tail = spot.rsplit("_", 1)[-1]
    if tail.isdigit():
        return int(tail)
    if spot.startswith(("hard", "big")):
        return int(spot[4:] if spot.startswith("hard") else spot[3:])
    return None


def is_travelled(spot: str) -> bool:
    """A come or don't come bet sitting on its number (it got there by itself)."""
    return spot.startswith(("come_", "dcome_")) and "odds" not in spot


def is_prop(spot: str) -> bool:
    return spot in PROPS or spot in HARDWAYS


def off_on_come_out(spot: str) -> bool:
    return spot.startswith(("place_", "buy_", "hard", "come_odds_"))


# ---------------------------------------------------------------- what bets pay
def true_odds(n: int, amount: int) -> int:
    return 2 * amount if n in (4, 10) else amount * 3 // 2 if n in (5, 9) else amount * 6 // 5


def lay_odds(n: int, amount: int) -> int:
    return amount // 2 if n in (4, 10) else amount * 2 // 3 if n in (5, 9) else amount * 5 // 6


def place_pays(n: int, amount: int) -> int:
    return amount * 9 // 5 if n in (4, 10) else amount * 7 // 5 if n in (5, 9) else amount * 7 // 6


def pounds(pence: int) -> int:
    """Paid down to whole chips: the change stays with the house."""
    return pence // 100 * 100


def vig(pence: int) -> int:
    """5% in whole pounds: £1 for every £20, rounded down, at least £1 (nothing on nothing)."""
    return max(100, pence // 2000 * 100) if pence > 0 else 0


def buy_vig(amount: int) -> int:
    return vig(amount)


def lay_vig(n: int, amount: int) -> int:
    return vig(pounds(lay_odds(n, amount)))


def vig_up_front(bets: dict) -> int:
    """The vig that goes with these bets when they're paid for (the lay bets')."""
    return sum(lay_vig(number_of(spot), a) for spot, a in bets.items() if a and spot.startswith("lay_"))


def unit(spot: str, point: int | None = None) -> int:
    """A bet's proper unit: in multiples of it, its payout (and vig) is whole pounds. Mirrored
    in crp_table.gd's unit()."""
    n = point if spot in ("pass_odds", "dont_odds") else number_of(spot)
    if spot.startswith("place_"):
        return 600 if n in (6, 8) else 500
    if spot.startswith(("buy_", "pass_odds", "come_odds_")) and n:
        return {4: 100, 10: 100, 5: 200, 9: 200, 6: 500, 8: 500}[n]
    if spot.startswith(("lay_", "dont_odds", "dcome_odds_")) and n:
        return {4: 200, 10: 200, 5: 300, 9: 300, 6: 600, 8: 600}[n]
    return {"horn": 400, "ce": 200}.get(spot, 100)


def proper(spot: str, amount: int, point: int | None = None) -> int:
    """`amount` paid down to the bet's proper unit (at least one unit)."""
    u = unit(spot, point)
    return max(u, amount // u * u)


@dataclass(frozen=True)
class Outcome:
    kind: str               # "win" | "lose" | "return" (the stake comes back) | "move" (to its number)
    win: int = 0            # what's paid, after any vig
    stays: bool = True      # a winning bet's stake stays up (False: it comes back with the winnings)
    to: str | None = None   # where a moving come bet goes
    vig: int = 0            # the vig the dealer takes out of the win


def resolve(bets: dict, d1: int, d2: int, point: int | None, working: bool = False) -> dict:
    """What this roll does to each bet: {spot: Outcome}. Bets it doesn't touch are left out."""
    t = d1 + d2
    hard = d1 == d2
    come_out = point is None
    out = {}
    for spot, a in bets.items():
        if not a:
            continue
        n = number_of(spot)
        o = None
        if spot == "pass":
            if come_out:
                o = Outcome("win", a) if t in (7, 11) else Outcome("lose") if t in (2, 3, 12) else None
            else:
                o = Outcome("win", a) if t == point else Outcome("lose") if t == 7 else None
        elif spot == "pass_odds":
            o = Outcome("win", true_odds(point, a), False) if t == point else Outcome("lose") if t == 7 else None
        elif spot == "dont_pass":
            if come_out:
                o = Outcome("win", a) if t in (2, 3) else Outcome("lose") if t in (7, 11) else None
            else:
                o = Outcome("win", a) if t == 7 else Outcome("lose") if t == point else None
        elif spot == "dont_odds":
            o = Outcome("win", lay_odds(point, a), False) if t == 7 else Outcome("lose") if t == point else None
        elif spot == "come":
            o = (Outcome("win", a) if t in (7, 11) else Outcome("lose") if t in (2, 3, 12)
                 else Outcome("move", to=f"come_{t}"))
        elif spot == "dont_come":
            o = (Outcome("win", a) if t in (2, 3) else Outcome("lose") if t in (7, 11)
                 else None if t == 12 else Outcome("move", to=f"dcome_{t}"))
        elif spot.startswith("come_odds_"):
            if come_out and not working:
                o = Outcome("return") if t in (n, 7) else None
            else:
                o = Outcome("win", true_odds(n, a), False) if t == n else Outcome("lose") if t == 7 else None
        elif spot.startswith("dcome_odds_"):
            o = Outcome("win", lay_odds(n, a), False) if t == 7 else Outcome("lose") if t == n else None
        elif spot.startswith("come_"):
            o = Outcome("win", a, False) if t == n else Outcome("lose") if t == 7 else None
        elif spot.startswith("dcome_"):
            o = Outcome("win", a, False) if t == 7 else Outcome("lose") if t == n else None
        elif spot == "field":
            o = (Outcome("win", a) if t in (3, 4, 9, 10, 11) else Outcome("win", 2 * a) if t == 2
                 else Outcome("win", 3 * a) if t == 12 else Outcome("lose"))
        elif spot in ("big6", "big8"):
            o = Outcome("win", a) if t == n else Outcome("lose") if t == 7 else None
        elif spot.startswith("place_"):
            if not come_out or working:
                o = Outcome("win", place_pays(n, a)) if t == n else Outcome("lose") if t == 7 else None
        elif spot.startswith("buy_"):
            if not come_out or working:
                v = buy_vig(a)
                o = Outcome("win", pounds(true_odds(n, a)) - v, vig=v) if t == n else Outcome("lose") if t == 7 else None
        elif spot.startswith("lay_"):   # (the next decision's vig, to keep it up)
            v = lay_vig(n, a)
            o = Outcome("win", pounds(lay_odds(n, a)) - v, vig=v) if t == 7 else Outcome("lose") if t == n else None
        elif spot in HARDWAYS:
            if not come_out or working:
                if t == n and hard:
                    o = Outcome("win", (7 if n in (4, 10) else 9) * a)
                elif t in (n, 7):
                    o = Outcome("lose")
        elif spot == "any7":
            o = Outcome("win", 4 * a) if t == 7 else Outcome("lose")
        elif spot == "any_craps":
            o = Outcome("win", 7 * a) if t in (2, 3, 12) else Outcome("lose")
        elif spot in ("two", "twelve"):
            o = Outcome("win", 30 * a) if t == (2 if spot == "two" else 12) else Outcome("lose")
        elif spot in ("three", "eleven"):
            o = Outcome("win", 15 * a) if t == (3 if spot == "three" else 11) else Outcome("lose")
        elif spot == "horn":   # a quarter on each of 2, 3, 11 and 12
            o = (Outcome("win", 27 * a // 4) if t in (2, 12) else Outcome("win", 3 * a) if t in (3, 11)
                 else Outcome("lose"))
        elif spot == "ce":     # half on any craps, half on 11
            o = Outcome("win", 3 * a) if t in (2, 3, 12) else Outcome("win", 7 * a) if t == 11 else Outcome("lose")
        if o is not None:
            out[spot] = o if o.kind != "win" or o.vig else Outcome(o.kind, pounds(o.win), o.stays, o.to)
    return out


def advance_point(point: int | None, total: int) -> tuple[int | None, str]:
    """The point after this roll, and what happened: point_set, point_made, seven_out,
    natural (7 or 11 coming out), craps (2, 3 or 12 coming out) or roll (nothing to the line)."""
    if point is None:
        if total in NUMBERS:
            return total, "point_set"
        return None, "natural" if total in (7, 11) else "craps"
    if total == point:
        return None, "point_made"
    if total == 7:
        return None, "seven_out"
    return point, "roll"


def call_words(d1: int, d2: int) -> str:
    """How the stickman names a roll: "Hard eight", "Six, easy six", "Yo-leven"."""
    t = d1 + d2
    if t in (4, 6, 8, 10):
        return f"Hard {WORDS[t].lower()}" if d1 == d2 else f"{WORDS[t]}, easy {WORDS[t].lower()}"
    return WORDS[t]


# ---------------------------------------------------------------- what can go down or come off
def removable(spot: str, point: int | None) -> bool:
    """Contract bets stay until decided: a Pass Line bet once the point is on, come bets on their numbers."""
    if spot == "pass":
        return point is None
    return not (spot.startswith("come_") and "odds" not in spot)   # (a don't bet can always come down)


def check(bets: dict, spot: str, old: int, new: int, point: int | None) -> str | None:
    """Whether one spot can go from `old` to `new` (with `bets` the seat's bets after the
    change). Returns what's wrong, or None."""
    n = number_of(spot)
    if new < old and not removable(spot, point):
        return "That's a contract bet now: it stays until it's decided."
    if new > old:
        if is_travelled(spot):
            return "Come bets move to their numbers by themselves -- bet the Come instead."
        if spot in ("pass", "dont_pass") and point is not None:
            return "The point is on: put odds behind your line bet instead."
        if spot in ("come", "dont_come") and point is None:
            return "Come bets go down once a point is on. On the come-out, bet the Pass Line."
        if spot in ("pass_odds", "dont_odds") and point is None:
            return "Odds go down once the point is on."
        if spot.startswith("place_") and bets.get(f"buy_{n}"):
            return f"You've bought the {n}. Take that down to place it instead."
        if spot.startswith("buy_") and bets.get(f"place_{n}"):
            return f"You've placed the {n}. Take that down to buy it instead."
    # Odds can't be more than their bet allows (whichever way the change went).
    caps = {"pass_odds": ("pass", ODDS_X.get(point, 0)), "dont_odds": ("dont_pass", LAY_ODDS_X)}
    for m in NUMBERS:
        caps[f"come_odds_{m}"] = (f"come_{m}", ODDS_X[m])
        caps[f"dcome_odds_{m}"] = (f"dcome_{m}", LAY_ODDS_X)
    for odds, (base, x) in caps.items():
        if bets.get(odds, 0) > bets.get(base, 0) * x:
            if odds == spot:
                if not bets.get(base):
                    return "There's no bet there for odds to go on."
                return f"Odds are capped at {x}x the bet there ({money(bets[base] * x)})."
            return "Take the odds down first."
    if new > 0 and new != old and "odds" not in spot:
        low, high = (MIN_PROP, MAX_PROP) if is_prop(spot) else (MIN_MAIN, MAX_FLAT)
        if new < low:
            return f"The minimum there is {money(low)}."
        if new > high:
            return f"The table limit there is {money(high)}."
    return None


# ---------------------------------------------------------------- where the chips are
# The dice bounce off chips, so the server needs to know where the client draws each
# seat's stack: this mirrors crp_table.gd's spot_pos() (table coordinates, see below).
RAIL_X = (164, 128, 92, 56, -56, -92, -128, -164)   # the standing spots (crp_table.tscn's Seat markers)
BOX_W = 124 / 6
PROP_AT = {"any7": (0, -102.75), "hard6": (-19, -93), "hard10": (19, -93), "hard8": (-19, -80), "hard4": (19, -80),
           "two": (-19, -66), "twelve": (19, -66), "three": (-19, -53.5), "eleven": (19, -53.5),
           "any_craps": (0, -42.5), "horn": (-19, -32), "ce": (19, -32)}   # the prop box's rows' centres
PAYOUT_AT = (4.5, -3.5)            # where the dealer puts winnings, from the bet


def chip_pos(seat: int, spot: str) -> tuple[float, float]:
    h = 1 if seat < 4 else -1
    x = RAIL_X[seat]
    rank = 3 - seat % 4
    fan = (rank - 1.5) * 4.4

    def within(a, b):   # x, kept inside an end's box that runs from a to b (right-hand end's x)
        return max(min(a * h, b * h), min(max(a * h, b * h), x))

    fixed = {"pass": (x, -20), "pass_odds": (x, -7.5), "dont_pass": (within(44, 142), -32),
             "dont_odds": (within(44, 142) + 6, -34), "come": (within(46, 162), -72),
             "dont_come": (49 * h + (rank - 1.5) * 2.2, -97), "field": (within(44, 142), -48),
             "big6": (159 * h + (rank - 1.5) * 2.2, -50.5), "big8": (159 * h + (rank - 1.5) * 2.2, -34.5)}
    if spot in fixed:
        return fixed[spot]
    if spot in PROP_AT:
        px, py = PROP_AT[spot]
        return px + (7 - seat - 3.5) * 3.6, py + 1
    n = number_of(spot)
    cx = (60 if h == 1 else -184) + NUMBERS.index(n) * BOX_W + BOX_W / 2 + fan
    for prefix, dx, y in (("lay_", 0, -113.5), ("dcome_odds_", 1.4, -113), ("dcome_", 0, -111.5),
                          ("come_odds_", 1.4, -107), ("come_", 0, -105.5), ("buy_", 0, -91)):
        if spot.startswith(prefix):
            return cx + dx, y
    return cx, -99   # place


def chips_on_table(seat_bets: dict) -> list[tuple[float, float]]:
    """Every stack on the layout: {seat: bets} -> [(x, y), ...]."""
    return [chip_pos(seat, spot) for seat, bets in seat_bets.items() for spot, a in bets.items() if a]


OFF_BUTTON_AT = (2.6, -3.4)        # the dealer's OFF button on a bet that's off this come-out, from the bet


def off_buttons(seat_bets: dict, working: dict) -> list[tuple[float, float]]:
    """The OFF buttons on the layout coming out: {seat: bets}, {seat: working} -> [(x, y), ...]."""
    return [(x + OFF_BUTTON_AT[0], y + OFF_BUTTON_AT[1]) for seat, bets in seat_bets.items() if not working.get(seat)
            for spot, a in bets.items() if a and off_on_come_out(spot) for x, y in [chip_pos(seat, spot)]]


def pucks_at(point: int | None) -> list[tuple[float, float]]:
    """Where the two pucks sit (crp_table.gd's _puck_target): ON on the point's box, or OFF
    in the Don't Come box, at each end."""
    if point is None:
        return [(49.0 * h, -106.0) for h in (1, -1)]
    return [((60 if h == 1 else -184) + NUMBERS.index(point) * BOX_W + BOX_W / 2, -102.0) for h in (1, -1)]


def puck_slide(was: int | None, now: int | None) -> list[tuple[float, float]]:
    """The pucks' way from one place to the other after a roll, while the dice are still lying
    there: points every few units along it (just the two places when it doesn't move)."""
    out = []
    for (x0, y0), (x1, y1) in zip(pucks_at(was), pucks_at(now)):
        steps = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / 3))
        out += [(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps) for k in range(steps + 1)]
    return out


# ---------------------------------------------------------------- the throw
# The dice are choreographed, like the roulette ball: the faces are drawn first,
# then plan_throw() lays out the path that brings each die to rest on its face --
# an arc across the table from the shooter's hand, into the far wall's rubber
# pyramids, back off them, a small hop and a slide. Low down (off the wall, the hop,
# the slide) a die that runs into a stack of chips or a puck bounces off it, and it
# never comes to rest on one (or where winnings will be put down beside one, or where
# a puck is about to slide). Everyone sees the same throw; the client (craps_dice.gd)
# just plays the plan back.
#
# Table coordinates, as the client draws the table: x across (0 at the middle),
# y up the table (0 at the players' edge of the felt, the far edge at -121).
# Seat 0 is the right-hand end of the near rail; the dice go round clockwise, 0 -> 7.
WALL_X = 183.5                    # the inside face of the pyramids at each end
FELT_Y = (-111.0, -15.0)          # where the dice may come to rest
HAND_Y = -13.0                    # the shooter's hand, reaching in clear of the heads at the rail (CrapsDice.HAND_Y)
HIT = 6.6                         # a die's middle comes no closer than this to a stack's (chip 3.3 + die 3.3)
PUCK_HIT = 7.7                    # ...or to a puck's (puck 4.4 + die 3.3)
BUTTON_HIT = 5.2                  # ...or to an OFF button's (button 1.9 + die 3.3)


def _first_hit(x, y, dx, dy, solids):
    """Where a die moving from (x, y) by (dx, dy) first touches one of `solids` [(x, y, reach)]:
    (fraction, nx, ny) with the contact's normal, or None."""
    best = None
    a = dx * dx + dy * dy
    if a < 1e-9:
        return None
    for cx, cy, reach in solids:
        ox, oy = x - cx, y - cy
        b = 2 * (ox * dx + oy * dy)
        c = ox * ox + oy * oy - reach * reach
        if c < 0:      # already touching: only a move further in counts, and it's stopped at once
            if b < 0:
                f = 0.0
            else:
                continue
        else:
            disc = b * b - 4 * a * c
            if disc < 0:
                continue
            f = (-b - math.sqrt(disc)) / (2 * a)
            if not 0 <= f <= 1:
                continue
        if best is None or f < best[0]:
            hx, hy = x + dx * f - cx, y + dy * f - cy
            d = math.hypot(hx, hy) or 1.0
            best = (f, hx / d, hy / d)
    return best


def plan_throw(shooter: int, faces: tuple, rng: random.Random, chips: list | None = None,
               payouts: list | None = None, pucks: list | None = None, puck_way: list | None = None,
               buttons: list | None = None, buttons_after: list | None = None) -> list:
    """Each die's path: a list of segments {k: "air"|"slide", t0, t1, x0, y0, x1, y1, h
    (an arc's height), f (the face showing), r0, r1 (its turn), kn (how hard it knocks
    something at the end, 0-1)}. The last two segments show the drawn face. `chips` are
    the stacks on the layout, `pucks` where the pucks are and `buttons` the OFF buttons on
    them, to bounce off; the dice don't stop on those, `payouts`, `puck_way` (where the pucks
    will slide once it's called) or `buttons_after` (the OFF buttons that will be up then)."""
    solids = ([(x, y, HIT) for x, y in chips or []] + [(x, y, PUCK_HIT) for x, y in pucks or []]
              + [(x, y, BUTTON_HIT) for x, y in buttons or []])
    keep_clear = (solids + [(x, y, HIT) for x, y in payouts or []]
                  + [(x, y, PUCK_HIT) for x, y in puck_way or []] + [(x, y, BUTTON_HIT) for x, y in buttons_after or []])
    to_left = shooter < 4            # right-hand players throw to the left-hand end, and vice versa
    d = -1 if to_left else 1
    wall = d * WALL_X
    from_x = RAIL_X[shooter] + 2 * (1 if shooter < 4 else -1)
    clamp = lambda y: max(FELT_Y[0], min(FELT_Y[1], y))
    u = rng.uniform
    best = None
    for attempt in range(60):
        plans = []
        clear = True
        for i in range(2):
            segs = []
            state = {"x": from_x + (3 if i else -3) * d, "y": HAND_Y - (0 if i else 3), "t": 0.0,
                     "f": rng.randint(1, 6), "r": u(0, 6.28)}
            spin = u(8, 13) * rng.choice((-1, 1))

            def go(kind, x1, y1, dur, h, face=None, kn=0.0):
                if face is None:
                    face = rng.choice([k for k in range(1, 7) if k != state["f"]])
                r1 = state["r"] + spin * dur * (0.25 if kind == "slide" else 1)
                segs.append({"k": kind, "t0": round(state["t"], 3), "t1": round(state["t"] + dur, 3),
                             "x0": round(state["x"], 2), "y0": round(state["y"], 2), "x1": round(x1, 2),
                             "y1": round(y1, 2), "h": round(h, 2), "f": face, "r0": round(state["r"], 3),
                             "r1": round(r1, 3), "kn": kn})
                state.update(x=x1, y=y1, t=state["t"] + dur, f=face, r=r1)

            def low(kind, x1, y1, dur, h, kn, face=None):
                """A move along the felt (or just off it) that bounces off any stack in its way."""
                dx, dy = x1 - state["x"], y1 - state["y"]
                for _ in range(4):
                    hit = _first_hit(state["x"], state["y"], dx, dy, solids)
                    if hit is None:
                        break
                    f, nx, ny = hit
                    if f > 0.02:
                        go(kind, state["x"] + dx * f, state["y"] + dy * f, max(dur * f, 0.04), h * f, face, 0.5)
                    rest = 1 - f
                    dot = dx * nx + dy * ny
                    dx, dy = (dx - 2 * dot * nx) * rest * 0.6, (dy - 2 * dot * ny) * rest * 0.6
                    dur, h = max(dur * rest * 0.85, 0.08), h * 0.5
                    if kind == "air":
                        h = max(h, 0.6)
                ex = max(-WALL_X, min(WALL_X, state["x"] + dx))
                go(kind, ex, clamp(state["y"] + dy), dur, h, face, kn)

            go("air", wall - d * u(42, 72), u(-95, -31), u(0.58, 0.7), u(20, 27), kn=1.0)
            if any(math.hypot(state["x"] - cx, state["y"] - cy) < reach for cx, cy, reach in solids):
                clear = False   # (it would come down on a stack or a puck: throw again)
            go("air", wall, clamp(state["y"] + u(-14, 14)), u(0.17, 0.23), u(5, 8), kn=1.0)
            low("air", wall - d * u(14, 24), clamp(state["y"] + u(-10, 10)), u(0.2, 0.26), u(3.5, 6), 0.6)
            low("air", state["x"] - d * u(6, 12), clamp(state["y"] + u(-6, 6)), u(0.14, 0.18), u(1.4, 2.4), 0.35,
                faces[i])
            low("slide", state["x"] - d * u(3, 8), clamp(state["y"] + u(-3, 3)), u(0.3, 0.42), 0.0, 0.0, faces[i])
            plans.append(segs)
        a, b = plans[0][-1], plans[1][-1]
        apart = math.hypot(a["x1"] - b["x1"], a["y1"] - b["y1"])
        crowded = sum(math.hypot(s["x1"] - cx, s["y1"] - cy) < reach for s in (a, b) for cx, cy, reach in keep_clear)
        score = (not clear) + crowded + (apart < 9) + sum(d * s["x1"] < 100 for s in (a, b))
        if best is None or score < best[0]:
            best = (score, plans)
        if score == 0:
            break
    return best[1]


def throw_seconds(plan: list) -> float:
    return max(segs[-1]["t1"] for segs in plan)


def resting(plan: list) -> list:
    """Where each die ends up: [[x, y, face, turn], ...]."""
    return [[segs[-1]["x1"], segs[-1]["y1"], segs[-1]["f"], segs[-1]["r1"]] for segs in plan]


# ---------------------------------------------------------------- the paytable
def rules() -> dict:
    return {"game": GAME_KEY, "title": GAME_LABEL, "min_bet": MIN_MAIN, "odds": {str(k): v for k, v in ODDS_X.items()},
            "sections": [
                {"title": "Line bets", "rows": [["Pass Line, Come", "1 to 1"], ["Don't Pass, Don't Come (bar 12)", "1 to 1"],
                                                ["Odds 3-4-5x", "2:1, 3:2, 6:5"], ["Lay odds up to 6x", "1:2, 2:3, 5:6"]]},
                {"title": "Numbers", "rows": [["Place 6 or 8 (in £6s)", "7 to 6"], ["Place 5 or 9", "7 to 5"],
                                              ["Place 4 or 10", "9 to 5"],
                                              ["Buy: £1 vig per £20 bet, out of a win", "true odds"],
                                              ["Lay: £1 vig per £20 it wins, up front", "true odds"]]},
                {"title": "Field and Big 6/8", "rows": [["Field 3, 4, 9, 10, 11", "1 to 1"], ["Field 2", "2 to 1"],
                                                        ["Field 12", "3 to 1"], ["Big 6, Big 8", "1 to 1"]]},
                {"title": "Hardways and props", "rows": [["Hard 6 or 8", "9 to 1"], ["Hard 4 or 10", "7 to 1"],
                                                         ["Any 7", "4 to 1"], ["Any Craps", "7 to 1"], ["2 or 12", "30 to 1"],
                                                         ["3 or 11", "15 to 1"], ["Horn: 2/12, 3/11", "27:4, 3:1"],
                                                         ["C & E: craps, 11", "3:1, 7:1"]]}],
            "notes": ["Place and buy bets, hardways and come odds are off on the come-out unless you mark them Working.",
                      "Once the point is on, a Pass Line or come bet can't come down. Click the Pass Line (or just behind "
                      "it) for odds; click Don't Pass to lay odds.",
                      "The shooter needs a Pass Line or Don't Pass bet. After a seven-out the dice move clockwise.",
                      "Everything pays in whole pounds. Your chips go down in each bet's proper units "
                      "(Place 6 and 8 in £6s, a Horn in £4s) so nothing's paid down.",
                      "£5 minimum (£1 on hardways and props), £500 maximum (£100 on a prop)."]}
