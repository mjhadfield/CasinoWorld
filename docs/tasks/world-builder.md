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
- [x] Phase 2: client builds the world from the plan; lobby spawn; zones; preview mode
- [ ] Phase 3: admin Floor plan tab (plan view, blueprint editor, paths, problems)
- [ ] Phase 4: LPC furniture library, uploads, PlanArt
- [ ] `tools/dev.sh test` passes; docs updated; merged and live

## Handoff
- **State:** Phases 0-2 committed on the branch: the server plan, and the client building the floor from it
  (PlanRoom/PlanDoor, zones, nav paths for taps, ?preview=). Next: Phase 3, the admin Floor plan tab
  (`server/casino_server/plan_web/`, tab id `plan`, replacing the old Floor tab in maintenance.html which still
  loads the deleted banks.js). README's admin "Floor" section and docs/games/README.md "The floor" still describe
  the old floor: rewrite with Phase 3. Furniture (`a:` items) needs Phase 4 (PlanArt is a stub).
- **Changed:** `tools/plan_catalogue.gd` + `server/casino_server/plan_catalogue.json` (table/cabinet footprints).
- **Checked:** `tools/dev.sh test`: 876 pass (test_plan.py covers the plan). shot.py on the dev instance: the
  lobby and its door; `dev.sh server --classic`: tables, NPCs, a tap-walk through the archway into the pit; a
  draft room's preview.
- **Questions for Mike:** —
- **Gotcha:** headless Godot tools connect to the live server through the Net autoload unless
  `CASINO_SERVER_URL=ws://127.0.0.1:9/ws` is set.
