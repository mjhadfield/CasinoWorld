"""High Card Flush and Baccarat: parity with Casino v2's engines to the penny, the
High Card Flush strategy, and both table machines. Parity is skipped without v2."""
import random
import sys
from pathlib import Path

import pytest

from casino_server.engines import baccarat as bac
from casino_server.engines import high_card_flush as hcf
from casino_server.engines.cards import Card, Deck
from casino_server.tables.baccarat import BaccaratMachine
from casino_server.tables.baccarat import Timings as BacTimings
from casino_server.tables.high_card_flush import HighCardFlushMachine
from casino_server.tables.high_card_flush import Timings as HcfTimings

from test_machine import FakeParticipant
from test_pai_gow_machine import PoolJackpot

V2_ROOT = Path.home() / "Projects" / "Casino"
needs_v2 = pytest.mark.skipif(not (V2_ROOT / "games" / "baccarat" / "logic.py").exists(), reason="Casino v2 not present")


@pytest.fixture(scope="module")
def v2():
    sys.path.insert(0, str(V2_ROOT))
    try:
        from core import cards as v2_cards
        from games.baccarat import logic as v2_bac
        from games.high_card_flush import logic as v2_hcf
        yield v2_cards, v2_hcf, v2_bac
    finally:
        sys.path.remove(str(V2_ROOT))


def to_v2(v2_cards, cards):
    return [v2_cards.Card(c.rank, v2_cards.Suit[c.suit.name]) for c in cards]


def cards(*codes):
    return [Card.from_code(c) for c in codes]


@needs_v2
def test_high_card_flush_matches_v2(v2):
    v2_cards, v2_hcf, _ = v2
    rng = random.Random(51)
    deck = Deck(rng=rng)
    pool = 800.0
    for _ in range(15_000):
        deck.reset()
        mine, dealer = deck.deal(7), deck.deal(7)
        ante, fl, sf, jp = rng.choice([1, 5, 25]), rng.choice([0, 1, 5]), rng.choice([0, 1, 5]), rng.choice([0, 1])
        game = v2_hcf.HighCardFlushGame()
        game.deal(float(ante), float(fl), float(sf), float(jp))
        r = game.result
        r.player_cards, r.dealer_cards = to_v2(v2_cards, mine), to_v2(v2_cards, dealer)
        r.player_flush_count, r.player_flush_values, _ = v2_hcf._best_flush(r.player_cards)
        r.player_straight_flush_count, _ = v2_hcf._best_straight_flush(r.player_cards)
        times = rng.choice([0, 1, 1, 2, 3])
        times = min(times, v2_hcf.max_raise_multiplier(r.player_flush_count))
        if times:
            game.raise_bet(times)
        else:
            game.fold()
        v = game.settle(pool)
        ours = hcf.settle(mine, dealer, hcf.Bets(ante * 100, fl * 100, sf * 100, jp * 100, ante * 100 * times), not times)
        assert ours.outcome == {"dealer_no_qualify": "no_qualify"}.get(v.outcome, v.outcome)
        assert (ours.ante_return, ours.raise_return, ours.flush_return, ours.straight_flush_return) == \
            tuple(round(x * 100) for x in (v.ante_return, v.raise_return, v.flush_return, v.straight_flush_return))
        if ours.jackpot_share:
            assert round(pool * ours.jackpot_share * 100) == round(v.jackpot_return * 100)
        else:
            assert ours.jackpot_fixed == round(v.jackpot_return * 100)


