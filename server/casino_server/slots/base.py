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
# Pays for 3, 4 and 5 in a row, in line bets. W is the Wild; the tiers are named by each variant.
PAYS = {
    "W": (20, 40, 120), "H1": (20, 40, 120), "H2": (20, 40, 100),
    "M1": (16, 24, 60), "M2": (16, 24, 60), "M3": (12, 20, 48), "M4": (12, 20, 48),
    "L1": (4, 8, 20), "L2": (4, 8, 20), "L3": (4, 8, 20), "L4": (4, 8, 20),
}
SCATTERS = ("BS", "FS")   # the bonus scatter and the free-spin scatter: never substituted, pay nothing
UPGRADES = {"L1": "M3", "L2": "M3", "L3": "M4", "L4": "M4", "M3": "M1", "M4": "M2", "M1": "H2", "M2": "H2", "H2": "H1"}
LADDER = [25, 50, 75, 100, 150, 250, 500, 1000, 2500]   # total bet in pence (a whole-pence line bet)
FEATURES = ["wilds", "wildReels", "colossal", "multiplier", "upgrade", "repeat", "instant"]


def grid_from_stops(strips, stops) -> list:
    return [strips[r][(stops[r] + row) % len(strips[r])] for r in range(REELS) for row in range(ROWS)]


def line_pay(syms):
    """The best pay for one line's five symbols: (sym, count, line bets), or None."""
    wild_run = 0
    while wild_run < REELS and syms[wild_run] == "W":
        wild_run += 1
    target = next((s for s in syms if s != "W"), None)
    best = None
    if wild_run >= 3:
        best = ("W", wild_run, PAYS["W"][wild_run - 3])
    if target in PAYS:
        k = 0
        while k < REELS and syms[k] in (target, "W"):
            k += 1
        if k >= 3 and (best is None or PAYS[target][k - 3] > best[2]):
            best = (target, k, PAYS[target][k - 3])
    return best


def evaluate(grid) -> list:
    """Line wins: the longest match per line only. Wild stands in for everything but the
    scatters, and a run of Wilds pays as Wilds when that's worth more.
    Returns [{line, sym, count, mult (line bets), cells}]."""
    wins = []
    for n, line in enumerate(LINES):
        cells = [reel * ROWS + row for reel, row in enumerate(line)]
        best = line_pay([grid[c] for c in cells])
        if best:
            wins.append({"line": n + 1, "sym": best[0], "count": best[1], "mult": best[2], "cells": cells[:best[1]]})
    return wins


def count_scatters(grid) -> dict:
    out = {"BS": [], "FS": []}
    for c, s in enumerate(grid):
        if s in out:
            out[s].append(c)
    return out


def exact_line_rtp(strips) -> float:
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
            best = line_pay(syms)
            if best:
                ev += p * best[2]
            return
        for s, q in freqs[reel]:
            syms[reel] = s
            walk(reel + 1, p * q)
    walk(0, 1.0)
    return ev
