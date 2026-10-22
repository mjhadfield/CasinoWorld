"""The admin page's Slots tab: meters, cabinets, jackpot settings and per-machine figures, and the slot art the game loads."""


def test_overview_lists_meters_and_cabinets(client):
    r = client.get("/api/slots").json()
    assert [t["id"] for t in r["tiers"]] == ["mini", "minor", "major", "grand"]
    assert len(r["cabinets"]) == 10 and all(c["variant"] == "armadillo" for c in r["cabinets"])


def test_reset_meter(client):
    assert client.post("/api/slots/reset-meter/grand").json()["amount"] == 500_000
    assert client.post("/api/slots/reset-meter/huge").status_code == 400


def test_art_manifest_serves_the_saved_picks(client):
    assert client.get("/api/slots/art/manifest").json()["variants"]["armadillo"] == {}
    client.app.state.slot_art.picks["armadillo"] = {"H1": "flux2/H1.png"}
    url = client.get("/api/slots/art/manifest").json()["variants"]["armadillo"]["H1"]
    assert url.startswith("/slot-art/armadillo/flux2/H1.png?v=")
    img = client.get(url)
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert client.get("/slot-art/armadillo/../../casino.sqlite").status_code == 404
    assert client.put("/api/slots/art/armadillo/H1", json={"source": "flux2/H1.png"}).status_code in (404, 405)


def test_jackpot_settings_change_the_rate_and_grow_by_the_second(client):
    r = client.put("/api/slots/jackpot-settings", json={"mini": {"rate": 0.005, "per_second": 2.5}})
    assert r.status_code == 200 and r.json()["settings"]["mini"] == {"rate": 0.005, "per_second": 2.5}
    tier = next(t for t in client.get("/api/slots").json()["tiers"] if t["id"] == "mini")
    assert tier["rate"] == 0.005 and tier["per_second"] == 2.5
    assert client.put("/api/slots/jackpot-settings", json={"mini": {"rate": 0.5}}).status_code == 400
    assert client.put("/api/slots/jackpot-settings", json={"grand": {"per_second": -1}}).status_code == 400


def test_overview_lists_each_machine_with_its_figures(client):
    casino = client.app.state.casino
    casino.slot_stats.record("armadillo", True, spins=3, staked=300, returned=120, bonuses=1)
    casino.slot_stats.record("armadillo", False, spins=1, staked=100, returned=0)
    [m] = client.get("/api/slots").json()["machines"]
    assert m["variant"] == "armadillo" and m["cabinets"] == 10
    assert (m["spins"], m["staked"], m["returned"], m["bonuses"]) == (4, 400, 120, 1)
    assert m["human"]["spins"] == 3 and m["npc"]["staked"] == 100