@needs_v2
def test_baccarat_matches_v2(v2):
    v2_cards, _, v2_bac = v2
    rng = random.Random(61)
    outcomes = set()
    for _ in range(20_000):
        deck = Deck(num_decks=8, rng=rng)
        stake = {s: rng.choice([0, 0, 1, 5]) for s in bac.ALL_SPOTS}
        stake["banker"] = stake["banker"] or rng.choice([0, 1, 5, 25])
        if not any(stake[s] for s in bac.MAIN_SPOTS):
            stake["player"] = 1
        ordered = deck.deal(6)

        class Stub:
            def __init__(self, seq):
                self.seq = list(seq)

            def deal(self, n):
                out, self.seq = self.seq[:n], self.seq[n:]
                return out

        coup = bac.deal_coup(Stub(ordered))
        game = v2_bac.BaccaratGame()
        game.deck = Stub(to_v2(v2_cards, ordered))
        game.deck.reset = lambda: None
        v = game.deal({k: float(a) for k, a in stake.items()})
        assert (coup.player_total, coup.banker_total, coup.outcome) == (v.player_total, v.banker_total, v.outcome)
        ours = bac.settle(coup, {k: a * 100 for k, a in stake.items()})
        for spot in bac.ALL_SPOTS:
            assert ours[spot] == round(getattr(v, f"{spot}_return") * 100), spot
        outcomes.add(coup.outcome)
    assert outcomes == {"player", "banker", "tie"}


@pytest.mark.parametrize("hand, expected", [
    (["2h", "5h", "9h", "Jh", "3c", "4d", "6s"], 1),       # 4-card flush: raise
    (["10h", "8h", "6h", "2c", "3d", "4s", "7c"], 1),      # 10-8-6: raise
    (["10h", "8h", "5h", "2c", "3d", "4s", "7c"], 0),      # 10-8-5: fold
    (["Kh", "3h", "2h", "2c", "3d", "4s", "7c"], 1),       # K-3-2 beats 10-8-6
    (["2h", "5h", "9h", "Jh", "Qh", "4d", "6s"], 2),       # 5-card flush: 2x
    (["2h", "5h", "9h", "Jh", "Qh", "Ah", "6s"], 3),       # 6-card flush: 3x
    (["Ah", "Kc", "Qd", "Js", "9h", "8c", "7d"], 0),       # no 3-card flush: fold
])
def test_high_card_flush_strategy(hand, expected):
    assert hcf.raise_by(cards(*hand)) == expected


class Rigged:
    def __init__(self, *packets):
        self.queue = [[Card.from_code(c) for c in p] for p in packets]

    def deal(self, n):
        return self.queue.pop(0) if len(self.queue[0]) == n else [self.queue[0].pop(0) for _ in range(n)]


def test_high_card_flush_round_and_side_bets_after_a_fold():
    mike, nora = FakeParticipant("Mike"), FakeParticipant("Nora")
    t = HcfTimings.instant()
    t.decide = 100.0
    m = HighCardFlushMachine("hcf_test", 6, t, PoolJackpot(),
                             deck_factory=lambda: Rigged(["2h", "5h", "9h", "Jh", "Qh", "4d", "6s"],
                                                         ["Ac", "Kc", "Qc", "Jc", "2d", "3s", "7h"],
                                                         ["Kd", "9d", "5d", "2c", "3h", "4s", "8h"]))
    for seat, (p, bets) in enumerate([(mike, {"ante": 100}), (nora, {"ante": 100, "straight_flush": 100})]):
        m.sit(seat, p, 0)
        m.set_bets(seat, bets, 0)
        m.ready(seat, 0)
    m.tick(0)
    with pytest.raises(Exception, match="at most 2x"):
        m.play_action(0, "raise3", 1)
    m.play_action(0, "raise2", 1)
    events = m.play_action(1, "fold", 1) + m.tick(1)
    reveal = next(e for e in events if e["kind"] == "dealer_reveal")
    assert reveal["qualified"] and reveal["hand"].startswith("3-card flush")
    settles = {e["seat"]: e for e in events if e["kind"] == "settle_seat"}
    assert settles[0]["outcome"] == "win" and mike.balance == 100_000 - 300 + 600   # 5-card flush beats 3
    # Nora folded but her A-K-Q-J of clubs is a 4-card straight flush: 60 to 1.
    assert settles[1]["steps"] == [{"spot": "straight_flush", "action": "pay", "amount": 100, "payout": 6_000}]
    assert nora.balance == 100_000 - 200 + 6_100


