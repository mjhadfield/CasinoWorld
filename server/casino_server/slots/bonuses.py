"""
The bonus games. Each is a small state machine the cabinet steps through:

- The Trail Bonus (3+ Bonus scatters, or Buy Bonus): a pistol loads 1-6 bullets and the
  armadillo moves that many spaces along a 120-space trail, collecting what it lands on.
  A Snake ends it unless a Heart is held; the end pays the prizepot (2,000x, 4,000x doubled).
- Combo Free Spins (3+ free-spin scatters): three free games with a random feature every spin.
- The wave battle, Red Alert (any way in a design gives it): your ship fires on waves of enemy ships. A shot either
  destroys its ship, which reveals a prize or free spins (banked, played as Combo Free Games afterwards), or is
  answered (the ship cloaks and fires back: shields -1). Shields at 0 end it; clearing a wave pays its reward and
  restores them. After the last wave a boss takes `boss_hits` hits and pays a big prize.
- The island voyage, Dead Man's Map (any way in a design gives it): a map of `legs` columns of three islands, all
  in view. From each island you choose the next (the one level with it or either side); what it gives is drawn when
  you land. Treasure Island pays, a Shipwreck gives relics (and maybe a key or an artefact), Skull Island pays big
  or sinks you (the voyage ends short of the final island), Port Royal trades relics, and a Hidden Cove needs a key.
  The final island pays the treasure chest, a part for each artefact held, the legend for all of them, and any
  relics left. Free games bought at Port Royal are banked and played as Combo Free Games afterwards.
- The expedition, Delta Quadrant (any way in a design gives it): choose one of three routes, each a length and a
  hazard level shown up front, then explore one of three hidden planets in each sector: credits, a multiplier (on
  every later prize and the final one), tech (a Scanner shows the next sector, a Shuttle explores a second planet
  there, Shields absorb a hazard), a special (an artefact's big prize, a Wormhole straight to a boosted final prize,
  or free games, played as Combo Free Games afterwards), or a hazard, which ends it short of the final prize.

Ported from the mockup (slots_math.js makeBoard / trailRoll / freeGames / battleShot / voyageStep /
expeditionStep), draw for draw.
"""
import json
import math

from casino_server.slots.outcome import spin_outcome
from casino_server.slots.rng import randint, shuffle, weighted


# ------------------------------------------------------------------ the Trail Bonus
def make_board(v, rng) -> list:
    """A fresh board for each bonus: space 0 is the start and the last is the prizepot. The
    spaces between have exactly the recipe's items (plus maybe a Spin Upgrade and a Double),
    the rest coins; Snakes are swapped out of the first two spaces and out of a Lightning
    Roll's reach (6 spaces, or 12 if a Spin Upgrade comes earlier)."""
    t = v.trail
    inner = t["length"] - 2
    pool = []
    for kind, n in t["counts"].items():
        pool += [kind] * n
    if rng() < t["upgrade_chance"]:
        pool.append("upgrade")
    if rng() < t["double_chance"]:
        pool.append("double")
    pool += ["coin"] * (inner - len(pool))
    shuffle(rng, pool)

    def reach_of(i):
        return 12 if "upgrade" in pool[:i] else 6

    def unsafe(i):
        if pool[i] != "snake":
            return False
        if i < 2:
            return True
        return any(pool[j] == "lightning" and i - j <= reach_of(j) for j in range(max(0, i - 12), i))

    for _ in range(500):
        left = False
        for i in range(inner):
            if not unsafe(i):
                continue
            left = True
            j = 2 + randint(rng, inner - 2)
            if pool[j] == "coin":
                pool[i], pool[j] = pool[j], pool[i]
        if not left:
            break
    spaces = [{"type": "start"}]
    for kind in pool:
        spaces.append({"type": kind, "x": weighted(rng, t["coins"])} if kind == "coin" else {"type": kind})
    spaces.append({"type": "prizepot", "x": t["prizepot"]})
    return spaces


