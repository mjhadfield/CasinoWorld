"""The slot cabinet (tables/slot_machine.py): money, pacing, each feature's flow, walking away
mid-feature, and NPCs leaving cabinets free for humans."""
import random

import pytest

from casino_server import floor
from casino_server.casino import Casino
from casino_server.slots import base, jackpots
from casino_server.slots.rng import mulberry32
from casino_server.store import Store
from casino_server.tables.base import TableError
from casino_server.tables.slot_machine import SlotMachine, Timings
from tests.test_machine import FakeParticipant


class FakeStore:
    def __init__(self):
        self.data = {}

    def get_json(self, key, default):
        return self.data.get(key, default)

    def set_json(self, key, value):
        self.data[key] = value


def cabinet(seed=1, **over):
    t = Timings.instant()
    t.min_spin = 1.0
    t.trail_auto = 6.0
    t.pick_idle = 15.0
    for k, v in over.items():
        setattr(t, k, v)
    m = SlotMachine("slot_t", 1, t, progressives=jackpots.SlotProgressives(FakeStore()), rng=mulberry32(seed))
    p = FakeParticipant("Ann", balance=1_000_000)
    m.sit(0, p, 0.0)
    return m, p


def run(m, now, until=None, step=0.5):
    """Tick the clock forward, collecting events, until `until(m)` or nothing's left to do."""
    events = []
    for _ in range(4000):
        events += m.tick(now)
        if until and until(m):
            break
        if m.deadline is None or (m.phase == "idle" and not m.pending):
            break
        now = max(now + step, m.deadline)
    return events, now


def test_a_spin_debits_the_bet_and_credits_the_win_at_once():
    m, p = cabinet()
    ev = m.spin(0, 100, now=0.0)
    spin = ev[0]
    assert spin["kind"] == "spin" and spin["outcome"]["bet"] == 100
    assert p.log[0] == (-100, "spin")
    assert p.log[1] == (spin["outcome"]["total"], "spin win")
    assert p in spin["_paid"]
    assert set(spin["meters"]) == {"mini", "minor", "major", "grand"}


def test_only_ladder_bets_and_not_too_fast():
    m, _ = cabinet()
    with pytest.raises(TableError):
        m.spin(0, 123, now=0.0)
    m.spin(0, 25, now=0.0)
    with pytest.raises(TableError):
        m.spin(0, 25, now=0.5)        # still spinning
    m.spin(0, 25, now=1.0)            # after min_spin: a quick stop / skip


def test_cant_spin_without_credit():
    m, p = cabinet()
    p._balance = 10
    with pytest.raises(TableError):
        m.spin(0, 25, now=0.0)


def test_every_bet_feeds_the_meters():
    m, _ = cabinet()
    before = m.progressives.amounts()
    m.spin(0, 2500, now=0.0)
    after = m.progressives.amounts()
    assert after["grand"] - before["grand"] == 25   # 1% of £25


def test_trail_bonus_waits_for_fire_and_pays_at_the_end():
    m, p = cabinet()
    m.rig = {"trigger": "trail"}
    ev = m.spin(0, 100, now=0.0)
    assert ev[0]["features_next"] == ["trail"] and m.phase == "spinning"
    ev, now = run(m, 0.0, until=lambda m: m.phase == "trail")
    assert any(e["kind"] == "trail_start" for e in ev)
    with pytest.raises(TableError):
        m.spin(0, 100, now=now)       # finish the bonus first
    paid_before = sum(a for a, n in p.log if n == "trail bonus")
    shots = 0
    while m.phase == "trail":
        now = max(now, m.trail_ready_at)
        ev = m.trail_fire(0, now=now)
        shots += 1
        assert ev[0]["kind"] == "trail_roll"
    end = next(e for e in ev if e["kind"] == "trail_end")
    assert end["total"] == sum(a for a, n in p.log if n == "trail bonus") - paid_before
    assert shots == end["rolls"]


