"""
Simulation, for tuning (tools/slot_tune.py) and the tests: paid spins with everything
included, and bought bonuses. The trail swings hard (a 2,000x prizepot about 1 in 250), so its
value is best judged from a long run of trails on its own (simulate_trail); the same goes for the wave battle
(simulate_battle), whose value includes the free games its ships give, and the island voyage (simulate_voyage, every
choice made by voyage_auto, with the free games it buys), and the expedition (simulate_expedition, the same with
expedition_auto, with the free games it finds).
"""
from casino_server.slots import jackpots
from casino_server.slots.bonuses import (battle_play_out, battle_start, expedition_play_out, expedition_start,
                                        free_games, trail_play_out, trail_start, voyage_play_out, voyage_start)
from casino_server.slots.base import BONUSES, SCATTERS
from casino_server.slots.outcome import pick_bonus, spin_outcome
from casino_server.slots.rng import mulberry32


def simulate(v, spins: int, bet: int = 100, seed: int = 7) -> dict:
    rng = mulberry32(seed)
    r = {"spins": spins, "staked": spins * bet, "plain": 0, "featured": 0, "repeat_extra": 0, "instant": 0, "trail": 0,
         "free": 0, "battle": 0, "voyage": 0, "expedition": 0, "hits": 0, "trails": 0, "frees": 0, "battles": 0, "voyages": 0,
         "expeditions": 0, "feature_spins": 0,
         "max": 0}
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
        elif o["trigger"] == "battle":
            got = battle_value(v, bet, rng)
            r["battles"] += 1
            r["battle"] += got
            won += got
        elif o["trigger"] == "voyage":
            got = voyage_value(v, bet, rng)
            r["voyages"] += 1
            r["voyage"] += got
            won += got
        elif o["trigger"] == "expedition":
            got = expedition_value(v, bet, rng)
            r["expeditions"] += 1
            r["expedition"] += got
            won += got
        r["hits"] += won > 0
        r["max"] = max(r["max"], won)
    pct = {k: 100 * r[k] / r["staked"] for k in ("plain", "featured", "repeat_extra", "instant", "trail", "free", "battle", "voyage", "expedition")}
    pct["game"] = sum(pct.values())
    pct["jackpot"] = 100 * jackpots.rtp()
    pct["total"] = pct["game"] + pct["jackpot"]
    r["rtp"] = pct
    return r


def simulate_buy(v, n: int, bet: int = 100, seed: int = 9) -> dict:
    """Bought bonuses: each one of the buyable bonuses at random (just the trail for Armadillo)."""
    rng = mulberry32(seed)
    won = top = ends = rolls = 0
    for _ in range(n):
        kind = pick_bonus(rng, v.routes.get("buy", []))
        if kind == "free":
            total = sum(g["total"] for g in free_games(v, bet, rng, v.free_games))
        elif kind == "battle":
            total = battle_value(v, bet, rng)
        elif kind == "voyage":
            total = voyage_value(v, bet, rng)
        elif kind == "expedition":
            total = expedition_value(v, bet, rng)
        else:
            st = trail_start(v, bet, rng)
            trail_play_out(v, st, rng)
            total = st["total"]
            rolls += st["rolls"]
            ends += st["pos"] >= len(st["board"]) - 1
        won += total
        top = max(top, total)
    return {"n": n, "rtp": 100 * won / (n * bet * v.buy_cost) if v.buy_cost else 0.0, "mean": won / n / bet,
            "max": top / bet, "prizepots": ends, "rolls": rolls / n}


def simulate_trail(v, n: int, bet: int = 100, seed: int = 9) -> float:
    """The mean Trail Bonus win, in bets."""
    rng = mulberry32(seed)
    won = 0
    for _ in range(n):
        st = trail_start(v, bet, rng)
        trail_play_out(v, st, rng)
        won += st["total"]
    return won / n / bet


def battle_value(v, bet: int, rng) -> int:
    """One wave battle fought to the end, plus the free games its ships gave, in pence."""
    st = battle_start(v, bet)
    battle_play_out(v, st, rng)
    return st["total"] + (sum(g["total"] for g in free_games(v, bet, rng, st["spins"])) if st["spins"] else 0)


