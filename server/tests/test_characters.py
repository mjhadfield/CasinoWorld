"""Accounts and characters: the character select, making, editing, deleting and picking characters, switching,
the difficulty's starting bank, bans covering the whole account, and moving an old database across."""
import sqlite3
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from casino_server.store import Store

from conftest import LOOK, enter, recv_until


def _account(ws, token=""):
    assert ws.receive_json()["type"] == "hello"
    ws.send_json({"type": "join", "token": token})
    return recv_until(ws, "account")


def _make(ws, name, difficulty="normal", look=None):
    ws.send_json({"type": "create_character", "name": name, "look": look or LOOK, "difficulty": difficulty})
    msg = ws.receive_json()
    while msg["type"] not in ("account", "error"):
        msg = ws.receive_json()
    return msg


def test_a_new_device_gets_an_empty_account_and_nobody_on_the_floor(client):
    with client.websocket_connect("/ws") as ws:
        account = _account(ws)
        assert account["characters"] == [] and account["max"] == 3 and account["token"]
        assert account["difficulties"] == {"easy": 500_000, "normal": 100_000, "hard": 25_000}
        ws.send_json({"type": "sit", "table": "tcp_1", "seat": 0})
        assert recv_until(ws, "error")["message"] == "Pick a character first."
    assert client.app.state.resort.casinos["demo"].world.entities == {}


def test_difficulty_sets_the_starting_bank_and_three_is_the_most(client):
    client.app.state.resort.casinos["demo"].store.set_json("bank_settings", {"start_hand": 0, "start_bank_hard": 300})
    with client.websocket_connect("/ws") as ws:
        _account(ws)
        for name, difficulty in (("Easy Ed", "easy"), ("Norm", "normal"), ("Hard Hal", "hard")):
            account = _make(ws, name, difficulty)
        banks = {c["name"]: (c["difficulty"], c["bank"], c["balance"]) for c in account["characters"]}
        assert banks == {"Easy Ed": ("easy", 500_000, 0), "Norm": ("normal", 100_000, 0), "Hard Hal": ("hard", 30_000, 0)}
        assert "3 characters" in _make(ws, "Fourth")["message"]


def test_names_and_looks_are_checked(client):
    with client.websocket_connect("/ws") as ws:
        _account(ws)
        assert _make(ws, "   ")["message"] == "Give your character a name."
        assert _make(ws, "Ann", look={"body": "male"})["type"] == "error"
        ws.send_json({"type": "create_character", "name": "Ann", "look": LOOK, "difficulty": "silly"})
        assert recv_until(ws, "error")["message"] == "Pick Easy, Normal or Hard."
        account = _make(ws, "  Ann   Lee  " + "x" * 20)
        assert account["characters"][0]["name"] == "Ann Lee xxxxxxxx"
        assert account["characters"][0]["look"].startswith("x_")
        assert "already have" in _make(ws, "ann lee xxxxxxxx")["message"]


def test_switching_characters_moves_you_off_and_back_on(client):
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        account = _account(a)
        first = _make(a, "Mike")["characters"][0]["id"]
        second = [c for c in _make(a, "Mo")["characters"] if c["name"] == "Mo"][0]["id"]
        enter(b, hello=True)
        a.send_json({"type": "pick_character", "id": first, "casino": "demo"})
        w1 = recv_until(a, "welcome")
        assert w1["player"]["name"] == "Mike"
        assert recv_until(b, "entity_spawn", where=lambda m: m["entity"]["id"] == w1["entity_id"])["entity"]["name"] == "Mike"
        a.send_json({"type": "sit", "table": "tcp_1", "seat": 0})
        recv_until(a, "seated")
        a.send_json({"type": "leave_character"})
        assert recv_until(a, "character_left")["reason"] == "switch"
        assert recv_until(a, "account")["last"] == first
        assert recv_until(b, "entity_despawn")["id"] == w1["entity_id"]
        assert client.app.state.resort.casinos["demo"].tables["tcp_1"].machine.seats[0].participant is None
        a.send_json({"type": "pick_character", "id": second, "casino": "demo"})
        w2 = recv_until(a, "welcome")
        assert w2["player"]["name"] == "Mo" and w2["entity_id"] != w1["entity_id"]
        assert recv_until(b, "entity_spawn", where=lambda m: m["entity"]["id"] == w2["entity_id"])["entity"]["name"] == "Mo"
        assert account["token"]


def test_picking_a_character_playing_elsewhere_takes_it_over_unless_resuming(client):
    with client.websocket_connect("/ws") as a:
        account, welcome = enter(a, hello=True, name="Mike")
        pid = welcome["player"]["id"]
        with client.websocket_connect("/ws") as b:
            _account(b, account["token"])
            b.send_json({"type": "pick_character", "id": pid, "resume": True})
            assert recv_until(b, "character_left") == {"type": "character_left", "reason": "elsewhere", "name": "Mike"}
            assert recv_until(b, "account")["characters"][0]["online"]
            b.send_json({"type": "edit_character", "id": pid, "name": "Mick", "look": LOOK})
            assert "on the floor" in recv_until(b, "error")["message"]
            b.send_json({"type": "pick_character", "id": pid, "casino": "demo"})
            recv_until(b, "welcome")
            assert recv_until(a, "character_left")["reason"] == "elsewhere"
            assert recv_until(a, "account")
            assert client.app.state.resort.casinos["demo"].online_players() == {pid}


