"""
Craps table (Vegas rules): a timed state machine that runs a real table's flow.
Signed off on Mike's Craps mockup (v1).

  betting    The dice are in the middle and bets go down. An NPC shooter rolls
             when the window closes; a human shooter rolls when they're ready
             (Roll, or Space), within human_roll seconds, or the dice pass on.
  throwing   "Dice are out": no more bets. New chips are paid for now (one
             debit per seat, however many clicks); the dice are drawn and their
             path planned (engines/craps.plan_throw), and the dice fly.
  settling   The stickman calls it; the base dealers sweep the losers and pay
             the winners beside their bets; winnings (and come bets and odds,
             which come back with them) go to the players; come bets travel to
             their numbers; the puck turns over. Then betting opens again.

Unlike the card tables, bets stay on the layout from roll to roll. A seat's
`bets` are everything it has on the table; `locked` is what's already paid for.
Taking a paid-for bet down refunds it at once; chips put down since the last
throw are paid for at the next one. A lay bet's vig is paid with it (so what's
been paid for a seat is its locked bets plus cr.vig_up_front(locked)), and comes
back with it when it's taken down.

The shooter: anyone seated can shoot, NPCs included. After a seven-out the dice
move clockwise (seat 0, the right-hand end of the near rail, to seat 7). A
player who walks up can take the dice: at once if no point is on and an NPC has
them, otherwise when the point is decided. If the shooter leaves, the next
player takes the dice and the point.
"""
import random
from dataclasses import dataclass

from casino_server.dealer import DealerLines
from casino_server.engines import craps as cr
from casino_server.tables.base import CHIPS, TableError, TableMachine, say, stakes_detail

HISTORY = 12
INACTIVE_ROLLS = 40   # a human with nothing on the table for this many rolls is stood up


@dataclass
class Timings:
    betting: float = 7.0           # an NPC shooter's betting window: "Dice out in 7"
    betting_npc_only: float = 5.0
    bet_reset: float = 5.0         # a real player's chips going down with less than this left put it back to this
    human_roll: float = 20.0       # a human shooter's time to roll
    min_betting: float = 2.0       # bets are open at least this long
    rebet: float = 3.0             # (the base class's; there's no Rebet at craps)
    dice_out: float = 0.8          # the stickman pushes the dice to the shooter
    land_pause: float = 0.3
    call: float = 1.4
    sweep: float = 1.0
    pay_step: float = 0.32         # each winning seat in turn
    pay_pause: float = 0.6
    vig: float = 0.5               # longer when the dealer takes a vig off a payout
    back: float = 0.9              # winnings go back to the players
    move: float = 0.7              # come bets travel to their numbers
    fetch: float = 0.85            # the stickman brings the dice back

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


