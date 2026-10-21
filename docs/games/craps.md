# Craps (`crp_1`)

Vegas rules, eight places at the rail, where players stand rather than sit. Each free place is marked on the floor
in the seating style's look (`craps_spot`: footprints on a brass-rimmed plate by default) and glows while you're
walking; a taken one shows its player's colour. While you're at the table the free ones are hidden. Each player
has a run of chips in the rail's groove beside them (on the stickman's side of their head, so it isn't hidden):
the edge-on chips of the dealer's rack, in the denominations they bet in (the biggest bet, odds aside, they've
had down since they came; the table minimum, or your picked chip, before that). It isn't their balance. The groove
runs the length of the players' rail, round both corners and up the ends, as on a real table. The boxman's chip rack
is part of the table: the rail runs deeper across the floor of his bay, as a leather-padded ledge in front of him,
with the rack cut into it and rimmed in brass. Signed
off on Mike's Craps mockup (v1). The bet catalogue and
payouts are in the docstring of `server/casino_server/engines/craps.py`; the table's flow is in `tables/craps.py`.

## Bets

Bets stay on the layout from roll to roll; there's no Rebet. New chips are paid for when the dice go out (one
debit per seat per roll), and taking a paid-for bet down refunds it at once.
- **The line:** Pass Line and Don't Pass Bar 12 pay 1 to 1; odds behind them go up to 3-4-5x (lay odds 6x)
  and pay true odds.
- **Come and Don't Come:** the same for a new point, any roll after the come-out. They travel to their number,
  where you can take odds on them.
- **Place** 4/10 9 to 5, 5/9 7 to 5, 6/8 7 to 6. **Buy** pays true odds and **Lay** true odds against, for a
  5% vig. Each number box is split as in a casino, and a click on a strip is that bet: Lay along the top (where
  don't come bets go too), Place on the number, Buy along the bottom.
- **On a number box** the chips are drawn smaller (0.5 scale, 0.6 elsewhere; a come bet shrinks as it travels
  there), each player's across the box by where they stand: come bets in a row above the number, place bets in a
  row below it, so the number stays readable. The ON puck sits in the point's box's top corner nearer the middle,
  clear of both rows.
- **Odds on a come bet:** click your own come (or don't come) chip on its number. The odds sit on top of it,
  half a chip in towards the box's middle, and the pair shares one tag in your colour saying both ("5+10")
  instead of the chips' own numbers.
- **Field** (3, 4, 9, 10, 11 even money; 2 double, 12 triple), **Big 6** and **Big 8**.
- **Hardways** (4/10 7 to 1, 6/8 9 to 1) and the one-roll props: Any 7, Any Craps, 2, 3, 11, 12, Horn, C&E.
- £5 minimum on the main bets, £1 on hardways and props.
- **Whole pounds:** the house pays in chips, so a payout is paid down to the pound and the change stays with it
  (£5 placed on the 6 would win £5, not £5.83). Your chips go down in each bet's proper unit, so that never
  happens to you: a click adds your chip rounded up to the unit (a £5 chip places the 6 for £6, a £25 one buys
  the 9 for £26), and a right-click takes it off rounded down. The units: Place 6/8 £6 (others £5); Buy and odds
  4/10 £1, 5/9 £2, 6/8 £5; Lay and lay odds 4/10 £2, 5/9 £3, 6/8 £6; Horn £4; C & E £2. The ghost chip under the
  pointer shows what a click adds. NPCs bet in proper units too.
- **The vig** is whole pounds: £1 for every £20, rounded down, never less than £1 (so a £20 or £25 buy costs £1,
  and a lay that wins £20 -- £40 on the 4, £30 on the 5, £24 on the 6 -- costs £1). A **buy** bet's vig comes out of
  a win: the dealer pays the win in full beside the bet, then takes the vig chips off it into the rack. A **lay**
  bet's is paid up front: as the dice go out, a VIG chip goes from the player, past the bet, into the rack (it
  comes back if the bet's taken down). When a lay wins, the next decision's vig is taken off the win the same way,
  to keep it up. Either way it's one vig per decision: buy 4/10 1.67%, 5/9 2%, 6/8 2.27% of the bet; lay 4/10
  2.5%, 5/9 3.33%, 6/8 4.17% of the bet (2.44%, 3.23%, 4% of the bet and vig together).
- Place and buy bets, hardways and come odds are off on the come-out unless you mark them **working** (the
  dealer's OFF button sits on each, over the chips); come and don't come bets themselves, don't come odds, lay
  bets, Big 6/8 and the props always work, as in Vegas (a come-out 7 takes a come bet and returns its odds). Winning bets stay up and only the winnings come back, except come
  bets and their odds, which come back with them.

## A roll

1. **Betting:** the dice are in the middle and bets go down. An NPC shooter rolls when the 5-second window
   closes ("Dice out in 5"). A human shooter rolls with **Roll** (or **Space**) within 20 seconds, or the dice
   pass on.
2. **"Dice are out":** no more bets. The dice are drawn and their path is planned on the server
   (`engines/craps.plan_throw`), so every viewer sees the same throw bounce off the walls, the chips, the
   pucks and the dealer's OFF buttons. A die never comes to rest on one, or where a puck is about to slide to
   (or an OFF button will go up) once the roll is called.
3. **Settling:** the stickman calls it; the base dealers sweep the losers and pay the winners beside their
   bets (and take the vig off any buy or lay win); winnings go back to the players; come bets travel to their numbers; the puck turns over. Then
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

There's no craps in v2, so the tests check every bet's exact house edge against the published one (with the
vig: buy on a win, lay up front), that every proper unit pays whole pounds on every roll, the lay vig's money
flow, plus the table flow and a roll over the wire.
