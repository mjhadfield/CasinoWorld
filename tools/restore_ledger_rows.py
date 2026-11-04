#!/usr/bin/env python3
"""Put back the four ledger rows the 2026-10-25 master-table relabel deleted.

    server/.venv/bin/python tools/restore_ledger_rows.py [--db server/data/casino.sqlite] [--dry-run]

On 25 Oct a one-off migration relabelled the Master Table's ledger rows to the game each was really played as (41
became three_card_poker), but it deleted four instead: ids 3123-3125 and 3189, from 22 Oct, net +£25 to Mike. His
cash in hand has been £25 more than his ledger adds up to since, and the balance chain breaks at 3126 and 3190
(docs/npc-data-analysis-2026-11-04.md, Problems).

The rows come back from the backup taken just before that migration, with their original id, time, amount and
balance_after. The rows after them already counted them, so the chain mends and no balance changes. The game:
3123-3125 are 28 seconds of one Blackjack hand (the payout's "side bets" note is Blackjack's alone); 3189, a lone £1
"upfront" with nothing after it, can't be told, so it stays master_table.

Safe while the server's running (one transaction; inserts below the ledger's top id). Rows already there are
skipped, so it can be run again.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "server/data"
BACKUP = DATA / "casino.pre-master-relabel.sqlite"
GAMES = {3123: "blackjack", 3124: "blackjack", 3125: "blackjack", 3189: "master_table"}
COLUMNS = ("id", "player_id", "at", "kind", "amount", "balance_after", "game", "note", "account", "detail")


def breaks(db, player_id: int) -> list[int]:
    """Ledger ids where a row's balance_after isn't the row before's plus its amount (per account)."""
    rows = db.execute("SELECT id, account, amount, balance_after FROM ledger WHERE player_id = ? ORDER BY id",
                      (player_id,)).fetchall()
    last, out = {}, []
    for i, account, amount, after in rows:
        if account in last and last[account] + amount != after:
            out.append(i)
        last[account] = after
    return out


def hand_gap(db, player_id: int) -> int:
    """Cash in hand less what the hand ledger adds up to, in pence (0 when they agree)."""
    balance = db.execute("SELECT balance FROM players WHERE id = ?", (player_id,)).fetchone()[0]
    total = db.execute("SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE player_id = ? AND account = 'hand'",
                       (player_id,)).fetchone()[0]
    return balance - total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(DATA / "casino.sqlite"))
    ap.add_argument("--backup", default=str(BACKUP))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    old = sqlite3.connect(f"file:{args.backup}?mode=ro&immutable=1", uri=True)
    has = {r[1] for r in old.execute("PRAGMA table_info(ledger)")}   # (the backup is older than `detail`)
    pick = ", ".join(c if c in has else "NULL" for c in COLUMNS)
    rows = old.execute(f"SELECT {pick} FROM ledger WHERE id IN ({', '.join('?' * len(GAMES))})",
                       tuple(GAMES)).fetchall()
    if len(rows) != len(GAMES):
        print(f"The backup has {len(rows)} of the {len(GAMES)} rows; stopping.")
        return 1
    db = sqlite3.connect(args.db, timeout=10)
    player_ids = {r[1] for r in rows}
    before = {p: (hand_gap(db, p), breaks(db, p)) for p in player_ids}
    there = {i for (i,) in db.execute(f"SELECT id FROM ledger WHERE id IN ({', '.join('?' * len(GAMES))})", tuple(GAMES))}
    todo = [dict(zip(COLUMNS, r)) for r in rows if r[0] not in there]
    for r in todo:
        r["game"] = GAMES[r["id"]]
        print(f"  {r['id']}  {r['at']}  {r['kind']:6} {r['amount'] / 100:+8.2f}  {r['game']:13} {r['note']}")
    if not todo:
        print("All four rows are already there.")
    elif args.dry_run:
        print(f"(dry run: {len(todo)} rows not written)")
    else:
        with db:
            db.executemany(f"INSERT INTO ledger ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                           [tuple(r[c] for c in COLUMNS) for r in todo])
        print(f"Put back {len(todo)} rows.")
    for p in sorted(player_ids):
        gap, chain = before[p]
        print(f"Player {p}: cash in hand less ledger {gap / 100:+.2f} -> {hand_gap(db, p) / 100:+.2f}; "
              f"chain breaks {chain or 'none'} -> {breaks(db, p) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
