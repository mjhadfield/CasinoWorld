"""
Let It Ride table: a timed state machine that runs a real table's flow.

  betting   Three equal bets -- 1, 2 and $ (a chip on any of them sets all
            three) -- plus the £1 Bonus, the 3 Card Bonus and the £1
            Jackpot. Countdown from the first bet; closes early once every
            human is Ready. The Jackpot lights lock in as at the other tables.
  dealing   Three cards to each seat in turn from first base (private), then
            the dealer's two community cards face down.
  deciding  Everyone decides at once: let bet 1 ride, or pull it back (it's
            handed straight back). Out of time: pulled back.
  revealing The dealer turns the first community card; then the same for
            bet 2, and the second card is turned.
  settling  Each player in turn, third base back to first: cards turned
            over, losing bets swept, every bet still up paid the same.
  clearing  Chips back, cards to the rack, betting opens again.

Seating, betting, Ready and the clock are shared with every table (base.py).
"""
from dataclasses import dataclass

from casino_server.dealer import DealerLines
from casino_server.engines import let_it_ride as lir
from casino_server.engines.cards import Deck
from casino_server.tables.base import CHIPS, TableError, TableMachine, returns_detail, say

SPOTS = ("bet1", "bet2", "ante", "bonus", "three_card", "jackpot")
DECISION_SPOTS = ("bet1", "bet2")


@dataclass
class Timings:
    betting: float = 15.0
    betting_npc_only: float = 5.0
    min_betting: float = 3.0
    rebet: float = 3.0
    decide: float = 20.0
    deal_card: float = 0.09
    deal_hand_pause: float = 0.5
    deal_pause: float = 0.8
    jackpot_lock: float = 1.6
    last_decision: float = 0.8
    pull_back: float = 0.6
    reveal: float = 1.4
    settle_pause: float = 0.9
    settle_base: float = 1.2
    settle_step: float = 0.45
    clear: float = 2.4

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


@dataclass
class Hand:
    participant: object
    bets: lir.Bets
    cards: list
    decided: bool = False
    settled: bool = False
    result: lir.Result | None = None
    paid: int = 0


