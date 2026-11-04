"""
The Tracker: every bet spot's money, for NPCs and players alike, against what the house expected to win on it
(edges.py). It lives on the Resort (app.state, per lifespan) and every Casino shares it, like the slots' SlotStats.

The tables already tell each participant what's on each spot as money moves (the ledger's `detail`: store.adjust).
Participant.debit/credit/refund pass that on here (participants.py), once the participant knows where it's sitting
(TableRunner, at sit). For each move the Tracker adds, per spot:
  staked     pence put down (a refund takes it back off)
  returned   pence paid back, stake and winnings
  expected   the house's expected win on what went down (stake x edge; a Craps bet that wins and stays up is charged
             again, as a fresh decision), so actual (staked - returned) against expected is the House page's figure
  var        the variance of the bettor's net, for a ±2σ band around the EV
  bets       how many times money went down on it
into three running sets: the daily rollup (bet_stats: day x casino x game x spot x human/NPC), each NPC's and each
player's lifetime figures by game and spot, and, for NPCs only, the bet log (npc_ledger: a row per money move, like
the players' ledger, kept for `bet_log_days`). A player's own ledger rows are still written as they happen
(store.adjust); this only counts them.

Counts build up in memory and are written in one transaction every SAVE_INTERVAL seconds (on the next money move
after it) and when the casino halts. The bet log is pruned once a day, in chunks, so it never holds the database's
write lock for long.
"""
import json
import time

from casino_server import roster
from casino_server.edges import SLOTS, Edges

SAVE_INTERVAL = 30.0
PRUNE_INTERVAL = 24 * 3600.0
FIELDS = ("bets", "staked", "returned", "expected", "var")
OTHER = "other"   # money a move's detail doesn't put on a spot


def day_of(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t))


def _travelled_from(spot: str) -> str:
    """A Craps Come or Don't Come bet that's travelled to its number settles as that (come_6, dcome_8); it was staked
    as the bet it started as."""
    return "come" if spot.startswith("come_") and "odds" not in spot else "dont_come" if spot.startswith("dcome_") \
        and "odds" not in spot else spot


def _blank() -> list:
    return [0, 0, 0, 0.0, 0.0]


