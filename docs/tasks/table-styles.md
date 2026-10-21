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
- **Phase B (build):** `client/scenes/table/table_felt.gd` and every `*_felt.gd`, `card_shuffler.gd`,
  `card_shoe.gd`, `discard_rack.gd`, `jackpot_lights.gd`, `card_2d.gd`, `chip_stack_2d.gd`, a new
  `classic_look.gd`, a new `client/scripts/table_style.gd`, a new `server/casino_server/table_styles.py`, the
  admin page and `server/protocol.md`.

## Done when
- [ ] Mike signs off a set of styles and a chip-tray option on the mockup
- [ ] Built in the worktree. The layout audit output is identical before and after, and Roulette and Craps shots
      are pixel-identical.
- [ ] Mike signs off in test, on the worktree's dev instance
- [ ] `tools/dev.sh test` passes, merged, exported and restarted live

## Handoff
- **State:** Phase A is done and waiting for Mike's review. Nothing has been built in the game, and live is untouched.
- **Mockup:** https://claude.ai/artifact/QhfdafyZkdYpyE3pH2h9QC (source in `docs/table_styles/mockup/`).
  - Presets: Grand Mahogany, Monte Carlo, Midnight Deco and Modern Vegas.
  - Every component is swappable.
  - A ledge vs sunk tray comparison.
  - A "Fixed layout" overlay.
  - Saved designs go to the artifact db collection `designs`: read them with ArtifactData `list`. Comments are
    on the artifact.
- **Geometry:** `docs/table_styles/mockup/geometry.json` comes from `tools/table_geometry.gd`
  (`cd client && CASINO_SERVER_URL=ws://127.0.0.1:1/ws godot --headless --path . -s ../tools/table_geometry.gd`).
  Rerun it if a table's layout changes.
- **The mockup's ledge:** the felt outline replaced behind the dealer's cards by `tongue()`. It is 38 wide each
  side of centre, with 9-radius fillets into the dealer's edge and 4-radius front corners, and its front sits at
  the tray's front (-122.39). The well is x -35.5..35.5, y -132.2..-124.3.
- **Textures:** Poly Haven CC0, processed by a scratch tile script. Its recipe (resize to 1024², then 512²;
  high-pass greyscale detail maps for leather and felt) is in `docs/table_styles/LICENSES.md`.
- **Questions for Mike:** which preset(s) to build first, ledge or sunk, any component changes, and whether
  styles are picked per table on the admin page (the plan's default).
