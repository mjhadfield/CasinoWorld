"""
SQLite persistence: accounts (one per device, by its token), their characters (the `players` table: up to
MAX_CHARACTERS each), the characters' money, a ledger of every balance change, and the progressive jackpot.

An account is who's at the keyboard: bans, timeouts and the admin page's Protected belong to it, so they cover
all its characters. A character is who walks the floor: a name, a look, a difficulty and its own money and stats.

A character has cash in hand (`balance`: what they bet with, and what the game's
top-left shows) and a bank balance (`bank`, which may go overdrawn), and the
lobby's ATM moves money between them (bank.py's rules, transfer() here).

All money is integer pence. Every change to cash in hand goes through adjust(),
and every ATM move through transfer(), each writing its ledger rows (one per
account) in the same transaction, so both balances always reconcile.
"""
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STARTING_BANK = 100_000  # £1,000 (new characters get bank.py's setting; this is its default, and what existing
                         # players were given when the bank arrived)
MAX_CHARACTERS = 3       # per account
DIFFICULTIES = ("easy", "normal", "hard")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id         INTEGER PRIMARY KEY,
    token      TEXT    NOT NULL UNIQUE,    -- the device's
    created_at TEXT    NOT NULL,
    protected  INTEGER NOT NULL DEFAULT 0, -- the admin page won't delete, ban or time them out
    banned     INTEGER NOT NULL DEFAULT 0,
    timeout_until REAL,                    -- unix time a timeout ends
    bar_reason TEXT                        -- shown to them with a ban or timeout
);
CREATE TABLE IF NOT EXISTS players (      -- the characters
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    name       TEXT    NOT NULL,
    balance    INTEGER NOT NULL,           -- cash in hand
    created_at TEXT    NOT NULL,
    bank       INTEGER NOT NULL DEFAULT 0, -- may be negative (overdrawn)
    last_withdraw_at REAL,                 -- unix time of the last ATM withdrawal
    last_big_at      REAL,                 -- and of the last one over the usual limit (bank.py)
    look       TEXT,                       -- JSON look spec (art.py); NULL: the stock player_default sheet
    difficulty TEXT    NOT NULL DEFAULT 'normal',   -- 'easy' | 'normal' | 'hard': what the bank started with
    last_played_at REAL,                   -- unix time it was last picked
    last_casino TEXT                       -- the casino it last entered (casinos.py)
);
CREATE TABLE IF NOT EXISTS ledger (
    id            INTEGER PRIMARY KEY,
    player_id     INTEGER NOT NULL REFERENCES players(id),
    at            TEXT    NOT NULL,
    kind          TEXT    NOT NULL,  -- 'start' | 'bet' | 'payout' | 'adjust' | 'withdraw' | 'deposit' (and old 'top_up')
    amount        INTEGER NOT NULL,  -- signed pence
    balance_after INTEGER NOT NULL,
    game          TEXT,
    note          TEXT,
    account       TEXT    NOT NULL DEFAULT 'hand'  -- 'hand' | 'bank'
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
    cooldown_until REAL,                         -- unix time
    archived_at    TEXT                          -- set: in the archive (off the floor, out of the roster)
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
    reason       TEXT    NOT NULL                -- 'bust' | 'done' | 'hit_and_run' | 'riches' | 'admin' | 'shutdown' | 'npcs_off'
);
CREATE TABLE IF NOT EXISTS slot_stats (
    variant  TEXT    NOT NULL,
    who      TEXT    NOT NULL,             -- 'human' | 'npc'
    spins    INTEGER NOT NULL DEFAULT 0,
    staked   INTEGER NOT NULL DEFAULT 0,   -- pence, spins and bought bonuses
    returned INTEGER NOT NULL DEFAULT 0,   -- pence, every win, bonus and jackpot
    bonuses  INTEGER NOT NULL DEFAULT 0,
    jackpots INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (variant, who)
);
"""


class InsufficientFunds(Exception):
    pass


@dataclass
class Player:
    """A character."""
    id: int
    account_id: int
    name: str
    balance: int                  # cash in hand
    bank: int = 0
    last_withdraw_at: float | None = None
    last_big_at: float | None = None
    look: dict | None = None      # the spec; None: player_default
    difficulty: str = "normal"


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
        self._add_bank()
        added = {"npcs": {"archived_at": "TEXT"}}
        if "token" in self._columns("players"):   # (from before accounts: its columns that came later, for the move)
            added["players"] = {"last_big_at": "REAL", "protected": "INTEGER NOT NULL DEFAULT 0",
                                "banned": "INTEGER NOT NULL DEFAULT 0", "timeout_until": "REAL", "bar_reason": "TEXT"}
        for table, columns in added.items():   # columns that came after the table did
            have = self._columns(table)
            for name, decl in columns.items():
                if name not in have:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        self.db.commit()
        self._add_accounts(path)
        if "last_casino" not in self._columns("players"):   # (came with several casinos)
            self.db.execute("ALTER TABLE players ADD COLUMN last_casino TEXT")
        self.db.execute("CREATE INDEX IF NOT EXISTS players_account ON players(account_id)")
        self.db.commit()

    def _columns(self, table: str) -> set[str]:
        return {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}

    def _add_accounts(self, path: Path):
        """A database from before characters (a player per device token): back it up beside itself as
        <name>.pre-characters.sqlite, then give each player an account holding its token and bar state, and make
        it that account's one Normal character, keeping its id (so the ledger and stats carry on)."""
        if "token" not in self._columns("players"):
            return
        backup = path.with_name(f"{path.stem}.pre-characters.sqlite")
        if not backup.exists():
            dest = sqlite3.connect(backup)
            self.db.backup(dest)
            dest.close()
        self.db.execute("PRAGMA foreign_keys = OFF")   # (the ledger points at players while it's rebuilt)
        try:
            with self.db:
                self.db.execute("INSERT INTO accounts (id, token, created_at, protected, banned, timeout_until, bar_reason)"
                                " SELECT id, token, created_at, protected, banned, timeout_until, bar_reason FROM players")
                self.db.execute("""CREATE TABLE players_new (
                    id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id), name TEXT NOT NULL,
                    balance INTEGER NOT NULL, created_at TEXT NOT NULL, bank INTEGER NOT NULL DEFAULT 0,
                    last_withdraw_at REAL, last_big_at REAL, look TEXT, difficulty TEXT NOT NULL DEFAULT 'normal',
                    last_played_at REAL)""")
                self.db.execute("INSERT INTO players_new (id, account_id, name, balance, created_at, bank, last_withdraw_at,"
                                " last_big_at) SELECT id, id, name, balance, created_at, bank, last_withdraw_at, last_big_at"
                                " FROM players")
                self.db.execute("DROP TABLE players")
                self.db.execute("ALTER TABLE players_new RENAME TO players")
                bad = self.db.execute("PRAGMA foreign_key_check").fetchall()
                if bad:
                    raise sqlite3.IntegrityError(f"moving players to accounts broke {len(bad)} references")
        finally:
            self.db.execute("PRAGMA foreign_keys = ON")

    def _add_bank(self):
        """A database from before the bank: add its columns, and give everyone already playing the starting bank
        (their balance stays as their cash in hand)."""
        if "bank" in {r["name"] for r in self.db.execute("PRAGMA table_info(players)")}:
            return
        with self.db:
            self.db.execute("ALTER TABLE players ADD COLUMN bank INTEGER NOT NULL DEFAULT 0")
            self.db.execute("ALTER TABLE players ADD COLUMN last_withdraw_at REAL")
            self.db.execute("ALTER TABLE ledger ADD COLUMN account TEXT NOT NULL DEFAULT 'hand'")
            self.db.execute("UPDATE players SET bank = ?", (STARTING_BANK,))
            self.db.execute(
                "INSERT INTO ledger (player_id, at, kind, amount, balance_after, account, note)"
                " SELECT id, ?, 'start', ?, ?, 'bank', 'the bank opened' FROM players", (_now(), STARTING_BANK, STARTING_BANK))

    def close(self):
        self.db.close()

    # ------------------------------------------------------------------ accounts and characters
    def account_by_token(self, token: str) -> dict | None:
        row = self.db.execute("SELECT id, token FROM accounts WHERE token = ?", (token,)).fetchone()
        return dict(row) if row else None

    def create_account(self) -> dict:
        token = secrets.token_urlsafe(24)
        with self.db:
            self.db.execute("INSERT INTO accounts (token, created_at) VALUES (?, ?)", (token, _now()))
        return self.account_by_token(token)

    _CHARACTER = "id, account_id, name, balance, bank, last_withdraw_at, last_big_at, look, difficulty"

    def _character(self, row) -> Player:
        d = dict(row)
        d["look"] = json.loads(d["look"]) if d["look"] else None
        return Player(**d)

    def character(self, player_id: int) -> Player | None:
        row = self.db.execute(f"SELECT {self._CHARACTER} FROM players WHERE id = ?", (player_id,)).fetchone()
        return self._character(row) if row else None

    def characters(self, account_id: int) -> list[Player]:
        """An account's characters, oldest first."""
        return [self._character(r) for r in self.db.execute(
            f"SELECT {self._CHARACTER} FROM players WHERE account_id = ? ORDER BY id", (account_id,))]

    def last_played(self, account_id: int) -> int | None:
        row = self.db.execute("SELECT id FROM players WHERE account_id = ? AND last_played_at IS NOT NULL"
                              " ORDER BY last_played_at DESC LIMIT 1", (account_id,)).fetchone()
        return row[0] if row else None

    def create_character(self, account_id: int, name: str, look: dict | None = None, difficulty: str = "normal",
                         bank: int = STARTING_BANK, hand: int = 0) -> Player:
        """A new character, with its starting bank (and cash in hand) on the ledger."""
        with self.db:
            cur = self.db.execute(
                "INSERT INTO players (account_id, name, balance, bank, created_at, look, difficulty)"
                " VALUES (?, ?, 0, ?, ?, ?, ?)",
                (account_id, name, bank, _now(), json.dumps(look, sort_keys=True) if look else None, difficulty))
            player_id = cur.lastrowid
            self.db.execute(
                "INSERT INTO ledger (player_id, at, kind, amount, balance_after, account) VALUES (?, ?, 'start', ?, ?, 'bank')",
                (player_id, _now(), bank, bank))
        if hand:
            self.adjust(player_id, hand, "start")
        return self.character(player_id)

    def create_player(self, name: str = "", bank: int = STARTING_BANK, hand: int = 0) -> Player:
        """A new account with one character (named "Guest <id>" when no name's given): for tests and tools."""
        account = self.create_account()
        p = self.create_character(account["id"], name or "Guest", bank=bank, hand=hand)
        if not name:
            self.update_character(p.id, name=f"Guest {p.id}")
        return self.character(p.id)

    def update_character(self, player_id: int, name: str | None = None, look: dict | None = None):
        with self.db:
            if name is not None:
                self.db.execute("UPDATE players SET name = ? WHERE id = ?", (name, player_id))
            if look is not None:
                self.db.execute("UPDATE players SET look = ? WHERE id = ?", (json.dumps(look, sort_keys=True), player_id))

    def played(self, player_id: int, now: float):
        with self.db:
            self.db.execute("UPDATE players SET last_played_at = ? WHERE id = ?", (now, player_id))

    def entered(self, player_id: int, casino_id: str):
        with self.db:
            self.db.execute("UPDATE players SET last_casino = ? WHERE id = ?", (casino_id, player_id))

    def last_casino(self, player_id: int) -> str | None:
        row = self.db.execute("SELECT last_casino FROM players WHERE id = ?", (player_id,)).fetchone()
        return row["last_casino"] if row else None

    # A player deleted on the admin page may still have a hand finishing at a table: their balance reads 0 and
    # money moves for them are dropped (adjust), rather than failing the table.
    def balance(self, player_id: int) -> int:
        row = self.db.execute("SELECT balance FROM players WHERE id = ?", (player_id,)).fetchone()
        return row[0] if row else 0

    def bank(self, player_id: int) -> tuple[int, float | None]:
        """(bank balance, unix time of the last withdrawal or None)."""
        row = self.db.execute("SELECT bank, last_withdraw_at FROM players WHERE id = ?", (player_id,)).fetchone()
        return (row[0], row[1]) if row else (0, None)

    def last_big_at(self, player_id: int) -> float | None:
        """Unix time of the last withdrawal over the usual limit (bank.py), or None."""
        return self.db.execute("SELECT last_big_at FROM players WHERE id = ?", (player_id,)).fetchone()[0]

    def adjust(self, player_id: int, amount: int, kind: str, game: str | None = None, note: str | None = None) -> int:
        """Changes cash in hand by `amount` (signed pence) and records it. Raises
        InsufficientFunds rather than ever going below zero. Returns the new balance."""
        with self.db:
            if self.db.execute("SELECT 1 FROM players WHERE id = ?", (player_id,)).fetchone() is None:
                return 0   # (deleted)
            balance = self.balance(player_id) + amount
            if balance < 0:
                raise InsufficientFunds()
            self.db.execute("UPDATE players SET balance = ? WHERE id = ?", (balance, player_id))
            self.db.execute(
                "INSERT INTO ledger (player_id, at, kind, amount, balance_after, game, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (player_id, _now(), kind, amount, balance, game, note))
        return balance

    def transfer(self, player_id: int, to_hand: int, now: float, big: bool = False) -> tuple[int, int]:
        """The ATM: moves `to_hand` pence from the bank to cash in hand (a withdrawal, which notes the time, and as
        the last bigger one when `big`), or the other way when it's negative (a deposit). The bank may go overdrawn; cash in hand can't go below zero
        (InsufficientFunds). The rules on what's allowed are bank.py's. Returns (bank, cash in hand)."""
        kind = "withdraw" if to_hand > 0 else "deposit"
        with self.db:
            bank = self.bank(player_id)[0] - to_hand
            hand = self.balance(player_id) + to_hand
            if hand < 0:
                raise InsufficientFunds()
            self.db.execute("UPDATE players SET bank = ?, balance = ? WHERE id = ?", (bank, hand, player_id))
            if kind == "withdraw":
                self.db.execute("UPDATE players SET last_withdraw_at = ? WHERE id = ?", (now, player_id))
            if big:
                self.db.execute("UPDATE players SET last_big_at = ? WHERE id = ?", (now, player_id))
            at = _now()
            for account, amount, after in (("bank", -to_hand, bank), ("hand", to_hand, hand)):
                self.db.execute(
                    "INSERT INTO ledger (player_id, at, kind, amount, balance_after, account) VALUES (?, ?, ?, ?, ?, ?)",
                    (player_id, at, kind, amount, after, account))
        return bank, hand

    def atm_history(self, player_id: int, n: int = 4) -> list[dict]:
        """The last `n` ATM moves, newest first: [{"kind": withdraw|deposit, "amount" (pence, positive), "at" (ISO)}]."""
        return [{"kind": r["kind"], "amount": abs(r["amount"]), "at": r["at"]} for r in self.db.execute(
            "SELECT kind, amount, at FROM ledger WHERE player_id = ? AND account = 'hand' AND kind IN ('withdraw', 'deposit')"
            " ORDER BY id DESC LIMIT ?", (player_id, n))]

    def set_bank(self, player_id: int, pence: int, note: str = "set by admin") -> int:
        """Sets a bank balance outright (it may be negative), with a ledger row for the difference."""
        with self.db:
            old = self.bank(player_id)[0]
            self.db.execute("UPDATE players SET bank = ? WHERE id = ?", (pence, player_id))
            self.db.execute(
                "INSERT INTO ledger (player_id, at, kind, amount, balance_after, account, note) VALUES (?, ?, ?, ?, ?, 'bank', ?)",
                (player_id, _now(), "adjust", pence - old, pence, note))
        return pence

    def players(self) -> list[dict]:
        """Every player, with how SQLite is holding the balance (it should be an
        integer of pence; a hand edit like '100,000' gets stored as text)."""
        return [dict(r) for r in self.db.execute(
            "SELECT id, name, balance, bank, typeof(balance) AS stored_as FROM players ORDER BY id")]

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
                last = self.db.execute("SELECT balance_after FROM ledger WHERE player_id = ? AND account = 'hand'"
                                       " ORDER BY id DESC LIMIT 1",
                                       (player_id,)).fetchone()
                raw = last[0] if last else 0
            self.db.execute("UPDATE players SET balance = ? WHERE id = ?", (pence, player_id))
            self.db.execute(
                "INSERT INTO ledger (player_id, at, kind, amount, balance_after, game, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (player_id, _now(), "adjust", pence - raw, pence, None, note))
        return pence

    # ------------------------------------------------------------------ player management (the admin page)
    # Protected, bans and timeouts are the account's: they cover every character on that device.
    _PLAYER_ADMIN = ("p.id, p.name, p.created_at, p.account_id, p.difficulty, a.protected, a.banned, a.timeout_until,"
                     " a.bar_reason, (SELECT COUNT(*) FROM players q WHERE q.account_id = p.account_id) AS characters")

    def player(self, player_id: int) -> dict | None:
        row = self.db.execute(f"SELECT {self._PLAYER_ADMIN} FROM players p JOIN accounts a ON a.id = p.account_id"
                              " WHERE p.id = ?", (player_id,)).fetchone()
        return {**dict(row), "protected": bool(row["protected"]), "banned": bool(row["banned"])} if row else None

    def account(self, account_id: int) -> dict | None:
        row = self.db.execute("SELECT id, created_at, protected, banned, timeout_until, bar_reason FROM accounts"
                              " WHERE id = ?", (account_id,)).fetchone()
        return {**dict(row), "protected": bool(row["protected"]), "banned": bool(row["banned"])} if row else None

    def barred(self, account_id: int, now: float) -> dict | None:
        """{kind: "ban" | "timeout", until (unix time or None), reason} while the account's kept out, else None."""
        a = self.account(account_id)
        if a is None:
            return None
        if a["banned"]:
            return {"kind": "ban", "until": None, "reason": a["bar_reason"] or ""}
        if a["timeout_until"] and a["timeout_until"] > now:
            return {"kind": "timeout", "until": a["timeout_until"], "reason": a["bar_reason"] or ""}
        return None

    def set_protected(self, account_id: int, on: bool):
        with self.db:
            self.db.execute("UPDATE accounts SET protected = ? WHERE id = ?", (int(on), account_id))

    def set_bar(self, account_id: int, banned: bool = False, until: float | None = None, reason: str | None = None):
        """Ban the account, time it out till `until`, or (neither) let it back in."""
        with self.db:
            self.db.execute("UPDATE accounts SET banned = ?, timeout_until = ?, bar_reason = ? WHERE id = ?",
                            (int(banned), until, reason or None, account_id))

    def delete_player(self, player_id: int):
        """A character gone for good, with its ledger (the account stays)."""
        with self.db:
            self.db.execute("DELETE FROM ledger WHERE player_id = ?", (player_id,))
            self.db.execute("DELETE FROM players WHERE id = ?", (player_id,))

    def delete_account(self, account_id: int):
        """An account and all its characters gone for good."""
        with self.db:
            self.db.execute("DELETE FROM ledger WHERE player_id IN (SELECT id FROM players WHERE account_id = ?)",
                            (account_id,))
            self.db.execute("DELETE FROM players WHERE account_id = ?", (account_id,))
            self.db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

    def player_stats(self) -> list[dict]:
        """Every character's lifetime figures from the ledger: staked, returned, net, last
        activity, and the same per game (with its account's bar state)."""
        rows = self.db.execute("""
            SELECT p.id, p.name, p.balance, p.bank, p.created_at, p.account_id, p.difficulty,
                   a.protected, a.banned, a.timeout_until, a.bar_reason, l.game,
                   COALESCE(SUM(CASE WHEN l.kind = 'bet' THEN -l.amount END), 0) AS wagered,
                   COALESCE(SUM(CASE WHEN l.kind = 'payout' THEN l.amount END), 0) AS returned,
                   COUNT(CASE WHEN l.kind = 'bet' AND l.amount < 0 THEN 1 END) AS bets,
                   MAX(l.at) AS last_at
            FROM players p JOIN accounts a ON a.id = p.account_id LEFT JOIN ledger l ON l.player_id = p.id
            GROUP BY p.id, l.game ORDER BY p.id""").fetchall()
        players: dict[int, dict] = {}
        for r in rows:
            p = players.setdefault(r["id"], {"id": r["id"], "name": r["name"], "balance": r["balance"],
                                             "bank": r["bank"], "created_at": r["created_at"],
                                             "account_id": r["account_id"], "difficulty": r["difficulty"],
                                             "protected": bool(r["protected"]),
                                             "banned": bool(r["banned"]), "timeout_until": r["timeout_until"],
                                             "bar_reason": r["bar_reason"], "wagered": 0, "returned": 0, "bets": 0,
                                             "last_at": None, "games": {}})
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

    def npcs(self, role: str | None = None, archived: bool | None = False) -> list[dict]:
        """The roster (archived False), the archive (True) or everyone (None)."""
        where, args = [], []
        if role:
            where.append("role = ?"); args.append(role)
        if archived is not None:
            where.append("archived_at IS " + ("NOT NULL" if archived else "NULL"))
        q = "SELECT * FROM npcs" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY role, name"
        return [self._npc_row(r) for r in self.db.execute(q, args)]

    def set_archived(self, npc_id: int, on: bool):
        with self.db:
            self.db.execute("UPDATE npcs SET archived_at = ? WHERE id = ?", (_now() if on else None, npc_id))

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

    # ------------------------------------------------------------------ slot machines' figures (slots/stats.py)
    def add_slot_stats(self, counts: dict):
        """Adds {(variant, who): {spins, staked, returned, bonuses, jackpots}} to the running totals."""
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('slot_stats_since', ?)", (_now(),))
            for (variant, who), c in counts.items():
                self.db.execute(
                    "INSERT INTO slot_stats (variant, who, spins, staked, returned, bonuses, jackpots) VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(variant, who) DO UPDATE SET spins = spins + excluded.spins, staked = staked + excluded.staked, "
                    "returned = returned + excluded.returned, bonuses = bonuses + excluded.bonuses, jackpots = jackpots + excluded.jackpots",
                    (variant, who, c["spins"], c["staked"], c["returned"], c["bonuses"], c["jackpots"]))

    def slot_stats(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM slot_stats ORDER BY variant, who")]

    # ------------------------------------------------------------------ meta
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str):
        with self.db:
            self.db.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
