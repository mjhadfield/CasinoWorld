# Casino World

A living 2D casino you play together in the browser. You walk your character around the floor
and pass other players and NPCs. You can watch the tables as you go by. Sit down at a Three Card
Poker table and play hands with whoever's there, alongside a dealer who deals, turns cards over
and pays everyone out. Then stand up and wander off again. It's the successor to
`~/Projects/Casino` (v2).

- **client/** is a Godot 4.7 project written in GDScript. It's exported to the web, so players
  just open a link.
- **server/** is a Python FastAPI app, and it's authoritative. It runs the tables, the NPCs and
  the world, holds the wallets, and serves the web export. The rules are ported from v2's
  `games/three_card_poker/logic.py`.
- **tools/build_art.py** builds the character sprite sheets (from LPC art) and the carpet tile.
- **docs/architecture.md** has the design. **server/protocol.md** documents every message.

## Setup (one-off)
```fish
sudo pacman -S godot                      # 4.7.x, plus Web export templates from the editor
cd ~/Projects/CasinoWorld/server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run
```fish
cd ~/Projects/CasinoWorld/server
.venv/bin/python -m casino_server          # HTTP 8660 (editor), HTTPS 8661 (browsers)
```
- **Browser or phone:** open `https://192.168.0.66:8661`. Each device shows a "connection not
  private" warning once (Advanced › Proceed). The certificate is self-signed and the server
  generates it into `server/data/tls/`. Godot's web build only runs over HTTPS or on `localhost`.
- **Desktop:** open `client/project.godot` in Godot and press **F5**. It connects to
  `ws://127.0.0.1:8660/ws`, or to `CASINO_SERVER_URL` if set.
- **Re-exporting** after client changes: `cd client && godot --headless --export-release Web
  ../build/web/index.html`, then reload the page. The server doesn't need a restart.

Environment knobs:
- `CASINO_NPCS` pins how many NPCs roam, overriding the floor population on the admin page's Settings tab (default 6).
- `CASINO_SPEED` scales every table timer and NPC pace; `0.5` is twice as fast.
- `CASINO_DATA_DIR` sets where the SQLite database lives (default `server/data/`).

## Playing
- **Walking:** WASD or arrow keys, or click/tap where you want to go. Click and hold to keep walking towards the pointer: the view follows you, so you can cross the whole floor that way, sliding along anything in the way. Your name tag comes from
  the welcome prompt on your first visit.
- **Taking a seat:** while you're walking, every free stool glows with **SIT**. Click one to sit there; if it's further away you walk over first. Or stand on a free stool and press **E**. The camera glides onto the table.
- **Betting:** pick a chip in the tray and click the spots *on the felt* in front of you: Pair
  Plus, Ante, Prime, and the Jackpot (£1). The Jackpot spot is a clear plastic disc with a light
  under it. The light flashes while your bet is on it. At "No more bets" the dealer locks the
  Jackpot bets in: the lights go solid red and the Jackpot chips are lifted off, leaving the
  light glowing until you're settled. Right-click takes a chip off.
  **Rebet** repeats your last hand. **Ready** (or **Space**) locks you in. Betting closes 15
  seconds after the first bet, or as soon as every player is Ready.
- **Deciding:** once the cards are dealt, everyone decides at the same time.
  - **Play** (**P**) matches your Ante. Your cards go face down, sideways, on the Play box, with
    the bet on top.
  - **Fold** (**F**) puts your cards in a messy face-down pile. A fold loses your Ante, Pair Plus
    and Jackpot bets. The exception is a Prime bet on three cards of one colour, which has already
    won: you tuck your cards under it, and it's paid at settlement.
  - There's a shared 20-second timer, which ends once everyone has decided, and anyone still
    undecided folds. NPCs take 2–10 seconds.
- **Settling,** one step at a time:
  1. The dealer takes the folded hands and their bets.
  2. The dealer turns their own cards over and announces them.
  3. The dealer settles each remaining player in turn, left to right on screen (third base to
     first). The player's cards slide out from under the bet and are turned over, and the dealer
     announces the hand ("Pair of Kings, wins."). After a pause, the losing bets are swept, the
     winnings are placed beside the stakes, and the cards are cleared away. There's another
     pause before the next player.
  4. Once everyone is settled, the winnings go back to the players and the next round begins.

  The dealer's lines appear in a bubble to the right of their head. Edit
  `server/casino_server/dealer_lines.toml` to add or reword them: the announcements, reactions
  by hand strength ("Nice hand!", "Oof, unlucky."), how often reactions happen, and the table
  calls. Changes apply on the next line the dealer says, with no restart.
- **Standing up:** use **Stand up** (or **Esc**). Standing mid-hand folds it at Three Card
  Poker, or stands your hands at Blackjack, after a confirmation. If you sit out three hands in a row, the table stands you up.

**Blackjack** is the second table on the floor: 3:2 for a Blackjack, dealt from a real 8-deck
shoe. The shoe carries on from hand to hand, and the discards pile up in the rack, until the
yellow cut card comes out. That hand is the last one; then the discards and the rest of the
shoe go through the shuffler and a fresh shoe goes in.
- **Bets:** the Blackjack circle, plus the side bets from v2: Super Pairs, 21+3, Top 3 (with a
  21+3 bet) and the £1 Jackpot, which shares Three Card Poker's progressive pool. Side bets settle
  straight after the deal; winnings stay beside their spots until the hand is over.
- **The deal:** one card at a time to every box, the dealer's up-card, a second card each, and
  the hole card face down. With an Ace showing, everyone can take **Insurance** (**I**) or decline
  (**N**). With an Ace or a 10 showing, the dealer checks the hole card for Blackjack. Once the
  dealer can't have Blackjack, any player Blackjack is paid 3:2 straight away.
- **Your turn:** boxes play in turn from first base. **Hit** (**H**), **Stand** (**S**),
  **Double** (**D**, on any two cards, also after splitting) or **Split** (**P**, any pair, up to
  4 times; split Aces get one card each). You have 20 seconds per decision; out of time stands.
  A bust is swept at once.
- **The dealer:** draws to 17 and stands on all 17s. Boxes are then settled from third base.

**Pai Gow Poker** fills the second row (centred under the three top tables): **Fortune Pai Gow** and **Face Up Pai Gow**. It's
53 cards, with a Joker that completes a Straight or Flush or else plays as an Ace.
- **Bets:** the Ante, plus the Fortune and £1 Jackpot side bets. They pay off your seven cards
  whatever happens to the Ante.
- **The deal:** the shuffler shows a number from 1 to 7. Counting the dealer as 1, that position
  gets the first of seven 7-card hands; hands for empty seats are dealt to their place, then swept to the discard rack before the reveal or the set.
- **Setting your hand:** you pick your cards up into the **sorter**, a panel over the bottom of
  the table. They arrive in no particular order; **Sort** (**S**) puts them in order. Tap a card
  (or press **1**–**7**) to move it between your 2-card **Low** hand and your 5-card **High**
  hand; it glides across, and the other cards shuffle along to make room. The panel names both hands and warns you about a foul (the High hand must beat the Low).
  **House Way** (**H**) sets it for you, and **Set hand** (**Enter**) puts it down: the Low hand
  upright in the LOW box, the High hand sideways in the HIGH box below it. If you run out of time,
  House Way sets it.
- **The dealer's hand:** all seven are turned over as dealt, then sorted, then the two Low cards
  are pushed forward and slid off to the left. Each card always lies over the one to its left, so
  every index stays visible. The label reads Low / High. At Fortune this happens once everyone has set; at
  Face Up it happens straight after the deal.
- **Settling:** each player's hands turn over, then a tick or cross pops in beside the Low hand,
  and a beat later beside the High hand. Win both hands against the dealer and the Ante pays 1:1,
  win one and it pushes.
  Ties go to the dealer. At both tables, £5 or more on Fortune also gets the **Envy Bonus** when
  another player hits Four of a Kind or better. A small round green ENVY button (half a chip
  across) sits beside a qualifying bet. Folded hands neither collect Envy nor trigger it.
  - **Fortune Pai Gow:** a 5% commission on winning Antes.
  - **Face Up Pai Gow:** no commission. The dealer's hand is set and shown before you set yours,
    and you may **Fold**: your cards are mucked unseen and every bet on them (Ante, Fortune,
    Jackpot) is lost at settlement. NPCs play the dealer's shown hand: they set to win if any
    split can, else to push, else they fold (unless their cards win a side bet, which a fold
    would throw away). A dealer Ace-high Pai Gow pushes every Ante. Nobody sets a hand then:
    if your cards win a side bet you **Claim bonus**, otherwise you **Fold**.

The engine fixes two bugs in v2's Pai Gow:
- A Joker with an Ace is now a pair of Aces. v2 split them, which made Face Up push Antes
  wrongly.
- A 5-card pair now beats a 2-card pair of the same rank, so the House Way's four-of-a-kind splits
  work. See the notes in `server/casino_server/engines/pai_gow.py`.

**NPCs** wander the floor, sit for a few hands (they play basic strategy: Q-6-4 or better), and
leave. They never take a table's last two free seats, so a real player can always sit down.

**Money:** each device is remembered as its own player and starts with £1,000. If you go broke,
**Top up** appears while you're walking. One progressive jackpot is shared by everyone.
`server/data/casino.sqlite` holds players, balances, the ledger and the jackpot; delete it to
start everyone fresh.

Don't edit balances in the database by hand: they're whole numbers of pence, and an edit like
`100,000` gets stored as text, which disconnects that player when they bet (the server warns
about it at startup). Use the admin command instead. It records the change in the ledger and is
safe to run while the server is up:
```fish
cd ~/Projects/CasinoWorld/server
.venv/bin/python -m casino_server.admin list
.venv/bin/python -m casino_server.admin set-balance Mike 1000      # pounds
```

**Betting when you sit down mid-hand:** at every table except Roulette, if a hand is already being played without
you, you can put your bets down straight away. They show faded on your spots, the bar says they play the next hand,
nothing leaves your balance yet, and Undo, Clear and Rebet work on them. When betting opens they go on as ordinary
bets and start the countdown. If you can no longer cover them, they come back with a message. At Roulette you still
wait for the next spin's betting (late bets during the spin are a separate thing).

The floor is a 3×3 grid of the nine card tables, plus a fourth column to the east for the wheel and dice
games (1800×1160):
- **Top row:** Three Card Poker, Blackjack, Mississippi Stud, then Roulette.
- **Middle row:** Fortune Pai Gow, Face Up Pai Gow, Ultimate Texas Hold'em, then a free space.
- **Bottom row:** Let It Ride, High Card Flush, Baccarat, then a free space.

The entrance is below the bottom row (at x 700).

**Mississippi Stud** (`ms_1`).
- **Bets:** the Ante, plus the 3 Card Bonus and the £1 Jackpot. You need ten times your Ante to sit a hand, enough to bet 3x on every street.
- **The deal:** two cards each, out of the shuffler, and only you see yours. Three community cards go face down in front of the dealer.
- **3rd, 4th and 5th Street:** everyone decides at once on one timer. **Fold** (**F**), or bet **1x**, **2x** or **3x** your Ante (**1**/**2**/**3**). Running out of time folds. After each street the dealer sweeps the folds and turns the next community card.
- **Settling:** your two cards plus the three community cards. Every bet still in play pays the same: Royal 500:1, Straight Flush 100:1, Quads 40:1, Full House 10:1, Flush 6:1, Straight 4:1, Trips 3:1, Two Pair 2:1, Jacks or better 1:1. A pair of 6s to 10s pushes.
- **A fold** loses the Ante, the street bets and the Jackpot. The 3 Card Bonus still pays on the community cards: every folded Bonus is settled together, at once. If everyone folds and no Bonus is riding, the hand just ends.
- **NPC thinking:** at most 3 seconds.
- **NPCs:** they follow Joseph Kisenwether's strategy (`engines/mississippi_stud.py: strategy`). A 9.6-million-hand simulation gives a house edge of 4.93% ± 0.32% of the Ante, in line with the published 4.91%.

**Ultimate Texas Hold'em** (`uth_1`).
- **Bets:** Ante, with an equal Blind placed automatically. Trips and the £1 Jackpot are optional. You need six Antes to play a hand (Ante, Blind and a 4x Play).
- **The deal:** two cards each (private), two to the dealer, five community cards, all face down.
- **Decisions:** everyone decides at once at each stage, and once your Play bet is down you're done.
  - Before the flop: bet **4x** or **3x**, or **check** (**C**).
  - After the flop: **2x** or check.
  - After the river (the turn and river are turned together): **1x** or **fold**.
  - Running out of time checks, or folds after the river.
- **Settling:** the dealer qualifies with a pair; if not, the Ante pushes. The Blind pays only on a Straight or better win. A fold loses the Ante, Blind, Trips and Jackpot. The Jackpot is judged on your hole cards plus the flop.
- **NPCs:** they follow the Wizard of Odds' simple strategy, including the "fewer than 21 dealer outs" river rule. Simulated house edge: 2.45% ± 0.31% (published 2.43%).

**Let It Ride** (`lir_1`, five seats spread out for room).
- **Bets:** three equal bets, 1, 2 and £ (a chip on any one sets all three). Side bets: the £1 Bonus, the 3 Card Bonus and the £1 Jackpot.
- **The deal:** three cards each (private) and two community cards.
- **Decisions:** after your three cards, **let it ride** (**R**) or **pull back** (**P**) bet 1; after the first community card, bet 2. Pulled bets come straight back. Running out of time pulls back. The £ always plays.
- **Settling:** a pair of 10s or better pays every bet still up (v2's paytable).
- **NPCs:** they follow the Wizard of Odds' strategy. Simulated: 3.27% ± 0.14% of one unit with v2's paytable.

**High Card Flush** (`hcf_1`, five seats spread out for room).
- **Bets:** Ante, plus the Flush, Straight Flush and £1 Jackpot side bets.
- **The deal:** seven cards each. Your own are fanned with your flush first.
- **Decisions:** everyone at once: **fold**, or **raise** 1x (2x with a 5-card flush, 3x with 6 or 7). Running out of time folds.
- **Raise:** your flush goes face down in front of you, and the other cards are set aside and swept. The dealer's hand is shown the same way: the flush slides forward and the rest is swept.
- **Fold:** the hand is swept away unseen with its Ante and side bets, the Flush bonus included (a table rule; v2 paid it). The exception is a straight flush of three or more with a Straight Flush bet or the Jackpot riding: those cards are tucked under the Straight Flush bet, as with a Prime at Three Card Poker, and still pay. A raised hand tucks a straight flush in another suit the same way.
- **Settling:** the longest flush wins, then the high cards. The dealer qualifies with a 3-card flush, 9-high; if not, the Ante pays and the Raise pushes.
- **NPCs:** they follow Mousseau's strategy (raise any 4+ flush or a 3-card 10-8-6+, always the most allowed). Simulated: 2.64% ± 0.11% (published 2.71%).

**Baccarat** (`bac_1`), Punto Banco.
- **Bets:** Player, Banker or Tie, plus the Player Dragon and Banker Dragon bonuses. There are no decisions.
- **The coup:** one for the whole table, out of the shuffler card by card, with running totals. Third cards follow the standard tableau. The dealer calls it, then every seat settles quickly.
- **Payouts:** Banker pays less 5%, rounded down to the penny. Tie pays 8:1.
- **5 Treasures:** v2's five side bets are in the engine (with parity tests) but not on the layout yet.

**Roulette** (`rou_1`), single zero with La Partage. Signed off on the Roulette mockup (claude.ai artifact, v6).
- **The table:** a long table rounded at the wheel end, with a bay where the dealer stands between the wheel
  and the layout. The float (for paying winners) is left of the bay and the chip hole (where losing chips go)
  is right of it. The results sign stands at the far end, showing the last 12, with reds right, blacks left
  and zero in the middle.
- **Bets:** chips anywhere on the standard layout, in your seat's own colour.
  - The middle of a box is a straight up, a side a split, a corner a corner.
  - The bottom edge of the 1-4-7 row is a street; on a line between two streets, it's a six line.
  - The zero's edge gives the 0-1, 0-2 and 0-3 splits, the two trios and the first four.
  - Hovering lights up the numbers a bet covers, and the bar names it and its payout.
  - Right-click takes a chip off. **Undo** (every table has it) takes back your last chip this round.
- **Limits:** £1 a bet; at most £100 straight up, £200 a split, £300 a street, £400 a corner, £600 a line,
  £1,000 a column or dozen, £2,000 an even chance.
- **The spin:** "SPINNING IN ..." counts down from the first bet (25s; 8s with only NPCs), or Ready spins sooner.
  - The dealer launches the ball: "FINAL BETS!" until just before it reaches the pockets (7.3s of its 7.6s run).
  - At "No more bets" the number is drawn (and only then). The server then plans the landing that carries the
    ball from where it reaches the pockets to that number: skids over the frets, slowing, then a few small hops.
    That's anything from a short stop to most of a lap, about 2-8s.
  - Then the dealer calls it and the dolly goes on the number. Losing chips fly down the hole (half of each
    even-money stake on a zero), winners are paid from the float, everything goes back, and the dolly comes off.
- **Payouts:** 35, 17, 11, 8, 5, 2 and 1 to 1. The house edge is 2.70% (1.35% on the even chances).
- **NPCs:** each has a habit: lucky numbers, the even chances, dozens and columns, or a sprinkle of
  splits, corners, streets and lines. They put chips down one at a time and sometimes slip in a late bet.
- **The ball** is choreographed, not simulated, and every viewer sees the same one. The spin sends the launch angle, so
  where the ball reaches the pockets is known from the start, but the number isn't. The arithmetic (`track_travel`,
  `arrival_pocket`, `plan_landing`, `landing_seconds`) lives in both `engines/roulette.py` and
  `scenes/table/roulette_wheel.gd`; keep the two in step.

## Admin page
Open **`/admin`** on the server (e.g. https://192.168.0.66:8661/admin; `/maintenance` still works). It has four tabs:
- **Sounds:** below. The moments and the library filter by **UI**, **Global**, **Game** (pick a game) and **Uploads**.
- **NPCs:** the roster. Punters come and go on their own; dealers work shifts.
  - **Looks:** design them in the browser: body and skin, hair, facial hair, top, over the top, legs, shoes,
    neck, glasses and hat, each in its colours, plus Randomise and uniforms. A live preview shows them
    walking, standing and seated. The server builds each look's sprite sheet from the LPC generator's layers
    (`casino_server/art.py`; downloads are cached in `server/lpc_cache/`, and `python -m casino_server.art prefetch`
    fetches the lot). The game downloads new looks as it meets them.
  - **How punters play:** a style (Grinder, Casual or Gambler) plus any traits (Whale, Chaser, Hit-and-run,
    Superstitious, Regular, Card counter, VIP; see `casino_server/roster.py`). Each also has a budget range,
    lucky numbers and favourite games.
  - **Visits:** each visit they bring a budget they're willing to lose. They leave bust, done for the day,
    while ahead (Hit-and-run) or doubled up (a Gambler), then stay away for a cooldown (a long one after
    going bust; Regulars come back sooner) while others take their place.
  - **Stats:** every visit is logged; lifetime staked, returned, net, best visit and busts are shown per NPC.
  - **Actions:** Bring in now, Send home and Reset stats.
  - **Staff roles:** waiters, pit bosses, cashiers and bar staff can be designed now, but don't work the
    floor yet.
- **Players:** everyone's lifetime staked, returned and net, per game, from the ledger.
- **Settings:** punters on the floor, cooldowns, dealer shift length.

The roster is seeded on first run with 20 punters and 14 dealers. It's stored in the SQLite database (tables
`npcs` and `npc_visits`). `CASINO_NPCS` overrides the floor population (tests use 0).

## Sounds
Open the **Sounds** tab of **`/admin`** on the server (e.g. https://192.168.0.66:8661/maintenance) to pick the sound
for each moment: the deal, chips, results, buttons, the background room and so on. Play anything
in the library, add or remove variants (a moment with several picks one at random each time),
trim its volume, or upload your own files. Changes save at once, and every open game reloads its
sounds within a second, so you can sit at a table and listen while you swap.

- **The library:** `server/sound_library/`, a CC0 collection (credits in its `LIBRARY.md`), plus your
  uploads in `<data dir>/sounds/uploads/`.
- **The choices:** `<data dir>/sounds.json`. Moments you haven't changed use the defaults in
  `casino_server/sounds.py`.
- **In the game:** `Sfx` fetches the choices when it connects. If the server can't be reached it plays
  the sounds built into the client (`client/assets/audio/`).
- **No password:** the page is open to anyone who can reach the server, the same as the game. Fine on
  the LAN and Tailscale.

## Table layout
Every table follows the same alignment rules:
- **Equipment:** the shuffler (or shoe) and discard rack sit inside the felt's cream border, level with the dealer's cards.
- **Dealer's cards:** they clear the chip tray (`DEALER_Y` -106.5).
- **Player cards:** their bottom edge sits 2 units inside the front border.
- **Betting rows:** stacked evenly just above the cards.
- **Winnings that can't go beside a stake** (the cards are right below) go as a second stack leaning on it.
- **Title:** centred in the band between the dealer's cards and the first row of bets (`title_y()`).
- **Countdown:** centred under the title where that band is roomy, otherwise level with it at the right-hand end (`countdown_pos()`).

`tools/layout_audit.gd` measures all of this for every table. For Roulette, it checks that the wheel, float, chip hole,
title and layout are on the felt and clear of each other, and that the sign stands clear of the table:

```fish
cd client; godot --headless --path . -s ../tools/layout_audit.gd
```

## Tests
```fish
cd server
.venv/bin/python -m pytest -q
```
The suite covers:
- **Table machine:** driven tick by tick (turn order, timeouts, folds and side-bet reveals,
  privacy, inactivity, jackpot).
- **NPCs:** simulated floors on a fake clock: budgets never overspent, visits reconcile with lifetime figures,
  busts cool down while the roster cycles, Hit-and-run, Chaser, Card counter, Regular and archetype sessions,
  dealers relieved only between hands.
- **Admin API:** NPC create/edit/delete, looks, bring in and send home, settings, player stats, sound categories.
- **WebSocket flows:** presence, a full seated round, passers-by not seeing private cards,
  disconnects.
- **v2 parity:** 20,000 hands and the special cases, with payouts matched to the penny.
- **Sounds:** the maintenance API, uploads, and that nothing outside the library can be reached.
- **Mississippi Stud:** 20,000 hands matched to v2 to the penny; Kisenwether's chart, line by line; the table flow.
- **Ultimate Texas Hold'em, Let It Ride, High Card Flush, Baccarat:** each matched to v2 to the penny over 8,000-20,000 hands; NPC strategies spot-checked; table flows.
- **Roulette:** there's no v2 version to match against, so it checks the arithmetic instead:
  - all 157 bets cover the right numbers, and every one's expected value is exactly -1/37 (-1/74 on the even chances)
  - the round (late bets, La Partage) and the limits
  - NPCs betting by habit on a simulated floor, late bets included

## Art
`python3 tools/build_art.py` rebuilds:
- `client/assets/sprites/characters/*.png`: the player, the dealer and 8 NPC looks
- `CREDITS.md`
- the carpet

To add a look, edit `LOOKS` in the script and rerun. The layers come from the Universal LPC
Spritesheet Character Generator, pinned to one commit, under CC-BY-SA/GPL. See
`client/assets/sprites/CREDITS.md`.

For now the floor is a compact test room (1000×820) holding only the four tables in a 2×2 grid.
The furniture placeholders are gone; the whole floor gets redesigned once the tables are done. The
room and the tables are drawn in code (`scenes/world/room.gd`, `scenes/table/tcp_felt.gd`), so they
stay sharp at any zoom. The table is the "Mahogany & Brass"
look: a wood rail with a brass bead, crimson felt, and cream printing in Cinzel
(`client/assets/fonts/Cinzel-SemiBold.ttf`, SIL Open Font License, see `Cinzel-OFL.txt`). It is a
static instance of the variable font with overlapping outlines merged (`fonttools varLib.instancer
Cinzel[wght].ttf wght=600 --remove-overlaps`), because MSDF text draws overlaps as specks.
`python3 tools/build_art.py tiles` rebuilds just the carpet and the felt grain.

Every game's table is built from shared, reusable pieces, so a new game mostly adds its own
layout and round:
- **`scenes/table/casino_table.gd` (`CasinoTable`)** is the base every table extends
  (`TcpTable`, `BlackjackTable`): the swept-bay shape and collision, seats and chairs, the dealer,
  chips and cards on the felt, Jackpot lights, the animation queue, and the hooks a game fills in
  (its spots, HUD actions and events). **`table_felt.gd` (`TableFelt`)** draws the Mahogany &
  Brass table; a game's felt (`tcp_felt.gd`, `bj_felt.gd`) only prints its layout.
- **`scenes/table/card_shoe.gd` (`CardShoe`)** is a dealing shoe with a cut card. Its stack shrinks
  as cards leave its `mouth_point()`, and the cut card is set aside once it's out.
- **`scenes/table/card_shuffler.gd` (`CardShuffler`)** is an in-table automatic shuffler. Hands
  come out of its front slot (`slot_point()` to `delivery_point()`) and used cards go into its
  intake (`intake_point()`). Call `deliver()` as each hand comes out and `shuffle(seconds)` after
  feeding it. Put it in a layer drawn above the cards.
- **`scenes/table/discard_rack.gd` (`DiscardRack`)** is a clear acrylic discard holder. `slot(n)`
  says where the nth discard lands, face down and sideways. It draws its own stack from `count`
  (so a whole shoe's worth costs nothing), and `take_all()` empties it for the shuffler. Put it in
  a layer drawn below the cards.

At Three Card Poker each hand comes out of the shuffler as a packet of three and is then dealt
across. Folded and settled hands go face down into the discard rack and stay there until the end
of the hand, when the dealer feeds the whole rack into the shuffler. Each table's
**Seat0–5** markers are editable in the editor. A seat's column of spots (Jackpot, Pair Plus and
Prime, Ante, Play) and its cards line up above its marker.

## Layout
- **server/casino_server/**
  - `tables/base.py`: seating, betting, Ready and the clock, shared by every table machine.
  - `tables/three_card_poker.py`, `tables/blackjack.py`, `tables/pai_gow.py`: the timed table
    machines, which are pure and emit events.
  - `tables/runner.py`: drives a table in real time and publishes its events.
  - `npc.py`: the NPC director.
  - `world.py`: everyone on the floor.
  - `casino.py`: sessions and message routing.
  - `engines/`: the v2 rules.
  - `store.py`, `jackpot.py`: storage and the progressive pool.
  - `floor.py`: the table list and the floor point names.
- **client/scenes/**
  - `world/`: the floor, avatars (`avatar.tscn`, `local_player`, `entity_avatar`), and the room.
  - `table/`: the tables (`casino_table` base, whose `seats` export and Seat0..n markers set the seat count and spacing; `tcp_table`, `bj_table`, `pg_table`), their felts,
    the shoe, shuffler and discard rack, cards and chips.
  - `ui/hand_sorter.gd`: the Pai Gow hand sorter.
  - `ui/settings_menu.gd`: the Settings panel (top-right button). It edits the `Settings`
    autoload (`autoload/settings.gd`), which saves to `user://settings.cfg` and sets the volumes on
    the audio buses: Master, Effects (game sounds) and Ambience (the room loop, 12% by default).
    The buses are declared in `client/default_bus_layout.tres`; adding them in code breaks web audio.
- **client/autoload/sfx.gd**: the game's sounds. `Sfx.play(key)` is for your own cues (buttons,
  your turn, the countdown tick); `Sfx.play_at(key, position)` is for table sounds, which fade with
  distance from the camera so you mostly hear your own table. Several variants per key are picked at
  random, with a minimum gap between plays. Deals make one swish per batch of cards that leaves together (a 3-card packet, a 7-card hand, a single Blackjack card). The
  sounds are all CC0, picked on a sound board; see `client/assets/audio/CREDITS.md`.
  - `ui/hud.tscn`: the HUD.
