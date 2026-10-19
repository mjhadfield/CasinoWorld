"""Craps: the bet catalogue and its arithmetic, the dice's choreography, the table's
roll flow (bets that stay up, the shooter, taking the dice), and the NPCs' place at it."""
import random
from fractions import Fraction
from itertools import product

import pytest

from casino_server.casino import Casino
from casino_server.engines import craps as cr
from casino_server.store import Store
from casino_server.tables.base import TableError
from casino_server.tables.craps import INACTIVE_ROLLS, CrapsMachine, Timings

from test_machine import FakeParticipant

ROLLS = list(product(range(1, 7), repeat=2))
STAKE = 3000   # divides cleanly by every payout's denominator


# ---------------------------------------------------------------- the engine
def test_the_catalogue():
    assert len(cr.SPOTS) == len(set(cr.SPOTS)) == 63
    assert cr.number_of("place_6") == 6 and cr.number_of("come_odds_10") == 10 and cr.number_of("hard8") == 8
    assert cr.number_of("big6") == 6 and cr.number_of("pass") is None and cr.number_of("dcome_4") == 4
    assert cr.is_travelled("come_5") and cr.is_travelled("dcome_9") and not cr.is_travelled("come_odds_5")


def _ev(spot: str, point, working=True, stake=STAKE, push_counts=False) -> Fraction:
    """The bet's expected return per decision, rolling until something happens to it."""
    total = decided = Fraction(0)
    for d1, d2 in ROLLS:
        o = cr.resolve({spot: stake}, d1, d2, point, working).get(spot)
        if o is None:
            if push_counts and spot in ("dont_pass", "dont_come") and d1 + d2 == 12:
                decided += Fraction(1, 36)   # a bar-12 push is a decision worth nothing
            continue
        decided += Fraction(1, 36)
        total += Fraction(1, 36) * (o.win if o.kind == "win" else -stake if o.kind == "lose" else 0)
    return total / decided / stake


def _line_ev(spot: str) -> Fraction:
    """A Pass or Don't Pass bet from the come-out to its decision (pushes count as bets)."""
    ev = Fraction(0)
    for d1, d2 in ROLLS:
        t = d1 + d2
        o = cr.resolve({spot: STAKE}, d1, d2, None).get(spot)
        if o is None and t in cr.NUMBERS:
            ev += Fraction(1, 36) * _ev(spot, t)
        elif o is not None:
            ev += Fraction(1, 36) * Fraction(o.win if o.kind == "win" else -STAKE, STAKE)
    return ev


def test_line_bets_have_the_published_edges():
    assert _line_ev("pass") == Fraction(-7, 495)          # 1.41%
    assert _line_ev("dont_pass") == Fraction(-3, 220)     # 1.36%


EDGES = {
    "place_4": Fraction(1, 15), "place_10": Fraction(1, 15), "place_5": Fraction(1, 25), "place_9": Fraction(1, 25),
    "place_6": Fraction(1, 66), "place_8": Fraction(1, 66),
    "buy_4": Fraction(1, 60), "buy_10": Fraction(1, 60), "buy_5": Fraction(1, 50), "buy_9": Fraction(1, 50),
    "buy_6": Fraction(1, 44), "buy_8": Fraction(1, 44),
    "lay_4": Fraction(1, 60), "lay_10": Fraction(1, 60), "lay_5": Fraction(1, 50), "lay_9": Fraction(1, 50),
    "lay_6": Fraction(1, 44), "lay_8": Fraction(1, 44),
    "field": Fraction(1, 36), "big6": Fraction(1, 11), "big8": Fraction(1, 11),
    "hard4": Fraction(1, 9), "hard10": Fraction(1, 9), "hard6": Fraction(1, 11), "hard8": Fraction(1, 11),
    "any7": Fraction(1, 6), "any_craps": Fraction(1, 9), "two": Fraction(5, 36), "twelve": Fraction(5, 36),
    "three": Fraction(1, 9), "eleven": Fraction(1, 9), "horn": Fraction(1, 8), "ce": Fraction(1, 9),
}