class Tracker:
    def __init__(self, store, edges: Edges | None = None, jackpot=None, wall=time.time, clock=time.monotonic):
        self.store = store
        self.edges = edges or Edges()
        self.jackpot = jackpot          # the progressive pool, for a Jackpot bet's EV (None: no pool)
        self.wall, self.clock = wall, clock
        self.rollup: dict = {}          # (day, casino, game, spot, who) -> FIELDS
        self.npc_spots: dict = {}       # (npc_id, game, spot) -> FIELDS
        self.player_spots: dict = {}    # (player_id, game, spot) -> FIELDS
        self.npc_games: dict = {}       # (npc_id, game) -> [rounds, seconds]
        self.log: list = []             # npc_ledger rows waiting to be written
        self.saved_at = clock()
        self.pruned_at = None
        self.unpriced: set = set()      # (game, spot) seen with no edge

    # ------------------------------------------------------------------ money moves (from participants.py)
    def stake(self, p, amount: int, note: str, detail: dict | None) -> float:
        """A debit: `amount` went down. Returns the house's expected win on it (pence)."""
        if amount <= 0 or not p.game:
            return 0.0
        spots = self._stake_spots(p.game, amount, detail)
        pool = self.jackpot.amount if self.jackpot is not None and "jackpot" in spots else 0
        expected = 0.0
        open_ = p.track_open
        for spot, stake in spots.items():
            ch = self.edges.charge(p.game, spot, stake, pool, buy=note == "buy bonus")
            if ch is None:
                self.unpriced.add((p.game, spot))
                ch = (0.0, 0.0)
            self._add(p, spot, (1, stake, 0, ch[0], ch[1]))
            o = open_.setdefault(spot, [0, 0.0, 0.0])
            o[0] += stake
            o[1] += ch[0]
            o[2] += ch[1]
            expected += ch[0]
        self._log(p, -amount, "bet", note, detail)
        return expected

    def settle(self, p, amount: int, note: str, detail: dict | None) -> float:
        """A credit: `amount` paid back. Returns the expected win charged on any bet that won and stays up (Craps)."""
        if not p.game or (amount <= 0 and not detail):
            return 0.0
        spots = (detail or {}).get("spots", {}) if p.game != SLOTS else {}
        paid = 0
        expected = 0.0
        open_ = p.track_open
        for spot, d in spots.items():
            ret = int(d.get("returned", 0))
            paid += ret
            ev = var = 0.0
            if d.get("stays"):   # paid, and the same stake left up for another decision
                ch = self.edges.charge(p.game, spot, int(d.get("stake", 0)))
                ev, var = ch if ch else (0.0, 0.0)
                expected += ev
            else:
                o = open_.get(spot) or open_.get(_travelled_from(spot))
                if o:
                    spot_open = spot if spot in open_ else _travelled_from(spot)
                    take = min(o[0], int(d.get("stake", 0)))
                    share = take / o[0] if o[0] else 1.0
                    o[1] -= o[1] * share
                    o[2] -= o[2] * share
                    o[0] -= take
                    if o[0] <= 0:
                        open_.pop(spot_open, None)
            self._add(p, spot, (0, 0, ret, ev, var))
        rest = amount - paid
        if rest:
            spot = (detail or {}).get("machine") if p.game == SLOTS else OTHER
            self._add(p, spot or OTHER, (0, 0, rest, 0.0, 0.0))
            if p.game == SLOTS:
                p.track_open.clear()
        self._log(p, amount, "payout", note, detail)
        return expected

    def hand_back(self, p, amount: int, note: str, detail: dict | None = None) -> float:
        """A refund: a stake taken down before it was decided. It comes off the open stakes it was part of, staked and
        EV both: the spots its `detail` names first, then the most recent. Returns the EV taken back off."""
        if amount <= 0 or not p.game:
            return 0.0
        left = amount
        back = 0.0
        open_ = p.track_open
        named = [s for s in (detail or {}).get("spots", {}) if s in open_]
        for spot in named + [s for s in reversed(list(open_)) if s not in named]:
            if spot not in open_:
                continue
            if left <= 0:
                break
            o = open_[spot]
            take = min(left, o[0])
            share = take / o[0] if o[0] else 1.0
            ev, var = o[1] * share, o[2] * share
            self._add(p, spot, (0, -take, 0, -ev, -var))
            o[0] -= take
            o[1] -= ev
            o[2] -= var
            if o[0] <= 0:
                open_.pop(spot)
            left -= take
            back += ev
        if left > 0:
            self._add(p, OTHER, (0, -left, 0, 0.0, 0.0))
        self._log(p, amount, "bet", note, None)
        return back

    def played(self, npc_id: int, game: str, rounds: int = 0, seconds: float = 0.0):
        """An NPC's rounds and time at a game (their lifetime figures), as each stint at a table ends."""
        row = self.npc_games.setdefault((npc_id, game), [0, 0.0])
        row[0] += rounds
        row[1] += seconds

    # ------------------------------------------------------------------ bookkeeping
    def _stake_spots(self, game: str, amount: int, detail: dict | None) -> dict:
        """What a debit put on each spot (anything its detail doesn't account for: OTHER). At a slot, the machine; at
        Craps, the vig paid up front with a Lay bet goes with it."""
        detail = detail or {}
        if game == SLOTS:
            return {detail.get("machine") or OTHER: amount}
        spots = {k: int(v) for k, v in detail.get("spots", {}).items() if int(v) > 0}
        vig = int(detail.get("vig", 0))
        if vig:
            lays = [s for s in spots if s.startswith("lay_")]
            if lays:
                total = sum(spots[s] for s in lays)
                given = 0
                for s in lays[:-1]:
                    share = vig * spots[s] // total
                    spots[s] += share
                    given += share
                spots[lays[-1]] += vig - given
        rest = amount - sum(spots.values())
        if rest:
            spots[OTHER] = spots.get(OTHER, 0) + rest
        return spots

    def _add(self, p, spot: str, delta: tuple):
        who = "human" if p.is_human else "npc"
        keys = [(self.rollup, (day_of(self.wall()), p.casino_id or "", p.game, spot, who))]
        if who == "npc":
            keys.append((self.npc_spots, (p.who_id, p.game, spot)))
        elif p.who_id is not None:
            keys.append((self.player_spots, (p.who_id, p.game, spot)))
        for table, key in keys:
            row = table.get(key)
            if row is None:
                row = table[key] = _blank()
            for i, v in enumerate(delta):
                row[i] += v
        if self.clock() - self.saved_at >= SAVE_INTERVAL:
            self.save()

    def _log(self, p, amount: int, kind: str, note: str, detail: dict | None):
        if p.is_human:
            return
        visit = p.visit_key
        self.log.append((p.who_id, visit, self.wall(), kind, amount, p.balance, p.game, note,
                         json.dumps(detail, separators=(",", ":")) if detail else None, p.casino_id, p.table_id))

    # ------------------------------------------------------------------ saving
    def pending(self) -> bool:
        return bool(self.rollup or self.npc_spots or self.player_spots or self.npc_games or self.log)

    def save(self):
        """Write what's built up (one transaction), and prune the bet log once a day."""
        self.saved_at = self.clock()
        if self.store is None:
            return
        if self.pending():
            started = time.perf_counter()
            rows = len(self.log)
            self.store.add_tracking(self.rollup, self.npc_spots, self.player_spots, self.npc_games, self.log)
            self.rollup, self.npc_spots, self.player_spots, self.npc_games, self.log = {}, {}, {}, {}, []
            ms = (time.perf_counter() - started) * 1000
            if ms > 50:
                print(f"tracking: saved {rows} bet log rows in {ms:.0f} ms", flush=True)
        if self.pruned_at is None or self.clock() - self.pruned_at >= PRUNE_INTERVAL:
            self.pruned_at = self.clock()
            days = roster.settings(self.store)["bet_log_days"]
            self.store.prune_npc_ledger(self.wall() - days * 86400)

    # ------------------------------------------------------------------ reading (saved plus pending)
    def _merged(self, saved: list[dict], pending: dict, names: tuple, match=lambda key: True) -> list[dict]:
        out = {}
        for r in saved:
            key = tuple(r[n] for n in names)
            out[key] = [r[f] for f in FIELDS]
        for key, row in pending.items():
            if not match(key):
                continue
            t = out.setdefault(key, _blank())
            for i in range(len(FIELDS)):
                t[i] += row[i]
        return [{**dict(zip(names, k)), **dict(zip(FIELDS, v))} for k, v in out.items()]

    def house(self, since_day: str | None = None, who: str | None = None, casino: str | None = None) -> list[dict]:
        """The rollup summed over days from `since_day` (None: all), by game and spot: humans, NPCs or both
        (`who` None), one casino or all."""
        def match(key):
            day, c, _g, _s, w = key
            return (since_day is None or day >= since_day) and (who is None or w == who) and (casino is None or c == casino)
        saved = self.store.bet_stats(since_day, who, casino)
        pending = {}
        for key, row in self.rollup.items():
            if match(key):
                t = pending.setdefault((key[2], key[3]), _blank())
                for i in range(len(FIELDS)):
                    t[i] += row[i]
        return self._merged(saved, pending, ("game", "spot"))

    def npc_figures(self, npc_id: int) -> dict:
        """An NPC's lifetime figures by game and spot, and rounds and time by game."""
        spots = self._merged(self.store.npc_game_spots(npc_id),
                             {(k[1], k[2]): v for k, v in self.npc_spots.items() if k[0] == npc_id}, ("game", "spot"))
        games = {r["game"]: {"rounds": r["rounds"], "seconds": r["seconds"]} for r in self.store.npc_games(npc_id)}
        for (nid, game), (rounds, seconds) in self.npc_games.items():
            if nid == npc_id:
                g = games.setdefault(game, {"rounds": 0, "seconds": 0.0})
                g["rounds"] += rounds
                g["seconds"] += seconds
        return {"spots": spots, "games": games}

    def player_figures(self, player_id: int) -> list[dict]:
        return self._merged(self.store.player_game_spots(player_id),
                            {(k[1], k[2]): v for k, v in self.player_spots.items() if k[0] == player_id},
                            ("game", "spot"))


