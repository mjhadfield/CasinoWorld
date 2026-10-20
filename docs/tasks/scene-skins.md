# Scene skins: a designed look per slot (LCARS first)

**Branch:** `main`

## Goal
The Scene step designs the whole look of a slot's screen as a **skin** (palette, glass, a shape per part, free decor,
fonts, screen labels), drawn the same by the wizard mockup and the Godot client. Claude designs bespoke skins in a
Claude Code session from Mike's brief. Voyager gets an LCARS skin, the first one. The full plan, agreed with Mike on
2026-10-20, is `~/.claude/plans/upgrade-to-slot-builder-valiant-salamander.md`.

## Files
- `client/scenes/slots/slot_screen.gd`, `client/autoload/slot_art.gd`
- `server/casino_server/slot_design_web/mockup/game.js`, `mockup/design.js`, `steps/scene.js`, `steps/sprites.js`,
  `steps/features.js`, `wizard.css`
- `server/casino_server/slot_design_scene.py` (new), `slot_design_steps.py`, `slot_design_art.py`, `slot_design.py`,
  `slot_design_build.py`, `app.py`
- `docs/slots/scenes.md` (new), `tools/scene.py` (new)

## Done when
- [ ] Phase 1: every part drawn through a skin object in both renderers; Classic looks exactly as before
- [ ] Phase 2: skins stored, validated, migrated (frame/deck + Sprites colours/fonts), built into `theme.skin`
- [ ] Phase 3: the LCARS family in both renderers (elbows, pills, tab-pills, glass, readouts)
- [ ] Phase 4: Scene step UI (skin picker, Look, Parts, Decor, Brief for Claude); Sprites keeps win animations + cabinet; feature names on Features
- [ ] Phase 5: Logo: Render, Generate, Stylise lettering
- [ ] Phase 6: `docs/slots/scenes.md` + `tools/scene.py` (shot, put)
- [ ] Phase 7: Voyager's LCARS skin saved as a draft on the live board
- [ ] `tools/dev.sh test` passes

## Handoff
- **State:** starting Phase 1.
- **Changed:**
- **Checked:**
- **Questions for Mike:**
