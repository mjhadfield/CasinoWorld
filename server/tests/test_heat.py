"""Card counting at Blackjack: the count anyone watching would keep, a counter's plays, and the pit backing off
whoever spreads their bets with it (heat.py)."""
import logging
import math
import random
from types import SimpleNamespace

import pytest

from casino_server.engines import blackjack as bj
from casino_server.engines.cards import Card
from casino_server.heat import WARNING_MIN, HeatWatch, clean_settings
from casino_server.tables.base import TableError

from test_blackjack_machine import deal, kinds, machine, timings
from test_machine import FakeParticipant
from test_master_table import change, table


def player(name="Mike", pid=1):
    p = FakeParticipant(name)
    p.player_id = pid
    return p


class Clock:
    def __init__(self):
        self.t = 1_000.0

    def __call__(self):
        return self.t


# ------------------------------------------------------------------ the count
def test_the_count_leaves_the_hole_card_out_until_its_turned_over():
    p = FakeParticipant("Mike")
    m = machine(["10h", "6c", "9d", "Ks", "2d"])   # Mike 10+9, dealer 6 up and a King in the hole, then a 2
    events = deal(m, p)
    dealt = next(e for e in events if e["kind"] == "dealt")
    assert dealt["count"]["running"] == 0          # 10 (-1), 6 (+1), 9 (0): the King's not seen yet
    assert m.snapshot(None, 0)["count"]["running"] == 0
    events = m.play_action(0, "stand", 1) + m.tick(1)
    reveal = next(e for e in events if e["kind"] == "dealer_reveal")
    assert reveal["count"]["running"] == -1        # the King now
    draw = next(e for e in events if e["kind"] == "dealer_draw")
    assert draw["count"]["running"] == 0           # and the 2


def test_the_true_count_is_over_the_decks_still_to_come():
    m = machine([])
    m.shoe.running = 10
    c = m.count()
    assert c["decks"] == round(m.shoe.remaining / 52, 1)
    assert c["true"] == round(10 / (m.shoe.remaining / 52), 1)


def test_a_shuffle_starts_the_count_again():
    m = machine(["2h"] * 10)
    for _ in range(5):
        m.shoe.draw()
    assert m.shoe.running == 5
    m.shoe.shuffle()
    assert m.shoe.running == 0 and m.count()["running"] == 0


# ------------------------------------------------------------------ a counter's plays
def cards(*codes):
    return [Card.from_code(c) for c in codes]


@pytest.mark.parametrize("hand,up,tc,play", [
    (("10h", "6c"), "Kd", 0, "stand"), (("10h", "6c"), "Kd", -1, None),
    (("10h", "2c"), "3d", 2, "stand"), (("10h", "2c"), "3d", 1.9, None),
    (("10h", "3c"), "2d", -1.5, "hit"), (("10h", "3c"), "2d", -1, None),
    (("6h", "4c"), "Ad", 4, "double"), (("5h", "4c"), "2d", 1, "double"),
    (("Kh", "Qc"), "6d", 4, "split"), (("Kh", "Qc"), "6d", 3, None),
    (("8h", "8c"), "Kd", 5, None),                 # a pair the chart splits stays split
    (("Ah", "5c"), "Kd", 5, None),                 # soft hands play the chart
])
def test_a_counter_changes_a_few_plays_with_the_count(hand, up, tc, play):
    assert bj.deviation(cards(*hand), Card.from_code(up), tc, True, True) == play


def test_a_double_it_cant_make_is_the_charts_hit():
    assert bj.deviation(cards("6h", "4c"), Card.from_code("Ad"), 5, False, True) is None


# ------------------------------------------------------------------ heat
def spread(watch, p, rounds, bet, tc):
    out = []
    for _ in range(rounds):
        out += watch.observe([(p, bet)], tc)
    return out


def keep_spreading(watch, p, pairs=6):
    """Warned, they carry on: £5 on a bad count, £40 on a good one."""
    out = []
    for _ in range(pairs):
        out += watch.observe([(p, 500)], 0) + watch.observe([(p, 4_000)], 3)
    return out


def test_spreading_with_the_count_gets_a_warning_then_a_back_off():
    clock = Clock()
    watch, p = HeatWatch(clock=clock), player()
    assert spread(watch, p, 3, 500, 0) == []                  # the base: £5
    assert spread(watch, p, 5, 4_000, 3) == []                # 8x on +3: +1.5 a round
    reached = spread(watch, p, 1, 4_000, 3)
    assert reached == [(p, "warned", 0)] and watch.warned(p) and not watch.barred(p)
    reached = keep_spreading(watch, p)
    assert reached == [(p, "backed_off", 60)] and watch.barred(p)
    assert "60 min" in watch.refusal(p)
    clock.t += 61 * 60
    assert not watch.barred(p) and watch.refusal(p) is None


