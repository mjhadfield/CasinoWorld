"""
Mississippi Stud table: a timed state machine that runs a real table's flow.

  betting   Ante, 3 Card Bonus and the £1 Jackpot. Countdown from the first
            bet; closes early once every human is Ready. The Jackpot lights
            lock in as at the other tables.
  dealing   Two cards to each seat in turn from first base (private), then
            three community cards face down in front of the dealer.
  deciding  3rd Street: everyone still in decides at once -- fold, or bet
            1x, 2x or 3x the Ante -- against one timer that ends early once
            the whole table has decided; anyone still undecided folds.
  sweeping  The dealer takes this street's folded hands: their Ante and
            street bets, and their Jackpot. A 3 Card Bonus stays in action.
  revealing The dealer turns the next community card. Then 4th Street and
            5th Street the same way (deciding, sweeping, revealing). If
            everyone has folded, the rest are turned at once for the Bonus.
  settling  First every folded hand's 3 Card Bonus, all at once (they ride
            on the same community cards). Then each seat still in, third base
            back to first: cards turned over, losing bets swept, every winning
            bet paid the same multiplier beside its stake. If everyone folded
            and nobody has a Bonus riding, the hand simply ends.
  clearing  Chips back to the players, cards to the rack, betting opens.

Seating, betting, Ready and the clock are shared with every table (base.py).
"""
from dataclasses import dataclass, field

from casino_server.dealer import DealerLines
from casino_server.engines import mississippi_stud as ms
from casino_server.engines.cards import Deck
from casino_server.tables.base import CHIPS, TableError, TableMachine, returns_detail, say, stakes_detail

SPOTS = ("ante", "bonus", "jackpot")
ACTIONS = {"fold": 0, "bet1": 1, "bet2": 2, "bet3": 3}
STREET_NAMES = ("3rd Street", "4th Street", "5th Street")


@dataclass
class Timings:
    betting: float = 15.0
    betting_npc_only: float = 5.0
    min_betting: float = 3.0
    rebet: float = 3.0
    decide: float = 20.0          # each street, everyone at once
    deal_card: float = 0.09       # between the two cards of one hand (a packet)
    deal_hand_pause: float = 0.5  # between hands out of the shuffler
    deal_pause: float = 0.8       # after the last card, community cards included
    jackpot_lock: float = 1.6
    last_decision: float = 0.8
    sweep_pause: float = 1.0
    sweep_each: float = 0.5
    reveal: float = 1.4           # the dealer turns a community card
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
    """A seat's stake in the round -- kept if they stand, so a hand already
    played still settles."""
    participant: object
    bets: ms.Bets
    cards: list
    folded: bool = False
    folded_at: int | None = None   # street index
    decided: bool = False          # this street
    swept: bool = False
    settled: bool = False
    raised_3x: bool = False
    result: ms.Result | None = None
    paid: int = 0                  # what settling returned


