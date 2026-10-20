"""
The base every slot shares: a 5x4 grid (cells numbered reel * 4 + row, row 0 at the top),
25 lines paying left to right, the pay table by tier in multiples of the line bet
(bet / 25), the stake ladder in pence, and the line evaluator.
"""
REELS, ROWS = 5, 4

# The 25 lines (the row on each reel), decoded from Armadillo Goes West's rules sheet.
LINES = [
    [1, 1, 1, 1, 1], [2, 2, 2, 2, 2], [0, 0, 0, 0, 0], [3, 3, 3, 3, 3], [1, 2, 3, 2, 1],
    [2, 1, 0, 1, 2], [0, 0, 1, 2, 3], [3, 3, 2, 1, 0], [1, 0, 0, 0, 1], [2, 3, 3, 3, 2],
    [0, 1, 2, 3, 3], [3, 2, 1, 0, 0], [1, 0, 1, 2, 1], [2, 3, 2, 1, 2], [0, 1, 0, 1, 0],
    [3, 2, 3, 2, 3], [1, 2, 1, 0, 1], [2, 1, 2, 3, 2], [0, 1, 1, 1, 0], [3, 2, 2, 2, 3],
    [1, 1, 2, 3, 3], [2, 2, 1, 0, 0], [1, 1, 0, 1, 1], [2, 2, 3, 2, 2], [1, 2, 2, 2, 3],
]
# The house standard (Armadillo's): pays for 3, 4 and 5 in a row, in line bets. W is the Wild; the tiers are
# named by each variant, and a variant can bring its own pays, upgrade chain and features (variant.py).
PAYS = {
    "W": (20, 40, 120), "H1": (20, 40, 120), "H2": (20, 40, 100),
    "M1": (16, 24, 60), "M2": (16, 24, 60), "M3": (12, 20, 48), "M4": (12, 20, 48),
    "L1": (4, 8, 20), "L2": (4, 8, 20), "L3": (4, 8, 20), "L4": (4, 8, 20),
}
SCATTERS = ("BS", "FS")   # the bonus scatter and the free-spin scatter: never substituted, pay nothing
BONUSES = ("trail", "free")   # the library's bonus games: the Trail Bonus and Combo Free Games
# Which bonuses each way in plays (3+ BS, 3+ FS, Buy Bonus). With more than one, it's one of them at random.
ROUTES = {"BS": ["trail"], "FS": ["free"], "buy": ["trail"]}
UPGRADES = {"L1": "M3", "L2": "M3", "L3": "M4", "L4": "M4", "M3": "M1", "M4": "M2", "M1": "H2", "M2": "H2", "H2": "H1"}
LADDER = [25, 50, 75, 100, 150, 250, 500, 1000, 2500]   # total bet in pence (a whole-pence line bet)
FEATURES = ["wilds", "wildReels", "colossal", "multiplier", "upgrade", "repeat", "instant"]


def tier_ids(shape: dict) -> list:
    """Every tier of a tier shape ({high, mid, low} counts), highest first: W, the scatters, H1.., M1.., L1.."""
    return (["W", "BS", "FS"] + [f"H{i}" for i in range(1, shape["high"] + 1)]
            + [f"M{i}" for i in range(1, shape["mid"] + 1)] + [f"L{i}" for i in range(1, shape["low"] + 1)])


def default_pays(shape: dict) -> dict:
    """The house standard's pays stretched to any tier shape (2 high, 4 mid, 4 low gives exactly PAYS)."""
    high = [(20, 40, 120), (20, 40, 100)] + [(16, 32, max(40, 80 - 8 * i)) for i in range(shape["high"])]
    mid = [(16, 24, 60), (16, 24, 60), (12, 20, 48), (12, 20, 48)] + [(10, 16, 40)] * shape["mid"]
    out = {"W": (20, 40, 120)}
    out.update({f"H{i + 1}": high[i] for i in range(shape["high"])})
    out.update({f"M{i + 1}": mid[i] for i in range(shape["mid"])})
    out.update({f"L{i + 1}": (4, 8, 20) for i in range(shape["low"])})
    return out


def default_upgrades(shape: dict) -> dict:
    """The house standard's upgrade chain for any tier shape (2/4/4 gives exactly UPGRADES): the lows step up into
    the bottom two mids, the bottom half of the mids into the top half, the top mids into the lowest high, and each
    high into the one above."""
    h, m, l = shape["high"], shape["mid"], shape["low"]
    out = {}
    low_targets = [f"M{max(1, m - 1)}", f"M{m}"]
    for i in range(1, l + 1):
        out[f"L{i}"] = low_targets[0] if i <= (l + 1) // 2 else low_targets[1]
    half = m // 2
    for i in range(1, m + 1):
        out[f"M{i}"] = f"M{i - half}" if i > half and m >= 2 else f"H{h}"
    for i in range(2, h + 1):
        out[f"H{i}"] = f"H{i - 1}"
    return out


def grid_from_stops(strips, stops) -> list:
    return [strips[r][(stops[r] + row) % len(strips[r])] for r in range(REELS) for row in range(ROWS)]


def line_pay(syms, pays=PAYS):
    """The best pay for one line's five symbols: (sym, count, line bets), or None."""
    wild_run = 0
    while wild_run < REELS and syms[wild_run] == "W":
        wild_run += 1
    target = next((s for s in syms if s != "W"), None)
    best = None
    if wild_run >= 3:
        best = ("W", wild_run, pays["W"][wild_run - 3])
    if target in pays:
        k = 0
        while k < REELS and syms[k] in (target, "W"):
            k += 1
        if k >= 3 and (best is None or pays[target][k - 3] > best[2]):
            best = (target, k, pays[target][k - 3])
    return best


def evaluate(grid, pays=PAYS) -> list:
    """Line wins: the longest match per line only. Wild stands in for everything but the
    scatters, and a run of Wilds pays as Wilds when that's worth more.
    Returns [{line, sym, count, mult (line bets), cells}]."""
    wins = []
    for n, line in enumerate(LINES):
        cells = [reel * ROWS + row for reel, row in enumerate(line)]
        best = line_pay([grid[c] for c in cells], pays)
        if best:
            wins.append({"line": n + 1, "sym": best[0], "count": best[1], "mult": best[2], "cells": cells[:best[1]]})
    return wins


def count_scatters(grid) -> dict:
    out = {"BS": [], "FS": []}
    for c, s in enumerate(grid):
        if s in out:
            out[s].append(c)
    return out


def exact_line_rtp(strips, pays=PAYS) -> float:
    """The exact return of the line pays alone (no features): every cell of a reel has the
    same symbol distribution, so one line's expectation is the whole game's."""
    freqs = []
    for strip in strips:
        f = {}
        for s in strip:
            f[s] = f.get(s, 0) + 1 / len(strip)
        freqs.append(list(f.items()))
    ev = 0.0
    syms = [None] * REELS

    def walk(reel, p):
        nonlocal ev
        if reel == REELS:
            best = line_pay(syms, pays)
            if best:
                ev += p * best[2]
            return
        for s, q in freqs[reel]:
            syms[reel] = s
            walk(reel + 1, p * q)
    walk(0, 1.0)
    return ev
