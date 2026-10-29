"""The server stopping mid-hand: every stake still riding goes back, whether it stops cleanly (Casino.halt) or
crashes (the runner keeps what's riding in the store, and the next start hands it back)."""
import random

from casino_server import roster
from casino_server.casino import Casino
from casino_server.resort import Resort
from casino_server.session import Session
from casino_server.store import Store
from casino_server.tables import base

from conftest import classic_floor

HAND = 100_000


def _casino(path, now):
    return Casino(Store(path), classic_floor(), npc_population=0, rng=random.Random(1), clock=lambda: now[0],
                  wall=lambda: now[0])


def _player(casino, name="Mike"):
    session = Session()
    player = casino.store.create_player(name, hand=HAND)
    session.account, session.player = casino.store.account(player.account_id), player
    casino.enter(session)
    return session


def _sent(session) -> list:
    out = []
    while not session.queue.empty():
        out.append(session.queue.get_nowait())
    return out


def _notices(session) -> list[str]:
    return [m["message"] for m in _sent(session) if m["type"] == "notice"]


def _run(casino, now, seconds, until):
    end = now[0] + seconds
    while now[0] < end:
        now[0] += 0.25
        for runner in casino.tables.values():
            runner.publish(runner.machine.tick(now[0]))
        if until():
            return True
    return False


def _mid_hand_at_three_card_poker(casino, now, session):
    """Ante £10 and Pair Plus £5 down, played (another £10): the dealer's still to reveal."""
    casino._sit(session, {"table": "tcp_1", "seat": 0})
    runner = casino.tables["tcp_1"]
    runner.act("set_bets", 0, {"ante": 1_000, "pair_plus": 500})
    runner.act("ready", 0)
    assert _run(casino, now, 30, lambda: runner.machine.phase == "deciding")
    runner.act("decide", 0, True)
    assert casino.store.balance(session.player.id) == HAND - 2_500
    return runner


def test_every_stake_is_counted_off_by_the_end_of_its_hand(tmp_path, monkeypatch):
    """NPCs play every round game for a while: by each hand's end, every stake has been settled or swept (none is
    left for _round_over's safety net), and none is ever counted off twice."""
    monkeypatch.setattr(base, "DEFAULT_LIMITS", {"main": (100, 10**9), "side": (100, 10**9)})
    left, rounds, below = [], set(), []
    over, ride = base.TableMachine._round_over, base.TableMachine._ride

    def round_over(self):
        rounds.add(self.game)
        left.extend((self.game, v) for v in self.stakes.values())
        over(self)

    def counted(self, participant, amount):
        ride(self, participant, amount)
        if self.stakes.get(participant, 0) < 0:
            below.append(self.game)
    monkeypatch.setattr(base.TableMachine, "_round_over", round_over)
    monkeypatch.setattr(base.TableMachine, "_ride", counted)
    now = [1_000_000.0]
    casino = Casino(Store(tmp_path / "s.sqlite"), classic_floor(), npc_population=30, rng=random.Random(6),
                    clock=lambda: now[0], wall=lambda: now[0])
    while now[0] < 1_000_000 + 2_400:
        now[0] += 0.25
        casino.npcs.tick(now[0])
        for runner in casino.tables.values():
            runner.publish(runner.machine.tick(now[0]))
    assert len(rounds) >= 7, rounds
    assert left == [] and below == []


