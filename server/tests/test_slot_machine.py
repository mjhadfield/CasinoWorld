"""The slot cabinet (tables/slot_machine.py): money, pacing, each feature's flow, walking away
mid-feature, and NPCs leaving cabinets free for humans."""
import random

import pytest

from casino_server import floor
from casino_server.casino import Casino
from casino_server.slots import base, jackpots
from casino_server.slots.bonuses import expedition_options, voyage_options
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


def battle_cabinet(seed=1):
    import dataclasses
    m, p = cabinet(seed, battle_auto=8.0)
    m.variant = dataclasses.replace(m.variant, routes={"BS": ["battle"], "FS": ["free"], "buy": ["battle"]})
    return m, p


def test_battle_waits_for_a_ship_and_pays_at_the_end():
    m, p = battle_cabinet()
    m.rig = {"trigger": "battle"}
    assert m.spin(0, 100, now=0.0)[0]["features_next"] == ["battle"]
    ev, now = run(m, 0.0, until=lambda m: m.phase == "battle")
    start = next(e for e in ev if e["kind"] == "battle_start")
    assert start["battle"]["ships"] == [True] * 4 and start["battle"]["shields"] == 3
    with pytest.raises(TableError):
        m.battle_fire(0, 9, now=now)                  # no ship there
    shots = 0
    while m.phase == "battle":
        now = max(now, m.battle_ready_at)
        st = m.battle
        target = None if st["boss_hp"] is not None else max(i for i, there in enumerate(st["ships"]) if there)
        ev = m.battle_fire(0, target, now=now)
        shots += 1
        assert ev[0]["kind"] == "battle_shot" and ev[0]["shot"]["target"] == (target if target is not None else "boss")
        if not ev[0]["shot"]["done"]:
            with pytest.raises(TableError):
                m.battle_fire(0, None, now=now)       # wait for the last shot
    end = next(e for e in ev if e["kind"] == "battle_end")
    assert (end["total"], "battle bonus") in p.log and end["shots"] == shots


def test_battle_fires_itself_and_its_free_spins_follow():
    for seed in range(1, 200):
        m, p = battle_cabinet(seed)
        m.rig = {"trigger": "battle"}
        m.spin(0, 100, now=0.0)
        ev, _ = run(m, 0.0)
        end = next(e for e in ev if e["kind"] == "battle_end")
        assert m.phase == "idle"
        if end["spins"]:
            start = next(e for e in ev if e["kind"] == "free_start")
            assert start["of"] == end["spins"] and start["source"] == "battle"
            assert len([e for e in ev if e["kind"] == "free_game"]) == end["spins"]
            assert [e["kind"] for e in ev].index("free_start") > [e["kind"] for e in ev].index("battle_end")
            return
        assert not any(e["kind"] == "free_start" for e in ev)
    pytest.fail("no battle gave free spins")


def test_standing_mid_battle_plays_it_out_and_pays():
    m, p = battle_cabinet(seed=3)
    m.buy_bonus(0, 100, now=0.0)
    assert m.phase == "battle"
    ev = m.stand(0, now=3.0, reason="")
    end = next(e for e in ev if e["kind"] == "battle_end")
    assert end["finished_for_you"] and (end["total"], "battle bonus") in p.log
    assert m.phase == "idle" and m.battle is None and not m.pending


def voyage_cabinet(seed=1):
    import dataclasses
    m, p = cabinet(seed, voyage_auto=12.0, present=1.0)
    m.variant = dataclasses.replace(m.variant, routes={"BS": ["voyage"], "FS": ["free"], "buy": ["voyage"]})
    return m, p


