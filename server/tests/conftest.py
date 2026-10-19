import pytest
from fastapi.testclient import TestClient

from casino_server.app import app
from casino_server.engines.cards import Card, Deck


class RiggedDeck(Deck):
    """Deals `codes` in order (seat 0's 3 cards, ..., then the dealer's 3)."""

    def __init__(self, codes):
        self.codes = codes
        super().__init__()

    def reset(self):
        self.cards = [Card.from_code(c) for c in self.codes]


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient on a scratch database -- never the real server/data -- with no
    NPCs and quick table timers (but a long decision window, so tests can act)."""
    monkeypatch.setenv("CASINO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CASINO_NPCS", "0")
    with TestClient(app) as c:
        for runner in c.app.state.casino.tables.values():
            t = type(runner.machine.timings).instant()
            t.betting = t.betting_npc_only = 30.0  # Ready closes betting (min_betting is 0)
            for name in ("decide", "insurance", "turn", "setting", "human_roll"):  # long windows, so tests can act
                if hasattr(t, name):
                    setattr(t, name, 30.0)
            runner.machine.timings = t
        yield c


def rig(client, *codes, table="tcp_1"):
    client.app.state.casino.tables[table].machine.deck_factory = lambda: RiggedDeck(list(codes))


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
