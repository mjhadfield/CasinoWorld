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
    runner sends their new balance after the table event that moved the money."""
    is_human = True

    def __init__(self, session, casino, game: str):
        self.session = session
        self.casino = casino
        self.game = game
        self.entity_id = session.entity_id
        self.name = session.player.name

    @property
    def balance(self) -> int:
        return self.casino.store.balance(self.session.player.id)

    def debit(self, amount, note):
        from casino_server.store import InsufficientFunds
        if amount <= 0:
            return True
        try:
            self.casino.store.adjust(self.session.player.id, -amount, "bet", self.game, note)
        except InsufficientFunds:
            return False
        return True

    def credit(self, amount, note):
        if amount > 0:
            self.casino.store.adjust(self.session.player.id, amount, "payout", self.game, note)

    def refund(self, amount, note):
        if amount > 0:   # a "bet" row the other way: it takes the stake back off what they've wagered
            self.casino.store.adjust(self.session.player.id, amount, "bet", self.game, note)


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
