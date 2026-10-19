# Three Card Poker (`tcp_1`)

The rules are ported from v2's `games/three_card_poker/logic.py`.

## Bets

Pair Plus, Ante, Prime, and the £1 Jackpot.

## The deal

Each hand comes out of the shuffler as a packet of three and is then dealt across.

## Deciding

Once the cards are dealt, everyone decides at the same time.
- **Play** (**P**) matches your Ante. Your cards go face down, sideways, on the Play box, with the bet on top.
- **Fold** (**F**) puts your cards in a messy face-down pile. A fold loses your Ante, Pair Plus and Jackpot
  bets. The exception is a Prime bet on three cards of one colour, which has already won: you tuck your
  cards under it, and it's paid at settlement.
- There's a shared 20-second timer, which ends once everyone has decided, and anyone still undecided folds.
  NPCs take 2–10 seconds.

## Settling, one step at a time

1. The dealer takes the folded hands and their bets.
2. The dealer turns their own cards over and announces them.
3. The dealer settles each remaining player in turn, left to right on screen (third base to first). The
   player's cards slide out from under the bet and are turned over, and the dealer announces the hand
   ("Pair of Kings, wins."). After a pause, the losing bets are swept, the winnings are placed beside the
   stakes, and the cards are cleared away. There's another pause before the next player.
4. Once everyone is settled, the winnings go back to the players and the next round begins.

Folded and settled hands go face down into the discard rack and stay there until the end of the hand, when
the dealer feeds the whole rack into the shuffler.

## NPCs

They play basic strategy: Q-6-4 or better.
