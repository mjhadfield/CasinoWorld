# Building a table

How the tables are drawn and laid out in the client. The rules of each game are in `docs/games/`.

## The look

The tables are drawn in code, as is the room (`scenes/world/room.gd`), so they stay sharp at any zoom.

**The card tables are drawn in their table style.** A style is a design made on the admin page's Tables tab:
- the felt (colour, velvet or woven grain, how much darker it gets towards the rail) and a border line
- the rail (one of five woods, a leather armrest or leather all round, a brass/gold/chrome bead where it meets the felt)
- the chip tray (a well cut into a dealer's ledge, or sunk in where it's always been, in three finishes)
- the printing's font and colours, and the betting spots' artwork
- the Jackpot disc, the shuffler, shoe and discard rack, card backs and chips

Every card table uses the default style, House (Mike's pick on the mockup, `docs/table_styles/`), unless the
Tables tab places another on it.

How it's put together:
- **The styles** live on the server (`table_styles.py`) and come in the welcome; `scripts/table_style.gd`
  (`TableStyle`) holds them.
- **The table** is painted by `scenes/table/styled_felt.gd` (`StyledFelt`), which each card game's felt extends.
- **The admin designer's renderer** (`server/casino_server/table_styles_web/render.js`) draws the same way, with
  the same tiles and fonts, so what's designed is what the floor shows.
- **A style changes looks only.** Every spot, card and machine stays where the game puts it. `tools/layout_audit.gd`
  doesn't change with a style, and the designer's "Fixed layout" draws those places over any design.
- **The dealer's ledge** replaces the felt behind the dealer's cards with the rail, swept across the bay with
  fillets into the dealer's edge (`StyledFelt.tongue()`). The well is cut into it inside `tray_rect()`, so chips
  still fly to and from `tray_pos()`. The collision and outline are unchanged.
- **Tiles and fonts:**
  - The wood, leather and felt tiles in `client/assets/tiles/table/` come from Poly Haven (CC0), made by
    `tools/build_table_tiles.py`. The leather and felt ones are "shades": white where the scan is lighter, black
    where darker, laid over the colour. Their import settings make mipmaps, so they don't shimmer at a distance.
  - The fonts are Cinzel, Cormorant SC, Josefin Sans and Montserrat, all OFL. Each is a static instance with its
    overlapping outlines merged (`fonttools varLib.instancer ... --remove-overlaps`), because MSDF text draws
    overlaps as specks.
  - Every outside asset is recorded in `docs/table_styles/LICENSES.md`.

**Roulette and Craps keep Mahogany & Brass** (`scenes/table/table_felt.gd`, `TableFelt`, which StyledFelt extends
for its helpers). `CasinoTable.styled()` is false for them, so they take no style and their chips stay the game's
own. That look is a wood rail with a brass bead, on craps leather-padded on the dealers' side (with a faint fine
grain from `assets/tiles/leather_grain.png`, drawn by `TableFelt._padding()`), crimson felt, and cream printing in
Cinzel.

In the game, a felt isn't drawn straight. `FeltCache` paints it into a texture at the screen's resolution and
shows that (docs/performance.md), so a felt's `paint()` (not `_draw()`) is its drawing. The felt's `_table()` is
the table, because the cache paints with a copy of the felt that lives in a SubViewport. Its `queue_redraw()`
repaints the texture.

## Shared pieces

Every game's table is built from shared, reusable pieces, so a new game mostly adds its own layout and round:
- **`scenes/table/floor_game.gd` (`FloorGame`)** is what every table and slot cabinet on the floor is.
- **`scenes/table/casino_table.gd` (`CasinoTable`)** is the base every card table extends: the swept-bay shape
  and collision, seats and chairs, the dealer, chips and cards on the felt, Jackpot lights, the animation
  queue, and the hooks a game fills in (its spots, HUD actions and events). Its `seats` export and the
  Seat0..n markers (editable in the editor) set the seat count and spacing. A seat's column of spots and its
  cards line up above its marker.
- **`scenes/table/styled_felt.gd` (`StyledFelt`)** draws a card table in its style; a game's felt only lays
  out its spots, with `spot()` (a shape, its ring colour, its words), `circle()`, `big()`, `card_box()` and
  `jackpot_disc()`. **`chip_face.gd` (`ChipFace`)** draws chips in a style (`ChipStack2D.style`); the card tables
  give every stack, card (`Card2D.back`) and machine their style, and `CasinoTable.restyle()` redraws them all
  when the styles change.