def test_voyage_waits_for_a_choice_and_pays_at_the_end():
    m, p = voyage_cabinet()
    m.rig = {"trigger": "voyage"}
    assert m.spin(0, 100, now=0.0)[0]["features_next"] == ["voyage"]
    ev, now = run(m, 0.0, until=lambda m: m.phase == "voyage")
    start = next(e for e in ev if e["kind"] == "voyage_start")["voyage"]
    assert len(start["map"]) == 6 and start["leg"] == -1 and start["options"] == [r for r in range(3) if start["map"][0][r] != "cove"]
    with pytest.raises(TableError):
        m.voyage_choose(0, 5, now=now)               # not an island
    steps = 0
    while m.phase == "voyage":
        now = max(now, m.voyage_ready_at)
        opts = voyage_options(m.variant, m.voyage)
        ev = m.voyage_choose(0, opts[-1], now=now)    # the bottom island, the last deal ("leave"), the final island
        steps += 1
        assert ev[0]["kind"] == "voyage_step" and ev[0]["step"]["choice"] == opts[-1] and not ev[0]["auto"]
        if not ev[0]["step"]["done"]:
            with pytest.raises(TableError):
                m.voyage_choose(0, opts[-1], now=now)  # wait for the ship
    end = next(e for e in ev if e["kind"] == "voyage_end")
    assert (end["total"], "voyage bonus") in p.log and end["steps"] == steps
    assert end["sunk"] or end["treasure"]["pence"] >= 1200


def test_voyage_chooses_itself():
    m, p = voyage_cabinet(seed=5)
    m.rig = {"trigger": "voyage"}
    m.spin(0, 100, now=0.0)
    ev, _ = run(m, 0.0)
    end = next(e for e in ev if e["kind"] == "voyage_end")
    assert m.phase == "idle" and all(e["auto"] for e in ev if e["kind"] == "voyage_step")
    assert (end["total"], "voyage bonus") in p.log


def test_free_games_bought_on_a_voyage_follow_it():
    for seed in range(1, 400):
        m, p = voyage_cabinet(seed)
        m.buy_bonus(0, 100, now=0.0)
        now, ev = 0.0, []
        while m.phase == "voyage":
            now = max(now, m.voyage_ready_at)
            opts = voyage_options(m.variant, m.voyage)
            ev += m.voyage_choose(0, "spins" if "spins" in opts else opts[0], now=now)
        end = next(e for e in ev if e["kind"] == "voyage_end")
        if end["spins"]:
            ev, _ = run(m, now)
            start = next(e for e in ev if e["kind"] == "free_start")
            assert start["of"] == end["spins"] and start["source"] == "voyage"
            assert len([e for e in ev if e["kind"] == "free_game"]) == end["spins"]
            return
    pytest.fail("no voyage bought free games")


def test_standing_mid_voyage_plays_it_out_and_pays():
    m, p = voyage_cabinet(seed=3)
    m.buy_bonus(0, 100, now=0.0)
    assert m.phase == "voyage"
    ev = m.stand(0, now=3.0, reason="")
    end = next(e for e in ev if e["kind"] == "voyage_end")
    assert end["finished_for_you"] and (end["total"], "voyage bonus") in p.log
    assert m.phase == "idle" and m.voyage is None and not m.pending


def expedition_cabinet(seed=1):
    import dataclasses
    m, p = cabinet(seed, expedition_auto=12.0, present=1.0)
    m.variant = dataclasses.replace(m.variant, routes={"BS": ["expedition"], "FS": ["free"], "buy": ["expedition"]})
    return m, p


def test_expedition_waits_for_a_choice_and_pays_at_the_end():
    m, p = expedition_cabinet()
    m.rig = {"trigger": "expedition"}
    assert m.spin(0, 100, now=0.0)[0]["features_next"] == ["expedition"]
    ev, now = run(m, 0.0, until=lambda m: m.phase == "expedition")
    start = next(e for e in ev if e["kind"] == "expedition_start")["expedition"]
    assert len(start["routes"]) == 3 and start["awaiting"] == "route" and start["options"] == [0, 1, 2]
    with pytest.raises(TableError):
        m.expedition_choose(0, 5, now=now)           # not a route
    steps = 0
    while m.phase == "expedition":
        now = max(now, m.expedition_ready_at)
        opts = expedition_options(m.variant, m.expedition)
        ev = m.expedition_choose(0, opts[-1], now=now)
        steps += 1
        step = ev[0]
        assert step["kind"] == "expedition_step" and step["step"]["choice"] == opts[-1] and not step["auto"]
        hidden = [q for q in step["expedition"]["planets"] or [] if not q["seen"]]
        assert all(q == {"kind": None, "seen": False, "by": None} for q in hidden)
        if not step["step"]["done"]:
            with pytest.raises(TableError):
                m.expedition_choose(0, opts[-1], now=now)   # wait for the ship
    end = next(e for e in ev if e["kind"] == "expedition_end")
    assert (end["total"], "expedition bonus") in p.log and end["steps"] == steps
    assert end["ended"] or end["final"] >= 2000


