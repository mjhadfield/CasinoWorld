"""
The Casino: connected sessions, the world (everyone on the floor), the tables,
the NPCs, the store and the jackpot. It lives on app.state for the app's
lifespan (see app.py); start()/stop() own the background tasks -- one runner
per table plus the NPC director.

Message handling is synchronous: the event loop runs one message at a time,
so table and world state never need locks.
"""
import asyncio
import sys
import time

from casino_server import PROTOCOL_VERSION, floor, slot_banks
from casino_server.jackpot import Jackpot
from casino_server import roster
from casino_server.dealers import DealerRoster
from casino_server.npc import NpcDirector
from casino_server.participants import HumanParticipant
from casino_server.session import Session
from casino_server.store import Store
from casino_server.slots.jackpots import SlotProgressives
from casino_server.tables import (baccarat, blackjack, craps, high_card_flush, let_it_ride, mississippi_stud, pai_gow,
                                  roulette, slot_machine, three_card_poker, ultimate_texas_holdem)
from casino_server.tables.base import TableError
from casino_server.tables.runner import TableRunner
from casino_server.world import Entity, World

PLAYER_LOOK = "player_default"
TOP_UP_AMOUNT = 100_000  # £1,000, only when a player can't afford a £1 Ante plus Play
MAX_NAME = 16
MACHINES = {"three_card_poker": three_card_poker.ThreeCardPokerMachine, "blackjack": blackjack.BlackjackMachine,
            "pai_gow_fortune": pai_gow.FortunePaiGowMachine, "pai_gow_face_up": pai_gow.FaceUpPaiGowMachine,
            "mississippi_stud": mississippi_stud.MississippiStudMachine,
            "ultimate_texas_holdem": ultimate_texas_holdem.UltimateTexasHoldemMachine,
            "let_it_ride": let_it_ride.LetItRideMachine,
            "high_card_flush": high_card_flush.HighCardFlushMachine,
            "baccarat": baccarat.BaccaratMachine,
            "roulette": roulette.RouletteMachine,
            "craps": craps.CrapsMachine,
            "slots": slot_machine.SlotMachine}


