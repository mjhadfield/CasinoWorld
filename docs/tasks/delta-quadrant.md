# Delta Quadrant: the exploration bonus

**Branch:** `main`

## Goal
A new library bonus game, from Mike's spec for the Voyager design: chart one of three routes through unexplored
Delta Quadrant sectors, explore a planet in each sector for credits, multipliers, tech or a special discovery, and
reach the final destination unless a hazard ends the expedition first. Any slot can switch it on in the wizard's
Bonus games step; Voyager will (Mike routes it).

## How it plays (Mike's picks, 2026-10-20)
- **Pick a planet each sector.** Three hidden planets a sector; pick one, the others then show what you missed.
- **Routes are random each time, hinted.** Each route's length and hazard level is drawn per bonus and shown as
  readings with its final prize. Riskier routes have richer planets and a bigger final prize, tuned so every
  route pays about the same on average (a test checks it).
- **A hazard keeps your wins but loses the final prize**, unless Shields absorb it.
- **Specials:** an ancient artefact (a big prize), a Wormhole (straight to the final destination, boosted) and free
  games (played afterwards as Combo Free Games).
- **Tech:** Scanner (the next sector shown before you pick), Shuttle (explore a second planet in the next sector;
  a hazard only loses the shuttle), Shields (absorb the next hazard).
- **Multipliers** add to a running expedition multiplier (from x1) on every later prize and the final prize.

Engine key `expedition` (base.BONUSES); variant field `expedition` (base.EXPEDITION defaults); display name
"DELTA QUADRANT".

## Files
- engine: `server/casino_server/slots/` (base, bonuses, variant, sim), `docs/slots/mockup/slots_math.js`
- cabinet: `tables/slot_machine.py`, `casino.py` (action), `npc.py`, `server/protocol.md`
- wizard: `slot_design_steps.py`, `slot_design_build.py`, `slot_design_web/steps/bonuses.js`, `maths.js`,
  `mockup/sim_worker.js`, `mockup/game.js`, `mockup/design.js`, `artslot.js`
- game: `client/scenes/slots/slot_screen.gd`; `sounds.py`
- docs: `docs/games/slots.md`, `docs/slots/README.md`, `docs/slots/scenes.md`, README

## Done when
- [x] Engine in Python and JS, draw for draw (parity test), sims include it, routes balanced
- [x] Cabinet plays it (expedition_choose, auto choose, stand-up plays it out, banked free games follow), NPCs play it
- [x] Wizard: Expedition row (on/off, ways in, words, settings, pictures), maths measures it, Build writes its texts
- [x] Mockup plays it (Try it)
- [x] The game's slot screen plays it
- [x] Sounds, docs
- [x] `tools/dev.sh test --all` passes
- [ ] Mike: switch it on for Voyager (route it), pictures, freeze the maths, sign off, Build, Install

## Handoff
- **State:** built and in the library (committed 2026-10-21). What's left is Mike's, on the live board: switch the
  expedition on for Voyager and choose its way in (Voyager's battle is on the bonus scatter, so sharing it plays
  one of the two at random; or Buy Bonus), pick its twelve pictures (stand-ins until then), freeze the maths (the
  expedition adds return), sign off, Build, Install.
- **Tuning (defaults, against Armadillo's free-game value ~15x a game):** random routes 45.8x (SD 49), safest
  43.1x (SD 41), most dangerous 49.4x (SD 58), shortest 43.8x, longest 48.5x: within 8% of each other. 40% of
  random expeditions end at a hazard, 7% go through a Wormhole. A `ramp` (hazards likelier deeper into a route)
  keeps long routes from paying more just because the multiplier keeps growing. The sweep scripts lived in the
  session scratchpad; `test_expedition_routes_pay_about_the_same_whatever_you_choose` keeps them within 15%.
- **Changed:** engine `slots/bonuses.py` expedition_* + `base.EXPEDITION` + `variant.expedition` + `sim.py`; JS twin
  in `slots_math.js` (parity fixture regenerated: old parts identical); cabinet phase `expedition` +
  `expedition_choose`; NPCs choose as `expedition_auto` would; wizard Expedition row, art slots x_* (stand-ins by
  `docs/slots/tools/expedition_standins.py`), maths report rows, Build texts expedition_*; mockup and Godot
  screens (same layout, timings match `_EXPEDITION_SECONDS`); six sound moments (Expedition Bonus section);
  `tools/scene.py shot --bonus expedition`.
- **Checked:** 723 tests (`--all`); the mockup played in headless Chromium (chart, scan, shuttle, shields, wormhole,
  final, plain runs to the end); the game's chart and a sector screenshotted under Star Trek's LCARS skin on a
  private dev instance, using a scratch copy of the Star Trek build routed to the expedition.
- **Questions for Mike:** the default words are Voyager's (VOYAGER, TRANSWARP CONDUIT, the five hazards) and
  editable; the sounds are the nearest fits in the library.
