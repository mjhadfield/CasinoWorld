"""NPCs from the roster, simulated with a fake clock: no sockets, no sleeping."""
import random

import pytest

from casino_server import roster
from casino_server.casino import Casino
from casino_server.npc import reserved_seats
from casino_server.store import Store

from conftest import classic_floor


def simulate(tmp_path, seconds, population=6, seed=3, settings=None, until=None, punters=None):
    """A casino with NPCs on a fake clock (real time and wall time both fake). Returns
    (casino, stats). `until(casino)` can stop it early."""
    now = [1_000_000.0]
    store = Store(tmp_path / "npc.sqlite")
    if settings:
        store.set_json("npc_settings", settings)
    if punters:   # change every punter (after the roster's seeded)
        from casino_server import roster as _roster
        _roster.seed(store)
        for rec in store.npcs("punter"):
            store.update_npc(rec["id"], punters)
    casino = Casino(store, classic_floor(), npc_population=population, rng=random.Random(seed), clock=lambda: now[0],
                    wall=lambda: now[0])
    stats = {"reserve_taken": 0, "seated_ever": set(), "despawned": 0, "rounds": 0, "dealer_changes": 0}
    original_remove = casino.world.remove

    def remove(entity_id):
        stats["despawned"] += entity_id.startswith("n")
        original_remove(entity_id)
    casino.world.remove = remove

    start = now[0]
    while now[0] < start + seconds:
        now[0] += 0.25
        casino.npcs.tick(now[0])
        for runner in casino.tables.values():
            events = runner.machine.tick(now[0])
            runner.publish(events)
            stats["rounds"] += sum(e["kind"] == "round_end" for e in events)
            seats = runner.machine.seats
            seated = [s.participant for s in seats if s.participant]
            if len(seats) > 1:   # (slot cabinets keep their free seats across the bank)
                reserved = reserved_seats(runner.machine.game, len(seats))
                stats["reserve_taken"] += sum(1 for i in reserved if seats[i].participant)
            stats["seated_ever"].update(p.entity_id for p in seated)
        if until and until(casino):
            break
    return casino, stats


def test_npcs_populate_play_respect_reserved_seats_and_leave(tmp_path):
    casino, stats = simulate(tmp_path, seconds=1800, settings={"cooldown_min": [1, 2], "bust_cooldown_min": [2, 3]})
    assert len([n for n in casino.npcs.npcs.values() if not n.ended]) <= 6
    assert stats["reserve_taken"] == 0     # nobody sat in a seat kept for real players
    assert len(stats["seated_ever"]) >= 3  # plenty of NPCs sat down
    assert stats["rounds"] >= 20           # and actually played hands
    assert stats["despawned"] >= 1         # some finished up and left
    for npc in casino.npcs.npcs.values():
        assert npc.bankroll >= 0


def test_reserved_seats_are_the_middle_ones_and_the_second_from_the_left_at_craps():
    assert reserved_seats("let_it_ride", 5) == {2}
    assert reserved_seats("blackjack", 6) == {2, 3}
    assert reserved_seats("craps", 8) == {2, 6}   # seat 0 is the right-hand end of the rail


def test_visits_are_logged_and_reconcile_with_lifetime_figures(tmp_path):
    casino, _ = simulate(tmp_path, seconds=2400, settings={"cooldown_min": [1, 2], "bust_cooldown_min": [2, 3]})
    casino.npcs.close_all("shutdown")
    store = casino.store
    logged = 0
    for rec in store.npcs("punter"):
        visits = store.npc_visits(rec["id"], limit=1000)
        logged += len(visits)
        assert rec["visits"] == len(visits)
        assert rec["net"] == sum(v["net"] for v in visits)
        assert rec["wagered"] == sum(v["wagered"] for v in visits)
        for v in visits:   # nobody loses more than they brought, and the books balance
            assert v["end_bankroll"] >= 0
            assert v["end_bankroll"] == v["budget"] - v["wagered"] + v["returned"]
    assert logged >= 4


def test_a_bust_npc_cools_down_and_the_roster_cycles(tmp_path):
    casino, _ = simulate(tmp_path, seconds=3600, population=4,
                         settings={"cooldown_min": [5, 10], "bust_cooldown_min": [60, 90]},
                         punters={"archetype": "gambler", "traits": [], "settings": {"budget_min": 500, "budget_max": 1_000}})
    store = casino.store
    busts = [v for r in store.npcs("punter") for v in store.npc_visits(r["id"], 100) if v["reason"] == "bust"]
    for r in store.npcs("punter"):
        last = store.npc_visits(r["id"], 1)
        if last and last[0]["reason"] == "bust":   # a long cooldown after going bust
            assert r["cooldown_until"] - last[0]["left_at"] >= 60 * 60 * 0.99 * (0.3 if "regular" in r["traits"] else 1)
    distinct = sum(1 for r in store.npcs("punter") if r["visits"])
    assert distinct >= 6   # more NPCs came through than fit on the floor at once
    assert busts, "nobody went bust in an hour of Gamblers with £5-£10 each"