def trail_start(v, bet: int, rng, board=None) -> dict:
    return {"bet": bet, "board": board or make_board(v, rng), "pos": 0, "hearts": 0, "doubled": False,
            "upgraded": False, "lightning": False, "total": 0, "done": False, "rolls": 0}


def trail_roll(v, st: dict, rng, rig_bullets: int = 0) -> dict:
    """One pull of the trigger; `st` advances. Returns {bullets, move, from, path, events, done}.
    Events: coin/prizepot {pos, pence}, heart, heart_used, snake, double, upgrade, lightning,
    lightning_roll, crate {r, pence}, forward/back {n}."""
    t, b = v.trail, st["board"]
    end = len(b) - 1
    bullets = rig_bullets or 1 + randint(rng, 6)
    move = bullets * (2 if st["upgraded"] else 1)
    ev, path = [], []
    st["rolls"] += 1

    def pay(pos, pence, kind):
        st["total"] += pence
        ev.append({"kind": kind, "pos": pos, "pence": pence})

    def collect_coin(pos):
        sp = b[pos]
        if sp["type"] == "coin" and not sp.get("taken"):
            sp["taken"] = True
            pay(pos, sp["x"] * st["bet"], "coin")

    def finish():
        pay(end, b[end]["x"] * st["bet"], "prizepot")
        st["done"] = True

    def land(pos, depth):
        st["pos"] = pos
        sp = b[pos]
        if pos >= end:
            return finish()
        kind = sp["type"]
        if kind == "coin":
            collect_coin(pos)
        elif kind == "heart":
            if not sp.get("taken"):
                sp["taken"] = True
                st["hearts"] += 1
                ev.append({"kind": "heart", "pos": pos})
        elif kind == "snake":
            if st["hearts"] > 0:
                st["hearts"] -= 1
                ev.append({"kind": "heart_used", "pos": pos})
            else:
                ev.append({"kind": "snake", "pos": pos})
                st["done"] = True
        elif kind == "double":
            if not st["doubled"]:
                st["doubled"] = True
                for s in b:
                    if (s["type"] == "coin" and not s.get("taken")) or s["type"] == "prizepot":
                        s["x"] *= 2
                ev.append({"kind": "double", "pos": pos})
        elif kind == "upgrade":
            if not st["upgraded"]:
                st["upgraded"] = True
                ev.append({"kind": "upgrade", "pos": pos})
        elif kind == "lightning":
            st["lightning"] = True
            ev.append({"kind": "lightning", "pos": pos})
        elif kind == "crate":
            r = weighted(rng, t["crate_radius"])
            pence = 0
            for j in range(max(1, pos - r), min(end - 1, pos + r) + 1):
                s = b[j]
                if s["type"] == "coin" and not s.get("taken"):
                    s["taken"] = True
                    pence += s["x"] * st["bet"]
            st["total"] += pence
            ev.append({"kind": "crate", "pos": pos, "r": r, "pence": pence})
        elif kind in ("forward", "back") and depth <= 3:
            n = 1 + randint(rng, 6)
            ev.append({"kind": kind, "pos": pos, "n": n})
            to = min(end, pos + n) if kind == "forward" else max(0, pos - n)
            path.append(to)
            land(to, depth + 1)

    frm = st["pos"]
    if st["lightning"]:
        # The roll after a Lightning space collects every award it passes, landing included.
        # Signposts are passed over, and there's never a Snake in reach.
        st["lightning"] = False
        ev.append({"kind": "lightning_roll", "pos": frm})
        to = min(end, frm + move)
        for p in range(frm + 1, to + 1):
            path.append(p)
            if p >= end:
                st["pos"] = end
                finish()
                break
            kind = b[p]["type"]
            if kind == "lightning" and p != to:
                continue   # only re-arms if you stop on it
            if kind not in ("forward", "back", "snake"):
                land(p, 9)
            st["pos"] = p
    else:
        to = min(end, frm + move)
        path += list(range(frm + 1, to + 1))
        land(to, 0)
    return {"bullets": bullets, "move": move, "from": frm, "path": path, "events": ev, "done": st["done"]}


