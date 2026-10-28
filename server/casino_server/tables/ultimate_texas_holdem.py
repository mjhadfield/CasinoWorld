"""
Ultimate Texas Hold'em table: a timed state machine that runs a real table's flow.

  betting   Ante (the Blind is always the same), Trips and the £1 Jackpot.
            Countdown from the first bet; closes early once every human is
            Ready. The Jackpot lights lock in as at the other tables.
  dealing   Two cards to each seat in turn from first base (private), two
            face down to the dealer, five community cards face down.
  deciding  Before the flop everyone still without a Play bet decides at
            once: bet 4x or 3x the Ante, or check (out of time: check).
  revealing The dealer turns the flop. Then the same for 2x or check, and
            the turn and river are turned together. After the river: bet 1x
            or fold (out of time: fold). A stage with nobody left to decide
            goes straight to the next cards.
  sweeping  The dealer takes the folded hands: Ante, Blind, Trips, Jackpot.
  reveal    The dealer turns their own two cards and announces the hand
            (a pair or better qualifies).
  settling  Each player still in, third base back to first: cards turned
            over, losing bets swept, winners paid beside their stakes.
  clearing  Chips back, cards to the rack, betting opens again.

Seating, betting, Ready and the clock are shared with every table (base.py).
"""
from dataclasses import dataclass

from casino_server.dealer import DealerLines
from casino_server.engines import ultimate_texas_holdem as uth
from casino_server.engines.cards import Deck
from casino_server.tables.base import CHIPS, TableError, TableMachine, returns_detail, say, stakes_detail

SPOTS = ("ante", "blind", "trips", "jackpot")
STAGES = ("preflop", "flop", "river")
ACTIONS = ({"check": 0, "bet4": 4, "bet3": 3}, {"check": 0, "bet2": 2}, {"fold": -1, "bet1": 1})
STAGE_NAMES = ("Before the flop", "The flop", "The river")


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
    reveal: float = 1.5           # the dealer turns the flop, or the turn and river
    skip_stage: float = 0.6       # a stage nobody needs to decide on
    sweep_pause: float = 1.0
    sweep_each: float = 0.5
    dealer_reveal: float = 2.0
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
    bets: uth.Bets
    cards: list
    play_stage: int | None = None   # when the Play bet went down
    folded: bool = False
    decided: bool = False           # this stage
    swept: bool = False
    settled: bool = False
    result: uth.Result | None = None
    paid: int = 0

    @property
    def waiting(self) -> bool:
        """Still to make a Play bet (and still in)."""
        return self.play_stage is None and not self.folded


