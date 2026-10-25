# Pai Gow Poker (`pgf_1` Fortune, `pgu_1` Face Up)

53 cards, with a Joker that completes a Straight or Flush or else plays as an Ace.

## Bets

The Ante, plus the Fortune and £1 Jackpot side bets. They pay off your seven cards whatever happens to the
Ante.

## The deal

The shuffler shows a number from 1 to 7. Counting the dealer as 1, that position gets the first of seven
7-card hands; hands for empty seats are dealt to their place, then swept to the discard rack before the
reveal or the set.

## Setting your hand

You pick your cards up into the **sorter**, a panel over the bottom of the table. They arrive in no
particular order; **Sort** (**S**) puts them in order. Tap a card (or press **1**–**7**) to move it between
your 2-card **Low** hand and your 5-card **High** hand; it glides across, and the other cards shuffle along to
make room. The panel names both hands and warns you about a foul (the High hand must beat the Low).
**House Way** (**H**) sets it for you, and **Set hand** (**Space** or **Enter**) puts it down: the Low hand upright in the
LOW box, the High hand sideways in the HIGH box below it. If you run out of time, House Way sets it.

## The dealer's hand

All seven are turned over as dealt, then sorted, then the two Low cards are pushed forward and slid off to
the left. Each card always lies over the one to its left, so every index stays visible. The label reads
Low / High. At Fortune this happens once everyone has set; at Face Up it happens straight after the deal.

## Settling

Each player's hands turn over, then a tick or cross pops in beside the Low hand, and a beat later beside the
High hand. Win both hands against the dealer and the Ante pays 1:1, win one and it pushes. Ties go to the
dealer.

At both tables, £5 or more on Fortune also gets the **Envy Bonus** when another player hits Four of a Kind or
better. A small round green ENVY button (half a chip across) sits beside a qualifying bet. Folded hands
neither collect Envy nor trigger it.

- **Fortune Pai Gow:** a 5% commission on winning Antes.
- **Face Up Pai Gow:** no commission. The dealer's hand is set and shown before you set yours, and you may
  **Fold**: your cards are mucked unseen and every bet on them (Ante, Fortune, Jackpot) is lost at
  settlement. Folded hands settle first: their bets and cards are swept straight in, with no pause, before
  the first played hand turns over. A dealer Ace-high Pai Gow pushes every Ante. Nobody sets a hand then: if your cards win a side
  bet you **Claim bonus** (**Space**), otherwise you **Fold** (**Backspace**).

## A second box
Not offered at either Pai Gow table.

## NPCs

They set by the House Way. At Face Up they play the dealer's shown hand: they set to win if any split can,
else to push, else they fold (unless their cards win a side bet, which a fold would throw away).

## Fixes to v2

- A Joker with an Ace is now a pair of Aces. v2 split them, which made Face Up push Antes wrongly.
- A 5-card pair now beats a 2-card pair of the same rank, so the House Way's four-of-a-kind splits work. See
  the notes in `server/casino_server/engines/pai_gow.py`.
