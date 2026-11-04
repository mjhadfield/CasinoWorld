"""
Look at or change player balances safely, instead of editing the database by
hand (a hand edit can store a balance the server can't read, e.g. '100,000').
Every change goes through the ledger. Safe to run while the server is up.
A player's balance is their cash in hand; their bank is separate (and may be
overdrawn).

    .venv/bin/python -m casino_server.admin list
    .venv/bin/python -m casino_server.admin set-balance Mike 1000      # cash in hand, pounds; 1000.50 works too
    .venv/bin/python -m casino_server.admin set-bank Mike -250         # the bank, pounds; may be negative
    .venv/bin/python -m casino_server.admin archive-stats "Before the wipe"   # a Stats archive (stats_archive.py)
    .venv/bin/python -m casino_server.admin wipe-npc-stats [--keep-tastes]   # with the server stopped: see below

wipe-npc-stats clears every NPC's figures so new ones start clean (Store.wipe_npc_stats): it won't run while the live
server's listening on 8660 (systemctl --user stop hub-proj-casino-world first), and it makes a backup beside the
database (casino.pre-npc-wipe-<time>.sqlite) and a Stats archive of the figures as they stand before it deletes
anything. Each punter gets new tastes (roster.make_tastes) unless --keep-tastes. Players' stats, wallets and the ledger
aren't touched. The rollback is in docs/development.md.

Uses the same database as the server (CASINO_DATA_DIR, default server/data/).
"""
import os
import socket
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from casino_server import roster, slot_builds, stats_archive
from casino_server.store import Store

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LIVE_PORT = 8660


def _listening(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wipe_npc_stats(store: Store, data_dir: Path, keep_tastes: bool = False) -> int:
    if data_dir.resolve() == DEFAULT_DATA_DIR.resolve() and _listening(LIVE_PORT):
        print(f"The live server's running (port {LIVE_PORT} is listening). Stop it first:"
              " systemctl --user stop hub-proj-casino-world")
        return 1
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = data_dir / f"casino.pre-npc-wipe-{stamp}.sqlite"
    store.backup(backup)
    print(f"Backed up to {backup}")
    slot_builds.install(Path(os.environ.get("CASINO_SLOT_BUILDS_DIR") or slot_builds.DEFAULT_DIR))   # (their names)
    since = store.get_meta("npc_stats_since")
    title = "Before the NPC stats wipe" + (f" (since {since[:10]})" if since else "")
    aid = stats_archive.save(data_dir, stats_archive.build(store, title))
    print(f"Archived as {aid}: \"{title}\" (the admin page's Stats archive)")
    gone = store.wipe_npc_stats()
    print("Wiped: " + ", ".join(f"{n:,} {t}" for t, n in gone.items()))
    if not keep_tastes:
        print(f"New tastes for {roster.ensure_tastes(store, everyone=True)} punters.")
    print("Done. Start the server again: systemctl --user start hub-proj-casino-world")
    return 0


def _pounds(pence) -> str:
    return f"£{pence / 100:,.2f}" if isinstance(pence, int) else f"{pence!r} (not a number -- fix with set-balance)"


def main(argv: list[str]) -> int:
    data_dir = Path(os.environ.get("CASINO_DATA_DIR", DEFAULT_DATA_DIR))
    store = Store(data_dir / "casino.sqlite")
    try:
        if argv[:1] == ["archive-stats"] and len(argv) == 2:
            slot_builds.install(Path(os.environ.get("CASINO_SLOT_BUILDS_DIR") or slot_builds.DEFAULT_DIR))   # (their names)
            aid = stats_archive.save(data_dir, stats_archive.build(store, argv[1]))
            print(f"Archived as {aid} ({stats_archive.folder(data_dir) / aid}.json); it's on the admin page's Stats archive.")
            return 0
        if argv[:1] == ["wipe-npc-stats"] and set(argv[1:]) <= {"--keep-tastes"}:
            return wipe_npc_stats(store, data_dir, keep_tastes="--keep-tastes" in argv)
        if argv[:1] == ["list"] or not argv:
            for p in store.players():
                print(f"{p['id']:>4}  {p['name']:<20} {_pounds(p['balance'])} in hand, {_pounds(p['bank'])} in the bank")
            return 0
        if argv[0] in ("set-balance", "set-bank") and len(argv) == 3:
            who, amount = argv[1], argv[2]
            matches = [p for p in store.players() if p["name"].lower() == who.lower() or str(p["id"]) == who]
            if len(matches) != 1:
                print(f"No single player called {who!r}; use their id from `list`.")
                return 1
            try:
                pence = int(Decimal(amount.replace(",", "").lstrip("£")) * 100)
            except InvalidOperation:
                print(f"{amount!r} isn't an amount of pounds.")
                return 1
            player = matches[0]
            if argv[0] == "set-bank":
                store.set_bank(player["id"], pence)
                print(f"{player['name']}'s bank: {_pounds(player['bank'])} -> {_pounds(pence)}")
                return 0
            try:
                store.set_balance(player["id"], pence)
            except ValueError as e:
                print(f"{e}.")
                return 1
            print(f"{player['name']}: {_pounds(player['balance'])} -> {_pounds(pence)}")
            return 0
        print(__doc__)
        return 1
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
