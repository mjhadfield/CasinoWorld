"""
Pai Gow Poker tables -- Fortune Pai Gow and Face Up Pai Gow -- as timed state
machines running a real table's flow.

  betting   Ante, Fortune and the £1 Jackpot. Countdown from the first bet;
            closes early once every human is Ready. The Jackpot lights lock
            in as at the other tables.
  dealing   A fresh 53-card deck through the shuffler. Its display shows a
            random number from 1 to 7: counting the dealer as 1 and the seats
            from first base as 2-7, that position gets the first of seven
            7-card hands, and the rest follow in order. Hands for empty seats
            are dealt to their places too, then cleared to the discard rack
            once the deal's done. Players' cards are private.
            Face Up: the dealer's seven cards are turned over, sorted and set
            by House Way at once, for everyone to see.
  claiming  Face Up only, after a dealer Ace-high Pai Gow: every Ante pushes
            and nobody sets a hand. A player whose seven cards win a side bet
            claims it (their cards are shown and it's paid); the rest fold,
            their cards mucked unseen. Out of time does the same for them.
  setting   Everyone sets their 2-card Low and 5-card High hands at once,
            against one timer that ends early once all have set; anyone out
            of time is set by House Way. Face Up players may fold instead:
            the hand is mucked unseen and every bet on it is lost.
  dealer    Fortune: the dealer turns their cards over and sets by House Way.
  settling  Each player in turn, third base back to first: their hands are
            turned over and played against the dealer's; losing bets swept,
            winnings placed beside the stakes. Fortune, Jackpot and Envy pay
            off the player's own seven cards whatever happens to the Ante.
  clearing  Chips back to the players, cards to the rack (and the shuffler).

Seating, betting, Ready and the clock are shared with every table (base.py).
"""
import random
from dataclasses import dataclass, field

from casino_server.dealer import DealerLines
from casino_server.engines import pai_gow as pg
from casino_server.engines.cards import Card, Deck
from casino_server.tables.base import CHIPS, TableError, TableMachine, say

SPOTS = ("ante", "fortune", "jackpot")
HANDS = 7  # always dealt: six seats and the dealer


@dataclass
class Timings:
    betting: float = 15.0
    betting_npc_only: float = 5.0
    min_betting: float = 3.0
    rebet: float = 3.0
    jackpot_lock: float = 1.6
    deal_hand: float = 0.55      # each 7-card hand out of the shuffler
    deal_pause: float = 1.0
    clear_empty: float = 1.4     # then the empty seats' hands are swept to the rack
    setting: float = 60.0        # everyone sets at once
    last_decision: float = 0.8
    dealer_set: float = 4.2      # the dealer turns over, sorts and sets (Fortune)
    reveal: float = 3.6          # Face Up: the same, straight after the deal
    ace_high: float = 1.5        # Face Up: a dealer Ace-high Pai Gow is announced
    claim: float = 15.0          # ...then players claim a side-bet win or fold
    settle_pause: float = 0.9
    settle_base: float = 2.3          # the hands turned over, then the Low and High marks a beat apart
    settle_step: float = 0.45
    fold_sweep: float = 0.8      # Face Up: each folded hand swept, before anyone's turned over
    clear: float = 2.4

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


@dataclass
class PlayerHand:
    participant: object
    bets: dict
    cards: list
    front: list = field(default_factory=list)
    back: list = field(default_factory=list)
    set: bool = False
    auto: bool = False       # set by House Way when time ran out
    folded: bool = False
    claimed: bool = False    # Face Up Ace-high push: showed their cards for a side-bet win
    bonus_name: str | None = None  # ...the side-bet win they can claim
    bonus: pg.Bonus | None = None
    settled: bool = False

    @property
    def decided(self) -> bool:
        """Set, folded or claimed: done with this hand's one decision (a second box can be shown)."""
        return self.set or self.folded or self.claimed


def _codes(cards) -> list:
    return [c.code for c in cards]


def _cards_from(codes, hand: list) -> list:
    """The player's own cards matching these codes (each used once)."""
    pool = list(hand)
    picked = []
    for code in codes:
        match = next((c for c in pool if c.code == code), None)
        if match is None:
            raise TableError("Those aren't your cards.")
        pool.remove(match)
        picked.append(match)
    return picked


def _labels(front, back) -> dict:
    return {"front_label": pg.two_card_label(pg.evaluate_two_card_hand(front)),
            "back_label": pg.five_card_label(pg.evaluate_five(back))}