def test_expedition_chooses_itself():
    m, p = expedition_cabinet(seed=5)
    m.rig = {"trigger": "expedition"}
    m.spin(0, 100, now=0.0)
    ev, _ = run(m, 0.0)
    end = next(e for e in ev if e["kind"] == "expedition_end")
    assert m.phase == "idle" and all(e["auto"] for e in ev if e["kind"] == "expedition_step")
    assert (end["total"], "expedition bonus") in p.log


def test_free_games_found_on_an_expedition_follow_it():
    for seed in range(1, 600):
        m, p = expedition_cabinet(seed)
        m.buy_bonus(0, 100, now=0.0)
        ev, now = run(m, 0.0, until=lambda m: m.phase != "expedition")
        end = next(e for e in ev if e["kind"] == "expedition_end")
        if end["spins"]:
            ev, _ = run(m, now)
            start = next(e for e in ev if e["kind"] == "free_start")
            assert start["of"] == end["spins"] and start["source"] == "expedition"
            assert len([e for e in ev if e["kind"] == "free_game"]) == end["spins"]
            return
    pytest.fail("no expedition found free games")


def test_standing_mid_expedition_plays_it_out_and_pays():
    m, p = expedition_cabinet(seed=3)
    m.buy_bonus(0, 100, now=0.0)
    assert m.phase == "expedition"
    ev = m.stand(0, now=3.0, reason="")
    end = next(e for e in ev if e["kind"] == "expedition_end")
    assert end["finished_for_you"] and (end["total"], "expedition bonus") in p.log
    assert m.phase == "idle" and m.expedition is None and not m.pending


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
        cabinets = [r for r in casino.tables.values() if r.machine.game == "slots"]
        assert len(cabinets) == 10
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


def test_stats_count_spins_stakes_wins_bonuses_and_jackpots():
    m, p = cabinet()
    m.rig = {"trigger": "trail"}
    m.spin(0, 100, now=0.0)
    _, now = run(m, 0.0, until=lambda m: m.phase == "trail")
    while m.phase == "trail":
        now = max(now, m.trail_ready_at)
        m.trail_fire(0, now=now)
    run(m, now)
    m.rig = {"jackpot": "mini"}
    m.spin(0, 100, now=now + 5)
    run(m, now + 5, until=lambda m: m.phase == "jackpot_pick")
    for i in range(len(m.pick["seq"])):
        m.jackpot_pick(0, i, now=now + 6)
    [row] = m.stats.rows()
    assert row["variant"] == "armadillo" and row["who"] == "human"
    assert row["spins"] == 2 and row["staked"] == 200 and row["bonuses"] == 1 and row["jackpots"] == 1
    assert row["returned"] == sum(a for a, n in p.log if a > 0)


def test_stats_count_a_bought_bonus_as_staked_and_npcs_apart():
    m, _ = cabinet()
    m.stand(0, 0.0)
    npc = FakeParticipant("Bot", balance=1_000_000, human=False)
    m.sit(0, npc, 0.0)
    m.buy_bonus(0, 100, now=1.0)
    [row] = m.stats.rows()
    assert row["who"] == "npc" and row["spins"] == 0 and row["bonuses"] == 1
    assert row["staked"] == 100 * m.variant.buy_cost


def test_stats_save_into_the_store_and_add_up(tmp_path):
    from casino_server.slots.stats import SlotStats
    store = Store(tmp_path / "s.sqlite")
    clock = [0.0]
    stats = SlotStats(store, clock=lambda: clock[0])
    stats.record("armadillo", True, spins=1, staked=100, returned=40)
    assert store.slot_stats() == []                  # not yet: saved every few seconds
    clock[0] = 10.0
    stats.record("armadillo", True, spins=1, staked=100, returned=0)
    stats.record("armadillo", False, spins=1, staked=25, returned=50)
    stats.save()
    rows = {r["who"]: r for r in SlotStats(store).rows()}
    assert rows["human"]["spins"] == 2 and rows["human"]["staked"] == 200 and rows["human"]["returned"] == 40
    assert rows["npc"]["returned"] == 50
    assert stats.since() is not None
