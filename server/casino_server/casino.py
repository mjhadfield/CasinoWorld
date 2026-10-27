"""
The Casino: connected sessions, its floor (floor.Floor, from the live plan), the
world (everyone on the floor), the tables, the NPCs, the store and the jackpot.
It lives on app.state for the app's lifespan (see app.py); start()/stop() own
the background tasks -- one runner per table plus the NPC director.

Message handling is synchronous: the event loop runs one message at a time,
so table and world state never need locks.
"""
import asyncio
import sys
import time
from datetime import datetime

from casino_server import PROTOCOL_VERSION, art, bank, casinos, plan, seating, table_styles
from casino_server.floor import Floor
from casino_server.jackpot import Jackpot
from casino_server import roster
from casino_server.dealers import DealerRoster
from casino_server.npc import NpcDirector
from casino_server.participants import HumanParticipant
from casino_server.session import Session
from casino_server.store import DIFFICULTIES, MAX_CHARACTERS, InsufficientFunds, Player, Store
from casino_server.slots.jackpots import SlotProgressives
from casino_server.slots.stats import SlotStats
from casino_server.tables import (baccarat, blackjack, craps, high_card_flush, let_it_ride, master, mississippi_stud,
                                  pai_gow, roulette, slot_machine, three_card_poker, ultimate_texas_holdem)
from casino_server.tables.base import TableError
from casino_server.tables.runner import TableRunner
from casino_server.world import Entity, World

PLAYER_LOOK = "player_default"   # a character with no look of its own (one from before characters)
MAX_NAME = 16
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


