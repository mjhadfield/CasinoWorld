import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from casino_server import casinos, floor, plan
from casino_server.app import app
from casino_server.engines.cards import Card, Deck
from casino_server.tables import base

# The floor the tests play on: the classic floor and the Blackjack pit (plan_classic.json, placed), with the casino's
# first slot bank -- ten Armadillo Goes West cabinets, slot_1..slot_10, four facing up, four down and one at each end
# -- and a spawn point by the entrance.
CLASSIC_PLAN = json.loads((Path(__file__).resolve().parent / "fixtures" / "plan_classic.json").read_text())


def pytest_addoption(parser):
    parser.addoption("--all", action="store_true", help="also run the slow simulations (@pytest.mark.slow)")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: a long simulation (minutes); skipped unless --all")


# The card tables' limits the tests play under: £1 to the most a plan allows, so a test about a game can bet what it
# likes. test_table_limits.py sets real limits on its tables.
OPEN_LIMITS = {"main": (100, plan.LIMIT_TOP), "side": (100, plan.LIMIT_TOP)}


def demo_plan_dir(data_dir):
    """Where Demo keeps its floor plan in a data dir."""
    return plan.plan_dir(casinos.casino_dir(data_dir, casinos.DEMO))


def classic_floor():
    """The classic plan's floor, for a Casino made without the app."""
    return plan.install(CLASSIC_PLAN)


@pytest.fixture(autouse=True)
def classic_plan(tmp_path, monkeypatch):
    """Every test's scratch data dir has the classic plan published as Demo's (the app's lifespan loads it from
    CASINO_DATA_DIR). Its card tables, and any made without the plan, take OPEN_LIMITS."""
    monkeypatch.setattr(base, "DEFAULT_LIMITS", OPEN_LIMITS)
    monkeypatch.setattr(plan, "DEFAULT_LIMITS", OPEN_LIMITS)
    monkeypatch.setattr(floor, "VIEW", (100_000, 100_000))   # (every table's in view: test_table_view has the real one)
    for name in ("live.json", "draft.json"):
        plan._write(demo_plan_dir(tmp_path) / name, CLASSIC_PLAN)


def pytest_collection_modifyitems(config, items):
    if config.getoption("--all"):
        return
    skip = pytest.mark.skip(reason="slow: run with --all (tools/dev.sh test --all)")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


class RiggedDeck(Deck):
    """Deals `codes` in order (seat 0's 3 cards, ..., then the dealer's 3)."""

    def __init__(self, codes):
        self.codes = codes
        super().__init__()

    def reset(self):
        self.cards = [Card.from_code(c) for c in self.codes]


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient on a scratch database and design board -- never the real ones -- with no
    NPCs and quick table timers (but a long decision window, so tests can act). New players arrive with £1,000 in
    hand (the real default is £0, and a trip to the ATM), so the table tests can bet straight away."""
    monkeypatch.setenv("CASINO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CASINO_DESIGNS_DIR", str(tmp_path / "slot_designs"))  # never the real design board
    monkeypatch.setenv("CASINO_SLOT_BUILDS_DIR", str(tmp_path / "slot_builds"))  # nor the real built slots
    monkeypatch.setenv("CASINO_NPCS", "0")
    with TestClient(app) as c:
        c.app.state.resort.casinos["demo"].store.set_json("bank_settings", {"start_hand": 1000})
        for runner in c.app.state.resort.casinos["demo"].tables.values():
            t = type(runner.machine.timings).instant()
            t.betting = t.betting_npc_only = 30.0  # Ready closes betting (min_betting is 0)
            for name in ("decide", "insurance", "turn", "setting", "human_roll"):  # long windows, so tests can act
                if hasattr(t, name):
                    setattr(t, name, 30.0)
            runner.machine.timings = t
        yield c


# A plain look for the characters tests make (the admin page's default new look).
LOOK = {"body": "female", "skin": "light", "hair": ["bob", "chestnut"], "top": ["tshirt", "teal"],
        "bottom": ["pants", "navy"], "shoes": ["shoes", "black"]}


def enter(ws, token="", name="Tester", difficulty="normal", look=None, hello=False, casino="demo"):
    """Onto a casino's floor: `join` with the token, make a character if the account has none, pick its first one
    and enter the casino. Returns (account, welcome) -- `account` as it was before the pick. With `hello`, reads the
    server's hello first."""
    if hello:
        assert ws.receive_json()["type"] == "hello"
    ws.send_json({"type": "join", "token": token})
    account = recv_until(ws, "account")
    if not account["characters"]:
        ws.send_json({"type": "create_character", "name": name, "look": look or LOOK, "difficulty": difficulty})
        account = recv_until(ws, "account")
    ws.send_json({"type": "pick_character", "id": account["characters"][0]["id"]})
    recv_until(ws, "casinos")
    ws.send_json({"type": "enter_casino", "casino": casino})
    return account, recv_until(ws, "welcome")


def rig(client, *codes, table="tcp_1"):
    client.app.state.resort.casinos["demo"].tables[table].machine.deck_factory = lambda: RiggedDeck(list(codes))


def recv_until(ws, kind, event=None, where=None):
    """Read messages until one of type `kind` arrives (for table_event: with that
    event kind, and matching `where` if given); returns it."""
    for _ in range(300):
        msg = ws.receive_json()
        if msg["type"] != kind:
            continue
        if event and msg["event"]["kind"] != event:
            continue
        if where and not where(msg):
            continue
        return msg
    raise AssertionError(f"no {kind}/{event} message")
