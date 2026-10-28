# Roulette (`rou_1`)

Single zero with La Partage. Signed off on the Roulette mockup (claude.ai artifact, v6).

## The table

A long table rounded at the wheel end, with a bay where the dealer stands between the wheel and the layout.
The float (for paying winners) is left of the bay and the chip hole (where losing chips go) is right of it.
The results sign stands at the far end (or the other: the floor plan's Sign), showing the last 12, with reds right, blacks left and zero in the
middle.

## Bets

Chips anywhere on the standard layout, in your seat's own colour.
- The middle of a box is a straight up, a side a split, a corner a corner.
- The bottom edge of the 1-4-7 row is a street; on a line between two streets, it's a six line.
- The zero's edge gives the 0-1, 0-2 and 0-3 splits, the two trios and the first four.
- Hovering lights up the numbers a bet covers, and the bar names it and its payout.
- Right-click takes a chip off. **Undo** takes back your last chip this round.
- You can't queue bets while sitting down mid-spin: wait for the next spin's betting (late bets during the
  spin are a separate thing).

## Limits

£1 a bet; at most £100 straight up, £200 a split, £300 a street, £400 a corner, £600 a line, £1,000 a column
or dozen, £2,000 an even chance.

## The spin

"SPINNING IN ..." counts down from the first bet (25s; 8s with only NPCs), or Ready spins sooner.
- The dealer launches the ball: "FINAL BETS!" until just before it reaches the pockets (7.3s of its 7.6s run).
- At "No more bets" the number is drawn (and only then). The server then plans the landing that carries the
  ball from where it reaches the pockets to that number: skids over the frets, slowing, then a few small
  hops. That's anything from a short stop to most of a lap, about 2-8s.
- Then the dealer calls it and the dolly goes on the number. Losing chips fly down the hole (half of each
  even-money stake on a zero), winners are paid from the float, everything goes back, and the dolly comes off.

## Payouts

35, 17, 11, 8, 5, 2 and 1 to 1. The house edge is 2.70% (1.35% on the even chances).

The round summary under your wallet is titled with the number and calls out the inside bets that hit (straight up,
splits, streets, trios, corners and the first four), biggest first.

## NPCs

Each has a habit: lucky numbers, the even chances, dozens and columns, or a sprinkle of splits, corners,
streets and lines. They put chips down one at a time and sometimes slip in a late bet.

## The ball

The ball is choreographed, not simulated, and every viewer sees the same one. The spin sends the launch
angle, so where the ball reaches the pockets is known from the start, but the number isn't. The arithmetic
(`track_travel`, `arrival_pocket`, `plan_landing`, `landing_seconds`) lives in both `engines/roulette.py` and
`scenes/table/roulette_wheel.gd`; keep the two in step.