# ---------------------------------------------------------------------- the House page's shape
def lines(edges: Edges, rows: list[dict], games: dict | None = None) -> list[dict]:
    """Rows of {game, spot, FIELDS} grouped for the admin page: each game, its lines (a decision game's main line, each
    side bet; edges.py), and each line's spots, with totals at every level. `games`: game key -> its name."""
    by_game: dict = {}
    for r in rows:
        if not (r["staked"] or r["returned"] or r["bets"]):
            continue
        g = by_game.setdefault(r["game"], {})
        line = edges.line(r["game"], r["spot"])
        g.setdefault(line, []).append(r)
    out = []
    for game, ls in by_game.items():
        names = edges.games.get(game, {}).get("lines", {})
        if game == SLOTS:
            names = {k: v.get("name", k) for k, v in edges.slots.items()}
        g_out = {"game": game, "name": (games or {}).get(game, game), "lines": [], **_total([])}
        for line, spots in ls.items():
            spots.sort(key=lambda r: -r["staked"])
            priced = all(edges.charge(game, r["spot"], 100) is not None or r["spot"] == OTHER for r in spots)
            g_out["lines"].append({"line": line, "name": names.get(line, line.replace("_", " ").capitalize()),
                                   "priced": priced, "spots": [{**r, "net": r["staked"] - r["returned"]} for r in spots],
                                   **_total(spots)})
        g_out["lines"].sort(key=lambda r: -r["staked"])
        g_out.update(_total(g_out["lines"]))
        out.append(g_out)
    out.sort(key=lambda r: -r["staked"])
    return out


def _total(rows: list[dict]) -> dict:
    t = {f: sum(r[f] for r in rows) for f in FIELDS}
    t["net"] = t["staked"] - t["returned"]   # the house's actual win
    t["expected"] = round(t["expected"], 2)
    return t
