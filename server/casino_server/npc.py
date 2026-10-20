"""
NPCs: the casino's regulars, from the roster on the admin page (roster.py). They
arrive with a budget they're willing to lose, wander the floor, sit down and
play, and leave -- bust, done for the day, or (some of them) while they're
ahead -- then stay away for a cooldown while others take their place, so the
floor keeps changing. Every visit is logged and folded into their lifetime
figures.

The NpcDirector runs as one task in the Casino's lifespan. At a table an NPC
uses the same machine actions as a player, at a human pace, and plays by its
profile (roster.profile: archetype and modifiers):

  stakes      a unit sized to their budget; a Chaser raises it after losses, a
              Card counter at Blackjack when the count is good
  decisions   each game's strategy (Three Card Poker Q-6-4, the Blackjack chart,
              House Way, Kisenwether, the Wizard of Odds' lines, Mousseau), with
              the odd mistake for a Casual and high-variance lines for a Gambler
  side bets   more or less often by archetype
  Roulette    a habit by type (lucky numbers, the even chances, dozens, a sprinkle);
              chips go down one at a time, sometimes a late bet as the ball spins
  Craps       a style: a grinder plays the line with full odds and a couple of come
              bets, a casual player the line and Place 6 and 8, a gambler the field,
              hardways and props, and some superstitious players the dark side.
              Anyone can shoot. They only get up once nothing of theirs is stuck
              on the table (no point on, no come bets out).

NPCs never take one of the last RESERVED_FOR_HUMANS free seats at a table, so
a real player can always sit down. The craps table tries to keep MIN_CRAPS_NPCS
NPCs at it (within the floor population): it's everyone's first choice while it's
short, and if it stays short an idle NPC is sent over. Dealers are rostered too
(dealers.py).
"""
import asyncio
import random
import time
from dataclasses import dataclass, field

from casino_server import floor, roster
from casino_server.engines import baccarat as bac
from casino_server.engines import blackjack as bj
from casino_server.engines import craps as cr
from casino_server.engines import high_card_flush as hcf
from casino_server.engines import let_it_ride as lir
from casino_server.engines import mississippi_stud as ms
from casino_server.engines import pai_gow as pg
from casino_server.engines import roulette as rou
from casino_server.engines import three_card_poker as tcp
from casino_server.engines import ultimate_texas_holdem as uth
from casino_server.participants import NpcParticipant
from casino_server.slots import base as slot_base
from casino_server.slots.bonuses import expedition_auto, voyage_options
from casino_server.slots.outcome import presentation_seconds
from casino_server.tables import slot_machine as slots
from casino_server.tables.base import TableError, say
from casino_server.world import Entity

RESERVED_FOR_HUMANS = 2
MIN_CRAPS_NPCS = 2
CRAPS_TOP_UP_AFTER = 20.0   # seconds the craps table can be short before an idle NPC is sent over
FALLBACK_LOOK = "player_default"
ROULETTE_HABITS = ("numbers", "even", "dozens", "sprinkle")
BET_LEAD = 0.6  # seconds: NPC bets go down at least this long before betting closes (the director ticks every 0.2)
HILO = {"2": 1, "3": 1, "4": 1, "5": 1, "6": 1, "7": 0, "8": 0, "9": 0, "10": -1, "J": -1, "Q": -1, "K": -1, "A": -1}


@dataclass
class Npc:
    entity_id: str
    npc_id: int
    name: str
    look: str
    prof: roster.Profile
    bankroll: int
    plan: list = field(default_factory=list)  # remaining steps: "wander" | "play" | "leave"
    state: str = "new"      # walking | loitering | seated | leaving
    until: float = 0.0      # when the current walk/loiter ends
    target: str = ""
    table: str | None = None
    seat: int | None = None
    bet_at: float | None = None
    decide_at: float | None = None
    decide_for: tuple | None = None  # the Blackjack decision decide_at belongs to
    seat_attempts: int = 0
    participant: NpcParticipant | None = None
    habit: str = ""                  # Roulette: how they like to bet
    favourites: tuple = ()           # ...and their numbers
    chips: list | None = None        # Roulette: (spot, amount) still to put down this spin
    late_bet: bool = False
    craps_style: str = ""            # Craps: grinder | casual | gambler | darkside
    craps_rolls: int = 0
    slot_spins: int = 0
    # this visit
    arrived: float = 0.0             # wall-clock time
    wagered: int = 0
    returned: int = 0
    rounds: int = 0
    games: dict = field(default_factory=dict)
    in_round: bool = False           # has bets riding in the round under way
    round_start: int = 0             # bankroll as that round's betting opened
    chase: float = 1.0               # a Chaser's stake multiplier
    ended: str | None = None         # why the visit ended (it's logged once)