def trail_play_out(v, st: dict, rng) -> list:
    """A player who leaves mid-bonus: it fires itself to the end."""
    rolls = []
    for _ in range(500):
        if st["done"]:
            break
        rolls.append(trail_roll(v, st, rng))
    return rolls


def trail_view(st: dict) -> dict:
    """The trail as clients see it (the board, where the armadillo is, what's been won)."""
    return {k: st[k] for k in ("bet", "board", "pos", "hearts", "doubled", "upgraded", "lightning", "total", "done", "rolls")}


# ------------------------------------------------------------------ Combo Free Spins
def free_games(v, bet: int, rng, n: int = 3) -> list:
    return [spin_outcome(v, bet, rng, free=True) for _ in range(n)]


# How long the screen takes to play each part of a roll (game.js animateRoll / playEvent),
# so the server waits for the animation before the next shot.
_EVENT_SECONDS = {"coin": 0.55, "prizepot": 1.6, "heart": 0.6, "heart_used": 0.9, "snake": 1.2, "double": 1.1,
                  "upgrade": 1.0, "lightning": 0.9, "lightning_roll": 0.6, "crate": 1.0, "forward": 0.6, "back": 0.6}


def trail_roll_seconds(roll: dict) -> float:
    t = 0.09 * roll["bullets"] + 0.6          # load and spin the cylinder
    at = roll["from"]
    for p in roll["path"]:
        t += 0.5 if abs(p - at) > 1 else 0.2  # a slide (a signpost) or a hop
        at = p
    return t + sum(_EVENT_SECONDS.get(e["kind"], 0.5) for e in roll["events"])


# ------------------------------------------------------------------ the wave battle (Red Alert)
def bet_pence(x, bet: int) -> int:
    """A prize of x bets in pence, rounded half up (Python's round() rounds halves to even; the JS twin can't)."""
    return math.floor(x * bet + 0.5)


def battle_start(v, bet: int) -> dict:
    """A fresh battle: wave 0's ships all there, full shields. Nothing is drawn until a shot is fired."""
    b = v.battle
    return {"bet": bet, "wave": 0, "waves": len(b["waves"]), "ships": [True] * b["waves"][0], "shields": b["shields"],
            "max_shields": b["shields"], "boss_hp": None, "boss_max": b["boss_hits"], "total": 0, "spins": 0,
            "shots": 0, "cleared": 0, "won": False, "done": False}


