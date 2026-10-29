"""
Blackjack table: a timed state machine that runs a real table's flow, dealt
from a real 8-deck shoe that's shuffled when the cut card comes out.

  betting     Seated players place chips on the Blackjack circle and the side
              bets. Countdown from the first bet; closes early once every human
              is Ready. Bets close: the Jackpot lights go solid and those
              chips are lifted, as at Three Card Poker.
  dealing     One card face up to each box from first base, the dealer's up-
              card, a second card to each box, then the dealer's hole card face
              down -- all from the shoe.
  side_bets   Super Pairs, 21+3, Top 3 and the Jackpot settle at once off each
              box's two cards and the up-card: losers swept, winners paid and
              handed straight back to the player.
  insurance   An Ace showing: everyone may insure (half their bet) at once,
              against a shared timer that ends early once all have decided.
  peek        An Ace or 10 showing: the dealer checks the hole card. A Dealer
              Blackjack is turned over and settles every box (insurance pays
              2:1); with no player Blackjack to push, every box loses and the
              lot is swept in one quick go. Otherwise the insurance bets are
              taken and play goes on.
  naturals    Once the dealer can't have Blackjack (after the peek, or straight
              away with a 2-9 showing), every player Blackjack is paid 3:2 at
              once and its cards cleared away.
  playing     Each box in turn from first base, each hand in turn after a
              split: Hit, Stand, Double or Split against a turn timer (out of
              time stands). A bust is swept straight away.
  dealer      The hole card is turned over and the dealer draws to 17, standing
              on all 17s (no draws if every hand has bust).
  settling    Each box in turn, third base back to first: losers swept,
              pushes left, winners paid beside the stake (Blackjack 3:2). A
              dealer bust wins every hand still in, so they're paid one after
              another in one quick go, with nothing to check.
  clearing    All chips go back to their players; the cards go in the discard
              rack, where they stay until the shoe is shuffled.
  shuffling   Only after a hand in which the cut card came out: the discards
              and the rest of the shoe go through the shuffler, and a fresh
              shoe is loaded with a new cut card.

Seating, betting, Ready and the clock are shared with every table game
(base.py). Player cards are dealt face up, so they're public; only the
dealer's hole card is hidden until it's turned over.
"""
import random
from dataclasses import dataclass, field

from casino_server.dealer import DealerLines
from casino_server.engines import blackjack as bj
from casino_server.engines.cards import Deck
from casino_server.tables.base import CHIPS, TableError, TableMachine, returns_detail, say, stakes_detail

SPOTS = ("bet", "super_pairs", "twenty_one_plus_three", "top_three", "jackpot")
SHOE_CARDS = 52 * bj.DECK_COUNT
CUT_FROM_BACK = (0.20, 0.30)  # the cut card goes this far from the back: 70-80% penetration


@dataclass
class Timings:
    betting: float = 15.0
    betting_npc_only: float = 5.0
    min_betting: float = 3.0
    rebet: float = 3.0
    deal_card: float = 0.32       # each card out of the shoe
    deal_pause: float = 0.6       # after the last card
    jackpot_lock: float = 1.6     # before the deal, as at Three Card Poker
    side_pause: float = 0.6       # before the side bets are settled
    side_step: float = 0.45       # a box's losing side bets swept together, then each winner paid
    side_sweep_gap: float = 0.12  # between the stacks of one sweep
    insurance: float = 10.0       # everyone decides at once
    last_decision: float = 0.8
    peek: float = 1.6             # the dealer checks the hole card
    turn: float = 20.0            # per decision; out of time stands
    after_action: float = 0.7     # room for the card to land before the next turn
    bust: float = 1.3             # a bust is swept
    dealer_reveal: float = 1.2
    dealer_card: float = 0.9
    settle_pause: float = 0.51
    settle_base: float = 0.64
    settle_step: float = 0.29
    sweep_gap: float = 0.12       # between the boxes when a Dealer Blackjack sweeps them all
    pay_gap: float = 0.42         # between the hands when a dealer bust pays everyone still in
    clear: float = 2.4
    shuffle: float = 6.0

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


