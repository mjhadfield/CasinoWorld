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

## Settling

Your two cards plus the three community cards. Every bet still in play pays the same: Royal 500:1, Straight
Flush 100:1, Quads 40:1, Full House 10:1, Flush 6:1, Straight 4:1, Trips 3:1, Two Pair 2:1, Jacks or better
1:1. A pair of 6s to 10s pushes.

**A fold** loses the Ante, the street bets and the Jackpot. The 3 Card Bonus still pays on the community
cards: every folded Bonus is settled together, at once. If everyone folds and no Bonus is riding, the hand
just ends.

## NPCs

They think for at most 3 seconds and follow Joseph Kisenwether's strategy
(`engines/mississippi_stud.py: strategy`). A 9.6-million-hand simulation gives a house edge of
4.93% ± 0.32% of the Ante, in line with the published 4.91%.
