"""
What every table game shares: seats, betting, Ready, sitting out, and the
clock. A game's machine (three_card_poker.py, blackjack.py) subclasses
TableMachine and adds its own round flow.

The machine is pure and synchronous: every method takes `now` (seconds) and
returns a list of events describing what happened, and tick(now) advances
anything that's due by calling the game's _advance(now). The TableRunner
(runner.py) supplies the clock, publishes the events, and wakes up at
next_deadline. Tests drive machines directly.

Events are dicts with a "kind". Anything only one seat may see sits under
"_private": {seat: {...}}; "_paid" lists the participants whose money the
event moved. The runner keeps "_" keys server-side.

Seats are numbered from first base (the dealer's left, the player's right on
screen).
"""
from dataclasses import dataclass, field

CHIPS = [100, 500, 2_500, 10_000, 50_000]  # Casino v2's £1/£5/£25/£100/£500
INACTIVE_ROUNDS = 3  # a human who sits out this many dealt rounds in a row is stood up...
INACTIVE_MAX_FREE = 1  # ...but only once the table has this many open seats or fewer


class TableError(Exception):
    """A rejected action; the message is shown to the player."""


@dataclass
class Seat:
    participant: object = None
    bets: dict = field(default_factory=dict)
    ready: bool = False
    last_bets: dict | None = None
    sat_out: int = 0
    queued: dict | None = None   # bets for the next hand, put down while this one plays without you
    queued_rebet: bool = False   # ...by Rebet, so they cut the countdown short when they go on
    auto_rebet: bool = False     # last hand's bets go back down by themselves as each hand ends


def say(text: str) -> list:
    """A dealer line as an event list (empty if there's nothing to say)."""
    return [{"kind": "say", "text": text}] if text else []


