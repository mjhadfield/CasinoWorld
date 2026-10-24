"""
Roulette, single zero, UK rules: the wheel, the bet catalogue and the
settlement, in integer pence.

Every bet on the layout has an id (the "spot" a chip is placed on):

  n0 .. n36           straight up                    35 to 1
  sp_A_B              split (incl. 0-1, 0-2, 0-3)    17 to 1
  st_S                street S, S+1, S+2             11 to 1
  tr_0_1_2, tr_0_2_3  trio                           11 to 1
  co_A_B              corner A, A+1, A+3, A+4 = B     8 to 1
  ff                  first four 0-1-2-3              8 to 1
  ln_S                six line S .. S+5               5 to 1
  col1 .. col3        column (col1 = 1, 4, 7 ...)     2 to 1
  doz1 .. doz3        dozen                           2 to 1
  red black odd even low high                         1 to 1

157 in all. La Partage: when 0 comes up, the even-money bets lose only half.
There's no roulette in Casino v2, so there's nothing to check this against
except the arithmetic (see the tests: every bet's expected value is -1/37,
-1/74 for the even chances).

The ball is choreographed, not simulated (see the end of this file): the
server plans its landing once the number is drawn, so the client's animation
finishes as the result is announced.
"""
import math
from dataclasses import dataclass

GAME_KEY = "roulette"
GAME_LABEL = "Roulette"

WHEEL = (0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
         5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26)
RED = frozenset({1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36})
EVEN_MONEY = ("low", "even", "red", "black", "odd", "high")
MIN_BET = 100
LIMITS = {1: 10_000, 2: 20_000, 3: 30_000, 4: 40_000, 6: 60_000, 12: 100_000, 18: 200_000}  # by numbers covered


@dataclass(frozen=True)
class Bet:
    id: str
    name: str
    numbers: tuple

    @property
    def pays(self) -> int:
        return 36 // len(self.numbers) - 1

    @property
    def limit(self) -> int:
        return LIMITS[len(self.numbers)]

    @property
    def even_money(self) -> bool:
        return len(self.numbers) == 18


def _catalogue() -> dict:
    bets = {}

    def add(bid, name, numbers):
        bets[bid] = Bet(bid, name, tuple(sorted(numbers)))

    for n in range(37):
        add(f"n{n}", f"Straight up {n}", [n])
    for k in (1, 2, 3):
        add(f"sp_0_{k}", f"Split 0/{k}", [0, k])
    for n in range(1, 37):
        if n <= 33:
            add(f"sp_{n}_{n + 3}", f"Split {n}/{n + 3}", [n, n + 3])
        if n % 3:
            add(f"sp_{n}_{n + 1}", f"Split {n}/{n + 1}", [n, n + 1])
    for s in range(1, 37, 3):
        add(f"st_{s}", f"Street {s}-{s + 1}-{s + 2}", [s, s + 1, s + 2])
    add("tr_0_1_2", "Trio 0-1-2", [0, 1, 2])
    add("tr_0_2_3", "Trio 0-2-3", [0, 2, 3])
    for a in range(1, 33):
        if a % 3:
            add(f"co_{a}_{a + 4}", f"Corner {a}/{a + 1}/{a + 3}/{a + 4}", [a, a + 1, a + 3, a + 4])
    add("ff", "First four 0-1-2-3", [0, 1, 2, 3])
    for s in range(1, 32, 3):
        add(f"ln_{s}", f"Six line {s}-{s + 5}", range(s, s + 6))
    for k in (1, 2, 3):
        add(f"col{k}", f"{('1st', '2nd', '3rd')[k - 1]} column", range(k, 37, 3))
        add(f"doz{k}", f"{('1st', '2nd', '3rd')[k - 1]} dozen", range(12 * k - 11, 12 * k + 1))
    add("red", "Red", RED)
    add("black", "Black", [n for n in range(1, 37) if n not in RED])
    add("odd", "Odd", range(1, 37, 2))
    add("even", "Even", range(2, 37, 2))
    add("low", "1-18", range(1, 19))
    add("high", "19-36", range(19, 37))
    return bets


BETS = _catalogue()
SPOTS = tuple(BETS)


def colour(number: int) -> str:
    return "green" if number == 0 else "red" if number in RED else "black"


def describe(number: int) -> str:
    """'17, black, odd, low' -- or 'Zero'."""
    if number == 0:
        return "Zero"
    return f"{number}, {colour(number)}, {'odd' if number % 2 else 'even'}, {'low' if number <= 18 else 'high'}"


def settle(number: int, bets: dict) -> dict:
    """What each bet returns (stake included; 0 = lost) when the ball lands on `number`."""
    returns = {}
    for spot, stake in bets.items():
        if stake <= 0:
            continue
        bet = BETS[spot]
        if number in bet.numbers:
            returns[spot] = stake * (bet.pays + 1)
        elif number == 0 and bet.even_money:
            returns[spot] = stake // 2  # La Partage
        else:
            returns[spot] = 0
    return returns