class NpcDirector:
    def __init__(self, casino, population: int | None = None, rng: random.Random | None = None,
                 clock=time.monotonic, pace: float = 1.0, wall=time.time):
        self.casino = casino
        self._population = population  # None: the admin page's setting
        self.rng = rng or random.Random()
        self.clock = clock
        self.wall = wall               # real time, for cooldowns and the visit log
        self.pace = pace  # scales NPC thinking/walking times (tests and quick demos use < 1)
        self.npcs: dict[str, Npc] = {}
        self._next_spawn = 0.0
        self._serial = 0
        self._craps_short_since: float | None = None

    async def run(self):
        while True:
            self.tick(self.clock())
            await asyncio.sleep(0.2)

    @property
    def population(self) -> int:
        if self._population is not None:
            return self._population
        return int(roster.settings(self.casino.store)["population"])

    def on_floor(self, npc_id: int) -> Npc | None:
        return next((n for n in self.npcs.values() if n.npc_id == npc_id), None)

    def status(self) -> dict:
        """For the admin page: who's here, doing what, with how much."""
        return {n.npc_id: {"state": n.state, "table": n.table, "bankroll": n.bankroll, "budget": n.prof.budget,
                           "rounds": n.rounds, "entity": n.entity_id} for n in self.npcs.values()}

    # ------------------------------------------------------------------ lifecycle
    def tick(self, now: float):
        dealers = getattr(self.casino, "dealers", None)
        if dealers is not None:
            dealers.tick(now)
        here = sum(1 for n in self.npcs.values() if not n.ended)
        if here < self.population and now >= self._next_spawn:
            record = self._pick_visitor()
            if record:
                self.spawn(record, now)
            self._next_spawn = now + self.rng.uniform(1.5, 5.0) * self.pace
        for npc in list(self.npcs.values()):
            self._step(npc, now)
        self._keep_craps_busy(now)

    # ------------------------------------------------------------------ the craps table
    def _craps_table(self) -> str | None:
        return next((tid for tid, r in self.casino.tables.items() if r.machine.game == cr.GAME_KEY), None)

    def npcs_at(self, table_id: str) -> int:
        """NPCs sitting at a table or on their way to a seat there."""
        return sum(1 for n in self.npcs.values() if n.table == table_id and not n.ended)

    def _keep_craps_busy(self, now: float):
        """If the craps table's been short of NPCs a while, send an idle one over."""
        table_id = self._craps_table()
        if table_id is None or self.npcs_at(table_id) >= MIN_CRAPS_NPCS:
            self._craps_short_since = None
            return
        if self._craps_short_since is None:
            self._craps_short_since = now
            return
        if now - self._craps_short_since < CRAPS_TOP_UP_AFTER * self.pace:
            return
        idle = [n for n in self.npcs.values()
                if n.state in ("loitering", "walking") and n.table is None and not n.ended]
        if idle and self._head_for_seat(self.rng.choice(idle), now, only=table_id):
            self._craps_short_since = now

    def _craps_style(self, prof: roster.Profile) -> str:
        if prof.superstitious and self.rng.random() < 0.5:
            return "darkside"
        return prof.archetype if prof.archetype in ("grinder", "casual", "gambler") else "casual"

    def _pick_visitor(self) -> dict | None:
        """An enabled punter who isn't here and isn't cooling down (Regulars more often)."""
        wall = self.wall()
        here = {n.npc_id for n in self.npcs.values()}
        free = [r for r in self.casino.store.npcs("punter")
                if r["enabled"] and r["id"] not in here and (r["cooldown_until"] or 0) <= wall]
        if not free:
            return None
        weights = [3.0 if "regular" in r["traits"] else 1.0 for r in free]
        return self.rng.choices(free, weights)[0]

    def spawn(self, record: dict, now: float) -> Npc:
        self._serial += 1
        prof = roster.profile(record, self.rng)
        look = self._look(record)
        npc = Npc(f"n{record['id']}_{self._serial}", record["id"], record["name"], look, prof, bankroll=prof.budget)
        npc.participant = NpcParticipant(npc)
        npc.arrived = self.wall()
        npc.habit = self._roulette_habit(prof)
        npc.craps_style = self._craps_style(prof)
        npc.favourites = prof.lucky or tuple(self.rng.sample(range(37), self.rng.randint(2, 4)))
        npc.plan = ["wander"] * self.rng.randint(0, 2) + ["play"] + ["wander"] * self.rng.randint(0, 1) + ["leave"]
        self.npcs[npc.entity_id] = npc
        self.casino.world.add(Entity(npc.entity_id, "npc", npc.name, look), at=floor.ENTRANCE)
        self._next_step(npc, now)
        return npc

    def _look(self, record: dict) -> str:
        looks = getattr(self.casino, "looks", None)
        if looks is None:
            return FALLBACK_LOOK
        try:
            return looks.ensure(record["look"])
        except Exception as e:   # a look that can't be built mustn't stop them coming in
            print(f"NPC {record['name']}: look not built ({e}); using {FALLBACK_LOOK}")
            return FALLBACK_LOOK

    def _roulette_habit(self, prof: roster.Profile) -> str:
        if prof.superstitious or prof.aggressive:
            return "numbers"
        if prof.archetype == "grinder":
            return self.rng.choice(["even", "even", "dozens"])
        return self.rng.choice(["even", "dozens", "sprinkle", "numbers"])

    def _despawn(self, npc: Npc):
        self.npcs.pop(npc.entity_id, None)
        self.casino.world.remove(npc.entity_id)

    def _walk(self, npc: Npc, target: str, now: float, state: str = "walking"):
        duration = self.rng.uniform(5.0, 9.0) * self.pace
        npc.state, npc.target, npc.until = state, target, now + duration
        self.casino.world.walk(npc.entity_id, target, duration)

    def _next_step(self, npc: Npc, now: float):
        step = npc.plan.pop(0) if npc.plan else "leave"
        if npc.ended and step == "play":
            step = "wander"
        if step == "play":
            if self._head_for_seat(npc, now):
                return
            npc.seat_attempts += 1
            if npc.seat_attempts < 3:  # tables full -- have a wander and try again
                npc.plan.insert(0, "play")
            step = "wander"
        if step == "wander":
            options = [p for p in floor.WANDER_POINTS if p != npc.target]
            self._walk(npc, f"point:{self.rng.choice(options)}", now)
        else:
            self.end_visit(npc, npc.ended or "done")
            self._walk(npc, f"point:{floor.ENTRANCE}", now, state="leaving")

    def _head_for_seat(self, npc: Npc, now: float, only: str | None = None) -> bool:
        claimed = {(n.table, n.seat) for n in self.npcs.values() if n.state == "walking" and n.table}
        tables = [(t, r) for t, r in self.casino.tables.items() if only is None or t == only]
        self.rng.shuffle(tables)
        prof = npc.prof

        def liking(item):   # favourite games first (a Card counter's is Blackjack), a bust table last
            table_id, runner = item
            game = runner.machine.game
            score = 0
            if game in prof.favourite_games or (prof.card_counter and game == bj.GAME_KEY):
                score -= 2
            if prof.superstitious and table_id == prof.avoid_table:
                score += 5
            if game == cr.GAME_KEY and self.npcs_at(table_id) < MIN_CRAPS_NPCS:
                score -= 10   # the craps table wants a couple of NPCs at it
            return score
        # Choose a game first, then a seat at it -- else the ten slot cabinets would swamp the draw.
        by_game: dict[str, list] = {}
        for item in tables:
            by_game.setdefault(item[1].machine.game, []).append(item)
        games = list(by_game)
        self.rng.shuffle(games)
        games.sort(key=lambda g: min(liking(item) for item in by_game[g]))
        for game in games:
            options = sorted(by_game[game], key=liking)
            if game == slots.GAME_KEY:
                # Slots: one seat each, so NPCs leave cabinets free across the bank instead.
                free = [(t, s) for t, r in options for s in r.machine.free_seats() if (t, s) not in claimed]
                if only is not None or len(free) - 1 >= floor.SLOTS_FOR_HUMANS:
                    if free:
                        npc.table, npc.seat = self.rng.choice(free)
                        self._walk(npc, f"seat:{npc.table}:{npc.seat}", now)
                        return True
                continue
            for table_id, runner in options:
                free = [s for s in runner.machine.free_seats() if (table_id, s) not in claimed]
                if len(free) - 1 >= RESERVED_FOR_HUMANS:
                    npc.table, npc.seat = table_id, self.rng.choice(free)
                    self._walk(npc, f"seat:{table_id}:{npc.seat}", now)
                    return True
        return False

    # ------------------------------------------------------------------ the visit
    def end_visit(self, npc: Npc, reason: str):
        """Log the visit and start their cooldown (once)."""
        if getattr(npc, "_logged", False):
            return
        npc._logged = True
        npc.ended = npc.ended or reason
        s = roster.settings(self.casino.store)
        lo, hi = s["bust_cooldown_min"] if reason == "bust" else s["cooldown_min"]
        minutes = self.rng.uniform(lo, hi) * (s["regular_cooldown"] if npc.prof.regular else 1.0)
        now = self.wall()
        cooldown = None if reason in ("shutdown", "admin_reset") else now + minutes * 60
        if reason == "bust" and npc.prof.superstitious and npc.table:
            rec = self.casino.store.npc(npc.npc_id)
            if rec:
                self.casino.store.update_npc(npc.npc_id, {"settings": {**rec["settings"], "avoid_table": npc.table}})
        self.casino.store.record_npc_visit(npc.npc_id, {
            "arrived": npc.arrived, "left_at": now, "budget": npc.prof.budget, "end_bankroll": npc.bankroll,
            "wagered": npc.wagered, "returned": npc.returned, "rounds": npc.rounds, "games": npc.games,
            "reason": npc.ended}, cooldown)

    def close_all(self, reason: str = "shutdown"):
        """The server's stopping: everyone's visit ends where it is."""
        for npc in list(self.npcs.values()):
            self.end_visit(npc, reason)

    def bring_in(self, npc_id: int, now: float) -> Npc:
        """Admin: in through the door now, cooldown or not."""
        here = self.on_floor(npc_id)
        if here:
            return here
        record = self.casino.store.npc(npc_id)
        if record is None or record["role"] != "punter":
            raise ValueError("Only punters can be brought in.")
        return self.spawn(record, now)

    def send_home(self, npc_id: int, now: float) -> bool:
        npc = self.on_floor(npc_id)
        if npc is None:
            return False
        npc.ended = npc.ended or "admin"
        if npc.table is not None and npc.state == "seated":
            runner = self.casino.tables[npc.table]
            if runner.machine.seats[npc.seat].participant is npc.participant:
                runner.act("stand", npc.seat)
            npc.table = npc.seat = None
        npc.plan = ["leave"]
        if npc.state != "leaving":
            self._next_step(npc, now)
        return True

    def restyle(self, npc_id: int, record: dict):
        """Admin changed a look: anyone wearing it on the floor changes now."""
        npc = self.on_floor(npc_id)
        if npc is None:
            return
        look = self._look(record)
        npc.look, npc.name = look, record["name"]
        self.casino.world.restyle(npc.entity_id, look=look, name=record["name"])

    # ------------------------------------------------------------------ per-tick behaviour
    def _step(self, npc: Npc, now: float):
        if npc.state in ("walking", "leaving") and now >= npc.until:
            self.casino.world.arrived(npc.entity_id)
            if npc.state == "leaving":
                return self._despawn(npc)
            if npc.table is not None:
                return self._arrive_at_seat(npc, now)
            npc.state, npc.until = "loitering", now + self.rng.uniform(2.0, 7.0) * self.pace
        elif npc.state == "loitering" and now >= npc.until:
            self._next_step(npc, now)
        elif npc.state == "seated":
            self._play(npc, now)

    def _arrive_at_seat(self, npc: Npc, now: float):
        runner = self.casino.tables[npc.table]
        try:
            runner.act("sit", npc.seat, npc.participant)
        except TableError:  # someone beat them to it
            npc.table = npc.seat = None
            npc.state, npc.until = "loitering", now + 1.0
            return
        npc.state = "seated"
        npc.slot_spins = 0
        if npc.prof.vip and getattr(runner.machine, "DEALER", True):   # a friend of the casino: the dealer knows them
            line = runner.machine.lines.say("vip", "greet", name=npc.name)
            if line:
                runner.publish(say(line))

    def _leave_table(self, npc: Npc, now: float, reason: str | None = None):
        runner = self.casino.tables[npc.table]
        if runner.machine.seats[npc.seat].participant is npc.participant:
            runner.act("stand", npc.seat)
        npc.table = npc.seat = None
        npc.bet_at = npc.decide_at = None
        npc.chips = None
        if reason:
            npc.ended = reason
            self.end_visit(npc, reason)
            if reason == "bust":
                npc.plan = ["leave"]   # nothing left to do here
        self._next_step(npc, now)

    def _round_over(self, npc: Npc, game: str):
        """The round they had bets in has finished: count it, and how it went."""
        if not npc.in_round:
            return
        npc.in_round = False
        npc.rounds += 1
        npc.games[game] = npc.games.get(game, 0) + 1
        result = npc.bankroll - npc.round_start
        if npc.prof.chaser:
            if npc.bankroll >= npc.prof.budget:
                npc.chase = 1.0            # back to even: back to normal
            elif result < 0:
                npc.chase = min(8.0, npc.chase * self.rng.uniform(1.5, 2.0))

    def _time_to_go(self, npc: Npc) -> str | None:
        p, b = npc.prof, npc.prof.budget
        if p.riches and npc.bankroll >= b * p.riches:
            return "riches"
        if p.hit_and_run is not None and npc.bankroll - b >= b * p.hit_and_run:
            return "hit_and_run"
        if npc.rounds >= p.rounds:
            return "done"
        return None

    def _unit(self, npc: Npc, m=None) -> int:
        """Their stake this round, in pence: a share of the budget, chased up after losses,
        spread with the count at Blackjack."""
        target = npc.prof.budget * npc.prof.unit_share * npc.chase
        if npc.prof.card_counter and m is not None and m.game == bj.GAME_KEY:
            tc = self._true_count(m)
            target *= 1 if tc < 2 else min(8, 2 ** (tc - 1))
        return roster.nice_unit(min(target, npc.bankroll * 0.5 if npc.prof.archetype != "gambler" else npc.bankroll))

    @staticmethod
    def _true_count(m) -> float:
        """Hi-Lo true count of the cards dealt from the shoe so far (the whole shoe sums to 0)."""
        left = m.shoe.deck.cards
        if not left:
            return 0.0
        running = -sum(HILO.get(c.rank, 0) for c in left)
        return running / max(len(left) / 52, 0.5)

    def _side(self, npc: Npc, base: float) -> bool:
        return self.rng.random() < min(0.9, base * npc.prof.side_appetite)

    @staticmethod
    def _before_close(at: float, m) -> float:
        """A bet planned for `at`, brought forward so it goes down before betting closes
        (a Rebet can cut the countdown to 3 seconds)."""
        if m.deadline is None:
            return at
        return min(at, m.deadline - BET_LEAD)

    def _mistake(self, npc: Npc) -> bool:
        return self.rng.random() < npc.prof.mistakes

    def _play(self, npc: Npc, now: float):
        m = self.casino.tables[npc.table].machine
        runner = self.casino.tables[npc.table]
        seat = m.seats[npc.seat]
        if seat.participant is not npc.participant:  # stood up by the table
            npc.table = npc.seat = None
            return self._next_step(npc, now)
        if m.game == rou.GAME_KEY:
            return self._play_roulette(npc, m, runner, now)
        if m.game == cr.GAME_KEY:
            return self._play_craps(npc, m, runner, now)
        if m.game == slots.GAME_KEY:
            return self._play_slot(npc, m, runner, now)

        if m.phase == "betting" and not seat.ready:
            if npc.bet_at is None:
                self._round_over(npc, m.game)
                reason = self._time_to_go(npc)
                if reason:
                    return self._leave_table(npc, now, reason)
                npc.bet_at = now + self.rng.uniform(1.0, 4.0) * self.pace
            npc.bet_at = self._before_close(npc.bet_at, m)
            if now >= npc.bet_at:
                npc.bet_at = None
                bets = self._choose_bets(npc, m.game, m)
                if bets is None:
                    return self._leave_table(npc, now, "bust")
                try:
                    npc.round_start = npc.bankroll
                    runner.act("set_bets", npc.seat, bets)
                    runner.act("ready", npc.seat)
                    npc.in_round = True
                except TableError:
                    pass
        elif m.phase != "betting":
            npc.bet_at = None

        if m.game == bj.GAME_KEY:
            return self._play_blackjack(npc, m, runner, now)
        if m.game in (pg.FORTUNE, pg.FACE_UP):
            return self._play_pai_gow(npc, m, runner, now)
        if m.game == ms.GAME_KEY:
            return self._play_mississippi(npc, m, runner, now)
        if m.game == uth.GAME_KEY:
            return self._play_holdem(npc, m, runner, now)
        if m.game == lir.GAME_KEY:
            return self._play_let_it_ride(npc, m, runner, now)
        if m.game == hcf.GAME_KEY:
            return self._play_high_card_flush(npc, m, runner, now)
        if m.game == bac.GAME_KEY:
            return  # nothing to decide once the bets are down
        mine = m.round.get(npc.seat)
        if m.phase == "deciding" and mine is not None and mine.participant is npc.participant and not mine.decided:
            if npc.decide_at is None:  # everyone decides at once; NPCs mull it over for 2-10s
                npc.decide_at = now + self.rng.uniform(2.0, 10.0) * self.pace
            elif now >= npc.decide_at:
                npc.decide_at = None
                hand = tcp.evaluate_three_card_hand(m.round[npc.seat].cards)
                play = tcp.should_play(hand) or npc.prof.aggressive
                if self._mistake(npc):
                    play = not play
                try:
                    runner.act("decide", npc.seat, play)
                except TableError:
                    pass
        else:
            npc.decide_at = None

    def _play_blackjack(self, npc: Npc, m, runner, now: float):
        box = m.round.get(npc.seat)
        if box is None or box.participant is not npc.participant:
            npc.decide_at = npc.decide_for = None
            return
        key = None
        if m.phase == "insurance" and not box.insurance_decided:
            key = ("insurance",)
        elif m.phase == "playing" and m.turn is not None and m.turn[0] == npc.seat:
            idx = m.turn[1]
            key = ("turn", idx, len(box.hands), len(box.hands[idx].cards))
        if key is None:
            npc.decide_at = npc.decide_for = None
            return
        if npc.decide_for != key:  # a new decision: think it over
            npc.decide_for = key
            think = self.rng.uniform(1.0, 4.0)
            if key[0] == "turn":  # nothing to ponder on a stiff 17+ or a hand under 10, unless it's a pair to split
                hand = box.hands[key[1]]
                if (hand.total >= 17 or hand.total < 10) and not hand.can_split(len(box.hands) - 1):
                    think = self.rng.uniform(0.3, 1.0)
            npc.decide_at = now + think * self.pace
            return
        if now < npc.decide_at:
            return
        npc.decide_at = npc.decide_for = None
        try:
            if key[0] == "insurance":
                take = (npc.prof.card_counter and self._true_count(m) >= 3) or self.rng.random() < 0.08
                runner.act("insure", npc.seat, take)
                return
            hand = box.hands[key[1]]
            can_double = hand.can_double and npc.bankroll >= hand.bet
            can_split = hand.can_split(len(box.hands) - 1) and npc.bankroll >= hand.bet
            action = bj.recommend(hand.cards, m.up_card, can_double, can_split)
            if npc.prof.aggressive and action == "hit" and can_double and 9 <= hand.total <= 11:
                action = "double"      # a Gambler doubles whenever it's anywhere near right
            if self._mistake(npc):
                others = [a for a in ("hit", "stand", "double" if can_double else None) if a and a != action]
                action = self.rng.choice(others) if others else action
            runner.act("play_action", npc.seat, action)
        except TableError:
            pass

    def _play_pai_gow(self, npc: Npc, m, runner, now: float):
        hand = m.round.get(npc.seat)
        if m.phase == "claiming" and hand is not None and hand.participant is npc.participant \
                and not hand.claimed and not hand.folded:  # a dealer Ace-high push: claim a bonus or fold
            if npc.decide_at is None:
                npc.decide_at = now + self.rng.uniform(1.0, 3.0) * self.pace
            elif now >= npc.decide_at:
                npc.decide_at = None
                try:
                    runner.act("claim" if hand.bonus_name else "fold", npc.seat)
                except TableError:
                    pass
            return
        if m.phase != "setting" or hand is None or hand.participant is not npc.participant or hand.set or hand.folded:
            npc.decide_at = None
            return
        if npc.decide_at is None:  # sorting seven cards takes a moment
            npc.decide_at = now + self.rng.uniform(3.0, 12.0) * self.pace
        elif now >= npc.decide_at:
            npc.decide_at = None
            front, back = pg.house_way_set(hand.cards)
            fold = False
            if m.game == pg.FACE_UP:  # the dealer's hand is on show: set to beat it, else to push, else fold
                outcome, front, back = pg.best_set_against(hand.cards, m.dealer_front, m.dealer_back)
                b = pg.bonus(hand.cards, hand.bets["fortune"], hand.bets["jackpot"])
                pays = b.fortune_return or b.jackpot_fixed or b.jackpot_share  # a fold would throw that away
                fold = outcome == "lose" and not pays and not npc.prof.aggressive
            try:
                if fold:
                    runner.act("fold", npc.seat)
                else:
                    runner.act("set_hand", npc.seat, [c.code for c in front], [c.code for c in back])
            except TableError:
                pass

    def _play_mississippi(self, npc: Npc, m, runner, now: float):
        """Each street, Joseph Kisenwether's strategy: bet 3x, 1x or fold (a Gambler goes 3x
        wherever the chart says play; a Casual slips up now and then)."""
        hand = m.round.get(npc.seat)
        if m.phase != "deciding" or hand is None or hand.participant is not npc.participant \
                or hand.folded or hand.decided:
            npc.decide_at = None
            return
        seen = hand.cards + m.community[:m.revealed]
        raise_by = ms.strategy(seen, hand.raised_3x)
        if npc.decide_at is None:  # a clear fold or a monster takes a moment; a close call a little longer (3s at most)
            think = self.rng.uniform(0.8, 2.0) if raise_by != 1 else self.rng.uniform(1.5, 3.0)
            npc.decide_at = now + think * self.pace
        elif now >= npc.decide_at:
            npc.decide_at = None
            if npc.prof.aggressive and raise_by == 1:
                raise_by = 3
            if self._mistake(npc):
                raise_by = self.rng.choice([x for x in (0, 1, 3) if x != raise_by])
            try:
                runner.act("play_action", npc.seat, {0: "fold", 1: "bet1", 3: "bet3"}[raise_by])
            except TableError:
                pass

    def _play_holdem(self, npc: Npc, m, runner, now: float):
        """The Wizard of Odds' simple strategy: 4x before the flop, 2x after it, 1x or fold after the river."""
        hand = m.round.get(npc.seat)
        if m.phase != "deciding" or hand is None or hand.participant is not npc.participant \
                or not hand.waiting or hand.decided:
            npc.decide_at = None
            return
        if npc.decide_at is None:
            npc.decide_at = now + self.rng.uniform(0.8, 3.0) * self.pace
            return
        if now < npc.decide_at:
            return
        npc.decide_at = None
        board = m.board[:m.revealed]
        stage = min(m.stage, 2)
        bet, wait = [("bet4", "check"), ("bet2", "check"), ("bet1", "fold")][stage]
        if stage == 0:
            right = uth.preflop_bet(hand.cards)
        elif stage == 1:
            right = uth.flop_bet(hand.cards, board)
        else:
            right = uth.river_bet(hand.cards, board)
        if npc.prof.aggressive and not right and self.rng.random() < 0.4:
            right = True                # a Gambler gets the money in
        if self._mistake(npc):
            right = not right
        try:
            runner.act("play_action", npc.seat, bet if right else wait)
        except TableError:
            pass

    def _play_let_it_ride(self, npc: Npc, m, runner, now: float):
        """The Wizard of Odds' strategy: ride or pull back bet 1, then bet 2."""
        hand = m.round.get(npc.seat)
        if m.phase != "deciding" or hand is None or hand.participant is not npc.participant or hand.decided:
            npc.decide_at = None
            return
        if npc.decide_at is None:
            npc.decide_at = now + self.rng.uniform(0.8, 3.0) * self.pace
            return
        if now < npc.decide_at:
            return
        npc.decide_at = None
        seen = hand.cards + m.community[:m.revealed]
        ride = lir.ride_first(seen) if m.stage == 0 else lir.ride_second(seen)
        ride = ride or npc.prof.aggressive
        if self._mistake(npc):
            ride = not ride
        try:
            runner.act("play_action", npc.seat, "ride" if ride else "pull")
        except TableError:
            pass

    def _play_high_card_flush(self, npc: Npc, m, runner, now: float):
        """Mousseau's strategy: raise (by the most allowed) any 4+ card flush or a 3-card 10-8-6+, else fold."""
        hand = m.round.get(npc.seat)
        if m.phase != "deciding" or hand is None or hand.participant is not npc.participant or hand.decided:
            npc.decide_at = None
            return
        if npc.decide_at is None:
            npc.decide_at = now + self.rng.uniform(0.8, 3.0) * self.pace
            return
        if now < npc.decide_at:
            return
        npc.decide_at = None
        times = hcf.raise_by(hand.cards)
        if npc.prof.aggressive and times == 0:
            times = 1                   # a Gambler plays on with anything
        if self._mistake(npc):
            times = 0 if times else 1
        try:
            runner.act("play_action", npc.seat, f"raise{times}" if times else "fold")
        except TableError:
            pass

    # ------------------------------------------------------------------ Roulette
    def _play_roulette(self, npc: Npc, m, runner, now: float):
        """Chips go down one at a time, a second or two apart; no Ready (so they
        can add a late bet as the ball spins, which some do)."""
        if m.phase == "betting":
            if npc.chips is None:
                self._round_over(npc, m.game)
                reason = self._time_to_go(npc)
                if reason:
                    return self._leave_table(npc, now, reason)
                chips = self._roulette_chips(npc, m.history[0])
                if not chips:
                    return self._leave_table(npc, now, "bust")
                npc.chips = chips
                npc.round_start = npc.bankroll
                npc.late_bet = self.rng.random() < (0.5 if npc.prof.aggressive else 0.25)
                npc.bet_at = now + self.rng.uniform(1.0, 4.0) * self.pace
            if npc.chips and npc.bet_at is not None:
                npc.bet_at = self._before_close(npc.bet_at, m)
                if now >= npc.bet_at:
                    self._put_chip(npc, m, runner, *npc.chips.pop(0))
                    npc.bet_at = now + self.rng.uniform(0.4, 1.6) * self.pace
        elif m.phase == "spinning":
            if npc.late_bet:
                npc.late_bet = False
                npc.bet_at = now + self.rng.uniform(0.5, 2.5) * self.pace
                npc.chips = [(f"n{self.rng.choice(npc.favourites)}", roster.nice_unit(self._unit(npc) / 2))]
            elif npc.chips and npc.bet_at is not None and now >= npc.bet_at:
                self._put_chip(npc, m, runner, *npc.chips.pop(0))
        else:
            npc.chips = None
            npc.bet_at = None

    def _play_craps(self, npc: Npc, m, runner, now: float):
        """Bets go down a chip at a time while the dice are in the middle (the shooter's
        line bet first). They only get up when nothing of theirs is stuck on the table."""
        seat = npc.seat
        if m.phase != "betting":
            npc.chips = None
            npc.bet_at = None
            return
        if npc.chips is None:   # a new betting window
            self._craps_roll_over(npc, m)
            mine = m.seats[seat].bets
            free_to_go = m.point is None and not m.contract_bets(seat) and \
                not any(mine.get(f"dcome_{n}") for n in cr.NUMBERS)
            reason = self._time_to_go(npc)
            if reason and free_to_go:
                return self._leave_table(npc, now, reason)
            wants = [] if reason else self._craps_wants(npc, m)   # (on their way out: nothing new)
            if not wants and free_to_go and not any(mine.values()) and npc.bankroll < cr.MIN_MAIN:
                return self._leave_table(npc, now, "bust")
            npc.chips = wants
            first = 0.4 if m.shooter == seat else self.rng.uniform(1.0, 3.0)
            npc.bet_at = now + first * self.pace
        if npc.chips and npc.bet_at is not None:
            npc.bet_at = self._before_close(npc.bet_at, m)
            if now >= npc.bet_at:
                spot, amount = npc.chips.pop(0)
                try:
                    runner.act("set_bet", seat, spot, m.seats[seat].bets.get(spot, 0) + amount)
                    npc.in_round = True
                except TableError:
                    pass
                npc.bet_at = now + self.rng.uniform(0.5, 1.5) * self.pace

    # ------------------------------------------------------------------ slots
    SLOT_ROUND = 10     # spins that count as one "round" toward a visit's length

    def _play_slot(self, npc: Npc, m, runner, now: float):
        """Spin at a pace that lets the screen finish, fire the trail or on a battle's ships, choose a voyage's islands
        (or a Port Royal deal) and an expedition's route and planets (as expedition_auto would), and pick coins after a moment's thought, and leave only with nothing on screen. A
        Gambler sometimes buys the bonus."""
        def after_thought(lo, hi):
            if npc.decide_at is None:
                npc.decide_at = now + self.rng.uniform(lo, hi) * self.pace
            if now < npc.decide_at:
                return False
            npc.decide_at = None
            return True

        if m.phase == "trail":
            if now >= m.trail_ready_at and after_thought(1.0, 2.0):
                try:
                    runner.act("trail_fire", npc.seat)
                except TableError:
                    pass
            return
        if m.phase == "battle":
            if m.battle and not m.battle["done"] and now >= m.battle_ready_at and after_thought(0.6, 1.6):
                ships = [i for i, there in enumerate(m.battle["ships"]) if there]
                try:
                    runner.act("battle_fire", npc.seat, self.rng.choice(ships) if ships else None)
                except TableError:
                    pass
            return
        if m.phase == "voyage":
            if m.voyage and not m.voyage["done"] and now >= m.voyage_ready_at and after_thought(1.2, 3.0):
                opts = voyage_options(m.variant, m.voyage)
                try:
                    runner.act("voyage_choose", npc.seat, self.rng.choice(opts))
                except TableError:
                    pass
            return
        if m.phase == "expedition":
            if m.expedition and not m.expedition["done"] and now >= m.expedition_ready_at and after_thought(1.2, 3.0):
                try:
                    runner.act("expedition_choose", npc.seat, expedition_auto(m.variant, m.expedition, self.rng.random))
                except TableError:
                    pass
            return
        if m.phase == "jackpot_pick":
            if m.pick and not m.pick["done"] and after_thought(1.0, 2.0):
                open_coins = [i for i, c in enumerate(m.pick["coins"]) if c is None]
                try:
                    runner.act("jackpot_pick", npc.seat, self.rng.choice(open_coins))
                except TableError:
                    pass
            return
        if m.phase != "idle" or m.pending:
            return   # free games and the in-between beats run by the clock
        if npc.bet_at is None:
            if npc.slot_spins and npc.slot_spins % self.SLOT_ROUND == 0:
                self._round_over(npc, m.game)
            reason = self._time_to_go(npc)
            if reason:
                return self._leave_table(npc, now, reason)
            shown = m.spun_at + (presentation_seconds(m.last) * m.timings.present if m.last else 0)
            npc.bet_at = max(now, shown) + self.rng.uniform(0.5, 2.5) * self.pace
        if now < npc.bet_at:
            return
        npc.bet_at = None
        ladder = slot_base.LADDER
        target = self._unit(npc) / 4   # a slot stake is a fraction of their table bet
        bet = max([b for b in ladder if b <= target] or [ladder[0]])
        while bet > npc.bankroll and bet != ladder[0]:
            bet = ladder[ladder.index(bet) - 1]
        if npc.bankroll < bet:
            return self._leave_table(npc, now, "bust")
        if npc.slot_spins % self.SLOT_ROUND == 0:
            npc.round_start, npc.in_round = npc.bankroll, True
        npc.slot_spins += 1
        try:
            cost = bet * m.variant.buy_cost
            if (npc.prof.archetype == "gambler" and m.variant.buy_cost and npc.bankroll >= 3 * cost
                    and self.rng.random() < 0.02):
                runner.act("buy_bonus", npc.seat, bet)
            else:
                runner.act("spin", npc.seat, bet)
        except TableError:
            pass

    def _craps_roll_over(self, npc: Npc, m):
        """A roll they had bets on is over; every third one counts as a round (a roll is
        quicker than a hand at the card tables)."""
        if not npc.in_round:
            return
        npc.craps_rolls += 1
        if npc.craps_rolls % 3 == 0:
            self._round_over(npc, m.game)
            npc.round_start = npc.bankroll
        npc.in_round = any(m.seats[npc.seat].bets.values())

    def _craps_wants(self, npc: Npc, m) -> list:
        """This roll's new bets, by their style: [(spot, pence)]."""
        r = self.rng
        u = min(cr.MAX_FLAT, max(cr.MIN_MAIN, roster.nice_unit(self._unit(npc))))
        b = m.seats[npc.seat].bets
        pt = m.point
        style = npc.craps_style or "casual"
        wants = []

        def need(spot: str, amount: int):
            if not b.get(spot) and amount > 0:
                wants.append((spot, amount))

        if style == "grinder":
            if pt is None:
                need("pass", u)
            else:
                if b.get("pass"):
                    need("pass_odds", b["pass"] * cr.ODDS_X[pt])
                comes = [n for n in cr.NUMBERS if b.get(f"come_{n}")]
                if len(comes) < 2 and r.random() < 0.6:
                    need("come", u)
                for n in comes:
                    need(f"come_odds_{n}", b[f"come_{n}"] * cr.ODDS_X[n])
        elif style == "casual":
            if pt is None:
                need("pass", u)
            else:
                place = max(600, u // 600 * 600)   # in sixes, so 7 to 6 pays in whole pounds
                need("place_6", place)
                need("place_8", place)
                if self._side(npc, 0.2):
                    need("field", u)
        elif style == "gambler":
            small = max(cr.MIN_PROP, roster.nice_unit(u / 5))
            need("field", u)
            if pt is None:
                if self._side(npc, 0.5):
                    need("ce", small)
            else:
                need("hard6", small)
                need("hard8", small)
                if self._side(npc, 0.25):
                    need("any_craps", small)
                if self._side(npc, 0.15):
                    need("eleven", small)
        else:   # the dark side
            if pt is None:
                need("dont_pass", u)
            elif b.get("dont_pass"):
                need("dont_odds", b["dont_pass"] * 2)
        if m.shooter == npc.seat and pt is None and not b.get("pass") and not b.get("dont_pass"):
            line = ("dont_pass" if style == "darkside" else "pass", u)
            if line not in wants:
                wants.insert(0, line)
        while wants and sum(a for _, a in wants) > npc.bankroll:
            wants.pop()
        return wants

    def _put_chip(self, npc: Npc, m, runner, spot: str, amount: int):
        current = m.seats[npc.seat].bets.get(spot, 0)
        try:
            runner.act("set_bet", npc.seat, spot, current + amount)
            npc.in_round = True
        except TableError:
            npc.chips = []  # over a limit or out of money: that'll do for this spin

    def _roulette_chips(self, npc: Npc, last: int) -> list:
        """This spin's chips, by the NPC's habit: [(spot, pence)], each one chip."""
        r = self.rng
        unit = self._unit(npc)
        if npc.habit == "numbers":   # their numbers (a Superstitious NPC's lucky ones), maybe the last one too
            per = roster.nice_unit(unit / max(1, len(npc.favourites)))
            chips = [(f"n{n}", min(per, rou.BETS[f"n{n}"].limit)) for n in npc.favourites]
            if r.random() < 0.3:
                chips.append((f"n{last}", per))
        elif npc.habit == "even":    # a colour or another even chance, sometimes a dozen with it
            chips = [(r.choice(rou.EVEN_MONEY), unit)]
            if self._side(npc, 0.4):
                chips.append((f"doz{r.randint(1, 3)}", roster.nice_unit(unit / 2)))
        elif npc.habit == "dozens":  # one or two dozens or columns
            kind = r.choice(["doz", "col"])
            picks = r.sample([1, 2, 3], r.randint(1, 2))
            chips = [(f"{kind}{k}", roster.nice_unit(unit / len(picks))) for k in picks]
        else:                        # a sprinkle across the layout
            inside = [b for b in rou.SPOTS if b.startswith(("co_", "sp_", "st_", "ln_"))]
            spots = r.sample(inside, r.randint(3, 6))
            chips = [(spot, roster.nice_unit(unit / len(spots))) for spot in spots]
        chips = [(s, max(100, a)) for s, a in chips]
        while chips and sum(a for _, a in chips) > npc.bankroll:
            chips.pop()
        return chips

    # ------------------------------------------------------------------ choosing bets
    def _choose_bets(self, npc: Npc, game: str = tcp.GAME_KEY, m=None) -> dict | None:
        """This round's bets at a card table: the main bet at their unit (dropping to what
        they can afford, side bets first), side bets by appetite. None: they can't afford £1."""
        unit = self._unit(npc, m)
        tries = [u for u in sorted({unit, roster.nice_unit(unit / 2), 500, 100}, reverse=True) if u <= unit]
        for u in tries:
            for with_sides in (True, False):
                bets, need = self._bets_for(npc, game, u, with_sides)
                if need <= npc.bankroll:
                    return bets
        return None

    def _bets_for(self, npc: Npc, game: str, u: int, with_sides: bool) -> tuple[dict, int]:
        """(bets, what they could cost in all) at one unit."""
        r = self.rng

        def side(base: float) -> int:
            if not with_sides or not self._side(npc, base):
                return 0
            return r.choice([500, 1_000, 2_500]) if npc.prof.aggressive else r.choice([100, 500])

        def flat(bet: int, base: float) -> int:
            return bet if with_sides and self._side(npc, base) else 0

        if game in (pg.FORTUNE, pg.FACE_UP):
            bets = {"ante": u, "fortune": side(0.25), "jackpot": flat(pg.JACKPOT_BET, 0.2)}
            return bets, sum(bets.values())
        if game == hcf.GAME_KEY:
            bets = {"ante": u, "flush": side(0.3), "straight_flush": side(0.2), "jackpot": flat(hcf.JACKPOT_BET, 0.25)}
            return bets, sum(bets.values()) + u * 3   # room to raise 3x
        if game == bac.GAME_KEY:
            spot = "banker" if r.random() < (0.45 if npc.prof.aggressive else 0.55) else "player"
            bets = {spot: u, "tie": side(0.12), f"{spot}_dragon": side(0.2)}
            return bets, sum(bets.values())
        if game == uth.GAME_KEY:
            bets = {"ante": u, "trips": side(0.35), "jackpot": flat(uth.JACKPOT_BET, 0.25)}
            return bets, sum(bets.values()) + u * 5   # the Blind and a 4x Play
        if game == lir.GAME_KEY:
            bets = {"bet1": u, "bet2": u, "ante": u, "bonus": flat(lir.BONUS_BET, 0.3),
                    "three_card": side(0.3), "jackpot": flat(lir.JACKPOT_BET, 0.25)}
            return bets, sum(bets.values())
        if game == ms.GAME_KEY:
            bets = {"ante": u, "bonus": side(0.35), "jackpot": flat(ms.JACKPOT_BET, 0.25)}
            return bets, sum(bets.values()) + u * 9   # room to bet 3x every street
        if game == bj.GAME_KEY:
            plus3 = side(0.25)
            bets = {"bet": u, "super_pairs": side(0.25), "twenty_one_plus_three": plus3,
                    "top_three": 100 if plus3 and self._side(npc, 0.3) else 0, "jackpot": flat(bj.JACKPOT_BET, 0.25)}
            return bets, sum(bets.values()) + u   # room to double
        bets = {"ante": u, "pair_plus": side(0.5), "prime": side(0.2), "jackpot": flat(tcp.JACKPOT_BET, 0.3)}
        return bets, sum(bets.values()) + u       # the Play bet