def battle_shot(v, st: dict, rng, target=None) -> dict:
    """One shot; `st` advances. `target` is a ship still there (any other, or None, takes the first one left; the boss
    needs none). Which ship is hit never changes the draw. Returns {target, answered, events, done}. Events:
    return_fire {ship, shields}, shields_down, destroyed {ship, pence | spins}, wave_clear {wave, pence},
    wave_start {wave, ships, shields}, boss_start {hp, shields}, boss_hit {hp}, boss_destroyed {pence}."""
    b, ev = v.battle, []
    st["shots"] += 1
    boss = st["boss_hp"] is not None
    if boss:
        target = "boss"
    elif not (isinstance(target, int) and 0 <= target < len(st["ships"]) and st["ships"][target]):
        target = st["ships"].index(True)
    answered = rng() < (b["boss_fire"] if boss else b["return_fire"][st["wave"]])
    if answered:
        st["shields"] -= 1
        ev.append({"kind": "return_fire", "ship": target, "shields": st["shields"]})
        if st["shields"] <= 0:
            ev.append({"kind": "shields_down"})
            st["done"] = True
    elif boss:
        st["boss_hp"] -= 1
        ev.append({"kind": "boss_hit", "hp": st["boss_hp"]})
        if st["boss_hp"] <= 0:
            pence = bet_pence(_draw(rng, b["boss"]), st["bet"])
            st["total"] += pence
            ev.append({"kind": "boss_destroyed", "pence": pence})
            st["won"] = st["done"] = True
    else:
        st["ships"][target] = False
        if rng() < b["spins_chance"]:
            n = _draw(rng, b["spins"])
            st["spins"] += n
            ev.append({"kind": "destroyed", "ship": target, "spins": n})
        else:
            pence = bet_pence(_draw(rng, b["prizes"]), st["bet"])
            st["total"] += pence
            ev.append({"kind": "destroyed", "ship": target, "pence": pence})
        if not any(st["ships"]):
            pence = bet_pence(b["clear"][st["wave"]], st["bet"])
            st["total"] += pence
            st["cleared"] += 1
            ev.append({"kind": "wave_clear", "wave": st["wave"], "pence": pence})
            st["wave"] += 1
            st["shields"] = st["max_shields"]
            if st["wave"] < st["waves"]:
                st["ships"] = [True] * b["waves"][st["wave"]]
                ev.append({"kind": "wave_start", "wave": st["wave"], "ships": len(st["ships"]), "shields": st["shields"]})
            else:
                st["ships"] = []
                st["boss_hp"] = st["boss_max"]
                ev.append({"kind": "boss_start", "hp": st["boss_hp"], "shields": st["shields"]})
    return {"target": target, "answered": answered, "events": ev, "done": st["done"]}


def _draw(rng, table):
    return weighted(rng, [tuple(p) for p in table])


def battle_play_out(v, st: dict, rng) -> list:
    """A player who leaves mid-battle (and the simulator): it fires itself to the end."""
    shots = []
    for _ in range(2000):
        if st["done"]:
            break
        shots.append(battle_shot(v, st, rng))
    return shots


def battle_view(st: dict) -> dict:
    """The battle as clients see it."""
    return dict(st, ships=list(st["ships"]))


# How long the screen takes to play each part of a shot (game.js / slot_screen.gd), so the server waits for it.
_BATTLE_SECONDS = {"return_fire": 1.0, "shields_down": 1.6, "destroyed": 0.9, "wave_clear": 1.8, "wave_start": 1.6,
                   "boss_start": 2.4, "boss_hit": 0.7, "boss_destroyed": 2.6}


def battle_shot_seconds(shot: dict) -> float:
    return 0.6 + sum(_BATTLE_SECONDS.get(e["kind"], 0.5) for e in shot["events"])


# ------------------------------------------------------------------ the island voyage (Dead Man's Map)
def voyage_map(v, rng) -> list:
    """The map, drawn up front: a list of legs, each three islands (top to bottom). No Port Royal on the first leg
    (there are no relics to trade yet); then each Hidden Cove takes an island on a leg of its own, from the second."""
    y = v.voyage
    first = [k for k in y["kinds"] if k[0] != "port"]
    legs = [[_draw(rng, first if leg == 0 else y["kinds"]) for _ in range(3)] for leg in range(y["legs"])]
    open_legs = list(range(1, y["legs"]))
    for _ in range(min(y["coves"], len(open_legs))):
        leg = open_legs.pop(randint(rng, len(open_legs)))
        legs[leg][randint(rng, 3)] = "cove"
    return legs


def voyage_start(v, bet: int, rng, chart=None) -> dict:
    """A fresh voyage at the start port (leg -1), its map drawn."""
    return {"bet": bet, "map": chart or voyage_map(v, rng), "leg": -1, "row": None, "route": [], "relics": 0, "keys": 0,
            "artefacts": [False] * len(v.voyage["parts"]), "spins": 0, "total": 0, "awaiting": "sail", "sunk": False,
            "treasure": None, "steps": 0, "done": False}


def voyage_deals(v, st: dict) -> list:
    """Port Royal's deals you can afford, in the screen's order."""
    y, n = v.voyage, st["relics"]
    out = []
    if n >= y["artefact_price"] and not all(st["artefacts"]):
        out.append("artefact")
    if n >= y["key_price"]:
        out.append("key")
    if n >= y["spins_price"]:
        out.append("spins")
    if n:
        out.append("sell")
    return out


