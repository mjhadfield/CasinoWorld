"""The slot banks (slot_banks.py): cabinets of any slot, placed anywhere clear on the floor, on the table list
when the server starts."""
import dataclasses
import json
import re
from pathlib import Path

import pytest

from casino_server import floor, slot_banks, sounds
from casino_server.slots.variants import VARIANTS
from tests.conftest import ARMADILLO_BANK

SCENE = Path(__file__).resolve().parents[2] / "client" / "scenes" / "world" / "casino_floor.tscn"


def _bank(x, y, *cabs, name="New", bid=None):
    b = {"name": name, "x": x, "y": y, "cabinets": [{"dx": dx, "dy": dy, "facing": f, "variant": v} for dx, dy, f, v in cabs]}
    return {**b, "id": bid} if bid else b


@pytest.fixture
def twin(monkeypatch):
    """A second slot to mix in: Armadillo's maths under another name."""
    monkeypatch.setitem(VARIANTS, "twin", dataclasses.replace(VARIANTS["armadillo"], id="twin", name="Twin"))


@pytest.fixture
def board(tmp_path):
    return slot_banks.SlotBankBoard(tmp_path, tmp_path / "slot_builds")


def test_the_floor_map_matches_the_scene():
    """floor_map.json (tools/floor_map.gd) has every table, where the scene puts it."""
    text = SCENE.read_text()
    placed = {m[1]: (float(m[0].split(",")[0]), float(m[0].split(",")[1]))
              for m in re.findall(r"position = Vector2\(([^)]*)\)\ntable_id = \"(\w+)\"", text)}
    tables = {t["id"]: (t["x"], t["y"]) for t in slot_banks.FLOOR_MAP["tables"]}
    assert set(tables) == {t for t, cfg in floor.TABLES.items() if cfg["game"] != "slots"}
    assert all(placed.get(t, xy) == xy for t, xy in tables.items())
    assert set(slot_banks.FLOOR_MAP["points"]) == set(floor.ALL_POINTS)


def test_the_armadillo_bank_is_on_the_floor_and_clear():
    assert [t for t, cfg in floor.TABLES.items() if cfg["game"] == "slots"] == [f"slot_{i}" for i in range(1, 11)]
    assert slot_banks.check([ARMADILLO_BANK]) == []
    cab = slot_banks.cabinets()
    assert (cab[0]["x"], cab[0]["y"], cab[0]["facing"], cab[0]["cabinet"]) == (1599, 947, "up", {})
    assert sounds.TABLE_SETS["slot_9"] == "slots.armadillo"


def test_a_mixed_bank_gets_ids_once_and_keeps_them(board, twin, tmp_path):
    mixed = _bank(1650, 860, (-17, 0, "down", "armadillo"), (17, 0, "down", "twin"))
    view = board.save({"banks": [ARMADILLO_BANK, mixed]})
    new = view["banks"][1]
    assert new["id"] == "b1" and new["name"] == "New" and [c["id"] for c in new["cabinets"]] == ["b1_1", "b1_2"]
    assert view["pending"] == 2
    # moved, turned round and re-slotted, a cabinet keeps its id; a new one gets the next
    new["x"], new["cabinets"][0]["variant"] = 1600, "twin"
    new["cabinets"].append({"dx": 51, "dy": 0, "facing": "down", "variant": "armadillo"})
    view = board.save({"banks": view["banks"]})
    assert [c["id"] for c in view["banks"][1]["cabinets"]] == ["b1_1", "b1_2", "b1_3"]
    # a removed cabinet's id isn't given again
    view["banks"][1]["cabinets"].pop()
    view["banks"][1]["cabinets"].append({"dx": 51, "dy": 0, "facing": "down", "variant": "armadillo"})
    assert board.save({"banks": view["banks"]})["banks"][1]["cabinets"][-1]["id"] == "b1_4"
    # restarting puts them on the floor, each its own slot with its own sounds
    slot_banks.install(tmp_path)
    assert floor.TABLES["b1_1"]["variant"] == "twin" and sounds.TABLE_SETS["b1_1"] == "slots.twin"
    assert sounds.TABLE_SETS["b1_4"] == "slots.armadillo" and board.view()["pending"] == 0