@pytest.mark.parametrize("spot", sorted(EDGES))
def test_every_bet_has_its_published_edge(spot):
    assert _ev(spot, point=4 if cr.number_of(spot) != 4 else 5) == -EDGES[spot]


@pytest.mark.parametrize("n", cr.NUMBERS)
def test_odds_are_free(n):
    assert _ev("pass_odds", n) == 0 and _ev("dont_odds", n) == 0
    assert _ev(f"come_odds_{n}", 4 if n != 4 else 5) == 0 and _ev(f"dcome_odds_{n}", 4) == 0


def test_how_a_roll_decides_things():
    r = cr.resolve({"come": 500, "dont_come": 500, "field": 500}, 5, 3, 6)
    assert r["come"] == cr.Outcome("move", to="come_8") and r["dont_come"] == cr.Outcome("move", to="dcome_8")
    assert r["field"].kind == "lose"
    assert "dont_pass" not in cr.resolve({"dont_pass": 500}, 6, 6, None)    # bar 12: a push
    assert "dont_come" not in cr.resolve({"dont_come": 500}, 6, 6, 4)    # bar 12: a push
    # A come bet on 8 wins and comes back with its odds; its odds are off on the come-out.
    r = cr.resolve({"come_8": 1000, "come_odds_8": 2000}, 4, 4, 5)
    assert r["come_8"] == cr.Outcome("win", 1000, False) and r["come_odds_8"] == cr.Outcome("win", 2400, False)
    r = cr.resolve({"come_8": 1000, "come_odds_8": 2000}, 4, 4, None)
    assert r["come_8"].kind == "win" and r["come_odds_8"].kind == "return"
    r = cr.resolve({"come_8": 1000, "come_odds_8": 2000}, 3, 4, None)
    assert r["come_8"].kind == "lose" and r["come_odds_8"].kind == "return"
    assert cr.resolve({"come_odds_8": 2000}, 4, 4, None, working=True)["come_odds_8"].kind == "win"
    # Place bets and hardways are off coming out, unless working; lay bets aren't.
    assert cr.resolve({"place_6": 600, "hard6": 100, "lay_4": 1000}, 3, 3, None) == {}
    r = cr.resolve({"place_6": 600, "hard6": 100, "lay_4": 1000}, 3, 4, None)
    assert list(r) == ["lay_4"] and r["lay_4"].win == 475
    r = cr.resolve({"place_6": 600, "hard6": 100}, 3, 3, None, working=True)
    assert r["place_6"].win == 700 and r["hard6"].win == 900
    assert cr.resolve({"hard6": 100}, 2, 4, 8)["hard6"].kind == "lose"       # easy six
    # Props and the money in them.
    assert cr.resolve({"horn": 400}, 1, 1, 4)["horn"].win == 2700
    assert cr.resolve({"horn": 400}, 5, 6, 4)["horn"].win == 1200
    assert cr.resolve({"ce": 200}, 1, 2, None)["ce"].win == 600 and cr.resolve({"ce": 200}, 5, 6, 9)["ce"].win == 1400
    assert cr.resolve({"buy_4": 2000}, 2, 2, 6)["buy_4"].win == 3900            # 2 to 1 less £1
    assert cr.resolve({"field": 500}, 6, 6, 9)["field"].win == 1500


def test_the_point():
    assert cr.advance_point(None, 8) == (8, "point_set")
    assert cr.advance_point(None, 7) == (None, "natural") and cr.advance_point(None, 12) == (None, "craps")
    assert cr.advance_point(8, 8) == (None, "point_made") and cr.advance_point(8, 7) == (None, "seven_out")
    assert cr.advance_point(8, 11) == (8, "roll")
    assert cr.call_words(4, 4) == "Hard eight" and cr.call_words(2, 4) == "Six, easy six" and cr.call_words(5, 6) == "Yo-leven"


