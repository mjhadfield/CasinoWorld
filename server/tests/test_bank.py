import sqlite3

import pytest

from casino_server import bank, plan
from casino_server.store import STARTING_BANK, InsufficientFunds, Store

from conftest import recv_until
from test_ws import join

S = bank.DEFAULT_SETTINGS
NOW = 1_000_000.0


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.sqlite")
    yield s
    s.close()


def reconciles(store, pid):
    hand, bank_ = (store.db.execute("SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE player_id = ? AND account = ?",
                                    (pid, a)).fetchone()[0] for a in ("hand", "bank"))
    return hand == store.balance(pid) and bank_ == store.bank(pid)[0]


# ------------------------------------------------------------------ the rules
def test_withdrawals_only_while_holding_under_the_limit():
    assert bank.withdraw_check(100_000, 49_999, None, S, NOW)["can"]
    c = bank.withdraw_check(100_000, 50_000, None, S, NOW)
    assert not c["can"] and c["why"] == "carrying"


def test_the_limit_rises_at_the_threshold():
    assert bank.withdraw_check(249_999, 0, None, S, NOW)["cap"] == 25_000
    assert bank.withdraw_check(250_000, 0, None, S, NOW)["cap"] == 200_000


def test_overdrawn_waits_between_withdrawals_but_the_first_dip_is_allowed():
    assert bank.withdraw_check(10_000, 0, NOW - 5, S, NOW)["can"]        # in credit: no wait, even just after one
    c = bank.withdraw_check(-15_000, 0, NOW - 60, S, NOW)                  # overdrawn a minute after the last one
    assert not c["can"] and c["why"] == "overdrawn" and c["wait"] == 29 * 60
    assert bank.withdraw_check(-15_000, 0, NOW - 30 * 60, S, NOW)["can"]   # the wait's over
    assert bank.withdraw_check(-15_000, 0, None, S, NOW)["can"]            # overdrawn by the admin, never withdrawn


def test_withdrawals_come_in_fifty_pound_notes_up_to_the_limit():
    ok = bank.withdraw_check(100_000, 0, None, S, NOW)
    assert bank.withdraw_problem(25_000, ok) is None
    assert bank.withdraw_problem(12_000, ok) == "Can't pay £120. Try £100."
    assert bank.withdraw_problem(30_000, ok) == "The most you can take is £250."
    assert bank.withdraw_problem(0, ok) and bank.withdraw_problem("50", ok) and bank.withdraw_problem(True, ok)


def test_settings_are_checked():
    assert bank.clean_settings({"high_cap": 1500, "cooldown_min": 0}) == {"high_cap": 1500, "cooldown_min": 0}
    for bad in ({"low_cap": 120}, {"low_cap": 0}, {"start_hand": -1}, {"threshold": 2.5}, {"cooldown_min": "30"}):
        with pytest.raises(ValueError):
            bank.clean_settings(bad)


# ------------------------------------------------------------------ the store
def test_a_new_player_starts_with_the_bank_and_nothing_in_hand(store):
    p = store.create_player()
    assert (p.balance, p.bank, p.last_withdraw_at) == (0, STARTING_BANK, None)
    assert reconciles(store, p.id)


def test_transfers_move_money_and_the_bank_can_go_overdrawn(store):
    p = store.create_player(bank=10_000)
    assert store.transfer(p.id, 25_000, NOW) == (-15_000, 25_000)
    assert store.bank(p.id) == (-15_000, NOW)
    assert store.transfer(p.id, -5_000, NOW + 10) == (-10_000, 20_000)
    assert store.bank(p.id) == (-10_000, NOW)   # (a deposit doesn't restart the wait)
    with pytest.raises(InsufficientFunds):
        store.transfer(p.id, -20_001, NOW)
    assert reconciles(store, p.id)
    assert [h["kind"] for h in store.atm_history(p.id)] == ["deposit", "withdraw"]