- **`scenes/table/table_felt.gd` (`TableFelt`)** draws the Mahogany & Brass table for Roulette and Craps. The dealer's chip tray (`_chip_tray()`) is built into the table, not sat on it: its wood frame is
  flush with the rail and casts no shadow, the felt's brass bead runs round its edge where it meets the felt, and
  the channels are a well sunk into it (shadowed under its back wall, lit along its front). Craps has no
  tray piece: its rail is a deeper ledge across the floor of the boxman's bay (`CrapsTable.LEDGE`, part of
  `CrapsTable.shape()`), padded in leather like the rest of its dealers'
  side, and the rack's well (`_tray_well()`) is cut straight into it with a brass rim. `TableFelt.edge_chip()` draws one chip on its edge in a channel (the dealer's chip tray, the
  craps chip rail). **`felt_cache.gd` (`FeltCache`)** shows it as one picture.
- **Chairs** are drawn by `scripts/seating.gd`, under the sitter in the table's own `_draw` and over them in a
  `ChairBack`. A free chair breathes (redraws) only on screen and on its table's own frame
  (`FloorGame.breathes_now()`). Each way of drawing a chair is built once and kept in its style (`Seating.Ink`).
- **`scenes/table/card_shoe.gd` (`CardShoe`)** is a dealing shoe with a cut card, in tinted acrylic or wood. Its stack shrinks as cards
  leave its `mouth_point()`, and the cut card is set aside once it's out.
- **`scenes/table/card_shuffler.gd` (`CardShuffler`)** is an in-table automatic shuffler (brushed metal, gloss with an LED strip, or wood and brass). Hands come out of
  its front slot (`slot_point()` to `delivery_point()`) and used cards go into its intake
  (`intake_point()`). Call `deliver()` as each hand comes out and `shuffle(seconds)` after feeding it. Put it
  in a layer drawn above the cards.
- **`scenes/table/discard_rack.gd` (`DiscardRack`)** is a discard holder (clear, tinted or wood-backed). `slot(n)` says where
  the nth discard lands, face down and sideways. It draws its own stack from `count` (so a whole shoe's worth
  costs nothing), and `take_all()` empties it for the shuffler. Put it in a layer drawn below the cards.

## Layout rules

Every card table follows the same alignment rules:
- **Equipment:** the shuffler (or shoe) and discard rack sit inside the felt's cream border, level with the
  dealer's cards.
- **Dealer's cards:** they sit clear of the chip tray, as a separate thing on the felt (`DEALER_Y` -106.5, about 6
  units below the tray; the audit prints the gap).
- **Player cards:** their bottom edge sits 2 units inside the front border.
- **Betting rows:** stacked evenly just above the cards.
- **Winnings that can't go beside a stake** (the cards are right below) go as a second stack leaning on it.
- **Title:** centred in the band between the dealer's cards and the first row of bets (`title_y()`).
- **Countdown:** centred under the title where that band is roomy, otherwise level with it at the right-hand
  end (`countdown_pos()`).

## Turned tables

A table on the floor can be turned (`rotation` on its instance in `casino_floor.tscn`). For example, the far row of
the Blackjack pit is set to `PI`, so its dealers stand with their backs to the pit. The table needs nothing of its
own for this:
- **To a walker** it's drawn as seen from that side. The felt's printing is upside down, and the players face
  you from behind it. The dealer has their back to you and stands on the floor at the felt's edge
  (`dealer_near_pos()`), in front of the table, not in the bay behind it. The chairs are drawn upright (`FloorGame.draw_chair`).
- **Things placed about a sitter** follow the screen, not the table, because the sitter is always upright.
  That covers their chair, the ring round whoever's thinking and their Ready tick. They use
  `FloorGame.on_screen(offset)`, and `screen_turn()` says which way up the table shows right now. A table
  redraws, and moves its dealer, when that changes (`CasinoTable._turned_on_screen`).
- **Sitting there** turns the whole floor (`World` in `casino_floor.tscn`) about the table, so the table is the
  right way up. Standing turns it back (`casino_floor.gd`, `_camera_to`'s `turn`). World Y-sorts, and Godot sorts
  in the turned frame, so the dealer goes behind the felt again and everyone overlaps the right way.
- **People stay upright.** `Avatar` keeps itself at no rotation on screen. Its `facing` is in its parent's frame
  (a dealer faces "down" across their own table), and the sprite shows that direction as the screen sees it.
  `FloorGame.world_dir()` turns a table's directions (`sit_facing`) into the floor's frame.
- **Positions** the floor and server use are in World's frame. Use `to_global()` for points on a table, never
  `global_position + offset`, as `focus_point()` does.

`tools/floor_map.gd` measures turned tables too. Their dealer's head is over the felt, so it adds nothing above
them.

## The layout audit

`tools/layout_audit.gd` measures all of this for every card table, headless, in a few seconds. For Roulette,
it checks that the wheel, float, chip hole, title and layout are on the felt and clear of each other, and
that the sign stands clear of the table. Run it before reaching for a screenshot:

```fish
cd client; godot --headless --path . -s ../tools/layout_audit.gd     # LAYOUT_ONLY=uth for one table
```