def test_baccarat_coup_settles_every_seat():
    mike, nora = FakeParticipant("Mike"), FakeParticipant("Nora")
    # Player 9-K (natural 9), Banker 3-4 (7): Player wins with a natural.
    m = BaccaratMachine("bac_test", 6, BacTimings.instant(), None,
                        deck_factory=lambda: Rigged(["9h", "3c", "Kd", "4s", "2h", "2c"]))
    for seat, (p, bets) in enumerate([(mike, {"player": 500, "player_dragon": 100}), (nora, {"banker": 1_000, "tie": 100})]):
        m.sit(seat, p, 0)
        m.set_bets(seat, bets, 0)
        m.ready(seat, 0)
    events = m.tick(0)
    cards_out = [(e["side"], e["card"]) for e in events if e["kind"] == "baccarat_card"]
    assert cards_out == [("player", "9h"), ("banker", "3c"), ("player", "Kd"), ("banker", "4s")]
    result = next(e for e in events if e["kind"] == "coup_result")
    assert result["outcome"] == "player" and result["natural"]
    assert mike.balance == 100_000 + 500 + 100      # Player 1:1, Dragon natural win 1:1
    assert nora.balance == 100_000 - 1_100


def test_baccarat_needs_a_main_bet():
    p = FakeParticipant("P")
    m = BaccaratMachine("bac_test", 6, BacTimings.instant(), None)
    m.sit(0, p, 0)
    m.set_bets(0, {"player_dragon": 100}, 0)
    with pytest.raises(Exception, match="Player, Banker or Tie"):
        m.ready(0, 0)


def hcf_round(hands, bets, actions):
    t = HcfTimings.instant()
    t.decide = 100.0
    m = HighCardFlushMachine("hcf_test", 6, t, PoolJackpot(), deck_factory=lambda: Rigged(*hands))
    players = [FakeParticipant(f"P{i}") for i in range(len(bets))]
    for seat, (p, b) in enumerate(zip(players, bets)):
        m.sit(seat, p, 0)
        m.set_bets(seat, b, 0)
        m.ready(seat, 0)
    m.tick(0)
    events = []
    for seat, action in enumerate(actions):
        events += m.play_action(seat, action, 1)
    return m, players, events + m.tick(1)


def test_a_raise_puts_the_flush_in_front_and_tucks_a_separate_straight_flush():
    # Seat 0: 4 hearts (the flush) and 7-8-9 of clubs (a separate straight flush). Dealer: 3-card 9-high.
    m, (p,), events = hcf_round([["2h", "6h", "10h", "Kh", "7c", "8c", "9c"], ["9s", "5s", "2s", "3d", "4c", "Qh", "Jd"]],
                                [{"ante": 100, "straight_flush": 100}], ["raise1"])
    action = next(e for e in events if e["kind"] == "hcf_action")
    assert action["flush_count"] == 4 and action["held_count"] == 3
    sweep = next(e for e in events if e["kind"] == "fold_sweep")
    assert sweep["seats"] == [{"seat": 0, "steps": [], "cards": 0}]   # nothing left over to sweep
    settle = next(e for e in events if e["kind"] == "settle_seat")
    assert settle["flush"] == ["Kh", "10h", "6h", "2h"] and sorted(settle["held"]) == ["7c", "8c", "9c"]
    assert {s["spot"]: s["action"] for s in settle["steps"]} == {"ante": "pay", "raise": "pay", "straight_flush": "pay"}


def test_a_fold_is_swept_unseen_and_loses_the_flush_bonus():
    # Seat 0 folds a 4-card flush with a Flush bet: swept, Flush bonus lost. Seat 1 raises.
    m, (folder, raiser), events = hcf_round(
        [["2h", "6h", "10h", "Kh", "3c", "8d", "Js"], ["Ac", "Kc", "Qc", "5d", "9s", "2d", "4s"],
         ["9s", "5s", "3s", "2c", "4d", "7h", "Jd"]],
        [{"ante": 100, "flush": 100}, {"ante": 100}], ["fold", "raise1"])
    sweep = next(e for e in events if e["kind"] == "fold_sweep")
    folded = next(x for x in sweep["seats"] if x["seat"] == 0)
    assert {s["spot"] for s in folded["steps"]} == {"ante", "flush"} and folded["cards"] == 7
    assert not any(e["kind"] == "settle_seat" and e["seat"] == 0 for e in events)
    assert folder.balance == 100_000 - 200
