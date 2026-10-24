# Ultimate Texas Hold'em (`uth_1`)

## Bets

Ante, with an equal Blind placed automatically. Trips and the £1 Jackpot are optional. You need six Antes to
play a hand (Ante, Blind and a 4x Play).

## The deal

Two cards each (private), two to the dealer, five community cards, all face down.

## Decisions

Everyone decides at once at each stage, and once your Play bet is down you're done.
- Before the flop: bet **4x** (**4**) or **3x** (**Space**), or **check** (**Backspace**).
- After the flop: **2x** (**Space**) or check (**Backspace**).
- After the river (the turn and river are turned together): **1x** (**Space**) or **fold** (**Backspace**).
- Running out of time checks, or folds after the river.

## A second box
With a second box (README, Betting at the card tables), Box 2's hole cards turn over for you once Box 1 has
decided before the flop, and at each stage Box 1 decides before Box 2.

## Settling

The dealer qualifies with a pair; if not, the Ante pushes. The Blind pays only on a Straight or better win. A
fold loses the Ante, Blind, Trips and Jackpot. The Jackpot is judged on your hole cards plus the flop.

## NPCs

They follow the Wizard of Odds' simple strategy, including the "fewer than 21 dealer outs" river rule;
a Gambler gets the money in on 40% of the hands it would check or fold. Slips (`npc_slips.py`) are close
calls only: before the flop a J/Q/K-high, a weak Ace (A-2 to A-5) or a small pair (2s-5s); on the flop a
single pair (checking a hidden one, betting a board pair); after the river a hand with 14-27 dealer outs. A
hidden pair or a made straight or flush is never folded.
Simulated house edge: 2.45% ± 0.31% (published 2.43%).
