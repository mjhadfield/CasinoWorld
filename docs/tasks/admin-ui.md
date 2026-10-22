# The new admin page

**Branch:** `main`

## Goal
A new desktop-only admin page, designed for 1440p, replaces `/maintenance` (`maintenance.html`). It's black/grey/purple
and themed through tokens, and editors keep their preview in view. Mike signed off a mockup
(https://claude.ai/artifact/4icwz9cA1Wi3Xt9kEbn4ej) and chose:
- the Amethyst (default) and Graphite skins
- Compact (default) and Comfortable densities
- a collapsible menu with labels
- a Display menu in the top bar

It's built side by side at `/admin/next` and swaps in once Mike signs it off.

Also: Slots › Art is dropped (Armadillo's art stays as it is; Mike will make it a Slot design project later), and
Slots shows per-machine figures (`slots/stats.py`).

## Files
- `server/casino_server/admin_web/`:
  - `index.html`, `theme.css` (tokens only), `base.css`, `shell.js`, `sections/*.js`
  - `fonts/` (Instrument Sans and JetBrains Mono, OFL)
  - the copies of the three editors, being reworked: `plan/`, `tables/`, `design/`
- `app.py`: the `/admin/next` and `/admin-ui/` routes, and `/api/slots` `machines`.
- `slots/stats.py`, `store.py` (the `slot_stats` table), `tables/slot_machine.py`, `casino.py`.
- The old page and its modules (`maintenance.html`, `plan_web/`, `slot_design_web/`, `table_styles_web/`) stay
  untouched until the swap. The editors are **copied** into `admin_web/` and changed there. A copied module imports
  any file it doesn't change from the old URL (e.g. `/slot-design-ui/mockup/game.js`).

## Done when
- [x] Shell, theme, Display menu
- [x] Settings, Players, Slots (+ per-machine stats), Sounds, NPCs
- [x] Tables: full-height three columns, kinds in the top bar
- [x] Floor plan: canvas fills its box, actions in the top bar, problems docked in the canvas
- [x] Slot design: steps rail, top-bar controls; Scene/Sprites/Mockup canvas pinned with controls beside it; Art as
      master and detail; Bonus games as list and detail; the other steps re-gridded
- [ ] Mike signs off `/admin/next`
- [ ] Swap:
  - `/maintenance` and `/admin` serve `admin_web/`
  - move the unchanged editor files across, then delete the old page and modules
  - remove the slot-art admin endpoints (`PUT`/`DELETE /api/slots/art/...`, uploads) and their tests
  - update the README
- [ ] `tools/dev.sh test` passes

## Handoff
- **State:** every section is built and live at https://192.168.0.66:8661/admin/next (the live server was restarted
  for the routes and the slot figures). It's waiting on Mike's review, then the swap (Done when, above).
- **Checked:**
  - Playwright on the dev instance at 2560×1440 and 1920×1080: every section and every Slot design step fits the
    window, with no console errors.
  - Behaviour spot checks:
    - Art: tile picks the card; Prompts dialog
    - step status toggle
    - Bonus games: row picks its settings
    - Tables: kind switch
    - NPC save
    - sound Use and Reset
    - jackpot meter save
    - Display skin and density
    - menu collapse
  - Read-only look at the live page with the Pirates design.
- **Known:**
  - The live floor is lobby-only, so Slots › Machines is empty until cabinets are placed and played.
  - Machine figures count from the restart on 2026-10-22.
- **Questions for Mike:** whatever the review turns up.
