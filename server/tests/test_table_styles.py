"""Table styles: House is every table's default, saving designs, giving tables their own, and the card tables,
Roulette and Craps each keeping their own styles."""
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
        welcome = recv_until(ws, "welcome")["table_styles"]
        assert welcome["cards"]["styles"]["house"]["design"]["rail"]["armrest"] == "all"
        assert welcome["roulette"]["styles"]["house"]["design"] == table_styles.ROULETTE_HOUSE
        assert welcome["craps"]["styles"]["house"]["design"] == table_styles.CRAPS_HOUSE


def test_every_built_in_and_house_is_a_valid_design():
    for kind, k in table_styles.KINDS.items():
        for style in [*k["built_in"].values(), {"design": k["house"]}]:
            assert table_styles.clean_design(style["design"], kind) == style["design"]


def test_editing_house_reaches_the_floor(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "token": ""})
        recv_until(ws, "welcome")
        design = copy.deepcopy(table_styles.HOUSE)
        design["felt"]["colour"] = "#0F5B3F"
        design["chips"] = "vintage"
        r = client.put("/api/table-styles/styles/house", json={"name": "House", "design": design})
        assert r.status_code == 200, r.text
        house = recv_until(ws, "table_styles")["table_styles"]["cards"]["styles"]["house"]["design"]
        assert house["felt"]["colour"] == "#0f5b3f" and house["chips"] == "vintage"
        assert house["rail"] == table_styles.HOUSE["rail"]   # (what wasn't changed stays)
    for bad in ({"border": "neon"}, {"felt": {"colour": "red"}}, {"felt": {"vignette": 2}}, {"print": {"font": "comic"}}):
        assert client.put("/api/table-styles/styles/house", json={"name": "House", "design": bad}).status_code == 400
    assert client.put("/api/table-styles/styles/house", json={"name": ""}).status_code == 400


def test_a_design_missing_newer_choices_takes_them_from_house():
    old = {"felt": {"colour": "#14284a"}, "border": "deco"}   # (saved before most of the choices existed)
    design = table_styles.clean_design(old)
    assert design["felt"]["colour"] == "#14284a" and design["border"] == "deco" and design["chips"] == table_styles.HOUSE["chips"]


def test_a_design_saved_before_the_bet_colours_keeps_its_look():
    old = {"print": {"font": "montserrat", "ink": "#f4f4f2", "accent": "#c8794a"}}   # (one colour for side bets and trim)
    pr = table_styles.clean_design(old)["print"]
    assert pr == {"font": "montserrat", "ink": "#f4f4f2", "primary": "#f4f4f2", "side": "#c8794a", "accent": "#c8794a"}
    assert table_styles.BUILT_IN["vegas"]["design"]["print"]["side"] == "#8fd3ff"


def test_a_card_back_saved_before_its_colour_keeps_its_look():
    assert table_styles.clean_design({"back": "sunburst"})["backColour"] == "#4d1616"
    green = table_styles.clean_design({"back": "emerald"})
    assert green["back"] == "lattice" and green["backColour"] == "#145238"
    assert table_styles.BUILT_IN["grand"]["design"]["backColour"] == "#34373c"
    fresh = table_styles.clean_design({"back": "stripe", "backColour": "#0E2A5C", "cardColour": "#efe4c8", "front": "jumbo", "suits": "four"})
    assert (fresh["backColour"], fresh["cardColour"], fresh["front"], fresh["suits"]) == ("#0e2a5c", "#efe4c8", "jumbo", "four")
    for bad in ({"front": "comic"}, {"suits": "six"}, {"backColour": "blue"}):
        try:
            table_styles.clean_design(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


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


def test_roulette_and_craps_have_their_own_styles_and_placement(client):
    rou = client.get("/api/table-styles?kind=roulette").json()
    assert rou["kind"] == "roulette" and list(rou["games"]) == ["rou_1"] and rou["games"]["rou_1"]["layout"] == "rou"
    assert rou["styles"]["house"]["design"] == table_styles.ROULETTE_HOUSE
    assert {"grand", "monte", "deco", "vegas", "cards"} <= {k for k, s in rou["styles"].items() if s["builtin"]}
    assert list(client.get("/api/table-styles?kind=craps").json()["games"]) == ["crp_1"]
    assert client.get("/api/table-styles?kind=slots").status_code == 404
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "token": ""})
        recv_until(ws, "welcome")
        design = copy.deepcopy(table_styles.ROULETTE_HOUSE)
        design["numbers"]["red"] = "#C8283A"
        design["wheel"]["metal"] = "chrome"
        r = client.put("/api/table-styles/styles/green_room?kind=roulette", json={"name": "Green room", "design": design})
        assert r.status_code == 200, r.text
        assert r.json()["styles"]["green_room"]["design"]["numbers"]["red"] == "#c8283a"
        recv_until(ws, "table_styles")
        assert client.put("/api/table-styles/tables?kind=roulette", json={"tables": {"rou_1": "green_room"}}).status_code == 200
        sent = recv_until(ws, "table_styles")["table_styles"]
        assert sent["roulette"]["tables"] == {"rou_1": "green_room"} and sent["cards"]["tables"] == {}
    # Each kind's own parts: a craps design has dice, a roulette one doesn't take a card table's choices.
    assert client.put("/api/table-styles/styles/x?kind=craps", json={"name": "X", "design": {"dice": "plaid"}}).status_code == 400
    assert client.put("/api/table-styles/styles/x?kind=craps", json={"name": "X", "design": {"rail": {"armrest": "player"}}}).status_code == 400
    assert client.put("/api/table-styles/tables?kind=roulette", json={"tables": {"crp_1": "house"}}).status_code == 400
    assert client.put("/api/table-styles/tables?kind=craps", json={"tables": {"crp_1": "green_room"}}).status_code == 400   # (Roulette's)
    assert client.put("/api/table-styles/tables", json={"tables": {"rou_1": "house"}}).status_code == 400
    assert "green_room" not in client.get("/api/table-styles").json()["styles"]
    assert client.delete("/api/table-styles/styles/green_room?kind=roulette").json()["tables"] == {}
