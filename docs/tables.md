# Building a table

How the tables are drawn and laid out in the client. The rules of each game are in `docs/games/`.

## The look

The tables are drawn in code, as are the rooms (`scenes/world/plan_room.gd`, built from the floor plan), so they stay sharp at any zoom.

**Every table is drawn in its table style.** A style is a design made on the admin page's Tables tab, which has
a tab for each kind of table, because they have different parts:
- **Card Games:** the felt (colour, a woven or velvet cloth, how much darker it gets towards the rail) and a border
  line; the rail (one of five woods, a leather armrest along the players' straight front or leather all round, a brass/gold/chrome bead where it
  meets the felt); the chip tray (a well cut into a dealer's ledge, or sunk in where it's always been, in three
  finishes); the printing's font and four colours (ink for titles, rules and follow-up bets like Play, Raise and the
  Mississippi streets; primary for the bet every hand must have: the Ante, Blackjack's bet, Hold'em's Blind, Let It
  Ride's three, Baccarat's Banker box and hand; side for the bonus bets, Baccarat's Tie and Dragons; and the trim for
  the gilt, double and deco borders, the House chips and the Master Table's crest; `StyledFelt.role_colour()`), and
  the betting spots' artwork and glow colour; the Jackpot disc, the shuffler,
  shoe and discard rack; the card backs (a design, its colour, and the card's colour round it) and fronts (Classic,
  Jumbo index, Vintage or Minimal, in red and black or four colours); the chairs' frame metal and upholstery; and
  chips.
- **Roulette:** the felt (with the fine grain it's always had as a fourth cloth), a border line, the rail (bare
  wood or leather all round), the printing's font, ink and accent, the red, black and zero colours (on the layout
  and the wheel's pockets), the float (wood frame, brushed steel or under a smoked lid) and the wheel (its bowl's
  wood and its metal: frets, turret, rims and the chip hole's rim), and the chairs' colours.
- **Craps:** the felt, the rail (bare wood, leather on the dealers' side, or all round), the printing's font, ink,
  gold (6 and 8, Field, Horn) and red (Come, Big 6/8, Seven, Any Craps), the rubber walls, the chip rack and the
  dice (on the table and the sign).

Each kind has its own styles and its own default, House, unless the Tables tab places another on a table. The
card tables' House is Mike's pick on the mockup (`docs/table_styles/`); Roulette's and Craps' House is how they
looked before they took styles (Mahogany & Brass: crimson felt with a fine grain, a mahogany rail, a brass bead,
cream Cinzel printing). Roulette's and Craps' chips stay the game's own whatever the style.

How it's put together:
- **The styles** live on the server (`table_styles.py`, `KINDS`) and come in the welcome, every kind at once;
  `scripts/table_style.gd` (`TableStyle`) holds them. `CasinoTable.style_kind()` says which kind a table takes,
  and `styled()` whether its chips, cards and card machines follow a card table's style (false for Roulette and
  Craps).
- **The table** is painted by `scenes/table/styled_felt.gd` (`StyledFelt`), which each card game's felt extends,
  and so do `rou_felt.gd` and `crp_felt.gd`: they give their own outline (`_grown()`), rail width, middle and
  padding area, and draw their own float or rack (`float_tray()`) and printing. `RouletteWheel.restyle()` and
  `CrapsDice.tone` take the wheel's and the dice's colours.
- **The admin designer's renderer** (`server/casino_server/admin_web/tables/render.js`) draws the same way, with
  the same tiles and fonts, so what's designed is what the floor shows. It draws Roulette and Craps (and the
  wheel) from their real geometry too.
- **A style changes looks only.** Every spot, card and machine stays where the game puts it. `tools/layout_audit.gd`
  doesn't change with a style, and the designer's "Fixed layout" draws those places over any design.
- **The dealer's ledge** replaces the felt behind the dealer's cards with the rail, swept across the bay with
  fillets into the dealer's edge (`StyledFelt.tongue()`). The well is cut into it inside `tray_rect()`, so chips
  still fly to and from `tray_pos()`. The collision and outline are unchanged.
- **The border line** is one unbroken line round the felt as you see it: round the ledge, or round the front of the
  sunk tray (`StyledFelt.border_edge()`, the felt less the tray, inset). The designer takes the same lines from
  `geometry.json` (`border`), which `tools/table_geometry.gd` writes for every inset a border uses.
