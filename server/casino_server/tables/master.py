"""
The Master Table: one table that becomes any of the card games that share the swept-bay table (never Roulette or
Craps). It starts blank -- the Master Table crest, no spots -- and a seated player asks the dealer for a game.

MasterMachine holds the chosen game's own machine (`inner`) and passes everything else through to it, so the
runner, the NPCs and the message handling see an ordinary table of that game. What it adds:
- choose_game: any seated person asks for a game. Anyone else seated gets VOTE seconds to say no (silence is a
  yes); NPCs don't vote. Asked mid-hand, the change waits for the hand to end ("queued").
- the change itself, between hands only: bets on the felt go back, NPCs who don't care for the new game get up,
  everyone else keeps their place in the order (the seat that goes or comes when the seat count changes 6<->5
  is the one that moves people least), and the table holds ("changing") while the clients animate it.
- going back to blank once no person has sat here for REVERT seconds: the NPCs finish their hand and go.

Seats: `seats` is the inner machine's, or the blank table's six. A blank table offers no seats to NPCs
(free_seats() is empty to them) -- only people sit down at the crest.
"""
from dataclasses import dataclass

from casino_server.tables.base import CHIPS, Seat, TableError, say

GAME_KEY = "master_table"
GAME_LABEL = "Master Table"
# The games it can become (plan_catalogue's keys), in the dealer's menu order.
GAMES = ("three_card_poker", "blackjack", "pai_gow_fortune", "pai_gow_face_up", "mississippi_stud",
         "ultimate_texas_holdem", "let_it_ride", "high_card_flush", "baccarat")
SEATS = {g: 5 if g in ("let_it_ride", "high_card_flush") else 6 for g in GAMES}
# Where each seat's chair stands across the table, by seat count (CasinoTable's Seat markers): only the order and
# spacing matter here, to pick the seat that moves people least.
CHAIR_X = {6: (122.5, 73.5, 24.5, -24.5, -73.5, -122.5), 5: (120.0, 60.0, 0.0, -60.0, -120.0)}
ANIMS = ("cloth", "sweep", "dust")
SPEEDS = (0.5, 1.0, 2.0)
DEFAULT_ANIM, DEFAULT_SPEED = "cloth", 1.0
# How long each change animation runs at 1x (the client's master_swap.gd), in seconds.
MORPH = {"cloth": 2.7, "sweep": 3.0, "dust": 3.3}
# Actions a player can take at the chosen game's table; refused while there's none, or while it's changing.
ACTIONS = {"set_bet", "set_bets", "clear_bets", "rebet", "set_auto_rebet", "ready", "decide", "insure",
           "play_action", "set_hand", "fold", "claim", "working_bets", "suggest", "check", "take_box", "drop_box"}


@dataclass
class Timings:
    vote: float = 10.0     # others seated have this long to say no
    revert: float = 30.0   # no person seated this long: back to the crest
    hold: float = 0.8      # on top of the animation, before betting opens on the new game

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


def morph_seconds(anim: str, speed: float) -> float:
    return MORPH.get(anim, MORPH[DEFAULT_ANIM]) / (speed or 1.0)


def remap(occupied: list[bool], to_n: int) -> list[int]:
    """For each seat of a `to_n`-seat table, the seat it takes over (-1: a new, empty one). Everyone keeps their
    order; when the count changes, the seat that goes (an empty one) or comes is the one that moves people least."""
    from_n = len(occupied)
    xf, xt = CHAIR_X[from_n], CHAIR_X[to_n]
    if to_n == from_n:
        return list(range(to_n))
    options = []
    if to_n < from_n:
        for gone in range(from_n):
            if not occupied[gone]:
                options.append([j for j in range(from_n) if j != gone][:to_n])
    else:
        for new in range(to_n):
            options.append([-1 if n == new else (n if n < new else n - 1) for n in range(to_n)])
    if not options:
        raise TableError("Every seat's taken -- that game seats fewer.")
    return min(options, key=lambda m: sum(abs(xf[j] - xt[n]) for n, j in enumerate(m) if j >= 0 and occupied[j]))


