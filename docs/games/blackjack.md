# Blackjack (`bj_1`, and `bj_2`..`bj_5` in the pit room)

3:2 for a Blackjack, dealt from a real 8-deck shoe. The shoe carries on from hand to hand, and the discards
pile up in the rack, until the yellow cut card comes out. That hand is the last one; then the discards and
the rest of the shoe go through the shuffler and a fresh shoe goes in.

## Bets

The Blackjack circle, plus the side bets from v2: Super Pairs, 21+3, Top 3 (with a 21+3 bet) and the £1
Jackpot. Side bets settle straight after the deal: a box's losing side bets are swept together in one quick
motion, then each winner is paid in turn. Winnings stay beside their spots until the hand is over.

## The deal

One card at a time to every box, the dealer's up-card, a second card each, and the hole card face down. With
an Ace showing, everyone can take **Insurance** (**Space**) or decline (**Backspace**). With an Ace or a 10 showing, the
dealer checks the hole card for Blackjack. Once the dealer can't have Blackjack, any player Blackjack is paid
3:2 straight away. A Dealer Blackjack that beats everyone (no player Blackjack to push) is swept in one quick
go, box after box, with no settling each hand in turn.

## Your turn

Boxes play in turn from first base. **Hit** (**Space**), **Stand** (**Backspace**), **Double** (**D**, on any two cards,
also after splitting) or **Split** (**P**, any pair, up to 4 times; split Aces get one card each). You have
20 seconds per decision; out of time stands. A bust is swept at once. Hit and Stand are always in the middle of
the betting bar, in the same place every time, with Split on their left and Double on their right when they're
offered.

Each hand's total sits just above its first card and stays put as the hand draws. Split hands sit a card's width
apart with their bets in a row above them, so their totals are short: a soft total shows both counts (`7/17`).

## A second box
With a second box (README, Betting at the card tables), each box is offered insurance and takes its turn in seat
order like any other seat. Every card's face up, so nothing waits on Box 1.

## The dealer

Draws to 17 and stands on all 17s. Boxes are then settled from third base. A dealer bust ("Everyone's a
winner!") needs no checking: every hand still in is paid, one after another with a short gap (`pay_gap`,
0.22s), and there's no line per box.

## NPCs

They play the basic strategy chart, and a Gambler doubles any 9-11 the chart hits. Casuals and Gamblers
(15% of the time, Grinders never) slip on a close call (`npc_slips.py`):

- **Casual (timid):** stands on 12-16 against a 7-A, hits 12 against a 4-6, doesn't double (hits, or stands
  on a soft 18 or 19), stands on a soft 17 or 18 against a 9-A, doesn't split (8s against a 10 or
  Ace stand on 16).
- **Gambler (reckless):** splits 10s against a 5 or 6, doubles a soft 19 against a 3-5 or a hard 8 against
  a 5 or 6.

Nobody ever hits a hard 17+, stands on 11 or less, doubles a hard 12+, splits 5s or plays Aces as anything
but a split. Insurance (or even money): a Card counter on a true count of +3, otherwise a Casual 15% of the
time, a Gambler 8%, a Grinder never.
