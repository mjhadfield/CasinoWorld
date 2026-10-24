# Playing Casino World

How the floor works and what every table has in common. Each game's rules are in its own file:

| Game | Table id | File |
|---|---|---|
| Three Card Poker | `tcp_1` | [three_card_poker.md](three_card_poker.md) |
| Blackjack | `bj_1`, and `bj_2`..`bj_5` in the pit room | [blackjack.md](blackjack.md) |
| Fortune Pai Gow, Face Up Pai Gow | `pgf_1`, `pgu_1` | [pai_gow.md](pai_gow.md) |
| Mississippi Stud | `ms_1` | [mississippi_stud.md](mississippi_stud.md) |
| Ultimate Texas Hold'em | `uth_1` | [ultimate_texas_holdem.md](ultimate_texas_holdem.md) |
| Let It Ride | `lir_1` | [let_it_ride.md](let_it_ride.md) |
| High Card Flush | `hcf_1` | [high_card_flush.md](high_card_flush.md) |
| Baccarat | `bac_1` | [baccarat.md](baccarat.md) |
| Roulette | `rou_1` | [roulette.md](roulette.md) |
| Craps | `crp_1` | [craps.md](craps.md) |
| Slots (Armadillo Goes West and built slots) | `slot_1`.. (the floor plan) | [slots.md](slots.md), and the design record in `docs/slots/` |
| Master Table: any of the card games above, chosen at the table | `mt_<n>` (the floor plan) | [master_table.md](master_table.md) |

## The floor

The floor is built on the admin page's Floor plan tab (README, Admin page; `server/casino_server/plan.py`): rooms
side by side on one plan, joined by doors and archways, with the tables and slot cabinets placed in them. A table's
id is given when it's placed (`bj_6`, `slot_12`) and never used again. Players appear at the plan's spawn point
(the lobby's, to start); NPCs come in at arrival points and wander between wander points.

The library keeps the old hand-built floor as two blueprints: **Classic floor** (1900×1160: the nine card tables in
a 3×3 grid, Roulette and Craps in a fourth column, the first slot bank in the south-east corner, the entrance
below the bottom row at x 700) and **Classic pit** (1000×1160, through an archway low in their shared wall: four
blackjack tables in two rows facing apart, the far row turned, with the pit boss at a podium between them and an
NPC-only zone closing the gaps). Players sitting at a turned table see the view turn round so it's the right way
up, and turn back when they stand.

## Walking and sitting

- **Walking:** WASD or arrow keys, or click/tap where you want to go (a tap walks round things and through
  doorways). Click and hold to keep walking towards the pointer: the view follows you, so you can cross the whole
  floor that way, sliding along anything in the way. You see the room you're in, any joined to it by archways, and
  the room through a door once you're in its doorway. Your name tag comes from the welcome prompt on your first visit.
- **Taking a seat:** while you're walking, every free chair glows. Click one and you walk to its side; the
  chair swivels round to you, you sit side-on, and it turns you to the table. Or stand by a table or slot with a
  free chair and a **Play** prompt shows under your feet: press **E** (or the prompt) to sit in the nearest free chair.
  You can't walk through the chairs, or through anyone else. Once you're sat, the camera glides onto the
  table, turning the view round first at a table that faces the other way. Other players and NPCs sit down the
  same way.
- **Chairs:** every table and slot cabinet has the same chair, from the **default seating style** on the admin
  page's Settings tab (a low-back stool in black leather on a brass frame, signed off on the seating mockup).
  Styles are stored by name with a table-to-style map, so a table can have its own later (`seating.py`).
- **Standing up:** use **Stand up** (or **Esc**). Standing mid-hand folds it at Three Card Poker, or stands
  your hands at Blackjack, after a confirmation. If you sit out three hands in a row while the table has one
  open seat or none, the table stands you up (at a quieter table you keep your seat until it fills up).

## Betting at the card tables

- Pick a chip in the tray and click the spots *on the felt* in front of you. Right-click takes a chip off, and
  **Undo** takes back your last chip this round.
- **Repeat Bet** (or **Space**) puts your last hand's bets down again, and cuts the countdown to 3 quiet seconds. It
  sits where Ready does until you've bet, then the button turns back into Ready. **Auto rebet** puts last hand's
  bets back down as each hand ends; timing out of any decision unticks it.
- **Ready** (or **Space**) locks you in. Betting closes 15 seconds after the first bet, or as soon as every
  player is Ready.
- **Sit out** is a switch beside Auto rebet: while it's on you're Ready with no bets each time betting opens, so
  you sit the hands out. Putting a chip down, Repeat Bet or ticking Auto rebet turns it off. (Not at Roulette,
  which spins anyway, or Craps.)
- **The £1 Jackpot** spot (at most tables) is a clear plastic disc with a light under it. The light flashes
  while your bet is on it. At "No more bets" the dealer locks the Jackpot bets in: the lights go solid red
  and the chips are lifted off, leaving the light glowing until you're settled. One progressive jackpot is
  shared by every table and everyone.
- **Sitting down mid-hand:** at every table except Roulette and Craps, if a hand is already being played
  without you, you can put your bets down straight away. They show faded on your spots, the bar says they
  play the next hand, nothing leaves your balance yet, and Undo, Clear and Repeat Bet work on them. When betting
  opens they go on as ordinary bets and start the countdown. If you can no longer cover them, they come back
  with a message.
- **A second box:** sitting at Three Card Poker, Blackjack, Mississippi Stud, Ultimate Texas Hold'em, Let It Ride
  or High Card Flush (or a Master Table playing one of them), a free chair right beside you shows a **2nd Box**
  pill. Click it and confirm ("Play second box? Your bets will be matched") and you play that seat too. Every bet
  you make is matched on it, so you need enough to cover both; a click on its spots is a bet on yours. It's dealt,
  decided and settled as a hand of its own, with its own result floating off its chair, and the bar asks about
  "Box 1" (your own seat) and then "Box 2". Where everyone decides at once, Box 2's cards stay face down to you
  until Box 1 has decided, and Box 1 decides first on every street. Between hands its chair shows **Drop Box** to
  give it back; it also goes when you stand up, and when a Master Table changes game. Not at Pai Gow or Baccarat.

## Dealers

The dealer's lines appear in a bubble to the right of their head. Edit
`server/casino_server/dealer_lines.toml` to add or reword them: the announcements, reactions by hand
strength ("Nice hand!", "Oof, unlucky."), how often reactions happen, and the table calls. Changes apply on
the next line the dealer says, with no restart. Dealers come from the roster and work shifts (admin page ›
NPCs, Settings).

## NPCs

NPCs come in at the floor plan's arrival points, wander between its wander points (by their weights, lingering
as long as each says), sit for a while, and leave the way they came. Nobody comes in while there's no free seat. Each game's file says how they play it. They never take a
seat kept for real players (the middle seat at a five-seat table, the middle two at a six-seater, the second
place from the left on each side of the craps table, and the last two free slot cabinets in a bank), so a real
player can always sit down. Their budgets, styles and traits are on the admin page (README › Admin page).

## Money

Each device is remembered as its own player and starts with £1,000. If you go broke, **Top up** appears
while you're walking. Balances are whole pence in `server/data/casino.sqlite`; change them with the admin
command, never by hand (README › Money).