class MississippiStudMachine(TableMachine):
    game = ms.GAME_KEY
    label = ms.GAME_LABEL
    SPOTS = SPOTS
    MAIN_SPOT = "ante"
    LIMITED = True
    FLAT_SPOTS = {"jackpot": ms.JACKPOT_BET}
    NEEDS_MAIN = "Side bets need an Ante alongside them."
    CANT_COVER = "Not enough balance: you need ten times your Ante (to bet 3x on every street), plus side bets."
    CANT_COVER_BOTH = "Not enough balance: you need ten times your Ante, plus side bets, on both boxes."
    SECOND_BOX = True

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=Deck, lines: DealerLines | None = None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.deck_factory = deck_factory
        self.round: dict[int, Hand] = {}
        self.community: list = []
        self.revealed = 0     # community cards face up
        self.street = 0       # 0, 1, 2: 3rd, 4th, 5th Street
        self._settle_queue: list[int] = []

    def rules(self) -> dict:
        return {**ms.rules(), "chips": CHIPS, "min_ante": CHIPS[0], "seats": len(self.seats)}

    def max_cost(self, bets: dict) -> int:
        return bets["ante"] * 10 + bets["bonus"] + bets["jackpot"]

    def live(self) -> list[int]:
        return [i for i, h in sorted(self.round.items()) if not h.folded]

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        h = self.round.get(seat)
        if h is not None and h.participant is self.seats[seat].participant and not h.folded \
                and self.phase in ("dealing", "deciding", "sweeping", "revealing"):
            return self._fold(seat, now, reason="left")
        return []

    # ------------------------------------------------------------------ deciding
    def play_action(self, seat: int, action: str, now: float) -> list:
        if self.phase != "deciding":
            raise TableError("It's not time to decide.")
        h = self.round.get(seat)
        if h is None or h.participant is not self.seats[seat].participant or h.folded:
            raise TableError("You're not in this hand.")
        if h.decided:
            raise TableError("You've already decided this street.")
        self._box_first(seat)
        if action not in ACTIONS:
            raise TableError("Fold, or bet 1x, 2x or 3x your Ante.")
        times = ACTIONS[action]
        if times == 0:
            return self._fold(seat, now)
        amount = h.bets.ante * times
        if not h.participant.debit(amount, STREET_NAMES[self.street], stakes_detail({ms.STREETS[self.street]: amount})):
            return self._fold(seat, now, reason="funds")
        h.bets.streets[self.street] = amount
        h.decided = True
        h.raised_3x = h.raised_3x or times == 3
        event = {"kind": "street_bet", "seat": seat, "street": self.street, "times": times, "amount": amount,
                 "_paid": [h.participant]}
        return [event] + self._all_decided(now)

    def _fold(self, seat: int, now: float, reason: str = "") -> list:
        h = self.round[seat]
        h.decided, h.folded, h.folded_at = True, True, self.street
        event = {"kind": "street_bet", "seat": seat, "street": self.street, "times": 0}
        if reason:
            event["reason"] = reason
        return [event] + self._all_decided(now)

    def _all_decided(self, now: float) -> list:
        if self.phase == "deciding" and all(h.decided for h in self.round.values() if not h.folded):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return self._reveal_boxes()

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            return self._open_street(now)
        if self.phase == "deciding":
            events = []
            for seat in self.live():  # out of time: anyone undecided folds
                if not self.round[seat].decided:
                    events += self._timed_out(seat) + self._fold(seat, now, reason="timeout")
            return events + self._sweep_folds(now)
        if self.phase == "sweeping":
            if not self.live():  # everyone's folded
                return self._everyone_folded(now)
            return self._reveal(now)
        if self.phase == "revealing":
            if self.revealed < 3:
                self.street += 1
                return self._open_street(now)
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
        self.round = {i: Hand(self.seats[i].participant, ms.Bets(bets["ante"], bets["bonus"], bets["jackpot"]),
                              deck.deal(2)) for i, bets in sorted(taken.items())}
        self.community = deck.deal(3)
        self.revealed, self.street = 0, 0
        self.phase = "dealing"
        order = [[who, c] for who in sorted(self.round) for c in range(2)] + [["community", c] for c in range(3)]
        jackpots = [i for i in sorted(taken) if taken[i]["jackpot"]]
        t = self.timings
        duration = len(order) * t.deal_card + len(self.round) * t.deal_hand_pause + t.deal_pause
        if jackpots:
            duration += t.jackpot_lock
        self.deadline = now + duration
        events.append({"kind": "bets_closed", "seats": sorted(taken), "jackpots": jackpots,
                       "_paid": [self.seats[i].participant for i in sorted(taken)]})
        events.append({"kind": "dealt", "order": order, "interval": t.deal_card, "hand_pause": t.deal_hand_pause,
                       "_private": {i: {"cards": [c.code for c in h.cards], "hand": self._seen_label(h)}
                                    for i, h in self.round.items()}})
        return events

    def _everyone_folded(self, now: float) -> list:
        """Nobody's left in: turn every remaining community card at once for the
        Bonus bets riding on them -- or, with none, just end the hand."""
        if not any(h.bets.bonus for h in self.round.values()):
            return self._start_settling(now)
        return self._reveal(now, all_remaining=True)

    def _open_street(self, now: float) -> list:
        live = self.live()
        if not live:
            return self._everyone_folded(now)
        for i in live:
            self.round[i].decided = False
        self.phase = "deciding"
        self.deadline = now + self.timings.decide
        events = [{"kind": "decisions_open", "street": self.street, "seconds": self.timings.decide, "seats": live,
                   "_private": {i: {"hand": self._seen_label(self.round[i])} for i in live}}]
        return events + say(self.lines.say("mississippi_stud", "street", street=STREET_NAMES[self.street]))

    def _sweep_folds(self, now: float) -> list:
        """The dealer takes this street's folds: Ante, street bets and Jackpot (a Bonus stays)."""
        self.phase = "sweeping"
        seats = []
        for seat in sorted(self.round, reverse=True):
            h = self.round[seat]
            if not h.folded or h.swept:
                continue
            h.swept = True
            spots = [("ante", h.bets.ante), ("jackpot", h.bets.jackpot)] + \
                [(ms.STREETS[k], h.bets.streets[k]) for k in range(3)]
            seats.append({"seat": seat, "steps": [{"spot": s, "amount": a} for s, a in spots if a > 0]})
        t = self.timings
        self.deadline = now + ((t.sweep_pause + t.sweep_each) * len(seats) + 0.4 * t.sweep_each if seats else 0.0)
        return [{"kind": "fold_sweep", "seats": seats, "pause": t.sweep_pause}] if seats else []

    def _reveal(self, now: float, all_remaining: bool = False) -> list:
        """The dealer turns the next community card (or all that are left)."""
        self.phase = "revealing"
        first = self.revealed
        self.revealed = 3 if all_remaining else self.revealed + 1
        cards = [c.code for c in self.community[first:self.revealed]]
        self.deadline = now + self.timings.reveal
        if all_remaining:
            self.street = 2
        return [{"kind": "community", "from": first, "cards": cards,
                 "_private": {i: {"hand": self._seen_label(h)} for i, h in self.round.items() if not h.folded}}]

    def _start_settling(self, now: float) -> list:
        self.phase = "settling"
        for h in self.round.values():
            h.result = ms.settle(h.cards, self.community, h.bets, h.folded)
        self._settle_queue = [i for i in sorted(self.round, reverse=True) if not self.round[i].folded]
        return self._settle_folded_bonuses(now) or self._settle_next(now)

    def _settle_folded_bonuses(self, now: float) -> list:
        """The folded hands' 3 Card Bonus bets all ride on the same three community
        cards, so the dealer settles them together: one announcement, one sweep or payout each."""
        seats = [i for i in sorted(self.round, reverse=True) if self.round[i].folded and self.round[i].bets.bonus]
        if not seats:
            return []
        entries, paid = [], []
        for seat in seats:
            h = self.round[seat]
            h.settled = True
            h.paid = h.result.bonus_return
            h.participant.credit(h.paid, "bonus", returns_detail(
                self._stakes(h, h.result, 0), bonus_hand=ms.bonus_label(h.result.bonus_eval) if h.result.bonus_eval else None))
            entries.append({"seat": seat, "steps": self._steps(h, h.result, 0), "total_returned": h.paid})
            paid.append(h.participant)
        bonus_eval = ms.evaluate_three_card_hand(self.community)
        wins = ms.bonus_multiplier(bonus_eval) > 0
        t = self.timings
        self.deadline = now + t.settle_pause + t.settle_step * 2
        line = self.lines.say("mississippi_stud", "bonus_all_win" if wins else "bonus_all_lose", bonus=ms.bonus_label(bonus_eval))
        return [{"kind": "bonus_settle", "seats": entries, "bonus_hand": ms.bonus_label(bonus_eval), "say": line,
                 "pause": t.settle_pause, "_paid": paid}]

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
        jackpot_pool = 0
        if r.jackpot_share and self.jackpot:
            jackpot_pool = self.jackpot.win() if r.jackpot_share >= 1.0 else self.jackpot.take(r.jackpot_share)
            events.append({"kind": "jackpot_won", "seat": seat, "amount": jackpot_pool, "name": h.participant.name})
        h.paid = r.total_returned + jackpot_pool
        h.participant.credit(h.paid, r.outcome, returns_detail(
            self._stakes(h, r, jackpot_pool), hand=ms.hand_label(r.final_eval) if r.final_eval else None,
            bonus_hand=ms.bonus_label(r.bonus_eval) if r.bonus_eval else None))
        steps = self._steps(h, r, jackpot_pool)
        t = self.timings
        self.deadline = now + t.settle_base + 2 * t.settle_pause + t.settle_step * len(steps)
        event = {"kind": "settle_seat", "seat": seat, "outcome": r.outcome, "multiplier": r.multiplier,
                 "cards": [] if h.folded else [c.code for c in h.cards],
                 "hand": ms.hand_label(r.final_eval) if r.final_eval else None,
                 "bonus_hand": ms.bonus_label(r.bonus_eval) if r.bonus_eval else None,
                 "steps": steps, "total_returned": h.paid, "pause": t.settle_pause, "_paid": [h.participant]}
        event["say"] = self._settle_line(h, r)
        return events + [event]

    @staticmethod
    def _stakes(h: Hand, r: ms.Result, jackpot_pool: int) -> list:
        """(spot, stake, returned) for each bet settled: a fold has only its Bonus left. The flat
        Jackpot's return is its winnings."""
        stakes = [("bonus", h.bets.bonus, r.bonus_return)]
        if not h.folded:
            stakes = [("ante", h.bets.ante, r.ante_return)] + \
                [(ms.STREETS[k], h.bets.streets[k], r.street_returns[k]) for k in range(3)] + stakes + \
                [("jackpot", h.bets.jackpot, r.jackpot_fixed + jackpot_pool)]
        return stakes

    @staticmethod
    def _steps(h: Hand, r: ms.Result, jackpot_pool: int) -> list:
        """Losing bets collected first, then pushes and winners paid."""
        steps = []
        for spot, bet, ret in MississippiStudMachine._stakes(h, r, jackpot_pool):
            if bet <= 0:
                continue
            if spot == "jackpot":  # a flat £1: the stake is gone either way, winnings are paid beside the light
                steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret} if ret
                             else {"spot": spot, "action": "collect", "amount": bet})
            elif ret == 0:
                steps.append({"spot": spot, "action": "collect", "amount": bet})
            elif ret == bet:
                steps.append({"spot": spot, "action": "push", "amount": bet})
            else:
                steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret - bet})
        return sorted(steps, key=lambda s: s["action"] != "collect")

    def _settle_line(self, h: Hand, r: ms.Result) -> str:
        name = h.participant.name
        hand = ms.hand_label(r.final_eval)
        if r.outcome == "win":
            return self.lines.say("mississippi_stud", "win", name=name, hand=hand, pays=f"{r.multiplier} to 1")
        return self.lines.say("mississippi_stud", r.outcome, name=name, hand=hand)

    def _box_private(self, seat: int) -> dict:
        h = self.round[seat]
        return {"cards": [c.code for c in h.cards], "hand": self._seen_label(h)}

    def _seen_label(self, h: Hand) -> str:
        """What a player's cards make so far (shown to them alone)."""
        seen = h.cards + self.community[:self.revealed]
        if len(seen) == 5:
            return ms.hand_label(ms.evaluate_five_card_hand(seen))
        values = sorted((c.value for c in seen), reverse=True)
        pairs = sorted({v for v in values if values.count(v) >= 2}, reverse=True)
        names = {14: "Aces", 13: "Kings", 12: "Queens", 11: "Jacks"}
        if any(values.count(v) >= 3 for v in values):
            return "Three of a Kind"
        if len(pairs) == 2:
            return "Two Pair"
        if pairs:
            return f"Pair of {names.get(pairs[0], str(pairs[0]) + 's')}"
        high = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}.get(values[0], str(values[0]))
        return f"{high} high"

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.community = []
        self.revealed = self.street = 0
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
                          "streets": [0, 0, 0], "result": None})
        for i, h in self.round.items():
            entry = seats[i]
            if entry is None or entry["entity"] != h.participant.entity_id:
                continue
            entry["bets"] = {"ante": h.bets.ante, "bonus": h.bets.bonus, "jackpot": h.bets.jackpot}
            entry["streets"] = list(h.bets.streets)
            entry["folded"], entry["decided"] = h.folded, h.decided
            if h.swept:
                entry["bets"] = {"ante": 0, "bonus": h.bets.bonus, "jackpot": 0}
                entry["streets"] = [0, 0, 0]
            if h.settled:
                entry["cards"] = [] if h.folded else [c.code for c in h.cards]
                entry["result"] = {"outcome": h.result.outcome, "returned": h.paid}
            elif not h.swept:
                show = self._sees(viewer, i)
                entry["cards"] = [c.code if show else "??" for c in h.cards]
                entry["hand"] = self._seen_label(h) if show else None
        community = [c.code if k < self.revealed else "??" for k, c in enumerate(self.community)]
        timer = self._timer(now, ("betting", "deciding"))
        return {"game": self.game, "phase": self.phase, "seats": seats, "community": community,
                "street": self.street, "timer": timer, "my_seat": viewer}
