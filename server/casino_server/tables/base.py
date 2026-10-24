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

from casino_server.participants import BoxParticipant

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
    box: int | None = None       # the seat beside this one its player is playing as a second box
    box_of: int | None = None    # this seat is a second box: the seat of the player playing it


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
    SECOND_BOX = False              # a player can play the free seat beside them too, with matching bets
    HIDE_BOX = True                 # ...whose cards they only see once their own hand is decided (not Blackjack)
    CANT_COVER_BOTH = "Not enough balance to match that on your second box."

    def __init__(self, table_id: str, seats: int, timings, jackpot, lines):
        self.table_id = table_id
        self.timings = timings
        self.jackpot = jackpot
        self.lines = lines
        self.seats = [self._empty_seat() for _ in range(seats)]
        self.phase = "betting"
        self.deadline: float | None = None  # when the current phase/step is due
        self.betting_opened_at = 0.0
        self.round_start: dict = {}   # seat -> (participant, their balance -- a second box: its flow -- before this hand)
        self._shown_boxes: set = set()  # second boxes in this hand whose cards their player has been shown

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
        if isinstance(entry[0], BoxParticipant):
            return entry[0].flow - entry[1]
        net = entry[0].balance - entry[1]
        box = self.round_start.get(self.seats[seat].box)
        if box is not None and isinstance(box[0], BoxParticipant) and box[0].owner is entry[0]:
            net -= box[0].flow - box[1]   # (the shared wallet moved for both hands)
        return net

    @property
    def next_deadline(self) -> float | None:
        return self.deadline

    def seat_of(self, participant) -> int | None:
        for i, s in enumerate(self.seats):
            if s.participant is participant and s.box_of is None:
                return i
        return None

    def free_seats(self) -> list[int]:
        return [i for i, s in enumerate(self.seats) if s.participant is None]

    def humans_seated(self) -> list[int]:
        """The seats people are sitting in (not their second boxes)."""
        return [i for i, s in enumerate(self.seats)
                if s.participant is not None and s.participant.is_human and s.box_of is None]

    def _main(self, seat: int) -> int:
        """The seat a second box's bets are made from (any other seat: itself)."""
        of = self.seats[seat].box_of
        return seat if of is None else of

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
        if s.box_of is not None:
            return self._release_box(s.box_of, now, reason)
        events = self._release_box(seat, now, "stood") if s.box is not None else []
        events += self._leaving_mid_hand(seat, now, reason)
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

    # ------------------------------------------------------------------ a second box
    def take_box(self, seat: int, box: int, now: float) -> list:
        """The player in `seat` plays the free seat beside them too. Its bets always match theirs."""
        if not self.SECOND_BOX:
            raise TableError("There's no second box at this game.")
        s = self.seats[seat]
        if s.participant is None or not s.participant.is_human or s.box_of is not None:
            raise TableError("Sit down first.")
        if s.box is not None:
            raise TableError("You're already playing a second box.")
        if not 0 <= box < len(self.seats) or abs(box - seat) != 1:
            raise TableError("Your second box has to be the seat beside you.")
        if self.seats[box].participant is not None:
            raise TableError("That seat's taken.")
        if 2 * self.max_cost({**dict.fromkeys(self.SPOTS, 0), **self._matched(s)}) > s.participant.balance:
            raise TableError(self.CANT_COVER_BOTH)
        self.seats[box] = self._empty_seat(BoxParticipant(s.participant))
        self.seats[box].box_of, s.box = seat, box
        return [{"kind": "box_taken", "seat": box, "of": seat, "entity": s.participant.entity_id,
                 "name": s.participant.name}] + self._mirror(seat)

    def drop_box(self, seat: int, now: float) -> list:
        """Give the second box back -- between hands, or while it's not in the one being played."""
        seat = self._main(seat)
        box = self.seats[seat].box
        if box is None:
            raise TableError("You're not playing a second box.")
        if self.phase not in self.BETTING_PHASES and self._in_round(box):
            raise TableError("Your second box is in this hand -- drop it after.")
        return self._release_box(seat, now, "dropped")

    def _release_box(self, seat: int, now: float, reason: str) -> list:
        box = self.seats[seat].box
        if box is None:
            return []
        events = self._leaving_mid_hand(box, now, reason)
        self.seats[box] = self._empty_seat()
        self.seats[seat].box = None
        events.append({"kind": "box_dropped", "seat": box, "of": seat, "reason": reason})
        if self.phase == "betting":
            events += self._maybe_close_early(now)
        return events + self._after_stand(box, now)

    @staticmethod
    def _matched(s: Seat) -> dict:
        """The bets a second box would carry for this seat now: these, or the next hand's."""
        return s.queued or s.bets

    def _mirror(self, seat: int) -> list:
        """A second box takes on its player's bets, Ready and all (bets for the next hand too)."""
        s = self.seats[seat]
        if s.box is None:
            return []
        b = self.seats[s.box]
        events = []
        if b.bets != s.bets and (self.phase in self.BETTING_PHASES or not self._in_round(s.box)):
            b.bets = dict(s.bets)
            events.append({"kind": "bet_changed", "seat": s.box, "bets": self._bets_view(b.bets)})
        if (b.queued or None) != (s.queued or None):
            b.queued = dict(s.queued) if s.queued else None
            events.append({"kind": "bet_changed", "seat": s.box, "queued": True,
                           "bets": self._bets_view(b.queued or dict.fromkeys(self.SPOTS, 0))})
        if s.ready and not b.ready:
            b.ready = True
            events.append({"kind": "ready", "seat": s.box})
        b.auto_rebet = s.auto_rebet
        return events

    def _box_shown(self, seat: int) -> bool:
        """Whether a second box's player may see its cards yet (always, for any other seat's own player)."""
        return self.seats[seat].box_of is None or not self.HIDE_BOX or seat in self._shown_boxes

    def _sees(self, viewer: int | None, seat: int) -> bool:
        """Whether the player in `viewer` sees `seat`'s private cards: their own, and their second box once shown."""
        if viewer is None:
            return False
        return seat == viewer or (self.seats[viewer].box == seat and self._box_shown(seat))

    @staticmethod
    def _undecided(hand) -> bool:
        """Whether a hand in a decide-at-once game is still to make this decision."""
        return not (hand.decided or getattr(hand, "folded", False) or not getattr(hand, "waiting", True))

    def _box_first(self, seat: int):
        """In the games where everyone decides at once, a second box waits for its player's own hand."""
        main = self.seats[seat].box_of
        if main is None or not self.HIDE_BOX:
            return
        hand = getattr(self, "round", {}).get(main)
        if hand is not None and hand.participant is self.seats[main].participant and self._undecided(hand):
            raise TableError("Decide Box 1 first.")

    def _box_private(self, seat: int) -> dict:
        """What a seat's own player is shown of its hand (the deal's "_private" entry)."""
        return {}

    def _reveal_boxes(self) -> list:
        """Each second box whose player has decided their own hand now: its cards, to them."""
        if not self.HIDE_BOX:
            return []
        events = []
        rnd = getattr(self, "round", {})
        for main, s in enumerate(self.seats):
            box = s.box
            if box is None or box in self._shown_boxes or box not in rnd or not self._in_round(box):
                continue
            hand = rnd.get(main)
            if hand is not None and hand.participant is s.participant and self._undecided(hand):
                continue
            self._shown_boxes.add(box)
            events.append({"kind": "box_revealed", "seat": box, "of": main, "_private": {box: self._box_private(box)}})
        return events

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
        seat = self._main(seat)
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
        being played without this seat. A second box's bets are its player's, matched."""
        seat = self._main(seat)
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
        boxes = 2 if s.box is not None else 1
        if self.max_cost(new) * boxes > s.participant.balance:
            raise TableError(self.CANT_COVER_BOTH if self.max_cost(new) <= s.participant.balance else self.CANT_COVER)
        if queued:
            s.queued = new if any(new.values()) else None
            s.queued_rebet = s.queued_rebet and s.queued is not None
            return [{"kind": "bet_changed", "seat": seat, "bets": self._bets_view(new), "queued": True}] + self._mirror(seat)
        first_bet = not any(any(x.bets.values()) for x in self.seats)
        s.bets = new
        events = [{"kind": "bet_changed", "seat": seat, "bets": self._bets_view(new)}] + self._mirror(seat)
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
        seat = self._main(seat)
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
        seat = self._main(seat)
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
        seat = self._main(seat)
        s = self._betting_seat(seat)
        if any(s.bets.values()) and not self._has_main(s.bets):
            raise TableError(self.NEEDS_MAIN)
        s.ready = True
        return [{"kind": "ready", "seat": seat}] + self._mirror(seat) + self._maybe_close_early(now)

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
        self._shown_boxes = set()
        # (everyone's figure before anyone's bets: a player and their second box share a wallet)
        befores = {i: s.participant.flow if isinstance(s.participant, BoxParticipant) else s.participant.balance
                   for i, s in enumerate(self.seats) if s.participant is not None}
        for i, s in enumerate(self.seats):
            if s.participant is None:
                continue
            before = befores[i]
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
            if i not in playing and self.seats[i].box not in playing:
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
            if s.box_of is not None:   # (a second box's bets come with its player's)
                s.queued = None
        events = [{"kind": "betting_open"}]
        for i, s in enumerate(self.seats):  # bets put down during the last hand go on now
            if s.participant is None or s.box_of is not None:
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
        return events + self._reveal_boxes()

    def _advance(self, now: float) -> list:
        raise NotImplementedError

    def _timer(self, now: float, phases=("betting",)) -> float | None:
        if self.deadline is not None and self.phase in phases:
            return round(max(0.0, self.deadline - now), 1)
        return None

    def _seat_entry(self, i: int, s: Seat) -> dict:
        return {"seat": i, "entity": s.participant.entity_id, "name": s.participant.name,
                "human": s.participant.is_human, "bets": self._bets_view(s.bets), "ready": s.ready,
                "queued": self._bets_view(s.queued) if s.queued else None, "auto_rebet": s.auto_rebet,
                "box_of": s.box_of}
