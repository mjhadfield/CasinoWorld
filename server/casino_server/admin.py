"""
Look at or change player balances safely, instead of editing the database by
hand (a hand edit can store a balance the server can't read, e.g. '100,000').
Every change goes through the ledger. Safe to run while the server is up.
A player's balance is their cash in hand; their bank is separate (and may be
overdrawn).

    .venv/bin/python -m casino_server.admin list
    .venv/bin/python -m casino_server.admin set-balance Mike 1000      # cash in hand, pounds; 1000.50 works too
    .venv/bin/python -m casino_server.admin set-bank Mike -250         # the bank, pounds; may be negative

Uses the same database as the server (CASINO_DATA_DIR, default server/data/).
"""
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from casino_server.store import Store

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _pounds(pence) -> str:
    return f"£{pence / 100:,.2f}" if isinstance(pence, int) else f"{pence!r} (not a number -- fix with set-balance)"


def main(argv: list[str]) -> int:
    store = Store(Path(os.environ.get("CASINO_DATA_DIR", DEFAULT_DATA_DIR)) / "casino.sqlite")
    try:
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