class Shoe:
    """The 8-deck shoe. Dealt down across many hands; the cut card comes out
    when only the last 20-30% are left, and the hand in progress is the last
    before a shuffle. `deck_factory` makes the cards (tests rig it)."""

    def __init__(self, deck_factory=None, rng: random.Random | None = None):
        self.deck_factory = deck_factory or (lambda: Deck(num_decks=bj.DECK_COUNT))
        self.rng = rng or random.Random()
        self.shuffle()

    def shuffle(self):
        self.deck = self.deck_factory()
        self.total = self.deck.cards_remaining()
        lo, hi = CUT_FROM_BACK
        self.cut_at = self.rng.randint(int(self.total * lo), int(self.total * hi)) if self.total > 52 else 0
        self.cut_out = False

    @property
    def remaining(self) -> int:
        return self.deck.cards_remaining()

    def draw(self):
        if self.remaining == 0:  # only a rigged test shoe can run dry
            self.shuffle()
        card = self.deck.deal(1)[0]
        if not self.cut_out and self.remaining <= self.cut_at:
            self.cut_out = True
        return card

    def state(self) -> dict:
        return {"remaining": self.remaining, "total": self.total, "cut": self.cut_at, "cut_out": self.cut_out}


@dataclass
class Box:
    """A seat's stake in the current round -- kept if they stand up, so money
    already down is still settled."""
    participant: object
    bets: dict
    hands: list = field(default_factory=list)  # bj.Hand
    insurance: int = 0
    insurance_decided: bool = False
    side: bj.SideBetResult | None = None
    settled: bool = False

    @property
    def live(self) -> bool:
        """Has a hand still to be settled against the dealer (not bust, not a
        Blackjack that's already been paid)."""
        return any(not h.bust and h.outcome is None for h in self.hands)


def _codes(cards) -> list:
    return [c.code for c in cards]