def test_what_can_go_down_and_come_off():
    assert cr.check({"pass": 500}, "pass", 0, 500, None) is None
    assert "point is on" in cr.check({"pass": 500}, "pass", 0, 500, 6)
    assert "come-out" in cr.check({"come": 500}, "come", 0, 500, None)
    assert "contract" in cr.check({"pass": 0}, "pass", 500, 0, 6)
    assert "contract" in cr.check({}, "come_6", 500, 0, 6)
    assert cr.check({}, "dcome_6", 500, 0, 6) is None                        # a don't bet can always come down
    assert "by themselves" in cr.check({"come_6": 1000}, "come_6", 500, 1000, 6)
    assert cr.check({"pass": 500, "pass_odds": 2500}, "pass_odds", 0, 2500, 6) is None   # 5x on 6
    assert "capped" in cr.check({"pass": 500, "pass_odds": 2000}, "pass_odds", 0, 2000, 4)  # 3x on 4
    assert "no bet there" in cr.check({"pass_odds": 500}, "pass_odds", 0, 500, 4)
    assert "odds down first" in cr.check({"dont_pass": 0, "dont_odds": 1000}, "dont_pass", 500, 0, 4)
    assert "minimum" in cr.check({"field": 100}, "field", 0, 100, None)
    assert cr.check({"hard8": 100}, "hard8", 0, 100, None) is None
    assert "limit" in cr.check({"any7": 20000}, "any7", 0, 20000, None)
    assert "bought" in cr.check({"buy_4": 1000, "place_4": 500}, "place_4", 0, 500, None)


# ---------------------------------------------------------------- the throw
@pytest.mark.parametrize("seed", range(40))
def test_the_dice_land_on_their_faces_at_the_far_end(seed):
    rng = random.Random(seed)
    shooter = seed % 8
    faces = (rng.randint(1, 6), rng.randint(1, 6))
    plan = cr.plan_throw(shooter, faces, rng)
    rest = cr.resting(plan)
    assert [r[2] for r in rest] == list(faces)
    far = -1 if shooter < 4 else 1   # right-hand players throw to the left end
    for segs in plan:
        assert segs[1]["x1"] == far * cr.WALL_X                              # it hits the far wall
        for a, b in zip(segs, segs[1:]):
            assert (a["x1"], a["y1"], a["t1"]) == (b["x0"], b["y0"], b["t0"])  # one continuous path
        assert all(cr.FELT_Y[0] <= s["y1"] <= cr.FELT_Y[1] for s in segs[1:])
        assert far * segs[-1]["x1"] > 100                                    # at rest out at the far end
    assert ((rest[0][0] - rest[1][0]) ** 2 + (rest[0][1] - rest[1][1]) ** 2) ** 0.5 >= 9
    assert 1.3 < cr.throw_seconds(plan) < 2.0


@pytest.mark.parametrize("seed", range(40))
def test_the_dice_bounce_off_chips_and_never_stop_on_them(seed):
    rng = random.Random(seed)
    shooter = seed % 8
    far = -1 if shooter < 4 else 1
    # A crowded far end: a stack every 12 units or so across the dice's landing area.
    chips = [(far * x + rng.uniform(-3, 3), y + rng.uniform(-3, 3)) for x in range(105, 164, 14)
             for y in range(-100, -20, 16)]
    faces = (rng.randint(1, 6), rng.randint(1, 6))
    plan = cr.plan_throw(shooter, faces, rng, chips)
    assert [r[2] for r in cr.resting(plan)] == list(faces)
    for segs in plan:
        for a, b in zip(segs, segs[1:]):
            assert (a["x1"], a["y1"], a["t1"]) == (b["x0"], b["y0"], b["t0"])
        for s in segs[2:]:   # low down (off the wall onwards), a die never runs into a stack
            for cx, cy in chips:
                for k in range(11):
                    x = s["x0"] + (s["x1"] - s["x0"]) * k / 10
                    y = s["y0"] + (s["y1"] - s["y0"]) * k / 10
                    assert ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 >= cr.HIT - 0.1