class CrapsMachine(TableMachine):
    game = cr.GAME_KEY
    label = cr.GAME_LABEL
    SPOTS = cr.SPOTS
    BREAKDOWN = False   # (the hardways and props that won are called out instead)
    BONUS_SPOTS = cr.HARDWAYS + cr.PROPS   # (the shooter's-hand summary's highlights)
    SPOT_NAMES = {"hard4": "Hard 4", "hard6": "Hard 6", "hard8": "Hard 8", "hard10": "Hard 10", "any7": "Any 7",
                  "two": "Aces", "three": "Ace-Deuce", "eleven": "Yo", "twelve": "Midnight", "ce": "C & E"}
    BETTING_PHASES = ("betting",)
    QUEUE_BETS = False

    def __init__(self, table_id: str, seats: int = 8, timings: Timings | None = None,
                 jackpot=None, deck_factory=None, lines: DealerLines | None = None, rng=None, dice=None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.rng = rng or random.SystemRandom()
        self.dice = dice                      # tests: a callable returning the next (d1, d2)
        self.point: int | None = None
        self.shooter: int | None = None
        self.want_dice: list[int] = []        # seats waiting to take the dice, in the order they asked
        self.locked = [{} for _ in range(seats)]
        self.working = [False] * seats
        self.idle_rolls = [0] * seats
        self.shoot_called = False
        self.roll: dict | None = None         # {dice, plan, at} while the dice are out
        self.rest: list | None = None         # where the dice lie after the last throw (until they're fetched)
        self.rolls_this_hand = 0
        # The shooter's-hand summary (shown as the next come-out opens): each player's worth -- balance and paid-for
        # bets on the layout -- when they first had chips riding this hand, and the hand's rolls and points made.
        self.hand_marks: dict = {}            # seat -> [participant, worth, played]
        self.hand_rolls = 0
        self.hand_points = 0
        self._pending_summary: dict | None = None
        # A table that's been running all day: the sign starts with twelve rolls.
        self.history = [[self.rng.randint(1, 6), self.rng.randint(1, 6)] for _ in range(HISTORY)]

    def rules(self) -> dict:
        return {**cr.rules(), "chips": CHIPS, "min_ante": cr.MIN_MAIN, "seats": len(self.seats)}

    def _bets_view(self, bets: dict) -> dict:
        return {spot: amount for spot, amount in bets.items() if amount}

    def _has_main(self, bets: dict) -> bool:
        return any(amount > 0 for amount in bets.values())

    def occupied(self) -> list[int]:
        return [i for i, s in enumerate(self.seats) if s.participant is not None]

    def is_human(self, seat: int | None) -> bool:
        return seat is not None and self.seats[seat].participant is not None and self.seats[seat].participant.is_human

    def next_shooter(self, after: int | None) -> int | None:
        start = -1 if after is None else after
        n = len(self.seats)
        for k in range(1, n + 1):
            seat = (start + k) % n
            if self.seats[seat].participant is not None:
                return seat
        return None

    def has_line_bet(self, seat: int) -> bool:
        b = self.seats[seat].bets
        return bool(b.get("pass") or b.get("dont_pass"))

    def contract_bets(self, seat: int) -> bool:
        """Bets that can't come down: they'd be left behind (and lost) if the seat got up."""
        return any(amount and not cr.removable(spot, self.point) for spot, amount in self.seats[seat].bets.items())

    # ------------------------------------------------------------------ seating
    def sit(self, seat: int, participant, now: float) -> list:
        events = super().sit(seat, participant, now)
        self.locked[seat] = {}
        self.working[seat] = False
        self.idle_rolls[seat] = 0
        if self.phase == "betting" and self.deadline is None:
            events += self._open_window(now)    # the first player at a quiet table starts it up
        return events

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        """Getting up: paid-for bets that can come down are refunded (only while bets are
        open -- once the dice are out, everything rides); contract bets stay with the house."""
        s = self.seats[seat]
        events = []
        if self.phase == "betting":
            down = {spot: min(s.bets.get(spot, 0), paid) for spot, paid in self.locked[seat].items()
                    if cr.removable(spot, self.point)}
            back = sum(down.values()) + cr.vig_up_front(down)
            if back:
                s.participant.refund(back, "taken down")
                events.append({"kind": "bets_back", "seat": seat, "amount": back, "_paid": [s.participant]})
        self.locked[seat] = {}
        self.working[seat] = False
        if seat in self.want_dice:
            self.want_dice.remove(seat)
        return events

    def _after_stand(self, seat: int, now: float) -> list:
        if seat != self.shooter:
            return []
        self.shooter = self.next_shooter(seat)
        if self.shooter is None:
            return []
        events = [{"kind": "shooter_change", "shooter": self.shooter, "reason": "left", "point": self.point}]
        events += say(self.lines.say("craps", "takes_dice", name=self._name(self.shooter),
                                     point=self.point or "") if self.point else
                      self.lines.say("craps", "new_shooter", name=self._name(self.shooter)))
        if self.phase == "betting":
            events += self._open_window(now)
        return events

    def stand(self, seat: int, now: float, reason: str = "") -> list:
        events = super().stand(seat, now, reason)
        if not self.occupied() and self.phase == "betting":
            self.deadline = None    # nobody left: the table goes quiet
            self.shooter = None
        return events

    def _name(self, seat: int | None) -> str:
        p = self.seats[seat].participant if seat is not None else None
        return p.name if p else ""

    # ------------------------------------------------------------------ betting
    def set_bets(self, seat: int, bets: dict, now: float) -> list:
        s = self.seats[seat]
        if s.participant is None:
            raise TableError("Sit down first.")
        if self.phase != "betting":
            raise TableError("The dice are out -- no more bets.")
        new = dict.fromkeys(self.SPOTS, 0)
        for spot, amount in bets.items():
            if spot not in self.SPOTS:
                raise TableError(f"There's no {spot} spot here.")
            try:
                new[spot] = int(amount)
            except (TypeError, ValueError):
                raise TableError("Bets are whole numbers of pence.")
            if new[spot] < 0:
                raise TableError("Bets can't be negative.")
        old = s.bets
        for spot in self.SPOTS:
            if new[spot] != old.get(spot, 0):
                err = cr.check(new, spot, old.get(spot, 0), new[spot], self.point)
                if err:
                    raise TableError(err)
        paid = self.locked[seat]
        kept = {spot: min(amount, new[spot]) for spot, amount in paid.items() if min(amount, new[spot])}
        vig_back = cr.vig_up_front(paid) - cr.vig_up_front(kept)
        refund = sum(max(0, amount - new[spot]) for spot, amount in paid.items()) + vig_back
        owed = (sum(max(0, new[spot] - paid.get(spot, 0)) for spot in self.SPOTS)
                + cr.vig_up_front(new) - cr.vig_up_front(kept))
        if owed > s.participant.balance + refund:
            raise TableError(self.CANT_COVER)
        events = [{"kind": "bet_changed", "seat": seat, "bets": self._bets_view(new)}]
        if refund:
            s.participant.refund(refund, "taken down")
            events[0]["_paid"] = [s.participant]
        if vig_back:
            events[0]["vig_back"] = vig_back
        self.locked[seat] = kept
        s.bets = new
        if s.participant.is_human and any(new[spot] > old.get(spot, 0) for spot in self.SPOTS):
            events += self._bet_reset(now)
        return events

    def _bet_reset(self, now: float) -> list:
        """A real player's bet going down late puts the dice-out countdown back up to
        `timings.bet_reset` seconds (an NPC shooter's window only: a human shooter rolls when ready)."""
        if (self.deadline is None or self.shoot_called or self.is_human(self.shooter)
                or self.deadline - now >= self.timings.bet_reset):
            return []
        self.deadline = now + self.timings.bet_reset
        return [{"kind": "betting_timer", "seconds": self.timings.bet_reset}]

    def clear_bets(self, seat: int, now: float) -> list:
        """Take down everything that can come down (contract bets stay)."""
        keep = {spot: a for spot, a in self.seats[seat].bets.items() if a and not cr.removable(spot, self.point)}
        return self.set_bets(seat, keep, now)

    def rebet(self, seat: int, now: float) -> list:
        raise TableError("Your bets stay on the table from roll to roll.")

    def set_auto_rebet(self, seat: int, on: bool, now: float) -> list:
        raise TableError("Your bets stay on the table from roll to roll.")

    def set_working(self, seat: int, on: bool, now: float) -> list:
        if self.seats[seat].participant is None:
            raise TableError("Sit down first.")
        self.working[seat] = bool(on)
        return [{"kind": "working", "seat": seat, "on": self.working[seat]}]

    # ------------------------------------------------------------------ the dice
    def ready(self, seat: int, now: float) -> list:
        """Space: the shooter rolls (there's no Ready otherwise)."""
        if seat == self.shooter:
            return self.shoot(seat, now)
        raise TableError("The shooter rolls when they're ready -- just get your bets down.")

    def shoot(self, seat: int, now: float) -> list:
        if seat != self.shooter:
            raise TableError("You're not the shooter.")
        if self.phase != "betting":
            raise TableError("The dice are already out.")
        if self.point is None and not self.has_line_bet(seat):
            raise TableError("The shooter needs a Pass Line or Don't Pass bet: put one down, then roll.")
        self.shoot_called = True
        self.deadline = max(now, self.betting_opened_at + self.timings.min_betting)
        return []

    def take_dice(self, seat: int, on: bool, now: float) -> list:
        if self.seats[seat].participant is None:
            raise TableError("Sit down first.")
        if not on:
            if seat in self.want_dice:
                self.want_dice.remove(seat)
            return [{"kind": "dice_queued", "seat": seat, "on": False}]
        if seat == self.shooter:
            return []
        if self.phase == "betting" and self.point is None and not self.is_human(self.shooter):
            self.shooter = seat
            events = [{"kind": "shooter_change", "shooter": seat, "reason": "taken", "point": None}]
            return events + say(self.lines.say("craps", "new_shooter", name=self._name(seat))) + self._open_window(now)
        if seat not in self.want_dice:
            self.want_dice.append(seat)
        return [{"kind": "dice_queued", "seat": seat, "on": True}]

    def pass_dice(self, seat: int, now: float, reason: str = "passed") -> list:
        if seat != self.shooter:
            raise TableError("You're not the shooter.")
        if self.phase != "betting":
            raise TableError("The dice are already out.")
        if seat in self.want_dice:
            self.want_dice.remove(seat)
        self.shooter = self.next_shooter(seat)
        events = [{"kind": "shooter_change", "shooter": self.shooter, "reason": reason, "point": self.point}]
        if self.shooter is not None:
            events += say(self.lines.say("craps", "new_shooter", name=self._name(self.shooter)))
        return events + self._open_window(now)

    def _open_window(self, now: float) -> list:
        """Bets are open: the dice are with the stickman until the shooter's ready."""
        self.phase = "betting"
        if not self.occupied():
            self.deadline = None    # an empty table waits for someone to step up (the puck off)
            self.shooter = None
            self.point = None
            self.rolls_this_hand = 0
            return []
        if self.shooter is None or self.seats[self.shooter].participant is None:
            self.shooter = self.next_shooter(self.shooter)
        events = []
        if self.point is None and not self.is_human(self.shooter):   # coming out: a player waiting gets the dice
            while self.want_dice and self.seats[self.want_dice[0]].participant is None:
                self.want_dice.pop(0)
            if self.want_dice:
                self.shooter = self.want_dice.pop(0)
                self.rolls_this_hand = 0
                events = [{"kind": "shooter_change", "shooter": self.shooter, "reason": "taken", "point": None}]
                events += say(self.lines.say("craps", "new_shooter", name=self._name(self.shooter)))
        human = self.is_human(self.shooter)
        length = self.timings.human_roll if human else (
            self.timings.betting if self.humans_seated() else self.timings.betting_npc_only)
        self.phase = "betting"
        self.betting_opened_at = now
        self.shoot_called = False
        self.deadline = now + length
        events.append({"kind": "roll_open", "shooter": self.shooter, "point": self.point, "seconds": length,
                       "human_shooter": human})
        if self._pending_summary:   # the come-out after a seven-out: how the last shooter's hand went
            events[-1]["summary"], self._pending_summary = self._pending_summary, None
        return events

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close(now)
        if self.phase == "throwing":
            return self._resolve(now)
        if self.phase == "settling":
            self.rest = None
            return self._open_window(now)
        return []

    def _close(self, now: float) -> list:
        """The window's up (or the shooter's ready): the dice go out -- if they can."""
        if not self.occupied():
            self.deadline = None
            return []
        shooter = self.shooter
        if shooter is None or self.seats[shooter].participant is None:
            return self._open_window(now)
        if self.is_human(shooter) and not self.shoot_called:
            return self.pass_dice(shooter, now, reason="timeout")    # they didn't roll in time
        if self.point is None and not self.has_line_bet(shooter):
            return self.pass_dice(shooter, now, reason="no_line_bet")
        return self._throw(now)

    def _throw(self, now: float) -> list:
        events, paid, vigs = [], [], {}
        for i in self.occupied():
            s = self.seats[i]
            mark = self.hand_marks.get(i)
            if mark is None or mark[0] is not s.participant:
                self.hand_marks[i] = mark = [s.participant, self._worth(i), False]
            vig = cr.vig_up_front(s.bets) - cr.vig_up_front(self.locked[i])
            owed = sum(max(0, a - self.locked[i].get(spot, 0)) for spot, a in s.bets.items()) + vig
            new = {spot: a - self.locked[i].get(spot, 0) for spot, a in s.bets.items()}
            detail = stakes_detail(new)
            if vig:
                detail["vig"] = vig
            if owed and not s.participant.debit(owed, "bets", detail):
                s.bets = {spot: min(a, self.locked[i].get(spot, 0)) for spot, a in s.bets.items()}   # new chips come back
                events.append({"kind": "bet_changed", "seat": i, "bets": self._bets_view(s.bets)})
            elif owed:
                paid.append(s.participant)
                if vig:   # the player hands the dealer each lay bet's vig with it
                    vigs[str(i)] = {spot: v for spot, a in s.bets.items() if spot.startswith("lay_") and
                                    (v := cr.vig_up_front({spot: a}) - cr.vig_up_front({spot: self.locked[i].get(spot, 0)}))}
            self.locked[i] = {spot: a for spot, a in s.bets.items() if a}
            mark[2] = mark[2] or bool(self.locked[i])
            if s.participant.is_human:
                self.idle_rolls[i] = 0 if self.locked[i] else self.idle_rolls[i] + 1
        for i in self.humans_seated():
            if self.idle_rolls[i] >= INACTIVE_ROLLS and i != self.shooter:
                events += self.stand(i, now, reason="inactive")
        d1, d2 = self.dice() if self.dice else (self.rng.randint(1, 6), self.rng.randint(1, 6))
        bets = {i: self.seats[i].bets for i in self.occupied()}
        chips = cr.chips_on_table(bets)
        payouts = [(x + cr.PAYOUT_AT[0], y + cr.PAYOUT_AT[1]) for x, y in chips]
        after = cr.advance_point(self.point, d1 + d2)[0]
        buttons = cr.off_buttons(bets, dict(enumerate(self.working)))
        plan = cr.plan_throw(self.shooter, (d1, d2), self.rng, chips, payouts, cr.pucks_at(self.point),
                             cr.puck_slide(self.point, after), buttons if self.point is None else [],
                             buttons if after is None else [])
        self.roll = {"dice": [d1, d2], "plan": plan, "at": now}
        self.phase = "throwing"
        self.deadline = now + self.timings.dice_out + cr.throw_seconds(plan) + self.timings.land_pause
        events.append({"kind": "throw", "shooter": self.shooter, "dice": [d1, d2], "plan": plan,
                       "out": self.timings.dice_out, "vig": vigs, "_paid": paid})
        return events + say(self.lines.say("craps", "dice_out"))

    def _resolve(self, now: float) -> list:
        d1, d2 = self.roll["dice"]
        total = d1 + d2
        before = self.point
        seats, after, paid = {}, {}, []
        losers = winners = moves = vigs = 0
        for i in self.occupied():
            s = self.seats[i]
            outcomes = cr.resolve(s.bets, d1, d2, before, self.working[i])
            if not outcomes:
                continue
            credit, steps, arriving = 0, [], []
            ledger = {}   # spot -> its stake and return, for the ledger
            bets = dict(s.bets)
            for spot, o in outcomes.items():
                stake = s.bets[spot]   # (as it was before this roll: see `arriving`)
                steps.append({"spot": spot, "kind": o.kind, "amount": stake, "win": o.win, "stays": o.stays,
                              "to": o.to, "vig": o.vig})
                if o.kind == "lose":
                    bets[spot] = 0
                    losers += 1
                    ledger[spot] = {"stake": stake, "returned": 0}
                elif o.kind == "win":
                    credit += o.win
                    vigs += o.vig > 0
                    ledger[spot] = {"stake": stake, "returned": o.win + (0 if o.stays else stake)}
                    if o.stays:
                        ledger[spot]["stays"] = True   # (paid, the stake left up)
                    else:
                        credit += stake
                        bets[spot] = 0
                    if o.vig:
                        ledger[spot]["vig"] = o.vig
                elif o.kind == "return":
                    credit += stake
                    bets[spot] = 0
                    ledger[spot] = {"stake": stake, "returned": stake}
                elif o.kind == "move":
                    bets[spot] = 0
                    arriving.append((o.to, stake))
                    moves += 1
            # A come bet travels to its number only once that number's own bets are decided:
            # a Come bet arriving on a 6 that's just won (and come off) takes its place, it
            # doesn't join it and come off with it.
            for to, stake in arriving:
                bets[to] = bets.get(to, 0) + stake
            if any(st["kind"] in ("win", "return") for st in steps):
                winners += 1
            if ledger:
                won = sum(o.win for o in outcomes.values())
                lost = sum(st["amount"] for st in steps if st["kind"] == "lose")
                self._credit(s.participant, credit, "win" if won > lost else "lose", {"spots": ledger})
                if credit:
                    paid.append(s.participant)
            s.bets = bets
            self.locked[i] = {spot: a for spot, a in bets.items() if a}
            seats[str(i)] = steps
            after[str(i)] = self._bets_view(bets)
        self.point, what = cr.advance_point(before, total)
        self.history = ([[d1, d2]] + self.history)[:HISTORY]
        self.rolls_this_hand += 1
        self.hand_rolls += 1
        self.hand_points += what == "point_made"
        self.rest = cr.resting(self.roll["plan"])
        self.roll = None
        old_shooter = self.shooter
        if what == "seven_out":
            self._pending_summary = self._hand_summary(old_shooter)
            self.shooter = self.next_shooter(self.shooter)
            self.rolls_this_hand = 0
        if what in ("point_made", "seven_out"):
            self._hand_dice_to_waiting(what, old_shooter)
        t = self.timings
        self.phase = "settling"
        self.deadline = now + (t.call + (t.sweep if losers else 0) + t.pay_step * winners + (t.pay_pause if winners else 0)
                               + (t.vig if vigs else 0)
                               + (t.back if winners else 0) + (t.move if moves else 0) + t.fetch)
        events = say(self._call(d1, d2, before, what))   # the call first: the client plays the payout after it
        events += [{"kind": "roll_result", "dice": [d1, d2], "total": total, "words": cr.call_words(d1, d2),
                   "was": before, "point": self.point, "what": what, "seats": seats, "after": after,
                   "shooter": self.shooter, "rolls": self.rolls_this_hand, "history": self.history,
                   "rest": self.rest, "_paid": paid}]
        if self.shooter != old_shooter and self.shooter is not None:
            events += say(self.lines.say("craps", "new_shooter", name=self._name(self.shooter)))
        return events

    def _worth(self, seat: int) -> int:
        """A player's balance and the paid-for bets they have on the layout."""
        return self.seats[seat].participant.balance + sum(self.locked[seat].values())

    def _hand_summary(self, shooter: int | None) -> dict | None:
        """A seven-out: the shooter's hand's summary (TableMachine._summary), each player's net the change in their
        worth since they joined it. Then the next hand starts afresh."""
        rows = []
        for i, (participant, worth, played) in self.hand_marks.items():
            if self.seats[i].participant is participant and played:
                rows.append({"seat": i, "participant": participant, "net": self._worth(i) - worth})
        rolls, points = self.hand_rolls, self.hand_points
        name = self._name(shooter)
        title = (f"{name}'s hand" if name else "Last hand") + \
            f" · {rolls} roll{'s' if rolls != 1 else ''} · {points} point{'s' if points != 1 else ''}"
        summary = self._summary(rows, title)
        self.hand_marks, self.round_book = {}, {}
        self.hand_rolls = self.hand_points = 0
        return summary

    def _hand_dice_to_waiting(self, what: str, old_shooter: int | None):
        """The point's decided: a player waiting for the dice gets them (from an NPC shooter
        at once; from a human, only once they seven out)."""
        while self.want_dice:
            seat = self.want_dice[0]
            if self.seats[seat].participant is None:
                self.want_dice.pop(0)
                continue
            if what == "seven_out" or not self.is_human(old_shooter):
                self.want_dice.pop(0)
                self.shooter = seat
                self.rolls_this_hand = 0
            return

    def _call(self, d1: int, d2: int, before: int | None, what: str) -> str:
        """The stickman's call: from dealer_lines.toml ([craps]), else a plain one."""
        total = d1 + d2
        words = cr.call_words(d1, d2)
        key = {"natural": "seven_winner" if total == 7 else "yo_winner", "point_set": "point_set",
               "point_made": "point_made", "seven_out": "seven_out"}.get(what)
        if what == "craps":
            key = "twelve_craps" if total == 12 else "craps_line_away"
        if what == "roll":
            key = "yo" if total == 11 else "craps_roll" if total in (2, 3, 12) else "roll"
        line = self.lines.say("craps", key, call=words, total=total, point=before or total) if key else ""
        if line:
            return line
        return {"natural": f"{words}, winner on the line!", "point_set": f"{words}. The point is {total}.",
                "point_made": f"{words}! Winner, pay the line.", "seven_out": "Seven out, line away!",
                "craps": f"{words}, craps!"}.get(what, f"{words}.")

    # ------------------------------------------------------------------ snapshot
    def _seat_entry(self, i: int, s) -> dict:
        return {**super()._seat_entry(i, s), "locked": dict(self.locked[i]), "working": self.working[i]}

    def snapshot(self, viewer: int | None, now: float) -> dict:
        seats = [self._seat_entry(i, s) if s.participant is not None else None for i, s in enumerate(self.seats)]
        throw = None
        if self.phase == "throwing" and self.roll is not None:
            throw = {"dice": self.roll["dice"], "plan": self.roll["plan"], "out": self.timings.dice_out,
                     "elapsed": round(now - self.roll["at"], 3)}
        return {"game": self.game, "phase": self.phase, "seats": seats, "point": self.point, "shooter": self.shooter,
                "want_dice": list(self.want_dice), "history": self.history, "rolls": self.rolls_this_hand,
                "human_shooter": self.is_human(self.shooter), "throw": throw, "rest": self.rest,
                "timer": self._timer(now), "my_seat": viewer}