- **Tiles and fonts:**
  - The wood, leather and felt tiles in `client/assets/tiles/table/` come from Poly Haven (CC0), made by
    `tools/build_table_tiles.py`. The leather and felt ones are "shades": white where the scan is lighter, black
    where darker, laid over the colour. Their import settings make mipmaps, so they don't shimmer at a distance.
    The fine grain is the game's own `assets/tiles/felt_grain.png` (`tools/build_art.py`).
  - The fonts are Cinzel, Cormorant SC, Josefin Sans and Montserrat, all OFL. Each is a static instance with its
    overlapping outlines merged (`fonttools varLib.instancer ... --remove-overlaps`), because MSDF text draws
    overlaps as specks.
  - Every outside asset is recorded in `docs/table_styles/LICENSES.md`.

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
  give every stack, card (`Card2D.look`) and machine their style, and `CasinoTable.restyle()` redraws them all
  when the styles change.
- **`scenes/table/table_felt.gd` (`TableFelt`)** is the base every felt extends: it puts the drawing in
  FeltCache and holds the shared helpers. `TableFelt.edge_chip()` draws one chip on its edge in a channel (the
  chip trays, the craps chip rail). The chip trays are built into the table, not sat on it: Roulette's float
  (`StyledFelt.float_tray()`) has a frame in the rail's wood, flush with the rail, the bead running round its edge
  where it meets the felt, and its channels are a well sunk into it (shadowed under its back wall, lit along its
  front). Craps has no tray piece: its rail is a deeper ledge across the floor of the boxman's bay
  (`CrapsTable.LEDGE`, part of `CrapsTable.shape()`), and the rack's well is cut straight into it, rimmed with the
  bead. **`felt_cache.gd` (`FeltCache`)** shows it as one picture.
- **The spot glow** (`scenes/table/spot_glow.gd`, `SpotGlow`) is the light round the local player's spots while
  they can bet: first only the primary bets (`CasinoTable.primary_spots()`, the main bet by default; Baccarat's
  Banker and Player, Hold'em's Ante and Blind, Let It Ride's three), then, once one of them has chips on it, the
  side bets still empty (`glowing_spots()`). It follows each spot's printed outline (`spot_shape()`: a circle of
  `SPOT_R` unless the game gives another, such as the Three Card Ante's diamond or Baccarat's boxes, which the felts
  also print from), with a breathing halo and a lit edge, in the style's `glow` colour. A
  click anywhere on a spot's shape lands on it. The designer's "Spot glow" plays the same (`drawGlow()` in render.js,
  from the shapes and primaries `tools/table_geometry.gd` writes). Roulette and Craps don't glow (`pulse_spots()`).
- **Chairs** are drawn by `scripts/seating.gd`, under the sitter in the table's own `_draw` and over them in a
  `ChairBack`. A free chair breathes (redraws) only on screen and on its table's own frame
  (`FloorGame.breathes_now()`). Each way of drawing a chair is built once and kept in its style (`Seating.Ink`).
  The chair's shape and the sit come from the seating style (Settings); a card table's or Roulette's chairs take
  their frame and upholstery from its table style (`FloorGame.chair_colours()`, `Seating.style(table_id, colours)`),
  and the designer draws the same chair (`seatChair()` in render.js, ported from `docs/seating/mockup.html`).
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

## The Master Table

A Master Table (docs/games/master_table.md) is drawn as whichever game it's playing: the floor swaps that game's own
table scene in, with the same id, place and turn (`casino_floor.gd`, `_master_node`). Blank, it's `master_table.tscn`
(`MasterTable`, no spots), and `master_felt.gd` prints its crest. `CasinoTable.is_master` marks either kind; clicking
the dealer while sitting there emits `dealer_clicked`.

The change animates over the felt (`master_swap.gd`, `MasterSwap`):
- **The felts:** a felt's `layer` paints all of it, just the table under the printing (`"base"`), or just the printing
  (`"print"`); `FeltCache` passes it on to its painter. The new table shows its base while `MasterSwap` paints each
  game's printing once into a texture and moves them over it.
- **The sweep's pieces:** the printing is cut into the band along the dealer's side, above the highest spot, and a
  column for each seat.
- **The old table** stays as a ghost until it's done, showing only its machines and anything still moving on its felt.
  Machines both tables have glide across; the rest slide on or off.
- **The chairs:** when the seat count changes, the new table's Seat markers start where the old chairs were and slide
  home with their sitters (`move_sitters()`), and the chair that goes fades.

The plan catalogue measures the blank scene and adds the five-seat table's stands and chairs (`stands5`, `chairs5`,
from Let It Ride). The admin renderer draws the crest as layout `mt` (`geometry.json` has it from
`tools/table_geometry.gd`).

## Turned tables

