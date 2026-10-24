# Master Table (`mt_<n>`)

One table that becomes any of the card games sharing the swept-bay table: Three Card Poker, Blackjack, both Pai
Gows, Mississippi Stud, Ultimate Texas Hold'em, Let It Ride, High Card Flush and Baccarat. It never becomes Roulette
or Craps. Mike signed it off on the mockup (https://claude.ai/artifact/GPAjSj5NTbXaN58X5hFzMN,
`docs/master_table/mockup/`). It's placed on the Floor plan tab like any table, as "Master Table".

## Blank

Until someone chooses a game, the felt carries only the Master Table crest:
- a gold ring with a crown set on top;
- MASTER TABLE and NINE GAMES · ONE TABLE round its band;
- the four suits round a gold star in the middle;
- ASK THE DEALER FOR ANY GAME under it;
- the dealer's rules either side: ANY CARD GAME / ON ONE TABLE and CHANGE GAME / BETWEEN HANDS.

Only people sit at a blank table, never NPCs. When you sit, the dealer asks what you'd like to play and the menu
opens.

## Choosing and changing

- **The menu:** each game with a picture of its layout in the table's own style, a line about it, and its key (1–9).
  Esc closes it.
- **Choosing:** anyone seated can choose. Click the dealer to open the menu again. The dealer lights up under the
  pointer while you're sitting there.
- **Others seated:** they're asked first. They have 10 seconds to agree; saying nothing counts as yes, and one no keeps
  the game. NPCs don't vote.
- **Timing:** a change happens only between hands. Asked mid-hand, it waits ("After this hand: Baccarat ✕"; the ✕
  stays on this game). Any bets on the felt come back first, since nothing is paid for until betting closes.
- **NPCs:** each one stays if it likes the new game (a favourite always, otherwise half the time; a Card counter only
  for Blackjack), or gets up and goes. Those who stay play the new game from its first betting round.
- **Five seats:** Let It Ride and High Card Flush seat five. From a six-seat game they're offered only while a seat is free; between the two of them a full table can switch freely. Everyone keeps
  their order; the empty seat that goes (or the new one that comes, going back to six) is the one that moves people
  least. The chairs slide with their sitters.

## The change animation

Picked per table on the Floor plan tab ("Changes with" and "Speed"). The default is Fresh cloth at 1×.

| Option | What it does | At 1× |
|---|---|---|
| Fresh cloth | A new cloth rolls down from the dealer's side, uncovering the new layout. | 2.7 s |
| Dealer's sweep | The printing flies into the chip tray seat by seat from third base, a sheen crosses the felt, then the new layout deals back out the same way. | 3.0 s |
| Gold dust | The printing breaks into gold dust that drifts across and settles into the new layout. | 3.3 s |

Speed is 0.5×, 1× or 2×. The server holds the table for the animation plus 0.8 s, then betting opens on the new game.
The shuffler, shoe and discard rack glide to their new places or slide on and off. The dealer gives a little bob.

## Empty

With no person seated, the table keeps its game for 30 seconds ("MASTER TABLE IN n" on the felt), so you can stand and
come back. Then the NPCs finish their hand and go, and it changes back to the crest. NPCs alone don't keep a game going.

## Sounds

It plays its game's sound set while it has one, and the casino's own while it's blank.