@pytest.mark.parametrize("where, said", [
    ((1560, 640), "in Craps's way"),                   # on the craps table
    ((1650, 1150), "off the floor"),                   # through the bottom wall
    ((700, 1104), "stands on the entrance"),
    ((1660, 955), "overlaps another cabinet ("),     # in among Armadillo's
])
def test_a_bank_must_stand_clear(board, where, said):
    with pytest.raises(slot_banks.BankError, match=re.escape(said)):
        board.save({"banks": [ARMADILLO_BANK, _bank(*where, (0, 0, "down", "armadillo"))]})


def test_cabinets_in_a_bank_must_not_block_each_other(board):
    with pytest.raises(slot_banks.BankError, match="overlaps another cabinet"):
        board.save({"banks": [_bank(1650, 860, (0, 0, "down", "armadillo"), (20, 0, "down", "armadillo"))]})
    with pytest.raises(slot_banks.BankError, match="can't be reached"):   # one in front of another's screen
        board.save({"banks": [_bank(1650, 860, (0, 0, "down", "armadillo"), (0, 48, "up", "armadillo"))]})


@pytest.mark.parametrize("bank, said", [
    (_bank(1650, 860, (0, 0, "sideways", "armadillo")), "can face"),
    (_bank(1650, 860, (0, 0, "down", "nope")), "no slot 'nope'"),
    ({**_bank(1650, 860, (0, 0, "down", "armadillo")), "id": "b9"}, "no bank 'b9'"),
    ({"name": "x", "cabinets": []}, "place on the floor"),
])
def test_what_the_page_sends_is_checked(board, bank, said):
    with pytest.raises(slot_banks.BankError, match=re.escape(said)):
        board.save({"banks": [bank]})
    stolen = {**ARMADILLO_BANK, "cabinets": ARMADILLO_BANK["cabinets"][:1]}
    other = _bank(1650, 860, (0, 0, "down", "armadillo"))
    other["cabinets"][0]["id"] = "slot_1"   # a cabinet can't move to another bank by its id
    with pytest.raises(slot_banks.BankError, match="no cabinet 'slot_1' in New"):
        board.save({"banks": [stolen, other]})


def test_install_skips_cabinets_it_cant_put_on_the_floor(tmp_path):
    banks = [_bank(1650, 860, (0, 0, "down", "gone"), bid="b1"), _bank(1650, 760, (0, 0, "down", "armadillo"), bid="b2")]
    banks[0]["cabinets"][0]["id"], banks[1]["cabinets"][0]["id"] = "b1_1", "tcp_1"
    slot_banks.path(tmp_path).write_text(json.dumps({"serial": 2, "banks": banks}))
    assert slot_banks.install(tmp_path) == []
    assert slot_banks.LOADED["skipped"] == ["b1_1", "tcp_1"] and floor.TABLES["tcp_1"]["game"] == "three_card_poker"
    assert slot_banks.cabinets() == []
    slot_banks.install(tmp_path / "none")   # no file: no slots
    assert not any(cfg["game"] == "slots" for cfg in floor.TABLES.values())


def test_the_floor_tab_api(client):
    view = client.get("/api/slot-banks").json()
    assert [b["id"] for b in view["banks"]] == ["slot"] and view["pending"] == 0 and view["problems"] == []
    assert view["slots"] == [{"id": "armadillo", "name": "Armadillo Goes West", "loaded": True, "cabinet": {},
                              "logo": "/slot-art/armadillo/vector/logo.png"}]
    assert view["rules"]["floor"]["room"] == [1900, 1160] and not view["live"]
    r = client.put("/api/slot-banks", json={"banks": [_bank(1560, 640, (0, 0, "down", "armadillo"))]})
    assert r.status_code == 400 and "Craps" in r.json()["detail"]
    r = client.put("/api/slot-banks", json={"banks": []})
    assert r.status_code == 200 and r.json()["pending"] == 10
    assert client.post("/api/slot-banks/apply").status_code == 400   # a test instance: restart it by hand
    assert client.get("/slot-banks-ui/banks.js").status_code == 200
