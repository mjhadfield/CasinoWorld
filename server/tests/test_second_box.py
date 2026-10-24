"""A second box: a player plays the free seat beside them too, with matching bets. Its cards stay hidden from them
until their own hand is decided (not at Blackjack, where everything's face up and played in turn)."""
import pytest

from casino_server.participants import BoxParticipant
from casino_server.tables.base import TableError
from casino_server.tables.baccarat import BaccaratMachine
from casino_server.tables.baccarat import Timings as BacTimings
from casino_server.tables.runner import TableRunner

from test_blackjack_machine import machine as bj_machine
from test_machine import FakeParticipant, find, kinds
from test_machine import machine as tcp_machine
from test_master_table import change, table
from test_mississippi_machine import machine as ms_machine

# Mike in seat 1, his box in seat 2: his three cards, the box's, then the dealer's.
TCP_CARDS = ["Ah", "Kh", "Qh", "2c", "7d", "9s", "3c", "5d", "8h"]


def with_box(m, player=None, seat=1, box=2, bets=None):
    mike = player or FakeParticipant("Mike")
    m.sit(seat, mike, 0)
    m.take_box(seat, box, 0)
    if bets:
        m.set_bets(seat, bets, 0)
    return mike


# ------------------------------------------------------------------ taking one
def test_the_box_has_to_be_a_free_seat_right_beside_you():
    m = tcp_machine()
    mike = FakeParticipant("Mike")
    m.sit(1, mike, 0)
    m.sit(0, FakeParticipant("Nora", human=False), 0)
    with pytest.raises(TableError, match="beside"):
        m.take_box(1, 3, 0)
    with pytest.raises(TableError, match="taken"):
        m.take_box(1, 0, 0)
    ev = m.take_box(1, 2, 0)
    assert ev[0] == {"kind": "box_taken", "seat": 2, "of": 1, "entity": mike.entity_id, "name": "Mike"}
    assert isinstance(m.seats[2].participant, BoxParticipant) and m.seats[2].box_of == 1 and m.seats[1].box == 2
    with pytest.raises(TableError, match="already"):
        m.take_box(1, 0, 0)
    assert m.humans_seated() == [1] and m.seat_of(mike) == 1 and 2 not in m.free_seats()


def test_npcs_cant_and_not_every_game_offers_one():
    m = tcp_machine()
    m.sit(1, FakeParticipant("Nora", human=False), 0)
    with pytest.raises(TableError):
        m.take_box(1, 2, 0)
    bac = BaccaratMachine("bac_test", 6, BacTimings.instant(), None)
    bac.sit(1, FakeParticipant("Mike"), 0)
    with pytest.raises(TableError, match="no second box"):
        bac.take_box(1, 2, 0)


def test_taking_a_box_matches_the_bets_already_down_if_they_can_be_covered():
    m = tcp_machine()
    mike = FakeParticipant("Mike", balance=3_000)
    m.sit(1, mike, 0)
    m.set_bets(1, {"ante": 1_000}, 0)   # 2,000 at most (Ante + Play): two boxes need 4,000
    with pytest.raises(TableError, match="both boxes"):
        m.take_box(1, 2, 0)
    mike._balance = 5_000
    ev = m.take_box(1, 2, 0)
    assert kinds(ev) == ["box_taken", "bet_changed"] and ev[1]["seat"] == 2 and ev[1]["bets"]["ante"] == 1_000


# ------------------------------------------------------------------ matched bets
def test_every_bet_is_matched_on_the_box_and_bets_aimed_at_it_are_yours():
    m = tcp_machine()
    with_box(m)
    ev = m.set_bet(1, "ante", 500, 0)
    assert [(e["kind"], e["seat"]) for e in ev[:2]] == [("bet_changed", 1), ("bet_changed", 2)]
    m.set_bet(2, "pair_plus", 200, 0)   # (a click on the box's spot)
    assert m.seats[1].bets == m.seats[2].bets and m.seats[1].bets["pair_plus"] == 200
    ev = m.ready(2, 0)
    assert m.seats[1].ready and m.seats[2].ready and {e["seat"] for e in find(ev, "ready")} == {1, 2}


def test_a_bet_that_cant_be_matched_is_refused():
    m = tcp_machine()
    with_box(m, FakeParticipant("Mike", balance=3_000))
    m.set_bet(1, "ante", 500, 0)
    with pytest.raises(TableError, match="both boxes"):
        m.set_bet(1, "ante", 1_000, 0)
    assert m.seats[2].bets["ante"] == 500


# ------------------------------------------------------------------ the hand
def tcp_dealt():
    m = tcp_machine(TCP_CARDS)
    mike = with_box(m, bets={"ante": 1_000})
    m.ready(1, 0)
    m.tick(0)          # bets close, the deal
    m.tick(0)          # decisions open
    assert m.phase == "deciding" and sorted(m.round) == [1, 2]
    return m, mike


def test_both_boxes_are_staked_and_settled_with_a_net_each():
    m, mike = tcp_dealt()
    assert mike.balance == 100_000 - 2_000
    m.decide(1, True, 1)
    m.decide(2, False, 1)
    events = []
    for k in range(20):
        events += m.tick(2 + k)
        if m.phase == "betting":
            break
    box_net, main_net = m.round_net(2), m.round_net(1)
    assert box_net == -1_000                      # folded: the Ante's gone
    assert mike.balance - 100_000 == main_net + box_net
    assert main_net > 0                           # a Straight Flush plays and wins


