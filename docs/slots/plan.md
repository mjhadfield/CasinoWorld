# Slot machines: a modular slot framework, with Armadillo Goes West as the first variant

## Context
Slots earn most of a real casino's revenue, so Casino World needs them, and in variety. Mike's concept:
- **Shared by every slot:**
  - one base game: the grid, lines, pay table and stake ladder
  - one set of Mini, Minor, Major and Grand progressives, separate from the table-game jackpot in `jackpot.py`
- **Per variant:**
  - the theme (colours, art, sounds)
  - above all, the bonus games

The first variant is **Armadillo Goes West**, from EveryMatrix/SlotMatrix's rules sheet (saved in `<scratchpad>/agw/agw.pdf`). It is a western-themed 5×4 game with 25 fixed lines, paying left to right, and has:
- **Random features** on any spin:
  - before the stop: Random Wilds (1–4), Wild Reels (1–3), Colossal Reels (2×2, 3×3 or 4×4 fused), and a Random Multiplier (2×–5×)
  - after the stop: Symbol Upgrade, Repeat Win (2–5×) and Instant Win (1×–200×, the "Random Prize" barrel)
- **Trail Bonus:** 3 or more Bonus scatters (the wagon). A board game: a pistol loads 1–6 bullets, and the Armadillo moves that many spaces along a trail of coins, Double, Forward/Back, Heart, Lightning Roll, Award-all-credits, Spin Upgrade and Snakes. The prizepot is 2000× for reaching the end.
- **Combo Feature Free Spins:** 3 or more Free Spin scatters (the crossed pistols). 3 free games, each with guaranteed random features, often several at once.
- **Buy Bonus:** 45× the bet takes you straight into the Trail Bonus.
- **RTP published:** 94.47% for the game, 93.73% for the Buy Bonus. **Not published:** reel strips, feature rates and the trail layout. We design these ourselves and tune them by simulation.

Deliverables:
1. **A floor cabinet with a stool**, placeable in any of 4 orientations, used by players and NPCs.
2. **A full-screen game screen.** This is the first in the game; tables keep the in-world camera.

**Mike's decisions (2026-10-18):**
- **Progressives:** won through a shared **Jackpot Pick**.
  - A random trigger on any spin, with odds proportional to the bet.
  - A board of 12 coins: pick until three match, and win that tier.
  - The meters grow from a share of every bet, from players and NPCs alike.
  - The four meters are the only slot state that persists.
- **No cross-player persistence.** A cabinet is self-contained and **limited to one session**. All of its state lives only while someone is seated. If they stand (or disconnect, or the server shuts down) mid-feature, the feature is played out at once and paid. The cabinet is then blank for the next person.
- **Stakes:** **one total-bet ladder.** Re-derived for 25 lines so the line bet is always whole pence: 25p, 50p, 75p, £1, £1.50, £2.50, £5, £10, £25.
- **Extras:** **Buy Bonus is included; Golden Bet is not.** Golden Bet stays possible later as an optional variant extra.
- **Symbol art:** the mockup shows **both** a hand-authored SVG set and a FLUX.2-klein set. Mike picks one. All art is original: nothing is taken from the real game.

**Defaults I've chosen (all reviewable in the mockup):**
- 10 cabinets in the empty south-east corner (x 1500–1850, y 830–1100): two back-to-back rows of 4, facing up and down, plus 2 end caps facing left and right, so every orientation is used.
- About 92% game RTP plus about 3% from the progressives, for about 95% in total, close to the real 94.47%.

**Gaps in the rules sheet, and my readings (each confirmed in the mockup):**
- **Boots** appears in the upgrade chain but not on the pay table. I've given it the Whiskey pays, since the chain pairs Whiskey with Boots and Hat with Horseshoe.
- **Repeat Win** is read as the same win paid N times in total, replayed on screen.
- **Double:** at most one per board. This matches the sheet's "1×–200× can be doubled to 2×–400×" and "2000× → 4000×".
- **The trail board** is generated at random for each bonus from a weighted recipe. No Snake is placed within reach of a Lightning Roll (6, or 12 after a Spin Upgrade), as the sheet requires.

## SIGN-OFF (Mike, 2026-10-18), mockup v1: https://claude.ai/artifact/Wi2rvMixzZZjGo68bQxMah
A local copy is in `docs/slots/mockup/`. To view it, serve that folder over http (`python3 -m http.server`); the Worker needs http.