def voyage_options(v, st: dict) -> list:
    """What can be chosen now: the open islands on the next leg (their rows; a cove needs a key), "final" after the
    last leg, or at Port Royal the deals you can afford and "leave"."""
    if st["done"]:
        return []
    if st["awaiting"] == "trade":
        return voyage_deals(v, st) + ["leave"]
    if st["leg"] == len(st["map"]) - 1:
        return ["final"]
    nxt = st["map"][st["leg"] + 1]
    rows = range(3) if st["leg"] < 0 else range(max(0, st["row"] - 1), min(2, st["row"] + 1) + 1)
    return [r for r in rows if nxt[r] != "cove" or st["keys"] > 0]


def voyage_auto(v, st: dict, rng):
    """The choice made for a player who waits (and for NPCs and the simulator): a random open island; at Port Royal
    an artefact if it can, else free games, else sell up."""
    opts = voyage_options(v, st)
    if st["awaiting"] == "trade":
        return next(d for d in ("artefact", "spins", "sell", "leave") if d in opts)
    return opts[0] if len(opts) == 1 else opts[randint(rng, len(opts))]


def _missing(st: dict) -> list:
    return [i for i, held in enumerate(st["artefacts"]) if not held]


def _find_artefact(st: dict, rng, ev: list) -> None:
    gone = _missing(st)
    if gone:
        i = gone[randint(rng, len(gone))]
        st["artefacts"][i] = True
        ev.append({"kind": "artefact", "i": i})


def voyage_step(v, st: dict, rng, choice=None) -> dict:
    """One choice; `st` advances. `choice` is one of voyage_options (anything else, or None, is chosen for you by
    voyage_auto). Returns {action (sail/trade/final), choice, events, done}. Events: arrive {leg, row, island},
    treasure/skull/cove {pence}, relics {n}, key, artefact {i}, unlock, sunk, port {deals}, bought {deal, cost},
    sold {n, pence}, leave, final {chest, parts, legend, relics, pence}."""
    y, ev = v.voyage, []
    opts = voyage_options(v, st)
    if choice not in opts or isinstance(choice, bool):
        choice = voyage_auto(v, st, rng)
    st["steps"] += 1
    if st["awaiting"] == "trade":
        st["awaiting"] = "sail"
        if choice == "sell":
            n, pence = st["relics"], bet_pence(st["relics"] * y["relic_value"], st["bet"])
            st["relics"] = 0
            st["total"] += pence
            ev.append({"kind": "sold", "n": n, "pence": pence})
        elif choice == "leave":
            ev.append({"kind": "leave"})
        else:
            cost = y[f"{choice}_price"]
            st["relics"] -= cost
            ev.append({"kind": "bought", "deal": choice, "cost": cost})
            if choice == "artefact":
                _find_artefact(st, rng, ev)
            elif choice == "key":
                st["keys"] += 1
                ev.append({"kind": "key"})
            else:
                st["spins"] += y["spins_games"]
        return {"action": "trade", "choice": choice, "events": ev, "done": False}
    if choice == "final":
        held = st["artefacts"]
        t = {"chest": bet_pence(y["chest"], st["bet"]), "parts": [bet_pence(p, st["bet"]) if h else 0 for p, h in zip(y["parts"], held)],
             "legend": bet_pence(y["legend"], st["bet"]) if all(held) else 0, "relics": bet_pence(st["relics"] * y["relic_value"], st["bet"])}
        t["pence"] = t["chest"] + sum(t["parts"]) + t["legend"] + t["relics"]
        st["total"] += t["pence"]
        st["treasure"] = t
        st["relics"] = 0
        st["leg"] += 1
        st["done"] = True
        ev.append({"kind": "final", **t})
        return {"action": "final", "choice": choice, "events": ev, "done": True}
    st["leg"] += 1
    st["row"] = choice
    st["route"].append(choice)
    island = st["map"][st["leg"]][choice]
    ev.append({"kind": "arrive", "leg": st["leg"], "row": choice, "island": island})

    def pay(kind, table):
        pence = bet_pence(_draw(rng, y[table]), st["bet"])
        st["total"] += pence
        ev.append({"kind": kind, "pence": pence})
    if island == "treasure":
        pay("treasure", "treasure")
    elif island == "wreck":
        n = _draw(rng, y["relics"])
        st["relics"] += n
        ev.append({"kind": "relics", "n": n})
        if rng() < y["item_chance"]:
            if not _missing(st) or rng() < y["key_chance"]:
                st["keys"] += 1
                ev.append({"kind": "key"})
            else:
                _find_artefact(st, rng, ev)
    elif island == "skull":
        if rng() < y["sink"]:
            st["sunk"] = st["done"] = True
            st["awaiting"] = None
            ev.append({"kind": "sunk"})
        else:
            pay("skull", "skull")
    elif island == "port":
        deals = voyage_deals(v, st)
        ev.append({"kind": "port", "deals": deals})
        if deals:
            st["awaiting"] = "trade"
    elif island == "cove":
        st["keys"] -= 1
        ev.append({"kind": "unlock"})
        pay("cove", "cove")
        _find_artefact(st, rng, ev)
    return {"action": "sail", "choice": choice, "events": ev, "done": st["done"]}


