"""The Pai Gow table machines, driven directly with explicit times -- no sleeping.

Rigged decks list the seven 7-card hands in the order they come out of the
shuffler; with the shuffler's number fixed at 1, the dealer's hand comes out
first, then seat 0's, seat 1's, and so on.
"""
import pytest

from casino_server.engines import pai_gow as pg
from casino_server.engines.cards import Card
from casino_server.tables.base import TableError
from casino_server.tables.pai_gow import FaceUpPaiGowMachine, FortunePaiGowMachine, Timings

from test_machine import FakeJackpot, FakeParticipant

NOTHING = ["2c", "4d", "6h", "8s", "10c", "Qd", "Kh"]   # King high, nothing else


class FixedRng:
    """The shuffler's number, fixed."""
    def __init__(self, n=1):
        self.n = n

    def randint(self, a, b):
        return self.n


class Hands:
    """A deck that deals these seven hands (filler for any not given)."""
    def __init__(self, hands):
        filler = [["3c", "5d", "7h", "9s", "Jc", "2d", "4h"]] * 7
        self.hands = [[Card("Joker") if c == "Jkr" else Card.from_code(c) for c in h] for h in (hands + filler)[:7]]

    def deal(self, n):
        return self.hands.pop(0)


class PoolJackpot(FakeJackpot):
    def take(self, share):
        paid = int(self._amount * share)
        self._amount -= paid
        return paid


def timings(**over):
    t = Timings.instant()
    t.setting = 100.0
    for k, v in over.items():
        setattr(t, k, v)
    return t


def machine(cls, hands, start=1, **kw):
    return cls("pg_test", 6, kw.pop("timings", timings()), kw.pop("jackpot", PoolJackpot()),
               deck_factory=lambda: Hands(hands), rng=FixedRng(start), **kw)


def kinds(events):
    return [e["kind"] for e in events]


def deal(m, *players, bets=None, seats=None, now=0.0):
    events = []
    for k, p in enumerate(players):
        seat = seats[k] if seats else k
        m.sit(seat, p, now)
        m.set_bets(seat, bets[k] if bets else {"ante": 1_000}, now)
        events += m.ready(seat, now)
    return events + m.tick(now)


def codes(cards):
    return [c if isinstance(c, str) else c.code for c in cards]


def test_seven_hands_from_the_shuffler_number_empty_seats_to_the_rack():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = machine(FortunePaiGowMachine, [], start=3)
    events = deal(m, a, b, seats=[0, 2])
    dealt = next(e for e in events if e["kind"] == "dealt")
    # Number 3: position 3 (seat 1, empty) first, then seat 2 ... seat 5, the dealer (1), seat 0 (2).
    assert dealt["start"] == 3 and dealt["order"] == [None, 2, None, None, None, "dealer", 0]
    assert set(dealt["_private"]) == {0, 2} and "dealer" not in dealt  # Fortune: the dealer's hand stays down
    assert m.phase == "setting" and kinds(events)[-1] == "setting_open"


def test_fortune_both_hands_win_pays_less_5_percent():
    p = FakeParticipant("Mike")
    dealer = NOTHING
    mine = ["As", "Ad", "Kc", "Kd", "9h", "5s", "3c"]
    m = machine(FortunePaiGowMachine, [dealer, mine])
    deal(m, p)
    with pytest.raises(TableError, match="High hand"):
        m.set_hand(0, ["As", "Ad"], ["Kc", "Kd", "9h", "5s", "3c"], 1)  # Aces in front over Kings behind: a foul
    events = m.set_hand(0, ["Kc", "Kd"], ["As", "Ad", "9h", "5s", "3c"], 1) + m.tick(1)
    assert kinds(events)[:2] == ["hand_set", "dealer_set"]
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert settle["outcome"] == "win" and settle["commission"] == 50
    assert settle["steps"] == [{"spot": "ante", "action": "pay", "amount": 1_000, "payout": 950}]
    assert p.balance == 100_950


