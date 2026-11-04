"""The Tracker (tracking.py): every bet spot's money against its EV, for players and NPCs."""
import random
from types import SimpleNamespace

from casino_server import roster
from casino_server.casino import Casino
from casino_server.engines import three_card_poker as tcp
from casino_server.participants import HumanParticipant
from casino_server.store import Store
from casino_server.tracking import Tracker, lines

from conftest import classic_floor
from test_machine import FakeJackpot, machine


def human(store, tracker, name="Mike", balance=1_000_000):
    player = store.create_player(name, hand=balance)
    session = SimpleNamespace(entity_id="e-" + name, player=player)
    p = HumanParticipant(session, SimpleNamespace(store=store, sessions=[session]), tcp.GAME_KEY)
    p.place(tracker, "demo", "tcp_1", tcp.GAME_KEY)
    return p, player.id


def play(m, players, rounds, rng, now=0.0):
    for i, p in enumerate(players):
        m.sit(i, p, now)
    for _ in range(rounds):
        for i, p in enumerate(players):
            m.set_bets(i, {"ante": 500, "pair_plus": rng.choice([0, 100]), "jackpot": rng.choice([0, 100])}, now)
            m.ready(i, now)
        for _ in range(200):
            now += 0.5
            for i in range(len(players)):
                r = m.round.get(i)
                if m.phase == "deciding" and r is not None and not r.decided:
                    m.decide(i, rng.random() < 0.8, now)
            if any(e["kind"] == "round_end" for e in m.tick(now)):
                break
    return now


def test_a_players_rollup_equals_their_ledger(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    tracker = Tracker(store, jackpot=FakeJackpot())
    mike, mid = human(store, tracker)
    nora, nid = human(store, tracker, "Nora")
    play(machine(), [mike, nora], 60, random.Random(4))
    tracker.save()
    for pid in (mid, nid):
        ledger = store.db.execute("SELECT COALESCE(SUM(CASE WHEN kind='bet' THEN -amount END), 0),"
                                  " COALESCE(SUM(CASE WHEN kind='payout' THEN amount END), 0) FROM ledger WHERE player_id = ?",
                                  (pid,)).fetchone()
        spots = tracker.player_figures(pid)
        assert sum(r["staked"] for r in spots) == ledger[0]
        assert sum(r["returned"] for r in spots) == ledger[1]
        assert {r["spot"] for r in spots} <= {"ante", "play", "ante_bonus", "pair_plus", "jackpot"}
        ante = next(r for r in spots if r["spot"] == "ante")
        assert ante["expected"] > 0 and ante["var"] > 0   # the main line's EV, charged on the Ante
    rows = store.db.execute("SELECT DISTINCT casino, table_id FROM ledger WHERE kind != 'start'").fetchall()
    assert [tuple(r) for r in rows] == [("demo", "tcp_1")]
    house = tracker.house()
    assert sum(r["staked"] for r in house) == sum(r["staked"] for pid in (mid, nid) for r in tracker.player_figures(pid))


def test_a_refund_comes_off_the_spot_and_its_ev(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    tracker = Tracker(store, jackpot=FakeJackpot())
    p, pid = human(store, tracker)
    assert p.debit(1000, "upfront", {"spots": {"ante": 600, "pair_plus": 400}})
    p.refund(400, "taken down")
    rows = {r["spot"]: r for r in tracker.player_figures(pid)}
    assert rows["pair_plus"]["staked"] == 0 and abs(rows["pair_plus"]["expected"]) < 1e-9
    assert rows["ante"]["staked"] == 600 and rows["ante"]["expected"] > 0


def test_npc_play_is_tracked_logged_and_pruned(tmp_path):
    now = [1_000_000.0]
    store = Store(tmp_path / "n.sqlite")
    casino = Casino(store, classic_floor(), npc_population=8, rng=random.Random(3), clock=lambda: now[0],
                    wall=lambda: now[0], npc_pace=0.3, speed=0.3)
    while now[0] < 1_000_000 + 2400:
        now[0] += 0.25
        casino.npcs.tick(now[0])
        for runner in casino.tables.values():
            runner.publish(runner.machine.tick(now[0]))
    casino.npcs.close_all()
    tracker = casino.tracker
    tracker.save()
    # Each NPC's lifetime spots add up to their visits' money
    for rec in store.npcs("punter"):
        visits = store.npc_visits(rec["id"], 1000)
        spots = store.npc_game_spots(rec["id"])
        assert sum(r["staked"] for r in spots) == sum(v["wagered"] for v in visits)
        assert sum(r["returned"] for r in spots) == sum(v["returned"] for v in visits)
        for v in visits:
            assert v["casino"] == casino.id
            assert sum(g["wagered"] for g in v["by_game"].values()) == v["wagered"]
            assert v["rounds"] == sum(g["rounds"] for g in v["by_game"].values())
    log = store.db.execute("SELECT COUNT(*), MIN(at) FROM npc_ledger").fetchone()
    assert log[0] > 100
    row = store.db.execute("SELECT * FROM npc_ledger WHERE kind = 'bet' AND game != 'slots' LIMIT 1").fetchone()
    assert row["detail"] and row["visit"] and row["table_id"] and row["casino"] == casino.id
    # The House rollup's EV builds up, and the grouping puts a main line's spots together
    house = lines(tracker.edges, tracker.house(who="npc"))
    assert sum(g["expected"] for g in house) > 0
    # Prune: everything older than a day after the last move goes
    assert store.prune_npc_ledger(now[0] + 1) == log[0]
    assert store.db.execute("SELECT COUNT(*) FROM npc_ledger").fetchone()[0] == 0


def test_figures_wait_in_memory_until_saved(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    clock = [0.0]
    tracker = Tracker(store, jackpot=FakeJackpot(), clock=lambda: clock[0])
    p, pid = human(store, tracker)
    p.debit(500, "upfront", {"spots": {"ante": 500}})
    assert store.player_game_spots(pid) == []         # not yet written...
    assert tracker.player_figures(pid)[0]["staked"] == 500   # ...but read with the rest
    clock[0] = 31.0
    p.credit(1000, "win", {"spots": {"ante": {"stake": 500, "returned": 1000}}})   # (the next move after 30s saves)
    assert store.player_game_spots(pid)[0]["staked"] == 500
    assert roster.settings(store)["bet_log_days"] == 30