def voyage_play_out(v, st: dict, rng) -> list:
    """A player who leaves mid-voyage (and the simulator): every choice made by voyage_auto, to the end."""
    steps = []
    for _ in range(100):
        if st["done"]:
            break
        steps.append(voyage_step(v, st, rng))
    return steps


def voyage_view(v, st: dict) -> dict:
    """The voyage as clients see it, with what can be chosen now."""
    out = json.loads(json.dumps(st))
    out["options"] = voyage_options(v, st)
    out["legs"] = len(st["map"])
    return out


# How long the screen takes to play each part of a step (game.js / slot_screen.gd), so the server waits for it.
_VOYAGE_SECONDS = {"arrive": 1.4, "treasure": 1.0, "relics": 0.8, "key": 0.8, "artefact": 1.2, "unlock": 0.8, "sunk": 2.2,
                   "skull": 1.2, "port": 0.6, "cove": 1.2, "bought": 0.6, "sold": 0.9, "leave": 0.3, "final": 4.5}


def voyage_step_seconds(step: dict) -> float:
    return 0.3 + sum(_VOYAGE_SECONDS.get(e["kind"], 0.5) for e in step["events"])


# ------------------------------------------------------------------ the expedition (Delta Quadrant)
EXPEDITION_RANK = ("hazard", "credits", "scanner", "shuttle", "shields", "mult", "spins", "artefact", "wormhole")


def expedition_start(v, bet: int, rng) -> dict:
    """A fresh expedition at the chart: three routes, each a length and a hazard level (with its final prize)."""
    e = v.expedition
    routes = []
    for _ in range(3):
        length = _draw(rng, e["lengths"])
        level = _draw(rng, [(i, lv["weight"]) for i, lv in enumerate(e["levels"])])
        routes.append({"length": length, "level": level, "final": e["levels"][level]["final"]})
    return {"bet": bet, "routes": routes, "route": None, "sector": -1, "planets": None, "found": [], "awaiting": "route",
            "mult": 1, "scanners": 0, "shuttles": 0, "shields": 0, "scanned": False, "shuttle_now": False, "spins": 0,
            "total": 0, "ended": False, "wormhole": False, "final": None, "steps": 0, "done": False}


