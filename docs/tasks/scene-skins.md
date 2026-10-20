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
- [x] Phase 1: every part drawn through the skin in both renderers; Classic looks exactly as before (Armadillo shot 2026-10-20)
- [x] Phase 2: skins stored, validated, migrated (frame/deck + Sprites colours/fonts), built into `theme.skin`
- [x] Phase 3: the LCARS family in both renderers (elbows, pills, tab-pills, glass, readouts)
- [x] Phase 4: Scene step UI (skin picker, Look, Parts, Decor, Brief for Claude); Sprites keeps win animations + cabinet; feature names on Features
- [x] Phase 5: Logo: Render, Generate, Style the lettering
- [x] Phase 6: `docs/slots/scenes.md` + `tools/scene.py` (brief, fresh, shot, put)
- [ ] Phase 7: Voyager's LCARS skin saved as a draft on the live board
- [x] `tools/dev.sh test` passes (slot design 50; full suite 2026-10-20, one flaky craps NPC test passes alone)

## Handoff
- **State:** Phases 1-6 done, committed and live (server restarted, client exported). Phase 7: Mike's brief and his
  LCARS phone mockup are filed on Voyager's Scene step; a background (3 takes) and a styled VOYAGER logo (3 takes)
  were queued on the live board; the Voyager LCARS skin goes on with `tools/scene.py put voyager <skin.json>`.
- **Changed:** slot_design_scene.py (new: skins, Brief, migration, look), slot_design_steps.py (scene view moved,
  sprites read the scene, queue_logo, feature names), slot_design.py (migration, logo jobs), slot_design_build.py
  (theme.skin, bg_glass, patched fonts, feature names), slot_design_art.py (web_font, logo prompts), app.py (skin,
  brief and logo routes); mockup game.js/design.js; steps scene.js (rewritten), sprites.js, features.js; client
  slot_screen.gd, skin_draw.gd (new), slot_art.gd (font fallback); tools/scene.py; docs/slots/scenes.md.
- **Checked:** tests; mockup shots (Scene, trail bonus) on dev; the Godot client drawing a LCARS skin (dev Star Trek
  build) and Armadillo unchanged; the live Scene page.
- **Questions for Mike:** pick the background and logo takes; tweak or keep the LCARS words (ENGAGE, TACTICAL
  SUBSYSTEMS, BEAM OUT, ALL HANDS STAND BY); Voyager still needs Build for the game itself to show it.
