"""
The bonus games. Each is a small state machine the cabinet steps through:

- The Trail Bonus (3+ Bonus scatters, or Buy Bonus): a pistol loads 1-6 bullets and the
  armadillo moves that many spaces along a 120-space trail, collecting what it lands on.
  A Snake ends it unless a Heart is held; the end pays the prizepot (2,000x, 4,000x doubled).
- Combo Free Spins (3+ free-spin scatters): three free games with a random feature every spin.

Ported from the mockup (slots_math.js makeBoard / trailRoll / freeGames), draw for draw.
"""
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
