# Slot design wizard

**Branch:** `main`

## Goal
Turn the admin page's Slot design tab into a wizard that builds a slot machine from art to a playable cabinet:
one tab per design (plus New), eleven steps (Concept, Art, Value ladder, Scene, Features, Bonus games, Sprites,
Sounds, Maths & payouts, Mockup & sign-off, Build), a mockup to tweak before building, and Star Trek taken all
the way through as the first. The full plan, agreed with Mike on 2026-10-20, is
`~/.claude/plans/updates-to-the-slot-snappy-cat.md`.

## Files
- `server/casino_server/slot_design.py`, `slot_design_art.py`, `slot_design_web/` (the wizard's UI), the Slot
  design tab in `maintenance.html`, `server/slot_designs/`
- the slot engine: `server/casino_server/slots/`, `docs/slots/mockup/slots_math.js`
- the client's slots: `client/scenes/slots/`, `client/autoload/slot_art.gd`, the floor's cabinets

## Done when
- [x] Phase 1: design tabs + New, step rail, Concept (sheet cutter), Art (Bin, Refine, Fit, theme brief)
- [x] Phase 2: Value ladder, Scene, engine generalisation (Armadillo parity unchanged)
- [x] Phase 3: base-game mockup from design data (slot_design_web/mockup/, Scene step + Play dialog)
- [x] Phase 4: Features and Bonus games (+ art slots, specs, rigged mockup runs)
- [x] Phase 5: Sprites and Sounds
- [x] Phase 6: Maths & payouts (simulate, auto-tune, freeze)
- [x] Phase 7: Mockup & sign-off
- [x] Phase 8: Build, data variants, client generalisation
- [x] Phase 9: Star Trek playable on the floor
- [x] `tools/dev.sh test` passes (663, 2026-10-20; `--all` passed after the engine change)

## Handoff
- **State:** Phases 1-8 done and live. Phase 9 is Mike's: take Star Trek through the steps on the live board (choices below), then Build + Install, and put its cabinets in a bank on the admin page's Floor tab (slot_banks.py; Build no longer places them). The dev copy (.dev/) was built end to end as a check.
- **Changed:** Phase 8: slot_builds.py, slot_design_build.py, steps/build.js, slot_art.py built variants + fonts, sounds.refresh_sets, welcome cabinets; client slot_screen theme, slot_cabinet look, casino_floor built cabinets, slot_art fonts + parallel downloads. Phase 7: checklist/rules/sign-off + pay lock in slot_design_steps.py, steps/mockup.js; mockup frame loop survives errors. Phase 6: maths in slot_design_steps.py (update_maths, freeze_maths with server replay, variant_from_design), mockup/sim_worker.js (sim, step-aware tune, sample), steps/maths.js, design.js designParams. Phase 5: sprites/sounds in slot_design_steps.py, steps/sprites.js, sounds.js; mockup theme colours (C.*), win animations, demoWin, design fonts via /slot-design-font/. Phase 4: features/bonuses/art slots/specs in slot_design_steps.py, steps/features.js, bonuses.js, artslot.js; mockup takes them. Phases 2-3: slots/variant.py (+ JSON variants), base.py tier defaults, slots_math.js makeVariant(pays, upgrades, features, strips), slot_design_steps.py (ladder, scene), steps/ladder.js, steps/scene.js, mockup/game.js + design.js. Phase 1: `slot_design_web/` (wizard.js, wizard.css, steps/concept.js, art.js, later.js), routes in app.py, migrations in `Design._migrate`.
- **Checked:** Phase 1: tests in test_slot_design.py; headless run of every Phase 1 control on the dev copy (one real FLUX Refine).
- **Questions for Mike (Phase 9):** free-spins scatter (tick Bonus or make one); theme brief; Value ladder order; background and logo; feature/bonus pictures (12 still Armadillo's) and names; frame, colours, fonts, cabinet; any own sounds; Maths auto-tune + freeze; sign off; floor spot (above or west of Armadillo's bank) and bank (Single, Double, Quad or Full); Install.
- **Rule:** the live server keeps each design in memory and saves over `design.json`, so data changes to a design
  are migrations in `Design.__init__` (applied on restart), never hand edits while it runs.
