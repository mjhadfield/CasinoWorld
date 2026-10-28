"""
A slot cabinet: one seat, one variant (slots/variants), the shared progressives.

  idle          Spin (or Buy Bonus) whenever you like; a new spin may cut the last one's
                presentation short after `min_spin` (quick stop / skip).
  spinning      A paid spin that triggered something is being shown; its features follow:
  jackpot_pick  12 coins; each pick reveals the next of a sequence drawn up front. Picks
                itself when you're idle.
  trail         The Trail Bonus: FIRE moves the armadillo; fires itself after `trail_auto`.
  free_games    Three Combo Free Games, played by the clock (or as many as a battle's ships gave, a voyage bought or an
                expedition found).
  battle        The wave battle (Red Alert): tap a ship to fire (battle_fire); fires itself after `battle_auto`.
                Free spins its ships give follow it as Combo Free Games.
  voyage        The island voyage (Dead Man's Map): choose the next island, or a deal at Port Royal (voyage_choose);
                chooses itself after `voyage_auto`. Free games bought follow it as Combo Free Games.
  expedition    The expedition (Delta Quadrant): choose a route, then a planet in each sector, and a second one when a
                Shuttle is out (expedition_choose); chooses itself after `expedition_auto`. Free games found follow it.

Which bonus a scatter or Buy Bonus plays comes from the variant's routes (one of several at random).
  summary       A beat to show what a feature paid, then the next feature or idle.

A paid spin is debited, its outcome drawn and its win credited at once (the client holds the
balance until the reels stop); a feature's win is credited when it ends. Everything about a
cabinet lasts only while its player sits there: standing up (or disconnecting) mid-feature
plays the rest out at once and pays it, and the next player finds a fresh cabinet. Only the
progressive meters persist (slots/jackpots.py).
"""
from dataclasses import dataclass

from casino_server.dealer import DealerLines
from casino_server.slots import base, bonuses, jackpots
from casino_server.slots.stats import SlotStats
from casino_server.slots.outcome import pick_bonus, presentation_seconds, spin_outcome
from casino_server.slots.rng import fresh
from casino_server.slots.variants import VARIANTS
from casino_server.tables.base import TableError, TableMachine

GAME_KEY = "slots"


@dataclass
class Timings:
    betting: float = 0.0          # (shared fields every table's Timings has; unused here)
    betting_npc_only: float = 0.0
    min_betting: float = 0.0
    rebet: float = 0.0
    min_spin: float = 1.0         # a spin can cut the last one's presentation short after this
    present: float = 1.0          # scales how long the screen takes to show a spin or a roll
    pick_idle: float = 15.0       # the Jackpot Pick picks for you after this...
    pick_auto: float = 1.0        # ...then one coin a second
    pick_reveal: float = 0.4
    celebrate: float = 4.0        # a jackpot won
    trail_intro: float = 2.2
    trail_auto: float = 6.0       # FIRE fires itself after this
    free_intro: float = 2.2
    battle_intro: float = 2.6
    battle_auto: float = 8.0      # it fires itself after this
    voyage_intro: float = 2.6
    voyage_auto: float = 12.0     # it chooses for you after this
    expedition_intro: float = 2.6
    expedition_auto: float = 12.0  # it chooses for you after this
    free_gap: float = 0.9
    summary: float = 5.0          # a feature's total on screen (it collects itself)
    idle_stand: float = 300.0     # a player who does nothing this long is stood up

    def scaled(self, factor: float) -> "Timings":
        return Timings(**{name: getattr(self, name) * factor for name in self.__dataclass_fields__})

    @classmethod
    def instant(cls) -> "Timings":
        return cls(**{name: 0.0 for name in cls.__dataclass_fields__})


