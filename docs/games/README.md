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
| Slots (Armadillo Goes West and built slots) | `b1_1`.. (the slot banks) | [slots.md](slots.md), and the design record in `docs/slots/` |

## The floor

The main floor is 1900×1160 (`client/scenes/world/room.gd`). The nine card tables are in a 3×3 grid, and a
fourth column to the east holds the wheel and the dice:
- **Top row:** Three Card Poker, Blackjack, Mississippi Stud, then Roulette.
- **Middle row:** Fortune Pai Gow, Face Up Pai Gow, Ultimate Texas Hold'em, then Craps.
- **Bottom row:** Let It Ride, High Card Flush, Baccarat.

**The Blackjack pit room** is east of the main floor (1000×1160), through a doorway low in the shared wall. Its
four blackjack tables stand close together in two rows facing apart across a narrow pit, with the dealers back to
back and the pit boss at a podium between them. An invisible fence (`PitFence`, which only the navigation map sees)
closes the gaps between the tables and the pit's ends, so NPCs never walk into the pit. Players can. The far row (`bj_2`, `bj_3`) is turned upside down, so its players sit on
the north side.
When you sit there, the view turns round so the table is the right way up, and it turns back when you stand. The
near row (`bj_4`, `bj_5`) is the usual way round. The pit boss is decoration for now.

The slot banks stand wherever the admin page's Floor tab puts them (the south-east corner, below Craps, is the
open floor for them). When a table moves or changes shape, run `tools/floor_map.gd` so the Floor tab and its
checks see it (README, Admin page).

The entrance is below the bottom row (at x 700).

## Walking and sitting

- **Walking:** WASD or arrow keys, or click/tap where you want to go. Click and hold to keep walking towards
  the pointer: the view follows you, so you can cross the whole floor that way, sliding along anything in the
  way. Your name tag comes from the welcome prompt on your first visit.
- **Taking a seat:** while you're walking, every free chair glows. Click one and you walk to its side; the
  chair swivels round to you, you sit side-on, and it turns you to the table. Or stand on a free chair and press **E**. Once you're sat, the camera glides onto the
  table, turning the view round first at a table that faces the other way. Other players and NPCs sit down the
  same way.
- **Chairs:** every table and slot cabinet has the same chair, from the **default seating style** on the admin
  page's Settings tab (a low-back stool in black leather on a brass frame, signed off on the seating mockup).
  Styles are stored by name with a table-to-style map, so a table can have its own later (`seating.py`).
- **Standing up:** use **Stand up** (or **Esc**). Standing mid-hand folds it at Three Card Poker, or stands
  your hands at Blackjack, after a confirmation. If you sit out three hands in a row, the table stands you up.

## Betting at the card tables

- Pick a chip in the tray and click the spots *on the felt* in front of you. Right-click takes a chip off, and
  **Undo** takes back your last chip this round.
- **Rebet** repeats your last hand, and cuts the countdown to 3 quiet seconds. **Auto rebet** puts last hand's
  bets back down as each hand ends; timing out of any decision unticks it.
- **Ready** (or **Space**) locks you in. Betting closes 15 seconds after the first bet, or as soon as every
  player is Ready.
- **The £1 Jackpot** spot (at most tables) is a clear plastic disc with a light under it. The light flashes
  while your bet is on it. At "No more bets" the dealer locks the Jackpot bets in: the lights go solid red
  and the chips are lifted off, leaving the light glowing until you're settled. One progressive jackpot is
  shared by every table and everyone.
- **Sitting down mid-hand:** at every table except Roulette and Craps, if a hand is already being played
  without you, you can put your bets down straight away. They show faded on your spots, the bar says they
  play the next hand, nothing leaves your balance yet, and Undo, Clear and Rebet work on them. When betting
  opens they go on as ordinary bets and start the countdown. If you can no longer cover them, they come back
  with a message.

## Dealers

The dealer's lines appear in a bubble to the right of their head. Edit
`server/casino_server/dealer_lines.toml` to add or reword them: the announcements, reactions by hand
strength ("Nice hand!", "Oof, unlucky."), how often reactions happen, and the table calls. Changes apply on
the next line the dealer says, with no restart. Dealers come from the roster and work shifts (admin page ›
NPCs, Settings).

## NPCs

NPCs wander the floor, sit for a while, and leave. Each game's file says how they play it. They never take a
table's last two free seats (or the last two free slot cabinets in a bank), so a real player can always sit
down. Their budgets, styles and traits are on the admin page (README › Admin page).

## Money

Each device is remembered as its own player and starts with £1,000. If you go broke, **Top up** appears
while you're walking. Balances are whole pence in `server/data/casino.sqlite`; change them with the admin
command, never by hand (README › Money).
