"""edges.json (tools/edges.py): every bet the tables can take has a house edge, the exact ones are exact, and a
progressive Jackpot's EV follows the pool."""
import random
from fractions import Fraction

import pytest

from casino_server import edges as edges_mod
from casino_server.casino import Casino
from casino_server.engines import craps as cr
from casino_server.engines import roulette as rou
from casino_server.store import Store

from conftest import classic_floor

E = edges_mod.Edges()


def close(x, frac, tol=1e-6):
    return abs(x - float(frac)) < tol


def test_roulette_is_one_in_37_and_la_partage_halves_it_on_the_even_chances():
    for spot, bet in rou.BETS.items():
        assert close(E.spot("roulette", spot)["edge"], Fraction(1, 74) if bet.even_money else Fraction(1, 37)), spot


def test_craps_has_its_published_edges_per_decision():
    s = E.games["craps"]["spots"]
    assert close(s["pass"]["edge"], Fraction(7, 495)) and close(s["come"]["edge"], Fraction(7, 495))
    assert close(s["dont_pass"]["edge"], Fraction(3, 220)) and close(s["dont_come"]["edge"], Fraction(3, 220))
    for spot, edge in cr.EDGES.items():
        assert close(s[spot]["edge"], edge), spot
    assert all(s[x]["edge"] == 0 for x in cr.SPOTS if "odds" in x)
    assert set(cr.SPOTS) <= set(s)


def test_baccarat_matches_the_published_8_deck_figures():
    s = E.games["baccarat"]["spots"]
    assert abs(s["banker"]["edge"] - 0.010579) < 2e-5 and abs(s["player"]["edge"] - 0.012351) < 2e-5
    assert abs(s["tie"]["edge"] - 0.143596) < 2e-5


def test_a_main_line_charges_its_whole_ev_on_the_first_wager():
    s = E.games["three_card_poker"]["spots"]
    assert s["ante"]["edge"] > 0.02 and s["play"]["edge"] == 0 and s["ante_bonus"]["line"] == "main"
    assert 0.025 < s["ante"]["edge"] < 0.042   # (3.37% published; simulated)


def test_the_jackpot_ev_follows_the_pool():
    low = E.charge("three_card_poker", "jackpot", 100, pool=500_000)[0]
    high = E.charge("three_card_poker", "jackpot", 100, pool=5_000_000)[0]
    share = E.spot("three_card_poker", "jackpot")["pool"]["share"]
    assert high < low and abs((low - high) - share * 4_500_000) < 1e-6


def test_unknown_spots_are_unpriced():
    assert E.charge("three_card_poker", "nonsense", 100) is None
    assert E.charge("slots", "no_such_machine", 100) is None


@pytest.fixture(scope="module")
def floor_day(tmp_path_factory):
    """Thirty NPCs playing every table on the classic floor for two hours of fake time."""
    from casino_server import floor
    from casino_server.tables import base
    from conftest import OPEN_LIMITS
    mp = pytest.MonkeyPatch()
    mp.setattr(base, "DEFAULT_LIMITS", OPEN_LIMITS)
    mp.setattr(floor, "VIEW", (100_000, 100_000))
    now = [1_000_000.0]
    store = Store(tmp_path_factory.mktemp("edges") / "e.sqlite")
    store.set_json("npc_settings", {"cooldown_min": [0.1, 0.2], "bust_cooldown_min": [0.1, 0.2]})
    casino = Casino(store, classic_floor(), npc_population=30, rng=random.Random(5), clock=lambda: now[0],
                    wall=lambda: now[0], npc_pace=0.3, speed=0.3)
    end = now[0] + 7200
    while now[0] < end:
        now[0] += 0.25
        casino.npcs.tick(now[0])
        for runner in casino.tables.values():
            runner.publish(runner.machine.tick(now[0]))
    casino.npcs.close_all()
    casino.tracker.save()
    yield casino
    mp.undo()


def test_every_spot_the_tables_book_money_on_has_an_edge(floor_day):
    tracker = floor_day.tracker
    assert tracker.unpriced == set()
    games = {r["game"] for r in floor_day.store.bet_stats()}
    assert len(games) >= 10   # (every game on the floor got played)
    assert not [r for r in floor_day.store.bet_stats() if r["spot"] == "other"]
