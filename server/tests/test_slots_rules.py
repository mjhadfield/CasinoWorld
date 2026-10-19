"""The slot engine's rules (slots/), each on its own, plus the signed-off return."""
import pytest

from casino_server.slots import base, jackpots, sim
from casino_server.slots.bonuses import make_board, trail_roll, trail_start
from casino_server.slots.outcome import spin_outcome
from casino_server.slots.rng import mulberry32
from casino_server.slots.variants.armadillo import VARIANT as V


def grid_with_line(syms, line=1, fill="L1"):
    g = [fill] * 20
    for reel, row in enumerate(base.LINES[line - 1]):
        g[reel * 4 + row] = syms[reel]
    return g


def test_lines_are_the_rules_sheets_25():
    assert len(base.LINES) == 25 == len({tuple(l) for l in base.LINES})
    assert base.LINES[4] == [1, 2, 3, 2, 1] and base.LINES[24] == [1, 2, 2, 2, 3]
    assert all(len(l) == 5 and all(0 <= r < 4 for r in l) for l in base.LINES)


@pytest.mark.parametrize("syms, want", [
    (["H1", "H1", "H1", "M3", "L2"], ("H1", 3, 20)),
    (["W", "H2", "H2", "H2", "H2"], ("H2", 5, 100)),
    (["W", "W", "W", "W", "H2"], ("W", 4, 40)),          # 4 wilds (40) beat 5 snakes? no: 5 snakes pay 100
    (["W", "W", "W", "BS", "H1"], ("W", 3, 20)),         # a scatter breaks the line
    (["BS", "H1", "H1", "H1", "H1"], None),              # scatters never pay on a line
    (["M1", "M1", "W", "M2", "M2"], ("M1", 3, 16)),
])
def test_line_pays(syms, want):
    best = base.line_pay(syms)
    if syms == ["W", "W", "W", "W", "H2"]:
        want = ("H2", 5, 100)
    assert best == want


def test_lines_add_up_and_the_longest_match_pays():
    g = ["H1"] * 20
    wins = base.evaluate(g)
    assert len(wins) == 25 and all(w["count"] == 5 and w["mult"] == 120 for w in wins)


def test_no_feature_lands_on_wilds_or_scatters_and_exclusions_hold():
    for seed in range(1, 3000):
        o = spin_outcome(V, 100, mulberry32(seed))
        for c in o["wilds"]:
            assert o["after_colossal"][c] not in ("W", "BS", "FS") or c in []
        if o["trigger"]:
            assert not o["wild_reels"] and not o["colossal"]
        if o["trigger"] == "free":
            assert not o["repeat"]
        assert not (o["repeat"] and o["instant"])
        assert not (len(o["scatters"]["BS"]) >= 3 and len(o["scatters"]["FS"]) >= 3)
        for c, s in enumerate(o["landed"]):
            if s in ("BS", "FS") and not o["colossal"]:
                assert o["grid"][c] == s    # scatters are never covered


def test_free_games_always_show_a_feature():
    for seed in range(1, 500):
        assert [f for f in spin_outcome(V, 100, mulberry32(seed), free=True)["features"] if f != "repeat"]


