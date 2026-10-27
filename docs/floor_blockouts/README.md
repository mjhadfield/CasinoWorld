# Resort floor blockouts

**All three have been built**, each as its own hidden casino (2026-10-27, `tools/seed_blockout.py a|b|c`; see
`docs/tasks/multi-casino.md`): A **The Loop** (`loop`), B **The Promenade** (`promenade`) and C **The Boulevard**
(`boulevard`). Step 4 onwards below (the placeholders, the NPCs) is still to do in each.

Three layouts for a medium resort casino, drawn at game scale on top of the live Modern lobby. They're blockouts,
not a build: nothing here is on the floor plan, live or draft. Nothing's been decided yet; this is for Mike to
review and, if one appeals, to build from.

**To review:** open [resort-floor-blockouts.html](resort-floor-blockouts.html) in a browser. It has the three plans,
a room schedule for each, and building notes. It's also published as a private artifact:
https://claude.ai/artifact/CaS96diAGkrDWER8PLxfLy. (Offline, the page falls back to system fonts.)

## The three variations

| | Idea | Inspired by | Tables | Slots | Furthest walk |
|---|---|---|---|---|---|
| **A · The Loop** | One big open floor. A racetrack aisle circles two pits plus roulette and craps, slots line the outside, and the centre bar is at the head of the entrance aisle. High limit salon, high limit slots, restaurant, showroom lounge and sportsbook open off the floor's walls. | Las Vegas Strip resorts | 16 | 152 | 34 s |
| **B · The Promenade** | Rooms in a line on one axis: Grand Hall, then Grand Salon, then Salle Privée, each one door further in. The slots get their own hall, and a garden terrace loops back to the salon. The lounge bar and restaurant are on the other side. | Grand European casinos | 13 | 112 | 28 s |
| **C · The Boulevard** | An indoor street across the front with a restaurant, show lounge, café, sportsbook and shop doors off it. Three archways lead onto a big floor: slots at the front, then two pits of six round an island bar, then roulette and craps. The Vault, the Jade Room (Baccarat and Pai Gow) and high limit slots open off its back and sides. | Resort shopping streets, Macau baccarat salons | 25 | 108 | 29 s |

"Furthest walk" is from the lobby spawn to the middle of the furthest named room, timed by the server's own
`plan.Routes` at the player's walking speed (105 px/s).

All three keep the Modern lobby where it is, at (0, −64) and 608 × 400, along with both lifts. The one change is
the lobby's top door, which becomes an **archway 192 wide** so you can see the casino from the spawn point.

## What's in this folder

- `resort-floor-blockouts.html`: the review page.
- `blueprints/plan_a.json`, `plan_b.json`, `plan_c.json`: each variation's new rooms as real floor plan rooms,
  ready to go into a draft (see below). Room ids are prefixed `a_`, `b_` and `c_` so all three can sit in one draft
  side by side. Every room is `placed: false`, and item and door ids are left out so the server gives fresh ones. An
  old id that matched a live table would otherwise be taken for that table. The lobby and lifts aren't included.
- `generator/`: the scripts that built everything. `common.py` has the helpers (rooms, pits, bar runs, dining sets)
  and the check, `plan_a.py` to `plan_c.py` hold the layouts in room coordinates, `render.py` exports the
  blueprints and draws the SVGs, and `page.py` writes the page.

To regenerate after changing a layout (this reads the asset library and live lobby, and writes only this folder):

```
cd docs/floor_blockouts/generator
PYTHONDONTWRITEBYTECODE=1 ../../../server/.venv/bin/python page.py
```

It prints each plan's problem count, tables, slots, seats and walk times.

## How they were checked

Every room, door, table, slot bank, piece and NPC point was built as a real plan, then run through `plan.clean` and
`plan.problems` (the checks the Floor plan tab runs before publishing). Those cover things off the floor, things in
each other's way, doors that don't line up or run into corners, and seats and points nobody can reach from the spawn.
All three pass with **0 problems**. The blueprint files also pass when merged into the current `draft.json` (tested
in memory only, nothing saved).

## Numbers they were built to

Taken from `plan_catalogue.json`, `plan.py` and the client, so a new room can be laid out the same way:

- **Walls:** back wall 70 px (8 if `back: thin`, like the terrace in B), sides 8, front 10. Doors and archways are
  40 to 600 wide and must stay clear of the corners, so a 160-tall NPCs-only room's side door has to sit at
  `at` ≥ 94 for a 48-wide door.
