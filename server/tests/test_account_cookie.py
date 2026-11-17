"""The account cookie: the game's own tab keeps its token as a cookie (POST /account-cookie), and a game in another
page's frame (Citadel's Casino page), whose partitioned storage holds a different token or none, joins with it."""
from conftest import recv_until

COOKIE = "casino_account"


def new_account(client, cookie=None, **join):
    """A fresh socket's `account` reply: joins with `join` ({token, framed}), bringing `cookie` if given."""
    headers = {"cookie": f"{COOKIE}={cookie}"} if cookie else {}
    with client.websocket_connect("/ws", headers=headers) as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "join", "token": "", **join})
        return recv_until(ws, "account")


def test_the_cookie_is_set_for_a_real_account(client):
    token = new_account(client)["token"]
    r = client.post("/account-cookie", json={"token": token})
    assert r.status_code == 204
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}={token};")
    for part in ("HttpOnly", "Secure", "SameSite=none", "Path=/", "Max-Age="):
        assert part.lower() in cookie.lower()


def test_no_cookie_for_an_unknown_token_or_without_json(client):
    assert client.post("/account-cookie", json={"token": "nobody"}).status_code == 404
    assert client.post("/account-cookie", json={}).status_code == 404
    token = new_account(client)["token"]
    r = client.post("/account-cookie", data={"token": token})   # a form, as another site could post
    assert r.status_code == 415 and "set-cookie" not in r.headers


def test_a_framed_join_uses_the_cookie_over_its_own_token(client):
    mine = new_account(client)["token"]
    stray = new_account(client)["token"]   # the account a frame made in its own storage
    got = new_account(client, cookie=mine, token=stray, framed=True)
    assert got["token"] == mine


def test_a_framed_join_without_a_cookie_keeps_its_own_token(client):
    stray = new_account(client)["token"]
    assert new_account(client, token=stray, framed=True)["token"] == stray


def test_a_framed_join_with_a_stale_cookie_falls_back_to_its_token(client):
    stray = new_account(client)["token"]
    assert new_account(client, cookie="gone", token=stray, framed=True)["token"] == stray


def test_the_game_in_its_own_tab_ignores_the_cookie(client):
    mine = new_account(client)["token"]
    other = new_account(client)["token"]
    assert new_account(client, cookie=other, token=mine)["token"] == mine
