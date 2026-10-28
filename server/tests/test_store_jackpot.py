import pytest

from casino_server.jackpot import JACKPOT_CEILING, JACKPOT_FLOOR, Jackpot
from casino_server.store import STARTING_BANK, InsufficientFunds, Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.sqlite")
    yield s
    s.close()


def test_new_player_gets_starting_balance_and_ledger_reconciles(store):
    p = store.create_player(hand=100_000)
    assert p.balance == 100_000 and p.bank == STARTING_BANK and p.name.startswith("Guest")
    store.adjust(p.id, -2_500, "bet", "three_card_poker")
    store.adjust(p.id, 5_000, "payout", "three_card_poker")
    total = store.db.execute("SELECT SUM(amount) FROM ledger WHERE player_id = ? AND account = 'hand'", (p.id,)).fetchone()[0]
    assert total == store.balance(p.id) == 100_000 + 2_500
    assert store.characters(p.account_id)[0].id == p.id


def test_ledger_keeps_each_spot_as_json(store, tmp_path):
    import json
    p = store.create_player(hand=100_000)
    spots = {"spots": {"ante": {"stake": 500, "returned": 1_000}, "pair_plus": {"stake": 100, "returned": 0}}}
    store.adjust(p.id, 1_000, "payout", "three_card_poker", "win", spots)
    store.adjust(p.id, -500, "bet", "three_card_poker", "upfront")
    rows = store.db.execute("SELECT detail FROM ledger WHERE player_id = ? AND game IS NOT NULL ORDER BY id", (p.id,))
    assert [r[0] and json.loads(r[0]) for r in rows] == [spots, None]
    # a database from before the column gets it
    store.db.execute("ALTER TABLE ledger DROP COLUMN detail")
    store.close()
    again = Store(tmp_path / "t.sqlite")
    assert "detail" in again._columns("ledger")
    again.close()


def test_a_settled_round_that_lost_still_gets_a_row_with_its_detail(store):
    from casino_server.participants import HumanParticipant
    p = store.create_player(hand=100_000)
    session = type("S", (), {"entity_id": "e1", "player": p})()
    casino = type("C", (), {"store": store, "sessions": {session}})()
    who = HumanParticipant(session, casino, "roulette")
    who.credit(0, "lose")   # nothing back and nothing to say: no row
    who.credit(0, "lose", {"spots": {"red": {"stake": 500, "returned": 0}}})
    rows = store.db.execute("SELECT kind, amount, note FROM ledger WHERE game = 'roulette'").fetchall()
    assert [tuple(r) for r in rows] == [("payout", 0, "lose")]


def test_balance_never_goes_negative(store):
    p = store.create_player(hand=100_000)
    with pytest.raises(InsufficientFunds):
        store.adjust(p.id, -(100_000 + 1), "bet")
    assert store.balance(p.id) == 100_000


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
    player = store.create_player("Mike", hand=100_000)
    store.adjust(player.id, -2500, "bet")
    store.db.execute("UPDATE players SET balance = '100,000' WHERE id = ?", (player.id,))  # what a hand edit does
    store.db.commit()
    assert store.players()[0]["stored_as"] == "text"
    store.set_balance(player.id, 150000)
    assert store.balance(player.id) == 150000 and store.players()[0]["stored_as"] == "integer"
    last = store.db.execute("SELECT kind, amount, balance_after FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    assert tuple(last) == ("adjust", 150000 - 97500, 150000)  # measured from the last good balance
    total = store.db.execute("SELECT SUM(amount) FROM ledger WHERE player_id = ? AND account = 'hand'", (player.id,)).fetchone()[0]
    assert total == store.balance(player.id)  # the ledger still reconciles
