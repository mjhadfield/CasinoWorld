"""
TableRunner: drives one table machine in real time and publishes its events.

Every player action goes through act(), which runs the machine method with the
current time, publishes the resulting events and wakes the loop. run() sleeps
until the machine's next deadline (or an action), then tick()s it. One runner
task per table, owned by the Casino's lifespan.

Every joined session gets every table's events, so tables are live to watch
from the floor. Keys starting "_" never leave the server: card faces a seat
may keep private ("_private") only go to the session in that seat (a second box's
go to its player as "mine_box", once they may see them), and "_paid"
lists participants whose balance the event changed (they get a wallet update
straight after it). Each seat's result for the hand goes out once: on its
settle_seat ("round_net"), or for a seat that had none (bust, folded, paid early)
on the round_end ("round_nets").
"""
import asyncio
import copy
import time


class TableRunner:
    def __init__(self, table_id: str, casino, machine, clock=time.monotonic):
        self.table_id = table_id
        self.casino = casino
        self.machine = machine
        self.clock = clock
        self._wake = asyncio.Event()
        self._netted = set()   # seats whose result for this hand has gone out

    def act(self, method: str, *args, **kwargs):
        """Run a machine action now; raises TableError for a rejected one."""
        events = getattr(self.machine, method)(*args, now=self.clock(), **kwargs)
        self.publish(events)
        self._wake.set()
        return events

    async def run(self):
        while True:
            deadline = self.machine.next_deadline
            timeout = None if deadline is None else max(0.0, deadline - self.clock())
            try:
                await asyncio.wait_for(self._wake.wait(), timeout)
            except TimeoutError:
                pass
            self._wake.clear()
            self.publish(self.machine.tick(self.clock()))

    # ------------------------------------------------------------------ publishing
    def viewer_seat(self, session) -> int | None:
        for i, seat in enumerate(self.machine.seats):
            p = seat.participant
            if p is not None and p.is_human and p.session is session and seat.box_of is None:
                return i
        return None

    def _box_of_viewer(self, seat: int | None) -> int | None:
        return self.machine.seats[seat].box if seat is not None else None

    def snapshot_for(self, session) -> dict:
        dealers = getattr(self.casino, "dealers", None)
        seat = self.viewer_seat(session)
        return {"type": "table_state", "table": self.table_id,
                **self.machine.snapshot(seat, self.clock()),
                "my_box": self._box_of_viewer(seat), "second_box": bool(getattr(self.machine, "SECOND_BOX", False)),
                "on_duty": dealers.on_table(self.table_id) if dealers and getattr(self.machine, "DEALER", True) else None}

    def publish(self, events: list):
        for event in events:
            self._side_effects(event)
            self._add_nets(event)
            private = event.get("_private")
            public = {k: v for k, v in event.items() if not k.startswith("_")}
            for session in self.casino.joined_sessions():
                body = public
                if private:
                    seat = self.viewer_seat(session)
                    box = self._box_of_viewer(seat)
                    if seat in private:
                        body = {**copy.deepcopy(public), "mine": private[seat]}
                    if box in private and self.machine._box_shown(box):
                        body = {**copy.deepcopy(body), "mine_box": private[box]}
                session.push({"type": "table_event", "table": self.table_id, "event": body})
            # A Master Table changed game: the whole table again, as each viewer may see it.
            if event.get("_resnap"):
                for session in self.casino.joined_sessions():
                    session.push(self.snapshot_for(session))
            # Money moved by this event: new balances follow the event that explains them.
            for participant in event.get("_paid", []):
                if participant.is_human and participant.session in self.casino.sessions:
                    self.casino.send_wallet(participant.session)

    def _add_nets(self, event: dict):
        round_net = getattr(self.machine, "round_net", None)   # (not at Craps, or a blank Master Table)
        if round_net is None:
            return
        if event["kind"] == "settle_seat":
            net = round_net(event["seat"])
            if net is not None:
                event["round_net"] = net
                self._netted.add(event["seat"])
        elif event["kind"] == "round_end":
            nets = [{"seat": i, "net": round_net(i)} for i in range(len(self.machine.seats)) if i not in self._netted]
            event["round_nets"] = [n for n in nets if n["net"] is not None]
            self._netted.clear()

    def _side_effects(self, event: dict):
        kind = event["kind"]
        if kind == "seated":
            self.casino.world.set_seat(event["entity"], self.table_id, event["seat"])
        elif kind == "stood":
            self.casino.world.set_seat(event["entity"], None, None)
            self.casino.on_stood(event["entity"], self.table_id, event.get("reason", ""))
        elif kind == "master_change":   # a Master Table's new game: everyone keeps their order, maybe in another seat
            self.casino.on_reseated(self.table_id, event["_remap"], event["map"])
        elif kind == "jackpot_won":
            self.casino.broadcast_all(self.casino.jackpot.snapshot())
        elif kind == "slot_jackpot_won":
            self.casino.broadcast_all(self.casino.slot_jackpots.snapshot())