def test_raising_on_a_good_count_for_a_few_hands_is_at_most_a_warning():
    watch, p = HeatWatch(clock=Clock()), player()
    spread(watch, p, 5, 500, 0)
    assert spread(watch, p, 5, 2_000, 2.5) == []              # 4x on +2.5 for five hands: not even a warning yet
    assert [r[1] for r in spread(watch, p, 10, 2_000, 2.5)] == ["warned"]   # ...and never more, kept level


def test_a_level_bet_after_the_warning_cools_at_any_size_and_stays_cool():
    watch, p = HeatWatch(clock=Clock()), player()
    spread(watch, p, 3, 500, 0)
    assert spread(watch, p, 6, 4_000, 3)[-1][1] == "warned"
    rng = random.Random(5)
    reached = []
    for _ in range(40):                                       # the raised bet, kept level whatever the count
        reached += watch.observe([(p, 4_000)], rng.uniform(-3, 5))
    assert reached == [] and not watch.warned(p) and watch.status(p)["heat"] == 0
    assert spread(watch, p, 10, 4_000, 4) == []               # (the £5 bets before the warning are forgotten)


def test_no_back_off_on_the_round_straight_after_a_warning():
    watch, p = HeatWatch(clock=Clock()), player()
    rec = watch._record(("player", 1), 1_000.0, make=True)
    rec.heat, rec.warned, rec.warned_at = 30.0, True, 1_000.0  # (red hot, and only just warned)
    assert watch.observe([(p, 500)], 0) == []
    assert watch.observe([(p, 500)], 0) == [(p, "backed_off", 60)]


def test_a_warning_runs_out_so_the_next_hot_run_only_warns_again():
    clock = Clock()
    watch, p = HeatWatch(clock=clock), player()
    spread(watch, p, 3, 500, 0)
    spread(watch, p, 6, 4_000, 3)
    assert watch.warned(p)
    clock.t += (WARNING_MIN + 1) * 60
    assert not watch.warned(p)
    spread(watch, p, 3, 500, 0)
    assert [r[1] for r in spread(watch, p, 8, 4_000, 3)] == ["warned"]


def test_warnings_and_back_offs_are_logged(caplog):
    watch, p = HeatWatch(clock=Clock()), player()
    with caplog.at_level(logging.INFO, logger="casino.heat"):
        spread(watch, p, 3, 500, 0)
        spread(watch, p, 6, 4_000, 3)
        keep_spreading(watch, p)
    lines = [r.getMessage() for r in caplog.records if r.name == "casino.heat"]
    assert len(lines) == 2
    assert lines[0].startswith("player 1 (Mike): warned") and "bet £40 on a base of £5 at TC +3.0" in lines[0]
    assert lines[1].startswith("player 1 (Mike): backed off for 60 min")


def test_flat_betting_and_chasing_losses_stay_cool():
    watch, p, q = HeatWatch(clock=Clock()), player(pid=1), player("Chas", pid=2)
    rng = random.Random(3)
    for _ in range(200):
        tc = rng.uniform(-4, 4)
        watch.observe([(p, 1_000)], tc)
        watch.observe([(q, rng.choice([500, 1_000, 2_000, 4_000]))], tc)   # big bets whatever the count
    assert not watch.warned(p) and not watch.barred(p)
    assert not watch.barred(q)


def test_heat_cools_with_time_and_an_npcs_back_off_lasts_their_visit():
    clock = Clock()
    watch = HeatWatch(clock=clock)
    npc = SimpleNamespace(npc=SimpleNamespace(npc_id=7), entity_id="n7", name="Ned", is_human=False)
    spread(watch, npc, 1, 500, 0)
    spread(watch, npc, 2, 4_000, 3)
    clock.t += 3 * 600                                        # half, three times over
    watch._record(("npc", 7), clock.t)
    assert watch._records[("npc", 7)].heat == pytest.approx(3 * 0.125)
    reached = spread(watch, npc, 6, 4_000, 3) + keep_spreading(watch, npc)
    assert [r[1] for r in reached] == ["warned", "backed_off"] and reached[1][2] == 0
    assert watch._records[("npc", 7)].barred_until == math.inf and "today" in watch.refusal(npc)
    watch.forget(npc)
    assert not watch.barred(npc)


