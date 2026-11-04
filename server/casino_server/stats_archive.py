"""
The Stats archive: frozen copies of the casino's figures, kept for the admin page's Stats archive section (Setup).

`build(store, title)` works out the figures from the store as they stand: totals, NPC and human money by game,
slots by machine, NPC archetypes, traits, how visits end, visit lengths, every punter's lifetime figures, the day by
day series and the jackpot pools. `save()` writes it to `<data>/stats_archive/<id>.json`, which is never changed
after that. Take one before NPC stats are wiped, so what they showed is kept (docs/npc-data-analysis-2026-11-04.md
is the first, written up).

NPC money isn't recorded per game, only per visit (with rounds per game), so NPC money by game comes from the visits
that played a single game; `npc_games_coverage` says how much of the stake that covers. "house" figures are the
house's side: staked less returned. Money is in pence.
"""
import json
import re
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from casino_server import roster
from casino_server.slots.variants import VARIANTS

DIR = "stats_archive"
TOP_NPCS = 5


def _hold(staked: int, returned: int) -> float | None:
    return round(100 * (staked - returned) / staked, 2) if staked else None


def _money(staked: int, returned: int) -> dict:
    return {"wagered": staked, "returned": returned, "house": staked - returned, "hold": _hold(staked, returned)}


def _pct(values: list, q: float):
    return values[min(len(values) - 1, int(len(values) * q))] if values else None


