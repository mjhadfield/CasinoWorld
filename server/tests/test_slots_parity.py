"""The Python slot engine against the signed-off mockup's maths (docs/slots/mockup/slots_math.js):
the same seed must give the same spin, trail, battle, voyage, pick and simulation totals. The fixture is made
by docs/slots/tools/make_parity_fixture.js."""
import dataclasses
import json
from pathlib import Path

import pytest

from casino_server.slots import base, jackpots, sim
from casino_server.slots.bonuses import (battle_shot, battle_start, trail_play_out, trail_start, voyage_options, voyage_start,
                                        voyage_step)
from casino_server.slots.outcome import spin_outcome
from casino_server.slots.rng import mulberry32
from casino_server.slots.variants.armadillo import VARIANT as V

FIX = json.loads((Path(__file__).parent / "fixtures" / "slots_parity.json").read_text())


def view(o):
    return {"stops": o["stops"], "grid": o["grid"], "landed": o["landed"], "after_colossal": o["after_colossal"],
            "trigger": o["trigger"], "colossal": o["colossal"], "wild_reels": o["wild_reels"], "wilds": o["wilds"],
            "multiplier": o["multiplier"], "upgrade": o["upgrade"], "repeat": o["repeat"], "instant": o["instant"],
            "line_win": o["line_win"], "total": o["total"], "features": o["features"],
            "wins": [[w["line"], w["sym"], w["count"], w["pence"]] for w in o["wins"]]}


def test_generator_matches():
    rng = mulberry32(12345)
    assert [rng() for _ in range(20)] == FIX["rng"]


def test_paid_spins_match():
    for case in FIX["spins"]:
        assert view(spin_outcome(V, case["bet"], mulberry32(case["seed"]))) == case["o"], case["seed"]


def test_free_games_match():
    for case in FIX["free"]:
        assert view(spin_outcome(V, 100, mulberry32(case["seed"]), free=True)) == case["o"], case["seed"]


# The fixture's variant whose bonus scatter and Buy Bonus play the battle.
VB = dataclasses.replace(V, routes={"BS": ["battle"], "FS": ["free", "battle"], "buy": ["battle"]})
# ...and the one whose bonus scatter and Buy Bonus play the island voyage.
VY = dataclasses.replace(V, routes={"BS": ["voyage"], "FS": ["free", "voyage"], "buy": ["voyage"]})


def test_rigged_spins_match():
    for case in FIX["rigged"]:
        rig = {"features": case["features"]} if "features" in case else {"trigger": case["trigger"]}
        bet = 250 if "features" in case else 100
        v = {"battle": VB, "voyage": VY}.get(case.get("trigger"), V)
        assert view(spin_outcome(v, bet, mulberry32(case["seed"]), rig=rig)) == case["o"], case


def test_trails_match():
    for case in FIX["trails"]:
        rng = mulberry32(case["seed"])
        st = trail_start(V, 100, rng)
        rolls = trail_play_out(V, st, rng)
        assert [[r["bullets"], r["from"], r["path"], r["events"]] for r in rolls] == case["rolls"], case["seed"]
        assert (st["total"], st["pos"]) == (case["total"], case["pos"])
        assert st["board"] == case["board"]


def test_battles_match():
    for case in FIX["battles"]:
        rng, st, shots = mulberry32(case["seed"]), battle_start(V, case["bet"]), []
        while not st["done"]:
            alive = [i for i, there in enumerate(st["ships"]) if there]
            r = battle_shot(V, st, rng, alive[-1] if alive and case["seed"] % 2 == 0 else None)
            shots.append([r["target"], r["answered"], r["events"]])
        assert shots == case["shots"], case["seed"]
        assert (st["total"], st["spins"], st["cleared"], st["won"]) == (case["total"], case["spins"], case["cleared"], case["won"])


def test_jackpot_picks_and_triggers_match():
    for case in FIX["picks"]:
        assert jackpots.pick_sequence(case["tier"], mulberry32(case["seed"])) == case["p"]
    got = [jackpots.trigger(base.LADDER[s % 9] * 400, mulberry32(s)) for s in range(1, 201)]
    assert got == FIX["triggers"]


def test_exact_line_return_matches():
    assert base.exact_line_rtp(V.strips) == pytest.approx(FIX["exact"], rel=1e-12)


def test_voyages_match():
    for case in FIX["voyages"]:
        rng = mulberry32(case["seed"])
        st, steps = voyage_start(V, case["bet"], rng), []
        assert st["map"] == case["map"], case["seed"]
        while not st["done"]:
            opts = voyage_options(V, st)
            r = voyage_step(V, st, rng, None if case["seed"] % 2 else opts[st["steps"] % len(opts)])
            steps.append([r["action"], r["choice"], r["events"]])
        assert steps == case["steps"], case["seed"]
        assert (st["total"], st["spins"], st["sunk"], st["artefacts"]) == (case["total"], case["spins"], case["sunk"], case["artefacts"])


def test_simulations_match():
    r = sim.simulate(V, 20000, 100, 7)
    js = FIX["sim"]
    assert (r["plain"], r["featured"], r["trail"], r["free"], r["instant"], r["repeat_extra"], r["trails"], r["frees"], r["hits"]) == \
        (js["plain"], js["featured"], js["trail"], js["free"], js["instant"], js["repeatExtra"], js["trails"], js["frees"], js["hits"])
    b = sim.simulate_buy(V, 2000, 100, 9)
    assert b["prizepots"] == FIX["buy"]["prizepots"]
    assert b["mean"] == pytest.approx(FIX["buy"]["mean"], rel=1e-12)
    js = FIX["battleSim"]
    r = sim.simulate(VB, 20000, 100, 7)
    assert (r["battle"], r["battles"], r["free"], r["frees"], r["hits"]) == (js["battle"], js["battles"], js["free"], js["frees"], js["hits"])
    assert sim.simulate_buy(VB, 2000, 100, 9)["mean"] == pytest.approx(js["buyMean"], rel=1e-12)
    assert sim.simulate_battle(VB, 2000, 100, 9) == pytest.approx(js["mean"], rel=1e-12)
    js = FIX["voyageSim"]
    r = sim.simulate(VY, 20000, 100, 7)
    assert (r["voyage"], r["voyages"], r["free"], r["frees"], r["hits"]) == (js["voyage"], js["voyages"], js["free"], js["frees"], js["hits"])
    assert sim.simulate_buy(VY, 2000, 100, 9)["mean"] == pytest.approx(js["buyMean"], rel=1e-12)
    assert sim.simulate_voyage(VY, 2000, 100, 9) == pytest.approx(js["mean"], rel=1e-12)
