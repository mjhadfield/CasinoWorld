"""
A Casino: one of the Resort's casinos (resort.py) -- its floor (floor.Floor, from
its live plan), its sessions (the players who've entered it, and previews of its
draft), the world (everyone on its floor), its tables, NPCs and dealers. The store,
the jackpots and the NPC claims are the Resort's, shared. start()/stop() own the
background tasks -- one runner per table plus the NPC director.

Message handling is synchronous: the event loop runs one message at a time,
so table and world state never need locks.
"""
import asyncio
import sys
import time
from datetime import datetime

from casino_server import art, bank, casinos, plan, seating, table_styles
from casino_server.floor import Floor
from casino_server.jackpot import Jackpot
from casino_server import roster
from casino_server.dealers import DealerRoster
from casino_server.npc import NpcDirector
from casino_server.participants import HumanParticipant
from casino_server.session import Session
from casino_server.store import InsufficientFunds, Player, Store
from casino_server.slots.jackpots import SlotProgressives
from casino_server.slots.stats import SlotStats
from casino_server.tables import (baccarat, blackjack, craps, high_card_flush, let_it_ride, master, mississippi_stud,
                                  pai_gow, roulette, slot_machine, three_card_poker, ultimate_texas_holdem)
from casino_server.tables.base import TableError
from casino_server.tables.runner import TableRunner
from casino_server.world import Entity, World

LOOK_STEP = 64   # walked this far, a player's tables in view are worked out again (Casino.look)

PLAYER_LOOK = "player_default"   # a character with no look of its own (one from before characters)
DECISIONS = {"decide", "insure", "act", "fold", "claim"}   # table messages a player can send for their second box (`seat`)
MACHINES = {"three_card_poker": three_card_poker.ThreeCardPokerMachine, "blackjack": blackjack.BlackjackMachine,
            "pai_gow_fortune": pai_gow.FortunePaiGowMachine, "pai_gow_face_up": pai_gow.FaceUpPaiGowMachine,
            "mississippi_stud": mississippi_stud.MississippiStudMachine,
            "ultimate_texas_holdem": ultimate_texas_holdem.UltimateTexasHoldemMachine,
            "let_it_ride": let_it_ride.LetItRideMachine,
            "high_card_flush": high_card_flush.HighCardFlushMachine,
            "baccarat": baccarat.BaccaratMachine,
            "roulette": roulette.RouletteMachine,
            "craps": craps.CrapsMachine,
            "slots": slot_machine.SlotMachine,
            "master_table": master.MasterMachine}


def look_of(player: Player) -> str:
    """The sheet a character walks about as: its look's id, or the stock one."""
    if not player.look:
        return PLAYER_LOOK
    try:
        return art.look_id(player.look)
    except art.ArtError:   # (a piece that's gone from the catalogue since)
        return PLAYER_LOOK


