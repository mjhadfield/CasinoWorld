# Building a table

How the tables are drawn and laid out in the client. The rules of each game are in `docs/games/`.

## The look

The tables are drawn in code (`scenes/table/table_felt.gd` and each game's `*_felt.gd`), as is the room
(`scenes/world/room.gd`), so they stay sharp at any zoom. The table is the "Mahogany & Brass" look: a wood
rail with a brass bead, crimson felt, and cream printing in Cinzel (`client/assets/fonts/Cinzel-SemiBold.ttf`,
SIL Open Font License, see `Cinzel-OFL.txt`). It is a static instance of the variable font with overlapping
outlines merged (`fonttools varLib.instancer Cinzel[wght].ttf wght=600 --remove-overlaps`), because MSDF text
draws overlaps as specks.

## Shared pieces

Every game's table is built from shared, reusable pieces, so a new game mostly adds its own layout and round:
- **`scenes/table/floor_game.gd` (`FloorGame`)** is what every table and slot cabinet on the floor is.
- **`scenes/table/casino_table.gd` (`CasinoTable`)** is the base every card table extends: the swept-bay shape
  and collision, seats and chairs, the dealer, chips and cards on the felt, Jackpot lights, the animation
  queue, and the hooks a game fills in (its spots, HUD actions and events). Its `seats` export and the
  Seat0..n markers (editable in the editor) set the seat count and spacing. A seat's column of spots and its
  cards line up above its marker.
- **`scenes/table/table_felt.gd` (`TableFelt`)** draws the Mahogany & Brass table; a game's felt only prints
  its layout.
- **`scenes/table/card_shoe.gd` (`CardShoe`)** is a dealing shoe with a cut card. Its stack shrinks as cards
  leave its `mouth_point()`, and the cut card is set aside once it's out.
- **`scenes/table/card_shuffler.gd` (`CardShuffler`)** is an in-table automatic shuffler. Hands come out of
  its front slot (`slot_point()` to `delivery_point()`) and used cards go into its intake
  (`intake_point()`). Call `deliver()` as each hand comes out and `shuffle(seconds)` after feeding it. Put it
  in a layer drawn above the cards.
- **`scenes/table/discard_rack.gd` (`DiscardRack`)** is a clear acrylic discard holder. `slot(n)` says where
  the nth discard lands, face down and sideways. It draws its own stack from `count` (so a whole shoe's worth
  costs nothing), and `take_all()` empties it for the shuffler. Put it in a layer drawn below the cards.

## Layout rules

Every card table follows the same alignment rules:
- **Equipment:** the shuffler (or shoe) and discard rack sit inside the felt's cream border, level with the
  dealer's cards.
- **Dealer's cards:** they clear the chip tray (`DEALER_Y` -106.5).
- **Player cards:** their bottom edge sits 2 units inside the front border.
- **Betting rows:** stacked evenly just above the cards.
- **Winnings that can't go beside a stake** (the cards are right below) go as a second stack leaning on it.
- **Title:** centred in the band between the dealer's cards and the first row of bets (`title_y()`).
- **Countdown:** centred under the title where that band is roomy, otherwise level with it at the right-hand
  end (`countdown_pos()`).

## The layout audit

`tools/layout_audit.gd` measures all of this for every card table, headless, in a few seconds. For Roulette,
it checks that the wheel, float, chip hole, title and layout are on the felt and clear of each other, and
that the sign stands clear of the table. Run it before reaching for a screenshot:

```fish
cd client; godot --headless --path . -s ../tools/layout_audit.gd     # LAYOUT_ONLY=uth for one table
```
