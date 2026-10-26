# Table limits and the Limits sign

**Branch:** `main`

## Goal
Every card table (the 9 card games and the Master Table) gets a minimum and maximum for its main bet and its side
bets, set per table on the Floor plan, shown on a second sign on the felt (top right, mirroring the jackpot sign) in
one of four designs picked by the table style. Roulette and Craps keep their fixed limits.

Decided with Mike (2026-10-26): the design is a table style choice (`limitsSign`, beside `jackpotSign`); defaults
Main £5–£500, Side £1–£50; NPCs bet within the limits and won't sit where they can't cover the minimum.
Plan: `~/.claude/plans/minimum-maximum-bets-per-table-nifty-pine.md`.

Mockup: https://claude.ai/artifact/4eKprTKuiJ6ivpSd8LXuFW, source `docs/limits_sign/mockup/` (a copy of
`admin_web/tables/render.js` with `limitsSign()` added, plus the House and preset designs in `styles.json`).
The four designs are `plaque` (brass plaque), `tent` (acrylic tent), `digital` and `deco` (deco frame). Drawn in the
jackpot sign's 220-unit mock space but scaled to 32 table units (the jackpot sign is 40): Mike asked for it smaller.

## Files
`server/casino_server/plan.py`, `tables/base.py` (+ the card tables' `PRIMARY_SPOTS`), `casino.py`, `npc.py`,
`table_styles.py`, `admin_web/tables/render.js`, `admin_web/plan/plan.js`, `client/scenes/table/limits_sign.gd` (new),
`casino_table.gd`, `master_swap.gd`, `client/scenes/world/plan_room.gd`, `client/scripts/table_style.gd`,
`tools/table_geometry.gd`, `tools/layout_audit.gd`, tests and docs.

## Done when
- [ ] Mike signs off the mockup (designs, place, Floor plan fields, how the limits play)
- [ ] Server: limits on the plan, checked on bets, handed back under the minimum, NPCs fit them
- [ ] Table style `limitsSign` + the designer's control; the client's LimitsSign on every card table
- [ ] Layout audit: the sign clear of everything on all 10 layouts
- [ ] `tools/dev.sh test` passes; docs updated

## Handoff
- **State:** mockup published, waiting for Mike's sign-off. Nothing in the game changed yet.
- **Changed:** `docs/limits_sign/mockup/` and this file.
- **Checked:** the mockup renders with no console errors (one Playwright look).
- **Questions for Mike:** which design House uses (the mockup pairs House with the brass plaque); anything to change in
  the designs or the rules listed on the mockup.