def test_trail_fires_itself_when_left():
    m, p = cabinet(seed=4)
    m.rig = {"trigger": "trail"}
    m.spin(0, 100, now=0.0)
    ev, now = run(m, 0.0)
    assert any(e["kind"] == "trail_end" for e in ev) and m.phase == "idle"


def test_free_games_play_by_the_clock_and_pay_the_total():
    m, p = cabinet(seed=2)
    m.rig = {"trigger": "free"}
    m.spin(0, 100, now=0.0)
    ev, _ = run(m, 0.0)
    games = [e for e in ev if e["kind"] == "free_game"]
    end = next(e for e in ev if e["kind"] == "free_end")
    assert len(games) == 3 and all(g["outcome"]["features"] for g in games)
    assert end["total"] == sum(g["outcome"]["total"] for g in games)
    assert (end["total"], "free games") in p.log


def test_jackpot_pick_reveals_in_order_and_pays_the_meter():
    m, p = cabinet()
    m.rig = {"jackpot": "major"}
    m.spin(0, 100, now=0.0)
    run(m, 0.0, until=lambda m: m.phase == "jackpot_pick")
    meter = m.progressives.amount("major")
    seq = list(m.pick["seq"])
    ev = []
    for i in range(len(seq)):
        ev += m.jackpot_pick(0, i, now=1.0)
    assert [e["tier"] for e in ev if e["kind"] == "jackpot_reveal"] == seq
    won = next(e for e in ev if e["kind"] == "slot_jackpot_won")
    assert won["tier"] == "major" and won["amount"] == meter
    assert (meter, "major jackpot") in p.log
    assert m.progressives.amount("major") == 50_000    # back to its seed
    with pytest.raises(TableError):
        m.jackpot_pick(0, 11, now=2.0)


def test_snapshot_never_shows_the_pick_sequence():
    m, _ = cabinet()
    m.rig = {"jackpot": "grand"}
    m.spin(0, 100, now=0.0)
    run(m, 0.0, until=lambda m: m.phase == "jackpot_pick")
    m.jackpot_pick(0, 0, now=1.0)
    snap = m.snapshot(0, 1.0)
    assert snap["pick"]["tier"] is None and sum(c is not None for c in snap["pick"]["coins"]) == 1
    assert "seq" not in str(snap)


def test_jackpot_then_bonus_in_that_order():
    m, _ = cabinet()
    m.rig = {"jackpot": "mini", "trigger": "free"}
    ev = m.spin(0, 100, now=0.0)
    assert ev[0]["features_next"] == ["pick", "free"]
    ev, _ = run(m, 0.0)
    kinds = [e["kind"] for e in ev if e["kind"] in ("slot_jackpot_won", "free_start")]
    assert kinds == ["slot_jackpot_won", "free_start"]


def test_standing_mid_feature_plays_it_out_and_pays():
    m, p = cabinet(seed=5)
    m.rig = {"jackpot": "minor", "trigger": "trail"}
    m.spin(0, 100, now=0.0)
    run(m, 0.0, until=lambda m: m.phase == "jackpot_pick")
    ev = m.stand(0, now=3.0, reason="")
    kinds = [e["kind"] for e in ev]
    assert "slot_jackpot_won" in kinds and "trail_end" in kinds and kinds[-1] == "stood"
    assert all(e.get("finished_for_you") for e in ev if e["kind"] != "stood")
    notes = [n for _, n in p.log]
    assert "minor jackpot" in notes and "trail bonus" in notes
    # ...and the next player finds a fresh cabinet
    assert m.phase == "idle" and m.last is None and not m.pending and m.trail is None
    q = FakeParticipant("Bea")
    m.sit(0, q, 10.0)
    assert m.snapshot(0, 10.0)["last"] is None


def test_buy_bonus_costs_45_bets_and_goes_to_the_trail():
    m, p = cabinet()
    ev = m.buy_bonus(0, 100, now=0.0)
    assert ev[0]["kind"] == "bonus_bought" and ev[0]["cost"] == 4500
    assert p.log[0] == (-4500, "buy bonus") and m.phase == "trail"


