# Betting UI overhaul

**Branch:** `main` (not started)

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
- **On the felt:** the spot under the pointer gets a breathing gold ring when you can bet on it. A felt countdown pill
  shows at the table's `countdown_pos()`. Right-click takes a chip off.
- A status chip top-left: the table's name and "n of 6 seated".

## Files
`client/scenes/ui/hud.tscn`, `hud.gd`, probably a new chip-button script using `ChipFace`, `casino_table.gd`'s hover and
countdown drawing. Every game's `seated_view()` feeds the bar. Today's Auto rebet, Clear, Paytable and the craps/roulette
extras need a home in the new bar.

## Done when
- [ ] Mike signs off the new bar at a card table, then at Roulette and Craps
- [ ] Auto rebet, Paytable and the game-specific actions all still work
- [ ] `tools/dev.sh test` passes

## Handoff
- **State:** not started; this note only.
- **Questions for Mike:** does it replace the HUD at Roulette, Craps and the slot screen too, or only at the card
  tables? Which parts he likes most (the chips, the layout, the info line, the felt highlight), in case some of it
  should stay as it is.
