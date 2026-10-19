"""Roulette: the bet catalogue and its arithmetic, and the table's round flow."""
import random
from fractions import Fraction

import pytest

from casino_server.engines import roulette as rou
from casino_server.tables.base import TableError
from casino_server.tables.roulette import RouletteMachine, Timings

from test_machine import FakeParticipant


# ---------------------------------------------------------------- the engine
def test_the_catalogue_has_every_bet_once():
    counts = {}
    for bet in rou.BETS.values():
        counts[len(bet.numbers)] = counts.get(len(bet.numbers), 0) + 1
    # 37 straights, 60 splits, 12 streets + 2 trios, 22 corners + first four, 11 lines, 6 columns/dozens, 6 even chances
    assert counts == {1: 37, 2: 60, 3: 14, 4: 23, 6: 11, 12: 6, 18: 6}
    assert len(rou.SPOTS) == 157
    assert len({b.numbers for b in rou.BETS.values()}) == 157   # no two ids cover the same numbers


def test_inside_bets_cover_neighbouring_numbers_on_the_layout():
    col, row = (lambda n: (n - 1) // 3), (lambda n: (n - 1) % 3)
    for bet in rou.BETS.values():
        ns = [n for n in bet.numbers if n]
        if len(bet.numbers) in (2, 4) and 0 not in bet.numbers:
            cols, rows = {col(n) for n in ns}, {row(n) for n in ns}
            assert max(cols) - min(cols) <= 1 and max(rows) - min(rows) <= 1, bet.id
    assert rou.BETS["co_17_21"].numbers == (17, 18, 20, 21)
    assert rou.BETS["ln_7"].numbers == (7, 8, 9, 10, 11, 12)
    assert rou.BETS["col1"].numbers[:3] == (1, 4, 7)


def test_wheel_and_colours():
    assert sorted(rou.WHEEL) == list(range(37))
    assert len(rou.RED) == 18 and 0 not in rou.RED
    # Red and black alternate round the wheel.
    seq = [rou.colour(n) for n in rou.WHEEL[1:]]
    assert all(a != b for a, b in zip(seq, seq[1:]))
    assert rou.describe(17) == "17, black, odd, low" and rou.describe(0) == "Zero"


@pytest.mark.parametrize("spot", rou.SPOTS)
def test_every_bet_gives_the_house_one_in_37(spot):
    """Expected return of a £1 bet over the 37 pockets: -1/37, or -1/74 on the even chances (La Partage)."""
    stake = 200  # even, so La Partage's half is whole
    ev = sum(Fraction(rou.settle(n, {spot: stake})[spot] - stake, stake) for n in range(37)) / 37
    assert ev == (Fraction(-1, 74) if rou.BETS[spot].even_money else Fraction(-1, 37))


def test_settle_pays_by_the_table_and_halves_on_zero():
    bets = {"n17": 100, "sp_17_20": 100, "co_17_21": 100, "black": 1_000, "red": 1_000, "doz2": 500, "col2": 500}
    r = rou.settle(17, bets)
    assert r == {"n17": 3_600, "sp_17_20": 1_800, "co_17_21": 900, "black": 2_000, "red": 0, "doz2": 1_500, "col2": 1_500}
    z = rou.settle(0, bets)
    assert z["black"] == z["red"] == 500 and z["n17"] == 0 and z["doz2"] == 0


def test_every_landing_ends_in_the_drawn_pocket_in_a_few_seconds():
    rng = random.Random(1)
    for _ in range(5000):
        ball = round(rng.uniform(0, 6.283), 6)
        number = rng.randrange(37)
        arrival = rou.arrival_pocket(ball)
        plan = rou.plan_landing(arrival, number, rng)
        end = (arrival - sum(length for _, length, _ in plan)) % 37
        k = rou.WHEEL.index(number)
        assert min(abs(end - k), 37 - abs(end - k)) < 1e-3
        assert plan[0][0] == "s" and all(d > 0 for _, _, d in plan)
        assert 1.5 < rou.landing_seconds(plan) < 8.5
        # skids only ever slow the ball (each starts no faster than the last ended)
        v = rou.ARRIVAL_SPEED
        for kind, length, d in plan:
            if kind == "s":
                v1 = 2 * length / d - v
                assert 0 < v1 <= v + 1e-6
                v = v1 * 0.85


# ---------------------------------------------------------------- the table
class Fixed(random.Random):
    """Draws the numbers given, in order (then the landing pattern 0)."""
    def __init__(self, *numbers):
        super().__init__(0)
        self.queue = list(numbers)

    def randrange(self, *args):
        if args == (37,) and self.queue:
            return self.queue.pop(0)
        return 0


def table(*numbers, **timings):
    t = Timings.instant()
    for k, v in timings.items():
        setattr(t, k, v)
    return RouletteMachine("rou_test", 6, t, rng=Fixed(*([0] * 12 + list(numbers))))


def test_a_round_takes_bets_late_draws_at_no_more_bets_and_pays():
    mike, nora = FakeParticipant("Mike"), FakeParticipant("Nora")
    m = table(17, spin_open=4.0, ball_track=7.6)
    m.sit(0, mike, 0)
    m.sit(1, nora, 0)
    m.set_bets(0, {"n17": 500, "red": 1_000}, 0)
    m.set_bets(1, {"black": 2_000}, 0)
    m.ready(0, 0)
    m.ready(1, 0)
    events = m.tick(0)
    assert [e["kind"] for e in events if e["kind"] != "say"] == ["spin"]
    assert m.phase == "spinning" and m.number is None   # nothing's drawn while bets are open
    m.set_bet(1, "n17", 100, 1.0)                        # a late bet
    with pytest.raises(TableError, match="already spinning"):
        m.ready(1, 1.0)
    events = m.tick(4.0)
    nmb = next(e for e in events if e["kind"] == "no_more_bets")
    assert nmb["number"] == 17 and m.phase == "rolling"
    assert nmb["land_in"] == pytest.approx(3.6 + rou.landing_seconds(m.landing), abs=0.01)
    assert nmb["landing"] == m.landing and sum(x[1] for x in m.landing) >= 4
    assert mike.balance == 100_000 - 1_500 and nora.balance == 100_000 - 2_100   # taken at no more bets
    with pytest.raises(TableError, match="closed"):
        m.set_bet(0, "n5", 100, 5.0)
    events = m.tick(100.0)   # lands, called, swept, settled, cleared, open again
    kinds = [e["kind"] for e in events if e["kind"] != "say"]
    assert kinds[:2] == ["ball_landed", "sweep"] and kinds[-2:] == ["round_end", "betting_open"]
    sweep = next(e for e in events if e["kind"] == "sweep")["seats"]
    assert sweep == {"0": [{"spot": "red", "amount": 1_000}]}
    assert mike.balance == 100_000 - 1_500 + 18_000             # 17 straight up: 35 to 1
    assert nora.balance == 100_000 - 2_100 + 4_000 + 3_600      # black 1:1, the late £1 on 17
    assert m.history[0] == 17 and len(m.history) == 12


def test_zero_halves_the_even_chances():
    mike = FakeParticipant("Mike")
    m = table(0)
    m.sit(0, mike, 0)
    m.set_bets(0, {"red": 1_000, "n0": 100, "doz1": 500}, 0)
    m.ready(0, 0)
    events = m.tick(0) + m.tick(0)
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert {s["spot"]: s["action"] for s in settle["steps"]} == {"red": "half", "n0": "pay"}
    sweep = next(e for e in events if e["kind"] == "sweep")["seats"]["0"]
    assert {"spot": "red", "amount": 500} in sweep and {"spot": "doz1", "amount": 500} in sweep
    assert mike.balance == 100_000 - 1_600 + 500 + 3_600


def test_limits_and_minimum():
    m = table()
    m.sit(0, FakeParticipant("P"), 0)
    with pytest.raises(TableError, match="limit is £100"):
        m.set_bets(0, {"n5": 10_100}, 0)
    with pytest.raises(TableError, match="minimum"):
        m.set_bets(0, {"red": 50}, 0)
    m.set_bets(0, {"n5": 10_000, "sp_5_8": 20_000}, 0)   # right at the limits is fine


def test_bet_events_and_snapshots_carry_only_the_spots_in_use():
    m = table(5, spin_open=4.0, ball_track=7.6)
    p = FakeParticipant("P")
    m.sit(0, p, 0)
    ev = m.set_bets(0, {"n5": 100, "sp_5_8": 200}, 0)[0]
    assert ev["bets"] == {"n5": 100, "sp_5_8": 200}
    snap = m.snapshot(0, 0)
    assert snap["seats"][0]["bets"] == {"n5": 100, "sp_5_8": 200} and len(snap["history"]) == 12
    m.ready(0, 0)
    m.tick(0)
    spin = m.snapshot(0, 1.0)["spin"]
    assert spin.keys() == {"elapsed", "track", "ball"} and spin["elapsed"] == 1.0   # no number while bets are open
    m.tick(4.0)
    spin = m.snapshot(0, 5.0)["spin"]
    assert spin["number"] == 5 and spin["landing"] == m.landing and spin["land_in"] > 0


def test_nobody_betting_means_no_spin():
    m = table()
    m.sit(0, FakeParticipant("P"), 0)
    m.set_bets(0, {"n5": 100}, 0)
    m.clear_bets(0, 0)
    m.deadline = 0.0
    assert [e["kind"] for e in m.tick(0)] == ["betting_reset"] and m.phase == "betting"


def test_npcs_bet_by_habit_within_the_limits():
    from casino_server import roster
    from casino_server.npc import ROULETTE_HABITS, Npc, NpcDirector
    d = NpcDirector(casino=None, rng=random.Random(4))
    for habit in ROULETTE_HABITS:
        for arch in roster.ARCHETYPES:
            prof = roster.profile({"archetype": arch, "traits": []}, random.Random(2))
            npc = Npc("n1", 1, "Nora", "npc_1", prof, bankroll=80_000, habit=habit, favourites=(7, 17, 27))
            chips = d._roulette_chips(npc, last=5)
            assert chips and all(spot in rou.BETS and 100 <= amount <= rou.BETS[spot].limit for spot, amount in chips)


def test_npcs_play_roulette_on_the_floor_with_late_bets(tmp_path):
    """NPCs on the whole casino, with a fake clock: some sit at the wheel, bet chip by chip,
    sometimes after the ball's been spun, and nobody's money goes negative."""
    from test_npc import simulate
    from casino_server.tables.runner import TableRunner
    seen = {"spins": 0, "late": 0, "chips": 0}
    original = TableRunner.publish

    def publish(self, events):
        if self.table_id == "rou_1":
            for e in events:
                seen["spins"] += e["kind"] == "no_more_bets" and bool(e["seats"])
                if e["kind"] == "bet_changed":
                    seen["chips"] += 1
                    seen["late"] += self.machine.phase == "spinning"
        original(self, events)

    TableRunner.publish = publish
    try:
        # (roulette their favourite, so some sit at the wheel whatever else the floor has)
        casino, _ = simulate(tmp_path, seconds=5400, population=12, seed=5,
                             punters={"settings": {"favourite_games": ["roulette"]}})
    finally:
        TableRunner.publish = original
    # (chips per spin runs about 1.6-2.7 depending on the seed: more than one is "chip by chip")
    assert seen["spins"] >= 5 and seen["chips"] > seen["spins"] * 1.5 and seen["late"] >= 1, seen
    for npc in casino.npcs.npcs.values():
        assert npc.bankroll >= 0
