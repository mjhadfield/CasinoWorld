"""The Three Card Poker table machine, driven directly with explicit times -- no sleeping."""
import pytest

from casino_server.engines import three_card_poker as tcp
from casino_server.engines.cards import Card
from casino_server.jackpot import JACKPOT_FLOOR
from casino_server.tables.three_card_poker import (INACTIVE_ROUNDS, TableError, ThreeCardPokerMachine,
                                                   Timings)

from conftest import RiggedDeck


class FakeParticipant:
    def __init__(self, name, balance=100_000, human=True):
        self.name, self.entity_id, self.is_human = name, f"e-{name}", human
        self._balance = balance
        self.log = []

    @property
    def balance(self):
        return self._balance

    def debit(self, amount, note):
        if amount > self._balance:
            return False
        self._balance -= amount
        self.log.append((-amount, note))
        return True

    def credit(self, amount, note):
        self._balance += amount
        self.log.append((amount, note))

    def refund(self, amount, note):
        self._balance += amount
        self.log.append((amount, note))


class FakeJackpot:
    def __init__(self, amount=700_000):
        self._amount, self.wins = amount, 0

    @property
    def amount(self):
        return self._amount

    def win(self):
        self.wins += 1
        paid, self._amount = self._amount, JACKPOT_FLOOR
        return paid


def timings(**over):
    """Instant, except a long decision window so humans get to act."""
    t = Timings.instant()
    t.decide = 100.0
    for k, v in over.items():
        setattr(t, k, v)
    return t


def machine(codes=None, **kw):
    deck = (lambda: RiggedDeck(list(codes))) if codes else None
    extra = {"deck_factory": deck} if deck else {}
    return ThreeCardPokerMachine("tcp_1", 6, kw.pop("timings", timings()), kw.pop("jackpot", FakeJackpot()), **extra)


def kinds(events):
    return [e["kind"] for e in events]


def find(events, kind):
    return [e for e in events if e["kind"] == kind]


# Seat 0: pair of Kings. Seat 2: 9-high (folds). Seat 4: flush. Dealer: Queen-high (qualifies).
CODES = ["Ks", "Kd", "4c", "9d", "5c", "2h", "2s", "7s", "Js", "Qh", "8c", "3d"]


def seat_three(m, now=0.0):
    a, b, c = FakeParticipant("Ann"), FakeParticipant("Bob", human=False), FakeParticipant("Cat", human=False)
    m.sit(0, a, now), m.sit(2, b, now), m.sit(4, c, now)
    return a, b, c