class PaiGowMachine(TableMachine):
    game = pg.FORTUNE
    SPOTS = SPOTS
    MAIN_SPOT = "ante"
    LIMITED = True
    FLAT_SPOTS = {"jackpot": pg.JACKPOT_BET}
    NEEDS_MAIN = "Side bets need an Ante alongside them."
    CANT_COVER = "Not enough balance for that."
    FACE_UP = False
    SECOND_BOX = True

    def __init__(self, table_id: str, seats: int = 6, timings: Timings | None = None, jackpot=None,
                 deck_factory=None, lines: DealerLines | None = None, rng=None):
        super().__init__(table_id, seats, timings or Timings(), jackpot, lines or DealerLines())
        self.deck_factory = deck_factory or (lambda: Deck(include_joker=True))
        self.rng = rng or random.Random()
        self.round: dict[int, PlayerHand] = {}
        self.dealer_cards: list = []
        self.dealer_front: list = []
        self.dealer_back: list = []
        self.dealer_shown = False
        self.ace_high_push = False
        self.start = 1
        self._settle_queue: list[int] = []
        self._envy: dict[int, int] = {}

    @property
    def label(self) -> str:
        return pg.LABELS[self.game]

    def rules(self) -> dict:
        return {**pg.rules(self.game), "chips": CHIPS, "min_ante": CHIPS[0], "seats": len(self.seats)}

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase == "betting":
            return self._close_betting(now)
        if self.phase == "dealing":
            if self.ace_high_push:
                return self._open_claims(now)
            self.phase = "setting"
            self.deadline = now + self.timings.setting
            return [{"kind": "setting_open", "seconds": self.timings.setting, "seats": sorted(self.round)}]
        if self.phase == "setting":
            events = []
            for seat, hand in sorted(self.round.items()):  # out of time: House Way
                if not hand.set and not hand.folded:
                    events += self._timed_out(seat) + self._set(seat, *pg.house_way_set(hand.cards), now, auto=True)
            return events + self._dealer_turn(now)
        if self.phase == "claiming":
            events = []
            for seat, hand in sorted(self.round.items()):  # out of time: claim a win, fold anything else
                if not hand.claimed and not hand.folded:
                    events += self._timed_out(seat) + self._respond(seat, hand.bonus_name is not None)
            return events + self._start_settling(now)
        if self.phase == "dealer":
            return self._start_settling(now)
        if self.phase == "settling":
            return self._settle_next(now)
        if self.phase == "clearing":
            return self._open_betting(now)
        return []

    # ------------------------------------------------------------------ the deal
    def _close_betting(self, now: float) -> list:
        events, taken = self._take_bets(now)
        if not taken:
            return events
        deck = self.deck_factory()
        hands = [deck.deal(7) for _ in range(HANDS)]
        self.start = self.rng.randint(1, HANDS)
        # Positions: 1 is the dealer, 2-7 are seats 0-5. Hand k goes to position start + k.
        order, given = [], 0
        self.round = {}
        for k in range(HANDS):
            position = (self.start - 1 + k) % HANDS + 1
            who = "dealer" if position == 1 else position - 2
            if who == "dealer":
                self.dealer_cards = hands[given]
            elif who in taken:
                self.round[who] = PlayerHand(self.seats[who].participant, taken[who], hands[given])
            else:
                who = None  # an empty seat: dealt to its place, then cleared to the rack
            order.append(who if who is None or who == "dealer" else int(who))
            given += 1
        self.dealer_front, self.dealer_back = pg.house_way_set(self.dealer_cards)
        self.dealer_shown = self.FACE_UP
        self.ace_high_push = self.FACE_UP and pg.is_ace_high_pai_gow(self.dealer_cards)
        self.phase = "dealing"
        seats = sorted(self.round)
        jackpots = [i for i in seats if taken[i]["jackpot"]]
        duration = HANDS * self.timings.deal_hand + self.timings.deal_pause
        if None in order:  # the empty seats' hands are cleared before anything else happens
            duration += self.timings.clear_empty
        if jackpots:
            duration += self.timings.jackpot_lock
        if self.FACE_UP:
            duration += self.timings.reveal
        if self.ace_high_push:
            duration += self.timings.ace_high
        self.deadline = now + duration
        events.append({"kind": "bets_closed", "seats": seats, "jackpots": jackpots,
                       "_paid": [self.seats[i].participant for i in seats]})
        dealt = {"kind": "dealt", "start": self.start, "order": order, "interval": self.timings.deal_hand,
                 "_private": {i: {"cards": _codes(h.cards)} for i, h in self.round.items()}}
        if self.FACE_UP:
            dealt["dealer"] = self._dealer_state()
            dealt["ace_high"] = self.ace_high_push  # nobody sets a hand: they claim or fold instead
        events.append(dealt)
        if self.ace_high_push:
            events.append({"kind": "ace_high_pai_gow"})
            events += say(self.lines.say("pai_gow", "ace_high_push"))
        elif self.FACE_UP:
            labels = _labels(self.dealer_front, self.dealer_back)
            events += say(self.lines.say("pai_gow", "dealer_set", high=labels["back_label"], low=labels["front_label"]))
        return events

    # ------------------------------------------------------------------ claiming (Face Up, Ace-high push)
    def _open_claims(self, now: float) -> list:
        self.phase = "claiming"
        self.deadline = now + self.timings.claim
        self._work_out_bonuses()
        private = {}
        for seat, hand in self.round.items():
            hand.bonus_name = self._winning_bonus(hand)
            private[seat] = {"bonus": hand.bonus_name}
        return [{"kind": "claim_open", "seconds": self.timings.claim, "seats": sorted(self.round), "_private": private}]

    @staticmethod
    def _winning_bonus(hand: PlayerHand) -> str | None:
        """The bonus hand a player can claim, if their side bets win anything."""
        b = hand.bonus
        if b and b.tier and (b.fortune_return or b.jackpot_fixed or b.jackpot_share):
            return pg.TIER_NAMES[b.tier]
        return None

    def claim(self, seat: int, now: float) -> list:
        hand = self._claiming_hand(seat)
        self._box_first(seat)
        if hand.bonus_name is None:
            raise TableError("There's no bonus to claim -- fold.")
        return self._respond(seat, True) + self._after_claims(now)

    def _claiming_hand(self, seat: int) -> PlayerHand:
        hand = self.round.get(seat)
        if hand is None or hand.participant is not self.seats[seat].participant:
            raise TableError("You're not in this hand.")
        if hand.claimed or hand.folded:
            raise TableError("You've already decided.")
        return hand

    def _respond(self, seat: int, claim: bool) -> list:
        hand = self.round[seat]
        hand.claimed, hand.folded = claim, not claim
        return [{"kind": "claimed", "seat": seat, "claimed": claim}]

    def _after_claims(self, now: float) -> list:
        if self.phase == "claiming" and all(h.claimed or h.folded for h in self.round.values()):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return self._reveal_boxes()

    def _dealer_state(self) -> dict:
        return {"cards": _codes(self.dealer_cards), "front": _codes(self.dealer_front),
                "back": _codes(self.dealer_back), **_labels(self.dealer_front, self.dealer_back)}

    # ------------------------------------------------------------------ setting
    def _hand_for(self, seat: int) -> PlayerHand:
        if self.phase != "setting":
            raise TableError("It's not time to set your hand.")
        hand = self.round.get(seat)
        if hand is None or hand.participant is not self.seats[seat].participant:
            raise TableError("You're not in this hand.")
        if hand.set or hand.folded:
            raise TableError("You've already set your hand.")
        return hand

    def set_hand(self, seat: int, front_codes: list, back_codes: list, now: float) -> list:
        hand = self._hand_for(seat)
        self._box_first(seat)
        if len(front_codes) != 2 or len(back_codes) != 5:
            raise TableError("Set 2 cards in your Low hand and 5 in your High hand.")
        front = _cards_from(front_codes, hand.cards)
        back = _cards_from(back_codes, [c for c in hand.cards if c not in front])
        if pg.is_foul(front, back):
            raise TableError("Your High hand has to beat your Low hand.")
        return self._set(seat, front, back, now) + self._after_setting(now)

    def fold(self, seat: int, now: float) -> list:
        if not self.FACE_UP:
            raise TableError("You can't fold at this table.")
        if self.phase == "claiming":
            self._claiming_hand(seat)
            self._box_first(seat)
            return self._respond(seat, False) + self._after_claims(now)
        hand = self._hand_for(seat)
        self._box_first(seat)
        hand.folded = True
        return [{"kind": "hand_set", "seat": seat, "folded": True}] + self._after_setting(now)

    def _set(self, seat: int, front, back, now: float, auto: bool = False) -> list:
        hand = self.round[seat]
        hand.front, hand.back, hand.set, hand.auto = list(front), list(back), True, auto
        event = {"kind": "hand_set", "seat": seat, "folded": False,
                 "_private": {seat: {"front": _codes(front), "back": _codes(back), **_labels(front, back)}}}
        if auto:
            event["auto"] = True
        return [event]

    def _after_setting(self, now: float) -> list:
        """Everyone has set (or folded): the timer ends early."""
        if self.phase == "setting" and all(h.set or h.folded for h in self.round.values()):
            end = now + self.timings.last_decision
            if self.deadline is None or end < self.deadline:
                self.deadline = end
        return self._reveal_boxes()

    def _box_private(self, seat: int) -> dict:
        hand = self.round[seat]
        private = {"cards": _codes(hand.cards)}
        if self.phase == "claiming":
            private["bonus"] = hand.bonus_name
        return private

    def suggest(self, seat: int) -> dict:
        """The House Way for a player's own cards (the House Way button)."""
        hand = self.round.get(seat)
        if hand is None or self.phase != "setting" or not self._box_shown(seat):
            raise TableError("There's no hand to set.")
        front, back = pg.house_way_set(hand.cards)
        return {"front": _codes(front), "back": _codes(back), **_labels(front, back)}

    def check(self, seat: int, front_codes: list, back_codes: list) -> dict:
        """Names a proposed split and says if it fouls (the sorter's live readout)."""
        hand = self.round.get(seat)
        if hand is None or not self._box_shown(seat):
            raise TableError("There's no hand to set.")
        result = {"front": front_codes, "back": back_codes, "front_label": "", "back_label": "", "foul": False}
        front = _cards_from(front_codes, hand.cards)
        back = _cards_from(back_codes, [c for c in hand.cards if c not in front])
        if len(front) == 2:
            result["front_label"] = pg.two_card_label(pg.evaluate_two_card_hand(front))
        if len(back) == 5:
            result["back_label"] = pg.five_card_label(pg.evaluate_five(back))
        if len(front) == 2 and len(back) == 5:
            result["foul"] = pg.is_foul(front, back)
        return result

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        """Getting up before setting: House Way sets the hand (the money's down)."""
        hand = self.round.get(seat)
        if hand is None or hand.participant is not self.seats[seat].participant:
            return []
        if self.phase == "setting" and not hand.set and not hand.folded:
            return self._set(seat, *pg.house_way_set(hand.cards), now, auto=True) + self._after_setting(now)
        return []

    # ------------------------------------------------------------------ the dealer and settling
    def _dealer_turn(self, now: float) -> list:
        if self.FACE_UP:
            return self._start_settling(now)
        self.phase = "dealer"
        self.dealer_shown = True
        self.deadline = now + self.timings.dealer_set
        labels = _labels(self.dealer_front, self.dealer_back)
        line = self.lines.say("pai_gow", "dealer_set", high=labels["back_label"], low=labels["front_label"])
        return [{"kind": "dealer_set", **self._dealer_state()}] + say(line)

    def _start_settling(self, now: float) -> list:
        self.phase = "settling"
        self._work_out_bonuses()
        # Folded hands are swept first, straight away, then the rest settle from third base.
        self._settle_queue = sorted(self.round, key=lambda seat: (not self.round[seat].folded, -seat))
        return self._settle_next(now)

    def _work_out_bonuses(self):
        """Fortune and Jackpot off each player's own seven cards; the Envy
        Bonus off everyone else's (Fortune bet of £5+). A folded hand is mucked
        unseen: it neither collects Envy nor triggers it for anyone else."""
        for hand in self.round.values():
            hand.bonus = pg.bonus(hand.cards, hand.bets["fortune"], hand.bets["jackpot"])
        self._envy = {}
        tiers = {seat: h.bonus.tier for seat, h in self.round.items() if not h.folded}
        for seat, hand in self.round.items():
            if hand.bets["fortune"] >= pg.ENVY_MIN_FORTUNE and not hand.folded:
                self._envy[seat] = sum(pg.ENVY_BONUS.get(t, 0) for other, t in tiers.items() if other != seat and t)

    def _settle_next(self, now: float) -> list:
        if not self._settle_queue:
            self.phase = "clearing"
            self.deadline = now + self.timings.clear
            return [{"kind": "round_end"}]
        seat = self._settle_queue.pop(0)
        hand = self.round[seat]
        hand.settled = True
        events, steps, returned = [], [], 0
        ante = hand.bets["ante"]
        if self.ace_high_push:
            outcome, ante_back, fee, front_win, back_win = "push", ante, 0, False, False
        elif hand.folded:
            outcome, ante_back, fee, front_win, back_win = "fold", 0, 0, False, False
        else:
            r = pg.settle_ante(hand.front, hand.back, self.dealer_front, self.dealer_back, ante,
                               commission=self.game == pg.FORTUNE)
            outcome, ante_back, fee, front_win, back_win = r.outcome, r.returned, r.commission, r.front_win, r.back_win
        steps.append(self._step("ante", ante, ante_back))
        returned += ante_back
        b = hand.bonus
        mucked = hand.folded  # folded hands are mucked unseen: every bet on them is simply lost
        if mucked:
            b = pg.Bonus()
        if hand.bets["fortune"]:
            steps.append(self._step("fortune", hand.bets["fortune"], b.fortune_return))
            returned += b.fortune_return
        if hand.bets["jackpot"]:
            jackpot_back = b.jackpot_fixed
            if b.jackpot_share and self.jackpot:
                jackpot_back = self.jackpot.win() if b.jackpot_share >= 1.0 else self.jackpot.take(b.jackpot_share)
                events.append({"kind": "jackpot_won", "seat": seat, "amount": jackpot_back, "name": hand.participant.name})
            steps.append(self._step("jackpot", hand.bets["jackpot"], jackpot_back, flat=True))
            returned += jackpot_back
        envy = self._envy.get(seat, 0)
        if envy:
            steps.append({"spot": "envy", "action": "pay", "amount": 0, "payout": envy})
            returned += envy
        hand.participant.credit(returned, outcome)
        steps.sort(key=lambda s: s["action"] != "collect")
        t = self.timings
        self.deadline = now + (t.fold_sweep if mucked else t.settle_base + 2 * t.settle_pause + t.settle_step * len(steps))
        event = {"kind": "settle_seat", "seat": seat, "outcome": outcome, "front_win": front_win, "back_win": back_win,
                 "commission": fee, "cards": [] if mucked else _codes(hand.cards),
                 "tier": pg.TIER_NAMES.get(b.tier) if b.tier else None,
                 "steps": steps, "total_returned": returned, "pause": t.settle_pause, "_paid": [hand.participant]}
        if hand.set:
            event.update(front=_codes(hand.front), back=_codes(hand.back), **_labels(hand.front, hand.back))
        key = {"win": "win", "lose": "lose", "push": "push", "fold": "fold"}[outcome]
        if self.ace_high_push:
            key = "ace_high"
        hands = {"high": event["back_label"], "low": event["front_label"]} if hand.set else {}
        event["say"] = self.lines.say("pai_gow", f"settle_{key}", name=hand.participant.name,
                                      tier=event["tier"] or "", **hands)
        return events + [event]

    @staticmethod
    def _step(spot: str, bet: int, back: int, flat: bool = False) -> dict:
        if back == 0:
            return {"spot": spot, "action": "collect", "amount": bet}
        if back == bet and not flat:
            return {"spot": spot, "action": "push", "amount": bet}
        return {"spot": spot, "action": "pay", "amount": bet, "payout": back if flat else back - bet}

    def _open_betting(self, now: float) -> list:
        self.round = {}
        self.dealer_cards, self.dealer_front, self.dealer_back = [], [], []
        self.dealer_shown = self.ace_high_push = False
        self._settle_queue = []
        return self._reopen_betting(now)

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        seats = []
        for i, s in enumerate(self.seats):
            seats.append(None if s.participant is None else {**self._seat_entry(i, s), "hand": None})
        for i, hand in self.round.items():
            entry = seats[i]
            if entry is None or entry["entity"] != hand.participant.entity_id:
                continue
            entry["bets"] = dict(hand.bets)
            state = "folded" if hand.folded else "claimed" if hand.claimed else "set" if hand.set else "dealt"
            entry["hand"] = None if hand.settled else {"state": state}
            if self._sees(viewer, i) and not hand.settled:
                entry["hand"]["cards"] = _codes(hand.cards)
                if self.phase == "claiming":
                    entry["hand"]["bonus"] = hand.bonus_name
                if hand.set:
                    entry["hand"].update(front=_codes(hand.front), back=_codes(hand.back), **_labels(hand.front, hand.back))
        dealer = {"cards": [], "shown": False}
        if self.dealer_cards:
            dealer = {**self._dealer_state(), "shown": True} if self.dealer_shown else {"cards": ["??"] * 7, "shown": False}
        return {"game": self.game, "phase": self.phase, "seats": seats, "dealer": dealer, "start": self.start,
                "face_up": self.FACE_UP, "timer": self._timer(now, ("betting", "setting", "claiming")), "my_seat": viewer}


class FortunePaiGowMachine(PaiGowMachine):
    game = pg.FORTUNE
    FACE_UP = False


class FaceUpPaiGowMachine(PaiGowMachine):
    game = pg.FACE_UP
    FACE_UP = True
