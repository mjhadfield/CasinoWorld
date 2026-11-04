"""The Stats archive (stats_archive.py): figures worked out from the store, saved once, listed and served."""
import json

from casino_server import stats_archive
from casino_server.store import Store

LOOK = {"body": "male", "skin": "light"}


def _visit(store, npc_id, games, wagered, returned, minutes=10, reason="done", arrived=1_760_000_000.0):
    budget = 50_000
    store.record_npc_visit(npc_id, {"arrived": arrived, "left_at": arrived + minutes * 60, "budget": budget,
                                    "end_bankroll": budget - wagered + returned, "wagered": wagered, "returned": returned,
                                    "rounds": sum(games.values()), "games": games, "reason": reason}, None)


def _store(tmp_path):
    store = Store(tmp_path / "casino.sqlite")
    rita = store.create_npc({"name": "Rita", "role": "punter", "look": LOOK, "archetype": "grinder", "traits": ["whale"]})
    dev = store.create_npc({"name": "Dev", "role": "punter", "look": LOOK, "archetype": "casual", "traits": []})
    _visit(store, rita, {"craps": 20}, 10_000, 9_000, minutes=30)
    _visit(store, rita, {"craps": 5, "roulette": 5}, 4_000, 4_400, minutes=20)   # two games: in the totals only
    _visit(store, dev, {"roulette": 10}, 2_000, 1_000, reason="bust")
    _visit(store, dev, {}, 0, 0, minutes=1)                                     # a walk-in
    p = store.create_player("Mike", hand=10_000)
    store.adjust(p.id, -1_000, "bet", "blackjack", "upfront")
    store.adjust(p.id, 2_500, "payout", "blackjack", "blackjack")
    store.adjust(p.id, -500, "bet", "craps", "bets")
    store.adjust(p.id, 200, "bet", "craps", "bets")   # a stake taken back
    return store, (rita, dev), p


def test_the_figures(tmp_path):
    store, (rita, dev), mike = _store(tmp_path)
    a = stats_archive.build(store, "Before the wipe")
    npc = a["summary"]["npc"]
    assert (npc["visits"], npc["rounds"], npc["wagered"], npc["returned"], npc["house"]) == (4, 40, 16_000, 14_400, 1_600)
    assert npc["in_profit"] == 0 and npc["punters"] == 2
    games = {g["game"]: g for g in a["npc_games"]}
    assert games["craps"]["rounds"] == 25 and games["craps"]["single_visits"] == 1 and games["craps"]["house"] == 1_000
    assert games["roulette"]["house"] == 1_000 and games["roulette"]["hold"] == 50.0
    assert a["npc_games_coverage"] == 75.0   # 12,000 of 16,000 staked in one-game visits
    assert a["games_per_visit"] == {"0": 1, "1": 2, "2": 1}
    assert a["visit_length"]["played"]["visits"] == 3 and a["visit_length"]["median_minutes"] == 20.0
    assert {r["key"]: r["visits"] for r in a["reasons"]} == {"done": 3, "bust": 1}
    assert {r["key"] for r in a["traits"]} == {"whale", "(none)"}
    human = a["summary"]["human"]
    assert (human["bets"], human["wagered"], human["returned"], human["house"]) == (2, 1_300, 2_500, -1_200)
    assert [p["name"] for p in a["human_players"]] == ["Mike"]
    assert a["best_npcs"][0] == rita and a["worst_npcs"][0] == dev   # Rita's -600 is the better of two losses
    assert a["biggest_payouts"][0]["amount"] == 2_500


def test_saved_once_listed_and_loaded(tmp_path):
    store, *_ = _store(tmp_path)
    a = stats_archive.build(store, "Before the wipe!")
    first = stats_archive.save(tmp_path, a)
    second = stats_archive.save(tmp_path, a)
    assert first.endswith("-before-the-wipe") and second == first + "-2"   # never overwritten
    assert {x["id"] for x in stats_archive.listing(tmp_path)} == {first, second}
    assert stats_archive.load(tmp_path, first)["summary"] == json.loads(json.dumps(a["summary"]))
    assert stats_archive.load(tmp_path, "../casino") is None and stats_archive.load(tmp_path, "nope") is None


def test_the_admin_api(client):
    resort = client.app.state.resort
    aid = stats_archive.save(resort.data_dir, stats_archive.build(resort.store, "Test"))
    assert [a["id"] for a in client.get("/api/stats/archives").json()["archives"]] == [aid]
    assert client.get(f"/api/stats/archives/{aid}").json()["title"] == "Test"
    assert client.get("/api/stats/archives/nope").status_code == 404
