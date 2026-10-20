"""Data variants (slots built with the Slot design wizard): a variant with its own tier shape (five royals), pays
and upgrade chain, frozen by the browser's maths (slots_math.js) and loaded by the server from JSON, must spin
the same in both, so the wizard's mockup shows what the cabinet will do."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from casino_server.slots import base, sim
from casino_server.slots.outcome import spin_outcome
from casino_server.slots.rng import mulberry32
from casino_server.slots.variant import from_json

MATH = Path(__file__).resolve().parents[2] / "docs/slots/mockup/slots_math.js"

# Five low tiers (L5), dearer high pays, a two-step upgrade chain, and no Colossal Reels.
NODE = """
const M = require(process.argv[1]);
const A = M.ARMADILLO;
const counts = [0, 1, 2, 3, 4].map((r) => ({W: r ? 2 : 0, H1: 2, H2: 3, M1: 4, M2: 4, M3: 5, M4: 5, L1: 6, L2: 6, L3: 6, L4: 6, L5: 6, BS: 1, FS: 1}));
const pays = {...M.PAYS, H1: [25, 50, 150], L5: [4, 8, 20]};
const upgrades = {L1: "M3", L2: "M3", L3: "M4", L4: "M4", L5: "M4", M3: "M1", M4: "M2", M1: "H2", M2: "H2", H2: "H1"};
const features = M.FEATURES.filter((f) => f !== "colossal");
const V = M.makeVariant({...A, strips: null, freeStrips: null, bigStrip: null, id: "testtrek", name: "Test Trek", counts, pays, upgrades, features,
  bigCounts: {W: 1, H1: 2, H2: 2, M1: 3, M2: 3, M3: 3, M4: 3, L1: 4, L2: 4, L3: 4, L4: 4, L5: 4},
  symbols: {...A.symbols, L5: "Ten"}});
const variant = {id: V.id, name: V.name, symbols: V.symbols, strips: V.strips, free_strips: V.freeStrips, big_strip: V.bigStrip,
  rates: V.rates, free_rates: V.freeRates, wild_counts: V.wildCounts, wild_reel_counts: V.wildReelCounts,
  colossal_sizes: V.colossalSizes, multipliers: V.multipliers, repeats: V.repeats, instants: V.instants,
  trail: {length: V.trail.length, prizepot: V.trail.prizepot, counts: V.trail.counts, upgrade_chance: V.trail.upgradeChance,
          double_chance: V.trail.doubleChance, coins: V.trail.coins, crate_radius: V.trail.crateRadius},
  buy_cost: V.buyCost, free_games: V.freeGames, pays: V.pays, upgrades: V.upgrades, features: V.features};
const spins = [];
for (let s = 1; s <= 300; s++) {
  const o = M.spinOutcome(V, M.LADDER[s % 9], M.mulberry32(s));
  spins.push({seed: s, stops: o.stops, grid: o.grid, total: o.total, upgrade: o.upgrade, wins: o.wins.map((w) => [w.line, w.sym, w.count, w.pence])});
}
console.log(JSON.stringify({variant, spins, exact: M.exactLineRtp(V.strips, V.pays)}));
"""


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if not shutil.which("node"):
        pytest.skip("needs node")
    out = json.loads(subprocess.run(["node", "-e", NODE, str(MATH)], capture_output=True, text=True, check=True).stdout)
    path = tmp_path_factory.mktemp("variants") / "testtrek.json"
    path.write_text(json.dumps(out["variant"]))
    return from_json(path), out


def test_a_data_variant_loads_with_its_own_tables(built):
    v, _ = built
    assert v.id == "testtrek" and v.pays["L5"] == (4, 8, 20) and v.upgrades["L5"] == "M4"
    assert "colossal" not in v.features and v.wild_counts[0] == (1, 40)


def test_it_spins_the_same_as_the_browser(built):
    v, out = built
    for case in out["spins"]:
        o = spin_outcome(v, base.LADDER[case["seed"] % 9], mulberry32(case["seed"]))
        assert o["stops"] == case["stops"] and o["grid"] == case["grid"], case["seed"]
        assert [[w["line"], w["sym"], w["count"], w["pence"]] for w in o["wins"]] == case["wins"], case["seed"]
        assert o["total"] == case["total"]
    assert any(w[1] == "L5" for c in out["spins"] for w in c["wins"])        # the fifth royal pays
    assert any(c["upgrade"] and c["upgrade"]["from"] == "L5" for c in out["spins"])


def test_its_maths_uses_its_own_pays(built):
    v, out = built
    assert base.exact_line_rtp(v.strips, v.pays) == pytest.approx(out["exact"], rel=1e-12)
    assert base.exact_line_rtp(v.strips, v.pays) != pytest.approx(base.exact_line_rtp(v.strips), rel=1e-6)
    assert sim.simulate(v, 3000, 100, 7)["plain"] > 0
