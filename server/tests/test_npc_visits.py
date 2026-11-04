"""NPC visits by time (roster.py, npc.py): about 90 minutes over several games with favourites, the archetypes' and
traits' leaving rules, and a visit carried on across a restart."""
import random
import statistics

import pytest

from casino_server import roster
from casino_server.casino import Casino
from casino_server.store import Store

from conftest import classic_floor

PACE = 0.25   # every NPC and table timer, and so the visits, at a quarter of real time


def run(store, seconds, population=12, seed=7, now=None, casino=None):
    now = now or [1_000_000.0]
    casino = casino or Casino(store, classic_floor(), npc_population=population, rng=random.Random(seed),
                              clock=lambda: now[0], wall=lambda: now[0], npc_pace=PACE, speed=PACE)
    end = now[0] + seconds
    while now[0] < end:
        now[0] += 0.25
        casino.npcs.tick(now[0])
        for runner in casino.tables.values():
            runner.publish(runner.machine.tick(now[0]))
    return casino, now


@pytest.fixture(scope="module")
def day(tmp_path_factory):
    """Sixteen hours of visits (four, at PACE) on the classic floor, short cooldowns so the whole cast comes through."""
    store = Store(tmp_path_factory.mktemp("visits") / "v.sqlite")
    store.set_json("npc_settings", {"cooldown_min": [5, 10], "bust_cooldown_min": [10, 20]})
    casino, _ = run(store, 4 * 3600)
    visits = [dict(v, archetype=r["archetype"], traits=r["traits"]) for r in store.npcs("punter")
              for v in store.npc_visits(r["id"], 1000)]
    return [v for v in visits if v["reason"] != "shutdown"]


def minutes(v):
    return (v["left_at"] - v["arrived"]) / PACE / 60


def test_visits_last_about_90_minutes_over_more_than_one_game(day):
    assert len(day) >= 30
    mean = statistics.mean(minutes(v) for v in day)
    assert 65 < mean < 115, mean
    games = statistics.mean(len([g for g, f in v["by_game"].items() if f["seconds"] > 0]) for v in day)
    assert games > 1.4, games
    for v in day:   # the time at each game is the time sat down, inside the visit
        assert sum(f["seconds"] for f in v["by_game"].values()) <= (v["left_at"] - v["arrived"]) + 1


def test_hit_and_run_leaves_sooner_and_gamblers_stay_longer(day):
    plain = [minutes(v) for v in day if "hit_and_run" not in v["traits"]]
    hit = [minutes(v) for v in day if "hit_and_run" in v["traits"]]
    if hit:
        assert statistics.mean(hit) < statistics.mean(plain)
    casual = [minutes(v) for v in day if v["archetype"] == "casual" and "hit_and_run" not in v["traits"]]
    gambler = [minutes(v) for v in day if v["archetype"] == "gambler" and "hit_and_run" not in v["traits"]
               and v["reason"] not in ("bust", "riches")]
    assert statistics.mean(gambler) > statistics.mean(casual)


def test_tastes_lean_by_archetype_and_traits():
    rng = random.Random(3)
    for arch, lean in roster.LEANS.items():
        favs = [g for _ in range(300) for g, t in roster.make_tastes({"archetype": arch, "traits": []}, rng).items()
                if t == "fav"]
        leaned = sum(g in lean or (g.startswith("pai_gow") and "pai_gow" in lean) for g in favs)
        assert leaned / len(favs) > 0.7, arch
    for _ in range(50):
        t = roster.make_tastes({"archetype": "casual", "traits": ["card_counter"]}, rng)
        assert t["blackjack"] == "fav" and 1 <= sum(x == "fav" for x in t.values()) <= 3
        t = roster.make_tastes({"archetype": "grinder", "traits": ["superstitious"]}, rng)
        assert "fav" in (t.get("roulette"), t.get("craps"))
    t = roster.make_tastes({"archetype": "grinder", "traits": [], "settings": {"favourite_games": ["slots"]}}, rng)
    assert t["slots"] == "fav"


def test_never_means_never(tmp_path):
    store = Store(tmp_path / "n.sqlite")
    roster.seed(store)
    for rec in store.npcs("punter"):
        store.update_npc(rec["id"], {"settings": {"tastes": {g: "never" for g in roster.GAMES if g != "roulette"}}})
    casino, _ = run(store, 1200, population=6)
    played = {g for r in store.npcs("punter") for v in store.npc_visits(r["id"], 100) for g in v["by_game"]}
    seated = {n.sat_game for n in casino.npcs.npcs.values() if n.sat_at is not None}
    assert (played | seated) <= {"roulette"}


def test_a_visit_carries_on_after_a_restart_without_the_downtime(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    casino, now = run(store, 600, population=4)
    here = {n.npc_id: n for n in casino.npcs.npcs.values() if not n.ended}
    assert here
    logged = {r["id"]: r["visits"] for r in store.npcs("punter")}
    casino.halt()   # (what was riding comes back to them first)
    before = {i: (n.bankroll, n.wagered, n.returned, n.rounds, n.arrived, n.visit_key, n.visit_end - now[0])
              for i, n in here.items()}
    assert {r["id"]: r["visits"] for r in store.npcs("punter")} == logged   # (no visit ended)
    assert store.db.execute("SELECT COUNT(*) FROM npc_open_visits").fetchone()[0] == len(here)
    now[0] += 900   # down a quarter of an hour
    again = Casino(store, classic_floor(), npc_population=0, rng=random.Random(2), clock=lambda: now[0],
                   wall=lambda: now[0], npc_pace=PACE, speed=PACE)
    again.npcs.tick(now[0])
    back = {n.npc_id: n for n in again.npcs.npcs.values()}
    assert set(back) == set(here)
    for i, n in back.items():
        bankroll, wagered, returned, rounds, arrived, key, left = before[i]
        assert (n.bankroll, n.wagered, n.returned, n.rounds, n.visit_key) == (bankroll, wagered, returned, rounds, key)
        assert n.arrived == pytest.approx(arrived + 900) and n.visit_end - now[0] == pytest.approx(left)
    assert store.db.execute("SELECT COUNT(*) FROM npc_open_visits").fetchone()[0] == 0
    again.npcs.close_all("done")
    for i in here:
        v = store.npc_visits(i, 1)[0]
        assert v["left_at"] - v["arrived"] == pytest.approx(600 - (before[i][4] - 1_000_000.0), abs=1)


def test_a_visit_held_too_long_is_logged_as_ended_then(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    casino, now = run(store, 300, population=3)
    ids = {n.npc_id for n in casino.npcs.npcs.values() if not n.ended}
    stopped = now[0]
    casino.halt()
    now[0] += 3 * 3600
    again = Casino(store, classic_floor(), npc_population=0, rng=random.Random(2), clock=lambda: now[0],
                   wall=lambda: now[0], npc_pace=PACE, speed=PACE)
    again.npcs.tick(now[0])
    assert not again.npcs.npcs
    for i in ids:
        v = store.npc_visits(i, 1)[0]
        assert v["reason"] == "shutdown" and v["left_at"] == pytest.approx(stopped)
