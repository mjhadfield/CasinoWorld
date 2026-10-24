"""The jackpot's new amount after a win names the table it was won at, so that table's sign can hold the old
amount until the win is shown there while every other sign just takes the new one."""
from casino_server.tables.runner import TableRunner


class _Casino:
    def __init__(self):
        self.sent = []
        self.jackpot = self

    def snapshot(self):
        return {"type": "jackpot", "amount": 500_000, "rate": 1.0, "ceiling": 5_000_000}

    def broadcast_all(self, msg):
        self.sent.append(msg)


def test_the_new_jackpot_after_a_win_names_the_table():
    casino = _Casino()
    TableRunner("tcp_1", casino, machine=None)._side_effects({"kind": "jackpot_won", "seat": 2, "amount": 1_234_567})
    assert casino.sent == [{"type": "jackpot", "amount": 500_000, "rate": 1.0, "ceiling": 5_000_000, "table": "tcp_1"}]