class BlackjackMachine(TableMachine):
    game = bj.GAME_KEY
    label = bj.GAME_LABEL
    SPOTS = SPOTS
    MAIN_NAME = "Hand"
    BONUS_SPOTS = bj.SIDE_BETS
    SPOT_NAMES = {"twenty_one_plus_three": "21+3", "top_three": "Top 3"}
    MAIN_SPOT = "bet"
    LIMITED = True
    FLAT_SPOTS = {"jackpot": bj.JACKPOT_BET}
    NEEDS_MAIN = "Side bets need a Blackjack bet alongside them."
    CANT_COVER = "Not enough balance for that."
    SECOND_BOX = True
    HIDE_BOX = False   # (every hand is dealt face up, and played in turn)

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None,
                 jackpot=None, deck_factory=None, lines: DealerLines | None = None, rng=None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.shoe = Shoe(deck_factory, rng)
        self.round: dict[int, Box] = {}
        self.dealer_cards: list = []
        self.hole_shown = False
        self.dealer_blackjack = False
        self.turn: tuple[int, int] | None = None  # (seat, hand index) whose decision it is
        self._turn_order: list[int] = []
        self._settle_queue: list[int] = []
        self._sweep = False
        self._cut_announced = False

    @property
    def deck_factory(self):
        return self.shoe.deck_factory

    @deck_factory.setter
    def deck_factory(self, factory):
        """Tests swap the cards in: the shoe is re-made from them at once."""
        self.shoe.deck_factory = factory
        self.shoe.shuffle()

    def rules(self) -> dict:
        return {**bj.rules(), "chips": CHIPS, "min_bet": CHIPS[0], "seats": len(self.seats)}

    def _validate_bets(self, bets: dict):
        if bets["top_three"] and not bets["twenty_one_plus_three"]:
            raise TableError("Top 3 needs a 21+3 bet alongside it.")

    # ------------------------------------------------------------------ shoe
    def _draw(self):
        return self.shoe.draw()

    def _cut_event(self) -> list:
        """The cut card has come out of the shoe: this is the last hand before the shuffle."""
        if self.shoe.cut_out and not self._cut_announced:
            self._cut_announced = True
            return [{"kind": "cut_card"}] + say(self.lines.say("blackjack", "cut_card"))
        return []

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            return self._settle_side_bets(now)
        if self.phase == "side_bets":
            return self._after_side_bets(now)
        if self.phase == "insurance":
            events = []
            for seat, box in sorted(self.round.items()):  # out of time: no insurance
                if not box.insurance_decided:
                    box.insurance_decided = True
                    events += self._timed_out(seat)
                    events.append({"kind": "insurance", "seat": seat, "take": False, "reason": "timeout"})
            return events + self._start_peek(now)
        if self.phase == "peek":
            return self._after_peek(now)
        if self.phase == "naturals":
            return self._start_playing(now)
        if self.phase == "playing":
            if self.turn is not None:  # out of time: stand
                seat, _ = self.turn
                return self._timed_out(seat) + self._act(seat, "stand", now, reason="timeout")
            return self._next_turn(now)
        if self.phase == "dealer":
            return self._dealer_step(now)
        if self.phase == "settling":
            return self._settle_next(now)
        if self.phase == "clearing":
            if self.shoe.cut_out:
                self.phase = "shuffling"
                self.deadline = now + self.timings.shuffle
                return [{"kind": "shuffle", "seconds": self.timings.shuffle}] + say(self.lines.say("blackjack", "shuffle"))
            return self._open_betting(now)
        if self.phase == "shuffling":
            self.shoe.shuffle()
            self._cut_announced = False
            return [{"kind": "shoe_loaded", "shoe": self.shoe.state()}] + self._open_betting(now)
        return []

    # ------------------------------------------------------------------ the deal
    def _close_betting(self, now: float) -> list:
        events, taken = self._take_bets(now)
        if not taken:
            return events
        self.round = {i: Box(self.seats[i].participant, bets) for i, bets in taken.items()}
        seats = sorted(self.round)
        order, cards = [], {i: [] for i in seats}
        self.dealer_cards = []
        for k in range(2):  # a card to each box, then the dealer; twice
            for i in seats:
                cards[i].append(self._draw())
                order.append([i, k])
            self.dealer_cards.append(self._draw())
            order.append(["dealer", k])
        for i in seats:
            self.round[i].hands = [bj.Hand(cards[i], bet=self.round[i].bets["bet"])]
        self.hole_shown = False
        self.dealer_blackjack = False
        self.phase = "dealing"
        jackpots = [i for i in seats if taken[i]["jackpot"]]
        duration = len(order) * self.timings.deal_card + self.timings.deal_pause
        if jackpots:
            duration += self.timings.jackpot_lock
        self.deadline = now + duration
        events.append({"kind": "bets_closed", "seats": seats, "jackpots": jackpots,
                       "_paid": [self.seats[i].participant for i in seats]})
        events.append({"kind": "dealt", "order": order, "interval": self.timings.deal_card,
                       "cards": {str(i): _codes(cards[i]) for i in seats},
                       "labels": {str(i): self.round[i].hands[0].label() for i in seats},
                       "dealer_up": self.dealer_cards[0].code, "shoe": self.shoe.state()})
        return events + self._cut_event()

    @property
    def up_card(self):
        return self.dealer_cards[0]

    def _settle_side_bets(self, now: float) -> list:
        """Side bets settle straight after the deal, off each box's two cards and the up-card."""
        self.phase = "side_bets"
        seats, pool_boxes, settle_time = [], [], 0.0
        for seat, box in sorted(self.round.items()):
            side_bets = {k: box.bets[k] for k in bj.SIDE_BETS if box.bets[k]}
            if not side_bets:
                continue
            box.side = bj.side_bet_returns(box.hands[0].cards, self.up_card, side_bets)
            if box.side.hits_pool:
                pool_boxes.append(box)
        events = []
        if pool_boxes and self.jackpot:  # suited A/K/Q trips: the pool, shared between the boxes that hit it
            share = self.jackpot.win() // len(pool_boxes)
            for box in pool_boxes:
                box.side.returns["jackpot"] = share
        for seat, box in sorted(self.round.items()):
            if box.side is None:
                continue
            steps = []
            for spot in bj.SIDE_BETS:
                bet = box.bets[spot]
                if not bet:
                    continue
                ret = box.side.returns.get(spot, 0)
                if ret:
                    steps.append({"spot": spot, "action": "pay", "amount": bet, "payout": ret - bet if spot != "jackpot" else ret})
                else:
                    steps.append({"spot": spot, "action": "collect", "amount": bet})
            steps.sort(key=lambda s: s["action"] != "collect")
            won = sum(box.side.returns.values())
            self._credit(box.participant, won, "side bets", returns_detail(
                [(spot, box.bets[spot], box.side.returns.get(spot, 0)) for spot in bj.SIDE_BETS if box.bets[spot]],
                hand=box.side.hand))
            if box in pool_boxes:
                events.append({"kind": "jackpot_won", "seat": seat, "amount": box.side.returns["jackpot"],
                               "name": box.participant.name})
            seats.append({"seat": seat, "steps": steps, "hand": box.side.hand, "returned": won})
            lost = sum(s["action"] == "collect" for s in steps)
            settle_time += self.timings.side_step * (len(steps) - lost + (lost > 0)) \
                + self.timings.side_sweep_gap * max(lost - 1, 0)
        if not seats:
            return self._after_side_bets(now)
        t = self.timings
        self.deadline = now + t.side_pause + settle_time + 0.5 * t.side_step * len(seats)
        events.append({"kind": "side_bets", "seats": seats, "pause": t.side_pause, "step": t.side_step,
                       "sweep_gap": t.side_sweep_gap,
                       "_paid": [self.round[s["seat"]].participant for s in seats]})
        return events

    def _after_side_bets(self, now: float) -> list:
        if self.up_card.rank == "A":
            self.phase = "insurance"
            self.deadline = now + self.timings.insurance
            seats = sorted(self.round)
            return [{"kind": "insurance_open", "seconds": self.timings.insurance, "seats": seats,
                     "costs": {str(i): self.round[i].bets["bet"] // 2 for i in seats}}] \
                + say(self.lines.say("blackjack", "insurance"))
        return self._start_peek(now)

    # ------------------------------------------------------------------ insurance & the peek
    def insure(self, seat: int, take: bool, now: float) -> list:
        if self.phase != "insurance":
            raise TableError("Insurance isn't open.")
        box = self.round.get(seat)
        if box is None or box.participant is not self.seats[seat].participant:
            raise TableError("You're not in this hand.")
        if box.insurance_decided:
            raise TableError("You've already decided.")
        box.insurance_decided = True
        event = {"kind": "insurance", "seat": seat, "take": False}
        if take:
            cost = box.bets["bet"] // 2
            if cost <= 0 or not self._debit(box.participant, cost, "insurance", stakes_detail({"insurance": cost})):
                event["reason"] = "funds"
            else:
                box.insurance = cost
                event.update(take=True, amount=cost, _paid=[box.participant])
        events = [event]
        if all(b.insurance_decided for b in self.round.values()):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return events

    def _start_peek(self, now: float) -> list:
        if not bj.peeks(self.up_card):
            return self._pay_naturals(now)
        self.phase = "peek"
        self.dealer_blackjack = bj.is_blackjack(self.dealer_cards)
        self.deadline = now + self.timings.peek
        return [{"kind": "peek"}]

    def _after_peek(self, now: float) -> list:
        events = []
        insured = [(seat, box) for seat, box in sorted(self.round.items()) if box.insurance]
        steps = []
        for seat, box in insured:
            ret = bj.insurance_return(box.insurance, self.dealer_blackjack)
            self._credit(box.participant, ret, "insurance", returns_detail([("insurance", box.insurance, ret)]))
            steps.append({"seat": seat, "action": "pay" if ret else "collect", "amount": box.insurance,
                          "payout": ret - box.insurance if ret else 0})
        if self.dealer_blackjack:
            self.hole_shown = True
            events.append({"kind": "dealer_reveal", "cards": _codes(self.dealer_cards), "label": "Blackjack",
                           "blackjack": True})
            events += say(self.lines.say("blackjack", "dealer_blackjack"))
        else:
            events += say(self.lines.say("blackjack", "no_blackjack"))
        if steps:
            events.append({"kind": "insurance_settled", "seats": steps,
                           "_paid": [self.round[s["seat"]].participant for s in steps]})
        if self.dealer_blackjack:
            for box in self.round.values():
                for hand in box.hands:
                    hand.done = True
            self.phase = "settling"
            self._settle_queue = sorted(self.round, reverse=True)
            self._sweep = not any(hand.natural for box in self.round.values() for hand in box.hands)
            self.deadline = now + self.timings.dealer_reveal + (self.timings.settle_pause if steps else 0.0)
            return events
        return events + self._pay_naturals(now)

    def _pay_naturals(self, now: float) -> list:
        """The dealer can't have Blackjack now: pay every player Blackjack 3:2 straight away."""
        seats = []
        for seat, box in sorted(self.round.items()):
            hand = box.hands[0]
            if len(box.hands) == 1 and hand.natural and hand.outcome is None:
                hand.outcome, hand.returned = "Blackjack", bj.blackjack_return(hand.bet)
                self._credit(box.participant, hand.returned, "blackjack",
                                       returns_detail([("bet", hand.bet, hand.returned)], hand="Blackjack"))
                seats.append({"seat": seat, "hand": 0, "amount": hand.bet, "payout": hand.returned - hand.bet})
        if not seats:
            return self._start_playing(now)
        self.phase = "naturals"
        t = self.timings
        self.deadline = now + t.settle_pause + t.settle_step * len(seats) + t.settle_base
        line = self.lines.say("blackjack", "settle_blackjack", name=self.round[seats[0]["seat"]].participant.name,
                              hand="Blackjack")
        return [{"kind": "blackjacks_paid", "seats": seats, "say": line, "pause": t.settle_pause,
                 "_paid": [self.round[s["seat"]].participant for s in seats]}]

    # ------------------------------------------------------------------ playing
    def _start_playing(self, now: float) -> list:
        self.phase = "playing"
        self._turn_order = sorted(self.round)
        self.turn = None
        return self._next_turn(now)

    def _current_hand(self, seat: int):
        box = self.round[seat]
        for idx, hand in enumerate(box.hands):
            if not hand.done:
                return idx, hand
        return None, None

    def _options(self, seat: int, hand) -> list:
        box = self.round[seat]
        options = ["hit", "stand"]
        if hand.can_double:
            options.append("double")
        if hand.can_split(len(box.hands) - 1):
            options.append("split")
        return options

    def _next_turn(self, now: float) -> list:
        while self._turn_order:
            seat = self._turn_order[0]
            idx, hand = self._current_hand(seat)
            if hand is None:
                self._turn_order.pop(0)
                continue
            self.turn = (seat, idx)
            self.deadline = now + self.timings.turn
            return [{"kind": "turn", "seat": seat, "hand": idx, "seconds": self.timings.turn,
                     "options": self._options(seat, hand), "total": hand.label()}]
        self.turn = None
        return self._start_dealer(now)

    def play_action(self, seat: int, action: str, now: float) -> list:
        if self.phase != "playing" or self.turn is None or self.turn[0] != seat:
            raise TableError("It's not your turn.")
        if self.round[seat].participant is not self.seats[seat].participant:
            raise TableError("You're not in this hand.")
        return self._act(seat, action, now)

    def _act(self, seat: int, action: str, now: float, reason: str = "") -> list:
        box = self.round[seat]
        idx, hand = self._current_hand(seat)
        if hand is None:
            return self._next_turn(now)
        if action not in self._options(seat, hand):
            raise TableError({"double": "You can only double on your first two cards.",
                              "split": "You can only split a pair."}.get(action, "You can't do that now."))
        event = {"kind": "action", "seat": seat, "hand": idx, "action": action}
        if reason:
            event["reason"] = reason
        events = []
        if action == "stand":
            hand.done = True
        elif action == "hit":
            hand.cards.append(self._draw())
            event["card"] = hand.cards[-1].code
            if hand.bust or hand.total == 21:
                hand.done = True
        elif action == "double":
            if not self._debit(box.participant, hand.bet, "double", stakes_detail({"double": hand.bet})):
                raise TableError("Not enough balance to double.")
            event.update(amount=hand.bet, _paid=[box.participant])
            hand.bet *= 2
            hand.doubled = True
            hand.cards.append(self._draw())
            event["card"] = hand.cards[-1].code
            hand.done = True
        elif action == "split":
            if not self._debit(box.participant, hand.bet, "split", stakes_detail({"split": hand.bet})):
                raise TableError("Not enough balance to split.")
            event.update(amount=hand.bet, _paid=[box.participant])
            c1, c2 = hand.cards
            aces = c1.rank == "A" and c2.rank == "A"
            a = bj.Hand([c1, self._draw()], bet=hand.bet, from_split=True, split_aces=aces)
            b = bj.Hand([c2, self._draw()], bet=hand.bet, from_split=True, split_aces=aces)
            if aces:  # split Aces: one card each, and stand
                a.done = b.done = True
            box.hands[idx:idx + 1] = [a, b]
            event["hands"] = [_codes(a.cards), _codes(b.cards)]
            event["labels"] = [a.label(), b.label()]
        event["total"] = box.hands[idx].label()
        event["done"] = box.hands[idx].done
        events.append(event)
        events += self._cut_event()
        if action in ("hit", "double") and hand.bust:
            box_hand_bet = hand.bet
            self._lost(box.participant, hand.bet)
            events.append({"kind": "bust", "seat": seat, "hand": idx, "amount": box_hand_bet})
            events += say(self.lines.say("blackjack", "bust", name=box.participant.name))
            self.turn = None
            self.deadline = now + self.timings.bust
            return events
        next_idx, next_hand = self._current_hand(seat)
        if next_hand is not None and next_idx == idx and action in ("hit", "split"):
            # Same hand still going: a fresh turn for the next decision.
            self.turn = (seat, idx)
            self.deadline = now + self.timings.turn
            events.append({"kind": "turn", "seat": seat, "hand": idx, "seconds": self.timings.turn,
                           "options": self._options(seat, next_hand), "total": next_hand.label()})
            return events
        self.turn = None
        self.deadline = now + self.timings.after_action
        return events

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        """Getting up mid-hand stands every hand still to play (the money's down,
        so they're settled as normal); insurance not yet decided is declined."""
        box = self.round.get(seat)
        if box is None or box.participant is not self.seats[seat].participant:
            return []
        for hand in box.hands:
            hand.done = True
        events = []
        if self.phase == "insurance" and not box.insurance_decided:
            box.insurance_decided = True
            events.append({"kind": "insurance", "seat": seat, "take": False, "reason": "left"})
        if self.phase == "playing" and self.turn is not None and self.turn[0] == seat:
            self.turn = None
            self.deadline = now + self.timings.after_action
        return events

    # ------------------------------------------------------------------ the dealer
    def _start_dealer(self, now: float) -> list:
        self.phase = "dealer"
        self.hole_shown = True
        self.deadline = now + self.timings.dealer_reveal
        return [{"kind": "dealer_reveal", "cards": _codes(self.dealer_cards),
                 "label": bj.Hand(list(self.dealer_cards), 0).label(), "blackjack": False}]

    def _dealer_step(self, now: float) -> list:
        """Draw to 17 -- but only if someone still has a hand to beat."""
        live = any(box.live for box in self.round.values())
        if live and bj.dealer_should_hit(self.dealer_cards):
            self.dealer_cards.append(self._draw())
            self.deadline = now + self.timings.dealer_card
            return [{"kind": "dealer_draw", "card": self.dealer_cards[-1].code,
                     "label": bj.Hand(list(self.dealer_cards), 0).label()}] + self._cut_event()
        total, _ = bj.hand_value(self.dealer_cards)
        key = "dealer_bust" if total > 21 else "dealer_total"
        events = [{"kind": "dealer_done", "total": total, "bust": total > 21}]
        if live:
            events += say(self.lines.say("blackjack", key, total=total))
        self.phase = "settling"
        self._settle_queue = [seat for seat in sorted(self.round, reverse=True) if self.round[seat].live]
        self._sweep = total > 21  # every hand still in wins: paid one after another, no checking
        return events + self._settle_next(now)

    # ------------------------------------------------------------------ settling
    def _settle_next(self, now: float) -> list:
        if not self._settle_queue:
            self.phase = "clearing"
            self.deadline = now + self.timings.clear
            return [{"kind": "round_end"}]
        if self._sweep:  # a Dealer Blackjack beat everyone, or the dealer bust: no need to look at each box
            seats, self._settle_queue = self._settle_queue, []
            t = self.timings
            hands = sum(1 for seat in seats for h in self.round[seat].hands if not h.bust and h.outcome is None)
            total, _ = bj.hand_value(self.dealer_cards)
            gap = t.pay_gap if total > 21 else t.sweep_gap
            events = [self._settle_seat(seat, now, sweep=gap) for seat in seats]
            self.deadline = now + gap * hands + t.settle_base + t.settle_pause
            return events
        return [self._settle_seat(self._settle_queue.pop(0), now)]

    def _settle_seat(self, seat: int, now: float, sweep: float | None = None) -> dict:
        box = self.round[seat]
        box.settled = True
        total, _ = bj.hand_value(self.dealer_cards)
        hands, returned, steps_total = [], 0, 0
        ledger_hands = []   # every hand on the box but a Blackjack already paid, busts included
        for idx, hand in enumerate(box.hands):
            if hand.bust:
                ledger_hands.append({"stake": hand.bet, "returned": 0, "outcome": "Bust"})
            if hand.bust or hand.outcome is not None:
                continue  # swept when it bust, or a Blackjack already paid
            outcome, ret = bj.settle_hand(hand, total, total > 21, self.dealer_blackjack)
            hand.outcome, hand.returned = outcome, ret
            returned += ret
            if ret == 0:
                step = {"action": "collect", "amount": hand.bet}
            elif ret == hand.bet:
                step = {"action": "push", "amount": hand.bet}
            else:
                step = {"action": "pay", "amount": hand.bet, "payout": ret - hand.bet}
            hands.append({"hand": idx, "outcome": outcome, "label": hand.label(), **step})
            ledger_hands.append({"stake": hand.bet, "returned": ret, "outcome": outcome, "label": hand.label()})
            steps_total += 1
        detail = None
        if ledger_hands:
            detail = returns_detail([("bet", sum(h["stake"] for h in ledger_hands), returned)], hands=ledger_hands)
        self._ride(box.participant, sum(h.bet for h in box.hands if h.bust))   # (counted off as they bust)
        self._credit(box.participant, returned, "blackjack", detail)
        t = self.timings
        self.deadline = now + t.settle_base + 2 * t.settle_pause + t.settle_step * steps_total
        outcomes = {h["outcome"] for h in hands}
        key = "blackjack" if outcomes == {"Blackjack"} else "win" if outcomes <= {"Win", "Blackjack"} \
            else "push" if outcomes == {"Push"} else "lose" if outcomes == {"Lose"} else "mixed"
        if sweep is not None:  # the dealer's already announced the Blackjack or the bust; `sweep` is the gap per hand
            return {"kind": "settle_seat", "seat": seat, "hands": hands, "say": "", "sweep": sweep,
                    "total_returned": returned, "_paid": [box.participant]}
        line = self.lines.say("blackjack", f"settle_{key}", name=box.participant.name,
                              hand=hands[0]["label"] if len(hands) == 1 else f"{len(hands)} hands")
        return {"kind": "settle_seat", "seat": seat, "hands": hands, "say": line, "pause": t.settle_pause,
                "total_returned": returned, "_paid": [box.participant]}

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.dealer_cards = []
        self.hole_shown = False
        self.dealer_blackjack = False
        self.turn = None
        self._settle_queue = []
        self._sweep = False
        return self._reopen_betting(now)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        seats = []
        on_felt = 0
        for i, s in enumerate(self.seats):
            if s.participant is None:
                seats.append(None)
                continue
            seats.append({**self._seat_entry(i, s), "hands": [], "insurance": 0})
        for i, box in self.round.items():
            on_felt += sum(len(h.cards) for h in box.hands if not (h.bust or h.outcome or box.settled))
            entry = seats[i]
            if entry is None or entry["entity"] != box.participant.entity_id:
                continue
            entry["bets"] = {**box.bets}
            if box.side is not None:  # side bets have been settled and handed back
                entry["bets"].update({k: 0 for k in bj.SIDE_BETS})
            entry["insurance"] = box.insurance if self.phase in ("insurance", "peek") else 0
            # Every hand, so indices match `turn`; a bust or paid Blackjack is `gone` from the felt.
            entry["hands"] = [] if box.settled else [
                {"cards": [] if h.bust or h.outcome else _codes(h.cards), "bet": h.bet, "doubled": h.doubled,
                 "label": h.label(), "done": h.done, "gone": h.bust or h.outcome is not None} for h in box.hands]
        dealer = {"cards": [], "label": None}
        if self.dealer_cards:
            on_felt += len(self.dealer_cards)
            if self.hole_shown:
                dealer = {"cards": _codes(self.dealer_cards), "label": bj.Hand(list(self.dealer_cards), 0).label()}
            else:
                dealer = {"cards": [self.dealer_cards[0].code, "??"], "label": None}
        dealt = self.shoe.total - self.shoe.remaining
        return {"game": self.game, "phase": self.phase, "seats": seats, "dealer": dealer,
                "turn": {"seat": self.turn[0], "hand": self.turn[1]} if self.turn else None,
                "shoe": self.shoe.state(), "discards": max(0, dealt - on_felt) if self.phase != "shuffling" else 0,
                "timer": self._timer(now, ("betting", "insurance", "playing")), "my_seat": viewer}
