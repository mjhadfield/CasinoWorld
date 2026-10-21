# Table styles for the card tables

**Branch:** `task/table-styles` (worktree `.claude/worktrees/table-styles`)
**Plan:** `~/.claude/plans/i-would-like-to-twinkly-truffle.md`

## Goal
Better-looking card tables, built from swappable styles that can be placed per table as the casino grows. The
chip tray becomes part of the table instead of looking bolted on. The geometry, card positions and betting-spot
positions don't change. Roulette and Craps keep their current look and chips, but are decoupled so they can
take a style later.

## Files
- **Phase A (mockup):** `docs/table_styles/` and `tools/table_geometry.gd` only.
- **Phase B (build):** the eight card `*_felt.gd`, new `styled_felt.gd` and `chip_face.gd`, `card_shuffler.gd`,
  `card_shoe.gd`, `discard_rack.gd`, `jackpot_lights.gd`, `card_2d.gd`, `chip_stack_2d.gd`, `casino_table.gd`
  (and `styled()` in `rou_table.gd`/`crp_table.gd`), `casino_floor.gd`, a new `client/scripts/table_style.gd`, a
  new `server/casino_server/table_styles.py` with `table_styles_web/`, the admin page and `server/protocol.md`.
  `table_felt.gd` stays as it was: it's Roulette's and Craps' look.

## Done when
- [x] Mike picked his default (House) on the mockup, 2026-10-21
- [x] Built in the worktree. The layout audit output is identical before and after; Roulette and Craps code is
      untouched (TableFelt, rou_felt, crp_felt, the wheel and ChipButton are unchanged; their tables only say styled() false)
- [ ] Mike signs off in test, on the worktree's dev instance (8672/8673)
- [ ] `tools/dev.sh test` passes, merged, exported and restarted live

## Handoff
- **State:** built and running on the worktree's dev instance, waiting for Mike's test sign-off. Live is untouched.
- **Server:** `table_styles.py`, with House as the default (`HOUSE` = Mike's design) and grand/monte/deco/vegas
  built in. The API is `/api/table-styles` (+ `/styles/{id}`, `/tables`). It's sent in the welcome and in the
  `table_styles` broadcast. Tests are in `tests/test_table_styles.py`.
- **Admin:** the Tables tab loads `table_styles_web/designer.js` (UI) and `render.js` (the mockup's renderer, using
  the game's tiles and fonts).
- **Client:**
  - `scripts/table_style.gd` holds the styles. `StyledFelt` draws the table and every card felt extends it;
    `ChipFace` draws the chips.
  - `ChipStack2D.style`, `Card2D.back`, and the shuffler, shoe, rack and Jackpot lights read their table's
    `style()`. `CasinoTable.restyle()` runs on a change.
- **Assets:**
  - `tools/build_table_tiles.py` makes the tiles and copies the fonts for the designer.
  - `tools/table_geometry.gd` writes the designer's and the mockup's geometry.json.
- **Testing on dev:**
  - Export to `.dev/web` with `godot --export-release Web ../.dev/web/index.html` from client/.
  - Run `CASINO_WEB_DIR=$PWD/.dev/web tools/dev.sh server`: the game is on https://<host>:8673/, the admin on http://<host>:8672/admin#tables.
- **Going live:** merge `task/table-styles`, then `tools/dev.sh test`, `tools/dev.sh export` and
  `tools/dev.sh restart`. House shows on every card table at once.