**All nine sign-off items are confirmed:**
1. **Art:** the hand-drawn vector set. FLUX candidate 2 is promising, so the admin page gets slot-art management (see "Admin: Slots › Art" below).
2. **Stakes ladder:** 25p, 50p, 75p, £1, £1.50, £2.50, £5, £10, £25. Buy Bonus is 45× the bet.
3. **Return:** game about 91.5% plus progressives 3.75%, about 95% in total. Buy Bonus 93.73%.
4. **Jackpot Pick:**
   - seeds: Mini £10, Minor £50, Major £500, Grand £5,000
   - each bet adds 0.25%, 0.25%, 0.5% and 1% to them
   - won about once per £1.5k, £10k, £150k and £2M wagered
   - the trigger chance scales with the bet
5. **Rule readings:**
   - Boots pays like Whiskey.
   - Repeat Win pays the win N times.
   - At most one Double per trail.
   - A Lightning Roll passes over signposts.
6. **Trail:**
   - 120 spaces with an exact count of each item: 20 snakes, 2 hearts, 3 forward, 3 back, 3 crates, 2 lightning.
   - A Spin Upgrade appears on 30% of boards and a Double on 40%.
7. **Big wins:** BIG at 10×, MEGA at 25×, EPIC at 50×. Autoplay offers 10, 25, 50 or 100 spins and stops on any bonus or a win of 25× or more.
8. **Cabinet:** the look, 4 orientations, and the 10-cabinet bank. **Keep the fade:** a cabinet whose screen faces up fades while someone sits behind it.
9. **Sounds:** picked later on the admin Sounds tab.

**The maths source of truth** is `docs/slots/mockup/slots_math.js`. Port it verbatim to Python, keeping the same strip seeds (1000+i base, 2000+i free, 3000 big) via `buildStrip`. It uses the mulberry32 shuffle, so either port that exactly or freeze the strip arrays: print them from node and paste them into `variants/armadillo.py`.
- **The other numbers are in `ARMADILLO`:** rates, freeRates, wildCounts, wildReelCounts, colossalSizes, multipliers, repeats, instants, the trail recipe, and the coin weights.
- **Tools** are in `docs/slots/tools/`: `tune.js`, the sweeps, `gen_svg.py` (the vector art), and the FLUX scripts (`flux_gen.py` for Odysseus at container localhost:8000, `process_flux.py` for the magenta key-out).
- **Raw FLUX outputs** are in `docs/slots/flux_raw/`.