def test_full_round_flow_order_and_money():
    m = machine(CODES)
    ann, bob, cat = seat_three(m)
    m.set_bets(0, {"ante": 500, "pair_plus": 100}, 0)
    m.set_bets(2, {"ante": 1_000}, 0)
    m.set_bets(4, {"ante": 500, "jackpot": 100}, 0)
    for s in (0, 2, 4):
        m.ready(s, 0)
    events = m.tick(1)
    assert kinds(events) == ["bets_closed", "say", "dealt", "decisions_open"]
    dealt = find(events, "dealt")[0]
    # three cards at a time: all of seat 0's hand, then seat 2's, then seat 4's, the dealer's last
    assert dealt["order"][:6] == [[0, 0], [0, 1], [0, 2], [2, 0], [2, 1], [2, 2]]
    assert dealt["order"][-3:] == [["dealer", 0], ["dealer", 1], ["dealer", 2]]
    assert dealt["_private"][0]["cards"] == ["Ks", "Kd", "4c"] and dealt["_private"][0]["hand"] == "Pair"
    assert find(events, "decisions_open")[0] == {"kind": "decisions_open", "seconds": 100.0, "seats": [0, 2, 4]}
    assert ann.balance == 100_000 - 600 and bob.balance == 100_000 - 1_000

    # Everyone decides at once, in any order.
    events = m.decide(2, False, 2)
    assert events[0] == {"kind": "decision", "seat": 2, "play": False, "held": False}
    with pytest.raises(TableError):
        m.decide(2, True, 2)  # already decided
    m.decide(4, True, 3)
    assert m.next_deadline == 100 + 1  # still waiting on Ann
    m.decide(0, True, 4)
    assert ann.balance == 100_000 - 1_100
    assert m.next_deadline == 4  # whole table decided: the timer ends early
    events = m.tick(4)
    assert kinds(events) == ["fold_sweep", "dealer_reveal", "say", "settle_seat", "settle_seat",
                             "round_end", "betting_open", "say"]

    # 1. The dealer takes the folded hands and their bets.
    assert find(events, "fold_sweep")[0]["seats"] == [
        {"seat": 2, "muck": True, "steps": [{"spot": "ante", "amount": 1_000}]}]
    # 2. The dealer's own cards are turned over -- nobody else's yet.
    reveal = find(events, "dealer_reveal")[0]
    assert reveal == {"kind": "dealer_reveal", "cards": ["Qh", "8c", "3d"], "hand": "High Card", "qualified": True}
    # 3. Each player settled in turn, third base back to first, their cards shown at their turn.
    #    Within a seat: losing bets swept, then winners paid.
    settles = find(events, "settle_seat")
    assert [x["seat"] for x in settles] == [4, 0]
    assert settles[0]["cards"] == ["2s", "7s", "Js"] and settles[0]["hand"] == "Flush"
    assert [step["action"] for step in settles[0]["steps"]] == ["collect", "pay", "pay"]
    assert settles[0]["steps"][0] == {"spot": "jackpot", "action": "collect", "amount": 100}
    assert settles[1]["net"] == 1_100
    assert {"spot": "pair_plus", "action": "pay", "amount": 100, "payout": 100} in settles[1]["steps"]
    assert ann.balance == 100_000 + 1_100
    assert bob.balance == 100_000 - 1_000
    assert cat.balance == 100_000 + 900  # flush: Ante + Play paid, £1 Jackpot bet lost
    assert m.phase == "betting" and all(not any(s.bets.values()) for s in m.seats)
    assert m.seats[0].last_bets == {"ante": 500, "pair_plus": 100, "prime": 0, "jackpot": 0}


def test_decision_timeout_folds_everyone_undecided():
    m = machine(CODES, timings=timings(decide=20.0))
    ann, bob, _ = seat_three(m)
    for s in (0, 2, 4):
        m.set_bets(s, {"ante": 500}, 0)
        m.ready(s, 0)
    m.tick(0)
    assert m.phase == "deciding"
    m.decide(2, True, 5)
    assert m.tick(19.9) == []
    events = m.tick(20.0)
    timeouts = [e for e in find(events, "decision") if e.get("reason") == "timeout"]
    assert [e["seat"] for e in timeouts] == [0, 4]
    assert "dealer_reveal" in kinds(events)


def test_betting_timer_starts_at_first_bet_and_ready_closes_early():
    m = machine(CODES, timings=Timings())
    ann = FakeParticipant("Ann")
    npc = FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0)
    m.sit(1, npc, 0)
    assert m.next_deadline is None
    events = m.set_bets(1, {"ante": 500}, 10)
    assert find(events, "betting_timer")[0]["seconds"] == 15.0 and m.next_deadline == 25.0
    m.set_bets(0, {"ante": 500}, 12)
    m.ready(0, 12)
    assert m.next_deadline == 12  # min_betting already passed since betting opened at 0
    assert kinds(m.tick(12))[0] == "bets_closed"