class MasterMachine:
    label = GAME_LABEL
    DEALER = True

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None, jackpot=None, *,
                 make=None, lines=None, anim: str = DEFAULT_ANIM, speed: float = DEFAULT_SPEED,
                 leavers=None, on_seats=None):
        """`make(game, seats)` builds a game's machine; `leavers(participants, game)` picks which of the NPCs
        seated get up for a new game; `on_seats(n)` hears the seat count change (the floor's seat points follow
        it)."""
        from casino_server.dealer import DealerLines
        self.table_id = table_id
        self.timings = timings or Timings()
        self.jackpot = jackpot
        self.lines = lines or DealerLines()
        self.make = make
        self.anim = anim if anim in ANIMS else DEFAULT_ANIM
        self.speed = speed if speed in SPEEDS else DEFAULT_SPEED
        self.leavers = leavers or (lambda participants, game: [])
        self.on_seats = on_seats or (lambda n: None)
        self.inner = None
        self._blank = [Seat() for _ in range(seats)]
        self.vote = None          # {game, by, votes: {seat: True|None}, until}
        self.queued = None        # a game agreed on, waiting for the hand to end ("" = back to the crest)
        self.changing_until = None
        self.revert_at = None

    # ------------------------------------------------------------------ passing through
    def __getattr__(self, name):
        # (only reached for what MasterMachine doesn't have itself)
        inner = self.__dict__.get("inner")
        if name in ACTIONS:
            if inner is None:
                return self._refuse("Ask the dealer for a game first.")
            if self.__dict__.get("changing_until") is not None:
                return self._refuse("One moment -- the table's changing.")
        if inner is None:
            raise AttributeError(name)
        return getattr(inner, name)

    @staticmethod
    def _refuse(message: str):
        def refuse(*args, **kwargs):
            raise TableError(message)
        return refuse

    @property
    def game(self) -> str:
        """The chosen game's key (what the NPCs play and the ledger books bets as), or GAME_KEY while blank."""
        return self.inner.game if self.inner is not None else GAME_KEY

    @property
    def current(self) -> str:
        """The game being played, or "" at the blank table."""
        return self.inner.game if self.inner is not None else ""

    @property
    def seats(self) -> list:
        return self.inner.seats if self.inner is not None else self._blank

    @property
    def phase(self) -> str:
        if self.changing_until is not None:
            return "changing"
        return self.inner.phase if self.inner is not None else "idle"

    @property
    def deadline(self):
        return self.inner.deadline if self.inner is not None else None

    @property
    def next_deadline(self) -> float | None:
        # (a revert or a queued change that's due waits for the hand to end: the inner machine's deadline wakes it)
        later = self.revert_at if self._between_hands() else None
        due = [t for t in (self.changing_until, later, self.vote and self.vote["until"]) if t is not None]
        if self.inner is not None and self.changing_until is None and self.inner.next_deadline is not None:
            due.append(self.inner.next_deadline)
        return min(due) if due else None

    def seat_of(self, participant) -> int | None:
        return next((i for i, s in enumerate(self.seats) if s.participant is participant and s.box_of is None), None)

    def free_seats(self) -> list[int]:
        if self.inner is None:
            return []   # (NPCs don't sit at a blank table; people sit through sit(), which checks the seat itself)
        return self.inner.free_seats()

    def humans_seated(self) -> list[int]:
        return [i for i, s in enumerate(self.seats)
                if s.participant is not None and s.participant.is_human and s.box_of is None]

    def rules(self) -> dict:
        if self.inner is not None:
            return self.inner.rules()
        return {"chips": CHIPS, "min_bet": CHIPS[0], "seats": len(self._blank)}

    def _between_hands(self) -> bool:
        return self.inner is None or self.inner.phase == "betting"

    # ------------------------------------------------------------------ seating
    def sit(self, seat: int, participant, now: float) -> list:
        if self.inner is not None:
            events = self.inner.sit(seat, participant, now)
        else:
            if not participant.is_human:
                raise TableError("There's no game here yet.")
            if not 0 <= seat < len(self._blank):
                raise TableError("There's no such seat.")
            if self._blank[seat].participant is not None:
                raise TableError("That seat's taken.")
            if self.seat_of(participant) is not None:
                raise TableError("You're already sitting here.")
            self._blank[seat] = Seat(participant=participant)
            events = [{"kind": "seated", "seat": seat, "entity": participant.entity_id, "name": participant.name,
                       "human": True}]
            events += say(self.lines.say("master", "ask"))
        return events + self._revert_check(now)

    def stand(self, seat: int, now: float, reason: str = "") -> list:
        if self.inner is not None:
            events = self.inner.stand(seat, now, reason)
        else:
            s = self._blank[seat]
            if s.participant is None:
                return []
            events = [{"kind": "stood", "seat": seat, "entity": s.participant.entity_id, "reason": reason}]
            self._blank[seat] = Seat()
        if self.vote is not None:
            self.vote["votes"].pop(seat, None)
            if not self.humans_seated():
                self.vote = None
                events.append({"kind": "master_vote_end", "ok": False, "game": "", "reason": "left"})
            elif all(self.vote["votes"].values()):
                events += self._vote_passed(now)
        return events + self._revert_check(now)

    # ------------------------------------------------------------------ asking for a game
    def choose_game(self, seat: int, game: str, now: float) -> list:
        s = self.seats[seat] if 0 <= seat < len(self.seats) else None
        if s is None or s.participant is None:
            raise TableError("Sit down first.")
        if game not in GAMES:
            raise TableError("The dealer can't set that game up here.")
        if game == self.current:
            raise TableError("That's the game already.")
        if self.vote is not None:
            raise TableError("A change is already being asked about.")
        if self.changing_until is not None:
            raise TableError("One moment -- the table's changing.")
        if SEATS[game] < len(self.seats) and all(x.participant is not None for x in self.seats):
            raise TableError(f"{_name(game)} seats {SEATS[game]}: a seat needs to be free first.")
        voters = [i for i in self.humans_seated() if i != seat]
        if voters:
            self.vote = {"game": game, "by": seat, "votes": dict.fromkeys(voters), "until": now + self.timings.vote}
            return [{"kind": "master_vote", "game": game, "by": seat, "name": s.participant.name, "voters": voters,
                     "seconds": self.timings.vote}] + say(self.lines.say("master", "vote", game=_name(game)))
        return self._agreed(game, now)

    def game_vote(self, seat: int, accept: bool, now: float) -> list:
        v = self.vote
        if v is None or seat not in v["votes"]:
            raise TableError("There's nothing to vote on.")
        if not accept:
            self.vote = None
            who = self.seats[seat].participant
            return [{"kind": "master_vote_end", "ok": False, "game": v["game"], "seat": seat,
                     "name": who.name if who else ""}] + say(
                self.lines.say("master", "declined", name=who.name if who else "", game=_name(self.current)))
        v["votes"][seat] = True
        events = [{"kind": "master_vote_cast", "seat": seat, "accept": True}]
        if all(v["votes"].values()):
            events += self._vote_passed(now)
        return events

    def _vote_passed(self, now: float) -> list:
        game, self.vote = self.vote["game"], None
        return [{"kind": "master_vote_end", "ok": True, "game": game}] + self._agreed(game, now)

    def cancel_queued(self, seat: int, now: float) -> list:
        if self.seats[seat].participant is None:
            raise TableError("Sit down first.")
        if self.queued is None:
            return []
        self.queued = None
        return [{"kind": "master_queued", "game": None}] + say(self.lines.say("master", "stay", game=_name(self.current)))

    def _agreed(self, game: str, now: float) -> list:
        if self._between_hands():
            return self._start_change(game, now)
        self.queued = game
        return [{"kind": "master_queued", "game": game}] + say(self.lines.say("master", "after_hand", game=_name(game)))

    # ------------------------------------------------------------------ the change
    def _start_change(self, game: str, now: float) -> list:
        """Change to `game` ("" for the blank table), between hands."""
        events = []
        self.queued = None
        if self.inner is not None:   # second boxes end with the game (between hands, so nothing's riding on them)
            for i, s in enumerate(self.inner.seats):
                if s.box is not None:
                    events += self.inner._release_box(i, now, "game_change")
        old = self.seats
        # bets on the felt go back (none are paid for until betting closes)
        if self.inner is not None:
            for i, s in enumerate(old):
                if s.participant is not None and (any(s.bets.values()) or s.queued):
                    s.queued, s.queued_rebet = None, False
                    events.append({"kind": "bet_changed", "seat": i, "bets": {k: 0 for k in s.bets}})
        # NPCs who don't care for it get up
        if game:
            going = {id(p) for p in self.leavers([s.participant for s in old
                                                   if s.participant is not None and not s.participant.is_human], game)}
            for i, s in enumerate(old):
                if s.participant is not None and id(s.participant) in going:
                    events += self._unseat(i, now, "game_change")
        n = SEATS[game] if game else 6
        occupied = [s.participant is not None for s in self.seats]
        if n < len(occupied) and all(occupied):
            # (someone sat down since it was agreed: no room at the smaller table)
            return events + say(self.lines.say("master", "no_room", game=_name(game)))
        mapping = remap(occupied, n)
        movers = [(new, self.seats[j]) for new, j in enumerate(mapping) if j >= 0 and self.seats[j].participant]
        if game:
            self.inner = self.make(game, n)
            for new, s in movers:
                self.inner.seats[new] = self.inner._empty_seat(s.participant)
        else:
            self.inner = None
            self._blank = [Seat() for _ in range(n)]
            for new, s in movers:
                self._blank[new] = Seat(participant=s.participant)
        for _, s in movers:
            if hasattr(s.participant, "game"):
                s.participant.game = game or GAME_KEY
        self.on_seats(n)
        seconds = morph_seconds(self.anim, self.speed) + self.timings.hold
        self.changing_until = now + seconds
        events.append({"kind": "master_change", "game": game, "seats": n, "map": mapping, "anim": self.anim,
                       "speed": self.speed, "seconds": seconds, "rules": self.rules(),
                       "_remap": {s.participant.entity_id: new for new, s in movers}, "_resnap": True})
        return events + say(self.lines.say("master", "changing" if game else "blank", game=_name(game)))

    def _unseat(self, seat: int, now: float, reason: str) -> list:
        return self.inner.stand(seat, now, reason) if self.inner is not None else self.stand(seat, now, reason)

    def _finish_change(self, now: float) -> list:
        self.changing_until = None
        if self.inner is None:
            return say(self.lines.say("master", "ask_any")) + self._revert_check(now)
        return self.inner._reopen_betting(now) + self._revert_check(now)

    # ------------------------------------------------------------------ back to the crest
    def _revert_check(self, now: float) -> list:
        """Start (or stop) the countdown back to the crest: it runs while a game's set and no person is seated."""
        want = self.inner is not None and not self.humans_seated()
        if want and self.revert_at is None:
            self.revert_at = now + self.timings.revert
            return [{"kind": "master_revert", "seconds": self.timings.revert}]
        if not want and self.revert_at is not None:
            self.revert_at = None
            return [{"kind": "master_revert", "seconds": None}]
        return []

    def _revert(self, now: float) -> list:
        events = []
        for i, s in enumerate(self.seats):
            if s.participant is not None:
                events += self._unseat(i, now, "closing")
        self.revert_at = None
        return events + self._start_change("", now)

    # ------------------------------------------------------------------ the clock
    def tick(self, now: float) -> list:
        events = []
        if self.changing_until is not None:
            if now < self.changing_until:
                return events
            events += self._finish_change(now)
        if self.vote is not None and now >= self.vote["until"]:
            events += self._vote_passed(now)   # (no answer is a yes)
            if self.changing_until is not None:
                return events
        if self.inner is not None:
            events += self.inner.tick(now)
        if self.queued is not None and self._between_hands() and self.changing_until is None:
            events += self._start_change(self.queued, now)
        elif self.revert_at is not None and now >= self.revert_at and self._between_hands() and self.changing_until is None:
            events += self._revert(now)
        return events

    # ------------------------------------------------------------------ what clients see
    def master_view(self, now: float) -> dict:
        v = self.vote
        return {"game": self.current, "anim": self.anim, "speed": self.speed, "games": list(GAMES),
                "seats_by_game": SEATS, "rules": self.rules(), "queued": self.queued,
                "vote": None if v is None else {"game": v["game"], "by": v["by"], "voters": list(v["votes"]),
                                                "agreed": [i for i, a in v["votes"].items() if a],
                                                "seconds": round(max(0.0, v["until"] - now), 1)},
                "changing": None if self.changing_until is None else round(max(0.0, self.changing_until - now), 1),
                "revert": None if self.revert_at is None else round(max(0.0, self.revert_at - now), 1)}

    def snapshot(self, viewer: int | None, now: float) -> dict:
        if self.inner is not None:
            snap = self.inner.snapshot(viewer, now)
            if self.changing_until is not None:
                snap["phase"], snap["timer"] = "changing", None
        else:
            seats = [None if s.participant is None else
                     {"seat": i, "entity": s.participant.entity_id, "name": s.participant.name,
                      "human": s.participant.is_human, "bets": {}, "ready": False, "queued": None, "auto_rebet": False}
                     for i, s in enumerate(self._blank)]
            snap = {"game": GAME_KEY, "phase": "changing" if self.changing_until is not None else "idle",
                    "seats": seats, "timer": None, "my_seat": viewer}
        return {**snap, "master": self.master_view(now)}


def _name(game: str) -> str:
    from casino_server import plan
    return plan.CATALOGUE["games"].get(game, {}).get("name", GAME_LABEL) if game else GAME_LABEL
