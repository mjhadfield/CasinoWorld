"""
SQLite persistence: players (identified by a per-device token), their wallet,
a ledger of every balance change, and the progressive jackpot.

All money is integer pence. Every balance change goes through adjust(), which
writes the ledger row in the same transaction, so balances always reconcile.
"""
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STARTING_BALANCE = 100_000  # £1,000

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id         INTEGER PRIMARY KEY,
    token      TEXT    NOT NULL UNIQUE,
    name       TEXT    NOT NULL,
    balance    INTEGER NOT NULL,
    created_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
    id            INTEGER PRIMARY KEY,
    player_id     INTEGER NOT NULL REFERENCES players(id),
    at            TEXT    NOT NULL,
    kind          TEXT    NOT NULL,  -- 'start' | 'bet' | 'payout' | 'top_up'
    amount        INTEGER NOT NULL,  -- signed pence
    balance_after INTEGER NOT NULL,
    game          TEXT,
    note          TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS npcs (
    id             INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL,
    role           TEXT    NOT NULL,             -- 'punter' | 'dealer' | later staff roles
    look           TEXT    NOT NULL,             -- JSON look spec (art.py)
    archetype      TEXT    NOT NULL DEFAULT '',  -- punters: 'grinder' | 'casual' | 'gambler'
    traits         TEXT    NOT NULL DEFAULT '[]',-- JSON list of modifiers
    settings       TEXT    NOT NULL DEFAULT '{}',-- JSON: budget range, lucky numbers, favourites...
    enabled        INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT    NOT NULL,
    visits         INTEGER NOT NULL DEFAULT 0,
    rounds         INTEGER NOT NULL DEFAULT 0,
    wagered        INTEGER NOT NULL DEFAULT 0,
    returned       INTEGER NOT NULL DEFAULT 0,
    net            INTEGER NOT NULL DEFAULT 0,
    biggest_win    INTEGER NOT NULL DEFAULT 0,   -- best single visit
    busts          INTEGER NOT NULL DEFAULT 0,
    last_seen      REAL,                         -- unix time
    cooldown_until REAL                          -- unix time
);
CREATE TABLE IF NOT EXISTS npc_visits (
    id           INTEGER PRIMARY KEY,
    npc_id       INTEGER NOT NULL REFERENCES npcs(id) ON DELETE CASCADE,
    arrived      REAL    NOT NULL,
    left_at      REAL    NOT NULL,
    budget       INTEGER NOT NULL,
    end_bankroll INTEGER NOT NULL,
    wagered      INTEGER NOT NULL,
    returned     INTEGER NOT NULL,
    rounds       INTEGER NOT NULL,
    games        TEXT    NOT NULL DEFAULT '{}',  -- JSON: game -> rounds
    reason       TEXT    NOT NULL                -- 'bust' | 'done' | 'hit_and_run' | 'riches' | 'admin' | 'shutdown'
);
"""


class InsufficientFunds(Exception):
    pass


@dataclass
class Player:
    id: int
    token: str
    name: str
    balance: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only ever used from the event loop's thread; the flag lets the test
        # client (which runs the app on a worker thread) poke at it directly.
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        # Every money move commits on the event loop: WAL with NORMAL sync makes a commit ~0.02 ms instead of ~2 ms
        # here, and a power cut can lose only the last moments, never corrupt. (Copy it with sqlite3's .backup.)
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = NORMAL")
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self):
        self.db.close()

    # ------------------------------------------------------------------ players
    def player_by_token(self, token: str) -> Player | None:
        row = self.db.execute("SELECT id, token, name, balance FROM players WHERE token = ?", (token,)).fetchone()
        return Player(**dict(row)) if row else None

    def create_player(self, name: str = "") -> Player:
        token = secrets.token_urlsafe(24)
        with self.db:
            cur = self.db.execute(
                "INSERT INTO players (token, name, balance, created_at) VALUES (?, ?, 0, ?)",
                (token, name or "Guest", _now()))
            player_id = cur.lastrowid
            if not name:
                self.db.execute("UPDATE players SET name = ? WHERE id = ?", (f"Guest {player_id}", player_id))
        self.adjust(player_id, STARTING_BALANCE, "start")
        return self.player_by_token(token)

    def set_name(self, player_id: int, name: str):
        with self.db:
            self.db.execute("UPDATE players SET name = ? WHERE id = ?", (name, player_id))

    def balance(self, player_id: int) -> int:
        return self.db.execute("SELECT balance FROM players WHERE id = ?", (player_id,)).fetchone()[0]

    def adjust(self, player_id: int, amount: int, kind: str, game: str | None = None, note: str | None = None) -> int:
        """Changes a balance by `amount` (signed pence) and records it. Raises
        InsufficientFunds rather than ever going below zero. Returns the new balance."""
        with self.db:
            balance = self.balance(player_id) + amount
            if balance < 0:
                raise InsufficientFunds()
            self.db.execute("UPDATE players SET balance = ? WHERE id = ?", (balance, player_id))
            self.db.execute(
                "INSERT INTO ledger (player_id, at, kind, amount, balance_after, game, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (player_id, _now(), kind, amount, balance, game, note))
        return balance

    def players(self) -> list[dict]:
        """Every player, with how SQLite is holding the balance (it should be an
        integer of pence; a hand edit like '100,000' gets stored as text)."""
        return [dict(r) for r in self.db.execute(
            "SELECT id, name, balance, typeof(balance) AS stored_as FROM players ORDER BY id")]

    def set_balance(self, player_id: int, pence: int, note: str = "set by admin") -> int:
        """Sets a balance outright, with a ledger row for the difference so the
        books still reconcile. Copes with a balance that was hand-edited into
        something that isn't a number: the difference is then measured from the
        ledger's last recorded balance."""
        if pence < 0:
            raise ValueError("a balance can't be negative")
        with self.db:
            raw = self.balance(player_id)
            if not isinstance(raw, int):
                last = self.db.execute("SELECT balance_after FROM ledger WHERE player_id = ? ORDER BY id DESC LIMIT 1",
                                       (player_id,)).fetchone()
                raw = last[0] if last else 0
            self.db.execute("UPDATE players SET balance = ? WHERE id = ?", (pence, player_id))
            self.db.execute(
                "INSERT INTO ledger (player_id, at, kind, amount, balance_after, game, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (player_id, _now(), "adjust", pence - raw, pence, None, note))
        return pence

    def player_stats(self) -> list[dict]:
        """Every player's lifetime figures from the ledger: staked, returned, net, last
        activity, and the same per game."""
        rows = self.db.execute("""
            SELECT p.id, p.name, p.balance, l.game,
                   COALESCE(SUM(CASE WHEN l.kind = 'bet' THEN -l.amount END), 0) AS wagered,
                   COALESCE(SUM(CASE WHEN l.kind = 'payout' THEN l.amount END), 0) AS returned,
                   COUNT(CASE WHEN l.kind = 'bet' AND l.amount < 0 THEN 1 END) AS bets,
                   MAX(l.at) AS last_at
            FROM players p LEFT JOIN ledger l ON l.player_id = p.id
            GROUP BY p.id, l.game ORDER BY p.id""").fetchall()
        players: dict[int, dict] = {}
        for r in rows:
            p = players.setdefault(r["id"], {"id": r["id"], "name": r["name"], "balance": r["balance"],
                                             "wagered": 0, "returned": 0, "bets": 0, "last_at": None, "games": {}})
            p["wagered"] += r["wagered"]
            p["returned"] += r["returned"]
            p["bets"] += r["bets"]
            if r["last_at"] and (p["last_at"] is None or r["last_at"] > p["last_at"]):
                p["last_at"] = r["last_at"]
            if r["game"] and (r["wagered"] or r["returned"]):
                p["games"][r["game"]] = {"wagered": r["wagered"], "returned": r["returned"],
                                         "net": r["returned"] - r["wagered"], "bets": r["bets"]}
        for p in players.values():
            p["net"] = p["returned"] - p["wagered"]
        return list(players.values())

    # ------------------------------------------------------------------ NPCs
    _NPC_JSON = ("look", "traits", "settings")
    _NPC_FIELDS = ("name", "role", "look", "archetype", "traits", "settings", "enabled")

    def _npc_row(self, row) -> dict:
        d = dict(row)
        for k in self._NPC_JSON:
            d[k] = json.loads(d[k])
        d["enabled"] = bool(d["enabled"])
        return d

    def npcs(self, role: str | None = None) -> list[dict]:
        q = "SELECT * FROM npcs" + (" WHERE role = ?" if role else "") + " ORDER BY role, name"
        return [self._npc_row(r) for r in self.db.execute(q, (role,) if role else ())]

    def npc(self, npc_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM npcs WHERE id = ?", (npc_id,)).fetchone()
        return self._npc_row(row) if row else None

    def create_npc(self, data: dict) -> int:
        vals = self._npc_values(data)
        with self.db:
            cur = self.db.execute(
                f"INSERT INTO npcs ({', '.join(vals)}, created_at) VALUES ({', '.join('?' * len(vals))}, ?)",
                (*vals.values(), _now()))
        return cur.lastrowid

    def update_npc(self, npc_id: int, data: dict):
        vals = self._npc_values(data)
        if vals:
            with self.db:
                self.db.execute(f"UPDATE npcs SET {', '.join(k + ' = ?' for k in vals)} WHERE id = ?",
                                (*vals.values(), npc_id))

    def _npc_values(self, data: dict) -> dict:
        vals = {}
        for k in self._NPC_FIELDS:
            if k in data:
                v = data[k]
                vals[k] = json.dumps(v) if k in self._NPC_JSON else int(v) if k == "enabled" else v
        return vals

    def delete_npc(self, npc_id: int):
        with self.db:
            self.db.execute("DELETE FROM npc_visits WHERE npc_id = ?", (npc_id,))
            self.db.execute("DELETE FROM npcs WHERE id = ?", (npc_id,))

    def set_npc_cooldown(self, npc_id: int, until: float | None):
        with self.db:
            self.db.execute("UPDATE npcs SET cooldown_until = ? WHERE id = ?", (until, npc_id))

    def record_npc_visit(self, npc_id: int, visit: dict, cooldown_until: float | None):
        """A visit's ended: log it and fold it into the NPC's lifetime figures."""
        net = visit["returned"] - visit["wagered"]
        with self.db:
            self.db.execute(
                "INSERT INTO npc_visits (npc_id, arrived, left_at, budget, end_bankroll, wagered, returned, rounds, games, reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (npc_id, visit["arrived"], visit["left_at"], visit["budget"], visit["end_bankroll"], visit["wagered"],
                 visit["returned"], visit["rounds"], json.dumps(visit.get("games", {})), visit["reason"]))
            self.db.execute(
                "UPDATE npcs SET visits = visits + 1, rounds = rounds + ?, wagered = wagered + ?, returned = returned + ?,"
                " net = net + ?, biggest_win = MAX(biggest_win, ?), busts = busts + ?, last_seen = ?, cooldown_until = ?"
                " WHERE id = ?",
                (visit["rounds"], visit["wagered"], visit["returned"], net, max(net, 0),
                 1 if visit["reason"] == "bust" else 0, visit["left_at"], cooldown_until, npc_id))

    def npc_visits(self, npc_id: int, limit: int = 20) -> list[dict]:
        rows = self.db.execute("SELECT * FROM npc_visits WHERE npc_id = ? ORDER BY id DESC LIMIT ?", (npc_id, limit))
        return [{**dict(r), "games": json.loads(r["games"]), "net": r["returned"] - r["wagered"]} for r in rows]

    def reset_npc_stats(self, npc_id: int):
        with self.db:
            self.db.execute("DELETE FROM npc_visits WHERE npc_id = ?", (npc_id,))
            self.db.execute("UPDATE npcs SET visits = 0, rounds = 0, wagered = 0, returned = 0, net = 0, biggest_win = 0,"
                            " busts = 0, last_seen = NULL, cooldown_until = NULL WHERE id = ?", (npc_id,))

    def get_json(self, key: str, default):
        raw = self.get_meta(key)
        try:
            return json.loads(raw) if raw is not None else default
        except ValueError:
            return default

    def set_json(self, key: str, value):
        self.set_meta(key, json.dumps(value))

    # ------------------------------------------------------------------ meta
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str):
        with self.db:
            self.db.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