- **Card table** (rot 0): 327 wide, covering 175 above its centre to 48 below (dealer above, seats 62 below).
  Rot 180 is the same, flipped.
- **Pit:** a row at 180 over a row at 0, 376 apart, with tables 344 apart along the row. It runs from 62 above
  the top row's centre to 438 below it, and a pit podium fits in the dealers' aisle 192 below the top row.
  See `pit()` in `common.py`.
- **Roulette** 355 × 195 and **craps** 397 × 232. Both have a 35-wide results sign past one end, so allow
  about 400 and 440.
- **Slot banks:** a bank of 6 is about 214 × 136 with its seats (rows 192 apart leave a walkable aisle). A bank of
  4 is about 214 wide and faces one way, so it suits a wall, at y = 134 under a back wall or 6 above the floor's
  bottom edge facing up.
- **Speeds:** players walk at 105 px/s and NPCs at 85, so 1024 px is about a 10-second walk.

## If you decide to build one

1. **Pick a variation, or mix parts.** Each room is its own blueprint, so a hybrid is mostly moving rooms around.
   For example, A's racetrack inside C's floor, or C's Jade Room off A's floor.
2. **Try it on the dev instance first** (`tools/dev.sh server`), not the live draft. To load a variation, add its
   `blueprints/plan_x.json` rooms to the draft's `rooms` and `PUT /api/plan/draft` with
   `{rooms, spawn, base_rev}`, or ask Claude to do it. The rooms carry absolute plan positions that assume
   the lobby at (0, −64). If the lobby moves, move every room by the same amount.
3. **Open the lobby's top door** into a 192 archway (in the blueprints this is noted in `lobby_change`, not done).
4. **Replace the placeholders:**
   - Every slot bank is set to Armadillo. Pick real slots per bank on the Floor plan tab.
   - NPC figures use stand-in looks ("dealer", "cashier", "security"). Live looks are generated ids (`x_…`)
     from Staff & uniforms, so choose real ones.
   - Labels like "Blackjack £500" are only labels. Set real **table limits** (`props.limits`) on the high-limit
     tables so the limits sign shows them, and give those rooms their own table styles.
   - Floors are all `carpet` with crimson walls, and the aisles and carpets are `plain` patches with a tint.
     Swap in Vegas, Modern or Nocturne textures and wall styles.
   - Furniture stand-ins: restaurant tables are `round_table` with an `armchair` each side, the sportsbook counter
     is `reception_desk`s, and bars are the Vegas bar counter, back bar and stools. New art would replace these.
5. **Tune the NPCs:** each room has one to three wander points (weight 1, linger 20 s), and each NPCs-only room
   (kitchen, staff, restrooms, boutique) has an arrival point. Adjust the weights so the bar and restaurant draw
   people.
6. **Publishing adds tables, so the casino reopens** with them (its players are moved across; other casinos carry on).

## Open questions before building

- **Performance.** C has 25 tables and 108 slots, and A has 152 slots. Each player is now sent only the tables
  near them (protocol.md "Tables near you"), but every room is still built on every client.
- **Walking time.** Around 30 s to the furthest rooms in all three. If that's too long in play, shrink the main
  floor rather than the side rooms, or add a spawn nearer the action.
- **Staff who only stand there.** Waiters, cashiers, bar staff and pit bosses are decoration for now (also in
  "Not done yet"). The restaurant, bars and cage look staffed but don't do anything yet.
- **Interactive objects.** Only the ATM responds to a click. The cashier cages, betting counters and bars would
  need an `interact` kind each if they're to do something.
- **Sportsbook.** It's decor and seats for now. Betting on it would be a new game.
- **Turned tables.** The pits use rot 0 and 180 only. Turned card tables beyond Blackjack, or 90° tables, could
  fit more into the salons.
- **No poker room.** CasinoWorld has no poker game. A tournament room could take one of the side-room slots if
  that changes.
- **High limit slots.** Their own rooms only mean something if cabinets can carry higher stakes than the
  floor's. Otherwise they're a theme.
- **Existing blueprints.** The unplaced Vegas floor and Casino Floor rooms in the draft could become rooms in one
  of these, for example as the sportsbook's or a lounge's art.
