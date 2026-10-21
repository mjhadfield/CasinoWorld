"""Table styles: House is every card table's default, saving designs, giving tables their own, and Roulette/Craps left out."""
import copy

from conftest import recv_until  # noqa: F401  (the client fixture lives in conftest)

from casino_server import table_styles


def test_every_card_table_starts_on_house(client):
    data = client.get("/api/table-styles").json()
    assert data["default"] == "house" and data["tables"] == {}
    assert data["styles"]["house"]["design"] == table_styles.HOUSE and not data["styles"]["house"]["builtin"]
    assert {"grand", "monte", "deco", "vegas"} <= {k for k, s in data["styles"].items() if s["builtin"]}
    assert "rou_1" not in data["games"] and "crp_1" not in data["games"]
    assert data["games"]["tcp_1"]["layout"] == "tcp" and data["games"]["pgu_1"]["layout"] == "pgu"
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "token": ""})
        assert recv_until(ws, "welcome")["table_styles"]["styles"]["house"]["design"]["rail"]["armrest"] == "all"


def test_every_built_in_and_house_is_a_valid_design():
    for style in [*table_styles.BUILT_IN.values(), {"design": table_styles.HOUSE}]:
        assert table_styles.clean_design(style["design"]) == style["design"]


def test_editing_house_reaches_the_floor(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "token": ""})
        recv_until(ws, "welcome")
        design = copy.deepcopy(table_styles.HOUSE)
        design["felt"]["colour"] = "#0F5B3F"
        design["chips"] = "vintage"
        r = client.put("/api/table-styles/styles/house", json={"name": "House", "design": design})
        assert r.status_code == 200, r.text
        house = recv_until(ws, "table_styles")["table_styles"]["styles"]["house"]["design"]
        assert house["felt"]["colour"] == "#0f5b3f" and house["chips"] == "vintage"
        assert house["rail"]["wood"] == "mahogany"   # (what wasn't changed stays)
    for bad in ({"border": "neon"}, {"felt": {"colour": "red"}}, {"felt": {"vignette": 2}}, {"print": {"font": "comic"}}):
        assert client.put("/api/table-styles/styles/house", json={"name": "House", "design": bad}).status_code == 400
    assert client.put("/api/table-styles/styles/house", json={"name": ""}).status_code == 400


def test_a_design_missing_newer_choices_takes_them_from_house():
    old = {"felt": {"colour": "#14284a"}, "border": "deco"}   # (saved before most of the choices existed)
    design = table_styles.clean_design(old)
    assert design["felt"]["colour"] == "#14284a" and design["border"] == "deco" and design["chips"] == table_styles.HOUSE["chips"]


def test_new_styles_go_on_some_tables_and_the_built_ins_stay(client):
    r = client.put("/api/table-styles/styles/pit_blue", json={"name": "Pit blue", "design": table_styles.BUILT_IN["vegas"]["design"]})
    assert r.status_code == 200, r.text
    r = client.put("/api/table-styles/tables", json={"tables": {"bj_2": "pit_blue", "bj_3": "monte"}})
    assert r.json()["tables"] == {"bj_2": "pit_blue", "bj_3": "monte"}
    assert client.put("/api/table-styles/tables", json={"tables": {"rou_1": "pit_blue"}}).status_code == 400
    assert client.put("/api/table-styles/tables", json={"tables": {"bj_2": "nope"}}).status_code == 400
    assert client.put("/api/table-styles/tables", json={"default": "pit_blue"}).json()["default"] == "pit_blue"
    assert client.put("/api/table-styles/styles/vegas", json={"name": "Mine"}).status_code == 400
    assert client.delete("/api/table-styles/styles/vegas").status_code == 400
    assert client.delete("/api/table-styles/styles/house").status_code == 400
    after = client.delete("/api/table-styles/styles/pit_blue").json()
    assert after["tables"] == {"bj_3": "monte"} and after["default"] == "house"   # its tables and the default go back to House
    assert client.put("/api/table-styles/tables", json={"tables": {"bj_3": None}}).json()["tables"] == {}
    assert client.put("/api/table-styles/styles/Bad Id", json={"name": "x"}).status_code == 400
