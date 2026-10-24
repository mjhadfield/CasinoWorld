# Mississippi Stud (`ms_1`)

## Bets

The Ante, plus the 3 Card Bonus and the £1 Jackpot. You need ten times your Ante to sit a hand, enough to bet
3x on every street.

## The deal

Two cards each, out of the shuffler, and only you see yours. Three community cards go face down in front of
the dealer.

## 3rd, 4th and 5th Street

Everyone decides at once on one timer. **Fold** (**F**), or bet **1x**, **2x** or **3x** your Ante
(**1**/**2**/**3**). Running out of time folds. After each street the dealer sweeps the folds and turns the
next community card.

## A second box
With a second box (README, Betting at the card tables), Box 2's hole cards turn over for you once Box 1 has
decided 3rd Street, and on every street Box 1 decides before Box 2.

## Settling

Your two cards plus the three community cards. Every bet still in play pays the same: Royal 500:1, Straight
Flush 100:1, Quads 40:1, Full House 10:1, Flush 6:1, Straight 4:1, Trips 3:1, Two Pair 2:1, Jacks or better
1:1. A pair of 6s to 10s pushes.

**A fold** loses the Ante, the street bets and the Jackpot. The 3 Card Bonus still pays on the community
cards: every folded Bonus is settled together, at once. If everyone folds and no Bonus is riding, the hand
just ends.

## NPCs

They think for at most 3 seconds and follow Joseph Kisenwether's strategy
(`engines/mississippi_stud.py: strategy`); a Gambler bets 3x where the chart says 1x. A slip
(`npc_slips.py`) is one step off the chart: 1x instead of 3x on a draw, fold or 3x instead of 1x, or 1x on
a hand the chart folds. On 5th Street neither the Gambler nor a slip goes to 3x unless the hand is one
someone would back (`mississippi_backs`: a low pair, an open-ended straight draw or three high cards), so
a gutshot or a couple of picture cards stays at 1x (or a timid fold). A made hand (6s or better) is always
bet 3x. A 9.6-million-hand simulation of
the chart gives a house edge of 4.93% ± 0.32% of the Ante, in line with the published 4.91%.