def test_buy_bonus_plays_one_of_its_bonuses_at_random():
    import dataclasses
    seen = set()
    for seed in range(1, 30):
        m, _ = cabinet(seed)
        m.variant = dataclasses.replace(m.variant, routes={"BS": ["trail"], "FS": ["free"], "buy": ["trail", "free"]})
        ev = m.buy_bonus(0, 100, now=0.0)
        seen.add(ev[-1]["kind"])
        if ev[-1]["kind"] == "free_start":
            assert ev[-1]["bought"] and m.phase == "free_games"
    assert seen == {"trail_start", "free_start"}


def test_no_buyable_bonus_means_no_buy_bonus():
    import dataclasses
    m, _ = cabinet()
    m.variant = dataclasses.replace(m.variant, routes={"BS": ["trail"], "FS": ["free"], "buy": []})
    with pytest.raises(TableError):
        m.buy_bonus(0, 100, now=0.0)


def test_an_idle_human_is_stood_up_after_five_minutes():
    m, p = cabinet(idle_stand=300.0)
    m.spin(0, 25, now=0.0)
    assert m.deadline == 300.0
    ev = m.tick(300.0)
    assert ev[-1]["kind"] == "stood" and ev[-1]["reason"] == "idle"


def test_rules_carry_the_whole_catalogue():
    m, _ = cabinet()
    r = m.rules()
    assert r["lines"] == base.LINES and r["ladder"] == base.LADDER and len(r["strips"]) == 5
    assert r["buy_cost"] == 45 and [t["id"] for t in r["tiers"]] == jackpots.TIER_IDS


def test_meters_persist_through_the_store(tmp_path):
    store = Store(tmp_path / "c.sqlite")
    pg = jackpots.SlotProgressives(store)
    pg.contribute(100_000)
    pg.save()
    again = jackpots.SlotProgressives(store)
    assert again.amounts() == pg.amounts() and again.amount("grand") == 501_000


def test_npcs_leave_two_cabinets_free_and_never_pass_the_bank(tmp_path):
    """Over a few floors (NPC choices are random, so one seed can just never fancy slots):
    never more than the bank less the two kept for humans, and NPCs do play them."""
    busiest = 0
    for seed in (5, 6, 7, 8):
        t = [0.0]
        casino = Casino(Store(tmp_path / f"c{seed}.sqlite"), npc_population=20, rng=random.Random(seed),
                        clock=lambda: t[0], wall=lambda: t[0])
        casino.dealers.start(0.0)
        cabinets = [r for tid, r in casino.tables.items() if tid in floor.SLOTS]
        for _ in range(int(1200 / 0.25)):
            t[0] += 0.25
            casino.npcs.tick(t[0])
            for r in casino.tables.values():
                r.publish(r.machine.tick(t[0]))
            seated = sum(r.machine.seats[0].participant is not None for r in cabinets)
            assert seated <= len(cabinets) - floor.SLOTS_FOR_HUMANS
            busiest = max(busiest, seated)
    assert busiest > 0

def test_meters_grow_by_the_second_and_by_their_share_of_each_bet(tmp_path):
    t = [0.0]
    store = Store(tmp_path / "c.sqlite")
    pg = jackpots.SlotProgressives(store, clock=lambda: t[0])
    pg.configure(jackpots.clean_settings({"mini": {"rate": 0.01, "per_second": 10}}))
    t[0] = 30.0
    assert pg.amount("mini") == 1_000 + 300
    pg.contribute(1_000)
    assert pg.amount("mini") == 1_000 + 300 + 10
    assert pg.snapshot()["rates"]["mini"] == 10
    again = jackpots.SlotProgressives(store, clock=lambda: t[0])   # the settings are kept
    assert again.settings["mini"] == {"rate": 0.01, "per_second": 10.0}
    assert again.rtp() == pytest.approx(jackpots.rtp() + 0.0075)
