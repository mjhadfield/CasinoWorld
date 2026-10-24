"""One connected client. Handlers push messages onto its queue; the socket's
sender task drains it -- so a handler can message any session (a broadcast to
a table) without awaiting anything."""
import asyncio
import threading

from casino_server.store import Player

## Messages waiting for a client that isn't reading them (a stalled tab that never said `away`). Past this it's
## cut off: the queue is dropped and the socket closed, and the client reconnects to a fresh snapshot.
MAX_BACKLOG = 2000


class Session:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._loop_thread = threading.get_ident()
        self.player: Player | None = None
        self.entity_id: str = ""
        self.table: str | None = None  # table id while seated
        self.seat: int | None = None
        self.away = False  # tab hidden: nothing is sent until the client asks to `resync`
        self.preview: str | None = None  # a floor-plan preview (the room it shows): no body, no tables, not "joined"

    def push(self, msg: dict):
        if self._loop and threading.get_ident() != self._loop_thread:   # (an admin request in the threadpool)
            self._loop.call_soon_threadsafe(self.push, msg)
            return
        if self.away:
            return
        if self.queue.qsize() >= MAX_BACKLOG:
            self.away = True
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(None)   # the sender closes the socket
            return
        self.queue.put_nowait(msg)

    def close(self):
        """Hang up once what's queued has gone (the sender closes the socket at the None)."""
        self.queue.put_nowait(None)

    def error(self, message: str):
        self.push({"type": "error", "message": message})