def simulate_battle(v, n: int, bet: int = 100, seed: int = 9) -> float:
    """The mean wave battle win (its free games included), in bets."""
    rng = mulberry32(seed)
    return sum(battle_value(v, bet, rng) for _ in range(n)) / n / bet


def voyage_value(v, bet: int, rng) -> int:
    """One island voyage sailed to the end (voyage_auto choosing), plus the free games it bought, in pence."""
    st = voyage_start(v, bet, rng)
    voyage_play_out(v, st, rng)
    return st["total"] + (sum(g["total"] for g in free_games(v, bet, rng, st["spins"])) if st["spins"] else 0)


def simulate_voyage(v, n: int, bet: int = 100, seed: int = 9) -> float:
    """The mean island voyage win (its free games included), in bets."""
    rng = mulberry32(seed)
    return sum(voyage_value(v, bet, rng) for _ in range(n)) / n / bet


def expedition_value(v, bet: int, rng) -> int:
    """One expedition explored to the end (expedition_auto choosing), plus the free games it found, in pence."""
    st = expedition_start(v, bet, rng)
    expedition_play_out(v, st, rng)
    return st["total"] + (sum(g["total"] for g in free_games(v, bet, rng, st["spins"])) if st["spins"] else 0)


def simulate_expedition(v, n: int, bet: int = 100, seed: int = 9) -> float:
    """The mean expedition win (its free games included), in bets."""
    rng = mulberry32(seed)
    return sum(expedition_value(v, bet, rng) for _ in range(n)) / n / bet


def scatter_odds(v) -> dict:
    """The exact chance a paid spin plays each bonus, from the strips. Scatters sit at least four
    apart on a strip, so a reel shows at most one; each reel shows BS, FS or neither. A scatter that
    plays several bonuses shares its chance between them equally."""
    per_reel = []
    for strip in v.strips:
        n = len(strip)
        bs, fs = 4 * strip.count("BS") / n, 4 * strip.count("FS") / n
        per_reel.append({"BS": bs, "FS": fs, None: 1 - bs - fs})
    hits = {"BS": 0.0, "FS": 0.0}

    def walk(reel, p, counts):
        if reel == len(per_reel):
            if counts["BS"] >= 3:
                hits["BS"] += p
            elif counts["FS"] >= 3:
                hits["FS"] += p
            return
        for s, q in per_reel[reel].items():
            if q:
                walk(reel + 1, p * q, {**counts, s: counts.get(s, 0) + 1} if s else counts)
    walk(0, 1.0, {"BS": 0, "FS": 0})
    odds = {k: 0.0 for k in BONUSES}
    for s in SCATTERS:
        for kind in v.routes.get(s, []):
            odds[kind] += hits[s] / len(v.routes[s])
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
    trail = simulate_trail(v, bonuses, 100, seed + 1)
    free = simulate_free(v, bonuses // 4, 100, seed + 2)
    battle = simulate_battle(v, bonuses // 4, 100, seed + 3) if odds["battle"] else 0.0
    voyage = simulate_voyage(v, bonuses // 4, 100, seed + 4) if odds["voyage"] else 0.0
    expedition = simulate_expedition(v, bonuses // 4, 100, seed + 5) if odds["expedition"] else 0.0
    base_part = sum(r["rtp"][k] for k in ("plain", "featured", "repeat_extra", "instant"))
    out = {"base": base_part, "trail": 100 * odds["trail"] * trail, "free": 100 * odds["free"] * free,
           "battle": 100 * odds["battle"] * battle, "trail_odds": odds["trail"], "free_odds": odds["free"],
           "battle_odds": odds["battle"], "trail_mean": trail, "free_mean": free, "battle_mean": battle,
           "voyage": 100 * odds["voyage"] * voyage, "voyage_odds": odds["voyage"], "voyage_mean": voyage,
           "expedition": 100 * odds["expedition"] * expedition, "expedition_odds": odds["expedition"],
           "expedition_mean": expedition,
           "jackpot": 100 * jackpots.rtp()}
    out["game"] = out["base"] + out["trail"] + out["free"] + out["battle"] + out["voyage"] + out["expedition"]
    out["total"] = out["game"] + out["jackpot"]
    return out