def test_jackpot_bets_are_locked_in_before_the_deal():
    m = machine(CODES, timings=Timings())
    seat_three(m)
    m.set_bets(0, {"ante": 500, "jackpot": 100}, 0)
    m.set_bets(2, {"ante": 500}, 0)
    m.set_bets(4, {"ante": 500, "jackpot": 100}, 0)
    events = m.tick(100)
    closed = find(events, "bets_closed")[0]
    assert closed["jackpots"] == [0, 4]
    t = Timings()
    # 4 hands of three (3 players + the dealer), a pause between each hand
    assert m.next_deadline == pytest.approx(100 + 12 * t.deal_card + 3 * t.deal_hand_pause + t.deal_pause + t.jackpot_lock)


def test_npc_only_table_uses_short_window():
    m = machine(CODES, timings=Timings())
    m.sit(0, FakeParticipant("Bob", human=False), 0)
    m.set_bets(0, {"ante": 500}, 5)
    assert m.next_deadline == 5 + Timings().betting_npc_only


def test_bet_validation():
    m = machine(CODES)
    poor = FakeParticipant("Pip", balance=1_000)
    m.sit(0, poor, 0)
    with pytest.raises(TableError):
        m.set_bets(0, {"ante": 600}, 0)  # can't back a £6 Ante with a £6 Play
    with pytest.raises(TableError):
        m.set_bets(0, {"jackpot": 500}, 0)
    with pytest.raises(TableError):
        m.set_bets(0, {"roulette": 5}, 0)
    m.set_bets(0, {"pair_plus": 100}, 0)
    with pytest.raises(TableError):
        m.ready(0, 0)  # side bet without an Ante
    with pytest.raises(TableError):
        m.set_bets(3, {"ante": 100}, 0)  # empty seat
    with pytest.raises(TableError):
        m.sit(0, FakeParticipant("Zed"), 0)  # taken


def test_side_bets_without_ante_are_returned_at_close():
    m = machine(CODES)
    a, b = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, a, 0), m.sit(1, b, 0)
    m.set_bets(0, {"pair_plus": 500}, 0)
    m.set_bets(1, {"ante": 500}, 0)
    events = m.tick(0)
    assert {"kind": "bet_changed", "seat": 0, "bets": dict.fromkeys(("ante", "pair_plus", "prime", "jackpot"), 0)} in events
    assert a.balance == 100_000 and 0 not in m.round


def test_folding_forfeits_pair_plus_even_on_a_winning_hand():
    m = machine(CODES)
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    m.set_bets(0, {"ante": 500, "pair_plus": 500, "jackpot": 100}, 0)  # pair of Kings
    m.tick(0)
    events = m.decide(0, False, 0) + m.tick(0)
    sweep = find(events, "fold_sweep")[0]["seats"][0]
    assert sweep["muck"] and [x["spot"] for x in sweep["steps"]] == ["ante", "pair_plus", "jackpot"]
    assert find(events, "settle_seat") == []
    assert ann.balance == 100_000 - 1_100  # that's on them


def test_fold_under_a_winning_prime_is_settled_like_a_played_hand():
    # Seat 0: all red. Dealer mixed colours, so Prime pays 3:1.
    m = machine(["2h", "7d", "9h", "Qh", "8c", "3d"])
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    m.set_bets(0, {"ante": 500, "pair_plus": 100, "prime": 100}, 0)
    m.tick(0)
    fold = m.decide(0, False, 0)[0]
    assert fold["held"] is True  # cards go under the Prime bet
    events = m.tick(0)
    sweep = find(events, "fold_sweep")[0]["seats"][0]
    assert sweep == {"seat": 0, "muck": False, "steps": [{"spot": "ante", "amount": 500},
                                                         {"spot": "pair_plus", "amount": 100}]}
    settle = find(events, "settle_seat")[0]
    assert settle["held"] and settle["cards"] == ["2h", "7d", "9h"]
    assert settle["steps"] == [{"spot": "prime", "action": "pay", "amount": 100, "payout": 300}]
    assert ann.balance == 100_000 - 700 + 400


