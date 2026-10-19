"""One connected client. Handlers push messages onto its queue; the socket's
sender task drains it -- so a handler can message any session (a broadcast to
a table) without awaiting anything."""
import asyncio

from casino_server.store import Player


class Session:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.player: Player | None = None
        self.entity_id: str = ""
        self.table: str | None = None  # table id while seated
        self.seat: int | None = None
        self.away = False  # tab hidden: nothing is sent until the client asks to `resync`

    def push(self, msg: dict):
        if not self.away:
            self.queue.put_nowait(msg)

    def error(self, message: str):
        self.push({"type": "error", "message": message})
