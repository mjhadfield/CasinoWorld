"""
Who's sitting in a seat. The table machine only talks to this interface, so a
real player and an NPC go through exactly the same rules and money moves.
"""


class Participant:
    is_human = False
    entity_id = ""
    name = ""

    @property
    def balance(self) -> int:
        raise NotImplementedError

    def debit(self, amount: int, note: str) -> bool:
        """Take `amount` pence; False (and nothing taken) if they can't cover it."""
        raise NotImplementedError

    def credit(self, amount: int, note: str):
        raise NotImplementedError

    def refund(self, amount: int, note: str):
        """A bet taken down before it was played: the stake back, and it no longer counts as staked."""
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
        self.player_id = session.player.id
        self.name = session.player.name

    @property
    def here(self) -> bool:
        """Still connected as the character that sat down (so their wallet's worth sending)."""
        s = self.session
        return s in self.casino.sessions and s.player is not None and s.player.id == self.player_id

    @property
    def balance(self) -> int:
        return self.casino.store.balance(self.player_id)

    def debit(self, amount, note):
        from casino_server.store import InsufficientFunds
        if amount <= 0:
            return True
        try:
            self.casino.store.adjust(self.player_id, -amount, "bet", self.game, note)
        except InsufficientFunds:
            return False
        return True

    def credit(self, amount, note):
        if amount > 0:
            self.casino.store.adjust(self.player_id, amount, "payout", self.game, note)

    def refund(self, amount, note):
        if amount > 0:   # a "bet" row the other way: it takes the stake back off what they've wagered
            self.casino.store.adjust(self.player_id, amount, "bet", self.game, note)


class NpcParticipant(Participant):
    """An NPC: the budget they came in with, counted as it's staked and paid back
    (their visit's figures go to the roster when they leave)."""

    def __init__(self, npc):
        self.npc = npc
        self.entity_id = npc.entity_id
        self.name = npc.name

    @property
    def balance(self) -> int:
        return self.npc.bankroll

    def debit(self, amount, note):
        if amount > self.npc.bankroll:
            return False
        self.npc.bankroll -= amount
        self.npc.wagered += amount
        return True

    def credit(self, amount, note):
        self.npc.bankroll += amount
        self.npc.returned += amount

    def refund(self, amount, note):
        self.npc.bankroll += amount
        self.npc.wagered -= amount


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

    def debit(self, amount, note):
        if not self.owner.debit(amount, note):
            return False
        self.flow -= max(0, amount)
        return True

    def credit(self, amount, note):
        self.owner.credit(amount, note)
        self.flow += max(0, amount)

    def refund(self, amount, note):
        self.owner.refund(amount, note)
        self.flow += max(0, amount)