def test_fold_with_a_losing_prime_sweeps_it():
    m = machine(CODES)
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    m.set_bets(0, {"ante": 500, "prime": 100}, 0)  # Ks Kd 4c: mixed colours
    m.tick(0)
    assert m.decide(0, False, 0)[0]["held"] is False
    events = m.tick(0)
    assert [x["spot"] for x in find(events, "fold_sweep")[0]["seats"][0]["steps"]] == ["ante", "prime"]
    assert ann.balance == 100_000 - 600


def test_snapshot_privacy():
    m = machine(CODES)
    seat_three(m)
    for s in (0, 2, 4):
        m.set_bets(s, {"ante": 500}, 0)
    m.tick(0)
    mine = m.snapshot(0, 0)
    assert mine["seats"][0]["cards"] == ["Ks", "Kd", "4c"] and mine["seats"][0]["hand"] == "Pair"
    assert mine["seats"][2]["cards"] == ["??"] * 3 and mine["seats"][2]["hand"] is None
    assert mine["dealer"]["cards"] == ["??"] * 3
    assert all(c == "??" for s in m.snapshot(None, 0)["seats"] if s for c in s["cards"])
    assert mine["phase"] == "deciding" and mine["timer"] == 100.0
    m.decide(2, False, 0)  # a fold stays face down on the felt until the dealer's sweep
    folded = m.snapshot(None, 0)["seats"][2]
    assert folded["folded"] and folded["cards"] == ["??"] * 3


def test_standing_mid_hand_folds_and_the_table_carries_on():
    m = machine(CODES)
    ann, bob, cat = seat_three(m)
    m.set_bets(0, {"ante": 500, "pair_plus": 100}, 0)  # pair of Kings, but a fold forfeits Pair Plus
    m.set_bets(2, {"ante": 500}, 0)
    m.tick(0)
    events = m.stand(0, 1)
    assert kinds(events) == ["decision", "stood"] and events[0]["reason"] == "left"
    m.decide(2, True, 2)
    events = m.tick(2)
    assert "dealer_reveal" in kinds(events)
    assert ann.balance == 100_000 - 600  # standing folds the hand: Ante and Pair Plus lost
    assert m.seats[0].participant is None


def test_inactive_human_is_stood_up_after_three_hands():
    m = machine(CODES * 5)
    ann, npc = FakeParticipant("Ann"), FakeParticipant("Bob", human=False)
    m.sit(0, ann, 0), m.sit(1, npc, 0)
    now = 0
    for round_no in range(INACTIVE_ROUNDS):
        m.set_bets(1, {"ante": 100}, now)
        events = m.tick(now)
        m.decide(1, False, now)
        events += m.tick(now)
        now += 1
    stood = find(events, "stood")
    assert stood and stood[0]["seat"] == 0 and stood[0]["reason"] == "inactive"


def test_rebet_and_jackpot_win():
    royal = ["Qs", "Ks", "As", "2c", "5d", "9h"]
    jp = FakeJackpot(1_234_567)
    m = machine(royal * 2, jackpot=jp)
    ann = FakeParticipant("Ann")
    m.sit(0, ann, 0)
    m.set_bets(0, {"ante": 100, "jackpot": 100}, 0)
    m.tick(0)
    events = m.decide(0, True, 0) + m.tick(0)
    assert find(events, "jackpot_won")[0]["amount"] == 1_234_567 and jp.wins == 1
    events = m.rebet(0, 1)
    assert events[0]["bets"] == {"ante": 100, "pair_plus": 0, "prime": 0, "jackpot": 100}


def test_dealer_lines():
    from casino_server.engines.hand_evaluator import evaluate_three_card_hand as ev
    from casino_server.tables.three_card_poker import describe
    assert describe(ev([Card.from_code(c) for c in ("Qh", "8c", "3d")])) == "Queen high"
    assert describe(ev([Card.from_code(c) for c in ("7h", "7c", "3d")])) == "a Pair of 7s"
    assert describe(ev([Card.from_code(c) for c in ("Qs", "Ks", "As")])) == "a Royal Flush"
