# Betting UI overhaul

**Branch:** `main` (done 2026-10-23)

## Goal
Mike much prefers the betting UI in the Master Table mockup to the game's current one, and wants it to replace
the seated HUD at every card table. It's the next project after the Master Table (said 2026-10-22).

The reference is the mockup: https://claude.ai/artifact/GPAjSj5NTbXaN58X5hFzMN, source
`docs/master_table/mockup/index.html` (the `.hud` markup and CSS, `hud()`, the chip buttons and the hit test). What it
does differently from today's `SeatedBar` in `client/scenes/ui/hud.tscn` / `hud.gd`:
- **One bar at the foot of the screen over a dark fade**, not a panel. Balance and "On the felt" on the left, the chips
  in the middle, and the action buttons on the right.
- **The chips are the table's own chips**, drawn in its style (`ChipFace`) as round buttons, with a gold ring on the one
  picked.
- **The buttons:** Undo, Rebet, Ready, Stand up. Each shows its key (Space, Esc, P, F). The decision buttons (Play/Fold,
  Raise…) replace Undo/Rebet/Ready while a decision is open, and name the amount ("Play £25").
- **The info line** sits centred above the bar, with the countdown in gold ("Bets close in 8 · Ready when you are",
  "Play or fold? · 9", "Settling, third base first…").
- **Pills above the bar** for anything pending: "After this hand: Baccarat ✕", and a vote card ("Anna wants to switch
  to …  Switch / Keep playing · 10").
- A status chip top-left: the table's name and "n of 6 seated".

## Files
`client/scenes/ui/hud.tscn`, `hud.gd`, probably a new chip-button script using `ChipFace`, `casino_table.gd`'s hover and
countdown drawing. Every game's `seated_view()` feeds the bar. Today's Auto rebet, Clear, Paytable and the craps/roulette
extras need a home in the new bar.

## Done when
- [x] Mike signs off the new bar at a card table, then at Roulette and Craps (mockup, 2026-10-23)
- [x] Auto rebet, Paytable and the game-specific actions all still work
- [x] `tools/dev.sh test` passes

## Handoff
- **State:** built and live (2026-10-23): `scenes/ui/betting_bar.gd` replaces the HUD's SeatedBar. The mockup stays in
  `docs/betting_ui/mockup/` (https://claude.ai/artifact/ECYKm3w3qpQaFVgKmEY7EH). Checked with `tools/shot.py` at Three
  Card Poker (betting, Play/Fold, the result flash), Roulette and Craps on a dev instance.
- **Not done:** the slot screen keeps its own controls (Mike hasn't said); the dealer's speech bubble in the game is
  unchanged (the mockup's bigger one was the mockup's own).