def outcome_view(o: dict) -> dict:
    """A spin as clients get it (everything the screen plays, in order)."""
    return {k: o[k] for k in ("bet", "free", "stops", "landed", "after_colossal", "pre_grid", "grid", "trigger",
                              "colossal", "wild_reels", "wilds", "multiplier", "upgrade", "wins", "line_win",
                              "repeat", "instant", "total", "features")} | {"scatters": o["scatters"]}


class SlotMachine(TableMachine):
    game = GAME_KEY
    label = "Slots"
    SPOTS = ()
    DEALER = False           # no rostered dealer (dealers.py skips it)
    QUEUE_BETS = False
    BETTING_PHASES = ()

    def __init__(self, table_id: str, seats: int = 1, timings: Timings | None = None, jackpot=None,
                 deck_factory=None, lines: DealerLines | None = None, variant: str = "armadillo",
                 progressives: jackpots.SlotProgressives | None = None, stats: SlotStats | None = None, rng=None):
        super().__init__(table_id, 1, timings or Timings(), jackpot, lines or DealerLines())
        self.variant = VARIANTS[variant]
        self.progressives = progressives or jackpots.SlotProgressives(None)
        self.stats = stats or SlotStats(None)
        self.rng = rng or fresh()
        self.rig: dict = {}      # tests and the dev rig: forced features/trigger/jackpot/stops for the next spin
        self._reset_session()
        self.phase = "idle"

    def _reset_session(self):
        self.bet = base.LADDER[3]
        self.last: dict | None = None        # the last spin shown
        self.pending: list = []              # features still to come: ("pick", tier) | (bonus, bet, bought[, free games, source])
        self.pick: dict | None = None
        self.trail: dict | None = None
        self.trail_ready_at = 0.0
        self.free: dict | None = None
        self.battle: dict | None = None
        self.battle_ready_at = 0.0
        self.voyage: dict | None = None
        self.voyage_ready_at = 0.0
        self.expedition: dict | None = None
        self.expedition_ready_at = 0.0
        self.spun_at = -1e9
        self.last_action = 0.0

    def rules(self) -> dict:
        v = self.variant
        return {"game": GAME_KEY, "variant": v.id, "name": v.name, "symbols": v.symbols, "lines": base.LINES,
                "pays": {k: list(p) for k, p in v.pays.items()}, "upgrades": v.upgrades, "ladder": base.LADDER,
                "features": v.features, "art": v.art, "theme": v.theme,
                "strips": v.strips, "free_strips": v.free_strips, "big_strip": v.big_strip, "buy_cost": v.buy_cost,
                "free_games": v.free_games, "routes": v.routes, "battle": v.battle, "voyage": v.voyage, "expedition": v.expedition, "tiers": [{k: t[k] for k in ("id", "name", "seed")} for t in jackpots.TIERS],
                "seats": 1}

    # ------------------------------------------------------------------ seating
    def sit(self, seat: int, participant, now: float) -> list:
        events = super().sit(seat, participant, now)
        self._reset_session()
        self.phase = "idle"
        self.last_action = now
        self._idle_deadline(now)
        return events

    def _leaving_mid_hand(self, seat: int, now: float, reason: str) -> list:
        """Whatever's still to come is played out now and paid."""
        return self._finish_everything(now)

    def _after_stand(self, seat: int, now: float) -> list:
        self._reset_session()
        self.phase = "idle"
        self.deadline = None
        return []

    def _player(self):
        p = self.seats[0].participant
        if p is None:
            raise TableError("Sit down first.")
        return p

    def _idle_deadline(self, now: float):
        p = self.seats[0].participant
        self.deadline = now + self.timings.idle_stand if p is not None and p.is_human and self.timings.idle_stand > 0 else None

    def _ledger(self, amount: int) -> dict | None:
        """The ledger's detail for a money move here: which machine (none on a 0, so a losing spin stays one row)."""
        return {"machine": self.variant.id} if amount else None

    # ------------------------------------------------------------------ actions
    def spin(self, seat: int, bet: int, now: float) -> list:
        p = self._player()
        if self.phase not in ("idle", "spinning") or self.pending:
            raise TableError("Finish your bonus first.")
        if now < self.spun_at + self.timings.min_spin:
            raise TableError("The reels are still spinning.")
        bet = self._check_bet(bet)
        if not p.debit(bet, "spin", self._ledger(bet)):
            raise TableError("Not enough credit for that bet.")
        self.bet, self.last_action = bet, now
        self.progressives.contribute(bet)
        rig, self.rig = self.rig, {}
        o = spin_outcome(self.variant, bet, self.rng, rig={k: rig[k] for k in ("features", "trigger", "stops") if rig.get(k)})
        tier = rig.get("jackpot") or jackpots.trigger(bet, self.rng)
        p.credit(o["total"], "spin win", self._ledger(o["total"]))
        self._count(p, spins=1, staked=bet, returned=o["total"])
        self.last, self.spun_at = o, now
        if tier:
            self.pending.append(("pick", tier))
        if o["trigger"]:
            self.pending.append((o["trigger"], bet, False))
        secs = presentation_seconds(o) * self.timings.present
        event = {"kind": "spin", "seat": 0, "outcome": outcome_view(o), "meters": self.progressives.amounts(), "rates": self.progressives.rates(),
                 "secs": round(secs, 2), "features_next": [f[0] for f in self.pending], "_paid": [p]}
        if self.pending:
            self.phase, self.deadline = "spinning", now + secs
        else:
            self.phase = "idle"
            self._idle_deadline(now)
        return [event]

    def buy_bonus(self, seat: int, bet: int, now: float) -> list:
        p = self._player()
        if self.phase != "idle" or self.pending:
            raise TableError("Finish what's on screen first.")
        if not self.variant.buy_cost or not self.variant.routes.get("buy"):
            raise TableError("This machine has no Buy Bonus.")
        bet = self._check_bet(bet)
        cost = bet * self.variant.buy_cost
        if not p.debit(cost, "buy bonus", self._ledger(cost)):
            raise TableError("Not enough credit to buy the bonus.")
        self._count(p, staked=cost)
        self.bet, self.last_action = bet, now
        self.pending.append((pick_bonus(self.rng, self.variant.routes["buy"]), bet, True))
        return [{"kind": "bonus_bought", "seat": 0, "bet": bet, "cost": cost, "_paid": [p]}] + self._next_feature(now)

    def trail_fire(self, seat: int, now: float) -> list:
        self._player()
        if self.phase != "trail" or self.trail is None:
            raise TableError("There's no trail to fire on.")
        if now < self.trail_ready_at:
            raise TableError("Wait for the armadillo.")
        self.last_action = now
        return self._fire(now)

    def battle_fire(self, seat: int, index, now: float) -> list:
        self._player()
        if self.phase != "battle" or self.battle is None:
            raise TableError("There's no battle on.")
        if now < self.battle_ready_at:
            raise TableError("Wait for the last shot.")
        st = self.battle
        if st["boss_hp"] is None:
            try:
                index = int(index)
            except (TypeError, ValueError):
                raise TableError("Pick a ship.")
            if not 0 <= index < len(st["ships"]) or not st["ships"][index]:
                raise TableError("Pick another ship.")
        self.last_action = now
        return self._shoot(now, index)

    def voyage_choose(self, seat: int, choice, now: float) -> list:
        self._player()
        if self.phase != "voyage" or self.voyage is None:
            raise TableError("There's no voyage on.")
        if now < self.voyage_ready_at:
            raise TableError("Wait for the ship.")
        if isinstance(choice, float) and choice.is_integer():
            choice = int(choice)
        if isinstance(choice, bool) or choice not in bonuses.voyage_options(self.variant, self.voyage):
            raise TableError("Choose one of the open islands." if self.voyage["awaiting"] == "sail" else "Choose a deal, or leave.")
        self.last_action = now
        return self._sail(now, choice)

    def expedition_choose(self, seat: int, choice, now: float) -> list:
        self._player()
        if self.phase != "expedition" or self.expedition is None:
            raise TableError("There's no expedition on.")
        if now < self.expedition_ready_at:
            raise TableError("Wait for the ship.")
        if isinstance(choice, float) and choice.is_integer():
            choice = int(choice)
        if isinstance(choice, bool) or choice not in bonuses.expedition_options(self.variant, self.expedition):
            raise TableError("Choose a route." if self.expedition["awaiting"] == "route" else "Choose a planet to explore.")
        self.last_action = now
        return self._explore(now, choice)

    def jackpot_pick(self, seat: int, index: int, now: float) -> list:
        self._player()
        if self.phase != "jackpot_pick" or self.pick is None:
            raise TableError("There's no Jackpot Pick on.")
        try:
            index = int(index)
        except (TypeError, ValueError):
            raise TableError("Pick a coin.")
        if not 0 <= index < jackpots.BOARD or self.pick["coins"][index] is not None:
            raise TableError("Pick another coin.")
        self.last_action = now
        return self._reveal(index, now)

    def _check_bet(self, bet) -> int:
        try:
            bet = int(bet)
        except (TypeError, ValueError):
            raise TableError("Pick a bet.")
        if bet not in base.LADDER:
            raise TableError("That isn't one of this machine's bets.")
        return bet

    # ------------------------------------------------------------------ the clock
    def _advance(self, now: float) -> list:
        if self.phase in ("spinning", "summary"):
            return self._next_feature(now)
        if self.phase == "jackpot_pick":
            if self.pick["done"]:
                return self._next_feature(now)
            return self._reveal(self.pick["coins"].index(None), now, auto=True)
        if self.phase == "trail":
            return self._fire(now)
        if self.phase == "free_games":
            return self._free_game(now)
        if self.phase == "battle":
            return self._shoot(now, None, auto=True)
        if self.phase == "voyage":
            return self._sail(now, None, auto=True)
        if self.phase == "expedition":
            return self._explore(now, None, auto=True)
        if self.phase == "idle" and self.seats[0].participant is not None and self.seats[0].participant.is_human:
            if now >= self.last_action + self.timings.idle_stand:
                return self.stand(0, now, reason="idle")
            self._idle_deadline(now)
        return []

    def _count(self, p, **counts):
        self.stats.record(self.variant.id, p.is_human, **counts)

    def _count_bonus(self):
        p = self.seats[0].participant
        if p is not None:
            self._count(p, bonuses=1)

    def _next_feature(self, now: float) -> list:
        self.pick = self.trail = self.free = self.battle = self.voyage = self.expedition = None
        if not self.pending:
            self.phase = "idle"
            self._idle_deadline(now)
            return [{"kind": "features_done", "seat": 0}]
        step = self.pending.pop(0)
        if step[0] == "pick":
            self.phase = "jackpot_pick"
            seq = jackpots.pick_sequence(step[1], self.rng)
            self.pick = {"tier": step[1], "seq": seq["seq"], "rest": seq["rest"], "step": 0,
                         "coins": [None] * jackpots.BOARD, "done": False}
            self.deadline = now + self.timings.pick_idle
            return [{"kind": "jackpot_start", "seat": 0, "coins": jackpots.BOARD}]
        if step[0] == "trail":
            _, bet, bought = step
            self._count_bonus()
            self.phase = "trail"
            self.trail = bonuses.trail_start(self.variant, bet, self.rng)
            self.trail_ready_at = now + self.timings.trail_intro
            self.deadline = now + self.timings.trail_intro + self.timings.trail_auto
            return [{"kind": "trail_start", "seat": 0, "bought": bought, "trail": bonuses.trail_view(self.trail)}]
        if step[0] == "battle":
            _, bet, bought = step
            self._count_bonus()
            self.phase = "battle"
            self.battle = bonuses.battle_start(self.variant, bet)
            self.battle_ready_at = now + self.timings.battle_intro
            self.deadline = now + self.timings.battle_intro + self.timings.battle_auto
            return [{"kind": "battle_start", "seat": 0, "bought": bought, "battle": bonuses.battle_view(self.battle)}]
        if step[0] == "voyage":
            _, bet, bought = step
            self._count_bonus()
            self.phase = "voyage"
            self.voyage = bonuses.voyage_start(self.variant, bet, self.rng)
            self.voyage_ready_at = now + self.timings.voyage_intro
            self.deadline = now + self.timings.voyage_intro + self.timings.voyage_auto
            return [{"kind": "voyage_start", "seat": 0, "bought": bought, "voyage": bonuses.voyage_view(self.variant, self.voyage)}]
        if step[0] == "expedition":
            _, bet, bought = step
            self._count_bonus()
            self.phase = "expedition"
            self.expedition = bonuses.expedition_start(self.variant, bet, self.rng)
            self.expedition_ready_at = now + self.timings.expedition_intro
            self.deadline = now + self.timings.expedition_intro + self.timings.expedition_auto
            return [{"kind": "expedition_start", "seat": 0, "bought": bought,
                     "expedition": bonuses.expedition_view(self.variant, self.expedition)}]
        self.phase = "free_games"
        source = step[4] if len(step) > 4 else "scatter"   # or free games a battle, voyage or expedition gave
        if source == "scatter":
            self._count_bonus()
        self.free = {"bet": step[1], "n": 0, "of": step[3] if len(step) > 3 else self.variant.free_games, "total": 0}
        self.deadline = now + self.timings.free_intro
        return [{"kind": "free_start", "seat": 0, "of": self.free["of"], "bet": step[1], "bought": step[2], "source": source}]

    # ------------------------------------------------------------------ the Jackpot Pick
    def _reveal(self, index: int, now: float, auto: bool = False) -> list:
        pk = self.pick
        tier = pk["seq"][pk["step"]]
        pk["step"] += 1
        pk["coins"][index] = tier
        events = [{"kind": "jackpot_reveal", "seat": 0, "index": index, "tier": tier, "auto": auto}]
        if pk["step"] < len(pk["seq"]):
            self.deadline = now + (self.timings.pick_auto if auto else self.timings.pick_idle)
            return events
        pk["done"] = True
        p = self.seats[0].participant
        amount = self.progressives.win(tier)
        p.credit(amount, f"{tier} jackpot", self._ledger(amount))
        self._count(p, returned=amount, jackpots=1)
        rest = list(pk["rest"])
        for i, c in enumerate(pk["coins"]):
            if c is None:
                pk["coins"][i] = rest.pop(0) if rest else tier
        events.append({"kind": "slot_jackpot_won", "seat": 0, "tier": tier, "amount": amount, "name": p.name,
                       "coins": pk["coins"], "meters": self.progressives.amounts(), "rates": self.progressives.rates(), "_paid": [p]})
        self.deadline = now + self.timings.pick_reveal + self.timings.celebrate
        return events

    # ------------------------------------------------------------------ the Trail Bonus
    def _fire(self, now: float) -> list:
        st = self.trail
        roll = bonuses.trail_roll(self.variant, st, self.rng)
        secs = bonuses.trail_roll_seconds(roll) * self.timings.present
        events = [{"kind": "trail_roll", "seat": 0, "roll": roll, "total": st["total"], "hearts": st["hearts"],
                   "upgraded": st["upgraded"], "doubled": st["doubled"], "secs": round(secs, 2)}]
        if not st["done"]:
            self.trail_ready_at = now + secs
            self.deadline = now + secs + self.timings.trail_auto
            return events
        p = self.seats[0].participant
        p.credit(st["total"], "trail bonus", self._ledger(st["total"]))
        self._count(p, returned=st["total"])
        events.append({"kind": "trail_end", "seat": 0, "total": st["total"], "prizepot": st["pos"] >= len(st["board"]) - 1,
                       "rolls": st["rolls"], "_paid": [p]})
        self.phase, self.deadline = "summary", now + secs + self.timings.summary
        return events

    # ------------------------------------------------------------------ Combo Free Games
    def _free_game(self, now: float) -> list:
        fg = self.free
        o = spin_outcome(self.variant, fg["bet"], self.rng, free=True)
        fg["n"] += 1
        fg["total"] += o["total"]
        secs = presentation_seconds(o) * self.timings.present
        events = [{"kind": "free_game", "seat": 0, "n": fg["n"], "of": fg["of"], "outcome": outcome_view(o),
                   "total": fg["total"], "secs": round(secs, 2)}]
        if fg["n"] < fg["of"]:
            self.deadline = now + secs + self.timings.free_gap
            return events
        p = self.seats[0].participant
        p.credit(fg["total"], "free games", self._ledger(fg["total"]))
        self._count(p, returned=fg["total"])
        events.append({"kind": "free_end", "seat": 0, "total": fg["total"], "_paid": [p]})
        self.phase, self.deadline = "summary", now + secs + self.timings.summary
        return events

    # ------------------------------------------------------------------ the wave battle
    def _shoot(self, now: float, target, auto: bool = False) -> list:
        st = self.battle
        shot = bonuses.battle_shot(self.variant, st, self.rng, target)
        secs = bonuses.battle_shot_seconds(shot) * self.timings.present
        events = [{"kind": "battle_shot", "seat": 0, "shot": shot, "total": st["total"], "spins": st["spins"],
                   "shields": st["shields"], "auto": auto, "secs": round(secs, 2)}]
        if not st["done"]:
            self.battle_ready_at = now + secs
            self.deadline = now + secs + self.timings.battle_auto
            return events
        p = self.seats[0].participant
        p.credit(st["total"], "battle bonus", self._ledger(st["total"]))
        self._count(p, returned=st["total"])
        events.append({"kind": "battle_end", "seat": 0, "total": st["total"], "spins": st["spins"], "cleared": st["cleared"],
                       "won": st["won"], "shots": st["shots"], "_paid": [p]})
        if st["spins"]:
            self.pending.insert(0, ("free", st["bet"], False, st["spins"], "battle"))
        self.phase, self.deadline = "summary", now + secs + self.timings.summary
        return events

    # ------------------------------------------------------------------ the island voyage
    def _sail(self, now: float, choice, auto: bool = False) -> list:
        st = self.voyage
        step = bonuses.voyage_step(self.variant, st, self.rng, choice)
        secs = bonuses.voyage_step_seconds(step) * self.timings.present
        events = [{"kind": "voyage_step", "seat": 0, "step": step, "voyage": bonuses.voyage_view(self.variant, st), "auto": auto,
                   "secs": round(secs, 2)}]
        if not st["done"]:
            self.voyage_ready_at = now + secs
            self.deadline = now + secs + self.timings.voyage_auto
            return events
        p = self.seats[0].participant
        p.credit(st["total"], "voyage bonus", self._ledger(st["total"]))
        self._count(p, returned=st["total"])
        events.append({"kind": "voyage_end", "seat": 0, "total": st["total"], "spins": st["spins"], "sunk": st["sunk"],
                       "treasure": st["treasure"], "steps": st["steps"], "_paid": [p]})
        if st["spins"]:
            self.pending.insert(0, ("free", st["bet"], False, st["spins"], "voyage"))
        self.phase, self.deadline = "summary", now + secs + self.timings.summary
        return events

    # ------------------------------------------------------------------ the expedition
    def _explore(self, now: float, choice, auto: bool = False) -> list:
        st = self.expedition
        step = bonuses.expedition_step(self.variant, st, self.rng, choice)
        secs = bonuses.expedition_step_seconds(step) * self.timings.present
        events = [{"kind": "expedition_step", "seat": 0, "step": step, "expedition": bonuses.expedition_view(self.variant, st),
                   "auto": auto, "secs": round(secs, 2)}]
        if not st["done"]:
            self.expedition_ready_at = now + secs
            self.deadline = now + secs + self.timings.expedition_auto
            return events
        p = self.seats[0].participant
        p.credit(st["total"], "expedition bonus", self._ledger(st["total"]))
        self._count(p, returned=st["total"])
        events.append({"kind": "expedition_end", "seat": 0, "total": st["total"], "spins": st["spins"], "ended": st["ended"],
                       "wormhole": st["wormhole"], "final": st["final"], "mult": st["mult"], "steps": st["steps"], "_paid": [p]})
        if st["spins"]:
            self.pending.insert(0, ("free", st["bet"], False, st["spins"], "expedition"))
        self.phase, self.deadline = "summary", now + secs + self.timings.summary
        return events

    # ------------------------------------------------------------------ walking away mid-feature
    def _finish_everything(self, now: float) -> list:
        """Plays out the feature on screen and everything queued after it, paying as it goes."""
        events = []
        for _ in range(20):
            if self.phase == "jackpot_pick" and self.pick and not self.pick["done"]:
                while not self.pick["done"]:
                    events += self._reveal(self.pick["coins"].index(None), now, auto=True)
            elif self.phase == "trail" and self.trail and not self.trail["done"]:
                while not self.trail["done"]:
                    events += self._fire(now)
            elif self.phase == "battle" and self.battle and not self.battle["done"]:
                while not self.battle["done"]:
                    events += self._shoot(now, None, auto=True)
            elif self.phase == "voyage" and self.voyage and not self.voyage["done"]:
                while not self.voyage["done"]:
                    events += self._sail(now, None, auto=True)
            elif self.phase == "expedition" and self.expedition and not self.expedition["done"]:
                while not self.expedition["done"]:
                    events += self._explore(now, None, auto=True)
            elif self.phase == "free_games" and self.free and self.free["n"] < self.free["of"]:
                while self.free["n"] < self.free["of"]:
                    events += self._free_game(now)
            elif self.pending:
                events += self._next_feature(now)
            else:
                break
        return [{**e, "finished_for_you": True} for e in events]

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, viewer: int | None, now: float) -> dict:
        s = self.seats[0]
        seats = [None if s.participant is None else self._seat_entry(0, s)]
        pick = None
        if self.pick:
            pick = {"coins": self.pick["coins"], "done": self.pick["done"],
                    "tier": self.pick["tier"] if self.pick["done"] else None}
        timer = round(max(0.0, self.deadline - now), 1) if self.deadline is not None and self.phase in ("trail", "jackpot_pick", "battle", "voyage", "expedition") else None
        return {"game": self.game, "variant": self.variant.id, "phase": self.phase, "seats": seats, "bet": self.bet,
                "last": outcome_view(self.last) if self.last else None, "pending": [f[0] for f in self.pending],
                "pick": pick, "trail": bonuses.trail_view(self.trail) if self.trail else None,
                "trail_ready_in": round(max(0.0, self.trail_ready_at - now), 1) if self.trail else None,
                "battle": bonuses.battle_view(self.battle) if self.battle else None,
                "battle_ready_in": round(max(0.0, self.battle_ready_at - now), 1) if self.battle else None,
                "voyage": bonuses.voyage_view(self.variant, self.voyage) if self.voyage else None,
                "voyage_ready_in": round(max(0.0, self.voyage_ready_at - now), 1) if self.voyage else None,
                "expedition": bonuses.expedition_view(self.variant, self.expedition) if self.expedition else None,
                "expedition_ready_in": round(max(0.0, self.expedition_ready_at - now), 1) if self.expedition else None,
                "free": dict(self.free) if self.free else None, "meters": self.progressives.amounts(), "rates": self.progressives.rates(),
                "timer": timer, "my_seat": viewer}
