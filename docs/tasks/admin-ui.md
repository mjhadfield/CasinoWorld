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
- [ ] Tables: full-height three columns, kinds in the top bar
- [ ] Floor plan: canvas fills its box, actions in the top bar, problems docked in the canvas
- [ ] Slot design: steps rail, top-bar controls; Scene/Sprites/Mockup canvas pinned with controls beside it; Art as
      master and detail; Bonus games as list and detail; the other steps re-gridded
- [ ] Mike signs off `/admin/next`
- [ ] Swap:
  - `/maintenance` and `/admin` serve `admin_web/`
  - move the unchanged editor files across, then delete the old page and modules
  - remove the slot-art admin endpoints (`PUT`/`DELETE /api/slots/art/...`, uploads) and their tests
  - update the README
- [ ] `tools/dev.sh test` passes

## Handoff
- **State:** shell and the five small sections done and committed. Next: Tables, Floor plan, Slot design.
- **Checked:**
  - Playwright on the dev instance (`tools/dev.sh server`, port 8670) at 2560×1440: every section fits the window
    (scrollHeight 1440), no console errors.
  - The check script is in the session scratchpad (`next/check.py`); it's easy to rewrite.
- **Questions for Mike:** none yet.