def test_edit_and_delete_from_the_select(client):
    with client.websocket_connect("/ws") as ws:
        _account(ws)
        pid = _make(ws, "Mike")["characters"][0]["id"]
        look = {**LOOK, "hair": ["afro", "black"]}
        ws.send_json({"type": "edit_character", "id": pid, "name": "Mick", "look": look})
        c = recv_until(ws, "account")["characters"][0]
        other = _make(ws, "Other")["characters"][1]
        assert c["name"] == "Mick" and other["name"] == "Other" and c["look"] != other["look"]
        ws.send_json({"type": "delete_character", "id": pid})
        assert [c["name"] for c in recv_until(ws, "account")["characters"]] == ["Other"]
        ws.send_json({"type": "delete_character", "id": 999})
        assert recv_until(ws, "error")["message"] == "No such character."
    store = client.app.state.resort.casinos["demo"].store
    assert store.character(pid) is None
    assert not store.db.execute("SELECT 1 FROM ledger WHERE player_id = ?", (pid,)).fetchone()


def test_someone_elses_character_cant_be_picked(client):
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        _, welcome = enter(a, hello=True)
        _account(b)
        b.send_json({"type": "pick_character", "id": welcome["player"]["id"]})
        assert recv_until(b, "error")["message"] == "No such character."


def test_a_ban_covers_every_character_on_the_account(client):
    ws = client.websocket_connect("/ws")
    ws.__enter__()
    account = _account(ws)
    ids = [c["id"] for c in _make(ws, "Mo")["characters"]]
    _make(ws, "Mike")
    ws.send_json({"type": "pick_character", "id": ids[0], "casino": "demo"})
    recv_until(ws, "welcome")
    assert client.post(f"/api/players/{ids[0]}/ban", json={"reason": "Card marking"}).status_code == 200
    assert recv_until(ws, "barred")["kind"] == "ban"
    with pytest.raises(WebSocketDisconnect):
        ws.receive_json()
    ws.__exit__(None, None, None)
    players = {p["name"]: p for p in client.get("/api/players").json()["players"]}
    assert players["Mike"]["banned"] and players["Mike"]["account_id"] == players["Mo"]["account_id"]
    with client.websocket_connect("/ws") as again:
        again.send_json({"type": "join", "token": account["token"]})
        assert recv_until(again, "barred")["kind"] == "ban"


def test_deleting_an_account_takes_all_its_characters(client):
    with client.websocket_connect("/ws") as ws:
        account = _account(ws)
        _make(ws, "Mo")
        aid = client.app.state.resort.casinos["demo"].store.account_by_token(account["token"])["id"]
        r = client.delete(f"/api/accounts/{aid}")
        assert r.status_code == 200 and r.json()["names"] == ["Mo"]
        assert recv_until(ws, "barred")["kind"] == "removed"
    assert client.app.state.resort.casinos["demo"].store.account_by_token(account["token"]) is None
    assert client.delete(f"/api/accounts/{aid}").status_code == 404


def test_look_options_are_the_catalogue(client):
    data = client.get("/api/look-options").json()
    assert data["bodies"] == ["male", "female"] and "hair" in [s["slot"] for s in data["slots"]]


def test_an_old_database_moves_each_player_to_an_account(tmp_path):
    path = tmp_path / "old.sqlite"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE players (id INTEGER PRIMARY KEY, token TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                              balance INTEGER NOT NULL, created_at TEXT NOT NULL, bank INTEGER NOT NULL DEFAULT 0,
                              last_withdraw_at REAL, last_big_at REAL, protected INTEGER NOT NULL DEFAULT 0,
                              banned INTEGER NOT NULL DEFAULT 0, timeout_until REAL, bar_reason TEXT);
        CREATE TABLE ledger (id INTEGER PRIMARY KEY, player_id INTEGER NOT NULL REFERENCES players(id), at TEXT NOT NULL,
                             kind TEXT NOT NULL, amount INTEGER NOT NULL, balance_after INTEGER NOT NULL, game TEXT,
                             note TEXT, account TEXT NOT NULL DEFAULT 'hand');
        INSERT INTO players VALUES (1, 'tok1', 'Mike', 23400, '2026-01-01', 90000, NULL, NULL, 1, 0, NULL, NULL);
        INSERT INTO players VALUES (4, 'tok4', 'Guest 4', 0, '2026-01-02', 100000, NULL, NULL, 0, 1, NULL, 'rude');
        INSERT INTO ledger VALUES (1, 1, '2026-01-01', 'payout', 23400, 23400, 'craps', NULL, 'hand');""")
    db.commit()
    db.close()
    store = Store(path)
    mike = store.characters(store.account_by_token("tok1")["id"])
    assert [(p.id, p.name, p.balance, p.bank, p.difficulty, p.look) for p in mike] == [(1, "Mike", 23400, 90000, "normal", None)]
    assert store.player(1)["protected"] and store.barred(store.account_by_token("tok4")["id"], time.time())["reason"] == "rude"
    assert store.player_stats()[0]["returned"] == 23400
    store.adjust(1, -400, "bet", "craps")   # the ledger still points at the character
    store.close()
    assert (tmp_path / "old.pre-characters.sqlite").exists()
    store = Store(path)   # and only once
    assert store.balance(1) == 23000 and len(store.characters(1)) == 1
    store.close()