def _planet(e: dict, level: dict, sector: int, rng) -> dict:
    """One hidden planet: what it is, and what it holds (credits and the artefact already scaled by the level).
    Hazards grow more likely the deeper into the route (`ramp` more weight a sector)."""
    kind = _draw(rng, e["kinds"] + [["hazard", level["hazard"] + e["ramp"] * sector]])
    p = {"kind": kind, "seen": False, "by": None}
    if kind == "credits":
        p["x"] = _draw(rng, e["credits"]) * level["scale"]
    elif kind == "mult":
        p["n"] = _draw(rng, e["mults"])
    elif kind == "tech":
        p["kind"] = _draw(rng, e["techs"])
    elif kind == "special":
        p["kind"] = _draw(rng, e["specials"])
        if p["kind"] == "artefact":
            p["x"] = _draw(rng, e["artefact"]) * level["scale"]
        elif p["kind"] == "spins":
            p["n"] = _draw(rng, e["spins"])
    return p


def _enter_sector(v, st: dict, rng, ev: list) -> None:
    """Warp to the next sector: its three planets drawn; a Scanner shows them, a Shuttle launches."""
    e = v.expedition
    level = e["levels"][st["routes"][st["route"]]["level"]]
    st["sector"] += 1
    st["planets"] = [_planet(e, level, st["sector"], rng) for _ in range(3)]
    st["found"].append([])
    st["awaiting"] = "planet"
    ev.append({"kind": "warp", "sector": st["sector"]})
    st["scanned"] = st["scanners"] > 0
    if st["scanned"]:
        st["scanners"] -= 1
        for p in st["planets"]:
            p["seen"] = True
        ev.append({"kind": "scan", "planets": json.loads(json.dumps(st["planets"]))})
    st["shuttle_now"] = st["shuttles"] > 0
    if st["shuttle_now"]:
        st["shuttles"] -= 1
        ev.append({"kind": "shuttle"})


def expedition_options(v, st: dict) -> list:
    """What can be chosen now: a route (0-2) at the chart, else the planets not yet explored in this sector."""
    if st["done"]:
        return []
    if st["awaiting"] == "route":
        return [0, 1, 2]
    return [i for i, p in enumerate(st["planets"]) if p["by"] is None]


def _worth(p: dict) -> tuple:
    return (EXPEDITION_RANK.index(p["kind"]), p.get("x", p.get("n", 0)))


def expedition_auto(v, st: dict, rng):
    """The choice made for a player who waits (and for NPCs and the simulator): a random route, a random planet, or
    in a scanned sector the best one shown (never a hazard while there's anything else)."""
    opts = expedition_options(v, st)
    if st["awaiting"] != "route" and st["scanned"]:
        best = opts[0]
        for i in opts[1:]:
            if _worth(st["planets"][i]) > _worth(st["planets"][best]):
                best = i
        return best
    return opts[randint(rng, len(opts))]


def _explore(v, st: dict, p: dict, by: str, ev: list):
    """What a planet does once explored. Returns "end" (a hazard), "wormhole", or None."""
    k = p["kind"]
    if k in ("credits", "artefact"):
        p["pence"] = bet_pence(p["x"] * st["mult"], st["bet"])
        st["total"] += p["pence"]
        ev.append({"kind": k, "pence": p["pence"]})
    elif k == "mult":
        st["mult"] += p["n"]
        ev.append({"kind": "mult", "n": p["n"], "mult": st["mult"]})
    elif k in ("scanner", "shuttle", "shields"):
        st[k + "s" if k != "shields" else k] += 1
        ev.append({"kind": "tech", "tech": k})
    elif k == "spins":
        st["spins"] += p["n"]
        ev.append({"kind": "spins", "n": p["n"]})
    elif k == "wormhole":
        ev.append({"kind": "wormhole"})
        return "wormhole"
    elif by == "shuttle":
        ev.append({"kind": "shuttle_lost"})
    elif st["shields"] > 0:
        st["shields"] -= 1
        ev.append({"kind": "shielded"})
    else:
        ev.append({"kind": "hazard"})
        return "end"
    return None