def test_hit_and_run_leaves_once_up(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    casino = Casino(store, classic_floor(), npc_population=0, rng=random.Random(1), clock=lambda: 0.0, wall=lambda: 0.0)
    rec = store.npcs("punter")[0]
    store.update_npc(rec["id"], {"traits": ["hit_and_run"], "settings": {"hit_and_run_pct": 50}})
    npc = casino.npcs.spawn(store.npc(rec["id"]), 0.0)
    npc.bankroll = npc.prof.budget + npc.prof.budget // 2
    assert casino.npcs._time_to_go(npc) == "hit_and_run"
    npc.bankroll = npc.prof.budget
    npc.rounds = 0
    assert casino.npcs._time_to_go(npc) is None


def test_a_chaser_raises_after_losses_and_resets_when_even(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    casino = Casino(store, classic_floor(), npc_population=0, rng=random.Random(1), clock=lambda: 0.0, wall=lambda: 0.0)
    rec = store.npcs("punter")[0]
    store.update_npc(rec["id"], {"archetype": "casual", "traits": ["chaser"]})
    d = casino.npcs
    npc = d.spawn(store.npc(rec["id"]), 0.0)
    base = d._unit(npc)
    for _ in range(3):   # three losing rounds
        npc.in_round, npc.round_start = True, npc.bankroll
        npc.bankroll -= base
        d._round_over(npc, "three_card_poker")
    assert npc.chase > 2 and d._unit(npc) > base
    npc.in_round, npc.round_start = True, npc.bankroll
    npc.bankroll = npc.prof.budget + 100
    d._round_over(npc, "three_card_poker")
    assert npc.chase == 1.0


def test_sessions_follow_the_archetype():
    rng = random.Random(5)
    grind = [roster.profile({"archetype": "grinder", "traits": []}, rng).rounds for _ in range(200)]
    gamble = [roster.profile({"archetype": "gambler", "traits": []}, rng).rounds for _ in range(200)]
    whale = roster.profile({"archetype": "casual", "traits": ["whale"]}, rng)
    casual = roster.profile({"archetype": "casual", "traits": []}, rng)
    assert min(grind) > max(gamble)
    assert whale.budget > casual.budget
    assert roster.profile({"archetype": "grinder", "traits": []}, rng).mistakes == 0


def test_a_card_counter_bets_up_on_a_good_count(tmp_path):
    from types import SimpleNamespace
    from casino_server.engines.cards import Card
    store = Store(tmp_path / "t.sqlite")
    casino = Casino(store, classic_floor(), npc_population=0, rng=random.Random(1), clock=lambda: 0.0, wall=lambda: 0.0)
    rec = store.npcs("punter")[0]
    store.update_npc(rec["id"], {"archetype": "grinder", "traits": ["card_counter"]})
    d = casino.npcs
    npc = d.spawn(store.npc(rec["id"]), 0.0)
    npc.prof.budget = npc.bankroll = 200_000
    neutral = SimpleNamespace(game="blackjack", shoe=SimpleNamespace(deck=SimpleNamespace(cards=[Card.from_code(c) for c in ["2h", "Ks"] * 52])))
    rich = SimpleNamespace(game="blackjack", shoe=SimpleNamespace(deck=SimpleNamespace(cards=[Card.from_code(c) for c in ["Ks"] * 60 + ["7h"] * 44])))
    assert d._true_count(neutral) == 0
    assert d._true_count(rich) >= 2   # the small cards are gone: tens and aces left
    assert d._unit(npc, rich) > d._unit(npc, neutral)


def test_regulars_come_back_sooner(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    t = [0.0]
    casino = Casino(store, classic_floor(), npc_population=0, rng=random.Random(1), clock=lambda: t[0], wall=lambda: t[0])
    store.set_json("npc_settings", {"cooldown_min": [60, 60], "regular_cooldown": 0.3})
    a, b = store.npcs("punter")[:2]
    store.update_npc(a["id"], {"traits": ["regular"]})
    store.update_npc(b["id"], {"traits": []})
    for rec in (a, b):
        npc = casino.npcs.spawn(store.npc(rec["id"]), 0.0)
        casino.npcs.end_visit(npc, "done")
    assert store.npc(a["id"])["cooldown_until"] == pytest.approx(60 * 60 * 0.3)
    assert store.npc(b["id"])["cooldown_until"] == pytest.approx(60 * 60)


def test_dealers_are_relieved_between_hands(tmp_path):
    casino, _ = simulate(tmp_path, seconds=700, population=2,
                         settings={"dealer_shift_min": 2, "dealer_stagger_min": 0.5})
    on = casino.dealers.on_duty
    staffed = [t for t, r in casino.tables.items() if getattr(r.machine, "DEALER", True)]   # (no dealers at slots)
    assert sorted(on) == sorted(staffed) and all(d["id"] for d in on.values())
    assert len({d["id"] for d in on.values()}) == len(on)   # nobody deals two tables

    # every table's relief is scheduled; and a relief only happens while the table's betting
    casino2, _ = simulate(tmp_path / "b", seconds=10, population=0, settings={"dealer_shift_min": 0.05, "dealer_stagger_min": 0})
    published = []
    for runner in casino2.tables.values():
        runner.publish = lambda events, r=runner: published.extend((r.machine.phase, e) for e in events)
    t = casino2.clock() + 60
    casino2.dealers.tick(t)
    changes = [(phase, e) for phase, e in published if e["kind"] == "dealer_change"]
    assert changes and all(phase == "betting" for phase, _ in changes)


def test_table_state_keeps_the_games_dealer(tmp_path):
    """Who's dealing rides alongside the game's own dealer state, never over it."""
    store = Store(tmp_path / "t.sqlite")
    t = [0.0]
    casino = Casino(store, classic_floor(), npc_population=0, rng=random.Random(1), clock=lambda: t[0], wall=lambda: t[0])
    casino.dealers.start(0.0)
    for table_id, runner in casino.tables.items():
        game = runner.machine.snapshot(None, 0.0)
        state = runner.snapshot_for(None)
        assert state.get("dealer") == game.get("dealer")
        if not getattr(runner.machine, "DEALER", True):
            assert state["on_duty"] is None    # a slot cabinet has no dealer
            continue
        assert state["on_duty"]["id"] == casino.dealers.on_duty[table_id]["id"]


def test_switching_npcs_off_sends_them_home_after_their_round_and_back_on_they_return_one_at_a_time(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    now = [1_000_000.0]
    casino = Casino(store, classic_floor(), npc_population=6, rng=random.Random(5), clock=lambda: now[0], wall=lambda: now[0])
    stands = []   # (table, phase, bets riding) whenever an NPC gets up after the switch
    for table_id, runner in casino.tables.items():
        m = runner.machine
        original = m.stand

        def stand(seat, now, reason="", m=m, original=original):
            if not casino.npcs.on:
                stands.append((m.game, m.phase, any(m.seats[seat].bets.values()) and m.game != "craps"))
            return original(seat, now, reason)
        m.stand = stand

    def run(seconds):
        end = now[0] + seconds
        while now[0] < end:
            now[0] += 0.25
            casino.npcs.tick(now[0])
            for runner in casino.tables.values():
                runner.publish(runner.machine.tick(now[0]))

    run(240)
    seated = [n for n in casino.npcs.npcs.values() if n.state == "seated"]
    assert seated, "nobody sat down in four minutes"
    store.set_json("npc_settings", {"npcs_on": False})
    run(600)
    assert not casino.npcs.npcs, "someone's still in the casino ten minutes after NPCs were switched off"
    assert stands
    for game, phase, riding in stands:   # they only got up between rounds, nothing left riding
        assert phase in ("betting", "idle") and not riding, (game, phase)
    left = [v for r in store.npcs("punter") for v in store.npc_visits(r["id"], 100) if v["reason"] == "npcs_off"]
    assert len(left) >= len(seated)
    assert all(r["cooldown_until"] is None for r in store.npcs("punter")
               if (store.npc_visits(r["id"], 1) or [{}])[0].get("reason") == "npcs_off")   # free to come straight back
    with pytest.raises(ValueError):
        casino.npcs.bring_in(store.npcs("punter")[0]["id"], now[0])

    arrivals = []
    original_spawn = casino.npcs.spawn
    casino.npcs.spawn = lambda record, t: arrivals.append(t) or original_spawn(record, t)
    store.set_json("npc_settings", {"npcs_on": True})
    run(60)
    assert len(arrivals) == 6
    assert all(b - a >= 1.5 for a, b in zip(arrivals, arrivals[1:]))   # one at a time



def test_npcs_in_a_snapshot_are_where_they_are_not_at_the_players_spawn_point(tmp_path):
    """A snapshot (joining, or back from a hidden tab) places each NPC where the server has them: the start of the
    walk they're on, or where they stopped -- never left for the client to put at the players' spawn point."""
    first = {}   # each NPC's place in the first snapshot they're in

    def check(casino):
        for e in casino.world.snapshot()["entities"]:
            if e["kind"] == "npc":
                assert e["x"] is not None and e["y"] is not None, e
                first.setdefault(e["id"], (e["x"], e["y"]))
        return False

    simulate(tmp_path, seconds=900, until=check)
    fl = classic_floor()
    arrivals = {fl.position(f"point:{k}") for k in fl.arrivals()}
    assert first and all(at in arrivals for at in first.values())   # each came in at an arrival point


def _player_on_floor(casino, name="Kicker"):
    from casino_server.session import Session
    session = Session()
    session.account = casino.store.create_account()
    session.player = casino.store.create_player(name)
    session.entity_id = "p-kicker"
    casino.sessions.add(session)
    return session


def _sent(session) -> list:
    out = []
    while not session.queue.empty():
        out.append(session.queue.get_nowait())
    return out


def _npc_seated_at_cards(casino, in_hand: bool):
    """(npc, table, seat) for an NPC sitting at a card table, in a hand (or between hands), else None."""
    for npc in casino.npcs.npcs.values():
        if npc.state == "seated" and not npc.kicked_by:
            m = casino.tables[npc.table].machine
            if m.game not in ("roulette", "craps", "slot") and len(m.seats) > 1 and \
                    (m.phase not in m.BETTING_PHASES) == in_hand and (not in_hand or npc.seat in m.round):
                return npc, npc.table, npc.seat
    return None


def _run(casino, now, seconds, until=None):
    end = now[0] + seconds
    while now[0] < end:
        now[0] += 0.25
        casino.npcs.tick(now[0])
        for runner in casino.tables.values():
            runner.publish(runner.machine.tick(now[0]))
        if until and until():
            return True
    return False


def _kick_casino(tmp_path, seed=7):
    now = [1_000_000.0]
    store = Store(tmp_path / "kick.sqlite")
    casino = Casino(store, classic_floor(), npc_population=6, rng=random.Random(seed), clock=lambda: now[0], wall=lambda: now[0])
    return casino, now


def test_a_kicked_npc_between_hands_gets_up_at_once_and_the_player_sits_down(tmp_path):
    casino, now = _kick_casino(tmp_path)
    assert _run(casino, now, 600, lambda: _npc_seated_at_cards(casino, in_hand=False))
    npc, table, seat = _npc_seated_at_cards(casino, in_hand=False)
    me = _player_on_floor(casino)
    casino.handle(me, {"type": "kick", "table": table, "seat": seat})
    assert (me.table, me.seat) == (table, seat) and me.kick is None
    assert any(m["type"] == "seated" and m["seat"] == seat for m in _sent(me))
    assert npc.table != table and npc.snubbed == table and npc.kicked_by is None
    _run(casino, now, 120)
    assert npc.table != table   # off to another table (or home), never back to this one


def test_a_kicked_npc_in_a_hand_finishes_it_then_the_seat_goes_to_the_player(tmp_path):
    casino, now = _kick_casino(tmp_path)
    assert _run(casino, now, 600, lambda: _npc_seated_at_cards(casino, in_hand=True))
    npc, table, seat = _npc_seated_at_cards(casino, in_hand=True)
    m = casino.tables[table].machine
    me, other = _player_on_floor(casino), _player_on_floor(casino, "Second")
    casino.handle(me, {"type": "kick", "table": table, "seat": seat})
    assert [x for x in _sent(me) if x["type"] == "kick_waiting"][0]["name"] == npc.name
    assert m.seats[seat].participant is npc.participant and me.table is None
    casino.handle(other, {"type": "kick", "table": table, "seat": seat})
    assert any(x["type"] == "error" and "already asked" in x["message"] for x in _sent(other))
    stood_in = []
    original = m.stand
    m.stand = lambda s, now, reason="": stood_in.append(m.phase) or original(s, now, reason)
    assert _run(casino, now, 120, lambda: me.table is not None)
    assert (me.table, me.seat) == (table, seat) and stood_in == ["betting"]   # up once the hand was settled


def test_walking_away_from_a_kick_leaves_the_npc_where_they_are(tmp_path):
    casino, now = _kick_casino(tmp_path)
    assert _run(casino, now, 600, lambda: _npc_seated_at_cards(casino, in_hand=True))
    npc, table, seat = _npc_seated_at_cards(casino, in_hand=True)
    me = _player_on_floor(casino)
    casino.handle(me, {"type": "kick", "table": table, "seat": seat})
    casino.handle(me, {"type": "kick_cancel"})
    m = casino.tables[table].machine
    _run(casino, now, 60, lambda: m.phase == "betting")
    _run(casino, now, 2)
    assert me.table is None and npc.kicked_by is None
    assert m.seats[seat].participant is npc.participant or npc.ended   # (unless their visit was over anyway)
