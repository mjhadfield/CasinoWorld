import time

from fastapi.testclient import TestClient

from casino_server import PROTOCOL_VERSION
from casino_server.app import app

from conftest import LOOK, enter, recv_until, rig

TABLE = "tcp_1"
STARTING_BALANCE = 100_000   # the test client's new players' cash in hand (conftest)
# Seat 0: pair of Kings. Dealer: Queen-high (qualifies). Seat 0 wins.
CODES = ["Ks", "Kd", "4c", "Qh", "9s", "3d"]


def join(ws, token="", name="Tester"):
    """Onto the floor as the account's first character (made, if it has none)."""
    assert ws.receive_json() == {"type": "hello", "protocol": PROTOCOL_VERSION}
    _, welcome = enter(ws, token, name=name)
    wallet = recv_until(ws, "wallet")
    jackpot = recv_until(ws, "jackpot")
    world = recv_until(ws, "world_snapshot")
    tables = [recv_until(ws, "table_state"), recv_until(ws, "table_state")]
    return welcome, wallet, jackpot, world, tables


def sit(ws, seat=0, table=TABLE):
    ws.send_json({"type": "sit", "table": table, "seat": seat})
    return recv_until(ws, "seated"), recv_until(ws, "table_state")


def test_join_sends_everything_and_token_remembers_player(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "join", "token": ""})
        account = recv_until(ws, "account")
        assert account["characters"] == [] and account["max"] == 3 and account["last"] is None
        token = account["token"]
        ws.send_json({"type": "create_character", "name": "Tester", "look": LOOK, "difficulty": "normal"})
        made = recv_until(ws, "character_made")["id"]
        ws.send_json({"type": "pick_character", "id": made})
        welcome = recv_until(ws, "welcome")
        wallet = recv_until(ws, "wallet")
        jackpot = recv_until(ws, "jackpot")
        world = recv_until(ws, "world_snapshot")
        tables = [recv_until(ws, "table_state"), recv_until(ws, "table_state")]
        assert wallet["balance"] == STARTING_BALANCE and welcome["look"].startswith("x_")
        assert welcome["entity_id"].startswith(f"p{welcome['player']['id']}-")
        assert jackpot["rate"] > 0 and world["entities"] == []
        assert {t["table"] for t in tables} == {"tcp_1", "bj_1"}
        assert tables[0]["phase"] == "betting" and len(tables[0]["seats"]) == 6
        spawn = recv_until(ws, "entity_spawn")
        assert spawn["entity"]["id"] == welcome["entity_id"] and spawn["at"] == "point:classic_floor/spawn"
        assert spawn["entity"]["look"] == welcome["look"]
        player_id = welcome["player"]["id"]
    with client.websocket_connect("/ws") as ws:
        welcome, *_ = join(ws, token)
        assert welcome["player"]["id"] == player_id


def test_presence_between_two_players(client):
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        wa, *_ = join(a, name="Mike H")
        wb, _, _, world_b, _ = join(b)
        assert [(e["id"], e["name"]) for e in world_b["entities"]] == [(wa["entity_id"], "Mike H")]
        a.send_json({"type": "move", "x": 120.5, "y": 300, "dir": "left", "anim": "walk"})
        move = recv_until(b, "entity_move")
        assert (move["x"], move["y"], move["dir"], move["anim"]) == (120.5, 300, "left", "walk")
    with client.websocket_connect("/ws") as c:
        _, _, _, world, _ = join(c)
        assert world["entities"] == []  # both earlier players have left


def test_full_seated_round_over_the_wire(client):
    rig(client, *CODES)
    with client.websocket_connect("/ws") as ws:
        join(ws)
        seated, state = sit(ws, seat=0)
        assert seated["rules"]["chips"][0] == 100 and seated["rules"]["seats"] == 6
        assert state["my_seat"] == 0

        for _ in range(5):  # rapid relative clicks all count
            ws.send_json({"type": "bet", "spot": "ante", "add": 100})
        for expected in (100, 200, 300, 400, 500):
            assert recv_until(ws, "table_event", "bet_changed")["event"]["bets"]["ante"] == expected
        ws.send_json({"type": "bet", "spot": "pair_plus", "amount": 100})
        ws.send_json({"type": "ready"})
        assert recv_until(ws, "wallet")["balance"] == STARTING_BALANCE - 600
        dealt = recv_until(ws, "table_event", "dealt")["event"]
        assert dealt["mine"] == {"cards": ["Ks", "Kd", "4c"], "hand": "Pair"}
        assert recv_until(ws, "table_event", "decisions_open")["event"]["seats"] == [0]

        ws.send_json({"type": "decide", "play": True})
        assert recv_until(ws, "wallet")["balance"] == STARTING_BALANCE - 1_100
        reveal = recv_until(ws, "table_event", "dealer_reveal")["event"]
        assert reveal["cards"] == ["Qh", "9s", "3d"]
        pay = recv_until(ws, "table_event", "settle_seat")["event"]
        assert pay["cards"] == ["Ks", "Kd", "4c"]
        assert pay["outcome"] == "win" and pay["net"] == 1_100
        assert recv_until(ws, "wallet")["balance"] == STARTING_BALANCE + 1_100
        recv_until(ws, "table_event", "betting_open")

        ws.send_json({"type": "rebet"})
        assert recv_until(ws, "table_event", "bet_changed")["event"]["bets"]["pair_plus"] == 100
        ws.send_json({"type": "stand"})
        assert recv_until(ws, "table_event", "stood")["event"]["seat"] == 0


