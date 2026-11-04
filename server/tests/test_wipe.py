"""admin wipe-npc-stats: a backup and an archive first, then every NPC figure gone and players' untouched."""
import random

from casino_server import admin, stats_archive
from casino_server.casino import Casino
from casino_server.store import Store

from conftest import classic_floor


def test_the_wipe_backs_up_archives_and_clears_npc_figures_only(tmp_path, monkeypatch):
    monkeypatch.setenv("CASINO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CASINO_SLOT_BUILDS_DIR", str(tmp_path / "slot_builds"))
    store = Store(tmp_path / "casino.sqlite")
    now = [1_000_000.0]
    store.set_json("npc_settings", {"visit_min_grinder": [3, 5], "visit_min_casual": [3, 5], "visit_min_gambler": [3, 5]})
    casino = Casino(store, classic_floor(), npc_population=6, rng=random.Random(4), clock=lambda: now[0],
                    wall=lambda: now[0], npc_pace=0.3, speed=0.3)
    while now[0] < 1_000_000 + 1800:
        now[0] += 0.25
        casino.npcs.tick(now[0])
        for runner in casino.tables.values():
            runner.publish(runner.machine.tick(now[0]))
    casino.halt()   # (some visits put aside for a restart)
    mike = store.create_player("Mike", hand=10_000)
    store.adjust(mike.id, -500, "bet", "roulette", "upfront", {"spots": {"red": 500}})
    count = lambda t, w="": store.db.execute(f"SELECT COUNT(*) FROM {t} {w}").fetchone()[0]
    assert count("npc_visits") and count("npc_ledger") and count("bet_stats", "WHERE who = 'npc'")
    tastes = {r["id"]: r["settings"].get("tastes") for r in store.npcs("punter")}
    ledger = count("ledger")
    store.close()

    assert admin.main(["wipe-npc-stats"]) == 0
    store = Store(tmp_path / "casino.sqlite")
    for t in ("npc_visits", "npc_open_visits", "npc_ledger", "npc_game_stats"):
        assert count(t) == 0, t
    assert count("bet_stats", "WHERE who = 'npc'") == 0 and count("slot_stats", "WHERE who = 'npc'") == 0
    assert all(r["visits"] == 0 and r["wagered"] == 0 and r["cooldown_until"] is None for r in store.npcs("punter"))
    assert count("ledger") == ledger and store.balance(mike.id) == 9_500
    assert store.get_meta("npc_stats_since")
    assert any(r["settings"]["tastes"] != tastes[r["id"]] for r in store.npcs("punter"))   # (new tastes)
    assert list(tmp_path.glob("casino.pre-npc-wipe-*.sqlite"))
    archives = stats_archive.listing(tmp_path)
    assert len(archives) == 1 and archives[0]["title"].startswith("Before the NPC stats wipe")
    old = Store(next(tmp_path.glob("casino.pre-npc-wipe-*.sqlite")))
    assert old.db.execute("SELECT COUNT(*) FROM npc_visits").fetchone()[0] > 0   # (the backup has them all)
    kept = {r["id"]: r["settings"]["tastes"] for r in store.npcs("punter")}
    store.close()
    assert admin.main(["wipe-npc-stats", "--keep-tastes"]) == 0
    store = Store(tmp_path / "casino.sqlite")
    assert {r["id"]: r["settings"]["tastes"] for r in store.npcs("punter")} == kept
