# Slots: Armadillo Goes West, and built slots

One-seat cabinets in slot banks, made and placed on the admin page's Floor tab: a bank is any mix of slots, each
cabinet facing any way, anywhere clear on the floor (cabinet ids are the bank's id and a number, `b1_3`). Slots
built with the admin page's Slot design wizard play by the same rules below as Armadillo, with their own
tiers, pays, features, bonus settings, look and words. A built slot can also switch a bonus off, start it from
either scatter, and say whether Buy Bonus gives it; a scatter or Buy Bonus with more than one bonus plays one of them
at random, and a scatter that starts nothing isn't on its reels. The design record, the maths source and how to add another
slot are in `docs/slots/` (start with its README).

## Playing

Sitting at a cabinet opens a full-screen game that grows out of its little screen.
- **The game:** 5×4 reels, 25 fixed lines paying left to right. One total-bet ladder: 25p, 50p, 75p, £1,
  £1.50, £2.50, £5, £10, £25.
- **Spin** whenever you like; a new spin can cut the last one's presentation short after a second.
- **Random features** on any spin: Random Wilds, Wild Reels, Colossal Reels, a Random Multiplier, Symbol
  Upgrade, Repeat Win and Instant Win.
- **Trail Bonus:** 3 or more wagon scatters. FIRE loads 1–6 bullets and the armadillo moves along a trail of
  prizes to a 2,000x prizepot (it fires itself if you wait).
- **Combo Free Games:** 3 or more crossed-pistol scatters give three free games, each with guaranteed
  features.
- **Buy Bonus:** 45x the bet goes straight to the Trail Bonus.
- **Red Alert (the battle bonus):** in the library for any built slot, off until its design switches it on (Star
  Trek's will start from its bonus scatter). Your ship faces five waves of enemy ships (4, 5, 6, 7 and 8 by
  default), then a boss. Tap a ship to fire (FIRE or Space fires at one; it fires itself after 8 seconds). Each
  shot's result is drawn when it's fired, so which ship you pick never changes the odds; ships cloak now and then
  for show, and a cloaked one can't be tapped. A shot either destroys its ship, which reveals a prize (0.2x to 25x
  the bet) or, 1.5% of the time, 1 to 3 free games, or is answered: the ship cloaks and fires back, costing a
  shield. Shields hold 3 hits a wave: lose them all and the battle ends with what you've won. Clearing a wave pays
  its reward (2x, 4x, 6x, 12x, 25x) and restores the shields. After the last wave the boss takes 6 hits and pays
  100x to 1,000x. The free games its ships gave play afterwards as Combo Free Games, that many of them. It's
  worth about 43x the bet on average with the defaults; about 7% of battles reach the boss and 4% destroy it.
- **Dead Man's Map (the voyage bonus):** in the library for any built slot, off until its design switches it on
  (built from the Pirates design's spec). A sea chart, all of it in view: the start port, six legs of three islands,
  then the final island. Click a lit island to sail there: the one level with yours on the next leg, or either side
  (it chooses for you, at random, after 12 seconds). What an island gives is drawn when you land:
  - **Treasure Island** pays 3x to 40x the bet.
  - **Shipwreck** gives 1 to 3 relics, and 55% of the time a key (30% of those) or an artefact you're missing.
  - **Skull Island** pays 8x to 120x, but 24% of the time it sinks the ship: the voyage ends there, you keep what
    you've won, and the final island and your relics are lost.
  - **Port Royal** (never on the first leg) trades relics, one deal a visit: an artefact you're missing (3 relics),
    a key (2), a free game (4), or sell them all (1x the bet each); or just set sail. Waiting buys an artefact if it
    can, else a free game, else sells.
  - **Hidden Cove** (one a map, from the second leg) is locked: a key opens it for 10x to 50x and an artefact.
  - **The final island** pays the legendary treasure: the chest (12x) always, each artefact's part (Compass 4x,
    Medallion 5x, Spyglass 8x, Cutlass 12x), the legend (90x) for all four, and 1x a relic left over.

  Free games bought play afterwards as Combo Free Games. The choices are real but balanced: with the defaults a
  voyage is worth about 45x choosing at random, and careful (avoiding Skull Island), bold (seeking it) and
  collecting routes all pay within about 7% of that; careful routes swing least, bold ones most (about a quarter
  of random voyages sink, nearly half of bold ones), and a collector gets all four artefacts about 8% of the time.
- **Delta Quadrant (the expedition bonus):** in the library for any built slot, off until its design switches it on
  (built from the Voyager design's spec). A star chart: your ship, three routes, the final destination. Each
  route's length (4, 5 or 6 sectors) and hazard level (Low, Moderate or Severe) is drawn fresh, and its readings
  show both and its final prize (20x, 22x or 24x the bet). Click a route; then in each sector click one of three
  hidden planets (it chooses for you after 12 seconds: a random route or planet, or in a scanned sector the best
  one shown). The other two then show what you missed. A planet holds:
  - **Credits:** 1x to 15x the bet, times the level's prize scale (x1, x1.7, x2.6) and the multiplier.
  - **A multiplier:** +1 (or +2) to the expedition multiplier, from x1, on every later prize and the final prize.
  - **Tech:** a **Scanner** shows the next sector's planets before you pick, a **Shuttle** explores a second
    planet in the next sector (a hazard it finds only loses the shuttle), and **Shields** absorb the next hazard.
  - **A special:** an **ancient artefact** (10x to 100x, scaled and multiplied), a **Wormhole** (straight to the
    final destination, its prize doubled), or 1 to 3 **free games**, played afterwards as Combo Free Games.
  - **A hazard** (Borg cube, Kazon raiders, Hirogen hunters, Species 8472, a spatial anomaly): the expedition ends
    there, you keep what you've won and lose the final prize. Hazards are likelier on riskier routes and deeper
    into any route.

  The final destination pays its prize times the multiplier. The choice is real but balanced: with the defaults
  an expedition is worth about 46x choosing at random, and always taking the safest, the most dangerous, the
  shortest or the longest route all pay within about 8% of that. Safe routes swing least (SD 41) and dangerous
  ones most (SD 58). About 40% of random expeditions end at a hazard and 7% go through a Wormhole.
- **Jackpot Pick:** a random trigger on any spin, more likely the bigger the bet. Pick coins from a board of
  12 until three match, and win that meter: Mini, Minor, Major or Grand. The four meters are shared by every
  cabinet, grow from every bet (players' and NPCs'), and are separate from the card tables' jackpot. It picks
  for you after 15 seconds.

## The return

The game returns about 91.5%, plus 3.75% from the progressives, about 95% in all. The Buy Bonus returns about
93.7%. The slow test `test_slots_rules.py::test_the_signed_off_return` checks this
(`tools/dev.sh test --all`).

## Money and sessions

A paid spin is debited and its win credited at once (the screen holds your balance back until the reels
stop); a feature's win is credited when it ends. A cabinet keeps nothing between players: standing up (or
disconnecting) mid-feature plays the rest out at once and pays it, and the next player finds a fresh cabinet.
Only the four progressive meters persist.

## NPCs

NPCs play the slots too (firing on the trail and a battle's ships, choosing a voyage's islands and deals at
random, and an expedition's route and planets the way the timer would, after a moment's thought), and always leave
at least two cabinets of the bank free for real players.

## Admin

The admin page's **Slots** tab shows the four jackpot meters and players' return on slots, and picks the symbol
art: the signed-off vector set, or FLUX 1 or 2.
