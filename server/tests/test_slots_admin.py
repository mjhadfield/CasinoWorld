"""The admin page's Slots tab: meters, cabinets, and swapping slot art."""
import io

from PIL import Image


def test_overview_lists_meters_and_cabinets(client):
    r = client.get("/api/slots").json()
    assert [t["id"] for t in r["tiers"]] == ["mini", "minor", "major", "grand"]
    assert len(r["cabinets"]) == 10 and all(c["variant"] == "armadillo" for c in r["cabinets"])


def test_reset_meter(client):
    assert client.post("/api/slots/reset-meter/grand").json()["amount"] == 500_000
    assert client.post("/api/slots/reset-meter/huge").status_code == 400


def test_art_defaults_to_vector_and_can_be_swapped(client):
    over = client.get("/api/slots/art").json()["variants"][0]
    h1 = next(a for a in over["assets"] if a["asset"] == "H1")
    assert h1["choice"] == "vector/H1.png" and "flux2/H1.png" in h1["candidates"]
    assert client.get("/api/slots/art/manifest").json()["variants"]["armadillo"] == {}
    assert client.put("/api/slots/art/armadillo/H1", json={"source": "flux2/H1.png"}).json()["choice"] == "flux2/H1.png"
    url = client.get("/api/slots/art/manifest").json()["variants"]["armadillo"]["H1"]
    assert url.startswith("/slot-art/armadillo/flux2/H1.png?v=")
    img = client.get(url)
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    client.delete("/api/slots/art/armadillo/H1")
    assert client.get("/api/slots/art/manifest").json()["variants"]["armadillo"] == {}


def test_uploads_are_fitted_and_choosable(client):
    buf = io.BytesIO()
    Image.new("RGB", (800, 400), (200, 30, 30)).save(buf, "PNG")
    src = client.put("/api/slot-art-uploads/armadillo/my hat.png", content=buf.getvalue()).json()["source"]
    assert src == "uploads/my-hat.png"
    assert client.put("/api/slots/art/armadillo/M1", json={"source": src}).status_code == 200
    got = Image.open(io.BytesIO(client.get(f"/slot-art/armadillo/{src}").content))
    assert got.size == (512, 512)
    assert client.put("/api/slot-art-uploads/armadillo/x.png", content=b"not an image").status_code == 400
    assert client.get("/slot-art/armadillo/../../casino.sqlite").status_code == 404
    client.delete("/api/slot-art-uploads/armadillo/my-hat.png")
    assert client.get("/api/slots/art").json()["variants"][0]["uploads"] == []


def test_jackpot_settings_change_the_rate_and_grow_by_the_second(client):
    r = client.put("/api/slots/jackpot-settings", json={"mini": {"rate": 0.005, "per_second": 2.5}})
    assert r.status_code == 200 and r.json()["settings"]["mini"] == {"rate": 0.005, "per_second": 2.5}
    tier = next(t for t in client.get("/api/slots").json()["tiers"] if t["id"] == "mini")
    assert tier["rate"] == 0.005 and tier["per_second"] == 2.5
    assert client.put("/api/slots/jackpot-settings", json={"mini": {"rate": 0.5}}).status_code == 400
    assert client.put("/api/slots/jackpot-settings", json={"grand": {"per_second": -1}}).status_code == 400
