# Red Alert: the wave battle bonus

**Branch:** `main`

## Goal
A new library bonus game, built from the Star Trek design's spec (Build step "Ideas to build in code"): your ship
(the Enterprise-D for Star Trek) fights five waves of cloaking enemy ships, then a boss. Any slot can switch it on
in the wizard's Bonus games step; Star Trek will start it from its bonus scatter.

## How it plays (Mike's picks, 2026-10-20)
- **Tap ships to fire.** Each shot's result is drawn by the server when it's fired, so which ship you pick never
  changes the odds (like the Jackpot Pick). Cloaked ships can't be targeted (cosmetic). It fires itself if you wait.
- **Shields can fail.** Shields hold 3 hits a wave. A shot is either answered (the ship cloaks, fires back:
  shields -1) or it destroys the ship, which reveals a prize (bet multiples) or free spins. Shields at 0 end the
  bonus; you keep what you've won. Clearing a wave pays its wave reward (rising) and restores shields.
- **Free spins are banked** and play as the slot's Combo Free Games after the battle (that many games).
- **Clear all 5 waves:** a boss flagship with its own hits bar; destroying it pays a big prize.

Engine key `battle` (base.BONUSES); variant field `battle` (base.BATTLE defaults); display name "RED ALERT".
Defaults (prototype, Armadillo's free-game value ~15x a game): waves 4/5/6/7/8 ships, return fire
.15/.20/.25/.30/.34, ship prizes .2x..25x, 1.5% a ship gives 1-3 spins, wave rewards 2/4/6/12/25x, boss 6 hits at
.30 return fire paying 100..1000x. Mean ~43x, boss reached ~7%, destroyed ~4%. Money: floor(x * bet + 0.5) in both
engines (Python's round() is banker's).

## Files
- engine: `server/casino_server/slots/` (base, bonuses, variant, sim), `docs/slots/mockup/slots_math.js`
- cabinet: `tables/slot_machine.py`, `casino.py` (action), `npc.py`, `server/protocol.md`
- wizard: `slot_design_steps.py`, `slot_design_build.py`, `slot_design_web/steps/bonuses.js`, `maths.js`,
  `mockup/sim_worker.js`, `mockup/game.js`, `mockup/design.js`
- game: `client/scenes/slots/slot_screen.gd`, `client/autoload/sfx.gd`; `sounds.py`
- docs: `docs/games/slots.md`, `docs/slots/README.md`, README

## Done when
- [x] Engine in Python and JS, draw for draw (parity test), sims include it
- [x] Cabinet plays it (battle_fire, auto fire, stand-up plays it out, banked free games follow), NPCs play it
- [x] Wizard: Battle card (on/off, ways in, words, settings, pictures), maths measures it, Build writes its texts
- [x] Mockup plays it (Try it)
- [x] The game's slot screen plays it
- [x] Sounds, docs
- [x] `tools/dev.sh test` passes (`--all`: the slots maths changed)
- [ ] Mike: reopen Star Trek's sign-off, switch Red Alert on (bonus scatter), pictures, re-freeze maths, sign off, Build, Install

## Handoff
- **State:** the bonus is built and in the library (committed 2026-10-20). What's left is Mike's, on the live board:
  reopen Star Trek's sign-off, switch the battle bonus on (it defaults to the bonus scatter and Buy Bonus), pick its
  three pictures, re-freeze the maths (the battle adds return), sign off, Build, Install. Then remove the "Red Alert"
  idea from Bonus games › New bonus ideas, or Build keeps listing it in IDEAS.md.
- **Changed:** engine `slots/bonuses.py` battle_* + `base.BATTLE` + `variant.battle` + `sim.py` (battle_value,
  simulate_battle, expected_rtp); JS twin in `slots_math.js` (parity fixture regenerated: old parts identical);
  cabinet phase `battle` + `battle_fire` + banked free games (`pending` 4-tuple, `free_start.source`); NPCs fire on
  random ships; wizard Battle card, art slots b_hero/b_enemy/b_boss (stand-ins in slot_art/armadillo/flux2), maths
  report rows, Build texts; mockup and Godot screens (same layout, timings match `_BATTLE_SECONDS`); five sound
  moments (Battle Bonus section).
- **Checked:** 675 tests (`--all`); mockup played to the boss in headless Chromium; the game's battle screenshotted on
  the dev instance (its dev Star Trek build's variant.json hand-routed to the battle; dev data only).
- **Questions for Mike:** the Star Trek art faces left (the Enterprise) and right (Birds of Prey); a mirror switch
  per picture would be easy if they look wrong. A proper Klingon flagship picture for the boss.
