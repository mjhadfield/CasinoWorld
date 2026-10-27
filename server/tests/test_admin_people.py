"""The admin page's people: the NPC archive, staff roles and uniforms, and managing players
(protect, ban, time out, delete)."""
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import enter, recv_until

LOOK = {"body": "female", "skin": "olive", "hair": ["bob", "black"], "top": ["tshirt", "teal"],
        "bottom": ["pants", "navy"], "shoes": ["shoes", "black"]}


def _npc(client, name="Wendy", role="punter"):
    r = client.post("/api/npcs", json={"name": name, "role": role, "look": LOOK})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- the archive
def test_archived_npcs_leave_the_roster_and_come_back(client):
    npc = _npc(client)
    r = client.post(f"/api/npcs/{npc['id']}/archive")
    assert r.status_code == 200 and r.json()["archived_at"]
    data = client.get("/api/npcs").json()
    assert npc["id"] not in [n["id"] for n in data["npcs"]] and [n["id"] for n in data["archived"]] == [npc["id"]]
    store = client.app.state.resort.casinos["demo"].store
    assert npc["id"] not in [n["id"] for n in store.npcs("punter")]          # the director never picks them
    assert client.post(f"/api/npcs/{npc['id']}/bring-in").status_code == 400
    assert client.post(f"/api/npcs/{npc['id']}/restore").status_code == 200
    assert npc["id"] in [n["id"] for n in client.get("/api/npcs").json()["npcs"]]


def test_an_archived_dealer_on_duty_is_relieved(client):
    casino = client.app.state.resort.casinos["demo"]
    table_id, on = next((t, d) for t, d in casino.dealers.on_duty.items() if d["id"])
    for other in casino.store.npcs("dealer"):   # nobody free to take over: the house's generic Dealer does
        if other["id"] != on["id"] and other["id"] not in {d["id"] for d in casino.dealers.on_duty.values()}:
            casino.store.set_archived(other["id"], True)
    assert client.post(f"/api/npcs/{on['id']}/archive").status_code == 200
    runner = casino.tables[table_id]
    runner.machine.phase = "betting"
    casino.dealers.tick(casino.clock())
    assert casino.dealers.on_table(table_id)["id"] is None


# ---------------------------------------------------------------- staff roles and uniforms
def test_a_new_role_with_its_own_uniform(client):
    r = client.post("/api/staff/uniforms", json={"name": "Waitress", "fits": "same",
                                                  "pieces": {"top": ["tshirt", "white"], "bottom": ["pants", "black"],
                                                             "shoes": ["shoes", "black"]}})
    assert r.status_code == 200, r.text
    uni = r.json()["key"]
    u = r.json()["uniforms"][uni]
    assert u["male"] == u["female"] and not u["builtin"]
    # the same for both: every piece must come in both fits
    assert client.post("/api/staff/uniforms", json={"name": "Shirts", "fits": "same",
                                                     "pieces": {"top": ["formal", "white"], "bottom": ["pants", "black"]}}).status_code == 400
    assert client.post("/api/staff/uniforms", json={"name": "waitress", "fits": "same", "pieces": u["male"]}).status_code == 400

    r = client.post("/api/staff/roles", json={"label": "Waitress", "uniform": uni})
    assert r.status_code == 200, r.text
    role = r.json()["key"]
    assert role == "waitress" and client.get("/api/npc-options").json()["roles"][role] == "Waitress"
    drafts = client.post("/api/npcs/generate", json={"count": 3, "role": role}).json()["drafts"]
    assert all(d["role"] == role and d["look"]["top"] == ["tshirt", "white"] for d in drafts)
    npc = _npc(client, "Wanda", role)

    # in use: neither can go
    assert client.delete(f"/api/staff/uniforms/{uni}").status_code == 400
    assert client.delete(f"/api/staff/roles/{role}").status_code == 400
    assert client.delete("/api/staff/roles/pit_boss").status_code == 400       # built in
    assert client.delete("/api/staff/uniforms/dealer").status_code == 400      # built in

    # change the uniform, then dress everyone in the role in it
    r = client.put(f"/api/staff/uniforms/{uni}", json={"name": "Waitress", "fits": "split",
                                                        "male": {"top": ["formal", "white"], "bottom": ["pants", "black"]},
                                                        "female": {"top": ["blouse", "white"], "bottom": ["skirt_straight", "black"]}})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/staff/uniforms/{uni}/dress").json()["dressed"] == ["Wanda"]
    assert client.get(f"/api/npcs/{npc['id']}").json()["look"]["top"] == ["blouse", "white"]

    client.post(f"/api/npcs/{npc['id']}/archive")
    assert client.delete(f"/api/staff/roles/{role}").status_code == 400        # archived people count
    client.delete(f"/api/npcs/{npc['id']}")
    assert client.delete(f"/api/staff/roles/{role}").status_code == 200
    assert client.delete(f"/api/staff/uniforms/{uni}").status_code == 200