def test_out_of_time_sets_by_house_way():
    p = FakeParticipant("Mike")
    m = machine(FortunePaiGowMachine, [NOTHING, ["As", "Ad", "Kc", "Kd", "9h", "5s", "3c"]], timings=timings(setting=5.0))
    deal(m, p)
    events = m.tick(5.0)
    assert next(e for e in events if e["kind"] == "hand_set")["auto"]
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert settle["front_label"] == "Pair of Kings" and settle["back_label"] == "Pair of Aces"  # A-A-K-K splits


def test_face_up_shows_the_dealer_and_an_ace_high_pai_gow_pushes():
    p = FakeParticipant("Mike")
    dealer = ["As", "Kd", "9c", "7h", "5s", "3d", "2c"]
    mine = ["Qh", "Qd", "Qc", "8s", "4c", "6d", "Js"]  # Three Queens: a Fortune win
    m = machine(FaceUpPaiGowMachine, [dealer, mine], timings=timings(claim=100.0))
    events = deal(m, p, bets=[{"ante": 1_000, "fortune": 500}])
    assert next(e for e in events if e["kind"] == "dealt")["dealer"]["back_label"] == "Ace high"
    assert "ace_high_pai_gow" in kinds(events) and "setting_open" not in kinds(events)
    opened = next(e for e in events if e["kind"] == "claim_open")
    assert opened["_private"] == {0: {"bonus": "Three of a Kind"}} and m.phase == "claiming"
    with pytest.raises(TableError):
        m.set_hand(0, ["Qh", "Qd"], ["Qc", "8s", "4c", "6d", "Js"], 1)  # nobody sets a hand
    events = m.claim(0, 1) + m.tick(1)
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert settle["outcome"] == "push" and settle["tier"] == "Three of a Kind"
    assert p.balance == 100_000 - 1_500 + 1_000 + 500 * 4  # Ante back, Fortune 3 to 1


def test_face_up_joker_and_ace_is_not_an_ace_high_pai_gow():
    """The reported bug: Joker + Ace + five unpaired cards is a pair of Aces."""
    p = FakeParticipant("Mike")
    m = machine(FaceUpPaiGowMachine, [["Jkr", "As", "Kd", "9c", "7h", "5s", "3d"]])
    events = deal(m, p)
    assert "ace_high_pai_gow" not in kinds(events) and m.phase == "setting"
    shown = next(e for e in events if e["kind"] == "dealt")["dealer"]
    assert shown["back_label"] == "Pair of Aces" and shown["front_label"] == "King-9"


def test_face_up_fold_mucks_the_hand_unseen_and_loses_every_bet():
    p = FakeParticipant("Mike")
    m = machine(FaceUpPaiGowMachine, [["Ah", "Ac", "Kh", "Kc", "Qd", "Qs", "2c"],
                                      ["7h", "7d", "7c", "2s", "4c", "9d", "Js"]])
    deal(m, p, bets=[{"ante": 1_000, "fortune": 500}])
    events = m.fold(0, 1) + m.tick(1)
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert settle["outcome"] == "fold" and settle["cards"] == []  # trip 7s would have paid the Fortune: gone
    assert {s["spot"]: s["action"] for s in settle["steps"]} == {"ante": "collect", "fortune": "collect"}
    assert p.balance == 100_000 - 1_500


def test_cannot_fold_at_fortune_pai_gow():
    m = machine(FortunePaiGowMachine, [])
    deal(m, FakeParticipant("Mike"))
    with pytest.raises(TableError, match="fold"):
        m.fold(0, 1)


def test_envy_bonus_pays_when_someone_else_hits_four_of_a_kind():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    quads = ["9s", "9h", "9d", "9c", "Kh", "7d", "4s"]
    m = machine(FortunePaiGowMachine, [NOTHING, NOTHING[:6] + ["3s"], quads])
    deal(m, a, b, bets=[{"ante": 1_000, "fortune": 500}, {"ante": 1_000, "fortune": 100}])
    m.set_hand(0, *pg_house(m, 0), 1)
    events = m.set_hand(1, *pg_house(m, 1), 1) + m.tick(1)
    settles = {e["seat"]: e for e in events if e["kind"] == "settle_seat"}
    assert {"spot": "envy", "action": "pay", "amount": 0, "payout": 500} in settles[0]["steps"]  # A envies B's quads
    assert not any(s["spot"] == "envy" for s in settles[1]["steps"])  # B's Fortune bet is under £5, and nobody else hit
    assert settles[1]["tier"] == "Four of a Kind"