def build(store, title: str) -> dict:
    db = store.db
    now = datetime.now(timezone.utc)
    visits = [dict(r) for r in db.execute(
        "SELECT v.*, n.name, n.archetype, n.traits FROM npc_visits v JOIN npcs n ON n.id = v.npc_id ORDER BY v.id")]
    for v in visits:
        v["games"] = json.loads(v["games"] or "{}")
        v["traits"] = json.loads(v["traits"] or "[]")
        v["minutes"] = (v["left_at"] - v["arrived"]) / 60
    ledger = [dict(r) for r in db.execute(
        "SELECT l.player_id, p.name, l.at, l.kind, l.amount, l.game FROM ledger l JOIN players p ON p.id = l.player_id"
        " WHERE l.kind IN ('bet', 'payout') ORDER BY l.id")]

    # ---- NPCs: totals, and money by game from single-game visits
    staked = sum(v["wagered"] for v in visits)
    returned = sum(v["returned"] for v in visits)
    rounds_by_game, single = defaultdict(int), defaultdict(lambda: {"visits": 0, "rounds": 0, "wagered": 0, "returned": 0, "minutes": 0.0})
    for v in visits:
        for g, n in v["games"].items():
            rounds_by_game[g] += n
        if len(v["games"]) == 1:
            s = single[next(iter(v["games"]))]
            s["visits"] += 1
            s["rounds"] += v["rounds"]
            s["wagered"] += v["wagered"]
            s["returned"] += v["returned"]
            s["minutes"] += v["minutes"]
    npc_games = []
    for g in sorted(set(rounds_by_game) | set(single), key=lambda g: -single[g]["wagered"]):
        s = single[g]
        npc_games.append({"game": g, "rounds": rounds_by_game[g], "single_visits": s["visits"],
                          **_money(s["wagered"], s["returned"]),
                          "per_round": round(s["wagered"] / s["rounds"]) if s["rounds"] else None,
                          "avg_minutes": round(s["minutes"] / s["visits"], 1) if s["visits"] else None,
                          "avg_rounds": round(s["rounds"] / s["visits"], 1) if s["visits"] else None})
    covered = sum(s["wagered"] for s in single.values())

    # ---- NPCs by archetype, trait and how the visit ended
    def group(key_of) -> list:
        out = defaultdict(lambda: {"visits": 0, "wagered": 0, "returned": 0, "busts": 0, "budget": 0, "minutes": 0.0, "rounds": 0})
        for v in visits:
            for k in key_of(v):
                o = out[k]
                o["visits"] += 1
                o["wagered"] += v["wagered"]
                o["returned"] += v["returned"]
                o["busts"] += v["reason"] == "bust"
                o["budget"] += v["budget"]
                o["minutes"] += v["minutes"]
                o["rounds"] += v["rounds"]
        return [{"key": k, "visits": o["visits"], **_money(o["wagered"], o["returned"]),
                 "bust_pct": round(100 * o["busts"] / o["visits"], 1), "avg_budget": round(o["budget"] / o["visits"]),
                 "avg_minutes": round(o["minutes"] / o["visits"], 1), "avg_rounds": round(o["rounds"] / o["visits"], 1)}
                for k, o in sorted(out.items(), key=lambda kv: -kv[1]["wagered"])]

    played = [v for v in visits if v["rounds"] > 0]
    minutes, rounds = sorted(v["minutes"] for v in played), sorted(v["rounds"] for v in played)
    budgets = sorted(v["budget"] for v in visits)

    def lengths(vs: list) -> dict:
        n = len(vs)
        return {"visits": n, "avg_minutes": round(sum(v["minutes"] for v in vs) / n, 1) if n else None,
                "avg_rounds": round(sum(v["rounds"] for v in vs) / n, 1) if n else None}

    # ---- NPCs by day
    by_day = defaultdict(lambda: {"visits": 0, "rounds": 0, "wagered": 0, "returned": 0})
    for v in visits:
        d = by_day[datetime.fromtimestamp(v["arrived"], timezone.utc).date().isoformat()]
        d["visits"] += 1
        d["rounds"] += v["rounds"]
        d["wagered"] += v["wagered"]
        d["returned"] += v["returned"]

    # ---- every punter's lifetime figures
    punters = []
    for r in db.execute("SELECT * FROM npcs WHERE role = 'punter' ORDER BY id"):
        punters.append({"id": r["id"], "name": r["name"], "archetype": r["archetype"], "traits": json.loads(r["traits"] or "[]"),
                        "visits": r["visits"], "rounds": r["rounds"], "wagered": r["wagered"], "returned": r["returned"],
                        "net": r["net"], "busts": r["busts"], "biggest_win": r["biggest_win"],
                        "archived": bool(r["archived_at"])})
    by_net = sorted(punters, key=lambda p: p["net"])

    # ---- humans, from the ledger ("bet" rows the other way are stakes taken back)
    h_games = defaultdict(lambda: {"bets": 0, "wagered": 0, "returned": 0})
    h_players = defaultdict(lambda: {"name": "", "games": defaultdict(lambda: {"bets": 0, "wagered": 0, "returned": 0})})
    biggest = []
    for row in ledger:
        g = row["game"] or "(none)"
        targets = (h_games[g], h_players[row["player_id"]]["games"][g])
        h_players[row["player_id"]]["name"] = row["name"]
        for t in targets:
            if row["kind"] == "bet":
                t["wagered"] -= row["amount"]
                t["bets"] += row["amount"] < 0
            else:
                t["returned"] += row["amount"]
        if row["kind"] == "payout":
            biggest.append(row)
    human_games = [{"game": g, "bets": t["bets"], **_money(t["wagered"], t["returned"])}
                   for g, t in sorted(h_games.items(), key=lambda kv: -kv[1]["wagered"])]
    human_players = []
    for pid, p in sorted(h_players.items()):
        games = [{"game": g, "bets": t["bets"], **_money(t["wagered"], t["returned"])}
                 for g, t in sorted(p["games"].items(), key=lambda kv: -kv[1]["wagered"])]
        w, r = sum(x["wagered"] for x in games), sum(x["returned"] for x in games)
        human_players.append({"id": pid, "name": p["name"], **_money(w, r), "games": games})
    hw, hr = sum(t["wagered"] for t in h_games.values()), sum(t["returned"] for t in h_games.values())
    biggest = [{"name": b["name"], "at": b["at"], "game": b["game"], "amount": b["amount"]}
               for b in sorted(biggest, key=lambda b: -b["amount"])[:TOP_NPCS * 2]]

    # ---- slots by machine (counted since slot_stats_since), and the jackpot pools
    slots = [{"variant": r["variant"], "name": VARIANTS[r["variant"]].name if r["variant"] in VARIANTS else r["variant"],
              "who": r["who"], "spins": r["spins"], **_money(r["staked"], r["returned"]),
              "bonuses": r["bonuses"], "jackpots": r["jackpots"]}
             for r in db.execute("SELECT * FROM slot_stats ORDER BY who, staked DESC")]
    pools = {"jackpot": round(float(store.get_meta("jackpot_amount") or 0))}
    for tier, amount in (store.get_json("slot_progressives", {}) or {}).items():
        pools[f"slots_{tier}"] = round(float(amount))

    arrived = [v["arrived"] for v in visits]
    first = min([datetime.fromtimestamp(a, timezone.utc).isoformat() for a in arrived[:1]] + [r["at"] for r in ledger[:1]], default=None)
    return {
        "title": title, "created": now.isoformat(timespec="seconds"),
        "period": {"from": first, "to": now.isoformat(timespec="seconds")},
        "games": {**roster.GAMES, "master_table": "Master Table"},
        "labels": {**{k: a["label"] for k, a in roster.ARCHETYPES.items()}, **{k: m["label"] for k, m in roster.MODIFIERS.items()}},
        "summary": {
            "npc": {"visits": len(visits), "rounds": sum(v["rounds"] for v in visits), **_money(staked, returned),
                    "hours": round(sum(v["minutes"] for v in visits) / 60), "punters": len(punters),
                    "in_profit": sum(p["net"] > 0 for p in punters)},
            "human": {"bets": sum(t["bets"] for t in h_games.values()), **_money(hw, hr), "players": len(human_players)},
            "pools": pools,
        },
        "npc_games": npc_games,
        "npc_games_coverage": round(100 * covered / staked, 1) if staked else None,
        "games_per_visit": {str(k): n for k, n in sorted(_count(len(v["games"]) for v in visits).items())},
        "archetypes": group(lambda v: [v["archetype"] or "(none)"]),
        "traits": group(lambda v: v["traits"] or ["(none)"]),
        "reasons": group(lambda v: [v["reason"]]),
        "visit_length": {"all": lengths(visits), "played": lengths(played),
                         "finished": lengths([v for v in played if v["reason"] != "shutdown"]),
                         "median_minutes": round(statistics.median(minutes), 1) if minutes else None,
                         "median_rounds": statistics.median(rounds) if rounds else None},
        "budgets": {"median": _pct(budgets, 0.5), "p10": _pct(budgets, 0.1), "p90": _pct(budgets, 0.9),
                    "max": budgets[-1] if budgets else None},
        "best_npcs": [p["id"] for p in reversed(by_net[-TOP_NPCS:])],
        "worst_npcs": [p["id"] for p in by_net[:TOP_NPCS]],
        "npcs": punters,
        "daily": [{"day": d, "visits": x["visits"], "rounds": x["rounds"], **_money(x["wagered"], x["returned"])}
                  for d, x in sorted(by_day.items())],
        "human_games": human_games,
        "human_players": human_players,
        "biggest_payouts": biggest,
        "slots": slots,
        "slots_since": store.get_meta("slot_stats_since"),
    }