def test_a_second_box_counts_as_its_owners():
    watch, p = HeatWatch(clock=Clock()), player()
    box = SimpleNamespace(owner=p)
    watch.observe([(p, 500), (box, 500)], 0)                  # base: £10 across both
    reached = []
    for _ in range(6):
        reached += watch.observe([(p, 2_000), (box, 2_000)], 3)
    assert reached and reached[0][0] is p


def test_switched_off_nobody_is_watched():
    store = SimpleNamespace(get_json=lambda key, default: {"on": False})
    watch, p = HeatWatch(store, clock=Clock()), player()
    assert spread(watch, p, 20, 50_000, 5) == []


def test_settings_are_checked():
    assert clean_settings({"warn_at": 4, "back_off_at": 8, "bar_min": 30, "on": True}) == \
        {"warn_at": 4, "back_off_at": 8, "bar_min": 30, "on": True}
    for bad in ({"warn_at": 0}, {"bar_min": 1.5}, {"on": "yes"}, {"warn_at": 8, "back_off_at": 8}):
        with pytest.raises(ValueError):
            clean_settings(bad)


# ------------------------------------------------------------------ at the table
def play_round(m, p, bet, now):
    m.set_bets(0, {"bet": bet}, now)
    events = m.ready(0, now) + m.tick(now)
    while m.phase != "betting":
        if m.phase == "playing" and m.turn is not None:
            events += m.play_action(0, "stand", now)
        now += 1
        events += m.tick(now)
    return events, now


def test_the_table_warns_then_stands_a_backed_off_player_and_wont_seat_them():
    clock = Clock()
    m = machine(["10h", "6c", "9d", "Ks"] * 100, timings=timings(insurance=0.0))
    m.heat = HeatWatch(clock=clock)
    p = player()
    m.sit(0, p, 0)
    events, now = play_round(m, p, 500, 0)
    m.count = lambda: {"running": 20, "true": 4.0, "decks": 5.0}   # a hot shoe from here on
    seen = []
    for bet in [4_000] * 6 + [500, 4_000] * 6:                      # warned on the sixth, then carrying on spreading
        if m.seat_of(p) is None:
            break
        events, now = play_round(m, p, bet, now)
        seen += [e for e in events if e["kind"] in ("heat", "stood")]
    assert [e.get("stage", e["kind"]) for e in seen] == ["warned", "backed_off", "stood"]
    assert seen[1]["minutes"] == 60 and seen[2]["reason"] == "backed_off"
    with pytest.raises(TableError, match="pit boss"):
        m.sit(0, p, now)


def test_a_warning_turns_auto_rebet_off():
    m = machine(["10h", "6c", "9d", "Ks"] * 100, timings=timings(insurance=0.0))
    m.heat = HeatWatch(clock=Clock())
    p = player()
    m.sit(0, p, 0)
    m.seats[0].auto_rebet = True
    rec = m.heat._record(("player", 1), 1_000.0, make=True)
    rec.heat, rec.bets = 7.5, type(rec.bets)([500], maxlen=rec.bets.maxlen)
    m._watched, m._watched_count = [(p, 4_000)], 3.0
    events = m._pit_check(0)
    assert [e["kind"] for e in events if e["kind"] in ("heat", "auto_rebet")] == ["heat", "auto_rebet"]
    assert not m.seats[0].auto_rebet


def test_a_master_table_wont_deal_blackjack_to_the_backed_off():
    clock = Clock()
    watch = HeatWatch(clock=clock)
    m = table()
    m.heat = watch
    barred, other = player("Bea", pid=1), player("Al", pid=2)
    watch._record(("player", 1), clock.t, make=True).barred_until = clock.t + 600
    m.sit(0, barred, 0)
    with pytest.raises(TableError, match="pit boss"):
        m.choose_game(0, "blackjack", 0)
    m.sit(1, other, 0)
    events = m.choose_game(1, "blackjack", 0)
    events += m.game_vote(0, True, 0)
    assert any(e["kind"] == "stood" and e.get("reason") == "backed_off" for e in events)
    change(m, 0)
    assert m.seat_of(barred) is None and m.seat_of(other) is not None


def test_the_admin_page_reads_and_saves_the_settings(client):
    assert client.get("/api/heat-settings").json() == {"on": True, "warn_at": 8, "back_off_at": 14, "bar_min": 60}
    assert client.put("/api/heat-settings", json={"bar_min": 30, "on": False}).json()["bar_min"] == 30
    assert client.put("/api/heat-settings", json={"warn_at": 20}).status_code == 400   # (over Back off at)
    assert client.get("/api/heat-settings").json() == {"on": False, "warn_at": 8, "back_off_at": 14, "bar_min": 30}