def test_a_royal_match_takes_half_the_jackpot():
    p, pot = FakeParticipant("Mike"), PoolJackpot(800_000)
    m = machine(FortunePaiGowMachine, [NOTHING, ["As", "Ks", "Qs", "Js", "10s", "Kh", "Qh"]], jackpot=pot)
    deal(m, p, bets=[{"ante": 1_000, "jackpot": 100}])
    events = m.set_hand(0, *pg_house(m, 0), 1) + m.tick(1)
    won = next(e for e in events if e["kind"] == "jackpot_won")
    assert won["amount"] == 400_000 and pot.amount == 400_000


def test_house_way_suggestion_and_live_check():
    p = FakeParticipant("Mike")
    m = machine(FortunePaiGowMachine, [NOTHING, ["As", "Ad", "Kc", "Kd", "9h", "5s", "3c"]])
    deal(m, p)
    assert m.suggest(0)["front_label"] == "Pair of Kings"
    check = m.check(0, ["As", "Ad"], ["Kc", "Kd", "9h", "5s", "3c"])
    assert check["foul"] and check["front_label"] == "Pair of Aces" and check["back_label"] == "Pair of Kings"
    assert m.check(0, ["As"], [])["front_label"] == ""  # half-built: no names, no foul yet
    with pytest.raises(TableError):
        m.check(0, ["Qh", "As"], [])  # not your card


def test_others_never_see_your_cards_until_settled():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    m = machine(FortunePaiGowMachine, [])
    deal(m, a, b)
    snap = m.snapshot(1, 0)
    assert "cards" not in snap["seats"][0]["hand"] and len(snap["seats"][1]["hand"]["cards"]) == 7
    assert snap["dealer"]["cards"] == ["??"] * 7


def pg_house(m, seat):
    front, back = pg.house_way_set(m.round[seat].cards)
    return codes(front), codes(back)


def test_face_up_ace_high_push_without_a_bonus_folds_unseen():
    a, b = FakeParticipant("A"), FakeParticipant("B")
    dealer = ["As", "Kd", "9c", "7h", "5s", "3d", "2c"]
    m = machine(FaceUpPaiGowMachine, [dealer, NOTHING, ["Qh", "Qd", "Qc", "8s", "4c", "6d", "Js"]],
                timings=timings(claim=10.0))
    events = deal(m, a, b, bets=[{"ante": 1_000, "fortune": 500}, {"ante": 1_000, "fortune": 500}])
    assert next(e for e in events if e["kind"] == "claim_open")["_private"][0] == {"bonus": None}
    with pytest.raises(TableError, match="no bonus"):
        m.claim(0, 1)
    m.fold(0, 1)
    events = m.tick(10.0)  # B doesn't answer: their Three of a Kind is claimed for them
    assert {"kind": "claimed", "seat": 1, "claimed": True} in events
    settles = {e["seat"]: e for e in events if e["kind"] == "settle_seat"}
    assert settles[0]["cards"] == [] and settles[0]["outcome"] == "push"  # mucked unseen, Ante back
    assert len(settles[1]["cards"]) == 7
    assert a.balance == 100_000 - 500 and b.balance == 100_000 + 1_500