def test_box_2_waits_for_box_1_and_its_cards_come_then():
    m, mike = tcp_dealt()
    snap = m.snapshot(1, 1)
    assert snap["seats"][1]["cards"] == ["Ah", "Kh", "Qh"]
    assert snap["seats"][2]["cards"] == ["??"] * 3 and snap["seats"][2]["box_of"] == 1
    with pytest.raises(TableError, match="Box 1 first"):
        m.decide(2, True, 1)
    ev = m.decide(1, True, 1)
    shown = find(ev, "box_revealed")
    assert shown and shown[0]["seat"] == 2 and shown[0]["_private"][2]["cards"] == ["2c", "7d", "9s"]
    assert m.snapshot(1, 1)["seats"][2]["cards"] == ["2c", "7d", "9s"]
    assert m.snapshot(None, 1)["seats"][2]["cards"] == ["??"] * 3   # (nobody else sees them)
    m.decide(2, False, 1)


def test_box_1_timing_out_still_shows_box_2():
    m, _ = tcp_dealt()
    ev = m.tick(200)
    assert find(ev, "box_revealed") and 2 in m._shown_boxes


def test_mississippi_box_1_decides_first_on_every_street():
    m = ms_machine([["Jh", "Jd"], ["2c", "7d"]], ["Js", "4c", "9h"])
    with_box(m, bets={"ante": 500})
    m.ready(1, 0)
    for k in range(3):
        m.tick(k * 0.01)
    assert m.phase == "deciding"
    with pytest.raises(TableError, match="Box 1 first"):
        m.play_action(2, "bet1", 1)
    assert find(m.play_action(1, "bet1", 1), "box_revealed")
    m.play_action(2, "bet1", 1)
    for k in range(5):
        m.tick(2 + k * 0.01)
        if m.phase == "deciding":
            break
    assert m.phase == "deciding" and m.street == 1
    with pytest.raises(TableError, match="Box 1 first"):   # shown, but Box 1 still goes first
        m.play_action(2, "bet1", 3)


def test_blackjack_boxes_take_their_turns_with_nothing_hidden():
    # seat 1, seat 2, dealer; then second cards the same way
    m = bj_machine(["10h", "9c", "7d", "8h", "7s", "Kd"])
    mike = with_box(m, bets={"bet": 1_000})
    m.ready(1, 0)
    turns = []
    for k in range(10):
        turns += [e["seat"] for e in find(m.tick(k * 0.01), "turn")]
        if m.phase == "playing":
            break
    assert m.turn[0] == 1 and m._box_shown(2)
    m.play_action(1, "stand", 1)
    m.tick(1)
    assert m.turn[0] == 2
    m.play_action(2, "stand", 1)
    assert mike.balance == 100_000 - 2_000


# ------------------------------------------------------------------ giving it back
def test_drop_it_between_hands_but_not_while_it_plays():
    m, _ = tcp_dealt()
    with pytest.raises(TableError, match="after"):
        m.drop_box(1, 1)
    m2 = tcp_machine()
    with_box(m2, bets={"ante": 500})
    ev = m2.drop_box(1, 0)
    assert find(ev, "box_dropped")[0] == {"kind": "box_dropped", "seat": 2, "of": 1, "reason": "dropped"}
    assert m2.seats[2].participant is None and m2.seats[1].box is None and 2 in m2.free_seats()


def test_standing_up_takes_the_box_too_and_mid_hand_it_folds_like_you():
    m, _ = tcp_dealt()
    ev = m.stand(1, 1)
    assert kinds(ev).index("box_dropped") < kinds(ev).index("stood")
    assert m.round[2].folded and m.round[1].folded
    assert m.seats[1].participant is None and m.seats[2].participant is None


def test_a_master_table_changing_game_ends_the_box():
    m = table()
    mike = FakeParticipant("Mike")
    m.sit(1, mike, 0)
    m.choose_game(1, "three_card_poker", 0)
    change(m, 0)
    m.take_box(1, 2, 1)
    assert m.humans_seated() == [1]
    ev = m.choose_game(1, "blackjack", 2)
    assert find(ev, "box_dropped")[0]["reason"] == "game_change"
    change(m, 2)
    assert m.seats[2].participant is None and m.seat_of(mike) == 1


# ------------------------------------------------------------------ what goes out
class FakeSession:
    def __init__(self):
        self.sent = []

    def push(self, msg):
        self.sent.append(msg)


class FakeCasino:
    def __init__(self, sessions):
        self.sessions = sessions

    def joined_sessions(self):
        return self.sessions

    def send_wallet(self, session):
        pass


def test_the_runner_gives_the_box_cards_to_its_player_once_shown():
    m = tcp_machine(TCP_CARDS)
    mike, other = FakeSession(), FakeSession()
    player = FakeParticipant("Mike")
    player.session = mike
    with_box(m, player, bets={"ante": 1_000})
    runner = TableRunner("tcp_1", FakeCasino([mike, other]), m, clock=lambda: 0.0)
    runner.act("ready", 1)
    runner.publish(m.tick(0))
    dealt = [x["event"] for x in mike.sent if x.get("event", {}).get("kind") == "dealt"][0]
    assert dealt["mine"]["cards"] == ["Ah", "Kh", "Qh"] and "mine_box" not in dealt
    runner.publish(m.tick(0))
    runner.act("decide", 1, True)
    shown = [x["event"] for x in mike.sent if x.get("event", {}).get("kind") == "box_revealed"][0]
    assert shown["mine_box"]["cards"] == ["2c", "7d", "9s"] and "mine" not in shown
    assert not any("mine_box" in x.get("event", {}) or "mine" in x.get("event", {}) for x in other.sent)
    snap = runner.snapshot_for(mike)
    assert snap["my_seat"] == 1 and snap["my_box"] == 2 and snap["second_box"] is True