def test_stopping_mid_hand_hands_a_players_stake_back_and_tells_them(tmp_path):
    now = [0.0]
    casino = _casino(tmp_path / "s.sqlite", now)
    session = _player(casino)
    runner = _mid_hand_at_three_card_poker(casino, now, session)
    _sent(session)
    casino.halt()
    assert casino.store.balance(session.player.id) == HAND
    assert _notices(session) == ["The server's stopping mid-hand, so the £25 you had riding at Three Card Poker is "
                                 "back in your hand."]
    row = casino.store.db.execute("SELECT kind, amount, note FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    assert tuple(row) == ("bet", 2_500, Store.RETURN_NOTE)   # (taken down: it doesn't count as wagered)
    # Leaving afterwards doesn't fold the hand (nothing's dealt any more), and nothing's left to tell them next time.
    casino.leave(session)
    assert not runner.machine.round[0].folded
    assert casino.store.stakes_returned(session.player.id) == []
    assert casino.halt() == [] and casino.store.balance(session.player.id) == HAND   # (once only)


def test_what_a_hand_has_settled_stays_settled(tmp_path):
    """A folded hand's ante has been swept: only what's still on the felt comes back."""
    now = [0.0]
    casino = _casino(tmp_path / "s.sqlite", now)
    session = _player(casino)
    casino._sit(session, {"table": "tcp_1", "seat": 0})
    runner = casino.tables["tcp_1"]
    runner.act("set_bets", 0, {"ante": 1_000})
    runner.act("ready", 0)
    assert _run(casino, now, 30, lambda: runner.machine.phase == "deciding")
    runner.act("decide", 0, False)
    assert _run(casino, now, 30, lambda: runner.machine.round[0].swept)
    casino.halt()
    assert casino.store.balance(session.player.id) == HAND - 1_000


def test_a_crash_mid_hand_is_handed_back_at_the_next_start(tmp_path):
    now = [0.0]
    casino = _casino(tmp_path / "casino.sqlite", now)
    session = _player(casino)
    _mid_hand_at_three_card_poker(casino, now, session)
    pid = session.player.id
    casino.store.close()   # (the process dies: no halt)

    store = Store(tmp_path / "casino.sqlite")
    Resort(store, tmp_path)
    assert store.balance(pid) == HAND
    assert store.return_stakes() == 0   # (once)
    again = Session()
    again.player = store.character(pid)
    again.account = store.account(again.player.account_id)
    Casino(store, classic_floor(), npc_population=0, clock=lambda: 0.0, wall=lambda: 0.0).enter(again)
    assert _notices(again) == ["The server stopped mid-hand, so the £25 you had riding at Three Card Poker was "
                               "handed back to you."]


def test_the_store_only_keeps_what_is_riding_now(tmp_path):
    now = [0.0]
    casino = _casino(tmp_path / "s.sqlite", now)
    session = _player(casino)
    runner = _mid_hand_at_three_card_poker(casino, now, session)
    rows = lambda: [tuple(r) for r in casino.store.db.execute("SELECT table_id, amount, returned FROM stakes")]
    assert rows() == [("demo/tcp_1", 2_500, 0)]
    assert _run(casino, now, 60, lambda: runner.machine.phase == "betting")
    assert rows() == []


def test_craps_hands_back_every_bet_on_the_layout_with_a_lays_vig(tmp_path):
    """Contract bets too: a stop isn't the player walking away."""
    now = [0.0]
    casino = _casino(tmp_path / "s.sqlite", now)
    roster.seed(casino.store)
    session = _player(casino)
    casino._sit(session, {"table": "crp_1", "seat": 0})
    runner = casino.tables["crp_1"]
    m = runner.machine
    m.dice = lambda: (3, 3)   # the point's 6
    runner.act("set_bets", 0, {"pass": 1_000})
    runner.act("shoot", 0)
    assert _run(casino, now, 120, lambda: m.point == 6 and m.phase == "betting")
    runner.act("set_bets", 0, {"pass": 1_000, "lay_4": 2_000})
    m.dice = lambda: (1, 1)   # nothing on the layout decided
    runner.act("shoot", 0)
    assert _run(casino, now, 120, lambda: m.phase == "throwing")
    paid = HAND - casino.store.balance(session.player.id)
    assert paid == 1_000 + 2_000 + 100   # (the lay's vig, up front: 5% of its win, in whole pounds)
    casino.halt()
    assert casino.store.balance(session.player.id) == HAND
