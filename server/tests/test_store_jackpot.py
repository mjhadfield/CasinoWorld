import pytest

from casino_server.jackpot import JACKPOT_CEILING, JACKPOT_FLOOR, Jackpot
from casino_server.store import STARTING_BALANCE, InsufficientFunds, Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.sqlite")
    yield s
    s.close()


def test_new_player_gets_starting_balance_and_ledger_reconciles(store):
    p = store.create_player()
    assert p.balance == STARTING_BALANCE and p.name.startswith("Guest")
    store.adjust(p.id, -2_500, "bet", "three_card_poker")
    store.adjust(p.id, 5_000, "payout", "three_card_poker")
    total = store.db.execute("SELECT SUM(amount) FROM ledger WHERE player_id = ?", (p.id,)).fetchone()[0]
    assert total == store.balance(p.id) == STARTING_BALANCE + 2_500
    assert store.player_by_token(p.token).id == p.id


def test_balance_never_goes_negative(store):
    p = store.create_player()
    with pytest.raises(InsufficientFunds):
        store.adjust(p.id, -(STARTING_BALANCE + 1), "bet")
    assert store.balance(p.id) == STARTING_BALANCE


def test_jackpot_grows_caps_resets_and_persists(store):
    now = [0.0]
    jp = Jackpot(store, rate=100.0, clock=lambda: now[0])
    assert jp.amount == JACKPOT_FLOOR
    now[0] = 10
    assert jp.amount == JACKPOT_FLOOR + 1_000
    now[0] = 10**9
    assert jp.amount == JACKPOT_CEILING and jp.snapshot()["rate"] == 0
    assert jp.win() == JACKPOT_CEILING
    assert jp.amount == JACKPOT_FLOOR
    now[0] += 50
    jp.save()
    assert Jackpot(store, clock=lambda: 0).amount == JACKPOT_FLOOR + 5_000


def test_set_balance_repairs_a_hand_edited_balance(tmp_path):
    store = Store(tmp_path / "c.sqlite")
    player = store.create_player("Mike")
    store.adjust(player.id, -2500, "bet")
    store.db.execute("UPDATE players SET balance = '100,000' WHERE id = ?", (player.id,))  # what a hand edit does
    store.db.commit()
    assert store.players()[0]["stored_as"] == "text"
    store.set_balance(player.id, 150000)
    assert store.balance(player.id) == 150000 and store.players()[0]["stored_as"] == "integer"
    last = store.db.execute("SELECT kind, amount, balance_after FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    assert tuple(last) == ("adjust", 150000 - 97500, 150000)  # measured from the last good balance
    total = store.db.execute("SELECT SUM(amount) FROM ledger WHERE player_id = ?", (player.id,)).fetchone()[0]
    assert total == store.balance(player.id)  # the ledger still reconciles