# ---------------------------------------------------------------- the table
class Dice:
    """Rolls the given totals (or pairs) in order."""

    def __init__(self, *rolls):
        self.rolls = [r if isinstance(r, tuple) else ((r // 2, r - r // 2) if r > 2 else (1, 1)) for r in rolls]

    def __call__(self):
        return self.rolls.pop(0)


def table(*rolls, seats=8):
    return CrapsMachine("crp_1", seats, Timings(), dice=Dice(*rolls), rng=random.Random(3))


def roll(m, now):
    """Run the clock until the next betting window is open; returns (now, events)."""
    events = []
    for _ in range(4):
        now = m.deadline
        events += m.tick(now)
        if m.phase == "betting":
            break
    return now, events


def kinds(events):
    return [e["kind"] for e in events]


def test_a_shooter_and_a_point():
    m = table(8, 6, 8)
    nora, ray = FakeParticipant("Nora", human=False), FakeParticipant("Ray", human=False)
    events = m.sit(2, nora, 0)
    assert m.shooter == 2 and kinds(events)[-1] == "roll_open" and m.deadline == 5.0   # "Dice out in 5"
    m.sit(5, ray, 0)
    m.set_bet(2, "pass", 1000, 1)
    m.set_bet(2, "pass", 1000, 1)   # (absolute: still £10)
    m.set_bet(5, "field", 500, 1)
    assert nora.balance == 100_000   # nothing's paid until the dice go out
    now, ev = roll(m, 1)
    throw = next(e for e in ev if e["kind"] == "throw")
    assert throw["dice"] == [4, 4] and throw["shooter"] == 2 and nora.balance == 99_000 and ray.balance == 99_500
    result = next(e for e in ev if e["kind"] == "roll_result")
    assert result["point"] == 8 and result["what"] == "point_set" and m.point == 8
    assert result["seats"]["5"][0]["kind"] == "lose" and m.seats[5].bets["field"] == 0
    # The point's on: the Pass Line can't come down, but odds go behind it.
    with pytest.raises(TableError, match="contract"):
        m.set_bet(2, "pass", 0, now)
    m.set_bet(2, "pass_odds", 5000, now)
    with pytest.raises(TableError, match="capped"):
        m.set_bet(2, "pass_odds", 5100, now)
    now, ev = roll(m, now)          # a 6: nothing to the line
    assert m.point == 8 and nora.balance == 94_000
    now, ev = roll(m, now)          # 8: the point. Pass pays even money, odds 6 to 5 and come back.
    result = next(e for e in ev if e["kind"] == "roll_result")
    assert result["what"] == "point_made" and m.point is None and m.shooter == 2
    assert nora.balance == 94_000 + 1000 + 5000 + 6000
    assert m.seats[2].bets["pass"] == 1000 and m.seats[2].bets["pass_odds"] == 0   # the line bet stays up


def test_seven_out_moves_the_dice_clockwise():
    m = table(9, 7, 4)
    a, b, c = (FakeParticipant(n, human=False) for n in "ABC")
    m.sit(1, a, 0)
    m.sit(3, b, 0)
    m.sit(6, c, 0)
    assert m.shooter == 1
    m.set_bet(1, "pass", 500, 0)
    now, _ = roll(m, 0)     # 9: the point
    now, ev = roll(m, now)  # seven out
    assert next(e for e in ev if e["kind"] == "roll_result")["shooter"] == 3 and m.shooter == 3
    assert any(e["kind"] == "say" and "New shooter" in e["text"] or "has the dice" in e.get("text", "") or
               "Dice to" in e.get("text", "") for e in ev)
    m.stand(6, now)
    m.stand(3, now)
    assert m.shooter == 1   # the shooter left: the dice go on round (to whoever's left)


def test_come_bets_travel_and_pay():
    m = table(6, 5, 5)
    p = FakeParticipant("Pat", human=False)
    m.sit(0, p, 0)
    m.set_bet(0, "pass", 500, 0)
    now, _ = roll(m, 0)                       # point 6
    m.set_bet(0, "come", 1000, now)
    now, ev = roll(m, now)                    # 5: the come bet goes to the 5
    assert m.seats[0].bets["come"] == 0 and m.seats[0].bets["come_5"] == 1000
    assert next(e for e in ev if e["kind"] == "roll_result")["after"]["0"]["come_5"] == 1000
    m.set_bet(0, "come_odds_5", 4000, now)
    with pytest.raises(TableError, match="contract"):
        m.set_bet(0, "come_5", 0, now)
    before = p.balance
    now, ev = roll(m, now)                    # 5 again: the come bet and its odds (3 to 2) come back with winnings
    assert p.balance == before - 4000 + 1000 + 1000 + 4000 + 6000
    assert m.seats[0].bets["come_5"] == 0 and m.seats[0].bets["come_odds_5"] == 0


def test_a_come_bet_arriving_on_a_number_that_just_won_stays_there():
    """Come bet on the 6, a new Come bet, a 6: the old one's paid and comes off, the new
    one takes its place on the 6 (it used to come off with the old one)."""
    m = table(4, 6, 6, 7)
    p = FakeParticipant("Pat", human=False)
    m.sit(0, p, 0)
    m.set_bet(0, "pass", 500, 0)
    now, _ = roll(m, 0)                       # point 4
    m.set_bet(0, "come", 1000, now)
    now, _ = roll(m, now)                     # 6: the come bet goes to the 6
    m.set_bet(0, "come", 2000, now)           # a new Come bet
    before = p.balance
    now, ev = roll(m, now)                    # 6 again
    result = next(e for e in ev if e["kind"] == "roll_result")
    assert m.seats[0].bets["come"] == 0 and m.seats[0].bets["come_6"] == 2000
    assert result["after"]["0"]["come_6"] == 2000
    assert p.balance == before - 2000 + 1000 + 1000   # the new bet's paid for; the old one's back with its win
    won = next(st for st in result["seats"]["0"] if st["spot"] == "come_6")
    assert won["kind"] == "win" and won["amount"] == 1000 and not won["stays"]
    assert m.locked[0]["come_6"] == 2000
    now, ev = roll(m, now)                    # seven out: the new come bet loses (it was really there)
    assert m.seats[0].bets["come_6"] == 0


def test_a_dont_come_bet_arriving_on_a_number_that_just_lost_stays_there():
    m = table(4, 9, 9)
    p = FakeParticipant("Pat", human=False)
    m.sit(0, p, 0)
    m.set_bet(0, "pass", 500, 0)
    now, _ = roll(m, 0)                       # point 4
    m.set_bet(0, "dont_come", 1000, now)
    now, _ = roll(m, now)                     # 9: the don't come bet goes behind the 9
    m.set_bet(0, "dont_come", 2000, now)
    now, ev = roll(m, now)                    # 9 again: the old one loses, the new one travels
    assert m.seats[0].bets["dcome_9"] == 2000 and m.seats[0].bets["dont_come"] == 0
    lost = next(st for st in next(e for e in ev if e["kind"] == "roll_result")["seats"]["0"] if st["spot"] == "dcome_9")
    assert lost["kind"] == "lose" and lost["amount"] == 1000


def test_the_dice_go_round_the_chips():
    """The throw is planned around the stacks on the far end's layout."""
    m = table(8)
    people = [FakeParticipant(n, human=False) for n in "ABCDE"]
    for seat, person in zip((0, 4, 5, 6, 7), people):
        m.sit(seat, person, 0)
    for seat in (4, 5, 6, 7):                 # the far end, for seat 0, is crowded
        for spot, a in (("pass", 500), ("field", 500), ("come", 0), ("place_6", 600), ("place_8", 600), ("big8", 500)):
            if a:
                m.set_bet(seat, spot, a, 0)
    m.set_bet(0, "pass", 500, 0)
    now, ev = roll(m, 0)
    throw = next(e for e in ev if e["kind"] == "throw")
    chips = cr.chips_on_table({i: m.seats[i].bets for i in m.occupied()})
    for x, y, *_ in cr.resting(throw["plan"]):
        assert all(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 >= cr.HIT - 0.05 for cx, cy in chips)


def test_chip_positions_match_the_layout():
    assert cr.chip_pos(0, "pass") == (164, -20) and cr.chip_pos(7, "pass_odds") == (-164, -7.5)
    assert cr.chip_pos(3, "field") == (56, -48) and cr.chip_pos(4, "come") == (-56, -72)
    assert cr.chip_pos(0, "field") == (142, -48)          # kept inside the Field
    assert cr.chip_pos(1, "place_6") == (60 + 2 * cr.BOX_W + cr.BOX_W / 2 + 2.2, -92)
    assert cr.chip_pos(0, "hard8") == (-19 + 3.5 * 3.6, -79)


def test_taking_bets_down():
    m = table(8, 8)
    p = FakeParticipant("Pat")
    q = FakeParticipant("Quin", human=False)
    m.sit(0, q, 0)
    m.sit(4, p, 0)
    m.set_bet(0, "pass", 500, 0)
    m.set_bet(4, "place_6", 1200, 0)
    m.set_bet(4, "place_6", 600, 0)     # never paid for: nothing to refund
    assert p.balance == 100_000
    now, _ = roll(m, 0)                  # paid for at the throw; point 8
    assert p.balance == 99_400
    ev = m.clear_bets(4, now)
    assert ev[0]["_paid"] == [p] and p.balance == 100_000 and m.locked[4] == {}
    with pytest.raises(TableError, match="Your bets stay"):
        m.rebet(4, now)


def test_working_bets_on_the_come_out():
    m = table(6, 6)
    p, q = FakeParticipant("Pat"), FakeParticipant("Quin", human=False)
    m.sit(0, q, 0)
    m.sit(4, p, 0)
    m.set_bet(0, "pass", 500, 0)
    m.set_bet(4, "place_6", 600, 0)
    now, ev = roll(m, 0)                 # a 6 coming out: the place bet's off
    assert "4" not in next(e for e in ev if e["kind"] == "roll_result")["seats"]
    m.point = None                       # (a fresh come-out)
    m.set_working(4, True, now)
    now, ev = roll(m, now)
    assert next(e for e in ev if e["kind"] == "roll_result")["seats"]["4"][0]["win"] == 700


def test_a_human_shooter_rolls_when_ready_or_passes_the_dice():
    m = table(7, 7)
    you = FakeParticipant("You")
    npc = FakeParticipant("Nora", human=False)
    m.sit(1, you, 0)
    m.sit(2, npc, 0)
    assert m.shooter == 1 and m.deadline == 20.0           # your roll: 20 seconds
    with pytest.raises(TableError, match="needs a Pass Line"):
        m.shoot(1, 0.5)
    m.set_bet(1, "pass", 500, 0.5)
    m.shoot(1, 0.5)
    assert m.deadline == 2.0                                # bets stay open at least 2 seconds
    with pytest.raises(TableError, match="not the shooter"):
        m.shoot(2, 0.5)
    now, ev = roll(m, 0.5)
    assert "throw" in kinds(ev) and you.balance == 100_000 and m.seats[1].bets["pass"] == 500   # won; the bet stays up
    # This time you don't roll: the dice pass on.
    assert m.shooter == 1
    events = m.tick(m.deadline)
    assert {"kind": "shooter_change", "shooter": 2, "reason": "timeout", "point": None} in events
    assert m.shooter == 2


def test_taking_the_dice_from_an_npc():
    m = table(5, 9, 5, 7)
    npc = FakeParticipant("Nora", human=False)
    you = FakeParticipant("You")
    m.sit(3, npc, 0)
    m.set_bet(3, "pass", 500, 0)
    m.sit(6, you, 0)
    ev = m.take_dice(6, True, 0)          # no point on: straight away
    assert m.shooter == 6 and "roll_open" in kinds(ev) and m.deadline == 20.0
    m.pass_dice(6, 1)
    assert m.shooter == 3
    now, _ = roll(m, 1)                   # Nora sets a 5
    ev = m.take_dice(6, True, now)        # the point's on: you'll get them when it's decided
    assert ev == [{"kind": "dice_queued", "seat": 6, "on": True}] and m.shooter == 3
    now, _ = roll(m, now)                 # 9
    assert m.shooter == 3
    now, _ = roll(m, now)                 # 5: point made -- the dice come to you
    assert m.shooter == 6 and m.want_dice == []


def test_waiting_on_a_human_shooter_until_they_seven_out():
    m = table(4, 4, 6, 7)
    a, b = FakeParticipant("Ann"), FakeParticipant("Bea")
    m.sit(0, a, 0)
    m.sit(5, b, 0)
    m.take_dice(5, True, 0)               # Ann's a human with the dice: Bea waits
    assert m.shooter == 0 and m.want_dice == [5]
    m.set_bet(0, "pass", 500, 0)
    m.shoot(0, 0)
    now, _ = roll(m, 0)                   # 4: point
    m.shoot(0, now)
    now, _ = roll(m, now)                 # 4: made -- Ann keeps the dice
    assert m.shooter == 0
    m.shoot(0, now)
    now, _ = roll(m, now)                 # 6: point
    m.shoot(0, now)
    now, _ = roll(m, now)                 # seven out: to Bea
    assert m.shooter == 5


def test_the_next_player_inherits_the_point():
    m = table(10)
    a, b = FakeParticipant("A", human=False), FakeParticipant("B", human=False)
    m.sit(2, a, 0)
    m.sit(4, b, 0)
    m.set_bet(2, "pass", 500, 0)
    m.set_bet(2, "place_6", 600, 0)
    now, _ = roll(m, 0)                   # point 10
    before = a.balance
    ev = m.stand(2, now)
    assert m.shooter == 4 and m.point == 10
    assert {"kind": "shooter_change", "shooter": 4, "reason": "left", "point": 10} in ev
    assert a.balance == before + 600      # the place bet came back; the Pass Line stayed with the house


def test_an_idle_player_is_stood_up():
    m = table(*([11] * (INACTIVE_ROLLS + 2)))
    npc, you = FakeParticipant("Nora", human=False), FakeParticipant("You")
    m.sit(0, npc, 0)
    m.sit(5, you, 0)
    m.set_bet(0, "dont_pass", 500, 0)   # (11s: the don't loses, so top it up)
    now = 0
    for _ in range(INACTIVE_ROLLS):
        if not m.seats[0].bets.get("dont_pass"):
            m.set_bet(0, "pass", 500, now)
        now, ev = roll(m, now)
    assert m.seats[5].participant is None
    assert any(e["kind"] == "stood" and e.get("reason") == "inactive" for e in ev)


def test_snapshot_mid_throw():
    m = table(3)
    p = FakeParticipant("P", human=False)
    m.sit(0, p, 0)
    m.set_bet(0, "pass", 500, 0)
    m.tick(m.deadline)
    snap = m.snapshot(None, m.roll["at"] + 0.5)
    assert snap["phase"] == "throwing" and snap["throw"]["elapsed"] == 0.5 and snap["throw"]["dice"] == [1, 2]
    assert snap["seats"][0]["locked"] == {"pass": 500}
    m.tick(m.deadline)
    snap = m.snapshot(None, m.deadline - 0.1)
    assert snap["phase"] == "settling" and len(snap["rest"]) == 2 and snap["history"][0] == [1, 2]


# ---------------------------------------------------------------- NPCs at the table
def test_npcs_keep_the_craps_table_busy(tmp_path):
    now = [1_000_000.0]
    casino = Casino(Store(tmp_path / "c.sqlite"), npc_population=3, rng=random.Random(7),
                    clock=lambda: now[0], wall=lambda: now[0], speed=0.2)
    craps = casino.tables["crp_1"]
    seen = 0
    for _ in range(6000):
        now[0] += 0.2
        casino.npcs.tick(now[0])
        for r in casino.tables.values():
            r.publish(r.machine.tick(now[0]))
        seen = max(seen, sum(1 for s in craps.machine.seats if s.participant is not None))
        if seen >= 2:
            break
    assert seen >= 2


def test_npcs_play_craps_and_only_leave_when_nothing_is_stuck(tmp_path):
    now = [1_000_000.0]
    casino = Casino(Store(tmp_path / "c.sqlite"), npc_population=4, rng=random.Random(11),
                    clock=lambda: now[0], wall=lambda: now[0], speed=0.2, npc_pace=0.2)
    m = casino.tables["crp_1"].machine
    throws = 0
    left_with_contract = []
    for _ in range(30_000):
        now[0] += 0.2
        before = {i: (s.participant, m.contract_bets(i)) for i, s in enumerate(m.seats) if s.participant}
        casino.npcs.tick(now[0])
        for r in casino.tables.values():
            events = r.machine.tick(now[0])
            throws += sum(1 for e in events if e["kind"] == "throw" and r.machine is m)
            r.publish(events)
        for i, (p, stuck) in before.items():
            if m.seats[i].participant is not p and stuck and m.phase == "betting":
                left_with_contract.append(p.name)
        if throws >= 60:
            break
    assert throws >= 60
    assert left_with_contract == []


# ---------------------------------------------------------------- over the wire
def test_a_roll_over_the_wire(client):
    from conftest import recv_until
    from test_ws import join
    client.app.state.casino.tables["crp_1"].machine.dice = Dice((3, 4))
    with client.websocket_connect("/ws") as ws:
        join(ws)
        ws.send_json({"type": "sit", "table": "crp_1", "seat": 2})
        seated = recv_until(ws, "seated")
        assert seated["rules"]["seats"] == 8 and seated["rules"]["min_ante"] == 500
        state = recv_until(ws, "table_state", where=lambda m: m["table"] == "crp_1")
        assert state["shooter"] == 2 and state["human_shooter"] and state["point"] is None
        ws.send_json({"type": "shoot"})
        assert "needs a Pass Line" in recv_until(ws, "error")["message"]
        ws.send_json({"type": "bet", "spot": "pass", "add": 500})
        ws.send_json({"type": "bet", "spot": "field", "add": 500})
        recv_until(ws, "table_event", "bet_changed", where=lambda m: "field" in m["event"]["bets"])
        ws.send_json({"type": "shoot"})
        throw = recv_until(ws, "table_event", "throw")["event"]
        assert throw["dice"] == [3, 4] and len(throw["plan"]) == 2
        assert recv_until(ws, "wallet")["balance"] == 99_000
        result = recv_until(ws, "table_event", "roll_result")["event"]
        assert result["what"] == "natural" and result["after"]["2"] == {"pass": 500}
        assert recv_until(ws, "wallet")["balance"] == 99_500     # the pass won (and stays up); the field lost
        ws.send_json({"type": "take_dice", "on": False})
        ws.send_json({"type": "working", "on": True})
        assert recv_until(ws, "table_event", "working")["event"]["on"] is True
        ws.send_json({"type": "stand"})
        assert recv_until(ws, "wallet")["balance"] == 100_000    # the pass bet comes down with you (no point on)...
        recv_until(ws, "table_event", "stood")                   # ...and then you're up


def test_asking_for_the_dice_while_they_are_out_gets_them_at_the_next_come_out():
    m = table(11, 4)
    npc, you = FakeParticipant("Nora", human=False), FakeParticipant("You")
    m.sit(3, npc, 0)
    m.set_bet(3, "pass", 500, 0)
    m.sit(6, you, 0)
    m.tick(m.deadline)                      # the dice are out
    assert m.take_dice(6, True, m.deadline) == [{"kind": "dice_queued", "seat": 6, "on": True}]
    now, ev = roll(m, m.deadline)           # 11: still coming out, so the dice come straight over
    assert m.shooter == 6 and {"kind": "shooter_change", "shooter": 6, "reason": "taken", "point": None} in ev


def test_the_last_player_leaving_mid_roll_leaves_the_table_ready_for_the_next():
    m = table(9, 4)
    you = FakeParticipant("You")
    m.sit(2, you, 0)
    m.set_bet(2, "pass", 500, 0)
    m.shoot(2, 0)
    m.tick(m.deadline)                    # the dice are out...
    m.stand(2, m.deadline)                # ...and you walk off
    m.tick(m.deadline)                    # the roll's settled
    m.tick(m.deadline)
    assert m.phase == "betting" and m.deadline is None and m.shooter is None
    other = FakeParticipant("Next")
    ev = m.sit(5, other, 100)
    assert m.shooter == 5 and kinds(ev)[-1] == "roll_open"
    m.set_bet(5, "pass", 500, 100)        # and bets go down
