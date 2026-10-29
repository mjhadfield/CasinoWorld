"""
The Resort: the casinos players choose between, and what they share. It lives on app.state for the app's lifespan
(see app.py); start()/stop() start and stop every casino.

Shared, made once and handed to each Casino: the store (so a character's cash and bank), the card progressive
(Jackpot), the slots' progressives and figures, the NPC cast and the claims on it (casinos.Claims: an NPC is in one
casino at a time). Each Casino (casino.py) has its own floor, tables, world, NPC director, dealers and sessions, and
its broadcasts go to its own sessions only. Every casino in the registry (casinos.py) runs all the time, players or
not.

The Resort holds every connected session and handles who's at the keyboard: `join` (and a floor-plan preview),
the account's characters (create, edit, delete, pick, leave), bans, and the casino chooser (`casinos`,
`enter_casino`, `leave_casino`). Once a session has entered a casino (session.casino), everything else is that
casino's to handle.

Message handling is synchronous: the event loop runs one message at a time, so no locks.
"""
import asyncio
import copy
import re
import time
from pathlib import Path

from casino_server import PROTOCOL_VERSION, art, bank, casinos, plan, roster
from casino_server.casino import Casino, look_of
from casino_server.jackpot import Jackpot
from casino_server.session import Session
from casino_server.slots.jackpots import SlotProgressives
from casino_server.slots.stats import SlotStats
from casino_server.store import DIFFICULTIES, MAX_CHARACTERS, Player, Store

MAX_NAME = 16


def _running() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


