# NPC and ledger data analysis (2026-11-04)

A look at what the live casino has recorded since it opened: how profitable it is overall and game by game, for
NPCs and for human players, and how much of the NPC play is tracked and in what detail. It covers 16 October to
3 November 2026.

The figures come from a read-only snapshot of `server/data/casino.sqlite` taken with SQLite's backup API, so the
live database wasn't touched. Money is stored in pence; everything here is in pounds.

## Summary

- **NPCs** staked £58.5M over 33,305 visits and 749,719 rounds. The house won £2.07M of it, a **3.54% hold**.
  Only 14 of the 100 punters are ahead over their lifetime.
- **Human players** (Mike, Jadzia and Slotty, all on Mike's account) staked £71,505 and were paid £77,293. The
  house is **down £5,788**, all of it at Blackjack.
- **Jackpot pools** hold about £31.9k: the shared Jackpot £17,385, and the slot progressives (Grand £10,417,
  Major £4,007, Minor £70, Mini £13). The stakes that fed them count as house winnings above, but they're owed
  back to whoever hits.
- NPC tracking is complete and consistent **per visit**, but there's nothing below that: no money by game, no
  bet spots, no table or casino. The per-game NPC figures below only work because NPCs almost never change game
  during a visit.
- The human ledger is **£25 short of Mike's cash in hand**, because the master-table relabel migration deleted 4
  rows (see [Problems](#problems)).

## What's recorded

| Table | Rows | What it holds |
|---|---:|---|
| `ledger` | 7,196 | Every money move for a human character: bet, payout, ATM, start, admin adjust |
| `npc_visits` | 33,305 | One row per NPC visit |
| `npcs` | 114 | 100 punters and 14 dealers, with each punter's lifetime totals |
| `slot_stats` | 8 | Running totals per slot machine, human and NPC, since 2026-10-22 22:06 |
| `players` / `accounts` | 3 / 1 | Mike's account and its three characters |

### Tracking, level by level

| Level | Humans | NPCs |
|---|---|---|
| Every bet and payout | Yes: one ledger row each, with game, note, signed amount and balance after | No |
| Bet spots (Ante, Pair Plus, Jackpot…) | Only since 2026-10-28, in the ledger's `detail` column | No: `NpcParticipant.debit/credit` ignore `detail` |
| Per visit | (No visits for humans) | Arrival and departure times, budget, final bankroll, staked, returned, rounds, why they left |
| Per game | Money by game, from the ledger | Round counts only (`npc_visits.games`), no money |
| Lifetime | Worked out from the ledger (`player_stats()`) | The `npcs` totals, which match the sum of their visits exactly |
| Slots | Per machine, since 2026-10-22 | Per machine, since 2026-10-22: spins, staked, returned, bonuses, jackpots |
| Which table, which casino | No | No |
| Dealers | | Nothing about their shifts is recorded |

Checks that passed:
- On every one of the 33,305 visits, budget minus final bankroll equals staked minus returned.
- The `npcs` lifetime totals equal the sums over `npc_visits`: staked, net, visits and rounds.
- Jadzia's and Slotty's ledgers add up to their cash in hand and bank. Mike's bank does too; his cash in hand
  doesn't (Problem 1).

What's missing:
- **NPC money by game.** Only round counts are kept per game. The per-game table below divides visits that
  played a single game, which is 99.7% of NPC stake: 27,748 visits played one game, 143 played two or more, and
  5,414 played none. If NPCs start moving between games, these figures can no longer be worked out.
- **NPC bet spots.** Without them we can't tell whether a game's hold comes from its main bet, side bets or the
  £1 Jackpot.
- **Rounds mean different things.** For slots, one counted round is about 10 spins: 2,580,872 NPC spins in
  `slot_stats` against about 258k slot rounds in visits since 22 Oct.
- **No casino or table ID** on visits or ledger rows. Only Demo has been open, so nothing is mixed up yet, but
  it will be once a second casino opens. Tables of the same game can't be compared either.
- **Human bet spots before 28 Oct.** About 6% of all ledger rows have `detail` (17% of Blackjack rows), so the
  older side-bet results can't be split out.

## Profit by game

### NPCs

Visits that played one game only, which is 99.7% of NPC stake:

| Game | Rounds (all visits) | Staked | House net | Hold | Stake per round |
|---|---:|---:|---:|---:|---:|
| Craps | 148,666 | £24,122,152 | £556,813 | 2.31% | £162.5 |
| Slots | 263,928 | £13,140,067 | £872,832 | 6.64% | £50.0 |
| Roulette | 185,662 | £8,781,751 | £209,794 | 2.39% | £47.5 |
| Blackjack | 68,304 | £4,099,470 | £68,172 | 1.66% | £61.4 |
| Baccarat | 16,378 | £3,492,252 | £51,961 | 1.49% | £213.2 |
| Ultimate Texas Hold'em | 9,173 | £1,007,141 | £84,687 | 8.41% | £111.3 |
| Mississippi Stud | 9,556 | £886,212 | £72,211 | 8.15% | £93.4 |
| Let It Ride | 8,805 | £861,769 | £91,155 | 10.58% | £99.0 |
| High Card Flush | 10,273 | £677,229 | £50,105 | 7.40% | £66.2 |
| Three Card Poker | 10,488 | £572,451 | £49,004 | 8.56% | £55.0 |
| Pai Gow Fortune | 9,246 | £378,002 | £780 | 0.21% | £41.5 |
| Pai Gow Face Up | 9,207 | £295,257 | £6,272 | 2.12% | £32.2 |
| Master Table | 33 | £7,421 | £29 | 0.39% | £224.9 |

- **Slots make the most money.** Craps gets the most action, but its edge is thin.
- **The five card-poker games hold 7–11%.** That's well above the base-game edges our simulations found
  (Hold'em 2.45%, Mississippi Stud 4.93%, High Card Flush 2.64%). Side bets and the £1 Jackpot could account for
  the difference, but NPC bets aren't recorded by spot, so this can't be confirmed from the data. Worth a
  simulation that uses NPC betting habits.
- **Pai Gow Fortune's 0.21% looks low.** Fortune pays out rarely but heavily, so on £378k it may just be luck.
  It's worth the same simulation.

NPC slots by machine, from `slot_stats` (since 22 Oct):

| Machine | Spins | Staked | Returned | Hold | Bonuses | Jackpots |
|---|---:|---:|---:|---:|---:|---:|
| Star Trek | 1,010,437 | £5,038,968 | £4,697,019 | 6.79% | 6,048 | 3,855 |
| Voyager | 1,006,455 | £4,814,034 | £4,670,383 | 2.98% | 8,788 | 3,776 |
| Armadillo Goes West | 279,515 | £1,543,124 | £1,400,433 | 9.25% | 2,534 | 1,206 |
| Pirates | 284,465 | £1,491,069 | £1,353,696 | 9.21% | 2,428 | 1,104 |

Together that's £12.9M staked, in line with the £13.1M of slot visits in the table above, which start four
days earlier.

### Humans

| Game | Bets | Staked | Returned | House net | Hold |
|---|---:|---:|---:|---:|---:|
| Blackjack | 991 | £16,680.00 | £24,751.87 | −£8,071.87 | −48.4% |
| Three Card Poker | 1,059 | £13,751.00 | £13,395.00 | +£356.00 | 2.6% |
| Craps | 663 | £10,052.00 | £9,598.53 | +£453.47 | 4.5% |
| Pai Gow Fortune | 351 | £9,865.00 | £10,576.25 | −£711.25 | −7.2% |
| Ultimate Texas Hold'em | 251 | £4,887.00 | £4,543.50 | +£343.50 | 7.0% |
| Baccarat | 242 | £4,403.00 | £4,396.25 | +£6.75 | 0.2% |
| Let It Ride | 107 | £3,048.00 | £2,498.00 | +£550.00 | 18.0% |
| Pai Gow Face Up | 108 | £2,583.00 | £2,418.00 | +£165.00 | 6.4% |
| Mississippi Stud | 302 | £2,498.00 | £2,193.00 | +£305.00 | 12.2% |
| High Card Flush | 144 | £1,917.00 | £1,188.00 | +£729.00 | 38.0% |
| Roulette | 48 | £1,384.00 | £1,360.00 | +£24.00 | 1.7% |
| Slots | 353 | £437.00 | £374.19 | +£62.81 | 14.4% |

Mike accounts for nearly all of it: the house is down £5,873 to him, up £153 on Jadzia and down £67 to Slotty.

The Blackjack loss comes from a few side-bet hits:
- **One payout of £5,964.87** on 2026-10-18, noted "side bets", is 74% of the Blackjack deficit. Its odd pence
  suggest a share of the shared Jackpot, but it predates `detail`, so that can't be confirmed.
- **The five biggest side-bet payouts** total £10,099. Without them, the house is up about £2,000 on Blackjack.
- **Side-bet payouts overall** came to £14,257 over 206 rows.

The human samples are small, so the per-game holds are mostly variance.

## NPC behaviour

### Archetypes

| Archetype | Visits | Staked | House net | Hold | Bust rate | Average budget |
|---|---:|---:|---:|---:|---:|---:|
| Grinder | 8,395 | £33.2M | £837k | 2.52% | 7.6% | £2,547 |
| Casual | 20,185 | £19.6M | £1,013k | 5.17% | 1.8% | £28,672 |
| Gambler | 4,725 | £5.7M | £221k | 3.87% | 2.6% | £3,948 |

Casuals' average budget is pulled up by a few whales. Across all visits, the median budget is £501 (10th
percentile £190, 90th £1,844, highest £998,427).

### Traits

Visits by NPCs with each trait (an NPC with several traits is counted under each):

| Trait | Visits | Staked | Hold |
|---|---:|---:|---:|
| Whale | 3,150 | £36.1M | 3.50% |
| Regular | 7,318 | £33.4M | 2.63% |
| (none) | 19,451 | £12.9M | 3.92% |
| VIP | 1,084 | £9.0M | 3.20% |
| Chaser | 3,180 | £3.5M | 3.86% |
| Card counter | 2,346 | £2.6M | 3.68% |
| Superstitious | 2,421 | £1.3M | 3.97% |
| Hit and run | 1,664 | £1.3M | 0.98% |

- **Whales and regulars bring most of the action:** 68.7% of all NPC stake comes from NPCs with either trait.
- **Hit-and-run NPCs hold 0.98%,** which suggests the trait works: they leave while they're ahead.
- **Card counters hold 3.68%,** but most of their stake isn't at Blackjack. This data can't tell whether
  counting pays off at the shoe.

### How visits end

| Reason | Visits | Average length | Average rounds | House net | Hold |
|---|---:|---:|---:|---:|---:|
| Done | 27,210 | 15.7 min | 23.9 | £1,636,078 | 3.3% |
| Shutdown | 4,335 | 18.9 min | 13.2 | £401,803 | 7.1% |
| Bust | 1,124 | 24.0 min | 34.5 | £1,033,172 | 36.1% |
| Riches | 455 | 3.2 min | 3.2 | −£888,378 | −271.7% |
| Hit and run | 179 | 10.5 min | 13.4 | −£111,048 | −74.8% |
| Kicked / admin | 2 | | | −£451 | |

- **13% of visits were cut short by a server restart:** 145 restarts in 17 days.
- **Shutdown visits hold more than finished ones.** At any moment, the NPCs still on the floor lean towards
  losers, because winners tend to leave early ("riches", "hit and run"). It isn't lost stakes:
  `TableRunner.hand_back` refunds what's riding.
- **The median visit is 10 minutes.** NPCs have spent 8,972 hours on the floor in total.

### Notable NPCs

| | NPC | Archetype | Traits | Visits | Staked | Lifetime net |
|---|---|---|---|---:|---:|---:|
| Best | Queenie | Gambler | | 270 | £266,024 | +£21,844 |
| | Wes | Casual | Superstitious, regular | 487 | £146,379 | +£19,235 |
| | Teddy | Grinder | Chaser | 208 | £421,679 | +£8,452 |
| Worst | Phil Ivey | Casual | Whale, VIP, regular | 1,084 | £9,006,030 | −£288,558 |
| | Ray | Casual | Whale | 440 | £2,635,299 | −£278,593 |
| | Reggie | Grinder | Whale, regular | 482 | £17,102,231 | −£261,971 |
| | Vic | Grinder | Whale, regular | 268 | £3,197,127 | −£206,918 |
| | Theo | Casual | Whale | 441 | £2,603,577 | −£169,929 |

- **Reggie is the busiest NPC by far,** almost all of it at craps. His single visits swing between +£71,500 and
  −£42,105.
- **The biggest single visit win** was Phil Ivey's: +£47,902 at the slots.

### By day

The hold moves between −0.7% (23 Oct, the day the bank opened) and 7.7%, with no trend. Activity peaked at
4,922 visits on 24 Oct; since 30 Oct it has run at 1,200–1,600 visits a day.

## Problems

1. **Mike's cash in hand is £25 more than his ledger adds up to.** The 2026-10-25 migration that relabelled
   `master_table` rows to their real game relabelled 41 rows to `three_card_poker`, but deleted four:
   - id 3123: bet, −£9
   - id 3124: side-bet payout, +£40
   - id 3125: bet, −£5
   - id 3189: bet, −£1

   That's +£25 net. The balance chain breaks at ids 3126 and 3190 because of it.

   **Fixed 2026-11-04:** `tools/restore_ledger_rows.py` copied the four rows back from
   `server/data/casino.pre-master-relabel.sqlite`. 3123–3125 went back as Blackjack (one hand; "side bets" is
   Blackjack's note) and 3189 as `master_table`. The ledger now adds up to Mike's cash in hand, with no chain
   breaks.
2. **335 visits staked money without any game being counted** (£28k between them). 279 of those were cut off
   by a restart before their first round finished. Their money is in the totals, but not in any game.

## Recommendations

In order of value:

1. ~~Put the four deleted ledger rows back~~ (done 2026-11-04).
2. **Record NPC money per game.** Keep `{game: {rounds, wagered, returned}}` in `npc_visits.games` instead of
   round counts. It's a small change in `NpcDirector._round_over` and `NpcParticipant`, and it makes the
   per-game figures exact whatever NPCs do.
3. **Record the casino and table** on `npc_visits` and the ledger (or the `detail` JSON). This is needed before
   a second casino opens.
4. **Record NPC bet spots**, as a running total per visit (`{game: {spot: [staked, returned]}}`) rather than a
   row per bet. That would explain the 7–11% holds on the card-poker games. One row per NPC bet would be about
   750k rows in 17 days, too many to keep.
5. **Simulate Pai Gow Fortune and the poker side bets** with NPC betting habits, to see whether their holds are
   luck.

## Reproducing this

1. Take a read-only snapshot, so nothing is written to the live database:

   ```python
   import sqlite3
   src = sqlite3.connect("file:server/data/casino.sqlite?mode=ro", uri=True)
   dst = sqlite3.connect("/path/to/snap.sqlite")
   src.backup(dst)
   ```

2. Run the queries against the snapshot:
   - **Human figures:** group `ledger` rows of kind `bet` and `payout` by `game`. A bet row with a positive
     amount is a stake handed back.
   - **NPC per-game figures:** sum `wagered` and `returned` over the `npc_visits` rows whose `games` JSON has
     exactly one key.