def test_colossal_cells_count_one_by_one():
    o = next(o for seed in range(1, 100)
             if (o := spin_outcome(V, 100, mulberry32(seed), rig={"features": ["colossal"]}))["colossal"])
    col = o["colossal"]
    for r in range(col["start"], col["start"] + col["k"]):
        for row in range(4):
            assert o["after_colossal"][r * 4 + row] == V.big_strip[(col["stop"] + (row + col["offset"]) // col["k"]) % len(V.big_strip)]


def test_upgrade_moves_one_symbol_up_the_chain():
    for seed in range(1, 60):
        o = spin_outcome(V, 100, mulberry32(seed), rig={"features": ["upgrade"]})
        u = o["upgrade"]
        if u:
            assert base.UPGRADES[u["from"]] == u["to"] and all(o["grid"][c] == u["to"] for c in u["cells"])
            assert u["from"] not in o["grid"]


def test_trail_boards_keep_the_recipe():
    for seed in range(1, 200):
        b = make_board(V, mulberry32(seed))
        kinds = [s["type"] for s in b[1:-1]]
        assert len(b) == 120 and b[0]["type"] == "start" and b[-1] == {"type": "prizepot", "x": 2000}
        for k, n in V.trail["counts"].items():
            assert kinds.count(k) == n
        assert kinds.count("double") <= 1 and kinds.count("upgrade") <= 1
        assert "snake" not in kinds[:2]
        for i, k in enumerate(kinds):
            if k == "lightning":
                reach = 12 if "upgrade" in kinds[:i] else 6
                assert "snake" not in kinds[i + 1:i + 1 + reach]


def test_a_heart_saves_you_from_one_snake():
    st = trail_start(V, 100, mulberry32(1), board=[{"type": "start"}, {"type": "heart"}, {"type": "snake"},
                                                    {"type": "snake"}] + [{"type": "coin", "x": 1} for _ in range(5)] + [{"type": "prizepot", "x": 2000}])
    trail_roll(V, st, mulberry32(1), rig_bullets=1)
    assert st["hearts"] == 1
    trail_roll(V, st, mulberry32(1), rig_bullets=1)
    assert st["hearts"] == 0 and not st["done"]
    trail_roll(V, st, mulberry32(1), rig_bullets=1)
    assert st["done"]


def test_double_doubles_coins_and_the_prizepot_and_the_end_pays_it():
    board = [{"type": "start"}, {"type": "double"}, {"type": "coin", "x": 5}, {"type": "prizepot", "x": 2000}]
    st = trail_start(V, 100, mulberry32(1), board=board)
    trail_roll(V, st, mulberry32(1), rig_bullets=1)
    assert board[2]["x"] == 10 and board[3]["x"] == 4000
    trail_roll(V, st, mulberry32(1), rig_bullets=6)
    assert st["done"] and st["total"] == 4000 * 100


def test_lightning_collects_every_coin_it_passes():
    board = ([{"type": "start"}, {"type": "lightning"}] + [{"type": "coin", "x": 2} for _ in range(6)]
             + [{"type": "coin", "x": 1} for _ in range(6)] + [{"type": "prizepot", "x": 2000}])
    st = trail_start(V, 100, mulberry32(1), board=board)
    trail_roll(V, st, mulberry32(1), rig_bullets=1)
    r = trail_roll(V, st, mulberry32(1), rig_bullets=4)
    assert [e["kind"] for e in r["events"]] == ["lightning_roll"] + ["coin"] * 4 and st["total"] == 800


def test_the_pick_always_completes_the_drawn_tier_first():
    for seed in range(1, 300):
        tier = jackpots.TIER_IDS[seed % 4]
        p = jackpots.pick_sequence(tier, mulberry32(seed))
        seq = p["seq"]
        assert seq[-1] == tier and seq.count(tier) == 3 and len(seq) + len(p["rest"]) <= 12
        assert all(seq[:-1].count(t) <= 2 for t in jackpots.TIER_IDS)


def test_jackpot_odds_scale_with_the_bet():
    def rate(bet):
        rng = mulberry32(3)
        return sum(jackpots.trigger(bet, rng) is not None for _ in range(200_000)) / 200_000
    assert rate(2500) / rate(250) == pytest.approx(10, rel=0.15)


@pytest.mark.slow  # ~2 minutes: run it (tools/dev.sh test --all) after changing the slots maths
def test_the_signed_off_return():
    """Game about 91.5% (each bonus valued from its own long run times its exact odds; the
    trail's 2,000x prizepot makes a single run swing), progressives 3.75%, Buy Bonus 93.7%."""
    e = sim.expected_rtp(V, spins=200_000, bonuses=100_000, seed=11)
    assert e["game"] == pytest.approx(91.5, abs=1.25)
    assert e["trail_odds"] == pytest.approx(1 / 189, rel=0.02) and e["free_odds"] == pytest.approx(1 / 294, rel=0.02)
    assert jackpots.rtp() * 100 == pytest.approx(3.75)
    assert sim.simulate_buy(V, 250_000, 100, 12)["rtp"] == pytest.approx(93.7, abs=2.0)   # (~3 SDs: the prizepot)
