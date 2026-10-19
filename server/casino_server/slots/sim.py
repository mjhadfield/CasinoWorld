"""
Simulation, for tuning (tools/slot_tune.py) and the tests: paid spins with everything
included, and bought bonuses. The trail swings hard (a 2,000x prizepot about 1 in 250), so its
value is best judged from a long run of trails on its own (simulate_buy).
"""
from casino_server.slots import jackpots
from casino_server.slots.bonuses import free_games, trail_play_out, trail_start
from casino_server.slots.outcome import spin_outcome
from casino_server.slots.rng import mulberry32


def simulate(v, spins: int, bet: int = 100, seed: int = 7) -> dict:
    rng = mulberry32(seed)
    r = {"spins": spins, "staked": spins * bet, "plain": 0, "featured": 0, "repeat_extra": 0, "instant": 0, "trail": 0,
         "free": 0, "hits": 0, "trails": 0, "frees": 0, "feature_spins": 0, "max": 0}
    for _ in range(spins):
        o = spin_outcome(v, bet, rng)
        won = o["total"]
        if o["features"]:
            r["feature_spins"] += 1
            r["featured"] += o["line_win"]
            r["repeat_extra"] += o["line_win"] * max(0, o["repeat"] - 1)
            r["instant"] += o["instant"]
        else:
            r["plain"] += o["line_win"]
        if o["trigger"] == "trail":
            st = trail_start(v, bet, rng)
            trail_play_out(v, st, rng)
            r["trails"] += 1
            r["trail"] += st["total"]
            won += st["total"]
        elif o["trigger"] == "free":
            fs = sum(g["total"] for g in free_games(v, bet, rng, v.free_games))
            r["frees"] += 1
            r["free"] += fs
            won += fs
        r["hits"] += won > 0
        r["max"] = max(r["max"], won)
    pct = {k: 100 * r[k] / r["staked"] for k in ("plain", "featured", "repeat_extra", "instant", "trail", "free")}
    pct["game"] = sum(pct.values())
    pct["jackpot"] = 100 * jackpots.rtp()
    pct["total"] = pct["game"] + pct["jackpot"]
    r["rtp"] = pct
    return r


def simulate_buy(v, n: int, bet: int = 100, seed: int = 9) -> dict:
    rng = mulberry32(seed)
    won = top = ends = rolls = 0
    for _ in range(n):
        st = trail_start(v, bet, rng)
        trail_play_out(v, st, rng)
        won += st["total"]
        top = max(top, st["total"])
        rolls += st["rolls"]
        ends += st["pos"] >= len(st["board"]) - 1
    return {"n": n, "rtp": 100 * won / (n * bet * v.buy_cost), "mean": won / n / bet, "max": top / bet,
            "prizepots": ends, "rolls": rolls / n}


def scatter_odds(v) -> dict:
    """The exact chance a paid spin triggers each bonus, from the strips. Scatters sit at least
    four apart on a strip, so a reel shows at most one; each reel shows BS, FS or neither."""
    per_reel = []
    for strip in v.strips:
        n = len(strip)
        bs, fs = 4 * strip.count("BS") / n, 4 * strip.count("FS") / n
        per_reel.append({"BS": bs, "FS": fs, None: 1 - bs - fs})
    odds = {"trail": 0.0, "free": 0.0}

    def walk(reel, p, counts):
        if reel == len(per_reel):
            if counts["BS"] >= 3:
                odds["trail"] += p
            elif counts["FS"] >= 3:
                odds["free"] += p
            return
        for s, q in per_reel[reel].items():
            if q:
                walk(reel + 1, p * q, {**counts, s: counts.get(s, 0) + 1} if s else counts)
    walk(0, 1.0, {"BS": 0, "FS": 0})
    return odds


def simulate_free(v, n: int, bet: int = 100, seed: int = 13) -> float:
    """The mean Combo Free Spins win, in bets."""
    rng = mulberry32(seed)
    return sum(sum(g["total"] for g in free_games(v, bet, rng, v.free_games)) for _ in range(n)) / n / bet


def expected_rtp(v, spins: int = 200_000, bonuses: int = 100_000, seed: int = 11) -> dict:
    """A steadier estimate than one long run: the base game simulated, each bonus valued from
    its own long run, times its exact trigger odds."""
    r = simulate(v, spins, 100, seed)
    odds = scatter_odds(v)
    trail = simulate_buy(v, bonuses, 100, seed + 1)["mean"]
    free = simulate_free(v, bonuses // 4, 100, seed + 2)
    base_part = sum(r["rtp"][k] for k in ("plain", "featured", "repeat_extra", "instant"))
    out = {"base": base_part, "trail": 100 * odds["trail"] * trail, "free": 100 * odds["free"] * free,
           "trail_odds": odds["trail"], "free_odds": odds["free"], "trail_mean": trail, "free_mean": free,
           "jackpot": 100 * jackpots.rtp()}
    out["game"] = out["base"] + out["trail"] + out["free"]
    out["total"] = out["game"] + out["jackpot"]
    return out
