"""
Three Card Poker table: a timed state machine that runs a real table's flow.

  betting   Seated players place chips on their spots (everyone sees them go
            down). A countdown starts at the first bet and closes early once
            every human at the table is Ready. "No more bets."
  dealing   Upfront bets are taken; three cards to each seat in turn from
            first base, then three face down to the dealer.
  deciding  Everyone in the hand decides at once: Play (matching the Ante) or
            Fold, against one shared timer that ends early once the whole
            table has decided; anyone still undecided folds.
  sweeping  The dealer takes the folded hands and their bets.
  reveal    The dealer turns their own cards over and announces the hand.
  settling  Then settles each remaining player in turn, third base back to
            first: their cards are turned over, losing bets swept, cards
            taken away, winnings placed beside the stakes.
  clearing  All the chips left on the felt go back to their players, then
            betting opens again.

House rule (this table, not the v2 engine): folding forfeits the Ante, Pair
Plus and Jackpot bets. A Prime bet on three cards of one colour has already
won, so a player who folds tucks their cards under it; that hand is settled
like a played one, with only the Prime paying.

Seating, betting, Ready and the clock are shared with every table game
(base.py); this module is the Three Card Poker round. Seats are numbered from
first base (the dealer's left, the player's right on screen) -- the deal goes
0..5, settling goes 5..0.
"""
from dataclasses import dataclass

from casino_server.dealer import DealerLines
from casino_server.engines import three_card_poker as tcp
from casino_server.engines.cards import Deck
from casino_server.tables.base import CHIPS, INACTIVE_ROUNDS, Seat, TableError, TableMachine, say  # noqa: F401

SPOTS = ("ante", "pair_plus", "prime", "jackpot")


@dataclass
class Timings:
    betting: float = 15.0        # from the first bet
    betting_npc_only: float = 5.0
    min_betting: float = 3.0     # betting stays open at least this long, even if everyone's Ready
    rebet: float = 3.0           # a Rebet cuts the betting countdown to this
    decide: float = 20.0         # everyone decides at once within this
    deal_card: float = 0.09      # between the cards of one hand (dealt as a packet of three)
    deal_hand_pause: float = 0.5  # between hands: each comes out of the shuffler, rests, then flies over
    deal_pause: float = 0.8      # after the last card
    jackpot_lock: float = 1.6    # before the deal: Jackpot lights go solid and the Jackpot chips are lifted
    last_decision: float = 0.8   # after the final Play/Fold, before the dealer moves
    sweep_pause: float = 1.0     # before the first folded hand is swept, and between each
    sweep_each: float = 0.5      # sweeping one folded hand
    reveal: float = 2.0          # dealer turns their cards over and announces the hand
    settle_pause: float = 1.0    # after the announcement, and after the payout, before moving on
    settle_base: float = 1.1     # per player: cards out, turned over, taken away (plus the pauses)...
    settle_step: float = 0.45    # ...plus this for each bet swept or paid
    clear: float = 2.4           # chips go back to everyone, then the cards are cleared

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        """Everything happens on the next tick -- for tests."""
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


@dataclass
class RoundSeat:
    """A seat's stake in the current round -- kept even if they stand up, so a
    hand that's already been played still gets settled and paid."""
    participant: object
    bets: tcp.Bets
    cards: list
    decided: bool = False
    folded: bool = False
    play_bet: int = 0
    result: tcp.HandResult | None = None
    held: bool = False      # folded under a winning Prime bet: settled like a played hand
    swept: bool = False     # folded, and the dealer has swept its bets (and its cards, unless held)
    revealed: bool = False
    settled: bool = False

    @property
    def in_settle(self) -> bool:
        """Still on the felt for the settle: played, or folded under a winning Prime."""
        return not self.folded or self.held


_say = say


def describe(hand_eval) -> str:
    """'Queen high', 'a Pair of 7s', 'a Straight' -- for the dealer's lines."""
    names = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack"}
    rank, name, tiebreak = hand_eval
    if name == "High Card":
        return f"{names.get(tiebreak[0], tiebreak[0])} high"
    if name == "Pair":
        v = tiebreak[0]
        return f"a Pair of {names.get(v, v)}s"
    label = tcp.hand_label(hand_eval)
    if label == "Three of a Kind":
        return label
    return f"a {label}"