def expedition_step(v, st: dict, rng, choice=None) -> dict:
    """One choice; `st` advances. `choice` is one of expedition_options (anything else, or None, is chosen for you by
    expedition_auto). Returns {action (route/explore/shuttle), choice, events, done}. Events: route {i}, warp {sector},
    scan {planets}, shuttle, reveal {i, by, planet}, credits/artefact {pence}, mult {n, mult}, tech {tech}, spins {n},
    wormhole, shielded, shuttle_lost, hazard, missed {planets: [[i, planet]]}, final {pence, mult, wormhole}."""
    e, ev = v.expedition, []
    opts = expedition_options(v, st)
    if choice not in opts or isinstance(choice, bool):
        choice = expedition_auto(v, st, rng)
    st["steps"] += 1
    if st["awaiting"] == "route":
        st["route"] = choice
        ev.append({"kind": "route", "i": choice})
        _enter_sector(v, st, rng, ev)
        return {"action": "route", "choice": choice, "events": ev, "done": False}
    by = "shuttle" if st["awaiting"] == "shuttle" else "ship"
    p = st["planets"][choice]
    p["by"], p["seen"] = by, True
    st["found"][-1].append(p["kind"])
    ev.append({"kind": "reveal", "i": choice, "by": by, "planet": dict(p)})
    out = _explore(v, st, p, by, ev)
    if out is None and by == "ship" and st["shuttle_now"]:
        st["awaiting"] = "shuttle"
        return {"action": "explore", "choice": choice, "events": ev, "done": False}
    missed = []
    for i, q in enumerate(st["planets"]):
        if q["by"] is None:
            q["seen"] = True
            if "x" in q:
                q["pence"] = bet_pence(q["x"] * st["mult"], st["bet"])
            missed.append([i, dict(q)])
    if missed:
        ev.append({"kind": "missed", "planets": missed})
    route = st["routes"][st["route"]]
    if out == "end":
        st["ended"] = st["done"] = True
        st["awaiting"] = None
    elif out == "wormhole" or st["sector"] == route["length"] - 1:
        st["wormhole"] = out == "wormhole"
        boost = e["wormhole"] if st["wormhole"] else 1
        st["final"] = bet_pence(route["final"] * boost * st["mult"], st["bet"])
        st["total"] += st["final"]
        st["done"] = True
        st["awaiting"] = None
        ev.append({"kind": "final", "pence": st["final"], "mult": st["mult"], "wormhole": st["wormhole"]})
    else:
        _enter_sector(v, st, rng, ev)
    return {"action": by if by == "shuttle" else "explore", "choice": choice, "events": ev, "done": st["done"]}


def expedition_play_out(v, st: dict, rng) -> list:
    """A player who leaves mid-expedition (and the simulator): every choice made by expedition_auto, to the end."""
    steps = []
    for _ in range(100):
        if st["done"]:
            break
        steps.append(expedition_step(v, st, rng))
    return steps


def expedition_view(v, st: dict) -> dict:
    """The expedition as clients see it: a planet not yet revealed or scanned shows nothing of what it is."""
    out = json.loads(json.dumps(st))
    if out["planets"]:
        out["planets"] = [p if p["seen"] else {"kind": None, "seen": False, "by": None} for p in out["planets"]]
    out["options"] = expedition_options(v, st)
    return out


# How long the screen takes to play each part of a step (game.js / slot_screen.gd), so the server waits for it.
_EXPEDITION_SECONDS = {"route": 1.6, "warp": 1.2, "scan": 1.0, "shuttle": 0.6, "reveal": 0.9, "credits": 0.8, "mult": 1.0,
                       "tech": 1.0, "artefact": 1.4, "wormhole": 2.2, "spins": 1.0, "hazard": 2.2, "shielded": 1.4,
                       "shuttle_lost": 1.2, "missed": 1.2, "final": 3.0}


def expedition_step_seconds(step: dict) -> float:
    return 0.3 + sum(_EXPEDITION_SECONDS.get(e["kind"], 0.5) for e in step["events"])