class Casino:
    def __init__(self, store: Store, floor: Floor, jackpot: Jackpot | None = None, speed: float | None = None,
                 npc_population: int | None = 6, npc_pace: float = 1.0, deck_factory=None, rng=None,
                 clock=time.monotonic, wall=time.time, looks=None, board: plan.PlanBoard | None = None,
                 casino_id: str = casinos.DEMO):
        self.id = casino_id
        self.store = store
        self.floor = floor
        self.board = board            # its floor plan (previews, and the tables its styles may name); None: no previews
        self.looks = looks            # art.LookCache: builds the roster's looks (None: built-in looks only)
        roster.seed(store)            # the starting cast, the first time
        self.jackpot = jackpot or Jackpot(store)
        self.slot_jackpots = SlotProgressives(store, clock=clock)   # the slots' own Mini/Minor/Major/Grand
        self.slot_stats = SlotStats(store)                           # each machine's figures (the admin page's Slots)
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
        self._tasks = [asyncio.create_task(r.run()) for r in self.tables.values()]
        self._tasks.append(asyncio.create_task(self.npcs.run()))

    async def stop(self):
        self.npcs.close_all("shutdown")
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self.jackpot.save()
        self.slot_jackpots.save()
        self.slot_stats.save()

    def connect(self, session: Session):
        self.sessions.add(session)
        session.push({"type": "hello", "protocol": PROTOCOL_VERSION})

    def disconnect(self, session: Session):
        if session.table is not None:
            self._stand(session)
        self.sessions.discard(session)
        if session.entity_id:
            self.world.remove(session.entity_id)

    # ------------------------------------------------------------------ outbound helpers
    def joined_sessions(self):
        return [s for s in self.sessions if s.player is not None and s.preview is None]

    def online_players(self) -> set[int]:
        return {s.player.id for s in self.joined_sessions()}

    def send_off(self, account_id: int, kind: str, until: float | None = None, reason: str = "",
                 player_id: int | None = None):
        """The admin page banned, timed out ("ban" | "timeout") or deleted ("removed") an account (or, with
        `player_id`, deleted just that character): every session on it -- at the character select too -- is told
        why and hung up on (the socket's end stands them up). Returns how many sessions that was."""
        gone = [s for s in self.sessions if s.account is not None and s.account["id"] == account_id and s.preview is None
                and (player_id is None or (s.player is not None and s.player.id == player_id))]
        for s in gone:
            self._barred(s, {"kind": kind, "until": until, "reason": reason})
        return len(gone)

    def _barred(self, session: Session, bar: dict):
        until = bar.get("until")
        session.push({"type": "barred", "kind": bar["kind"], "reason": bar.get("reason") or "",
                      "retry_in": max(1, round(until - time.time())) if until else None})
        session.close()

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
        kind = msg.get("type")
        if kind == "ping":
            return session.push({"type": "pong", "t": msg.get("t")})
        if kind == "join":
            if msg.get("preview"):
                return self._join_preview(session, str(msg.get("token") or ""), str(msg["preview"]))
            return self._join(session, str(msg.get("token") or ""))
        if kind == "away":
            session.away = True
            return
        if kind == "resync":
            return self._resync(session)
        if session.account is None:
            return session.error("Send `join` first.")
        if session.preview is not None:
            return   # (a preview only looks)
        account_handler = {
            "create_character": self._create_character, "edit_character": self._edit_character,
            "delete_character": self._delete_character, "pick_character": self._pick_character,
            "leave_character": self._leave_character,
        }.get(kind)
        if account_handler is not None:
            return account_handler(session, msg)
        if session.player is None:
            return session.error("Pick a character first.")
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

    # ------------------------------------------------------------------ accounts and characters
    def _join(self, session: Session, token: str):
        """Who's at the keyboard: the device's account (a new one for a new device), answered with `account` --
        their characters to pick from. Nobody's on the floor until they pick one."""
        if session.account is not None:
            return session.error("Already joined.")
        account = self.store.account_by_token(token) if token else None
        bar = account and self.store.barred(account["id"], time.time())
        if bar:
            return self._barred(session, bar)
        session.account = account or self.store.create_account()
        self._send_account(session)

    def _send_account(self, session: Session):
        aid = session.account["id"]
        online = self.online_players()
        s = bank.settings(self.store)
        session.push({"type": "account", "token": session.account["token"], "max": MAX_CHARACTERS,
                      "characters": [{"id": p.id, "name": p.name, "look": self._look_of(p), "spec": p.look, "difficulty": p.difficulty,
                                      "balance": p.balance, "bank": p.bank, "online": p.id in online}
                                     for p in self.store.characters(aid)],
                      "difficulties": {d: bank.start_bank(s, d) for d in DIFFICULTIES},
                      "last": self.store.last_played(aid)})

    @staticmethod
    def _look_of(player: Player) -> str:
        """The sheet a character walks about as: its look's id, or the stock one."""
        if not player.look:
            return PLAYER_LOOK
        try:
            return art.look_id(player.look)
        except art.ArtError:   # (a piece that's gone from the catalogue since)
            return PLAYER_LOOK

    def _after_look(self, session: Session, spec: dict | None, then):
        """Run `then` once the look's sheet is built (straight away if it's built already, or there's no builder):
        building one takes a moment, so it's done off the event loop."""
        if not spec or self.looks is None or self.looks.path(art.look_id(spec)):
            return then()
        future = asyncio.get_running_loop().run_in_executor(None, self.looks.ensure, spec)

        def done(f):
            if session not in self.sessions:
                return
            if f.exception() is not None:
                return session.error(f"That look couldn't be made: {f.exception()}")
            then()
        future.add_done_callback(done)

    def _mine(self, session: Session, msg: dict) -> Player | None:
        try:
            p = self.store.character(int(msg.get("id")))
        except (TypeError, ValueError):
            p = None
        if p is None or p.account_id != session.account["id"]:
            session.error("No such character.")
            return None
        return p

    def _character_fields(self, session: Session, msg: dict, editing: int | None = None) -> tuple[str, dict] | None:
        """The name and look sent for a character, cleaned, or None (and the reason sent) if they won't do."""
        name = " ".join(str(msg.get("name") or "").split())[:MAX_NAME]
        if not name:
            session.error("Give your character a name.")
            return None
        if any(p.name.casefold() == name.casefold() and p.id != editing for p in self.store.characters(session.account["id"])):
            session.error(f"You already have a character called {name}.")
            return None
        look = msg.get("look")
        if not isinstance(look, dict):
            session.error("Choose how your character looks.")
            return None
        try:
            look = art.validate(look)
        except art.ArtError as e:
            session.error(str(e))
            return None
        return name, look

    def _create_character(self, session: Session, msg: dict):
        if len(self.store.characters(session.account["id"])) >= MAX_CHARACTERS:
            return session.error(f"You can have {MAX_CHARACTERS} characters: delete one to make another.")
        difficulty = msg.get("difficulty")
        if difficulty not in DIFFICULTIES:
            return session.error("Pick Easy, Normal or Hard.")
        fields = self._character_fields(session, msg)
        if fields is None:
            return
        name, look = fields

        def create():
            if len(self.store.characters(session.account["id"])) >= MAX_CHARACTERS:   # (two at once)
                return session.error(f"You can have {MAX_CHARACTERS} characters: delete one to make another.")
            s = bank.settings(self.store)
            p = self.store.create_character(session.account["id"], name, look, difficulty,
                                            bank=bank.start_bank(s, difficulty), hand=s["start_hand"] * 100)
            session.push({"type": "character_made", "id": p.id})
            self._send_account(session)
        self._after_look(session, look, create)

    def _playing_elsewhere(self, player_id: int) -> list[Session]:
        return [s for s in self.joined_sessions() if s.player.id == player_id]

    def _edit_character(self, session: Session, msg: dict):
        p = self._mine(session, msg)
        if p is None:
            return
        if self._playing_elsewhere(p.id):
            return session.error(f"{p.name} is on the floor: leave first to change them.")
        fields = self._character_fields(session, msg, editing=p.id)
        if fields is None:
            return
        name, look = fields

        def save():
            self.store.update_character(p.id, name=name, look=look)
            self._send_account(session)
        self._after_look(session, look, save)

    def _delete_character(self, session: Session, msg: dict):
        p = self._mine(session, msg)
        if p is None:
            return
        if self._playing_elsewhere(p.id):
            return session.error(f"{p.name} is on the floor: leave first to delete them.")
        self.store.delete_player(p.id)
        self._send_account(session)

    def _pick_character(self, session: Session, msg: dict):
        """Onto the floor as one of their characters. If it's playing somewhere else already it's taken over from
        there (that window goes back to its character select), unless this is a reconnect (`resume`), which gives
        way instead."""
        if session.player is not None:
            return session.error("You're already playing: leave first.")
        p = self._mine(session, msg)
        if p is None:
            return
        bar = self.store.barred(p.account_id, time.time())
        if bar:
            return self._barred(session, bar)
        others = self._playing_elsewhere(p.id)
        if others and msg.get("resume"):
            session.push({"type": "character_left", "reason": "elsewhere", "name": p.name})
            return self._send_account(session)
        for other in others:
            self._leave(other, "elsewhere")
        self._after_look(session, p.look, lambda: self._enter(session, p))

    def _enter(self, session: Session, player: Player):
        if session.player is not None:   # (picked twice while the look was being built)
            return
        session.player = player
        self._serial += 1
        session.entity_id = f"p{player.id}-{self._serial}"
        self.store.played(player.id, self.wall())
        self._welcome(session)
        self.send_wallet(session)
        session.push(self.jackpot.snapshot())
        session.push(self.slot_jackpots.snapshot())
        session.push(self.world.snapshot())
        for runner in self.tables.values():
            session.push(runner.snapshot_for(session))
        self.world.add(Entity(session.entity_id, "player", player.name, self._look_of(player)),
                       at=f"point:{self.floor.spawn}")

    def _leave_character(self, session: Session, msg: dict):
        if session.player is None:
            return self._send_account(session)
        self._leave(session, "switch")

    def _leave(self, session: Session, reason: str):
        """Off the floor and back to the character select ("switch": they asked; "elsewhere": the character was
        picked in another window). A hand they're in plays out for the character that sat down."""
        name = session.player.name
        if session.table is not None:
            self._stand(session)
        if session.entity_id:
            self.world.remove(session.entity_id)
        session.player, session.entity_id = None, ""
        session.push({"type": "character_left", "reason": reason, "name": name})
        self._send_account(session)

    def _join_preview(self, session: Session, token: str, room_id: str):
        """A floor-plan preview (the admin page's Preview button): the draft's floor to walk round alone, with the
        tables shown but not dealt. It has no body on the floor and isn't sent the casino's goings-on."""
        if session.account is not None:
            return session.error("Already joined.")
        if self.board is None:
            return session.error("Previews aren't available here.")
        session.account = {"id": 0, "token": ""}
        session.player, session.preview = Player(0, 0, "Preview", 0), room_id
        session.entity_id = "preview"
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
                      "entity_id": session.entity_id, "look": self._look_of(player), "world": world,
                      "preview": session.preview, "seating": self.seating_view(), "table_styles": self.styles_view()})

    def _resync(self, session: Session):
        """The client's tab is visible again: it has dropped everything it buffered while
        hidden, up to this marker, so send the whole picture afresh instead of a backlog."""
        session.away = False
        session.push({"type": "resync", "table": session.table, "seat": session.seat})
        if session.account is None:  # hidden before joining: the hello it dropped
            return session.push({"type": "hello", "protocol": PROTOCOL_VERSION})
        if session.player is None:   # at the character select
            return self._send_account(session)
        self._welcome(session)      # (in case it was hidden between picking and `welcome`)
        if session.preview is not None:
            return
        self.send_wallet(session)
        session.push(self.jackpot.snapshot())
        session.push(self.slot_jackpots.snapshot())
        session.push(self.world.snapshot())
        for runner in self.tables.values():
            session.push(runner.snapshot_for(session))

    def _move(self, session: Session, msg: dict):
        try:
            x, y = float(msg["x"]), float(msg["y"])
        except (KeyError, TypeError, ValueError):
            return
        self.world.move(session.entity_id, x, y, str(msg.get("dir", "")), str(msg.get("anim", "")), source=session)

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
