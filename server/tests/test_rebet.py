"""Rebet cuts the betting countdown to 3 seconds (quietly, with the NPCs keeping up),
and Auto rebet puts last hand's bets back down as each hand ends until a timeout."""
import random

from casino_server.casino import Casino
from casino_server.store import Store
from casino_server.tables.three_card_poker import Timings

from test_machine import CODES, FakeParticipant, find, kinds, machine, timings

ANTE = {"ante": 500, "pair_plus": 0, "prime": 0, "jackpot": 0}


def real_betting(**over):
    """Instant play, but the real betting countdowns."""
    t = Timings()
    return timings(betting=t.betting, betting_npc_only=t.betting_npc_only, min_betting=t.min_betting,
                   rebet=t.rebet, **over)


def played_a_hand(m, seat, now=0.0):
    """Seat `seat` plays a hand of £5 Ante; betting is open again afterwards. Returns the events."""
    m.set_bets(seat, ANTE, now)
    m.ready(seat, now)
    events = m.tick(now + 20)
    if m.phase == "deciding":
        events += m.decide(seat, True, now + 21) + m.tick(now + 21)
    assert m.phase == "betting"
    return events


def test_rebet_cuts_the_countdown_to_three_seconds_quietly():
    m = machine(CODES * 3, timings=real_betting())
    ann, bob = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0), m.sit(1, bob, 0)
    played_a_hand(m, 0)
    m.set_bets(1, ANTE, 100)                         # Bob's bet starts the 15s countdown
    assert m.next_deadline == 115
    events = m.rebet(0, 101)
    assert find(events, "bet_changed")[0]["bets"] == ANTE
    assert find(events, "betting_timer") == [{"kind": "betting_timer", "seconds": 3.0, "quiet": True}]
    assert m.next_deadline == 104


def test_a_rebet_as_the_first_bet_sends_one_quiet_timer():
    m = machine(CODES * 3, timings=real_betting())
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    played_a_hand(m, 0)
    events = m.rebet(0, 100)
    assert find(events, "betting_timer") == [{"kind": "betting_timer", "seconds": 3.0, "quiet": True}]
    assert m.next_deadline == 103


def test_a_rebet_never_puts_the_close_back():
    m = machine(CODES * 3, timings=real_betting())
    ann, bob = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0), m.sit(1, bob, 0)
    played_a_hand(m, 0)
    m.set_bets(1, ANTE, 100)
    events = m.rebet(0, 113)                         # 2s left: stays at 2s
    assert find(events, "betting_timer") == [] and m.next_deadline == 115


def test_auto_rebet_puts_the_bets_back_as_each_hand_ends():
    m = machine(CODES * 4, timings=real_betting())
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    assert m.set_auto_rebet(0, True, 0) == [{"kind": "auto_rebet", "seat": 0, "on": True}]  # nothing to repeat yet
    events = played_a_hand(m, 0)
    opened = kinds(events).index("betting_open")
    back = events[opened:]
    assert find(back, "bet_changed")[0]["bets"] == ANTE
    assert find(back, "betting_timer") == [{"kind": "betting_timer", "seconds": 3.0, "quiet": True}]
    assert m.snapshot(0, 21)["seats"][0]["auto_rebet"] is True
    assert kinds(m.tick(24))[0] == "bets_closed"     # and they play the hand


def test_ticking_auto_rebet_in_the_betting_window_rebets_at_once():
    m = machine(CODES * 3, timings=real_betting())
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    played_a_hand(m, 0)
    events = m.set_auto_rebet(0, True, 100)
    assert kinds(events)[:2] == ["auto_rebet", "bet_changed"] and m.next_deadline == 103
    m.set_auto_rebet(0, False, 101)
    m.clear_bets(0, 101)
    assert kinds(m.set_auto_rebet(0, True, 101)) == ["auto_rebet", "bet_changed"]   # already closing sooner
    assert m.next_deadline == 103
    m.set_bets(0, {**ANTE, "ante": 1_000}, 102)      # something down already: left alone
    m.set_auto_rebet(0, False, 102)
    assert kinds(m.set_auto_rebet(0, True, 102)) == ["auto_rebet"]