def test_existing_players_keep_their_balance_as_cash_and_get_the_starting_bank(tmp_path):
    db = sqlite3.connect(tmp_path / "old.sqlite")   # the database as it was before the bank
    db.executescript("""
        CREATE TABLE players (id INTEGER PRIMARY KEY, token TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                              balance INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE ledger (id INTEGER PRIMARY KEY, player_id INTEGER NOT NULL REFERENCES players(id), at TEXT NOT NULL,
                             kind TEXT NOT NULL, amount INTEGER NOT NULL, balance_after INTEGER NOT NULL, game TEXT, note TEXT);
        INSERT INTO players VALUES (1, 'tok', 'Mike', 234000, '2026-01-01');
        INSERT INTO ledger VALUES (1, 1, '2026-01-01', 'start', 100000, 100000, NULL, NULL);
        INSERT INTO ledger VALUES (2, 1, '2026-01-02', 'payout', 134000, 234000, 'craps', NULL);""")
    db.commit()
    db.close()
    store = Store(tmp_path / "old.sqlite")
    p = store.player_by_token("tok")
    assert (p.balance, p.bank) == (234_000, STARTING_BANK) and reconciles(store, p.id)
    store.close()
    store = Store(tmp_path / "old.sqlite")   # and only once
    assert store.bank(1)[0] == STARTING_BANK and reconciles(store, 1)
    store.close()


def test_atms_are_the_interact_pieces_on_placed_rooms(monkeypatch):
    monkeypatch.setitem(plan.ASSETS, "test_atm", {"mount": "floor", "interact": "atm"})
    monkeypatch.setitem(plan.ASSETS, "test_sofa", {"mount": "floor"})
    rooms = [{"placed": True, "x": 100, "y": 50, "items": [{"asset": "a:test_atm", "x": 380, "y": 88},
                                                           {"asset": "a:test_sofa", "x": 10, "y": 10}]},
             {"placed": False, "x": 0, "y": 0, "items": [{"asset": "a:test_atm", "x": 0, "y": 0}]}]
    monkeypatch.setattr(plan, "live", lambda: {"rooms": rooms})
    assert bank.atms() == [(480, 138)]
    assert bank.near_atm(480, 160) and not bank.near_atm(480, 260) and not bank.near_atm(None, None)


# ------------------------------------------------------------------ the ATM, over the socket
def test_the_atm(client, monkeypatch):
    monkeypatch.setattr(bank, "atms", lambda: [(400.0, 100.0)])
    client.put("/api/bank-settings", json={"start_hand": 0})
    with client.websocket_connect("/ws") as ws:
        welcome, wallet, *_ = join(ws)
        assert wallet["balance"] == 0
        ws.send_json({"type": "atm_open"})
        assert recv_until(ws, "error")["message"] == "Walk up to the ATM to use it."
        ws.send_json({"type": "move", "x": 400, "y": 120, "dir": "up", "anim": "idle"})
        ws.send_json({"type": "atm_open"})
        atm = recv_until(ws, "atm")
        assert (atm["bank"], atm["can"], atm["cap"], atm["threshold"], atm["history"]) == (100_000, True, 25_000, 250_000, [])
        ws.send_json({"type": "atm_withdraw", "amount": 12_000})
        assert recv_until(ws, "atm")["error"] == "Can't pay £120. Try £100."
        ws.send_json({"type": "atm_withdraw", "amount": 25_000})
        assert recv_until(ws, "wallet")["balance"] == 25_000
        atm = recv_until(ws, "atm")
        assert atm["done"] == {"kind": "withdraw", "amount": 25_000} and atm["bank"] == 75_000
        ws.send_json({"type": "atm_deposit", "amount": 30_000})
        assert recv_until(ws, "atm")["error"] == "You're not holding that much."
        ws.send_json({"type": "atm_deposit", "amount": 2_550})
        assert recv_until(ws, "wallet")["balance"] == 22_450
        atm = recv_until(ws, "atm")
        assert atm["bank"] == 77_550 and [h["kind"] for h in atm["history"]] == ["deposit", "withdraw"]
        ws.send_json({"type": "top_up"})
        assert recv_until(ws, "error")["message"] == "Unknown message type: top_up"


def test_bank_settings_api(client):
    assert client.get("/api/bank-settings").json()["threshold"] == 2500
    r = client.put("/api/bank-settings", json={"high_cap": 1500})
    assert r.status_code == 200 and r.json()["high_cap"] == 1500
    assert client.put("/api/bank-settings", json={"low_cap": 75}).status_code == 400