def _count(items) -> dict:
    out = defaultdict(int)
    for i in items:
        out[i] += 1
    return out


def folder(data_dir: Path) -> Path:
    return Path(data_dir) / DIR


def save(data_dir: Path, archive: dict) -> str:
    """Write an archive; returns its id (the date it was taken, and its title). Never overwrites one."""
    slug = re.sub(r"[^a-z0-9]+", "-", archive["title"].lower()).strip("-")[:48] or "archive"
    base = f"{archive['created'][:10]}-{slug}"
    d = folder(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    aid, n = base, 1
    while (d / f"{aid}.json").exists():
        n += 1
        aid = f"{base}-{n}"
    archive = {"id": aid, **archive}
    tmp = d / f".{aid}.{int(time.time())}.tmp"
    tmp.write_text(json.dumps(archive, separators=(",", ":")))
    tmp.rename(d / f"{aid}.json")
    return aid


def listing(data_dir: Path) -> list[dict]:
    """Every archive, newest first: id, title, when it was taken, the period it covers."""
    out = []
    for path in sorted(folder(data_dir).glob("*.json")) if folder(data_dir).is_dir() else []:
        try:
            a = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        out.append({"id": a.get("id", path.stem), "title": a.get("title", path.stem), "created": a.get("created"),
                    "period": a.get("period")})
    return sorted(out, key=lambda a: a["created"] or "", reverse=True)


def load(data_dir: Path, archive_id: str) -> dict | None:
    if not re.fullmatch(r"[a-z0-9-]+", archive_id):
        return None
    path = folder(data_dir) / f"{archive_id}.json"
    return json.loads(path.read_text()) if path.is_file() else None
