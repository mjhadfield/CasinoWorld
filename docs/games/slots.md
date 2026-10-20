# Slots: Armadillo Goes West (`slot_1`..`slot_10`), and built slots

Ten one-seat Armadillo cabinets in the south-east corner. Slots built with the admin page's Slot design wizard
stand in banks of up to ten on named spots nearby (`<id>_1`..), and play by the same rules below with their own
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

NPCs play the slots too (firing on the trail and a battle's ships, and choosing a voyage's islands and deals at
random, after a moment's thought), and always leave
at least two cabinets of the bank free for real players.

## Admin

The admin page's **Slots** tab shows the four jackpot meters and players' return on slots, and picks the symbol
art: the signed-off vector set, or FLUX 1 or 2.
