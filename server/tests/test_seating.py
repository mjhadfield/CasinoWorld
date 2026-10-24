"""Seating styles: the default every table uses, editing it, more styles per table."""
from conftest import enter, recv_until  # noqa: F401  (the client fixture lives in conftest)

from casino_server import seating


def test_every_table_starts_on_the_default_style(client):
    data = client.get("/api/seating").json()
    assert data["styles"] == {"default": seating.DEFAULT_STYLE} and data["tables"] == {}
    assert data["styles"]["default"]["chair"] == "stool" and data["styles"]["default"]["craps_spot"] == "footprints"
    with client.websocket_connect("/ws") as ws:
        assert enter(ws)[1]["seating"]["styles"]["default"]["sit"] == "swivel"


def test_editing_a_style_reaches_the_floor(client):
    with client.websocket_connect("/ws") as ws:
        enter(ws)
        r = client.put("/api/seating/styles/default", json={"upholstery": "#145C43", "back": 1.1, "frame": "chrome"})
        assert r.status_code == 200, r.text
        style = recv_until(ws, "seating")["seating"]["styles"]["default"]
        assert style["upholstery"] == "#145c43" and style["back"] == 1.1 and style["frame"] == "chrome"
        assert style["chair"] == "stool"   # (what wasn't sent stays)
    for bad in ({"back": 3}, {"frame": "wood"}, {"upholstery": "red"}, {"name": ""}):
        assert client.put("/api/seating/styles/default", json=bad).status_code == 400


def test_a_second_style_for_some_tables(client):
    r = client.put("/api/seating/styles/lounge_red", json={"name": "Lounge red", "chair": "lounge", "upholstery": "#a3201c"})
    assert r.status_code == 200 and r.json()["styles"]["lounge_red"]["sit"] == "swivel"
    assert client.put("/api/seating/tables", json={"tcp_1": "lounge_red"}).json()["tables"] == {"tcp_1": "lounge_red"}
    assert client.put("/api/seating/tables", json={"tcp_1": "nope"}).status_code == 400
    assert client.delete("/api/seating/styles/default").status_code == 400
    assert client.delete("/api/seating/styles/lounge_red").json()["tables"] == {}   # its tables go back to the default
    assert client.put("/api/seating/styles/Bad Id", json={}).status_code == 400