def test_envy_pays_at_face_up_but_a_folded_hand_neither_triggers_nor_collects_it():
    a, b, c = FakeParticipant("A"), FakeParticipant("B"), FakeParticipant("C")
    dealer = ["Ah", "Ac", "Kh", "Kc", "Qd", "Qs", "2c"]
    quads = ["9s", "9h", "9d", "9c", "Kd", "7d", "4s"]
    m = machine(FaceUpPaiGowMachine, [dealer, NOTHING, quads, ["8s", "8h", "8d", "8c", "Js", "6d", "3s"]])
    deal(m, a, b, c, bets=[{"ante": 1_000, "fortune": 500}] * 3)
    m.set_hand(0, *pg_house(m, 0), 1)
    m.set_hand(1, *pg_house(m, 1), 1)
    events = m.fold(2, 1) + m.tick(1)  # C's four 8s are mucked unseen
    settles = {e["seat"]: e for e in events if e["kind"] == "settle_seat"}
    envy = {seat: [s["payout"] for s in e["steps"] if s["spot"] == "envy"] for seat, e in settles.items()}
    assert envy == {0: [pg.ENVY_BONUS[pg.FOUR_OF_A_KIND_TIER]], 1: [], 2: []}  # A envies B only; C gets nothing


# ------------------------------------------------------------------ Face Up NPCs
from types import SimpleNamespace

from casino_server.npc import NpcDirector

FACE_UP_DEALER = ["9s", "9h", "Kd", "7c", "5h", "3d", "2c"]   # House Way: King-7 / Pair of 9s


def cards(codes):
    return [Card.from_code(c) for c in codes]


def npc_decision(mine, bets=None):
    """One Face Up NPC deciding against FACE_UP_DEALER: the action it takes."""
    dealer_front, dealer_back = pg.house_way_set(cards(FACE_UP_DEALER))
    me = object()
    hand = SimpleNamespace(participant=me, cards=cards(mine), set=False, folded=False, claimed=False,
                           bets=bets or {"ante": 1_000, "fortune": 0, "jackpot": 0})
    m = SimpleNamespace(phase="setting", game=pg.FACE_UP, round={0: hand},
                        dealer_front=dealer_front, dealer_back=dealer_back)
    acted = []
    runner = SimpleNamespace(act=lambda *a: acted.append(a))
    npc = SimpleNamespace(seat=0, participant=me, decide_at=-1.0, prof=SimpleNamespace(aggressive=False, mistakes=0.0))
    NpcDirector(None, rng=__import__("random").Random(1))._play_pai_gow(npc, m, runner, 0.0)
    return acted[0], dealer_front, dealer_back


def test_best_set_against_finds_a_win_house_way_misses():
    # House Way keeps the pair of 10s behind (A-K in front): that wins anyway, so it's kept.
    outcome, front, back = pg.best_set_against(cards(["10s", "10h", "As", "Kc", "8d", "4h", "2c"]),
                                               *pg.house_way_set(cards(FACE_UP_DEALER)))
    assert outcome == "win" and codes(front) == ["As", "Kc"]
    # A spade flush and a pair of Queens. House Way plays the flush behind with Q-8 in front -- which
    # loses to King-7, so only a push. Queens behind and K-J in front beats both dealer hands.
    seven = cards(["Qc", "Qs", "7s", "4s", "Ks", "Js", "8c"])
    df, db = pg.house_way_set(cards(FACE_UP_DEALER))
    assert pg.settle_ante(*pg.house_way_set(seven), df, db, 1, False).outcome == "push"
    outcome, front, back = pg.best_set_against(seven, df, db)
    assert outcome == "win" and codes(front) == ["Ks", "Js"]


def test_face_up_npc_sets_to_win_then_push_else_folds():
    action, df, db = npc_decision(["10s", "10h", "As", "Kc", "8d", "4h", "2c"])
    assert action[0] == "set_hand"
    assert pg.settle_ante(cards(action[2]), cards(action[3]), df, db, 1, False).outcome == "win"
    action, df, db = npc_decision(["Ah", "Kc", "Qd", "8s", "6h", "4c", "3s"])  # no pair: can't beat the 9s
    assert action[0] == "set_hand"
    assert pg.settle_ante(cards(action[2]), cards(action[3]), df, db, 1, False).outcome == "push"
    action, _, _ = npc_decision(["8s", "7h", "6d", "4c", "3s", "2h", "Jc"])  # nothing beats King-7 or the 9s
    assert action == ("fold", 0)