**Mockup behaviours to carry over:**
- Summaries collect themselves after 5s.
- The bonus anticipation tease shows with 2 scatters.
- During a feature, INFO is disabled.
- The logo is lettering, not art (FLUX can't spell ARMADILLO).
- The win cycle runs while idle.
- `presentationSeconds()` sets NPC and server pacing.

### Corrections after sign-off (2026-10-18)
The large-sample measurements showed the v1 tuner figures were lucky samples: the game really returned about 93% and Buy Bonus about 92.3%. To meet the signed-off targets:
- Instant Win 0.0105 → 0.008
- trail 1× coin weight 32 → 30
- Spin Upgrade chance is 0.2; the mockup's "30%" text was wrong and has been corrected

A board-generator bug was also fixed (a Snake could stay in a Lightning Roll's reach). Every change was made in JS and Python alike.

Measured now: game 91.22%, total 94.97%, Buy Bonus 93.55%. Use `slots.sim.expected_rtp`; a single run swings ±2% because of the prizepot.

### Admin: Slots › Art (added at sign-off)
Model it on the Sounds tab (`sounds.py` SoundBoard, `/api/sounds/manifest`, `Sfx` runtime download with built-in fallback).
- **Library:** `server/slot_art/<variant>/` holds the candidates: `vector/*.png` (rendered from the SVGs), `flux1/*.png` and `flux2/*.png` (from `docs/slots/mockup/art/flux/*_1|_2.png`), plus uploads in `<data>/slot_art/uploads/`.
- **Choices:** `<data>/slot_art.json`, holding the chosen file per asset id per variant. The defaults are the vector set.
- **Endpoints:**
  - `GET /api/slots/art` lists the choices and candidates.
  - `PUT /api/slots/art` sets one choice.
  - Uploads use a raw body, as sound uploads do; images are resized to 512² with Pillow.
  - `GET /api/slots/art/manifest`.
  - A `slot_art_changed` broadcast.
- **Admin UI:** a grid of every asset with its current pick, the candidates side by side (as in the mockup's sheet), click to choose, and an upload button.
- **Client:** a `SlotArt` loader (like `LookLoader` and `Sfx`) downloads chosen images at runtime (`Image.load_png_from_buffer`), falling back to the built-in `client/assets/slots/<variant>/` vector PNGs. Cabinets and the screen re-skin on `slot_art_changed`.

---

## Architecture

### The shared base (from AGW, the house standard for every future slot)

**Grid and lines:** 5×4 and 25 lines, decoded from the rules sheet's line chart (rows top = 0):

```
 1 [1,1,1,1,1]   2 [2,2,2,2,2]   3 [0,0,0,0,0]   4 [3,3,3,3,3]   5 [1,2,3,2,1]
 6 [2,1,0,1,2]   7 [0,0,1,2,3]   8 [3,3,2,1,0]   9 [1,0,0,0,1]  10 [2,3,3,3,2]
11 [0,1,2,3,3]  12 [3,2,1,0,0]  13 [1,0,1,2,1]  14 [2,3,2,1,2]  15 [0,1,0,1,0]
16 [3,2,3,2,3]  17 [1,2,1,0,1]  18 [2,1,2,3,2]  19 [0,1,1,1,0]  20 [3,2,2,2,3]
21 [1,1,2,3,3]  22 [2,2,1,0,0]  23 [1,1,0,1,1]  24 [2,2,3,2,2]  25 [1,2,2,2,3]
```

**Pay table by tier, in multiples of the line bet (bet ÷ 25):**

| Tier | AGW symbol | 5 | 4 | 3 | Upgrades to |
|---|---|---|---|---|---|
| W | Sheriff star (Wild) | 120 | 40 | 20 | – |
| H1 | Armadillo | 120 | 40 | 20 | – |
| H2 | Snake | 100 | 40 | 20 | H1 |
| M1 | Hat | 60 | 24 | 16 | H2 |
| M2 | Horseshoe | 60 | 24 | 16 | H2 |
| M3 | Whiskey | 48 | 20 | 12 | M1 |
| M4 | Boots (assumed) | 48 | 20 | 12 | M2 |
| L1/L2 | Spade, Club | 20 | 8 | 4 | M3 |
| L3/L4 | Diamond, Heart | 20 | 8 | 4 | M4 |

- **BS:** the Bonus scatter, anywhere; 3 or more start the bonus game.
- **FS:** the Free-Spin scatter, anywhere; 3 or more start the free games.
- Scatters pay nothing, and Wild substitutes for everything except BS and FS.
- **Line evaluation:** the longest match per line only. Line wins add up.
- **Money:** wins are computed in exact pence (`line_bet × multiple × multiplier`), and round down only where a fraction arises.

**The rest of the shared base:**
- the line evaluator
- the scatter count
- the spin lifecycle, autoplay, quick stop, turbo
- the Jackpot Pick and its meters

### The feature library (reusable building blocks)
AGW's base-game flavour is a set of **composable modifiers**, each its own class with a shared interface. A variant picks which ones it uses and sets their weights, so future slots can reuse them differently.

**Pre-stop modifiers** (decided before the stops are shown):

| Modifier | Effect |
|---|---|
| `RandomWilds(1–4)` | wilds on random cells, never over W, BS or FS |
| `WildReels(1–3)` | whole reels turn wild |
| `ColossalReels(2/3/4)` | adjacent reels fuse; every cell under the big symbol counts as that symbol |
| `Multiplier(2–5)` | multiplies all line wins |

**Post-stop modifiers** (applied to the landed grid):

| Modifier | Effect |
|---|---|
| `SymbolUpgrade` | one chosen symbol upgrades one step along the tier chain |
| `RepeatWin(2–5)` | the win is paid that many times |
| `InstantWin(1–200× bet)` | a cash prize from the barrel |

**Rules enforced by the outcome pipeline:**
- No modifier lands on W, BS or FS cells.
- Wild Reels and Colossal Reels are never awarded on a spin that triggers a bonus.
- Repeat Win never happens alongside a Free-Spin trigger or an Instant Win.
- Both bonuses can never trigger on the same spin.

**The pipeline** is fixed and shared:
1. Draw the stops.
2. Count the scatters.
3. Draw the pre-stop modifiers, with the exclusions above.
4. Rebuild the fused reels from the big-symbol strips.
5. Place the wilds.
6. Apply the post-stop upgrade.
7. Evaluate the lines with the multiplier.
8. Apply Repeat Win or Instant Win.
9. Run the jackpot trigger.

The server sends every stage, so the client can play each one in order.

### Bonus games (the per-variant part)
- **`TrailBonus`:**
  - **Board:** generated from a weighted recipe of about 40 spaces.
  - **State:** position, hearts, doubled, upgraded, lightning armed, total.
  - **`roll()`:** draws 1–6, doubled after a Spin Upgrade. A Lightning Roll collects every space passed. Forward and Back moves award the space they land on. Award-all collects coins within a radius of 1–3 (weighted). A Snake costs a heart or ends the bonus. Reaching the end pays the prizepot, 2000× or 4000× if doubled.
  - **Pacing:** each roll waits for the player to press **FIRE** (Space), with a 6s auto-fire. NPCs fire after 1–2s.
- **`ComboFreeSpins`:**
  - 3 free games paid at the triggering bet, with no retrigger.
  - Each free game uses the feature library's **free-game weights**, which guarantee at least one feature and often several.
  - The free-game strips have no scatters.
- **`BuyBonus`:** an optional extra on the variant. It charges 45× the bet and starts the `TrailBonus` straight away, with its own RTP tuned near 93.7%.

### Server (`server/casino_server/`)

**New `slots/` package**

- **`base.py`:** `LINES`, `TIERS`, `PAYTABLE`, `UPGRADES`, `LADDER`, `Grid`, `evaluate(grid, multiplier) -> [Win{line, tier, count, pence, cells}]`, `scatters(grid)`.
- **`features.py`:** the modifier classes above. Each has:
  - `draw(ctx, rng)`: decide whether it fires and with what parameters
  - `apply(ctx)`: change the grid or the pay
  - `view()`: what the event carries
- **`outcome.py`:** the pipeline as `spin_outcome(variant, bet, rng, free=False) -> Outcome`, plus `presentation_seconds(outcome)`. The NPC pacing and the server's busy deadline use the same timing function the client's choreography follows.
- **`bonuses.py`:** `BonusGame` protocol (`start`, `act`, `step`, `done`, `total`, `auto_complete`, `view`), with `TrailBonus` and `ComboFreeSpins`.
- **`jackpots.py`: `SlotProgressives(store)`**
  - Tiers with seed, contribution rate and weight.
  - `contribute(bet)`.
  - `trigger(bet, rng)`, with odds ∝ bet.
  - `pick_sequence(tier, rng)`: the reveal order is fixed in advance, so the drawn tier reaches three first and no other tier gets three.
  - `win(tier)`: pays the tier and resets it to its seed.
  - `snapshot()`.
  - Persisted with `store.set_json("slot_progressives")`, throttled to every 5s. Saved on win and on `Casino.stop()`.
- **`variants/armadillo.py`: `VARIANT = SlotVariant(...)`**
  - id `armadillo`, the AGW symbol names per tier, theme id
  - base, free-game and colossal big-symbol strips
  - base and free feature weights
  - the trail recipe
  - bonuses `{BS: TrailBonus, FS: ComboFreeSpins}`
  - extras `{buy_bonus: 45}`
- **`sim.py` and `tools/slot_tune.py`**
  - **Exact** base-line RTP with no features: per-reel symbol frequencies, enumerated over 12⁵ combinations, × 25 lines (every line has the same per-reel distribution).
  - **Monte Carlo** for everything else, giving an RTP breakdown per feature, the bonus, free games, Buy Bonus and jackpots, plus hit rate, bonus frequency and volatility.

**New `tables/slot_machine.py`: `SlotMachine(TableMachine)`**
- 1 seat, `game = "slots"` (one key for the ledger, stats and NPC favourites).
- `DEALER = False`, `QUEUE_BETS = False`.
- `__init__(table_id, seats, timings, jackpot, deck_factory=None, lines=None, variant=, progressives=, rng=)`. No store access: there's no cabinet persistence.
- **Phases:** `idle` → `spinning`, then on to `jackpot_pick`, `trail` or `free_games`, then `idle`. If both trigger, the jackpot comes first.
- **Actions:**
  - `spin(seat, bet)`: the ladder is checked, then a debit (`TableError` if the player can't cover it), `contribute`, `spin_outcome`, and an immediate credit with `_paid`. Allowed `min_spin` (1s) after the last spin, so quick stop and skip work.
  - `buy_bonus(seat, bet)`: debits 45× the bet and starts the trail.
  - `trail_fire(seat)`, `jackpot_pick(seat, index)`.
- **Deadlines:**
  - free games run themselves on `free_game` deadlines, with the length set by `presentation_seconds`
  - the trail auto-fires after 6s
  - the jackpot pick auto-picks after 15s idle, then once a second
  - a player idle for 5 minutes is stood up
- **`_leaving_mid_hand` / `stand`:** finishes any feature with `auto_complete` (pays the remaining free games, plays the trail to the end with auto-fire, completes the pick), credits it, then resets the session state.
- **`snapshot()`:** only the current session's state (phase, last bet, last outcome, trail board and position, free-game count, pick board), plus the meters, so a resync can rebuild the screen.
- `Timings` with `scaled()` and `instant()`, as the conftest expects.

**Wiring**
- **`floor.py`:** `slot_1`…`slot_10` as `{"game": "slots", "variant": "armadillo", "name": "Armadillo Goes West", "seats": 1}`.
- **`casino.py`**
  - `MACHINES["slots"]`.
  - A small `_build_machine(table_id, cfg)` that passes `variant`, `progressives` and `rng` to slot machines. Other tables keep the current call.
  - `self.slot_jackpots` is created and saved in `stop()`.
  - The `slot_jackpots` snapshot is sent on join and on resync.
  - New messages, guarded with `hasattr(machine, "spin")` as craps is: `spin {bet}`, `buy_bonus {bet}`, `trail_fire`, `jackpot_pick {index}`.
- **`runner.py`:**
  - `_side_effects`: `slot_jackpot_won` broadcasts the meters.
  - `snapshot_for`: sends `on_duty: None` when `DEALER` is False.
- **`dealers.py`:** skip tables whose machine has `DEALER = False`, in `start`, `tick` and `restyle`.
- **`npc.py`**
  - **`_head_for_seat`:**
    - Pick the **game first**, weighted by `liking()`, then a seat at that game's tables. Otherwise 10 cabinets would swamp the shuffle.
    - Slot reservation is per bank: NPCs fill at most `cabinets − SLOTS_FOR_HUMANS (2)`. The per-table `len(free) - 1 >= RESERVED_FOR_HUMANS` rule can never pass with one seat.
  - **`_play_slot`** (early dispatch, like craps)
    - Spins `presentation_seconds + 0.5–2.5s` apart × pace.
    - Picks a ladder step from `_unit()`.
    - Fires the trail after 1–2s, and picks a coin every 1–2s.
    - A Gambler sometimes uses Buy Bonus when its bankroll is at least 3 × 45 × the bet.
    - 10 spins count as a round for `_round_over` and `_time_to_go`.
    - Skips the VIP greeting at cabinets.
- **`roster.py`:** `GAMES["slots"] = "Slots"`.
- **`sounds.py`:**
  - `game:slots` moments: `reel_spin` (loop), `reel_stop`, `reel_tease`, `win_small`, `win_bangup`, `big_win`, `feature_wilds` (gunshots), `feature_reels`, `feature_multiplier`, `feature_upgrade`, `instant_win`, `bonus_trigger`, `trail_fire` (cylinder spin and shots), `trail_hop`, `trail_coin`, `trail_snake`, `pick_reveal`, `jackpot_win`.
  - CC0 clips go in `sound_library/slots/`, with built-in fallbacks in `client/assets/audio/`.
- **Admin (`maintenance.html`, `app.py`):** a small **Slots** tab:
  - the four meters, with "reset to seed"
  - each cabinet: who's playing and the current phase
  - observed RTP, from the ledger and NPC visits
  - endpoints `GET /api/slots`, `POST /api/slots/reset-meter`
- **`protocol.md`:** a **Slots** section covering the messages above, plus these events:
  - `spin {seat, bet, stops, fused, pre, grid, upgraded, final, wins, multiplier, repeat, instant, total, triggers, meters, secs}`
  - `jackpot_trigger`, `jackpot_reveal`, `slot_jackpot_won`
  - `trail_start {board}`, `trail_roll {bullets, path, awards, hearts, total}`, `trail_end`
  - `free_start`, `free_game {n, of, …spin fields}`, `free_end`
  
  The protocol stays at version 3, since everything is additive.

**Meters travel with every `spin` event**, so every client's meters stay current with no extra message.

### Client (`client/`)

**A refactor first: `FloorGame` base (`scenes/table/floor_game.gd`).**
- **Moves up from `casino_table.gd`, verbatim:** the seat and stool API (`chair_pos`, `stool_pos`, `stool_at`, `stand_pos`, `free_seats`, `offer_seats`, `_draw_stool`, `seat_pose`, `focus_point`), the event queue (`handle_event`, `_process`), and the `Anim` epoch (`_after`, `_tween`, `_anim_root`).
- `CasinoTable extends FloorGame`, unchanged otherwise.
- **`casino_floor.gd`** types its generic paths as `FloorGame`: stool click, E, `_resolve_target`, `table_state`/`table_event` routing, `_sat_down`, `_leave_table`. Paths specific to bets, chips and the `SeatedBar` only run when `active_table is CasinoTable`.
- The table-only signal hookups at `casino_floor.gd:41-59` are guarded by `is CasinoTable`.
- The hardcoded `"up"` facing becomes `t.sit_facing(seat)`.

**The floor cabinet (`scenes/slots/slot_cabinet.gd` + `.tscn`, `SlotCabinet extends FloorGame`)**
- Exports: `table_id`, `variant`, and `facing`, the direction the screen faces (`down`, `up`, `left` or `right`).
- **Drawn in code**, like the felts. It is about 30 wide and 22 deep, with a 3/4-view height of about 52.
  - **Facing down:** topper with the logo, screen, button deck, LED trim in the theme accent (the reference image's coloured trims; AGW is amber and leather), and a candle on top.
  - **Facing up:** the back panel with vents and the trim edges.
  - **Facing left or right:** the profile, mirrored for the other side.
- One stool (`Seat0`) on the facing side. The sitter faces the cabinet.
- **The live mini-screen** shows the cabinet's last grid as tiny icons:
  - it blurs and stops on `spin` events, so the floor visibly plays
  - it shows a trail strip during a bonus
  - the topper flashes on big wins, and the candle spins on a progressive
- Collision is a `StaticBody2D` rectangle, and the cabinet is in `navigation_obstacles`.
- Ten instances go in `casino_floor.tscn`, editable in the Godot editor.

**The full-screen game (`scenes/slots/slot_screen.gd/.tscn`, `SlotScreen extends Control`)**
- Built under the HUD, below `SettingsMenu`, `Toast` and `Banner`.
- `hud.set_mode("slot")` hides the `TopBar` and `SeatedBar`, and `hud.is_typing()` covers it.
- **Transition:** the camera glides to the cabinet while the screen grows out of the cabinet's screen rectangle. Standing reverses it.
- Laid out from `get_viewport().get_visible_rect()` and resized on `size_changed`, as `HandSorter` does. `texture_filter = LINEAR`.
- **Top band:** the logo with a sheen shader, and four meter pills (GRAND, MAJOR, MINOR, MINI) with rolling digits.
- **Reels:** `ReelSet` with 5 `ReelStrip`s, drawing the real strips from `rules()`. There's a motion-blur shader, an exact stop on the server's stops with a bounce, and the reels stop left to right. With 2 scatters showing, the remaining reels spin longer (`reel_tease`). Space stops the reels at once.
- **Feature choreography** (`FeatureFx`, driven by the stages in the outcome):
  - **Multiplier:** a badge appears at spin start.
  - **Wild Reels:** the armadillo rolls down the reel and leaves it wild.
  - **Colossal Reels:** the reels fuse while spinning, and a big symbol lands.
  - **Random Wilds:** the pistol shoots wilds onto their cells.
  - **Symbol Upgrade:** matching symbols flip one tier up.
  - **Repeat Win:** the win is replayed with a "×N" count.
  - **Instant Win:** the barrel bursts with coins.
- **Win presentation (`WinPresenter`):**
  1. All winning lines together: glowing polylines, and pulsing symbols with a shine sweep.
  2. Each line in turn.
  3. The win meter bangs up.
- **Big-win tiers:** 10× is BIG, 25× MEGA, 50× EPIC. A coin shower (`CPUParticles2D`) plays.
- **Button deck:**
  - CREDIT (`Session.hold_balance` keeps it in step with the reels), BET − and +, WIN
  - SPIN: a big round button; Space spins
  - AUTO: 10, 25, 50 or 100 spins, stopping on a feature or a win of 25× or more
  - TURBO, BUY BONUS (with a confirmation showing 45× the bet), INFO (the pay table, line chart and feature rules from `rules()`), Settings, CASH OUT (stand)
- **Shared `JackpotPickView`:** 12 coins. The reveals arrive by event, and the third match sets off the celebration.
- **Variant registry (`scenes/slots/slot_variants.gd`):** variant id → `{theme, bonus views}`.
- **`slots/variants/armadillo/`**
  - `theme.tres`: a desert-dusk palette, a wooden saloon frame, symbol textures, the cabinet trim.
  - `trail_view.gd`: the scrolling board of item tiles. The revolver cylinder spins and loads the bullets. The armadillo hops space by space (squash and stretch). It also handles Lightning streaks, Double sweeping the board, hearts in a holster row, the snake strike, and the gold-bar prizepot at the end.
  - `free_games_view.gd`: a "COMBO FREE GAME n OF 3" band and the total-win outro.
- **Shaders:** `reel_blur`, `shine`, `glow`. They are the project's first shaders, so they get checked in the web export early.
- **Sounds:** `Sfx.play` while full-screen. Floor cabinets use `play_at` only for big wins and progressives.

### Art pipeline
**About 30 assets:**
- **12 tier symbols:** Wild star, Armadillo, Snake, Hat, Horseshoe, Whiskey, Boots, and the 4 suits carved in wood.
- **BS, FS and the barrel:** the wagon, the crossed pistols, the Random Prize barrel.
- **About 10 trail item tiles:** coin, ×2, forward and back signposts, heart, lightning, crate, upgrade sign, gold bars, snake.
- **Characters and props:** the armadillo (a rig of separate parts for the hop), the revolver cylinder, the logo.
- **Output:** 512² PNGs in `client/assets/slots/armadillo/`.

**SVG route:**
- I author the SVGs in `tools/slot_art/armadillo/*.svg`.
- `tools/build_slot_art.py` renders them with Playwright Chromium, so filters and glows survive, which Godot's ThorVG import would not.

**FLUX route:**
- Mike starts FLUX.2-klein in the Odysseus Cookbook with **CPU Offload** ticked (Gemma unloaded).
- I generate 3 candidates per asset from one shared style prompt, on a flat chroma background.
- The background is keyed out with Pillow, falling back to rembg in a scratch venv.
- The results are normalised to 512².

**Shared:** both routes produce the same file names, so the client doesn't care which art won. The cabinet and the screen chrome are drawn in code, with shaders in the theme palette.

---

## Phase A: the AGW mockup (build first, then stop for Mike's sign-off)
**Deliverable:** one self-contained HTML/canvas Artifact, "Casino World Slots". The source is `<scratchpad>/slots_mockup.html` plus `art/svg/` and `art/flux/`, published through `files`. It reuses the roulette and craps mockups' tokens and fonts, the stage and controls structure, and the sign-off panels. I'll load the `artifact-design` skill first. Redeploys go to the same path.

**What it shows:**
1. **The full-screen game at 1280×720.** It's playable, with the real JS maths: the strips, 25 lines, the full feature pipeline with its choreography, the Trail Bonus, Combo Free Spins, Buy Bonus, the Jackpot Pick, and meters fed by simulated NPC bets. It has autoplay, turbo and quick stop.
2. **An art toggle:** SVG against FLUX, on the live reels, the trail, and a symbol sheet. **Mike picks one.**
3. **The floor:** a cabinet in all 4 orientations on the carpet, at in-game zoom, with an LPC avatar seated, and the proposed 10-cabinet bank, with mini-screens animating.
4. **A tuner:** a Web Worker simulates about 1M spins, plus 100k bought bonuses. It gives an RTP breakdown per feature and bonus, hit rate, bonus frequency and volatility.
5. **Developer rigs:** force any single feature or a combination; force the trail (and seed its board), the free games, or a jackpot tier; 1×/3× speed.
6. **"To sign off" panel:**
   - the ladder
   - the RTP split
   - the feature rates
   - the trail recipe
   - jackpot seeds, rates and frequencies (proposed: Mini £10, Minor £50, Major £500, Grand £5,000; 0.25/0.25/0.5/1.0% of each bet)
   - big-win thresholds, autoplay and turbo
   - the cabinet look and the bank layout
   - the four rule readings above (Boots, Repeat Win, Double, the board)
7. **Pay table and line chart panel.**

**Phase A ends** when Mike signs off a version. The values go into the project memory, and the tuned strips and weights are copied verbatim into `variants/armadillo.py`.

## Phase B: server
1. `slots/` (`base`, `features`, `outcome`, `bonuses`, `jackpots`, `variants/armadillo`, `sim`). Port the mockup's maths, and confirm the Python sim matches the mockup's RTP figures.
2. `tables/slot_machine.py`, then the wiring in `casino.py`, `floor.py`, `runner.py`, `dealers.py`, `roster.py`.
3. NPCs: game-first choice, per-bank reservation, `_play_slot`.
4. Sounds, the admin Slots tab, the `protocol.md` Slots section.
5. Tests.

## Phase C: client
1. The `FloorGame` refactor. Check that all 11 tables still work before going on.
2. `SlotCabinet` in 4 orientations, with the mini-screen; 10 instances on the floor.
3. `SlotScreen`, reels, `FeatureFx`, `WinPresenter`, meters, the deck, `JackpotPickView`, shaders.
4. The AGW theme, `trail_view`, `free_games_view`, the registry.
5. HUD `slot` mode, the floor branches, the transition, resync (rebuild mid-trail, mid-free-games or mid-pick).
6. Docs: README, and a "Slots: adding a variant" section in `docs/architecture.md` (compose the features, write a bonus, theme folder, floor instances, tune with `tools/slot_tune.py`).

## Verification
- **pytest** (the whole suite stays green apart from the known hash-seed-flaky rebet test):
  - **Lines:** the 25 patterns match the chart.
  - **Evaluator:** the longest match per line only; wild substitution, except over BS and FS; lines add up; the multiplier applies to line wins only.
  - **Exact base-line RTP:** the enumeration agrees with a seeded simulation.
  - **Each modifier:** never over W, BS or FS; Colossal cells count individually; Upgrade follows the chain.
  - **Pipeline exclusions:** no Wild Reels or Colossal on a bonus trigger; no Repeat Win with Instant Win or an FS trigger; never both bonuses.
  - **Trail:** bullets 1–6, ×2 after an upgrade; Lightning collects every space and never meets a Snake; Forward and Back award where they land; a heart absorbs a Snake; Award-all radius; at most one Double, and it doubles the coins and the prizepot; the end pays 2000× or 4000×; `auto_complete` pays the same as playing it out with the same rng.
  - **Free games:** exactly 3, at least one feature each, no retrigger, paid at the triggering bet.
  - **Buy Bonus:** charges 45× the bet, its RTP within tolerance.
  - **Jackpots:** contributions; odds ∝ bet; the pick sequence always completes the drawn tier first; win → seed; persistence.
  - **Machine:** a spin is refused when broke or too soon; the ladder; the ledger reconciles (one debit and one payout row per spin, one 45× debit per buy); a mid-feature stand or disconnect pays the remainder and leaves a blank cabinet; the 5-minute idle stand.
  - **NPCs:** no more than `cabinets − 2` NPCs at slots; the game-first choice keeps the tables populated.
  - **Full-game RTP:** a seeded 200k-spin simulation within ±1% of the signed-off target.
  - **WebSocket round:** sit at `slot_1`, spin, receive the event and the wallet.
- **Headless Godot (`CASINO_SERVER_URL` pointing at a scratch server):**
  - `ReelStrip` lands on the server's stops for 200 random stop vectors, fused reels included.
  - Every `variant` in `floor.py` has a registry entry.
  - The cabinet ids match `floor.py`.
  - A cabinet section in `tools/layout_audit.gd`: stools are reachable on the navmesh in every orientation.
- **Playwright, on a scratch server only:**
  - Set-up: `CASINO_WEB_DIR` with a scratch export, a scratch `CASINO_DATA_DIR`, ports other than 8660/8661/8670, swiftshader GL; use `pg.wait_for_timeout`.
  - Walk to a cabinet, sit, and the screen grows out of it.
  - 20 spins with the balance arithmetic checked.
  - Rigged features (scratchpad `rig` server with `RIG=wild_reels|colossal|…`).
  - A rigged trail with a heart, a snake, lightning, and reaching the end.
  - Free games.
  - Buy Bonus.
  - A jackpot pick.
  - Hide the tab mid-trail and resync.
  - Stand mid-free-games: paid, cabinet blank.
  - A second browser watches the mini-screen.
  - Check that the shaders render in the web export.
- **Deploy:** restart `hub-proj-casino-world` from Citadel first, then export to `build/web`. Update the Casino World memory afterwards.

## Critical files
- **New, server:** `server/casino_server/slots/{__init__,base,features,outcome,bonuses,jackpots,sim}.py`, `slots/variants/armadillo.py`, `tables/slot_machine.py`, `tools/slot_tune.py`, `tests/test_slots_*.py`, `sound_library/slots/`.
- **Edited, server:** `casino.py`, `floor.py`, `tables/runner.py`, `dealers.py`, `npc.py`, `roster.py`, `sounds.py`, `app.py`, `maintenance.html`, `protocol.md`, `tests/test_npc.py` (the reservation assert).
- **New, client:** `scenes/table/floor_game.gd`, `scenes/slots/{slot_cabinet,slot_screen,reel_set,reel_strip,feature_fx,win_presenter,jackpot_meters,jackpot_pick_view,slot_variants}.gd` (+ `.tscn`), `scenes/slots/variants/armadillo/*`, `shaders/*.gdshader`, `assets/slots/armadillo/*.png`, `tools/build_slot_art.py`, `tools/slot_art/`.
- **Edited, client:** `casino_table.gd` (the code moved to `FloorGame`), `casino_floor.gd`, `casino_floor.tscn`, `hud.gd`, `autoload/sfx.gd`, `tools/layout_audit.gd`.
- **Reference:**
  - `tables/craps.py`: early NPC dispatch, extra messages.
  - `tables/roulette.py`: rng, and the plan the client plays back.
  - `jackpot.py`: persistence.
  - `hand_sorter.gd`: code-built overlay, `_place`.
  - `crp_table.gd`: `_draw_stool` override, custom collision.
  - The roulette and craps mockup HTML.
  - The AGW rules PDF and the decoded lines in `<scratchpad>/agw/`.
