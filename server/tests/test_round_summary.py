"""The round summary: the whole table's results after a hand (round_end's `summary`), or after a shooter's hand at
Craps (the next come-out's roll_open)."""
from casino_server.participants import BoxParticipant
from casino_server.tables.base import returns_detail

from test_craps import roll, table as craps_table
from test_machine import CODES, FakeParticipant, find, machine, seat_three
from test_roulette import table as roulette_table


def test_three_card_poker_nets_every_seat_best_first_and_calls_out_side_bets():
    m = machine(CODES)
    ann, bob, cat = seat_three(m)
    m.set_bets(0, {"ante": 500, "pair_plus": 100}, 0)
    m.set_bets(2, {"ante": 1_000}, 0)
    m.set_bets(4, {"ante": 500, "jackpot": 100}, 0)
    for s in (0, 2, 4):
        m.ready(s, 0)
    m.tick(1)
    m.decide(2, False, 2)
    m.decide(4, True, 3)
    m.decide(0, True, 4)
    m.tick(4)
    summary = m.round_summary()
    assert summary["title"] == "Last hand"
    assert [r["name"] for r in summary["rows"]] == ["Ann", "Cat", "Bob"]
    assert [r["net"] for r in summary["rows"]] == [m.round_net(0), m.round_net(4), m.round_net(2)]
    assert summary["rows"][0]["net"] == 1_100 and summary["rows"][-1]["net"] == -1_000
    # Ann's Pair Plus won: her net bet by bet, adding up. Cat's Jackpot lost and Bob had none: just their nets.
    assert summary["rows"][0]["lines"] == [{"text": "Ante & Play", "amount": 1_000, "jackpot": False},
                                           {"text": "Pair Plus · Pair", "amount": 100, "jackpot": False}]
    assert summary["rows"][1]["lines"] == [] and summary["rows"][2]["lines"] == []


def test_the_breakdown_adds_up_with_losing_side_bets_and_a_jackpot_first():
    m = machine(CODES)
    ann, _, _ = seat_three(m)
    m.round_start = {0: (ann, ann.balance + 800)}   # (her stakes: ante, Pair Plus, Prime, Jackpot)
    m._credit(ann, 0, "side bets", returns_detail([("prime", 100, 0)]))
    m._credit(ann, 600, "side bets", returns_detail([("pair_plus", 100, 600)], hand="Straight"))
    m._credit(ann, 100_000, "jackpot", returns_detail([("jackpot", 100, 100_000)], hand="Mini Royal"))
    m._credit(ann, 1_000, "win", returns_detail([("ante", 500, 1_000)]))
    summary = m.round_summary()
    assert summary["rows"] == [{"seat": 0, "name": "Ann", "net": 100_800, "lines": [
        {"text": "Ante & Play", "amount": 500, "jackpot": False},
        {"text": "Jackpot · Mini Royal", "amount": 99_900, "jackpot": True},
        {"text": "Pair Plus · Straight", "amount": 500, "jackpot": False},
        {"text": "Prime", "amount": -100, "jackpot": False}]}]
    assert sum(b["amount"] for b in summary["rows"][0]["lines"]) == 100_800


def test_a_second_box_is_one_entry_with_its_player():
    m = machine(CODES)
    ann, bob, _ = seat_three(m)
    box = BoxParticipant(ann)
    m._credit(box, 600, "side bets", returns_detail([("pair_plus", 100, 600)], hand="Straight"))
    m._credit(ann, 200, "side bets", returns_detail([("pair_plus", 100, 200)], hand="Pair"))
    summary = m._summary([{"seat": 1, "participant": box, "net": 1_500}, {"seat": 0, "participant": ann, "net": -500},
                          {"seat": 2, "participant": bob, "net": 200}], "Last hand")
    assert summary["rows"] == [
        {"seat": 0, "name": "Ann", "net": 1_000, "lines": [{"text": "Ante & Play", "amount": 400, "jackpot": False},
                                                           {"text": "Pair Plus · Straight", "amount": 600, "jackpot": False}]},
        {"seat": 2, "name": "Bob", "net": 200, "lines": []}]


def test_nobody_played_means_no_summary():
    m = machine(CODES)
    seat_three(m)
    assert m.round_summary() is None


def test_roulette_titles_the_number_and_calls_out_inside_hits():
    mike, nora = FakeParticipant("Mike"), FakeParticipant("Nora")
    m = roulette_table(17, spin_open=4.0, ball_track=7.6)
    m.sit(0, mike, 0)
    m.sit(1, nora, 0)
    m.set_bets(0, {"n17": 500, "red": 1_000}, 0)
    m.set_bets(1, {"black": 2_000, "sp_14_17": 100}, 0)
    m.ready(0, 0)
    m.ready(1, 0)
    m.tick(0)
    m.tick(4.0)
    events = m.tick(100.0)
    assert m.number is None   # (betting's open again by the time the runner asks)
    summary = m.round_summary()
    assert summary["title"] == "17 Black"
    assert [(r["name"], r["net"], [(b["text"], b["amount"]) for b in r["lines"]]) for r in summary["rows"]] == [
        ("Mike", 16_500, [("Straight up 17", 17_500)]),
        ("Nora", 3_700, [("Split 14/17", 1_700)])]   # (Black's even money: not called out)
    assert find(events, "round_end")


def test_craps_sums_up_a_shooters_hand_at_the_next_come_out():
    m = craps_table((4, 4), (4, 4), (3, 3), (3, 4))   # point 8, hard 8 (point made), point 6, seven out
    nora, ray = FakeParticipant("Nora", human=False), FakeParticipant("Ray", human=False)
    m.sit(2, nora, 0)
    m.sit(5, ray, 0)
    m.set_bet(2, "pass", 1_000, 1)
    now, _ = roll(m, 1)
    m.set_bet(2, "hard8", 100, now)
    now, ev = roll(m, now)                  # hard 8: the point, and the hard way pays 9 to 1 (it stays up)
    assert not any(e.get("summary") for e in ev)
    now, ev = roll(m, now)                  # 6: a new point
    m.set_bet(5, "field", 500, now)
    now, ev = roll(m, now)                  # seven out
    opened = [e for e in ev if e["kind"] == "roll_open"]
    summary = opened[-1]["summary"]
    assert summary["title"] == "Nora's hand · 4 rolls · 1 point"
    # Nora: the line won £10 and lost £10; the hard 8 won £9 and then lost its £1.
    assert summary["rows"] == [
        {"seat": 2, "name": "Nora", "net": 800, "lines": [{"text": "Hard 8", "amount": 900, "jackpot": False}]},
        {"seat": 5, "name": "Ray", "net": -500, "lines": []}]
    assert nora.balance == 100_000 + 800
    now, ev = roll(m, now)                  # the next hand's first roll: no summary of its own yet
    assert not any(e.get("summary") for e in ev)


def test_a_bet_that_pays_on_something_other_than_the_hand_names_no_hand():
    m = machine(CODES)
    ann, _, _ = seat_three(m)
    m.round_start = {0: (ann, ann.balance + 700)}
    m._credit(ann, 1_100, "win", returns_detail([("ante", 500, 1_000), ("prime", 100, 400), ("pair_plus", 100, 0)],
                                                 hand="Pair"))
    lines = m.round_summary()["rows"][0]["lines"]
    assert [b["text"] for b in lines] == ["Ante & Play", "Prime", "Pair Plus"]   # (Prime pays on colour)
