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
- `server/casino_server/admin_web/`: `index.html`, `theme.css` (tokens only), `base.css`, `shell.js`, `sections/*.js`,
  `fonts/` (Instrument Sans and JetBrains Mono, OFL), and the editors: `plan/`, `tables/` (with the renderer, its
  textures, fonts and geometry), `design/` (with the design-driven mockup).
- `app.py`: `/admin` and `/maintenance` serve it, `/admin-ui/` its files, `/admin/next` redirects to `/admin`.
- `slots/stats.py`, `store.py` (the `slot_stats` table), `tables/slot_machine.py`, `casino.py`.

## Done when
- [x] Shell, theme, Display menu
- [x] Settings, Players, Slots (+ per-machine stats), Sounds, NPCs
- [x] Tables: full-height three columns, kinds in the top bar
- [x] Floor plan: canvas fills its box, actions in the top bar, problems docked in the canvas
- [x] Slot design: steps rail, top-bar controls; Scene/Sprites/Mockup canvas pinned with controls beside it; Art as
      master and detail; Bonus games as list and detail; the other steps re-gridded
- [x] Mike signs off `/admin/next` (2026-10-22)
- [x] Swap: `/admin` and `/maintenance` serve `admin_web/`; the unchanged editor files moved across and the old page
      and modules (`maintenance.html`, `plan_web/`, `slot_design_web/`, `table_styles_web/`) deleted; the slot-art
      admin endpoints and their tests removed (the game's manifest and files stay); README updated
- [x] `tools/dev.sh test` passes

## Handoff
- **State:** done. The new page is the admin page on the live server.
- **Checked:** the full suite; a test that every `/admin-ui/` file the page names is served; Playwright on the dev
  instance through every section and the Slot design steps (no console errors, no failed requests), with the
  Tables designer and Floor plan drawn.
