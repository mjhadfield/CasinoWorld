"""
The world: every avatar on the casino floor -- players and NPCs -- and where
they are. Players move themselves and report it (move); the server relays it
to everyone else. NPCs are given walks (entity_walk) to named floor points or
seats with a duration, and each client paths them there in that time.
"""
import time
from dataclasses import dataclass, field


@dataclass
class Entity:
    id: str
    kind: str   # "player" | "npc"
    name: str
    look: str
    x: float | None = None  # a player: None until their first move (clients place them at the spawn point);
                            # an NPC: where their current walk started, or where they are when not walking
    y: float | None = None
    dir: str = "down"
    anim: str = "idle"
    seat: dict | None = None      # {"table", "seat"} while seated
    walk: dict | None = None      # {"target", "duration", "started"} for an NPC on the move

    def to_dict(self, now: float) -> dict:
        d = {"id": self.id, "kind": self.kind, "name": self.name, "look": self.look,
             "x": self.x, "y": self.y, "dir": self.dir, "anim": self.anim, "seat": self.seat}
        if self.walk:
            d["walk"] = {"target": self.walk["target"], "duration": round(self.walk["duration"], 2),
                         "remaining": round(max(0.0, self.walk["started"] + self.walk["duration"] - now), 2)}
        return d


DIRS = ("up", "down", "left", "right")
ANIMS = ("idle", "walk")


class World:
    def __init__(self, casino, clock=time.monotonic):
        self.casino = casino
        self.clock = clock
        self.entities: dict[str, Entity] = {}

    def snapshot(self) -> dict:
        now = self.clock()
        return {"type": "world_snapshot", "entities": [e.to_dict(now) for e in self.entities.values()]}

    def add(self, entity: Entity, at: str | None = None):
        self.entities[entity.id] = entity
        msg = {"type": "entity_spawn", "entity": entity.to_dict(self.clock())}
        if at:
            msg["at"] = at
        self.casino.broadcast_all(msg)

    def remove(self, entity_id: str):
        if self.entities.pop(entity_id, None) is not None:
            self.casino.broadcast_all({"type": "entity_despawn", "id": entity_id})

    def move(self, entity_id: str, x: float, y: float, direction: str, anim: str, source=None):
        e = self.entities.get(entity_id)
        if e is None or e.seat is not None:
            return
        e.x, e.y = x, y
        e.dir = direction if direction in DIRS else e.dir
        e.anim = anim if anim in ANIMS else "idle"
        self.casino.broadcast_all({"type": "entity_move", "id": entity_id, "x": x, "y": y,
                                   "dir": e.dir, "anim": e.anim}, exclude=source)

    def walk(self, entity_id: str, target: str, duration: float, start: tuple | None = None):
        """`start`: where the walk sets off from, so a snapshot mid-walk starts them there (not at the spawn point)."""
        e = self.entities.get(entity_id)
        if e is None:
            return
        if start is not None:
            e.x, e.y = start
        e.walk = {"target": target, "duration": duration, "started": self.clock()}
        self.casino.broadcast_all({"type": "entity_walk", "id": entity_id, "target": target,
                                   "duration": round(duration, 2)})

    def arrived(self, entity_id: str, at: tuple | None = None):
        e = self.entities.get(entity_id)
        if e is not None:
            e.walk = None
            if at is not None:
                e.x, e.y = at

    def rename(self, entity_id: str, name: str):
        e = self.entities.get(entity_id)
        if e is not None:
            e.name = name
            self.casino.broadcast_all({"type": "entity_update", "id": entity_id, "name": name})

    def restyle(self, entity_id: str, look: str | None = None, name: str | None = None):
        """An NPC's look or name changed on the admin page: everyone sees it now."""
        e = self.entities.get(entity_id)
        if e is None:
            return
        msg = {"type": "entity_update", "id": entity_id}
        if look:
            e.look = msg["look"] = look
        if name:
            e.name = msg["name"] = name
        self.casino.broadcast_all(msg)

    def set_seat(self, entity_id: str, table: str | None, seat: int | None):
        e = self.entities.get(entity_id)
        if e is not None:
            e.seat = None if table is None else {"table": table, "seat": seat}
            e.walk = None