def test_blackjack_round_over_the_wire(client):
    # Mike: 10, 9 (19) and Super Pairs; dealer 6 up, 10 down, draws a 2 to 18.
    rig(client, "10h", "6c", "9d", "10s", "2d", *["3c"] * 20, table="bj_1")
    with client.websocket_connect("/ws") as ws:
        join(ws)
        seated, state = sit(ws, seat=0, table="bj_1")
        assert seated["rules"]["game"] == "blackjack" and state["shoe"]["remaining"] == 25
        ws.send_json({"type": "bet", "spot": "bet", "add": 1_000})
        ws.send_json({"type": "bet", "spot": "super_pairs", "add": 100})
        ws.send_json({"type": "ready"})
        assert recv_until(ws, "wallet")["balance"] == STARTING_BALANCE - 1_100
        dealt = recv_until(ws, "table_event", "dealt")["event"]
        assert dealt["cards"] == {"0": ["10h", "9d"]} and dealt["dealer_up"] == "6c" and "mine" not in dealt
        side = recv_until(ws, "table_event", "side_bets")["event"]
        assert side["seats"][0]["steps"] == [{"spot": "super_pairs", "action": "collect", "amount": 100}]
        turn = recv_until(ws, "table_event", "turn")["event"]
        assert turn["seat"] == 0 and turn["options"] == ["hit", "stand", "double"]
        ws.send_json({"type": "act", "action": "split"})
        assert "pair" in recv_until(ws, "error")["message"]
        ws.send_json({"type": "act", "action": "stand"})
        assert recv_until(ws, "table_event", "dealer_reveal")["event"]["cards"] == ["6c", "10s"]
        assert recv_until(ws, "table_event", "dealer_draw")["event"]["card"] == "2d"
        settle = recv_until(ws, "table_event", "settle_seat")["event"]
        assert settle["hands"][0]["outcome"] == "Win"
        assert recv_until(ws, "wallet")["balance"] == STARTING_BALANCE - 1_100 + 2_000
        recv_until(ws, "table_event", "betting_open")


def test_pai_gow_round_over_the_wire(client):
    from test_pai_gow_machine import FixedRng, Hands, NOTHING
    m = client.app.state.casino.tables["pgf_1"].machine
    m.deck_factory = lambda: Hands([NOTHING, ["As", "Ad", "Kc", "Kd", "9h", "5s", "3c"]])
    m.rng = FixedRng(1)
    with client.websocket_connect("/ws") as ws:
        join(ws)
        seated, state = sit(ws, seat=0, table="pgf_1")
        assert seated["rules"]["game"] == "pai_gow_fortune" and state["face_up"] is False
        ws.send_json({"type": "bet", "spot": "ante", "add": 1_000})
        ws.send_json({"type": "ready"})
        dealt = recv_until(ws, "table_event", "dealt")["event"]
        assert sorted(dealt["mine"]["cards"]) == sorted(["As", "Ad", "Kc", "Kd", "9h", "5s", "3c"])
        recv_until(ws, "table_event", "setting_open")
        ws.send_json({"type": "pg_suggest"})
        suggest = recv_until(ws, "pg_suggest")
        assert suggest["front_label"] == "Pair of Kings" and suggest["back_label"] == "Pair of Aces"
        ws.send_json({"type": "pg_check", "front": ["As", "Ad"], "back": ["Kc", "Kd", "9h", "5s", "3c"]})
        assert recv_until(ws, "pg_check")["foul"]
        ws.send_json({"type": "set_hand", "front": suggest["front"], "back": suggest["back"]})
        mine = recv_until(ws, "table_event", "hand_set")["event"]
        assert mine["mine"]["back_label"] == "Pair of Aces"
        assert recv_until(ws, "table_event", "dealer_set")["event"]["back_label"] == "King high"
        settle = recv_until(ws, "table_event", "settle_seat")["event"]
        assert settle["outcome"] == "win" and settle["commission"] == 50
        assert recv_until(ws, "wallet")["balance"] == STARTING_BALANCE + 950


