"""
Who's sitting in a seat. The table machine only talks to this interface, so a
real player and an NPC go through exactly the same rules and money moves.
"""


class Participant:
    is_human = False
    entity_id = ""
    name = ""
    # Where they're sitting, for the Tracker (tracking.py): TableRunner.place() sets these as they sit down (a Master
    # Table's game as it changes). With no tracker, nothing's counted.
    tracker = None
    game = ""
    casino_id = ""
    table_id = ""
    who_id = None      # the player's or NPC's id
    visit_key = None   # an NPC's visit (the bet log's)

    @property
    def track_open(self) -> dict:
        """The Tracker's note of what this participant has down that's not been decided yet, by spot."""
        if "_track_open" not in self.__dict__:
            self._track_open = {}
        return self._track_open

    def place(self, tracker, casino_id: str, table_id: str, game: str):
        self.tracker, self.casino_id, self.table_id, self.game = tracker, casino_id, table_id, game
        self.track_open.clear()   # (what's open is at the table they've left: a swept bet never gets a payout row)

    @property
    def balance(self) -> int:
        raise NotImplementedError

    # `detail` is the ledger's breakdown of the move (store.adjust()); only a real player's wallet keeps it.
    def debit(self, amount: int, note: str, detail: dict | None = None) -> bool:
        """Take `amount` pence; False (and nothing taken) if they can't cover it."""
        raise NotImplementedError

    def credit(self, amount: int, note: str, detail: dict | None = None):
        """Pay `amount` pence back. With a `detail`, even 0 is recorded (a settled round that lost)."""
        raise NotImplementedError

    def refund(self, amount: int, note: str, detail: dict | None = None):
        """A bet taken down before it was played: the stake back, and it no longer counts as staked. `detail`: which
        spots it came off ({"spots": {spot: pence}}), when the table knows (Craps)."""
        raise NotImplementedError


class HumanParticipant(Participant):
    """A connected player: money goes through the SQLite wallet and ledger. The
    runner sends their new balance after the table event that moved the money.
    It keeps the character it sat down as: a hand that finishes after they've
    switched character (or left) still pays that one."""
    is_human = True

    def __init__(self, session, casino, game: str):
        self.session = session
        self.casino = casino
        self.game = game
        self.entity_id = session.entity_id
        self.player_id = self.who_id = session.player.id
        self.name = session.player.name

    @property
    def here(self) -> bool:
        """Still connected as the character that sat down (so their wallet's worth sending)."""
        s = self.session
        return s in self.casino.sessions and s.player is not None and s.player.id == self.player_id

    @property
    def balance(self) -> int:
        return self.casino.store.balance(self.player_id)

    def debit(self, amount, note, detail=None):
        from casino_server.store import InsufficientFunds
        if amount <= 0:
            return True
        try:
            self.casino.store.adjust(self.player_id, -amount, "bet", self.game, note, detail, *self._where())
        except InsufficientFunds:
            return False
        if self.tracker is not None:
            self.tracker.stake(self, amount, note, detail)
        return True

    def credit(self, amount, note, detail=None):
        if amount > 0 or detail:
            self.casino.store.adjust(self.player_id, max(0, amount), "payout", self.game, note, detail, *self._where())
            if self.tracker is not None:
                self.tracker.settle(self, max(0, amount), note, detail)

    def refund(self, amount, note, detail=None):
        if amount > 0:   # a "bet" row the other way: it takes the stake back off what they've wagered
            self.casino.store.adjust(self.player_id, amount, "bet", self.game, note, None, *self._where())
            if self.tracker is not None:
                self.tracker.hand_back(self, amount, note, detail)

    def _where(self) -> tuple:
        return (self.casino_id or None, self.table_id or None)


class NpcParticipant(Participant):
    """An NPC: the budget they came in with, counted as it's staked and paid back, in all and by game (their visit's
    figures go to the roster when they leave)."""

    def __init__(self, npc):
        self.npc = npc
        self.entity_id = npc.entity_id
        self.name = npc.name
        self.who_id = npc.npc_id

    @property
    def visit_key(self):
        return self.npc.visit_key

    @property
    def balance(self) -> int:
        return self.npc.bankroll

    def _game(self) -> dict:
        return self.npc.game_figures(self.game)

    def debit(self, amount, note, detail=None):
        if amount > self.npc.bankroll:
            return False
        self.npc.bankroll -= amount
        self.npc.wagered += amount
        g = self._game()
        g["wagered"] += amount
        if note == "spin":
            g["spins"] = g.get("spins", 0) + 1
        if self.tracker is not None:
            g["expected"] += self.tracker.stake(self, amount, note, detail)
        return True

    def credit(self, amount, note, detail=None):
        self.npc.bankroll += amount
        self.npc.returned += amount
        g = self._game()
        g["returned"] += amount
        if self.tracker is not None:
            g["expected"] += self.tracker.settle(self, amount, note, detail)

    def refund(self, amount, note, detail=None):
        self.npc.bankroll += amount
        self.npc.wagered -= amount
        g = self._game()
        g["wagered"] -= amount
        if self.tracker is not None:
            g["expected"] -= self.tracker.hand_back(self, amount, note, detail)


class BoxParticipant(Participant):
    """A player's second box: a seat of its own, played with their own money through their own
    participant. `flow` counts what this box has staked (-) and been paid (+), so its hand has a
    net of its own while the wallet is shared."""
    is_human = True

    def __init__(self, owner):
        self.owner = owner
        self.flow = 0

    @property
    def entity_id(self):
        return self.owner.entity_id

    @property
    def name(self):
        return self.owner.name

    @property
    def session(self):
        return self.owner.session

    @property
    def here(self) -> bool:
        return self.owner.here

    @property
    def balance(self) -> int:
        return self.owner.balance

    def debit(self, amount, note, detail=None):
        if not self.owner.debit(amount, note, detail):
            return False
        self.flow -= max(0, amount)
        return True

    def credit(self, amount, note, detail=None):
        self.owner.credit(amount, note, detail)
        self.flow += max(0, amount)

    def refund(self, amount, note, detail=None):
        self.owner.refund(amount, note, detail)
        self.flow += max(0, amount)
