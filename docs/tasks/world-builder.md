# World builder: rooms, blueprints, lobby, asset library

**Branch:** `task/world-builder` (worktree `.claude/worktrees/world-builder`, dev port 8672)
**Plan:** `~/.claude/plans/pasted-content-id-7584-up-to-zesty-thacker.md` (approved 2026-10-21)

## Goal
Replace the hand-built floor with a data-driven floor plan: rooms joined by doors and archways on one casino plan,
designed as blueprints in a new admin tab (grid editor: drag/rotate tables, slots, furniture, decor NPCs; walls,
floors, doors; NPC paths), previewed in the game, then published. The live casino starts with just a small lobby
(the new spawn); the old floor is kept as an unplaced "Classic" pair in the library (and the git tag `classic-floor`).
Furniture from LPC packs, categorised, plus uploads.

## Files
Server: new `plan.py`, `plan_catalogue.json`, `plan_classic.json`, `plan_web/`; changes `floor.py`, `casino.py`,
`npc.py`, `app.py`, `sounds.py`, `table_styles.py`, `maintenance.html`; removes `slot_banks.py`, `slot_banks_web/`,
`floor_map.json`. Client: `casino_floor.tscn/.gd` (hand-built nodes go), new `plan_builder.gd`, `plan_room.gd`,
`furniture.gd`, `PlanArt` autoload. Protocol v4. Tools: `plan_catalogue.gd` replaces `floor_map.gd`.

## Done when
- [x] Phase 0: Classic floor + pit kept as unplaced blueprints; tag `classic-floor`
- [x] Phase 1: server plan (draft/live/history, validation, publish, NPCs from the plan), tests
- [ ] Phase 2: client builds the world from the plan; lobby spawn; zones; preview mode
- [ ] Phase 3: admin Floor plan tab (plan view, blueprint editor, paths, problems)
- [ ] Phase 4: LPC furniture library, uploads, PlanArt
- [ ] `tools/dev.sh test` passes; docs updated; merged and live

## Handoff
- **State:** Phases 0 and 1 (server) done and committed on the branch. Next: Phase 2, the client builds the floor from `welcome.world` (the old hand-built floor still in casino_floor.tscn is now out of step with the server: do not merge before Phase 2). README "Floor" admin section and docs/games/README.md "The floor" still describe the old floor: rewrite them with Phases 2-3.
- **Changed:** `tools/plan_catalogue.gd` + `server/casino_server/plan_catalogue.json` (table/cabinet footprints).
- **Checked:** `tools/dev.sh test`: 876 pass (test_plan.py covers the plan).
- **Questions for Mike:** —
- **Gotcha:** headless Godot tools connect to the live server through the Net autoload unless
  `CASINO_SERVER_URL=ws://127.0.0.1:9/ws` is set.