class Casino:
    def __init__(self, store: Store, floor: Floor, jackpot: Jackpot | None = None, speed: float | None = None,
                 npc_population: int | None = 6, npc_pace: float = 1.0, deck_factory=None, rng=None,
                 clock=time.monotonic, wall=time.time, looks=None, board: plan.PlanBoard | None = None,
                 casino_id: str = casinos.DEMO, resort=None, slot_jackpots: SlotProgressives | None = None,
                 slot_stats: SlotStats | None = None, claims: casinos.Claims | None = None):
        self.id = casino_id
        self.resort = resort          # the Resort it's one of (None: a casino on its own, in tests)
        self.store = store
        self.floor = floor
        self.board = board            # its floor plan (previews, and the tables its styles may name); None: no previews
        self.looks = looks            # art.LookCache: builds the roster's looks (None: built-in looks only)
        roster.seed(store)            # the starting cast, the first time
        self.jackpot = jackpot or Jackpot(store)
        self.slot_jackpots = slot_jackpots or SlotProgressives(store, clock=clock)   # the slots' Mini/Minor/Major/Grand
        self.slot_stats = slot_stats or SlotStats(store)                             # each machine's figures
        self.claims = claims or casinos.Claims()   # which casino each NPC is in
        self.clock = clock
        self.wall = wall              # unix time (the ATM's overdrawn wait)
        self.sessions: set[Session] = set()
        self.world = World(self, clock)
        self._speed = speed
        self._deck_factory = deck_factory
        self.tables = {}
        for table_id, cfg in floor.tables.items():
            self.tables[table_id] = TableRunner(table_id, self, self._make_machine(table_id, cfg["game"], cfg["seats"], cfg), clock)
        self.npcs = NpcDirector(self, npc_population, rng, clock, pace=npc_pace, wall=wall)
        self.dealers = DealerRoster(self, rng, clock, pace=npc_pace)
        self._tasks: list[asyncio.Task] = []
        self._serial = 0

    @property
    def name(self) -> str:
        return self.resort.name_of(self.id) if self.resort is not None else self.id

    def listed(self) -> bool:
        """On the players' chooser (open), not hidden. A casino on its own counts as open."""
        e = self.resort.entry(self.id) if self.resort is not None else None
        return bool(e["open"]) if e else True

    def population(self) -> int:
        """How many punters its NPC director keeps on the floor: the registry's figure (the admin page's setting
        when it's on its own)."""
        if self.resort is not None:
            return self.resort.population(self.id)
        return int(roster.settings(self.store)["population"])


    def _make_machine(self, table_id: str, game: str, seats: int, cfg: dict | None = None):
        machine_class = MACHINES[game]
        # `speed` scales every timer (CASINO_SPEED); each game has its own Timings.
        game_timings = None
        if self._speed is not None:
            game_timings = sys.modules[machine_class.__module__].Timings().scaled(self._speed)
        extra = {"deck_factory": self._deck_factory} if self._deck_factory and game != master.GAME_KEY else {}
        machine = machine_class(table_id, seats, game_timings, self.jackpot, **extra, **self._machine_extras(table_id, game, cfg or {}))
        if cfg and "limits" in cfg:   # (a card table's, from the floor plan; a Master Table hands them to each game)
            machine.limits = {k: tuple(v) for k, v in cfg["limits"].items()}
        return machine

    def _machine_extras(self, table_id: str, game: str, cfg: dict) -> dict:
        """What a machine needs beyond the common arguments (a slot cabinet: its variant and the shared
        progressives; a Master Table: how to make the games it becomes, its animation, and its seat points)."""
        if game == "slots":
            return {"variant": cfg["variant"], "progressives": self.slot_jackpots, "stats": self.slot_stats}
        if game == master.GAME_KEY:
            def on_seats(n: int):   # (the floor's seat points as the live plan has them now: it may have moved)
                stands = self.floor.tables.get(table_id, {}).get("stands", {})
                if str(n) in stands:
                    self.floor.seats[table_id] = [tuple(p) for p in stands[str(n)]]
                runner = self.tables.get(table_id)
                self.floor.sound_sets[table_id] = (runner.machine.current if runner else "") or "casino"

            return {"make": lambda g, n: self._make_machine(table_id, g, n), "anim": cfg.get("anim", master.DEFAULT_ANIM),
                    "speed": cfg.get("speed", master.DEFAULT_SPEED), "leavers": self._npc_leavers, "on_seats": on_seats}
        return {}

    def _npc_leavers(self, participants: list, game: str) -> list:
        """At a Master Table changing game: which of the NPCs sitting there get up for `game`."""
        npcs = getattr(self, "npcs", None)
        return npcs.leavers(participants, game) if npcs is not None else []

    # ------------------------------------------------------------------ lifecycle
    async def start(self):
        self.launch()

    def launch(self):
        """Start the background tasks (on the event loop)."""
        self._tasks = [asyncio.create_task(r.run()) for r in self.tables.values()]
        self._tasks.append(asyncio.create_task(self.npcs.run()))

    async def stop(self):
        tasks = self.halt()
        await asyncio.gather(*tasks, return_exceptions=True)

    def halt(self) -> list[asyncio.Task]:
        """Stop without waiting (a reload, on the event loop): every NPC's visit ends where it is, the tasks are
        cancelled (returned, to await if you can), its NPCs and dealers are free for other casinos."""
        self.npcs.close_all("shutdown")
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        self.claims.release_all(self.id)
        self.jackpot.save()
        self.slot_jackpots.save()
        self.slot_stats.save()
        return tasks

    # ------------------------------------------------------------------ outbound helpers
    def joined_sessions(self):
        return [s for s in self.sessions if s.player is not None and s.preview is None]

    def online_players(self) -> set[int]:
        return {s.player.id for s in self.joined_sessions()}

    def sees(self, session: Session, table_id: str) -> bool:
        """Whether a session is sent that table's states and events (else only who sits there: `table_seats`)."""
        return table_id in session.sees or table_id == session.table

    def look(self, session: Session, quiet: bool = False):
        """Which tables the session is sent: Floor.tables_near where it is (the table it's sitting at, else its last
        move, else the spawn point), checked again once it's moved LOOK_STEP or into another room. Tables that come
        into view get a fresh `table_state` (unless `quiet`: a snapshot follows)."""
        e = self.world.entities.get(session.entity_id)
        if session.table in self.floor.at:   # (sitting, its moves don't count, and a far table's neighbours show)
            at = self.floor.at[session.table]
        elif e is not None and e.x is not None:
            at = (e.x, e.y)
        else:
            spawn = self.floor.points.get(self.floor.spawn)
            at = (spawn["x"], spawn["y"]) if spawn else None
        room = self.floor.room_at(*at) if at is not None else None
        if room is None:
            room = session.room if session.room in self.floor.rooms else None
        last = session.looked_at
        if not quiet and room == session.room and at is not None and last is not None \
                and abs(at[0] - last[0]) < LOOK_STEP and abs(at[1] - last[1]) < LOOK_STEP:
            return
        old = session.sees
        session.room, session.looked_at = room, at
        session.sees = self.floor.tables_near(room, at, old)
        if not quiet:
            for table_id in session.sees - old:
                if table_id in self.tables and table_id != session.table:
                    session.push(self.tables[table_id].snapshot_for(session))

    def broadcast_world(self, floor: Floor):
        """The live floor plan changed (a publish that needed no restart): the casino takes the new floor, and
        everyone rebuilds it."""
        self.floor = floor
        for table_id, runner in self.tables.items():   # a Master Table's options, and its seat points where it stands now
            cfg = floor.tables.get(table_id, {})
            if "limits" in cfg:   # (each card table's limits: bets already down stand)
                runner.machine.limits = {k: tuple(v) for k, v in cfg["limits"].items()}
            if isinstance(runner.machine, master.MasterMachine) and table_id in floor.tables:
                runner.machine.anim, runner.machine.speed = cfg.get("anim", master.DEFAULT_ANIM), cfg.get("speed", master.DEFAULT_SPEED)
                runner.machine.on_seats(len(runner.machine.seats))
        for session in self.joined_sessions():   # (the rooms may have moved: the resync after the rebuild sends tables)
            self.look(session, quiet=True)
        self.broadcast_all({"type": "world", "world": plan.world(floor.plan)})

    def preview_world(self, room_id: str) -> dict:
        """The draft's world for a preview starting in `room_id` (plan.PlanError if it can't be shown)."""
        return plan.preview_world(self.board.draft(), room_id)

    def every_table(self) -> dict | None:
        """The tables its settings may name (PlanBoard.every_table) by qualified id, or None without a board."""
        if self.board is None:
            return None
        return {casinos.qualify(self.id, k): v for k, v in self.board.every_table().items()}

    def seating_view(self) -> dict:
        """The seating styles, with this casino's tables' placements by plain table id (as clients look them up)."""
        s = seating.load(self.store)
        return {**s, "tables": casinos.own(s["tables"], self.id)}

    def styles_view(self) -> dict:
        """Every kind's table styles, with this casino's tables' placements by plain table id."""
        return {kind: {**v, "tables": casinos.own(v["tables"], self.id)}
                for kind, v in table_styles.load_all(self.store, self.every_table()).items()}

    def preview_changed(self):
        """The draft was saved: every preview shows it again."""
        for s in self.sessions:
            if s.preview is not None and self.board is not None:
                try:
                    s.push({"type": "world", "world": self.preview_world(s.preview)})
                except plan.PlanError as e:
                    s.error(str(e))

    def send_wallet(self, session: Session):
        session.push({"type": "wallet", "balance": self.store.balance(session.player.id)})

    def broadcast_all(self, msg: dict, exclude: Session | None = None):
        for session in self.joined_sessions():
            if session is not exclude:
                session.push(msg)

    def broadcast_resort(self, msg: dict, table: str | None = None):
        """News for every casino (the jackpots are shared): this one's players get it with `table`, the table it's
        about (table ids repeat between casinos, so the others don't)."""
        for casino in (self.resort.casinos.values() if self.resort is not None else [self]):
            casino.broadcast_all({**msg, "table": table} if casino is self and table else msg)

    def on_reseated(self, table_id: str, seats: dict, mapping: list):
        """A Master Table changed game and its sitters moved seats (entity id -> seat; `mapping`: each new seat's old
        one, or -1): the sessions, the world and the NPCs follow."""
        for entity_id, seat in seats.items():
            self.world.set_seat(entity_id, table_id, seat)
            for session in self.sessions:
                if session.entity_id == entity_id and session.table == table_id:
                    session.seat = seat
        npcs = getattr(self, "npcs", None)
        if npcs is not None:
            npcs.reseated(table_id, mapping)

    def on_stood(self, entity_id: str, table_id: str, reason: str):
        """A table stood someone up (they asked, timed out, or disconnected)."""
        for session in self.sessions:
            if session.entity_id == entity_id:
                session.table = session.seat = None
                if reason == "inactive":
                    session.push({"type": "notice", "message": "You sat out three hands at a busy table, so you've been stood up."})
                elif reason == "idle":
                    session.push({"type": "notice", "message": "You left the machine idle for five minutes, so you've been stood up."})

    # ------------------------------------------------------------------ inbound
    def handle(self, session: Session, msg: dict):
        """A message from someone on this floor (the Resort has seen to everything before that)."""
        kind = msg.get("type")
        handler = {
            "move": self._move, "sit": self._sit, "stand": self._stand_msg, "kick": self._kick, "kick_cancel": self._kick_cancel,
            "bet": self._table_action, "clear_bets": self._table_action, "rebet": self._table_action, "auto_rebet": self._table_action,
            "ready": self._table_action, "decide": self._table_action, "insure": self._table_action,
            "act": self._table_action, "set_hand": self._table_action, "fold": self._table_action, "claim": self._table_action,
            "pg_suggest": self._pai_gow_query, "pg_check": self._pai_gow_query,
            "atm_open": self._atm, "atm_withdraw": self._atm, "atm_deposit": self._atm,
            "shoot": self._table_action, "take_dice": self._table_action, "pass_dice": self._table_action,
            "working": self._table_action,
            "spin": self._table_action, "buy_bonus": self._table_action, "trail_fire": self._table_action,
            "jackpot_pick": self._table_action, "battle_fire": self._table_action,
            "voyage_choose": self._table_action,
            "expedition_choose": self._table_action,
            "choose_game": self._table_action, "game_vote": self._table_action, "cancel_game_change": self._table_action,
            "second_box": self._table_action, "drop_box": self._table_action,
        }.get(kind)
        if handler is None:
            return session.error(f"Unknown message type: {kind}")
        handler(session, msg)

    # ------------------------------------------------------------------ entering and leaving
    def enter(self, session: Session):
        """Onto this floor as the session's character (the Resort has it picked): the welcome, then the picture."""
        player = session.player
        session.casino = self
        self.sessions.add(session)
        self._serial += 1
        session.entity_id = f"p{player.id}-{self._serial}"
        self.store.entered(player.id, self.id)
        self._welcome(session)
        self._snapshots(session)
        self.world.add(Entity(session.entity_id, "player", player.name, look_of(player)),
                       at=f"point:{self.floor.spawn}")

    def leave(self, session: Session):
        """Off this floor (to the chooser, the character select, or gone): a hand they're in plays out for them."""
        session.kick = None
        if session.table is not None:
            self._stand(session)
        if session.entity_id:
            self.world.remove(session.entity_id)
        self.sessions.discard(session)
        session.casino, session.entity_id = None, ""

    def join_preview(self, session: Session, token: str, room_id: str):
        """A floor-plan preview (the admin page's Preview button): the draft's floor to walk round alone, with the
        tables shown but not dealt. It has no body on the floor and isn't sent the casino's goings-on."""
        if self.board is None:
            return session.error("Previews aren't available here.")
        session.account = {"id": 0, "token": ""}
        session.player, session.preview = Player(0, 0, "Preview", 0), room_id
        session.entity_id = "preview"
        session.casino = self
        self.sessions.add(session)
        self._welcome(session)
        session.push({"type": "wallet", "balance": 0})

    def _welcome(self, session: Session):
        player = session.player
        if session.preview is not None:
            try:
                world = self.preview_world(session.preview)
            except plan.PlanError as e:
                session.error(str(e))
                world = plan.world(self.floor.plan)
        else:
            world = plan.world(self.floor.plan)
        session.push({"type": "welcome", "player": {"id": player.id, "name": player.name, "difficulty": player.difficulty},
                      "entity_id": session.entity_id, "look": look_of(player), "world": world,
                      "casino": {"id": self.id, "name": self.name}, "sound_sets": self.floor.sound_sets,
                      "preview": session.preview, "seating": self.seating_view(), "table_styles": self.styles_view()})

    def _snapshots(self, session: Session):
        """Everything going on: the wallet, the jackpots, everyone on the floor, the tables in view and who sits at
        the rest."""
        self.send_wallet(session)
        session.push(self.jackpot.snapshot())
        session.push(self.slot_jackpots.snapshot())
        session.push(self.world.snapshot())
        self.look(session, quiet=True)
        far = {}
        for table_id, runner in self.tables.items():
            if self.sees(session, table_id):
                session.push(runner.snapshot_for(session))
            else:
                far[table_id] = runner.seats_view()
        if far:
            session.push({"type": "table_seats", "tables": far})

    def resync(self, session: Session):
        """The client's tab is visible again: it has dropped everything it buffered while
        hidden, up to this marker, so send the whole picture afresh instead of a backlog."""
        session.away = False
        session.push({"type": "resync", "table": session.table, "seat": session.seat})
        self._welcome(session)
        if session.preview is None:
            self._snapshots(session)

    def _move(self, session: Session, msg: dict):
        try:
            x, y = float(msg["x"]), float(msg["y"])
        except (KeyError, TypeError, ValueError):
            return
        self.world.move(session.entity_id, x, y, str(msg.get("dir", "")), str(msg.get("anim", "")), source=session)
        self.look(session)

    def _sit(self, session: Session, msg: dict):
        session.kick = None   # (sitting anywhere ends a wait for an NPC's seat)
        runner = self.tables.get(msg.get("table"))
        if runner is None:
            return session.error(f"Unknown table: {msg.get('table')}")
        if session.table is not None:
            return session.error("You're already sitting at a table.")
        try:
            seat = int(msg.get("seat"))
        except (TypeError, ValueError):
            return session.error("Pick a seat.")
        participant = HumanParticipant(session, self, runner.machine.game)
        try:
            runner.act("sit", seat, participant)
        except TableError as e:
            return session.error(str(e))
        session.table, session.seat = runner.table_id, seat
        session.push({"type": "seated", "table": runner.table_id, "seat": seat, "rules": runner.machine.rules()})
        session.push(runner.snapshot_for(session))
        self.look(session)

    def _kick(self, session: Session, msg: dict):
        """Ask the NPC in a seat to give it up (the client has asked if they're sure). They get up now, and the
        seat's yours (`seated`), or after the hand they're in (`kick_waiting`, then `seated`)."""
        runner = self.tables.get(msg.get("table"))
        if runner is None:
            return session.error(f"Unknown table: {msg.get('table')}")
        if session.table is not None:
            return session.error("You're already sitting at a table.")
        try:
            seat = int(msg.get("seat"))
        except (TypeError, ValueError):
            return session.error("Pick a seat.")
        if not 0 <= seat < len(runner.machine.seats):
            return session.error("There's no such seat.")
        who = runner.machine.seats[seat].participant
        try:
            free = self.npcs.kick(runner.table_id, seat, session, self.npcs.clock())
        except TableError as e:
            return session.error(str(e))
        if not free:
            session.push({"type": "kick_waiting", "table": runner.table_id, "seat": seat, "name": who.name})

    def _kick_cancel(self, session: Session, msg: dict):
        session.kick = None

    def seat_kicker(self, session: Session, table_id: str, seat: int):
        """The NPC a player asked for their seat has got up: the player sits down in it."""
        session.kick = None
        if session in self.sessions and session.player is not None and session.table is None:
            self._sit(session, {"table": table_id, "seat": seat})

    def _stand_msg(self, session: Session, msg: dict):
        if session.table is not None:
            self._stand(session)

    def _stand(self, session: Session):
        runner, seat = self.tables[session.table], session.seat
        session.table = session.seat = None
        runner.act("stand", seat)

    def _table_action(self, session: Session, msg: dict):
        if session.table is None:
            return session.error("Sit at a table first.")
        runner, seat, kind = self.tables[session.table], session.seat, msg["type"]
        try:
            if kind in DECISIONS and msg.get("seat") is not None:   # a decision for their second box
                try:
                    box = int(msg["seat"])
                except (TypeError, ValueError):
                    raise TableError("There's no such seat.")
                if box != seat and runner.machine.seats[seat].box != box:
                    raise TableError("That's not your box.")
                seat = box
            if kind == "second_box":
                try:
                    box = int(msg.get("seat"))
                except (TypeError, ValueError):
                    raise TableError("Pick the seat beside you.")
                runner.act("take_box", seat, box)
            elif kind == "drop_box":
                runner.act("drop_box", seat)
            elif kind == "bet":
                spot = str(msg.get("spot"))
                if "add" in msg:  # relative, so rapid clicks don't race the server's echo
                    current = runner.machine.working_bets(seat).get(spot, 0)
                    try:
                        amount = max(0, current + int(msg["add"]))
                    except (TypeError, ValueError):
                        raise TableError("Bets are whole numbers of pence.")
                else:
                    amount = msg.get("amount", 0)
                runner.act("set_bet", seat, spot, amount)
            elif kind == "clear_bets":
                runner.act("clear_bets", seat)
            elif kind == "rebet":
                runner.act("rebet", seat)
            elif kind == "auto_rebet":
                runner.act("set_auto_rebet", seat, bool(msg.get("on")))
            elif kind == "ready":
                runner.act("ready", seat)
            elif kind == "decide":
                runner.act("decide", seat, bool(msg.get("play")))
            elif kind == "insure":
                runner.act("insure", seat, bool(msg.get("take")))
            elif kind == "act":
                runner.act("play_action", seat, str(msg.get("action", "")))
            elif kind == "set_hand":
                runner.act("set_hand", seat, list(msg.get("front") or []), list(msg.get("back") or []))
            elif kind == "fold":
                runner.act("fold", seat)
            elif kind == "claim":
                runner.act("claim", seat)
            elif kind in ("shoot", "pass_dice", "take_dice", "working") and not hasattr(runner.machine, "shoot"):
                raise TableError("That's for the craps table.")
            elif kind == "shoot":
                runner.act("shoot", seat)
            elif kind == "pass_dice":
                runner.act("pass_dice", seat)
            elif kind == "take_dice":
                runner.act("take_dice", seat, bool(msg.get("on", True)))
            elif kind == "working":
                runner.act("set_working", seat, bool(msg.get("on")))
            elif kind in ("choose_game", "game_vote", "cancel_game_change") and not hasattr(runner.machine, "choose_game"):
                raise TableError("That's for a Master Table.")
            elif kind == "choose_game":
                runner.act("choose_game", seat, str(msg.get("game", "")))
            elif kind == "game_vote":
                runner.act("game_vote", seat, bool(msg.get("accept")))
            elif kind == "cancel_game_change":
                runner.act("cancel_queued", seat)
            elif kind in ("spin", "buy_bonus", "trail_fire", "jackpot_pick", "battle_fire", "voyage_choose", "expedition_choose") and not hasattr(runner.machine, "spin"):
                raise TableError("That's for the slot machines.")
            elif kind == "spin":
                runner.act("spin", seat, msg.get("bet"))
            elif kind == "buy_bonus":
                runner.act("buy_bonus", seat, msg.get("bet"))
            elif kind == "trail_fire":
                runner.act("trail_fire", seat)
            elif kind == "jackpot_pick":
                runner.act("jackpot_pick", seat, msg.get("index"))
            elif kind == "battle_fire":
                runner.act("battle_fire", seat, msg.get("index"))
            elif kind == "voyage_choose":
                runner.act("voyage_choose", seat, msg.get("choice"))
            elif kind == "expedition_choose":
                runner.act("expedition_choose", seat, msg.get("choice"))
        except TableError as e:
            session.error(str(e))

    def _pai_gow_query(self, session: Session, msg: dict):
        """The Pai Gow sorter asking about your own cards: the House Way split
        (pg_suggest), or what a split makes and whether it fouls (pg_check).
        Answers go only to you; nothing changes at the table."""
        if session.table is None:
            return session.error("Sit at a table first.")
        machine = self.tables[session.table].machine
        if not hasattr(machine, "suggest"):
            return session.error("That's for Pai Gow tables.")
        try:
            if msg["type"] == "pg_suggest":
                answer = machine.suggest(session.seat)
            else:
                answer = machine.check(session.seat, [str(c) for c in msg.get("front") or []],
                                       [str(c) for c in msg.get("back") or []])
        except TableError as e:
            return session.error(str(e))
        session.push({"type": msg["type"], "table": session.table, **answer})

    def _atm(self, session: Session, msg: dict):
        """The lobby's ATM (bank.py): atm_open for its screen, atm_withdraw / atm_deposit {amount} to use it. On foot
        and in front of one only. Each reply is an `atm` (with `done`, or the `error` its screen shows) and, when money
        moved, the `wallet`."""
        if session.table is not None:
            return session.error("Stand up first to use the ATM.")
        e = self.world.entities.get(session.entity_id)
        if e is None or not bank.near_atm(self.floor, e.x, e.y):
            return session.error("Walk up to the ATM to use it.")
        pid = session.player.id
        s = bank.settings(self.store)
        amount = msg.get("amount")
        error = done = None
        if msg["type"] != "atm_open":
            if msg["type"] == "atm_withdraw":
                error = bank.withdraw_problem(amount, self._withdraw_check(pid, s))
            elif not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
                error = "Enter an amount."
            elif amount > self.store.balance(pid):
                error = "You're not holding that much."
            if error is None:
                to_hand = amount if msg["type"] == "atm_withdraw" else -amount
                try:
                    self.store.transfer(pid, to_hand, self.wall(), big=to_hand > s["low_cap"] * 100)
                except InsufficientFunds:
                    error = "You're not holding that much."
                else:
                    done = {"kind": "withdraw" if to_hand > 0 else "deposit", "amount": amount}
                    self.send_wallet(session)
        session.push(self._atm_state(pid, s) | ({"done": done} if done else {}) | ({"error": error} if error else {}))

    def _withdraw_check(self, pid: int, s: dict) -> dict:
        bank_now, last = self.store.bank(pid)
        return bank.withdraw_check(bank_now, self.store.balance(pid), last,
                                   self.store.last_big_at(pid), s, self.wall())

    def _atm_state(self, pid: int, s: dict) -> dict:
        return {"type": "atm", "bank": self.store.bank(pid)[0], **self._withdraw_check(pid, s),
                "threshold": s["threshold"] * 100, "hand_under": s["hand_under"] * 100, "cooldown_min": s["cooldown_min"],
                "big_wait_min": s["big_wait_min"],
                "history": [{"kind": h["kind"], "amount": h["amount"], "t": datetime.fromisoformat(h["at"]).timestamp()}
                            for h in self.store.atm_history(pid)]}