class UltimateTexasHoldemMachine(TableMachine):
    game = uth.GAME_KEY
    label = uth.GAME_LABEL
    SPOTS = SPOTS
    MAIN_SPOT = "ante"
    LIMITED = True
    PRIMARY_SPOTS = ("ante", "blind")
    FLAT_SPOTS = {"jackpot": uth.JACKPOT_BET}
    NEEDS_MAIN = "Side bets need an Ante alongside them."
    CANT_COVER = "Not enough balance: you need six times your Ante (Ante, Blind and a 4x Play), plus side bets."
    CANT_COVER_BOTH = "Not enough balance: you need six times your Ante, plus side bets, on both boxes."
    SECOND_BOX = True

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=Deck, lines: DealerLines | None = None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.deck_factory = deck_factory
        self.round: dict[int, Hand] = {}
        self.dealer_cards: list = []
        self.board: list = []
        self.revealed = 0       # community cards face up: 0, 3, 5
        self.stage = 0
        self.dealer_shown = False
        self._settle_queue: list[int] = []

    def rules(self) -> dict:
        return {**uth.rules(), "chips": CHIPS, "min_ante": CHIPS[0], "seats": len(self.seats)}

    # The Blind is always the Ante: a bet on either spot sets both.
    def set_bets(self, seat: int, bets: dict, now: float) -> list:
        bets = dict(bets)
        bets["blind"] = bets.get("ante", 0)
        return super().set_bets(seat, bets, now)

    def set_bet(self, seat: int, spot: str, amount: int, now: float) -> list:
        return super().set_bet(seat, "ante" if spot == "blind" else spot, amount, now)

    def max_cost(self, bets: dict) -> int:
        return bets["ante"] * 6 + bets["trips"] + bets["jackpot"]

    def live(self) -> list[int]:
        return [i for i, h in sorted(self.round.items()) if not h.folded]

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        h = self.round.get(seat)
        if h is not None and h.participant is self.seats[seat].participant and h.waiting \
                and self.phase in ("dealing", "deciding", "revealing"):
            h.decided, h.folded = True, True
            return [{"kind": "uth_action", "seat": seat, "stage": self.stage, "action": "fold", "reason": "left"}] \
                + self._all_decided(now)
        return []

    # ------------------------------------------------------------------ deciding
    def play_action(self, seat: int, action: str, now: float) -> list:
        if self.phase != "deciding":
            raise TableError("It's not time to decide.")
        h = self.round.get(seat)
        if h is None or h.participant is not self.seats[seat].participant or not h.waiting:
            raise TableError("You've nothing to decide.")
        if h.decided:
            raise TableError("You've already decided.")
        self._box_first(seat)
        options = ACTIONS[self.stage]
        if action not in options:
            raise TableError({0: "Bet 4x or 3x, or check.", 1: "Bet 2x or check.", 2: "Bet 1x or fold."}[self.stage])
        return self._act(seat, action, now)

    def _act(self, seat: int, action: str, now: float, reason: str = "") -> list:
        h = self.round[seat]
        times = ACTIONS[self.stage][action]
        h.decided = True
        event = {"kind": "uth_action", "seat": seat, "stage": self.stage, "action": action}
        if reason:
            event["reason"] = reason
        if times > 0:
            amount = h.bets.ante * times
            if not h.participant.debit(amount, "play", stakes_detail({"play": amount})):
                times, action = 0, ("check" if self.stage < 2 else "fold")
                event["action"], event["reason"] = action, "funds"
            else:
                h.bets.play, h.play_stage = amount, self.stage
                event.update(amount=amount, _paid=[h.participant])
        if times < 0 or (times == 0 and action == "fold"):
            h.folded = True
        return [event] + self._all_decided(now)

    def _all_decided(self, now: float) -> list:
        if self.phase == "deciding" and all(h.decided for h in self.round.values() if h.waiting):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return self._reveal_boxes()

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            return self._open_stage(now)
        if self.phase == "deciding":
            events = []
            for seat in sorted(self.round):  # out of time: check -- or after the river, fold
                h = self.round[seat]
                if h.waiting and not h.decided:
                    events += self._timed_out(seat) + self._act(seat, "check" if self.stage < 2 else "fold", now, reason="timeout")
            return events + self._after_stage(now)
        if self.phase == "revealing":
            self.stage += 1
            return self._open_stage(now)
        if self.phase == "sweeping":
            return self._dealer_reveal(now) if self.live() else self._start_settling(now)
        if self.phase == "reveal":
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
        self.round = {i: Hand(self.seats[i].participant, uth.Bets(b["ante"], b["trips"], b["jackpot"]), deck.deal(2))
                      for i, b in sorted(taken.items())}
        self.dealer_cards = deck.deal(2)
        self.board = deck.deal(5)
        self.revealed, self.stage, self.dealer_shown = 0, 0, False
        self.phase = "dealing"
        order = [[who, c] for who in sorted(self.round) for c in range(2)] + \
            [["dealer", c] for c in range(2)] + [["community", c] for c in range(5)]
        jackpots = [i for i in sorted(taken) if taken[i]["jackpot"]]
        t = self.timings
        duration = len(order) * t.deal_card + (len(self.round) + 2) * t.deal_hand_pause + t.deal_pause
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
        waiting = [i for i, h in sorted(self.round.items()) if h.waiting]
        for h in self.round.values():
            h.decided = False
        if not waiting:  # everyone has a Play bet down (or has folded): straight on
            self.phase = "deciding"
            self.deadline = now + self.timings.skip_stage
            return []
        self.phase = "deciding"
        self.deadline = now + self.timings.decide
        line = self.lines.say("ultimate_texas_holdem", STAGES[self.stage])
        return [{"kind": "decisions_open", "stage": self.stage, "seconds": self.timings.decide, "seats": waiting,
                 "_private": {i: {"hand": self._seen_label(self.round[i])} for i in waiting}}] + say(line)

    def _after_stage(self, now: float) -> list:
        if self.stage < 2:
            return self._reveal(now)
        return self._sweep_folds(now)

    def _reveal(self, now: float) -> list:
        """The flop (after the first stage), or the turn and river together (after the second)."""
        self.phase = "revealing"
        first = self.revealed
        self.revealed = 3 if self.stage == 0 else 5
        self.deadline = now + self.timings.reveal
        return [{"kind": "community", "from": first, "cards": [c.code for c in self.board[first:self.revealed]],
                 "_private": {i: {"hand": self._seen_label(h)} for i, h in self.round.items() if not h.folded}}]

    def _sweep_folds(self, now: float) -> list:
        self.phase = "sweeping"
        seats = []
        for seat in sorted(self.round, reverse=True):
            h = self.round[seat]
            if not h.folded or h.swept:
                continue
            h.swept = True
            spots = [("ante", h.bets.ante), ("blind", h.bets.blind), ("trips", h.bets.trips), ("jackpot", h.bets.jackpot)]
            seats.append({"seat": seat, "steps": [{"spot": s, "amount": a} for s, a in spots if a > 0]})
        t = self.timings
        self.deadline = now + ((t.sweep_pause + t.sweep_each) * len(seats) + 0.4 * t.sweep_each if seats else 0.0)
        return [{"kind": "fold_sweep", "seats": seats, "pause": t.sweep_pause}] if seats else []

    def _dealer_reveal(self, now: float) -> list:
        self.phase = "reveal"
        self.dealer_shown = True
        ev, _ = uth.best_hand(self.dealer_cards + self.board)
        qualified = ev[0] >= uth.ONE_PAIR
        self.deadline = now + self.timings.dealer_reveal
        line = self.lines.say("ultimate_texas_holdem", "qualifies" if qualified else "no_qualify", dealer=uth.hand_label(ev))
        return [{"kind": "dealer_reveal", "cards": [c.code for c in self.dealer_cards], "hand": uth.hand_label(ev),
                 "qualified": qualified}] + say(line)

    def _start_settling(self, now: float) -> list:
        self.phase = "settling"
        for h in self.round.values():
            h.result = uth.settle(h.cards, self.dealer_cards, self.board, h.bets, h.folded)
        self._settle_queue = [i for i in sorted(self.round, reverse=True) if not self.round[i].folded]
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
        name, hand = h.participant.name, uth.hand_label(r.player_eval)
        h.participant.credit(h.paid, r.outcome, returns_detail(self._stakes(h, r, pool), hand=hand))
        steps = self._steps(h, r, pool)
        t = self.timings
        self.deadline = now + t.settle_base + 2 * t.settle_pause + t.settle_step * len(steps)
        line = self.lines.say("ultimate_texas_holdem", r.outcome, name=name, hand=hand,
                              dealer=uth.hand_label(r.dealer_eval))
        events.append({"kind": "settle_seat", "seat": seat, "outcome": r.outcome, "cards": [c.code for c in h.cards],
                       "hand": hand, "qualified": r.dealer_qualified, "steps": steps, "total_returned": h.paid,
                       "say": line, "pause": t.settle_pause, "_paid": [h.participant]})
        return events

    @staticmethod
    def _stakes(h: Hand, r: uth.Result, pool: int) -> list:
        """(spot, stake, returned) for each bet; the flat Jackpot's return is its winnings."""
        return [("ante", h.bets.ante, r.ante_return), ("blind", h.bets.blind, r.blind_return),
                ("play", h.bets.play, r.play_return), ("trips", h.bets.trips, r.trips_return),
                ("jackpot", h.bets.jackpot, r.jackpot_fixed + pool)]

    @staticmethod
    def _steps(h: Hand, r: uth.Result, pool: int) -> list:
        steps = []
        for spot, bet, ret in UltimateTexasHoldemMachine._stakes(h, r, pool):
            if bet <= 0:
                continue
            if spot == "jackpot":
                steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret} if ret
                             else {"spot": spot, "action": "collect", "amount": bet})
            elif ret == 0:
                steps.append({"spot": spot, "action": "collect", "amount": bet})
            elif ret == bet:
                steps.append({"spot": spot, "action": "push", "amount": bet})
            else:
                steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret - bet})
        return sorted(steps, key=lambda s: s["action"] != "collect")

    def _box_private(self, seat: int) -> dict:
        h = self.round[seat]
        return {"cards": [c.code for c in h.cards], "hand": self._seen_label(h)}

    def _seen_label(self, h: Hand) -> str:
        seen = h.cards + self.board[:self.revealed]
        if len(seen) >= 5:
            return uth.hand_label(uth.best_hand(seen)[0])
        a, b = sorted((c.value for c in h.cards), reverse=True)
        if a == b:
            return uth.hand_label((uth.ONE_PAIR, "", (a,)))
        suited = " suited" if h.cards[0].suit == h.cards[1].suit else ""
        return f"{uth.NAMES.get(a, str(a))}-{uth.NAMES.get(b, str(b))}{suited}"

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.dealer_cards, self.board = [], []
        self.revealed = self.stage = 0
        self.dealer_shown = False
        self._settle_queue = []
        return self._reopen_betting(now)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        seats = []
        for i, s in enumerate(self.seats):
            if s.participant is None:
                seats.append(None)
                continue
            seats.append({**self._seat_entry(i, s), "cards": [], "hand": None, "folded": False, "decided": False,
                          "play": 0, "result": None})
        for i, h in self.round.items():
            entry = seats[i]
            if entry is None or entry["entity"] != h.participant.entity_id:
                continue
            entry["bets"] = {"ante": h.bets.ante, "blind": h.bets.blind, "trips": h.bets.trips, "jackpot": h.bets.jackpot}
            entry["play"], entry["folded"], entry["decided"] = h.bets.play, h.folded, h.decided or not h.waiting
            if h.swept:
                entry["bets"] = dict.fromkeys(SPOTS, 0)
            if h.settled:
                entry["cards"] = [c.code for c in h.cards]
                entry["result"] = {"outcome": h.result.outcome, "returned": h.paid}
            elif not h.swept:
                show = self._sees(viewer, i)
                entry["cards"] = [c.code if show else "??" for c in h.cards]
                entry["hand"] = self._seen_label(h) if show else None
        board = [c.code if k < self.revealed else "??" for k, c in enumerate(self.board)]
        dealer = [c.code if self.dealer_shown else "??" for c in self.dealer_cards]
        timer = self._timer(now, ("betting", "deciding"))
        return {"game": self.game, "phase": self.phase, "seats": seats, "community": board, "dealer": {"cards": dealer},
                "stage": self.stage, "timer": timer, "my_seat": viewer}