def rules() -> dict:
    return {"game": GAME_KEY, "title": GAME_LABEL, "wheel": list(WHEEL), "red": sorted(RED),
            "la_partage": True, "min_bet": MIN_BET, "limits": {str(k): v for k, v in LIMITS.items()},
            "sections": [{"title": "Inside bets", "rows": [["Straight up", "35:1"], ["Split", "17:1"],
                                                            ["Street, Trio", "11:1"], ["Corner, First four", "8:1"],
                                                            ["Six line", "5:1"]]},
                         {"title": "Outside bets", "rows": [["Column, Dozen", "2:1"],
                                                             ["Red/Black, Odd/Even, 1-18/19-36", "1:1"]]}],
            "notes": ["Single zero. La Partage: when 0 comes up, the even-money bets lose only half.",
                      "The middle of a box is a straight up; a side, a split; a corner, a corner; the bottom edge "
                      "of the 1-4-7 row, a street (between two streets, a six line).",
                      "Bets stay open for the first few seconds of the spin.",
                      "£1 a bet. At most £100 straight up, £200 a split, up to £2,000 on the even chances."]}


# ---------------------------------------------------------------- the ball
# The ball is choreographed, and every viewer sees the same one. The spin sends
# the ball's launch angle relative to the rotor; it then rolls round the track
# against the wheel, slowing evenly from LAUNCH_SPEED, and reaches the pockets
# BALL_TRACK seconds later at ARRIVAL_SPEED (against the wheel) -- so where it
# arrives is known from the launch (arrival_pocket), though not the number. That
# is drawn at "No more bets", just before the ball arrives, and plan_landing()
# works out the landing that carries the ball from where it arrives to the
# winning pocket: one to three skids over the frets, slowing, then a few small
# hops (the odd one back off a fret), anything from a short stop to most of a lap.
# The client (roulette_wheel.gd) runs the same arithmetic: keep the two in step.

POCKETS = 37
STEP = 2 * math.pi / POCKETS
BALL_TRACK = 7.6         # seconds from launch until the ball reaches the pockets (6.0 on the track, 1.6 down the bowl)
OMEGA = 0.55             # the rotor, rad/s
LAUNCH_SPEED = 9.0       # the ball leaving the dealer's fingers, rad/s
ARRIVAL_SPEED = 14.0     # pockets a second against the wheel as it reaches them
SKID_GAP, HOP_GAP, SETTLE = 0.04, 0.06, 0.4
SKID_END = 2.5          # pockets a second as the last skid ends
HOP_TAILS = ((-1, 2, 1, -1, 1), (-1, 1, 1), (2, -1, 1, -1), (1, -1, 1), (-2, 1, 1, -1, 1), (1, 1, -1, 1))
SKID_SPLITS = ((1.0,), (0.62, 0.38), (0.48, 0.32, 0.2))


def track_travel(t: float) -> float:
    """How far round the ball has gone (radians, against the wheel) t spin-seconds after launch."""
    end_speed = ARRIVAL_SPEED * STEP - OMEGA
    decel = (LAUNCH_SPEED - end_speed) / BALL_TRACK
    return LAUNCH_SPEED * t - 0.5 * decel * t * t


def arrival_pocket(ball_rel: float, scale: float = 1.0) -> float:
    """Where on the rotor (in pockets, 0 = the zero's pocket) the ball reaches the pockets,
    given its launch angle relative to the rotor. `scale` is a sped-up server's time factor."""
    rel = ball_rel - track_travel(BALL_TRACK) - OMEGA * BALL_TRACK * scale
    return ((rel + math.pi / 2) / STEP) % POCKETS


def plan_landing(arrival: float, number: int, rng) -> list:
    """The landing from `arrival` (pockets) to `number`'s pocket: [[kind, pockets, seconds]],
    kind "s" (a skid) or "h" (a hop); positive pockets are onward."""
    onward = (arrival - WHEEL.index(number)) % POCKETS
    if onward < 4.0:
        onward += POCKETS      # it needs some distance to lose its speed: round once more
    tail = list(rng.choice(HOP_TAILS))
    skids = onward - sum(tail)
    split = SKID_SPLITS[0 if skids <= 8 else 1 if skids <= 22 else 2]
    # The skids slow the ball evenly over their whole distance, from ARRIVAL_SPEED to SKID_END
    # (each fret it clips between skids takes a little more off).
    plan = []
    v = ARRIVAL_SPEED
    covered = 0.0
    for f in split:
        length = skids * f
        covered += length
        v1 = math.sqrt(max(SKID_END ** 2, ARRIVAL_SPEED ** 2 - (ARRIVAL_SPEED ** 2 - SKID_END ** 2) * covered / skids))
        v1 = min(v1, 0.9 * v)
        plan.append(["s", round(length, 4), round(2 * length / (v + v1), 4)])
        v = v1 * 0.85
    for length in tail:
        plan.append(["h", length, round(0.16 + 0.17 * abs(length), 4)])
    return plan


def landing_seconds(plan: list) -> float:
    """How long a landing takes, from reaching the pockets to coming to rest."""
    total = SETTLE
    for i, (kind, _, d) in enumerate(plan):
        total += (SKID_GAP if i else 0.0) if kind == "s" else HOP_GAP
        total += d
    return total