def test_a_decision_timeout_unticks_auto_rebet():
    m = machine(CODES * 4, timings=real_betting(decide=20.0))
    ann, bob = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0), m.sit(1, bob, 0)
    played_a_hand(m, 0)
    m.set_auto_rebet(0, True, 50)                    # rebets at once
    m.set_bets(1, ANTE, 50), m.ready(1, 50)
    m.tick(53)
    assert m.phase == "deciding"
    m.decide(1, True, 54)
    events = m.tick(73)                              # Ann never decides
    off = find(events, "auto_rebet")
    assert off == [{"kind": "auto_rebet", "seat": 0, "on": False, "reason": "timeout"}]
    assert kinds(events).index("auto_rebet") < kinds(events).index("decision")
    assert m.phase == "betting" and not any(m.seats[0].bets.values())


def test_auto_rebet_goes_off_when_the_balance_cant_cover_it():
    m = machine(CODES * 3, timings=real_betting())
    ann = FakeParticipant("Ann", balance=1_200)
    m.sit(0, ann, 0)
    m.set_auto_rebet(0, True, 0)
    m.set_bets(0, ANTE, 0), m.ready(0, 0)
    m.tick(20)
    ann._balance = 600                               # can't cover £5 Ante + £5 Play
    events = m.decide(0, False, 21) + m.tick(21)
    off = find(events, "auto_rebet")
    assert len(off) == 1 and off[0]["on"] is False and off[0]["reason"] .startswith("Not enough balance")
    assert m.seats[0].auto_rebet is False


def test_a_rebet_queued_during_a_hand_cuts_the_next_countdown():
    m = machine(CODES * 4, timings=real_betting(decide=50.0))
    ann, bob = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0), m.sit(1, bob, 0)
    played_a_hand(m, 0)
    m.set_bets(1, ANTE, 30), m.ready(1, 30)
    m.ready(0, 30)                                   # Bob's hand: Ann sits it out
    m.tick(35)
    assert m.phase == "deciding" and not m._in_round(0)
    queued = m.rebet(0, 36)
    assert find(queued, "bet_changed")[0]["queued"] is True and find(queued, "betting_timer") == []
    events = m.decide(1, True, 37) + m.tick(37)
    opened = kinds(events).index("betting_open")
    assert find(events[opened:], "betting_timer") == [{"kind": "betting_timer", "seconds": 3.0, "quiet": True}]


def test_npcs_get_their_bets_down_inside_a_rebet_countdown(tmp_path):
    """A human rebets at a table of NPCs who haven't bet yet: every NPC still seated when
    betting closes has a bet down by then. Three Card Poker and Roulette (chip by chip)."""
    for table, population in (("tcp_1", 12), ("rou_1", 30)):   # (enough NPCs that some sit there)
        now = [1_000_000.0]
        casino = Casino(Store(tmp_path / f"{table}.sqlite"), npc_population=population, rng=random.Random(5),
                        clock=lambda: now[0], wall=lambda: now[0])
        runner = casino.tables[table]
        casino.tables = {table: runner}   # the only table on the floor, so its seats fill whatever the NPCs fancy
        m = runner.machine
        mike = FakeParticipant("Mike")
        mike.session = None
        rebet_at = None
        for _ in range(20_000):
            now[0] += 0.2
            casino.npcs.tick(now[0])
            npcs = {i: s.participant for i, s in enumerate(m.seats) if s.participant and not s.participant.is_human}
            if rebet_at is None:
                fresh = (m.phase == "betting" and m.deadline is None and len(npcs) >= 2 and m.free_seats()
                         and not any(any(s.bets.values()) for s in m.seats))
                if fresh:
                    seat = m.free_seats()[0]
                    runner.act("sit", seat, mike)
                    m.seats[seat].last_bets = dict.fromkeys(m.SPOTS, 0) | (ANTE if table == "tcp_1" else {"red": 500})
                    runner.act("rebet", seat)
                    rebet_at, watching = now[0], dict(npcs)
                    assert m.deadline == rebet_at + 3.0
            elif m.phase == "betting":
                bets_before_close = {i: dict(m.seats[i].bets) for i in npcs}
            for r in casino.tables.values():
                r.publish(r.machine.tick(now[0]))
            if rebet_at is not None and m.phase != "betting":
                break
        assert rebet_at is not None, f"{table}: never found a table of NPCs waiting to bet"
        assert now[0] <= rebet_at + 3.0 + 0.2
        still_here = [i for i, p in watching.items() if m.seats[i].participant is p]
        assert still_here, f"{table}: every NPC left"
        for i in still_here:
            assert any(bets_before_close[i].values()), f"{table}: seat {i} didn't bet in time"