def test_passers_by_see_events_but_not_private_cards(client):
    rig(client, *CODES)
    with client.websocket_connect("/ws") as player, client.websocket_connect("/ws") as watcher:
        join(player)
        join(watcher)
        sit(player, seat=3)
        player.send_json({"type": "bet", "spot": "ante", "amount": 100})
        player.send_json({"type": "ready"})
        dealt = recv_until(watcher, "table_event", "dealt")["event"]
        assert "mine" not in dealt and dealt["order"][0] == [3, 0]
        assert recv_until(player, "table_event", "dealt")["event"]["mine"]["cards"] == ["Ks", "Kd", "4c"]


def test_seat_rules_and_turn_errors(client):
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        join(a)
        join(b)
        sit(a, seat=1)
        b.send_json({"type": "sit", "table": TABLE, "seat": 1})
        assert "taken" in recv_until(b, "error")["message"]
        b.send_json({"type": "sit", "table": TABLE, "seat": 9})
        assert recv_until(b, "error")
        b.send_json({"type": "bet", "spot": "ante", "amount": 100})
        assert "Sit" in recv_until(b, "error")["message"]
        a.send_json({"type": "decide", "play": True})
        assert recv_until(a, "error")
        a.send_json({"type": "sit", "table": "bj_1", "seat": 0})
        assert "already" in recv_until(a, "error")["message"]


def test_disconnect_mid_hand_stands_you_up_and_table_carries_on(client):
    rig(client, *CODES)
    with client.websocket_connect("/ws") as watcher:
        join(watcher)
        with client.websocket_connect("/ws") as player:
            join(player)
            sit(player, seat=0)
            player.send_json({"type": "bet", "spot": "ante", "amount": 100})
            player.send_json({"type": "ready"})
            recv_until(player, "table_event", "decisions_open")
        stood = recv_until(watcher, "table_event", "stood")["event"]
        assert stood["seat"] == 0
        recv_until(watcher, "table_event", "betting_open")
        machine = client.app.state.casino.tables[TABLE].machine
        assert machine.phase == "betting" and machine.free_seats() == list(range(6))


def test_ping_and_bad_json(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "ping", "t": 42})
        assert ws.receive_json() == {"type": "pong", "t": 42}
        ws.send_json({"type": "sit", "table": TABLE, "seat": 0})
        assert "join" in ws.receive_json()["message"]


def _until_resync(ws):
    """Everything received before the `resync` marker, and the marker."""
    before = []
    while (msg := ws.receive_json())["type"] != "resync":
        before.append(msg)
    return before, msg


def test_away_pauses_messages_and_resync_sends_fresh_state(client):
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        wa, *_ = join(a)
        join(b)
        a.send_json({"type": "away"})
        time.sleep(0.2)                       # (b's move below must land after a went away)
        b.send_json({"type": "move", "x": 50, "y": 60, "dir": "up", "anim": "walk"})
        b.send_json({"type": "ping", "t": 2})
        recv_until(b, "pong")
        a.send_json({"type": "resync"})
        before, marker = _until_resync(a)
        assert not any(m["type"] == "entity_move" for m in before)  # nothing was sent while away
        assert marker == {"type": "resync", "table": None, "seat": None}
        assert [a.receive_json()["type"] for _ in range(5)] == ["welcome", "wallet", "jackpot", "slot_jackpots", "world_snapshot"]
        assert {a.receive_json()["table"] for _ in range(2)} == {"tcp_1", "bj_1"}
        a.send_json({"type": "ping", "t": 1})  # and messages flow again
        assert recv_until(a, "pong")["t"] == 1


def test_resync_marker_says_where_you_sit(client):
    with client.websocket_connect("/ws") as ws:
        join(ws)
        sit(ws, seat=2)
        ws.send_json({"type": "away"})
        ws.send_json({"type": "resync"})
        _, marker = _until_resync(ws)
        assert (marker["table"], marker["seat"]) == (TABLE, 2)
        state = recv_until(ws, "table_state", where=lambda m: m["table"] == TABLE)
        assert state["my_seat"] == 2


def test_resync_before_join_sends_hello_again(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "away"})
        ws.send_json({"type": "resync"})
        _until_resync(ws)
        assert ws.receive_json() == {"type": "hello", "protocol": PROTOCOL_VERSION}
        ws.send_json({"type": "join", "token": ""})
        assert recv_until(ws, "account")["characters"] == []


def test_lan_http_redirects_to_https_but_localhost_does_not():
    app.state.https_port = 8661
    try:
        client = TestClient(app, base_url="http://192.168.0.66:8660")
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 307 and r.headers["location"] == "https://192.168.0.66:8661/"
        local = TestClient(app, base_url="http://localhost:8660")
        assert local.get("/", follow_redirects=False).status_code == 200
        https = TestClient(app, base_url="https://192.168.0.66:8661")
        assert https.get("/", follow_redirects=False).status_code == 200
    finally:
        del app.state.https_port