class Resort:
    def __init__(self, store: Store, data_dir: Path, builds_dir: Path | None = None, registry: list | None = None,
                 speed: float | None = None, npc_population: int | None = None, npc_pace: float = 1.0, looks=None,
                 rng=None, clock=time.monotonic, wall=time.time, deck_factory=None):
        self.store = store
        self.data_dir, self.builds_dir = data_dir, builds_dir
        self.looks = looks            # art.LookCache: builds the characters' and the cast's looks
        self.clock, self.wall = clock, wall
        roster.seed(store)            # the starting cast, the first time
        if returned := store.return_stakes():   # (a crash left money riding: back before any table deals)
            print(f"handed back {returned} stake(s) left riding when the server last stopped", flush=True)
        self.jackpot = Jackpot(store)
        self.slot_jackpots = SlotProgressives(store, clock=clock)
        self.slot_stats = SlotStats(store)
        self.claims = casinos.Claims()
        self.registry = registry if registry is not None else casinos.migrate(data_dir, store)
        self.sessions: set[Session] = set()
        self.boards: dict[str, plan.PlanBoard] = {}
        self.casinos: dict[str, Casino] = {}
        self._casino_args = {"speed": speed, "npc_population": npc_population, "npc_pace": npc_pace, "looks": looks,
                             "rng": rng, "clock": clock, "wall": wall, "deck_factory": deck_factory}
        for c in self.registry:
            self._open(c["id"])

    def _open(self, cid: str) -> Casino:
        """Make a casino from its board's live floor (a new board the first time)."""
        board = self.boards.get(cid)
        if board is None:
            board = self.boards[cid] = plan.PlanBoard(casinos.casino_dir(self.data_dir, cid), self.builds_dir)
            board.on_draft = lambda _draft: self.casinos[cid].preview_changed()
            board.on_publish = lambda floor: self.casinos[cid].broadcast_world(floor)
            board.on_reload = lambda _floor: self.reload(cid)
        casino = Casino(self.store, board.floor, jackpot=self.jackpot, board=board, casino_id=cid, resort=self,
                        slot_jackpots=self.slot_jackpots, slot_stats=self.slot_stats, claims=self.claims,
                        **self._casino_args)
        self.casinos[cid] = casino
        return casino

    def entry(self, cid: str) -> dict | None:
        return next((c for c in self.registry if c["id"] == cid), None)

    def name_of(self, cid: str) -> str:
        e = self.entry(cid)
        return e["name"] if e else cid

    def population(self, cid: str) -> int:
        e = self.entry(cid)
        return int(e.get("population", 0)) if e else 0

    # ------------------------------------------------------------------ lifecycle
    async def start(self):
        for casino in self.casinos.values():
            await casino.start()

    def close(self):
        """The server's stopping (__main__, before anyone's disconnected): every casino halts, handing back what's
        riding, so a player's leaving can't fold or stand a hand that won't be finished."""
        for casino in self.casinos.values():
            casino.halt()

    async def stop(self):
        for casino in self.casinos.values():
            await casino.stop()

    def reload(self, cid: str) -> Casino:
        """Reopen a casino on its board's floor (a publish that added or took away tables): the old one stops as if
        the server were stopping, a new one starts, and its players are moved across (`casino_left` {`reload`}, then a
        fresh welcome) and its previews kept. The other casinos carry on."""
        old = self.casinos[cid]
        players = old.joined_sessions()
        previews = [s for s in old.sessions if s.preview is not None]
        old.halt()   # (first: its hands are void, their stakes handed back, before anyone's stood up)
        for s in players:
            old.leave(s)
            s.push({"type": "casino_left", "reason": "reload"})
        new = self._open(cid)
        for s in previews:
            s.casino = new
            new.sessions.add(s)
        new.preview_changed()
        if _running():   # (a test may reload without a loop)
            new.launch()
        for s in players:
            new.enter(s)
        return new

    def connect(self, session: Session):
        self.sessions.add(session)
        session.push({"type": "hello", "protocol": PROTOCOL_VERSION})

    def disconnect(self, session: Session):
        if session.casino is not None:
            session.casino.leave(session)
        self.sessions.discard(session)

    # ------------------------------------------------------------------ who's where
    def joined_sessions(self):
        """Everyone on a casino floor (not previews)."""
        return [s for c in self.casinos.values() for s in c.joined_sessions()]

    def online_players(self) -> set[int]:
        return {s.player.id for s in self.joined_sessions()}

    def where(self, player_id: int) -> str | None:
        """The casino a character is in, if they're on a floor."""
        return next((s.casino.id for s in self.joined_sessions() if s.player.id == player_id), None)

    def npc_casino(self, npc_id: int) -> Casino | None:
        """The casino an NPC is in now, punter or dealer."""
        cid = self.claims.by_npc.get(npc_id)
        return self.casinos.get(cid) if cid else None

    def restyle(self, record: dict):
        """An NPC's look or name changed on the admin page: wherever they are, they change in front of you."""
        for casino in self.casinos.values():
            casino.npcs.restyle(record["id"], record)
            casino.dealers.restyle(record)

    def broadcast_all(self, msg: dict):
        """Everyone on every floor."""
        for casino in self.casinos.values():
            casino.broadcast_all(msg)

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

    # ------------------------------------------------------------------ inbound
    def handle(self, session: Session, msg: dict):
        kind = msg.get("type")
        if kind == "ping":
            return session.push({"type": "pong", "t": msg.get("t")})
        if kind == "join":
            if msg.get("preview"):
                return self._join_preview(session, msg)
            return self._join(session, str(msg.get("token") or ""))
        if kind == "away":
            session.away = True
            return
        if kind == "resync":
            if session.casino is not None:
                return session.casino.resync(session)
            return self._resync(session)
        if session.account is None:
            return session.error("Send `join` first.")
        if session.preview is not None:
            return   # (a preview only looks)
        account_handler = {
            "create_character": self._create_character, "edit_character": self._edit_character,
            "delete_character": self._delete_character, "pick_character": self._pick_character,
            "leave_character": self._leave_character, "enter_casino": self._enter_casino,
            "leave_casino": self._leave_casino, "list_casinos": self._list_casinos,
        }.get(kind)
        if account_handler is not None:
            return account_handler(session, msg)
        if session.player is None:
            return session.error("Pick a character first.")
        if session.casino is None:
            return session.error("Choose a casino first.")
        session.casino.handle(session, msg)

    def _resync(self, session: Session):
        """Back from a hidden tab off any floor: what it dropped (see Casino.resync)."""
        session.away = False
        session.push({"type": "resync", "table": None, "seat": None})
        if session.account is None:  # hidden before joining: the hello it dropped
            return session.push({"type": "hello", "protocol": PROTOCOL_VERSION})
        if session.player is None:   # at the character select
            return self._send_account(session)
        self._send_casinos(session)

    # ------------------------------------------------------------------ accounts and characters
    def _join(self, session: Session, token: str):
        """Who's at the keyboard: the device's account (a new one for a new device), answered with `account` --
        their characters to pick from. Nobody's on a floor until they pick one and a casino."""
        if session.account is not None:
            return session.error("Already joined.")
        account = self.store.account_by_token(token) if token else None
        bar = account and self.store.barred(account["id"], time.time())
        if bar:
            return self._barred(session, bar)
        session.account = account or self.store.create_account()
        self._send_account(session)

    def _join_preview(self, session: Session, msg: dict):
        """A floor-plan preview of a casino's draft (the admin page's Preview button, `casino`: Demo if unset)."""
        if session.account is not None:
            return session.error("Already joined.")
        casino = self.casinos.get(str(msg.get("casino") or casinos.DEMO))
        if casino is None:
            return session.error("There's no such casino.")
        casino.join_preview(session, str(msg.get("token") or ""), str(msg["preview"]))

    def _send_account(self, session: Session):
        aid = session.account["id"]
        online = {s.player.id for s in self.sessions if s.player is not None and s.preview is None}
        s = bank.settings(self.store)
        session.push({"type": "account", "token": session.account["token"], "max": MAX_CHARACTERS,
                      "characters": [{"id": p.id, "name": p.name, "look": look_of(p), "spec": p.look, "difficulty": p.difficulty,
                                      "balance": p.balance, "bank": p.bank, "online": p.id in online}
                                     for p in self.store.characters(aid)],
                      "difficulties": {d: bank.start_bank(s, d) for d in DIFFICULTIES},
                      "last": self.store.last_played(aid)})

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

    def _playing_elsewhere(self, player_id: int, but: Session | None = None) -> list[Session]:
        """The sessions playing a character, on a floor or at the casino chooser."""
        return [s for s in self.sessions if s is not but and s.player is not None and s.preview is None
                and s.player.id == player_id]

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
        """Playing as one of their characters: the casino chooser (`casinos`) next, or with `casino` straight into
        that one (a reconnect's `resume`, or a ?casino= link). If the character is playing somewhere else already
        it's taken over from there (that window goes back to its character select), unless this is a reconnect
        (`resume`), which gives way instead."""
        if session.player is not None:
            return session.error("You're already playing: leave first.")
        p = self._mine(session, msg)
        if p is None:
            return
        bar = self.store.barred(p.account_id, time.time())
        if bar:
            return self._barred(session, bar)
        others = self._playing_elsewhere(p.id, but=session)
        if others and msg.get("resume"):
            session.push({"type": "character_left", "reason": "elsewhere", "name": p.name})
            return self._send_account(session)
        for other in others:
            self._leave(other, "elsewhere")
        want = msg.get("casino") or (self.store.last_casino(p.id) if msg.get("resume") else None)

        def picked():
            if session not in self.sessions or session.player is not None:   # (gone, or picked twice while building)
                return
            session.player = p
            self.store.played(p.id, self.wall())
            if want in self.casinos:
                self.casinos[want].enter(session)
            else:
                self._send_casinos(session)
        self._after_look(session, p.look, picked)

    def _leave_character(self, session: Session, msg: dict):
        if session.player is None:
            return self._send_account(session)
        self._leave(session, "switch")

    def _leave(self, session: Session, reason: str):
        """Off the floor (if they're on one) and back to the character select ("switch": they asked; "elsewhere":
        the character was picked in another window). A hand they're in plays out for the character that sat down."""
        name = session.player.name
        if session.casino is not None:
            session.casino.leave(session)
        session.player = None
        session.push({"type": "character_left", "reason": reason, "name": name})
        self._send_account(session)

    # ------------------------------------------------------------------ the casino chooser
    def listing(self, also: str | None = None) -> list[dict]:
        """The casinos a player can choose (the open ones, and `also` if it's hidden), with who's in each."""
        out = []
        for c in self.registry:
            casino = self.casinos.get(c["id"])
            if casino is None or not (c["open"] or c["id"] == also):
                continue
            out.append({"id": c["id"], "name": c["name"], "blurb": c.get("blurb", ""),
                        "players": len(casino.joined_sessions()), "npcs": casino.npcs.here(),
                        "tables": sum(1 for r in casino.tables.values() if r.machine.game != "slots")})
        return out

    def _send_casinos(self, session: Session):
        last = self.store.last_casino(session.player.id)
        session.push({"type": "casinos", "list": self.listing(last), "last": last})

    def casinos_changed(self):
        """The registry changed: everyone at the chooser sees the new list."""
        for s in self.sessions:
            if s.player is not None and s.casino is None and s.preview is None:
                self._send_casinos(s)

    def _list_casinos(self, session: Session, msg: dict):
        """The chooser's list, fresh (opened from the floor to switch casino)."""
        if session.player is None:
            return session.error("Pick a character first.")
        self._send_casinos(session)

    def _enter_casino(self, session: Session, msg: dict):
        if session.player is None:
            return session.error("Pick a character first.")
        if session.casino is not None:
            return session.error("You're in a casino already: leave it first.")
        casino = self.casinos.get(str(msg.get("casino") or ""))
        if casino is None:
            return session.error("There's no such casino.")
        casino.enter(session)

    def _leave_casino(self, session: Session, msg: dict):
        if session.casino is None:
            return self._send_casinos(session) if session.player is not None else None
        session.casino.leave(session)
        session.push({"type": "casino_left", "reason": "leave"})
        self._send_casinos(session)

    # ------------------------------------------------------------------ the admin page's Casinos
    def overview(self) -> list[dict]:
        """The registry, in order, with who's in each now (the admin page)."""
        out = []
        for c in self.registry:
            casino = self.casinos[c["id"]]
            out.append({**c, "players": len(casino.joined_sessions()), "npcs": casino.npcs.here(),
                        "tables": sum(1 for r in casino.tables.values() if r.machine.game != "slots"),
                        "cabinets": sum(1 for r in casino.tables.values() if r.machine.game == "slots")})
        return out

    def add_casino(self, name: str, blurb: str = "", start: str = "lobby") -> str:
        """A new casino, hidden, from `start`: "lobby" (an empty lobby: Demo's Modern lobby if it has one) or
        "copy:<id>" (that casino's live plan, its draft too). Returns its id."""
        name = _clean_name(name)
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:20] or "casino"
        cid, n = base, 2
        while cid in self.casinos or casinos.casino_dir(self.data_dir, cid).exists():
            cid, n = f"{base}_{n}", n + 1
        if start.startswith("copy:"):
            board = self.boards.get(start[5:])
            if board is None:
                raise ValueError("There's no such casino to copy.")
            live, draft = copy.deepcopy(board.floor.plan), board.draft()
        elif start == "lobby":
            live = new_lobby_plan(self.boards[self.registry[0]["id"]].floor.plan if self.registry else None)
            draft = copy.deepcopy(live)
        else:
            raise ValueError("Start from a lobby or a copy of a casino.")
        d = plan.plan_dir(casinos.casino_dir(self.data_dir, cid))
        plan._write(d / "live.json", live)
        plan._write(d / "draft.json", draft)
        self.registry.append(casinos.entry(cid, name, _clean_blurb(blurb), open_=False, population=0))
        casinos.save(self.data_dir, self.registry)
        casino = self._open(cid)
        if _running():
            casino.launch()
        self.casinos_changed()
        return cid

    def change_casino(self, cid: str, data: dict) -> dict:
        """Rename it, its blurb, Open (listed) or Hidden, its population, its place in the order."""
        e = self.entry(cid)
        if e is None:
            raise KeyError(cid)
        if "name" in data:
            e["name"] = _clean_name(data["name"])
        if "blurb" in data:
            e["blurb"] = _clean_blurb(data["blurb"])
        if "open" in data:
            e["open"] = bool(data["open"])
        if "population" in data:
            try:
                n = int(data["population"])
            except (TypeError, ValueError):
                raise ValueError("Punters on the floor is a whole number.")
            if not 0 <= n <= 30:
                raise ValueError("Punters on the floor is 0 to 30.")
            e["population"] = n
        if "order" in data:
            try:
                at = max(0, min(len(self.registry) - 1, int(data["order"])))
            except (TypeError, ValueError):
                raise ValueError("Order is a number.")
            self.registry.remove(e)
            self.registry.insert(at, e)
        casinos.save(self.data_dir, self.registry)
        self.casinos_changed()
        return e

    def delete_casino(self, cid: str):
        """Gone, when nobody's playing in it and it isn't the last one: its plan is kept aside in
        <data>/casinos-deleted/ (settings kept by its tables' ids just stop being used)."""
        casino = self.casinos.get(cid)
        if casino is None:
            raise KeyError(cid)
        if len(self.registry) <= 1:
            raise ValueError("That's the last casino: there has to be one.")
        if casino.joined_sessions():
            raise ValueError("There are people playing in it: wait until it's empty (or hide it first).")
        for s in [s for s in casino.sessions if s.preview is not None]:
            casino.leave(s)
            s.close()
        casino.halt()
        del self.casinos[cid], self.boards[cid]
        self.registry = [c for c in self.registry if c["id"] != cid]
        casinos.save(self.data_dir, self.registry)
        gone = self.data_dir / "casinos-deleted" / f"{cid}-{time.strftime('%Y%m%d-%H%M%S')}"
        gone.parent.mkdir(parents=True, exist_ok=True)
        casinos.casino_dir(self.data_dir, cid).rename(gone)
        self.casinos_changed()


def _clean_name(raw) -> str:
    name = " ".join(str(raw or "").split())[:casinos.MAX_NAME]
    if not name:
        raise ValueError("Give the casino a name.")
    return name


def _clean_blurb(raw) -> str:
    return " ".join(str(raw or "").split())[:casinos.MAX_BLURB]


def new_lobby_plan(source: dict | None) -> dict:
    """A plan with just a lobby: the source plan's Modern lobby (placed or in its library), else the plain first
    lobby, where it was (so blueprints drawn round it fit). Its spawn is the lobby's."""
    room = next((r for r in (source or {}).get("rooms", []) if r["id"] == "modern_lobby"), None)
    room = copy.deepcopy(room) if room else plan.lobby()
    room["placed"] = True
    spawn = next((p["name"] for p in room["paths"]["points"] if p["kind"] == "spawn"), "")
    out = {"rev": 1, "next": {}, "spawn": f"{room['id']}/{spawn}" if spawn else "", "rooms": [room]}
    out["next"] = plan._serials(out)
    return out