class LetItRideMachine(TableMachine):
    game = lir.GAME_KEY
    label = lir.GAME_LABEL
    SPOTS = SPOTS
    BONUS_SPOTS = ("three_card", "bonus", "jackpot")
    SPOT_NAMES = {"three_card": "3 Card Bonus"}
    SPOT_HANDS = {"three_card": "three_card"}
    MAIN_SPOT = "ante"
    LIMITED = True
    PRIMARY_SPOTS = ("bet1", "bet2", "ante")
    FLAT_SPOTS = {"bonus": lir.BONUS_BET, "jackpot": lir.JACKPOT_BET}
    NEEDS_MAIN = "Side bets need the three main bets alongside them."
    CANT_COVER = "Not enough balance for three equal bets plus side bets."
    CANT_COVER_BOTH = "Not enough balance for three equal bets plus side bets on both boxes."
    SECOND_BOX = True

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=Deck, lines: DealerLines | None = None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.deck_factory = deck_factory
        self.round: dict[int, Hand] = {}
        self.community: list = []
        self.revealed = 0
        self.stage = 0
        self._settle_queue: list[int] = []

    def rules(self) -> dict:
        return {**lir.rules(), "chips": CHIPS, "min_ante": CHIPS[0], "seats": len(self.seats)}

    # 1, 2 and $ are always equal: a bet on any of them sets all three.
    def set_bets(self, seat: int, bets: dict, now: float) -> list:
        bets = dict(bets)
        unit = max(int(bets.get(s, 0) or 0) for s in lir.BASE_SPOTS)
        for s in lir.BASE_SPOTS:
            bets[s] = unit
        return super().set_bets(seat, bets, now)

    def set_bet(self, seat: int, spot: str, amount: int, now: float) -> list:
        bets = self.working_bets(seat)
        if spot in lir.BASE_SPOTS:
            for b in lir.BASE_SPOTS:
                bets[b] = amount
        else:
            bets[spot] = amount
        return super().set_bets(seat, bets, now)

    def live(self) -> list[int]:
        return sorted(self.round)

    # ------------------------------------------------------------------ deciding
    def play_action(self, seat: int, action: str, now: float) -> list:
        if self.phase != "deciding":
            raise TableError("It's not time to decide.")
        h = self.round.get(seat)
        if h is None or h.participant is not self.seats[seat].participant:
            raise TableError("You're not in this hand.")
        if h.decided:
            raise TableError("You've already decided.")
        self._box_first(seat)
        if action not in ("ride", "pull"):
            raise TableError("Let it ride, or pull the bet back.")
        return self._decide(seat, action == "ride", now)

    def _decide(self, seat: int, ride: bool, now: float, reason: str = "") -> list:
        h = self.round[seat]
        h.decided = True
        spot = DECISION_SPOTS[self.stage]
        event = {"kind": "lir_decision", "seat": seat, "stage": self.stage, "spot": spot, "ride": ride}
        if reason:
            event["reason"] = reason
        if not ride:  # pulled back: the bet goes straight back to its owner
            setattr(h.bets, spot, False)
            self._credit(h.participant, h.bets.unit, "pull_back", returns_detail([(spot, h.bets.unit, h.bets.unit)]))
            event.update(amount=h.bets.unit, _paid=[h.participant])
        return [event] + self._all_decided(now)

    def _all_decided(self, now: float) -> list:
        if self.phase == "deciding" and all(h.decided for h in self.round.values()):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return self._reveal_boxes()

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        h = self.round.get(seat)
        if h is not None and h.participant is self.seats[seat].participant and not h.decided \
                and self.phase == "deciding":
            return self._decide(seat, False, now, reason="left")
        return []

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            return self._open_stage(now)
        if self.phase == "deciding":
            events = []
            for seat in sorted(self.round):  # out of time: pulled back
                if not self.round[seat].decided:
                    events += self._timed_out(seat) + self._decide(seat, False, now, reason="timeout")
            return events + self._reveal(now)
        if self.phase == "revealing":
            if self.revealed < 2:
                self.stage += 1
                return self._open_stage(now)
            return self._start_settling(now)
        if self.phase == "settling":
            return self._settle_next(now)
        if self.phase == "clearing":
            return self._open_betting(now)
        return []

    # ------------------------------------------------------------------ round flow
    def _close_betting(self, now: float) -> list:
        events, taken = self._take_bets(now)
        if not taken:
            return events
        deck = self.deck_factory()
        self.round = {i: Hand(self.seats[i].participant,
                              lir.Bets(b["ante"], b["bonus"], b["three_card"], b["jackpot"]), deck.deal(3))
                      for i, b in sorted(taken.items())}
        self.community = deck.deal(2)
        self.revealed, self.stage = 0, 0
        self.phase = "dealing"
        order = [[who, c] for who in sorted(self.round) for c in range(3)] + [["community", c] for c in range(2)]
        jackpots = [i for i in sorted(taken) if taken[i]["jackpot"]]
        t = self.timings
        duration = len(order) * t.deal_card + (len(self.round) + 1) * t.deal_hand_pause + t.deal_pause
        if jackpots:
            duration += t.jackpot_lock
        self.deadline = now + duration
        events.append({"kind": "bets_closed", "seats": sorted(taken), "jackpots": jackpots,
                       "_paid": [self.seats[i].participant for i in sorted(taken)]})
        events.append({"kind": "dealt", "order": order, "interval": t.deal_card, "hand_pause": t.deal_hand_pause,
                       "_private": {i: {"cards": [c.code for c in h.cards], "hand": self._seen_label(h)}
                                    for i, h in self.round.items()}})
        return events

    def _open_stage(self, now: float) -> list:
        for h in self.round.values():
            h.decided = False
        self.phase = "deciding"
        self.deadline = now + self.timings.decide
        line = self.lines.say("let_it_ride", "decide", bet=str(self.stage + 1))
        return [{"kind": "decisions_open", "stage": self.stage, "spot": DECISION_SPOTS[self.stage],
                 "seconds": self.timings.decide, "seats": sorted(self.round),
                 "_private": {i: {"hand": self._seen_label(h)} for i, h in self.round.items()}}] + say(line)

    def _reveal(self, now: float) -> list:
        self.phase = "revealing"
        first = self.revealed
        self.revealed += 1
        pulled = sum(1 for h in self.round.values() if not getattr(h.bets, DECISION_SPOTS[self.stage]))
        self.deadline = now + self.timings.reveal + (self.timings.pull_back if pulled else 0.0)
        return [{"kind": "community", "from": first, "cards": [self.community[first].code],
                 "_private": {i: {"hand": self._seen_label(h)} for i, h in self.round.items()}}]

    def _start_settling(self, now: float) -> list:
        self.phase = "settling"
        for h in self.round.values():
            h.result = lir.settle(h.cards, self.community, h.bets)
        self._settle_queue = sorted(self.round, reverse=True)
        return self._settle_next(now)

    def _settle_next(self, now: float) -> list:
        if not self._settle_queue:
            self.phase = "clearing"
            self.deadline = now + self.timings.clear
            return [{"kind": "round_end"}]
        seat = self._settle_queue.pop(0)
        h = self.round[seat]
        h.settled = True
        r = h.result
        events = []
        pool = 0
        if r.jackpot_share and self.jackpot:
            pool = self.jackpot.win() if r.jackpot_share >= 1.0 else self.jackpot.take(r.jackpot_share)
            events.append({"kind": "jackpot_won", "seat": seat, "amount": pool, "name": h.participant.name})
        h.paid = r.total_returned + pool
        hand = lir.hand_label(lir.evaluate_five_card_hand(h.cards + self.community))
        self._credit(h.participant, h.paid, "win" if r.qualified else "lose", returns_detail(
            self._stakes(h, r, pool), hand=hand, three_card=self._three_card_label(r.three_tier)))
        steps = self._steps(h, r, pool)
        t = self.timings
        self.deadline = now + t.settle_base + 2 * t.settle_pause + t.settle_step * len(steps)
        key = "win" if r.qualified else "lose"
        line = self.lines.say("let_it_ride", key, name=h.participant.name, hand=hand, pays=f"{r.multiplier} to 1")
        events.append({"kind": "settle_seat", "seat": seat, "outcome": key, "multiplier": r.multiplier,
                       "cards": [c.code for c in h.cards], "hand": hand,
                       "three_card": self._three_card_label(r.three_tier),
                       "steps": steps, "total_returned": h.paid, "say": line, "pause": t.settle_pause,
                       "_paid": [h.participant]})
        return events

    @staticmethod
    def _three_card_label(tier: str | None) -> str | None:
        if tier is None or tier == "high_card":
            return None
        return "Pair" if tier == "pair" else lir.TIER_LABELS[tier]

    @staticmethod
    def _stakes(h: Hand, r: lir.Result, pool: int) -> list:
        """(spot, stake, returned) for each bet still riding; the flat Jackpot's return is its winnings."""
        stakes = [(spot, h.bets.unit, r.base_returns[spot]) for spot in lir.BASE_SPOTS if spot in r.base_returns]
        return stakes + [("bonus", h.bets.bonus, r.bonus_return), ("three_card", h.bets.three_card, r.three_card_return),
                         ("jackpot", h.bets.jackpot, r.jackpot_fixed + pool)]

    @staticmethod
    def _steps(h: Hand, r: lir.Result, pool: int) -> list:
        steps = []
        for spot, bet, ret in LetItRideMachine._stakes(h, r, pool):
            if bet <= 0:
                continue
            if ret == 0:
                steps.append({"spot": spot, "action": "collect", "amount": bet})
            else:
                steps.append({"spot": spot, "action": "pay", "amount": bet,
                              "payout": ret if spot == "jackpot" else ret - bet})
        return sorted(steps, key=lambda s: s["action"] != "collect")

    def _box_private(self, seat: int) -> dict:
        h = self.round[seat]
        return {"cards": [c.code for c in h.cards], "hand": self._seen_label(h)}

    def _seen_label(self, h: Hand) -> str:
        seen = h.cards + self.community[:self.revealed]
        if len(seen) == 5:
            return lir.hand_label(lir.evaluate_five_card_hand(seen))
        values = sorted((c.value for c in seen), reverse=True)
        names = {14: "Aces", 13: "Kings", 12: "Queens", 11: "Jacks"}
        trips = [v for v in values if values.count(v) >= 3]
        pairs = sorted({v for v in values if values.count(v) == 2}, reverse=True)
        if trips:
            return "Three of a Kind"
        if len(pairs) == 2:
            return "Two Pair"
        if pairs:
            return "Pair of " + names.get(pairs[0], f"{pairs[0]}s")
        high = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}.get(values[0], str(values[0]))
        return f"{high} high"

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.community = []
        self.revealed = self.stage = 0
        self._settle_queue = []
        return self._reopen_betting(now)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        seats = []
        for i, s in enumerate(self.seats):
            if s.participant is None:
                seats.append(None)
                continue
            seats.append({**self._seat_entry(i, s), "cards": [], "hand": None, "decided": False, "result": None})
        for i, h in self.round.items():
            entry = seats[i]
            if entry is None or entry["entity"] != h.participant.entity_id:
                continue
            b = h.bets
            entry["bets"] = {"bet1": b.unit if b.bet1 else 0, "bet2": b.unit if b.bet2 else 0, "ante": b.unit,
                             "bonus": b.bonus, "three_card": b.three_card, "jackpot": b.jackpot}
            entry["decided"] = h.decided
            if h.settled:
                entry["cards"] = [c.code for c in h.cards]
                entry["result"] = {"returned": h.paid}
            else:
                show = self._sees(viewer, i)
                entry["cards"] = [c.code if show else "??" for c in h.cards]
                entry["hand"] = self._seen_label(h) if show else None
        community = [c.code if k < self.revealed else "??" for k, c in enumerate(self.community)]
        timer = self._timer(now, ("betting", "deciding"))
        return {"game": self.game, "phase": self.phase, "seats": seats, "community": community,
                "stage": self.stage, "timer": timer, "my_seat": viewer}