def test_built_in_roles_can_change_uniform(client):
    r = client.post("/api/staff/uniforms", json={"name": "Red shirts", "fits": "same",
                                                  "pieces": {"top": ["tshirt", "red"], "bottom": ["pants", "black"]}})
    uni = r.json()["key"]
    r = client.put("/api/staff/roles/dealer", json={"label": "Croupier", "uniform": uni})
    assert r.status_code == 200 and r.json()["roles"]["dealer"] == {"label": "Dealer", "uniform": uni, "builtin": True}
    assert client.put("/api/staff/roles/punter", json={"uniform": uni}).status_code == 400


# ---------------------------------------------------------------- players
def _join(client, token=""):
    """On the floor as the account's first character: (socket, welcome with the account's token added)."""
    ws = client.websocket_connect("/ws")
    ws.__enter__()
    account, welcome = enter(ws, token)
    return ws, {**welcome, "token": account["token"]}


def test_a_banned_player_is_sent_off_and_kept_out(client):
    ws, welcome = _join(client)
    pid, token = welcome["player"]["id"], welcome["token"]
    assert next(p for p in client.get("/api/players").json()["players"] if p["id"] == pid)["online"]
    assert client.post(f"/api/players/{pid}/ban", json={"reason": "Card marking"}).status_code == 200
    msg = recv_until(ws, "barred")
    assert msg["kind"] == "ban" and msg["reason"] == "Card marking" and msg["retry_in"] is None
    with pytest.raises(WebSocketDisconnect):
        ws.receive_json()
    ws.__exit__(None, None, None)

    with client.websocket_connect("/ws") as again:
        again.send_json({"type": "join", "token": token})
        assert recv_until(again, "barred")["kind"] == "ban"
    assert client.post(f"/api/players/{pid}/lift").status_code == 200
    ws, welcome = _join(client, token)
    assert welcome["player"]["id"] == pid
    ws.__exit__(None, None, None)


def test_a_timeout_runs_out(client):
    ws, welcome = _join(client)
    ws.__exit__(None, None, None)
    pid, token = welcome["player"]["id"], welcome["token"]
    assert client.post(f"/api/players/{pid}/timeout", json={"minutes": 0}).status_code == 400
    assert client.post(f"/api/players/{pid}/timeout", json={"minutes": 10}).status_code == 200
    with client.websocket_connect("/ws") as again:
        again.send_json({"type": "join", "token": token})
        msg = recv_until(again, "barred")
        assert msg["kind"] == "timeout" and 590 <= msg["retry_in"] <= 600
    store = client.app.state.resort.casinos["demo"].store
    store.set_bar(store.character(pid).account_id, until=time.time() - 1)
    ws, welcome = _join(client, token)
    assert welcome["player"]["id"] == pid
    ws.__exit__(None, None, None)


def test_protected_players_cant_be_touched(client):
    ws, welcome = _join(client)
    ws.__exit__(None, None, None)
    pid = welcome["player"]["id"]
    assert client.post(f"/api/players/{pid}/protect", json={"on": True}).json()["protected"]
    for call in (lambda: client.delete(f"/api/players/{pid}"), lambda: client.post(f"/api/players/{pid}/ban", json={}),
                 lambda: client.post(f"/api/players/{pid}/timeout", json={"minutes": 5})):
        r = call()
        assert r.status_code == 400 and "protected" in r.json()["detail"]
    client.post(f"/api/players/{pid}/protect", json={"on": False})
    assert client.delete(f"/api/players/{pid}").status_code == 200
    assert pid not in [p["id"] for p in client.get("/api/players").json()["players"]]


def test_deleting_a_player_who_is_playing(client):
    ws, welcome = _join(client)
    pid = welcome["player"]["id"]
    assert client.delete(f"/api/players/{pid}").status_code == 200
    assert recv_until(ws, "barred")["kind"] == "removed"
    ws.__exit__(None, None, None)
    store = client.app.state.resort.casinos["demo"].store
    assert store.adjust(pid, 500, "payout") == 0 and store.balance(pid) == 0   # a hand finishing after: dropped
    assert store.db.execute("SELECT COUNT(*) FROM ledger WHERE player_id = ?", (pid,)).fetchone()[0] == 0