class Casino:
    def __init__(self, store: Store, jackpot: Jackpot | None = None, speed: float | None = None,
                 npc_population: int | None = 6, npc_pace: float = 1.0, deck_factory=None, rng=None,
                 clock=time.monotonic, wall=time.time, looks=None):
        self.store = store
        self.looks = looks            # art.LookCache: builds the roster's looks (None: built-in looks only)
        roster.seed(store)            # the starting cast, the first time
        self.jackpot = jackpot or Jackpot(store)
        self.slot_jackpots = SlotProgressives(store, clock=clock)   # the slots' own Mini/Minor/Major/Grand
        self.clock = clock
        self.sessions: set[Session] = set()
        self.world = World(self, clock)
        extra = {"deck_factory": deck_factory} if deck_factory else {}
        self.tables = {}
        for table_id, cfg in floor.TABLES.items():
            machine_class = MACHINES[cfg["game"]]
            # `speed` scales every timer (CASINO_SPEED); each game has its own Timings.
            game_timings = None
            if speed is not None:
                game_timings = sys.modules[machine_class.__module__].Timings().scaled(speed)
            machine = machine_class(table_id, cfg["seats"], game_timings, self.jackpot, **extra, **self._machine_extras(cfg))
            self.tables[table_id] = TableRunner(table_id, self, machine, clock)
        self.npcs = NpcDirector(self, npc_population, rng, clock, pace=npc_pace, wall=wall)
        self.dealers = DealerRoster(self, rng, clock, pace=npc_pace)
        self._tasks: list[asyncio.Task] = []
        self._serial = 0

    def _machine_extras(self, cfg: dict) -> dict:
        """What a machine needs beyond the common arguments (a slot cabinet: its variant and
        the shared progressives)."""
        if cfg["game"] == "slots":
            return {"variant": cfg["variant"], "progressives": self.slot_jackpots}
        return {}

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
        return [s for s in self.sessions if s.player is not None]

    def send_wallet(self, session: Session):
        session.push({"type": "wallet", "balance": self.store.balance(session.player.id)})

    def broadcast_all(self, msg: dict, exclude: Session | None = None):
        for session in self.joined_sessions():
            if session is not exclude:
                session.push(msg)

    def on_stood(self, entity_id: str, table_id: str, reason: str):
        """A table stood someone up (they asked, timed out, or disconnected)."""
        for session in self.sessions:
            if session.entity_id == entity_id:
                session.table = session.seat = None
                if reason == "inactive":
                    session.push({"type": "notice", "message": "You sat out three hands, so you've been stood up."})
                elif reason == "idle":
                    session.push({"type": "notice", "message": "You left the machine idle for five minutes, so you've been stood up."})

    # ------------------------------------------------------------------ inbound
    def handle(self, session: Session, msg: dict):
        kind = msg.get("type")
        if kind == "ping":
            return session.push({"type": "pong", "t": msg.get("t")})
        if kind == "join":
            return self._join(session, str(msg.get("token") or ""))
        if kind == "away":
            session.away = True
            return
        if kind == "resync":
            return self._resync(session)
        if session.player is None:
            return session.error("Send `join` first.")
        handler = {
            "set_name": self._set_name, "move": self._move, "sit": self._sit, "stand": self._stand_msg,
            "bet": self._table_action, "clear_bets": self._table_action, "rebet": self._table_action, "auto_rebet": self._table_action,
            "ready": self._table_action, "decide": self._table_action, "insure": self._table_action,
            "act": self._table_action, "set_hand": self._table_action, "fold": self._table_action, "claim": self._table_action,
            "pg_suggest": self._pai_gow_query, "pg_check": self._pai_gow_query, "top_up": self._top_up,
            "shoot": self._table_action, "take_dice": self._table_action, "pass_dice": self._table_action,
            "working": self._table_action,
            "spin": self._table_action, "buy_bonus": self._table_action, "trail_fire": self._table_action,
            "jackpot_pick": self._table_action, "battle_fire": self._table_action,
            "voyage_choose": self._table_action,
            "expedition_choose": self._table_action,
        }.get(kind)
        if handler is None:
            return session.error(f"Unknown message type: {kind}")
        handler(session, msg)

    def _join(self, session: Session, token: str):
        if session.player is not None:
            return session.error("Already joined.")
        player = self.store.player_by_token(token) if token else None
        if player is None:
            player = self.store.create_player()
        session.player = player
        self._serial += 1
        session.entity_id = f"p{player.id}-{self._serial}"
        self._welcome(session)
        self.send_wallet(session)
        session.push(self.jackpot.snapshot())
        session.push(self.slot_jackpots.snapshot())
        session.push(self.world.snapshot())
        for runner in self.tables.values():
            session.push(runner.snapshot_for(session))
        self.world.add(Entity(session.entity_id, "player", player.name, PLAYER_LOOK), at=floor.ENTRANCE)

    def _welcome(self, session: Session, needs_name: bool | None = None):
        player = session.player
        if needs_name is None:
            needs_name = player.name.startswith("Guest ")
        session.push({"type": "welcome", "player": {"id": player.id, "name": player.name},
                      "token": player.token, "entity_id": session.entity_id, "look": PLAYER_LOOK,
                      "needs_name": needs_name, "cabinets": slot_banks.cabinets()})

    def _resync(self, session: Session):
        """The client's tab is visible again: it has dropped everything it buffered while
        hidden, up to this marker, so send the whole picture afresh instead of a backlog."""
        session.away = False
        session.push({"type": "resync", "table": session.table, "seat": session.seat})
        if session.player is None:  # hidden before joining: the hello it dropped
            return session.push({"type": "hello", "protocol": PROTOCOL_VERSION})
        self._welcome(session)      # (in case it was hidden between `join` and `welcome`)
        self.send_wallet(session)
        session.push(self.jackpot.snapshot())
        session.push(self.slot_jackpots.snapshot())
        session.push(self.world.snapshot())
        for runner in self.tables.values():
            session.push(runner.snapshot_for(session))

    def _set_name(self, session: Session, msg: dict):
        name = " ".join(str(msg.get("name") or "").split())[:MAX_NAME]
        if not name:
            return session.error("Pick a name with at least one letter.")
        self.store.set_name(session.player.id, name)
        session.player.name = name
        self.world.rename(session.entity_id, name)
        if session.table is not None:
            participant = self.tables[session.table].machine.seats[session.seat].participant
            participant.name = name
        self._welcome(session, needs_name=False)

    def _move(self, session: Session, msg: dict):
        try:
            x, y = float(msg["x"]), float(msg["y"])
        except (KeyError, TypeError, ValueError):
            return
        self.world.move(session.entity_id, x, y, str(msg.get("dir", "")), str(msg.get("anim", "")), source=session)

    def _sit(self, session: Session, msg: dict):
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
            if kind == "bet":
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

    def _top_up(self, session: Session, msg: dict):
        if self.store.balance(session.player.id) >= 200:
            return session.error("Top-ups are only for when you can't afford the minimum bet.")
        self.store.adjust(session.player.id, TOP_UP_AMOUNT, "top_up")
        self.send_wallet(session)
