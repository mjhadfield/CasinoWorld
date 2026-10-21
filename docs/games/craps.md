# Craps (`crp_1`)

Vegas rules, eight places at the rail, where players stand rather than sit. Each free place is marked on the floor
in the seating style's look (`craps_spot`: footprints on a brass-rimmed plate by default) and glows with **STAND**
while you're walking; a taken one shows its player's colour. Signed off on Mike's Craps mockup (v1). The bet catalogue and payouts are in the
docstring of `server/casino_server/engines/craps.py`; the table's flow is in `tables/craps.py`.

## Bets

Bets stay on the layout from roll to roll; there's no Rebet. New chips are paid for when the dice go out (one
debit per seat per roll), and taking a paid-for bet down refunds it at once.
- **The line:** Pass Line and Don't Pass Bar 12 pay 1 to 1; odds behind them go up to 3-4-5x (lay odds 6x)
  and pay true odds.
- **Come and Don't Come:** the same for a new point, any roll after the come-out. They travel to their number,
  where you can take odds on them.
- **Place** 4/10 9 to 5, 5/9 7 to 5, 6/8 7 to 6. **Buy** pays true odds less 5% of the bet; **Lay** true odds
  against, less 5% of the win.
- **Field** (3, 4, 9, 10, 11 even money; 2 double, 12 triple), **Big 6** and **Big 8**.
- **Hardways** (4/10 7 to 1, 6/8 9 to 1) and the one-roll props: Any 7, Any Craps, 2, 3, 11, 12, Horn, C&E.
- £5 minimum on the main bets, £1 on hardways and props. Payouts round down to the penny.
- Place and buy bets, hardways and come odds are off on the come-out unless you mark them **working**; lay
  bets, Big 6/8 and the props always work. Winning bets stay up and only the winnings come back, except come
  bets and their odds, which come back with them.

## A roll

1. **Betting:** the dice are in the middle and bets go down. An NPC shooter rolls when the 5-second window
   closes ("Dice out in 5"). A human shooter rolls with **Roll** (or **Space**) within 20 seconds, or the dice
   pass on.
2. **"Dice are out":** no more bets. The dice are drawn and their path is planned on the server
   (`engines/craps.plan_throw`), so every viewer sees the same throw bounce off the walls and the chips.
3. **Settling:** the stickman calls it; the base dealers sweep the losers and pay the winners beside their
   bets; winnings go back to the players; come bets travel to their numbers; the puck turns over. Then
   betting opens again.

## The shooter

Anyone seated can shoot, NPCs included. After a seven-out the dice move clockwise (seat 0, the right-hand end
of the near rail, to seat 7). You can **take the dice** from an NPC: at once if no point is on, otherwise when
the point is decided. If the shooter leaves, the next player takes the dice and the point. A human with
nothing on the table for 40 rolls is stood up.

## NPCs

Each has a style: a grinder plays the line with full odds and a couple of come bets, a casual player the line
and Place 6 and 8, a gambler the field, hardways and props, and some superstitious players the dark side.
They only get up once nothing of theirs is stuck on the table. The table tries to keep at least two NPCs at
it, so there's always a game.

## Tests

There's no craps in v2, so the tests check every bet's exact house edge against the published one, plus the
table flow and a roll over the wire.