A table on the floor can be turned (its `rot` on the floor plan): upright, a quarter turn either way (90, 270) or
upside down (180). `plan_catalogue.json` says which turns each game takes, and every table takes all four. For
example, the far row of the classic Blackjack pit is upside down, so its dealers stand with their backs to the pit.
Most of it lives in `FloorGame` and `CasinoTable`, so a card table needs nothing of its own:
- **To a walker** it's drawn as seen from that side: the felt's printing upside down or on its side. The dealer
  stands on the floor at the felt's edge (`dealer_near_pos()`), not in the bay with the felt hiding their feet. At
  90 the dealer's side is to our right, at 270 to our left; on its side (`FloorGame.sideways()`) the dealer draws
  over the rail at z 1, as a sitter does, since the felt's own place in the Y-sort can be either side of their feet.
  The chairs are drawn upright (`FloorGame.draw_chair`), and they come in towards the table
  (`CasinoTable.chair_tuck()`). Chairs and sitters are drawn upright from their feet, so at an upright table they
  rise towards it and the sitter leans over the rail. Past an upside-down table's far side they'd rise away from it
  and leave a gap, so there `chair_pos()` brings them in until the feet are 8.5 behind the rail (`tuck_far()`), and
  on its side until a stool's edge is just clear of it (`tuck_side()`). Craps' standers come in the same way.
  `seat_pos()` is the seat itself: `stand_pos()`, the server's seat points and NPC walks are measured from it, so
  nothing moves on the floor's map, only on screen. When the way up changes, the chairs move and everyone sitting
  moves with them (`FloorGame.move_sitters()`; `Seating` keeps `sitters` and puts a sitter in the chair's latest place
  as a sit-down ends). Seen from in front, a stool's back hides its brass post.
- **Light** comes from the top of the screen whichever way up a table shows: its shadow on the carpet falls down the
  screen and its rail's crown is lit along the top (`TableFelt._lit()`; the felt repaints when the turn changes).
- **Things placed about a sitter** follow the screen, not the table, because the sitter is always upright.
  That covers their chair, the ring round whoever's thinking and their Ready tick. They use
  `FloorGame.on_screen(offset)`, and `screen_turn()` says which way up the table shows right now. A table
  redraws, and moves its dealer, when that changes (`CasinoTable._turned_on_screen`).
- **Chip stacks stand upright** on screen too (`ChipStack2D.face_screen()`, when they're put down and when the
  table shows a different way up). The cards lie flat and turn with the table.
- **Things lying on the floor in perspective** (Roulette's seat rings, the craps standing spots) are squashed up
  and down the screen, not the table: `Seating._on_floor()`, or a `draw_set_transform` turned by
  `-screen_turn()`. A standing spot still points at the table.
- **Sitting there** turns the whole floor (`World` in `casino_floor.tscn`) about the table, so the table is the
  right way up. Standing turns it back (`casino_floor.gd`, `_camera_to`'s `turn`). World Y-sorts, and Godot sorts
  in the turned frame, so the dealer goes behind the felt again and everyone overlaps the right way.
- **People stay upright.** `Avatar` keeps itself at no rotation on screen. Its `facing` is in its parent's frame
  (a dealer faces "down" across their own table), and the sprite shows that direction as the screen sees it.
  `FloorGame.world_dir()` turns a table's directions (`sit_facing`) into the floor's frame.
- **Positions** the floor and server use are in World's frame. Use `to_global()` for points on a table, never
  `global_position + offset`, as `focus_point()` does.
- **Roulette and Craps** add a little of their own. Their results signs keep themselves upright about their foot,
  like the people. The floor plan's Sign picks the end it stands past (`props.sign`, "left" or "right" as the
  players see it: `CasinoTable.sign_side`). Unpicked, it's the right-hand end, except at 90, where that end is the
  one nearest us and the sign would stand in front of the table, so it stands past the other end
  (`CasinoTable._stand_sign`). Roulette's dealer stands at the mouth of its
  shallower bay (`dealer_near_pos()` is `FELT_TOP`). At Craps the `dealer` is the stickman, who stands among the
  players and doesn't move; the boxman already stands just outside the bay's ledge, and draws over the rail on its
  side as the stickman does. The shooter's badge, "next shooter" and the standing spots go at a player's feet as
  the screen sees it, and the badge's text reads upright.

`tools/plan_catalogue.gd` measures each game at every turn it takes: the collision outline, a sitter in every
chair (where `chair_pos()` puts it at that turn) and every dealer standing, plus where the chairs and dealers are so
the Floor plan tab can draw them upright as the game does. A results sign gets its own footprint and base at each
end, apart from the table's: merged in, a tall thin sign past one end would claim the table's whole width.

## The layout audit

`tools/layout_audit.gd` measures all of this for every card table, headless, in a few seconds. For Roulette,
it checks that the wheel, float, chip hole, title and layout are on the felt and clear of each other, and
that the sign stands clear of the table. Run it before reaching for a screenshot:

```fish
cd client; godot --headless --path . -s ../tools/layout_audit.gd     # LAYOUT_ONLY=uth for one table
```
