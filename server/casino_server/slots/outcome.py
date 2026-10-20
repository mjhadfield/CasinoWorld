"""
One spin's whole outcome, in the order the screen shows it: the stops, the pre-stop features
(Colossal Reels, Wild Reels, Random Wilds, a Multiplier), the post-stop Symbol Upgrade, the
line wins, then Repeat Win or Instant Win. The draws happen in exactly the mockup's order, so
the same seed gives the same spin (slots_math.js spinOutcome).

The rules the pipeline keeps (from the rules sheet):
- no feature lands on a Wild or a scatter
- Wild Reels and Colossal Reels never come on a spin that triggers a bonus
- Repeat Win never comes with a free-spin trigger, nor with an Instant Win
- the two scatters never trigger together
- a scatter (or Buy Bonus) that plays more than one bonus picks one at random (pick_bonus)
"""
from casino_server.slots.base import REELS, ROWS, SCATTERS, count_scatters, evaluate, grid_from_stops
from casino_server.slots.rng import randint, sample, weighted


def spin_outcome(v, bet: int, rng, free: bool = False, rig: dict | None = None) -> dict:
    """`v` is a variant (variants/); `bet` the total bet in pence. `free` uses the free-game
    strips and feature rates. `rig` (tests and the dev rig) may force
    {features: [...], trigger: "trail"|"free", stops: [5]}."""
    rig = rig or {}
    strips = v.free_strips if free else v.strips
    line_bet = bet / 25
    tries = 0
    while True:
        stops = list(rig["stops"]) if rig.get("stops") else [randint(rng, len(s)) for s in strips]
        grid = grid_from_stops(strips, stops)
        if rig.get("trigger") and not rig.get("stops"):
            _force_trigger(grid, rig["trigger"], rng, v.routes)
        sc = count_scatters(grid)
        if not (len(sc["BS"]) >= 3 and len(sc["FS"]) >= 3) or tries > 50:   # never both bonuses at once
            break
        tries += 1
    landed = list(grid)
    hit = "BS" if len(sc["BS"]) >= 3 else "FS" if len(sc["FS"]) >= 3 else None
    trigger = pick_bonus(rng, v.routes.get(hit, []), rig.get("trigger")) if hit else None

    # Which features fire. Free games guarantee at least one, and often several.
    rates = v.free_rates if free else v.rates
    on = {}
    if rig.get("features"):
        for f in rig["features"]:
            on[f] = True
    else:
        for f in v.features:
            if rng() < rates[f]:
                on[f] = True
    if trigger:
        on.pop("wildReels", None)
        on.pop("colossal", None)
    if trigger == "free":
        on.pop("repeat", None)
    if on.get("repeat") and on.get("instant"):
        on.pop("repeat" if rng() < 0.5 else "instant")
    if free and not any(f != "repeat" for f in on):
        on[weighted(rng, [(f, rates[f]) for f in v.features if f != "repeat"])] = True

    out = {"bet": bet, "free": free, "stops": stops, "landed": landed, "trigger": trigger, "scatters": sc,
           "colossal": None, "wild_reels": [], "wilds": [], "multiplier": 1, "upgrade": None, "repeat": 0, "instant": 0}

    # Pre-stop: Colossal Reels (over a span with no scatters showing), Wild Reels, Random Wilds, Multiplier.
    if on.get("colossal"):
        k = weighted(rng, v.colossal_sizes)
        spans = [s for s in range(REELS - k + 1)
                 if not any(grid[r * ROWS + row] in SCATTERS for r in range(s, s + k) for row in range(ROWS))]
        if spans:
            start = spans[randint(rng, len(spans))]
            big = v.big_strip
            stop, offset = randint(rng, len(big)), randint(rng, k)
            for r in range(start, start + k):
                for row in range(ROWS):
                    grid[r * ROWS + row] = big[(stop + (row + offset) // k) % len(big)]
            out["colossal"] = {"start": start, "k": k, "stop": stop, "offset": offset}
    out["after_colossal"] = list(grid)
    if on.get("wildReels"):
        col = out["colossal"]
        reels = [r for r in range(REELS) if not (col and col["start"] <= r < col["start"] + col["k"])]
        out["wild_reels"] = sorted(sample(rng, reels, min(len(reels), weighted(rng, v.wild_reel_counts))))
        for r in out["wild_reels"]:
            for row in range(ROWS):
                if grid[r * ROWS + row] not in SCATTERS:
                    grid[r * ROWS + row] = "W"
    if on.get("wilds"):
        open_cells = [c for c in range(REELS * ROWS) if grid[c] != "W" and grid[c] not in SCATTERS]
        out["wilds"] = sorted(sample(rng, open_cells, min(len(open_cells), weighted(rng, v.wild_counts))))
        for c in out["wilds"]:
            grid[c] = "W"
    if on.get("multiplier"):
        out["multiplier"] = weighted(rng, v.multipliers)
    out["pre_grid"] = list(grid)

    # Post-stop: Symbol Upgrade, then the lines, then Repeat Win or Instant Win.
    if on.get("upgrade"):
        present = list(dict.fromkeys(s for s in grid if s in v.upgrades))
        if present:
            frm = present[randint(rng, len(present))]
            to = v.upgrades[frm]
            cells = [c for c, s in enumerate(grid) if s == frm]
            for c in cells:
                grid[c] = to
            out["upgrade"] = {"from": frm, "to": to, "cells": cells}
    out["grid"] = grid
    out["wins"] = [{**w, "pence": int(w["mult"] * line_bet * out["multiplier"])} for w in evaluate(grid, v.pays)]
    out["line_win"] = sum(w["pence"] for w in out["wins"])
    if on.get("repeat") and out["line_win"] > 0:
        out["repeat"] = weighted(rng, v.repeats)
    if on.get("instant"):
        out["instant"] = weighted(rng, v.instants) * bet
    out["total"] = out["line_win"] * (out["repeat"] or 1) + out["instant"]
    shown = {"colossal": bool(out["colossal"]), "wildReels": bool(out["wild_reels"]), "wilds": bool(out["wilds"]),
             "upgrade": bool(out["upgrade"]), "repeat": bool(out["repeat"])}
    out["features"] = [f for f in on if shown.get(f, True)]
    return out


def pick_bonus(rng, choices: list, want: str | None = None) -> str | None:
    """The bonus a way in plays: `want` if it's one of them (the rig), the only one, or one at random. One
    choice draws nothing, so a slot with a bonus per way in spins exactly as it always has."""
    if want in choices:
        return want
    if len(choices) <= 1:
        return choices[0] if choices else None
    return choices[randint(rng, len(choices))]


def _force_trigger(grid, kind, rng, routes):
    """The test rig: three of the scatter that plays bonus `kind`, on reels 1, 3 and 5 (none if only Buy gives it)."""
    sym = next((s for s in SCATTERS if kind in routes.get(s, [])), None)
    if sym is None:
        return
    for c in range(len(grid)):
        if grid[c] in SCATTERS:
            grid[c] = "L1"
    for r in (0, 2, 4):
        grid[r * ROWS + randint(rng, ROWS)] = sym


def presentation_seconds(o: dict, turbo: bool = False) -> float:
    """How long the screen takes to show a spin, so the server and NPCs pace themselves to it."""
    t = 1.3 + 0.18 * (REELS - 1)
    if o["colossal"]:
        t += 0.9
    if o["wild_reels"]:
        t += 0.7 * len(o["wild_reels"])
    if o["wilds"]:
        t += 0.35 * len(o["wilds"]) + 0.3
    if o["multiplier"] > 1:
        t += 0.7
    if o["upgrade"]:
        t += 1.1
    if o["wins"]:
        t += 1.2
    if o["repeat"]:
        t += 0.9 * o["repeat"]
    if o["instant"]:
        t += 1.6
    x = o["total"] / o["bet"]
    if x >= 10:
        t += 5 if x >= 50 else 4 if x >= 25 else 3
    return t * 0.55 if turbo else t
