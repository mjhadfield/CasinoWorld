"""A session's outgoing queue: cut off when the client stops reading, and safe to push to from a worker thread."""
import asyncio
import threading

from casino_server import session as session_module
from casino_server.session import Session


def test_a_client_that_stops_reading_is_cut_off(monkeypatch):
    monkeypatch.setattr(session_module, "MAX_BACKLOG", 5)
    s = Session()
    for i in range(5):
        s.push({"type": "x", "i": i})
    assert s.queue.qsize() == 5 and not s.away
    s.push({"type": "x", "i": 5})
    assert s.away
    assert s.queue.qsize() == 1 and s.queue.get_nowait() is None   # (the sender closes the socket on None)
    s.push({"type": "x"})
    assert s.queue.empty()


def test_a_push_from_another_thread_lands_on_the_loop():
    async def main():
        s = Session()
        t = threading.Thread(target=s.push, args=({"type": "from_thread"},))
        t.start()
        t.join()
        return await asyncio.wait_for(s.queue.get(), 1.0)

    assert asyncio.run(main()) == {"type": "from_thread"}