class TableMachine:
    game = ""
    label = ""
    SPOTS: tuple = ()
    MAIN_SPOT = ""                  # the bet that has to be down to play a hand
    FLAT_SPOTS: dict = {}           # spot -> the one amount it can be (e.g. a £1 Jackpot)
    NEEDS_MAIN = "Side bets need a main bet alongside them."
    CANT_COVER = "Not enough balance for that."
    BETTING_PHASES = ("betting",)   # when bets can be placed (Roulette also takes them as the ball spins)
    QUEUE_BETS = True               # out of the hand being played, bets go down for the next one (not at Roulette)

    def __init__(self, table_id: str, seats: int, timings, jackpot, lines):
        self.table_id = table_id
        self.timings = timings
        self.jackpot = jackpot
        self.lines = lines
        self.seats = [self._empty_seat() for _ in range(seats)]
        self.phase = "betting"
        self.deadline: float | None = None  # when the current phase/step is due
        self.betting_opened_at = 0.0
        self.round_start: dict = {}   # seat -> (participant, their balance before this hand's bets)

    def _empty_seat(self, participant=None) -> Seat:
        return Seat(participant=participant, bets=dict.fromkeys(self.SPOTS, 0))

    def _clear_seat_bets(self, s: Seat):
        s.bets = dict.fromkeys(self.SPOTS, 0)
        s.ready = False

    # ------------------------------------------------------------------ queries
    def round_net(self, seat: int) -> int | None:
        """What this hand has won (+) or lost (-) the seat's player so far; None if they're not in it."""
        entry = self.round_start.get(seat)
        if entry is None or self.seats[seat].participant is not entry[0]:
            return None
        return entry[0].balance - entry[1]

    @property
    def next_deadline(self) -> float | None:
        return self.deadline

    def seat_of(self, participant) -> int | None:
        for i, s in enumerate(self.seats):
            if s.participant is participant:
                return i
        return None

    def free_seats(self) -> list[int]:
        return [i for i, s in enumerate(self.seats) if s.participant is None]

    def humans_seated(self) -> list[int]:
        return [i for i, s in enumerate(self.seats) if s.participant is not None and s.participant.is_human]

    # ------------------------------------------------------------------ seating
    def sit(self, seat: int, participant, now: float) -> list:
        if not 0 <= seat < len(self.seats):
            raise TableError("There's no such seat.")
        if self.seats[seat].participant is not None:
            raise TableError("That seat's taken.")
        if self.seat_of(participant) is not None:
            raise TableError("You're already sitting here.")
        self.seats[seat] = self._empty_seat(participant)
        return [{"kind": "seated", "seat": seat, "entity": participant.entity_id, "name": participant.name,
                 "human": participant.is_human}]

    def stand(self, seat: int, now: float, reason: str = "") -> list:
        s = self.seats[seat]
        if s.participant is None:
            return []
        events = self._leaving_mid_hand(seat, now, reason)
        events.append({"kind": "stood", "seat": seat, "entity": s.participant.entity_id, "reason": reason})
        self.seats[seat] = self._empty_seat()
        if self.phase == "betting":
            events += self._maybe_close_early(now)
        return events + self._after_stand(seat, now)

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        """A player is getting up: the game decides what happens to a hand in progress."""
        return []

    def _after_stand(self, seat: int, now: float) -> list:
        return []

    # ------------------------------------------------------------------ betting
    def max_cost(self, bets: dict) -> int:
        """The most these bets could cost this round (Three Card Poker adds a Play bet)."""
        return sum(bets.values())

    def upfront(self, bets: dict) -> int:
        """What's taken when betting closes."""
        return sum(bets.values())

    def _validate_bets(self, bets: dict):
        """Game-specific rules; raise TableError to reject."""

    def _has_main(self, bets: dict) -> bool:
        """Whether these bets include the one a hand needs (Baccarat: any of Player, Banker, Tie)."""
        return bets.get(self.MAIN_SPOT, 0) > 0

    def _bets_view(self, bets: dict) -> dict:
        """Bets as events and snapshots carry them (Roulette sends only the spots in use)."""
        return dict(bets)

    def _in_round(self, seat: int) -> bool:
        """Whether this seat's player is in the hand being played (every machine keeps `round`)."""
        entry = getattr(self, "round", {}).get(seat)
        return entry is not None and getattr(entry, "participant", None) is self.seats[seat].participant

    def _bet_slot(self, seat: int) -> tuple[Seat, bool]:
        """Where a seat's bets go now: (the seat, True if they're queued for the next hand).
        While a hand is being played, anyone not in it can put their bets down for the next."""
        s = self.seats[seat]
        if s.participant is None:
            raise TableError("Sit down first.")
        if self.phase in self.BETTING_PHASES:
            if s.ready:
                raise TableError("You're marked Ready -- your bets are locked in.")
            return s, False
        if not self.QUEUE_BETS or self._in_round(seat):
            raise TableError("Bets are closed -- wait for the next hand.")
        return s, True

    def working_bets(self, seat: int) -> dict:
        """The bets a seat is placing now: this hand's, or (out of it) the next hand's."""
        s, queued = self._bet_slot(seat)
        return dict(s.queued or {}) if queued else dict(s.bets)

    def _betting_seat(self, seat: int) -> Seat:
        if self.phase not in self.BETTING_PHASES:
            raise TableError("Bets are closed -- wait for the next hand.")
        s = self.seats[seat]
        if s.participant is None:
            raise TableError("Sit down first.")
        if s.ready:
            raise TableError("You're marked Ready -- your bets are locked in.")
        return s

    def set_bets(self, seat: int, bets: dict, now: float) -> list:
        """Replace a seat's whole set of bets (spot -> pence) -- for the next hand, if one's
        being played without this seat."""
        s, queued = self._bet_slot(seat)
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
        for spot, flat in self.FLAT_SPOTS.items():
            if new[spot] not in (0, flat):
                raise TableError(f"The {spot.replace('_', ' ').title()} bet is exactly £{flat // 100}.")
        self._validate_bets(new)
        if self.max_cost(new) > s.participant.balance:
            raise TableError(self.CANT_COVER)
        if queued:
            s.queued = new if any(new.values()) else None
            s.queued_rebet = s.queued_rebet and s.queued is not None
            return [{"kind": "bet_changed", "seat": seat, "bets": self._bets_view(new), "queued": True}]
        first_bet = not any(any(x.bets.values()) for x in self.seats)
        s.bets = new
        events = [{"kind": "bet_changed", "seat": seat, "bets": self._bets_view(new)}]
        if first_bet and any(new.values()) and self.deadline is None:
            only_npcs = not self.humans_seated()
            length = self.timings.betting_npc_only if only_npcs else self.timings.betting
            self.deadline = now + length
            events.append({"kind": "betting_timer", "seconds": length})
        return events

    def set_bet(self, seat: int, spot: str, amount: int, now: float) -> list:
        return self.set_bets(seat, {**self.working_bets(seat), spot: amount}, now)

    def clear_bets(self, seat: int, now: float) -> list:
        return self.set_bets(seat, {}, now)

    def rebet(self, seat: int, now: float) -> list:
        """Last hand's bets again -- and betting closes in `timings.rebet` seconds (quietly),
        unless it's due sooner. Out of the hand being played, they go down for the next one."""
        s, queued = self._bet_slot(seat)
        if not s.last_bets:
            raise TableError("No previous bets to repeat.")
        events = self.set_bets(seat, s.last_bets, now)
        if queued:
            s.queued_rebet = True
            return events
        return self._rush_betting([e for e in events if e["kind"] != "betting_timer"], now)

    def _rush_betting(self, events: list, now: float) -> list:
        """A Rebet cuts the betting countdown to `timings.rebet` seconds, with no ticking
        (NPCs at the table get their bets down in time -- npc.py)."""
        if self.phase != "betting":   # Roulette's late bets: the ball's already spinning
            return events
        close_at = now + self.timings.rebet
        if self.deadline is not None and self.deadline <= close_at:
            return events
        self.deadline = close_at
        return events + [{"kind": "betting_timer", "seconds": self.timings.rebet, "quiet": True}]

    def set_auto_rebet(self, seat: int, on: bool, now: float) -> list:
        """Auto rebet: as each hand ends, last hand's bets go back down (a Rebet). Ticked in
        the betting window with nothing down yet, it rebets straight away."""
        s = self.seats[seat]
        if s.participant is None:
            raise TableError("Sit down first.")
        s.auto_rebet = bool(on)
        events = [{"kind": "auto_rebet", "seat": seat, "on": s.auto_rebet}]
        if (s.auto_rebet and s.last_bets and self.phase == "betting" and not s.ready
                and not any(s.bets.values())):
            try:
                events += self.rebet(seat, now)
            except TableError as e:
                events += self._auto_rebet_off(seat, str(e))
        return events

    def _auto_rebet_off(self, seat: int, reason: str) -> list:
        s = self.seats[seat]
        if not s.auto_rebet:
            return []
        s.auto_rebet = False
        return [{"kind": "auto_rebet", "seat": seat, "on": False, "reason": reason}]

    def _timed_out(self, seat: int) -> list:
        """A player in this hand ran out of time on a decision: Auto rebet goes off, so
        nobody who's walked away keeps playing."""
        if not self._in_round(seat):
            return []
        return self._auto_rebet_off(seat, "timeout")

    def ready(self, seat: int, now: float) -> list:
        s = self._betting_seat(seat)
        if any(s.bets.values()) and not self._has_main(s.bets):
            raise TableError(self.NEEDS_MAIN)
        s.ready = True
        return [{"kind": "ready", "seat": seat}] + self._maybe_close_early(now)

    def _maybe_close_early(self, now: float) -> list:
        """Every human Ready (and someone's actually betting) -> close soon."""
        humans = self.humans_seated()
        if not humans or not all(self.seats[i].ready for i in humans):
            return []
        if not any(self._has_main(s.bets) for s in self.seats if s.participant):
            return []
        close_at = max(now, self.betting_opened_at + self.timings.min_betting)
        if self.deadline is None or close_at < self.deadline:
            self.deadline = close_at
        return []

    def _take_bets(self, now: float) -> tuple[list, dict]:
        """Betting closes: take each playing seat's upfront bets. Seats with no
        main bet (or that can't cover it) are cleared; humans sitting out a hand
        that's going ahead are counted, and stood up after INACTIVE_ROUNDS -- but
        only while INACTIVE_MAX_FREE or fewer seats are open, so nobody's moved on
        from a quiet table. The count keeps going, so they go once it fills up.
        Returns (events, {seat: bets dict}) -- an empty dict if nobody's playing."""
        events = []
        playing = {}
        self.round_start = {}
        for i, s in enumerate(self.seats):
            if s.participant is None:
                continue
            before = s.participant.balance
            if not self._has_main(s.bets) or not s.participant.debit(self.upfront(s.bets), "upfront"):
                if any(s.bets.values()):  # side bets without a main bet go back
                    events.append({"kind": "bet_changed", "seat": i, "bets": self._bets_view(dict.fromkeys(self.SPOTS, 0))})
                self._clear_seat_bets(s)
                continue
            playing[i] = dict(s.bets)
            self.round_start[i] = (s.participant, before)
        if not playing:
            self.deadline = None  # nobody bet -- stay open until someone does
            return events + [{"kind": "betting_reset"}], {}
        for i in self.humans_seated():
            if i not in playing:
                self.seats[i].sat_out += 1
                if self.seats[i].sat_out >= INACTIVE_ROUNDS and len(self.free_seats()) <= INACTIVE_MAX_FREE:
                    events += self.stand(i, now, reason="inactive")
            else:
                self.seats[i].sat_out = 0
        for i, bets in playing.items():
            self.seats[i].last_bets = dict(bets)
        return events, playing

    def _reopen_betting(self, now: float) -> list:
        self.phase = "betting"
        self.betting_opened_at = now
        self.deadline = None
        for s in self.seats:
            self._clear_seat_bets(s)
        events = [{"kind": "betting_open"}]
        for i, s in enumerate(self.seats):  # bets put down during the last hand go on now
            if s.participant is None:
                continue
            if s.queued:
                bets, s.queued = s.queued, None
                rebet, s.queued_rebet = s.queued_rebet, False
                try:
                    placed = self.set_bets(i, bets, now)   # (starts the countdown, like any first bet)
                    events += self._rush_betting([e for e in placed if e["kind"] != "betting_timer"], now) if rebet else placed
                except TableError as e:
                    events.append({"kind": "queued_dropped", "seat": i, "reason": str(e)})
            elif s.auto_rebet and s.last_bets:
                try:
                    events += self.rebet(i, now)
                except TableError as e:
                    events += self._auto_rebet_off(i, str(e))
        return events + say(self.lines.say("table", "place_bets"))

    # ------------------------------------------------------------------ the clock
    def tick(self, now: float) -> list:
        """Advance everything that's due by `now`."""
        events = []
        for _ in range(200):  # each pass makes progress; bounded for safety
            if self.deadline is None or now < self.deadline:
                break
            self.deadline = None
            events += self._advance(now)
        return events

    def _advance(self, now: float) -> list:
        raise NotImplementedError

    def _timer(self, now: float, phases=("betting",)) -> float | None:
        if self.deadline is not None and self.phase in phases:
            return round(max(0.0, self.deadline - now), 1)
        return None

    def _seat_entry(self, i: int, s: Seat) -> dict:
        return {"seat": i, "entity": s.participant.entity_id, "name": s.participant.name,
                "human": s.participant.is_human, "bets": self._bets_view(s.bets), "ready": s.ready,
                "queued": self._bets_view(s.queued) if s.queued else None, "auto_rebet": s.auto_rebet}