class ThreeCardPokerMachine(TableMachine):
    game = tcp.GAME_KEY
    label = tcp.GAME_LABEL
    SPOTS = SPOTS
    MAIN_SPOT = "ante"
    FLAT_SPOTS = {"jackpot": tcp.JACKPOT_BET}
    NEEDS_MAIN = "Side bets need an Ante alongside them."
    CANT_COVER = "Not enough balance to cover that plus a matching Play bet."

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=Deck, lines: DealerLines | None = None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.deck_factory = deck_factory
        self.round: dict[int, RoundSeat] = {}
        self.dealer_cards: list = []
        self.dealer_eval = None
        self._settle_queue: list[int] = []

    def rules(self) -> dict:
        rules = tcp.rules()
        notes = rules["notes"] + ["Folding loses your Ante, Pair Plus and Jackpot bets.",
                                  "A Prime on three cards of one colour still pays if you fold."]
        return {**rules, "notes": notes, "chips": CHIPS, "min_ante": CHIPS[0], "seats": len(self.seats)}

    def max_cost(self, bets: dict) -> int:
        return bets["ante"] * 2 + bets["pair_plus"] + bets["prime"] + bets["jackpot"]

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        rs = self.round.get(seat)
        if rs is not None and rs.participant is self.seats[seat].participant and not rs.decided \
                and self.phase in ("dealing", "deciding"):
            return self._fold(seat, now, reason="left")
        return []

    # ------------------------------------------------------------------ deciding
    def decide(self, seat: int, play: bool, now: float) -> list:
        if self.phase != "deciding":
            raise TableError("It's not time to decide.")
        rs = self.round.get(seat)
        if rs is None or rs.participant is not self.seats[seat].participant:
            raise TableError("You're not in this hand.")
        if rs.decided:
            raise TableError("You've already decided.")
        if play:
            if not rs.participant.debit(rs.bets.ante, "play"):
                return self._fold(seat, now, reason="funds")
            rs.decided, rs.play_bet = True, rs.bets.ante
            event = {"kind": "decision", "seat": seat, "play": True, "amount": rs.bets.ante,
                     "_paid": [rs.participant]}
            return [event] + self._all_decided(now)
        return self._fold(seat, now)

    def _fold(self, seat: int, now: float, reason: str = "") -> list:
        rs = self.round[seat]
        rs.decided, rs.folded = True, True
        # Three cards of one colour have already won any Prime bet: the cards
        # go under it rather than onto the folded pile.
        rs.held = rs.bets.prime > 0 and len({c.color for c in rs.cards}) == 1
        event = {"kind": "decision", "seat": seat, "play": False, "held": rs.held}
        if reason:
            event["reason"] = reason
        return [event] + self._all_decided(now)

    def _all_decided(self, now: float) -> list:
        """Once the whole table has decided, the timer ends early."""
        if self.phase == "deciding" and all(rs.decided for rs in self.round.values()):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return []

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            self.phase = "deciding"
            self.deadline = now + self.timings.decide
            return [{"kind": "decisions_open", "seconds": self.timings.decide, "seats": sorted(self.round)}]
        if self.phase == "deciding":
            events = []
            for seat in sorted(self.round):  # out of time: anyone undecided folds
                if not self.round[seat].decided:
                    events += self._timed_out(seat) + self._fold(seat, now, reason="timeout")
            self._work_out_results()
            return events + self._sweep_folds(now)
        if self.phase == "sweeping":
            return self._reveal(now)
        if self.phase == "reveal":
            self.phase = "settling"
            self._settle_queue = [seat for seat in sorted(self.round, reverse=True) if self.round[seat].in_settle]
            return self._settle_next(now)
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
        playing = {i: tcp.Bets(**bets) for i, bets in taken.items()}
        rnd = tcp.ThreeCardPokerRound(playing, deck=self.deck_factory())
        self.round = {i: RoundSeat(self.seats[i].participant, bets, rnd.hands[i]) for i, bets in playing.items()}
        self.dealer_cards = rnd.dealer_cards
        self.phase = "dealing"
        # Three cards at a time: all of first base's hand, then the next seat's,
        # and so on, the dealer's own hand last.
        hands = sorted(playing) + ["dealer"]
        order = [[who, c] for who in hands for c in range(3)]
        # The Jackpot bets are locked in before the deal: the dealer presses the button
        # (the lights go solid red) and lifts the Jackpot chips off the table.
        jackpots = [i for i in sorted(playing) if playing[i].jackpot]
        duration = (len(order) * self.timings.deal_card + (len(hands) - 1) * self.timings.deal_hand_pause
                    + self.timings.deal_pause)
        if jackpots:
            duration += self.timings.jackpot_lock
        self.deadline = now + duration
        events.append({"kind": "bets_closed", "seats": sorted(playing), "jackpots": jackpots,
                       "_paid": [self.seats[i].participant for i in sorted(playing)]})
        events += _say(self.lines.say("table", "no_more_bets"))
        events.append({
            "kind": "dealt", "order": order, "interval": self.timings.deal_card,
            "hand_pause": self.timings.deal_hand_pause,
            "_private": {i: {"cards": [c.code for c in rs.cards],
                             "hand": tcp.hand_label(tcp.evaluate_three_card_hand(rs.cards))}
                         for i, rs in self.round.items()},
        })
        return events

    def _work_out_results(self):
        jackpot_amount = self.jackpot.amount if self.jackpot else 0
        for rs in self.round.values():
            r = tcp.settle_hand(rs.cards, self.dealer_cards, rs.bets, rs.folded, jackpot_amount)
            if rs.folded:  # house rule: a fold forfeits Pair Plus and Jackpot
                r.pair_plus_return = 0
                r.jackpot_return, r.jackpot_won = 0, False
            rs.result = r

    def _sweep_folds(self, now: float) -> list:
        """The dealer takes the folded hands, and every bet that went with them."""
        self.phase = "sweeping"
        seats = []
        for seat in sorted(self.round, reverse=True):
            rs = self.round[seat]
            if not rs.folded:
                continue
            spots = [("ante", rs.bets.ante), ("pair_plus", rs.bets.pair_plus), ("jackpot", rs.bets.jackpot)]
            if not rs.held:
                spots.append(("prime", rs.bets.prime))
            rs.swept = True
            seats.append({"seat": seat, "muck": not rs.held,
                          "steps": [{"spot": spot, "amount": amount} for spot, amount in spots if amount > 0]})
        t = self.timings
        self.deadline = now + ((t.sweep_pause + t.sweep_each) * len(seats) + 0.4 * t.sweep_each if seats else 0.0)
        return [{"kind": "fold_sweep", "seats": seats, "pause": t.sweep_pause}] if seats else []

    def _reveal(self, now: float) -> list:
        """The dealer turns their own cards over and announces the hand."""
        self.phase = "reveal"
        self.dealer_eval = tcp.evaluate_three_card_hand(self.dealer_cards)
        qualifies = tcp.dealer_qualifies(self.dealer_eval)
        self.deadline = now + self.timings.reveal
        line = self.lines.say("dealer", "qualifies" if qualifies else "no_qualify", dealer=describe(self.dealer_eval))
        return [{"kind": "dealer_reveal", "cards": [c.code for c in self.dealer_cards],
                 "hand": tcp.hand_label(self.dealer_eval), "qualified": qualifies}] + _say(line)

    def _settle_next(self, now: float) -> list:
        """Settle one player: their losing bets swept first, then their winners
        paid. Seats with nothing left on the felt (a fold, no side bets) are skipped."""
        if not self._settle_queue:
            self.phase = "clearing"
            self.deadline = now + self.timings.clear
            return [{"kind": "round_end"}]
        seat = self._settle_queue.pop(0)
        rs = self.round[seat]
        rs.settled = rs.revealed = True
        result = rs.result
        events = []
        if result.jackpot_won and self.jackpot:
            self.jackpot.win()
            events.append({"kind": "jackpot_won", "seat": seat, "amount": result.jackpot_return,
                           "name": rs.participant.name})
        rs.participant.credit(result.total_returned, result.outcome)
        steps = self._steps(rs, result)
        t = self.timings
        self.deadline = now + t.settle_base + 2 * t.settle_pause + t.settle_step * len(steps)
        events.append({
            "kind": "settle_seat", "seat": seat, "outcome": result.outcome, "held": rs.held,
            "say": self.lines.announce(result, rs.participant.name, rs.held), "pause": t.settle_pause,
            "cards": [c.code for c in rs.cards], "hand": tcp.hand_label(result.player_eval),
            "steps": steps,
            "net": result.net, "total_returned": result.total_returned,
            "_paid": [rs.participant],
        })
        return events

    @staticmethod
    def _steps(rs: RoundSeat, r: tcp.HandResult) -> list:
        """What the dealer does on each spot -- losing bets collected first, then
        pushes and winners paid -- in that order. A fold held under a winning
        Prime has only the Prime left (everything else went with the fold)."""
        if rs.folded:
            return [{"spot": "prime", "action": "pay", "amount": rs.bets.prime,
                     "payout": r.prime_return - rs.bets.prime}] if rs.held and r.prime_return else []
        steps = []
        stakes = [("ante", rs.bets.ante, r.ante_return), ("play", rs.play_bet, r.play_return),
                  ("pair_plus", rs.bets.pair_plus, r.pair_plus_return),
                  ("prime", rs.bets.prime, r.prime_return), ("jackpot", rs.bets.jackpot, r.jackpot_return)]
        for spot, bet, ret in stakes:
            if bet <= 0:
                continue
            if ret == 0:
                steps.append({"spot": spot, "action": "collect", "amount": bet})
            elif ret == bet:
                steps.append({"spot": spot, "action": "push", "amount": bet})
            else:
                steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret - bet})
        if r.ante_bonus_return:
            steps.append({"spot": "ante", "action": "bonus", "amount": 0, "payout": r.ante_bonus_return})
        return sorted(steps, key=lambda step: step["action"] != "collect")  # stable: losers first

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.dealer_cards = []
        self.dealer_eval = None
        self._settle_queue = []
        return self._reopen_betting(now)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        """The whole table as `viewer` (a seat index, or None for a passer-by) may see it."""
        seats = []
        for i, s in enumerate(self.seats):
            if s.participant is None:
                seats.append(None)
                continue
            entry = {**self._seat_entry(i, s), "cards": [], "hand": None, "decided": False,
                     "folded": False, "result": None}
            seats.append(entry)
        for i, rs in self.round.items():
            entry = seats[i]
            if entry is None or entry["entity"] != rs.participant.entity_id:
                continue  # they stood up mid-hand; the hand settles off-screen
            entry["bets"] = {**rs.bets.to_dict(), "play": rs.play_bet}  # a fold's bets stay until the sweep
            entry["decided"], entry["folded"], entry["held"] = rs.decided, rs.folded, rs.held
            if rs.swept:  # the dealer has taken the folded hand's bets -- all but a held Prime
                entry["bets"] = {**dict.fromkeys(SPOTS, 0), "play": 0, "prime": rs.bets.prime if rs.held else 0}
            if rs.settled or (rs.swept and not rs.held):
                entry["cards"] = []
            else:  # face down until their settle; you know your own
                show = viewer == i
                entry["cards"] = [c.code if show else "??" for c in rs.cards]
                entry["hand"] = tcp.hand_label(tcp.evaluate_three_card_hand(rs.cards)) if show else None
            if rs.settled:
                entry["result"] = {"outcome": rs.result.outcome, "net": rs.result.net}
        dealer = {"cards": [], "hand": None, "qualified": None}
        if self.dealer_cards:
            if self.dealer_eval is not None:
                dealer = {"cards": [c.code for c in self.dealer_cards], "hand": tcp.hand_label(self.dealer_eval),
                          "qualified": tcp.dealer_qualifies(self.dealer_eval)}
            else:
                dealer["cards"] = ["??"] * 3
        timer = self._timer(now, ("betting", "deciding"))
        return {"game": self.game, "phase": self.phase, "seats": seats, "dealer": dealer,
                "timer": timer, "my_seat": viewer}
