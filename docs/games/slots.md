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

NPCs play the slots too, and always leave at least two cabinets of the bank free for real players.

## Admin

The admin page's **Slots** tab shows the four jackpot meters and players' return on slots, and picks the symbol
art: the signed-off vector set, or FLUX 1 or 2.
