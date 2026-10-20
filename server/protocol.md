# Casino World protocol (v3)

Messages are JSON objects with a `type` field, carried over a WebSocket at `/ws`.
The server is authoritative, so the client sends intents and renders what comes back.
Money is always an integer number of **pence**. Cards are codes like `"Qs"` or `"10h"`, and
`"??"` is a face-down card.

## Connecting
1. The server sends `hello` {`protocol`}.
2. The client replies `join` {`token`}. On a device's first visit the token is `""`; after that
   it's the one saved from `welcome`.
3. The server sends, in order:
   - `welcome`
   - `wallet`
   - `jackpot`
   - `world_snapshot`
   - one `table_state` per table
   - your own `entity_spawn`, which everyone receives

## Client → server
| type | fields | meaning |
|---|---|---|
| `join` | `token` | Identify, or create a new player. Must come first. |
| `set_name` | `name` | Choose a display name, up to 16 characters. The reply is a fresh `welcome`, and everyone gets `entity_update`. |
| `move` | `x`, `y`, `dir`, `anim` | Your avatar's position on the floor, sent about 10 times a second while moving. It's ignored while you're seated. |
| `sit` | `table`, `seat` | Sit at a seat (0–5; seat 0 is first base, the dealer's left). |
| `stand` | | Stand up. At Three Card Poker, standing before you've acted on a hand folds it; at Blackjack it stands every hand you still have to play (they're settled as normal). |
| `bet` | `spot`, plus `add` or `amount` | Change a bet while betting is open, or at any time if you're not in the hand being played: those bets are queued for the next hand (not at Roulette). `add` is relative, so rapid clicks don't race the echo; `amount` is absolute. `spot` is `ante`, `pair_plus`, `prime` or `jackpot` at Three Card Poker, and `bet`, `super_pairs`, `twenty_one_plus_three`, `top_three` or `jackpot` at Blackjack (the jackpot bet is exactly £1 or 0; Top 3 needs a 21+3 bet). |
| `clear_bets` / `rebet` | | Remove all your bets, or repeat last hand's bets. A rebet in the betting window cuts the countdown to 3 seconds (a quiet `betting_timer`) unless it's due sooner; NPCs at the table bet before it runs out. Queued for the next hand, it cuts that hand's countdown the same way. |
| `auto_rebet` | `on` (bool) | Tick or untick Auto rebet: as each hand ends, last hand's bets go back down as a rebet. Ticked in the betting window with nothing down, it rebets at once. Timing out of any decision unticks it. |
| `ready` | | Lock your bets in. Ready with no bets means sitting this hand out. |
| `decide` | `play` (bool) | Three Card Poker: Play (matches the Ante) or Fold. |
| `insure` | `take` (bool) | Blackjack, while insurance is open: insure for half your bet, or decline. |
| `act` | `action` | Blackjack, on your turn: `hit`, `stand`, `double` or `split` (only what the `turn` event offered). |
| `set_hand` | `front` [2 codes], `back` [5 codes] | Pai Gow, while setting: your Low and High hands. A foul (High not beating Low) is refused. |
| `fold` | | Face Up Pai Gow, while setting: muck your cards unseen and lose every bet (Ante, Fortune and Jackpot); `cards` in your `settle_seat` is empty. While claiming after a dealer Ace-high Pai Gow: muck your cards unseen (the Ante still pushes). |
| `claim` | | Face Up Pai Gow, while claiming: show your cards to collect a side-bet win. |
| `pg_suggest` | | Pai Gow: the House Way split of your own cards. The reply `pg_suggest` {`front`, `back`, `front_label`, `back_label`} goes only to you. |
| `pg_check` | `front`, `back` | Pai Gow: name a proposed split and say if it fouls. The reply `pg_check` {`front`, `back`, `front_label`, `back_label`, `foul`} goes only to you. |
| `top_up` | | Get £1,000 more. Only allowed when you can't afford a £1 Ante plus Play. |
| `ping` | `t` | A latency check. |
| `away` | | The tab was hidden. The server sends nothing more until `resync`; you stay on the floor (and seated). |
| `resync` | | The tab is visible again. Drop every message until the `resync` reply; the full state follows it. |

## Server → client
| type | fields | when |
|---|---|---|
| `welcome` | `player` {`id`, `name`}, `token`, `entity_id`, `look`, `needs_name`, `cabinets` | The reply to `join` and `set_name`. `cabinets` lists the cabinets of slots built with the Slot design wizard, which aren't in the floor scene: [{`id`, `variant`, `name`, `x`, `y`, `facing`, `cabinet` (its look: `body`, `trim`, `title`, `lines`)}]; the client adds any it doesn't have. |
| `wallet` | `balance` | Sent on join and after each money-moving table event, straight after that event. |
| `jackpot` | `amount`, `rate` (pence/s), `ceiling` | Sent on join and after a jackpot win. The client extrapolates the meter between updates. |
| `world_snapshot` | `entities[]` | Everyone already on the floor. |
| `entity_spawn` | `entity`, `at` | Someone arrived. `at` is a floor point name, used while `x` is null. |
| `entity_move` | `id`, `x`, `y`, `dir`, `anim` | Another player moved. |
| `entity_walk` | `id`, `target`, `duration` | An NPC heads for `point:<name>` or `seat:<table>:<n>`. The client paths them there in `duration` seconds. |
| `entity_update` | `id`, `name`?, `look`? | Someone renamed, or an NPC was restyled on the admin page (a `look` id starting `x_` is a server-built sheet at `/looks/<id>.png`). |
| `entity_despawn` | `id` | Someone left. |
| `seated` | `table`, `seat`, `rules` | You sat down. `rules` holds the paytable, `chips`, `min_ante` and `seats`. A `table_state` follows. |
| `table_state` | `table`, `game`, `phase`, `seats[]`, `dealer` (the game's dealer state), `timer`, `my_seat`, `on_duty` {`id`, `name`, `look`} for who's dealing (from the dealer roster), plus at Blackjack `turn`, `shoe`, `discards` | The whole table as you may see it. Sent on join, and when you sit. |
| `table_event` | `table`, `event` | Something happened at a table. Every joined player gets every table's events (see below). |
| `notice` / `error` | `message` | Information, or a rejected action. |
| `pong` | `t` | The reply to `ping`. |
| `resync` | `table`, `seat` | The reply to `resync`: where you're seated now (null if you were stood up while away). Then `wallet`, `jackpot`, `world_snapshot` and one `table_state` per table, as on join. Before joining, it's followed by `hello` instead. |
| `sounds_changed` | `version` | The sound choices changed on the admin page. The client refetches `GET /api/sounds/manifest`. |

An entity is {`id`, `kind` (`player`/`npc`), `name`, `look`, `x`, `y`, `dir`, `anim`, `seat`,
`walk`}. Floor point names live in `casino_server/floor.py`, and each must exist as a
`Marker2D` in the client's floor scene.

### Three Card Poker table events (`event.kind`)
These are listed in the order a round produces them.

| kind | fields | meaning |
|---|---|---|
| `seated` / `stood` | `seat`, `entity`, `name`, `human` / `reason` | Someone sat down or got up. The `reason` for standing can be `inactive` (sat out 3 hands) or `left`. |
| `bet_changed` | `seat`, `bets`, `queued`? | A seat's chips changed during betting. With `queued: true`, they're for the next hand, put down during this one. At `betting_open` the queued bets go on as ordinary `bet_changed` events, and the countdown starts. |
| `queued_dropped` | `seat`, `reason` | Bets queued during the last hand that couldn't go on (for example, the balance no longer covers them). |
| `betting_timer` | `seconds`, `quiet`? | The first bet went down, and betting closes in this many seconds (sooner once every human is Ready). `quiet: true` after a rebet: no countdown ticks. |
| `auto_rebet` | `seat`, `on`, `reason`? | A seat's Auto rebet was ticked or unticked. `reason` says why it went off by itself: `timeout`, or the rebet's error (such as the balance not covering it). Seat entries in snapshots carry `auto_rebet` too. |
| `ready` | `seat` | That seat locked in. |
| `bets_closed` | `seats`, `jackpots` | "No more bets." Upfront bets have been taken. For the seats in `jackpots`, the dealer locks the Jackpot bets in: the lights under the plastic Jackpot discs go from flashing to solid red, and the Jackpot chips are lifted off the table before the deal. Each light stays on until that player is settled. |
| `dealt` | `order`, `interval`, `hand_pause`, `mine` | Cards dealt in `order`, three at a time: all three of first base's cards, then the next seat's, and so on, with the dealer's own three last ([[seat, 0], [seat, 1], [seat, 2], …, ["dealer", 2]]). The cards of one hand are `interval` seconds apart, with `hand_pause` seconds between hands. (The client shows each hand coming out of the shuffler as a packet, resting a moment, then flying to its place.) `mine` {`cards`, `hand`} goes only to the seat it belongs to. |
| `decisions_open` | `seconds`, `seats` | Everyone dealt in now decides **at once** before the timer runs out. The timer ends early once the whole table has decided. Anyone still undecided folds. |
| `decision` | `seat`, `play`, plus `amount` or `held`, `reason` | A Play (the cards go face down, sideways, on the Play box with the Play bet on top) or a Fold (the cards go in a messy face-down pile). `held` means three cards of one colour with a Prime bet: the cards go under the Prime bet instead. `reason` can be `timeout` or `left`. |
| `fold_sweep` | `seats[]` {`seat`, `muck`, `steps[]` {`spot`, `amount`}}, `pause` | Once everyone has decided, this is the dealer's first move: it takes the folded hands and their bets. A fold forfeits the Ante, Pair Plus and Jackpot (a house rule). `muck` is false for a held fold, which keeps its cards and the Prime bet. The hands go one at a time, with `pause` seconds before the first and between each. |
| `dealer_reveal` | `cards`, `hand`, `qualified` | The dealer turns their own cards over. A `say` with the announcement follows. |
| `settle_seat` | `seat`, `cards`, `hand`, `held`, `outcome`, `steps[]`, `net`, `total_returned`, `say`, `pause` | One player settled, from third base back to first. Their cards come out from under the bet and are turned over, and nobody else's are shown yet. Steps run in order: losing bets swept (`collect`), then `push`, then winners paid (`pay`, plus `bonus` for the Ante Bonus). `say` is the dealer's announcement ("Pair of Kings, wins. Nice hand!") as the cards are turned over. Then the order is: `pause`, losing bets swept, winners paid (they stay beside the stakes), the cards cleared away last, then `pause` before the next player. Seats with nothing left on the felt are skipped. |
| `jackpot_won` | `seat`, `amount`, `name` | The spades Royal Flush hit the progressive jackpot. |
| `round_end` | | Everyone is settled: all the chips on the felt go back to their players, then the dealer's cards go to the discard rack. |
| `betting_open` | | A new hand: place your bets. |
| `say` | `text` | A line for the dealer's speech bubble. |
| `betting_reset` | | Betting closed with no Antes down, so the table stays open. |

### Blackjack table events (`event.kind`)
Seating, betting, `bets_closed` (with the Jackpot lock), `say`, `round_end`,
`betting_open` and `betting_reset` work exactly as at Three Card Poker. The
shoe is 8 decks, dealt down across many hands; player cards are dealt face
up, so they're public.

| kind | fields | meaning |
|---|---|---|
| `dealt` | `order`, `interval`, `cards` {seat: [two codes]}, `labels` {seat: total}, `dealer_up`, `shoe` | One card at a time out of the shoe, `interval` seconds apart: a card to each box from first base, the dealer's up-card, a second card each, then the hole card face down (`order` lists them, e.g. [[0, 0], ["dealer", 0], [0, 1], ["dealer", 1]]). `shoe` {`remaining`, `total`, `cut`, `cut_out`} is the shoe after the deal. |
| `cut_card` | | The cut card came out: this is the last hand before the shuffle. |
| `side_bets` | `seats[]` {`seat`, `steps[]` {`spot`, `action`, `amount`, `payout`}, `hand`, `returned`}, `pause` | Super Pairs, 21+3, Top 3 and the Jackpot settle straight after the deal off the first two cards and the up-card: losers swept (`collect`), winners paid (`pay`) beside their spots, where stake and winnings stay until `round_end`. |
| `insurance_open` | `seconds`, `seats`, `costs` {seat: pence} | An Ace showing: everyone may insure, at once, for half their bet. Ends early once all have decided; anyone undecided declines. |
| `insurance` | `seat`, `take`, `amount`, `reason` | A seat's insurance decision. |
| `peek` | | An Ace or 10 showing: the dealer checks the hole card. |
| `dealer_reveal` | `cards`, `label`, `blackjack` | The hole card is turned over: after the peek if it's a Dealer Blackjack (every box then settles), or once every box has played. |
| `insurance_settled` | `seats[]` {`seat`, `action`, `amount`, `payout`} | Insurance pays 2:1 on a Dealer Blackjack, otherwise it's taken. |
| `blackjacks_paid` | `seats[]` {`seat`, `hand`, `amount`, `payout`}, `say`, `pause` | Once the dealer can't have Blackjack (after the peek, or straight after the deal with a 2-9 showing), every player Blackjack is paid 3:2 at once; the winnings stay beside the bet until `round_end` and the cards go to the discard rack. |
| `turn` | `seat`, `hand`, `seconds`, `options`, `total` | Whose decision it is (each box in turn from first base, each hand in turn after a split), what they may do, and their time. Out of time stands. |
| `action` | `seat`, `hand`, `action`, `total`, `done`, plus `card`, `amount`, `hands`, `labels`, `reason` | A Hit (`card`), Stand, Double (`amount` added, one `card` dealt sideways) or Split (`amount` added; `hands` are the two new hands' cards, each dealt a second card). `reason` can be `timeout`. |
| `bust` | `seat`, `hand`, `amount` | Over 21: the dealer takes the hand's bet and cards straight away. |
| `dealer_draw` | `card`, `label` | The dealer draws to 17 (standing on all 17s); no draws if every hand has bust. |
| `dealer_done` | `total`, `bust` | The dealer stands or busts. A `say` follows. |
| `settle_seat` | `seat`, `hands[]` {`hand`, `outcome`, `label`, `action`, `amount`, `payout`}, `say`, `pause`, `total_returned` | One box settled, third base back to first, hand by hand: losers swept, pushes left, winners paid beside the bet (Blackjack 3:2). The cards go to the discard rack last. |
| `shuffle` | `seconds` | After a hand in which the cut card came out: the discards and the rest of the shoe go through the shuffler. |
| `shoe_loaded` | `shoe` | A freshly shuffled shoe with a new cut card. Betting opens. |

### Pai Gow table events (`event.kind`)
Fortune Pai Gow (`pgf_1`) and Face Up Pai Gow (`pgu_1`). Seating, betting
(`ante`, `fortune`, `jackpot`), `bets_closed` (with the Jackpot lock), `say`,
`round_end`, `betting_open` and `betting_reset` work as at the other tables.

| kind | fields | meaning |
|---|---|---|
| `dealt` | `start`, `order`, `interval`, `mine`, plus `dealer` and `ace_high` at Face Up | A fresh 53-card deck through the shuffler. `start` (1-7) is the shuffler's number: counting the dealer as 1 and seats 0-5 as 2-7, that position gets the first of seven 7-card hands. `order` lists who each hand went to (a seat, `"dealer"`, or null for an empty seat, whose hand is dealt to its place and swept to the discard rack once the deal is done, before anything else happens). `mine` {`cards`} only goes to you. Face Up: `dealer` {`cards`, `front`, `back`, `front_label`, `back_label`} is the dealer's hand, set by House Way and shown at once. |
| `ace_high_pai_gow` | | Face Up only: the dealer's seven cards make nothing but Ace high, so every Ante pushes and nobody sets a hand. |
| `claim_open` | `seconds`, `seats`, `mine` {`bonus`} | Face Up, after an Ace-high push: each player claims a side-bet win (`bonus` names the hand, or null) or folds. Out of time claims a win and folds anything else. |
| `claimed` | `seat`, `claimed` | A player claimed (their cards are shown at their settle) or folded (mucked unseen; `cards` in their `settle_seat` is empty). |
| `setting_open` | `seconds`, `seats` | Everyone sets at once. The timer ends early once all have set; anyone out of time is set by House Way. |
| `hand_set` | `seat`, `folded`, `auto`, `mine` | A seat set its hand (`auto`: by House Way when time ran out) or folded. `mine` {`front`, `back`, `front_label`, `back_label`} only goes to you. |
| `dealer_set` | `cards`, `front`, `back`, `front_label`, `back_label` | Fortune only: the dealer turns over and sets by House Way. `cards` are in dealt order: the client turns them over unsorted, sorts them, then slides the two Low cards (`front`) off to the left. (At Face Up the same reveal follows the deal.) |
| `settle_seat` | `seat`, `outcome` (`win`, `push`, `lose`, `fold`), `front_win`, `back_win`, `commission`, `cards`, `front`, `back`, `front_label`, `back_label`, `tier`, `steps[]`, `total_returned`, `say`, `pause` | One player settled, from third base. Their hands are turned over and played against the dealer's (a copy goes to the dealer). Steps: `ante` (Fortune: a win pays 1:1 less 5%), `fortune`, `jackpot` (a fixed amount or a share of the pool), and `envy` (£5+ on Fortune pays when another player hits Four of a Kind or better; folded hands don't count). |

### Mississippi Stud table events (`event.kind`)
Table `ms_1`. Seating, betting, Ready and the Jackpot lights work as at the other tables. Bet spots
are `ante`, `bonus` and `jackpot` (a flat £1). Street decisions are sent as `act` with `action`
set to `fold`, `bet1`, `bet2` or `bet3`.

| kind | fields | meaning |
|---|---|---|
| `dealt` | `order` [[who, index]] (who is a seat or `community`), `interval`, `hand_pause`, `mine` {`cards`, `hand`} | Two cards per seat (private), then three community cards face down. |
| `decisions_open` | `street` (0-2: 3rd/4th/5th), `seconds`, `seats`, `mine` {`hand`} | Everyone still in decides at once. Out of time folds. |
| `street_bet` | `seat`, `street`, `times` (0 = fold), `amount`, `reason` | A street bet of `times` × Ante, or a fold (`reason`: `timeout`, `left`, `funds`). |
| `fold_sweep` | `seats[]` {`seat`, `steps[]` {`spot`, `amount`}}, `pause` | The street's folds are swept: Ante, street bets, Jackpot. The Bonus stays. |
| `community` | `from`, `cards`, `mine` {`hand`} | The dealer turns the next community card (all remaining ones if everyone has folded). |
| `bonus_settle` | `seats[]` {`seat`, `steps[]`, `total_returned`}, `bonus_hand`, `say`, `pause` | First in the settle: every folded hand's 3 Card Bonus at once (they all ride on the community cards). |
| `settle_seat` | `seat`, `outcome` (`win`/`push`/`lose`), `multiplier`, `cards`, `hand`, `bonus_hand`, `steps[]`, `total_returned`, `say`, `pause` | Each seat still in, from third base. Spots: `ante`, `third`, `fourth`, `fifth`, `bonus`, `jackpot`. |

If everyone folds, the dealer turns any remaining community cards at once when a Bonus is riding, and the hand simply ends when none is.

The snapshot adds `community` (codes, `??` until turned) and `street`, and each seat gets `streets` [3], `folded` and `decided`.

### Ultimate Texas Hold'em, Let It Ride, High Card Flush and Baccarat (`event.kind`)
These follow the same pattern as Mississippi Stud: `bets_closed`, `dealt` (with `mine`), `decisions_open`,
`community`, `fold_sweep`, `settle_seat` (`steps[]` per spot), `round_end`. Decisions are sent as `act` with an `action`:

| table | spots | `act` actions | own events |
|---|---|---|---|
| `uth_1` | `ante` (sets `blind` too), `trips`, `jackpot`; `play` | stage 0: `bet4`, `bet3`, `check`; 1: `bet2`, `check`; 2: `bet1`, `fold` | `uth_action` {`seat`, `stage`, `action`, `amount`}; `dealer_reveal` {`cards`, `hand`, `qualified`} |
| `lir_1` | `bet1`, `bet2`, `ante` (all equal), `bonus` (£1), `three_card`, `jackpot` | `ride`, `pull` | `lir_decision` {`seat`, `stage`, `spot`, `ride`, `amount`} |
| `hcf_1` | `ante`, `flush`, `straight_flush`, `jackpot`; `raise` | `fold`, `raise1`, `raise2`, `raise3` (up to `mine.max_raise`) | `hcf_action` {`seat`, `times`, `amount`, `flush_count`, `held_count`, `mine` {`flush`, `held`}}: the flush goes face down in front, `held` (a straight flush) under the Straight Flush bet, the rest aside; `fold_sweep` seats carry `cards` (how many are swept); `dealer_reveal` {`cards`, `hand`, `flush`, `qualified`}; `settle_seat` {`flush`, `held`} |
| `bac_1` | `player`, `banker`, `tie`, `player_dragon`, `banker_dragon` | none | `baccarat_card` {`side`, `index`, `card`, `total`}; `coup_result` {`outcome`, `player_total`, `banker_total`, `natural`} |

### Roulette (`event.kind`)
One shared layout. Spots are the bet ids from `engines/roulette.py`, 157 of them:
- `n0`..`n36`, `sp_A_B`, `st_S`, `tr_0_1_2`, `tr_0_2_3`, `co_A_B`, `ff`, `ln_S`
- `col1`..`col3`, `doz1`..`doz3`
- `red`, `black`, `odd`, `even`, `low`, `high`

`bet_changed` and the snapshot carry only the spots in use. Bets are placed with the usual `bet`
(`add` can be negative: Undo uses that), and are also taken during `spinning`. `ready` is refused
once the ball's spinning.

| event | fields | meaning |
|---|---|---|
| `spin` | `open`, `track`, `ball` | The dealer spins ("Final bets!"). Bets stay open for `open` seconds, until just before the ball reaches the pockets `track` seconds after this. `ball` is its launch angle relative to the rotor, so where it arrives is known (`engines/roulette.py: arrival_pocket`). |
| `no_more_bets` | `seats`, `number`, `landing`, `land_in` | Bets are taken (the wallet follows), and the number is drawn now. `landing` is the ball's path from where it arrives to the number: [[`"s"` skid / `"h"` hop, pockets onward, seconds]]. It settles in `land_in` seconds. |
| `ball_landed` | `number`, `colour`, `history` | The call; `history` is the last 12, newest first. |
| `sweep` | `seats` {seat: [{`spot`, `amount`}]} | Every losing chip (or half of an even-money stake on a zero) goes down the chip hole. |
| `settle_seat` | `seat`, `steps[]` {`spot`, `action` `pay`/`half`, `amount`, `payout`}, `total_returned` | Each winning seat, outside bets first. `half` is La Partage's remaining half. |

The snapshot adds:
- `history`
- `dolly` (the number the dolly is on, or null)
- `spin`: {`elapsed`, `track`, `ball`}, plus {`number`, `landing`, `land_in`} once bets are closed. A late joiner picks up the ball mid-flight.

### Craps (`event.kind`)
Bets stay on the layout from roll to roll. A seat's `bets` are everything it has down; `locked` is
what's already paid for. New chips are paid for when the dice go out (one debit per seat per roll);
taking a paid-for bet down refunds it at once. Spot ids: see `engines/craps.py` (`pass`, `pass_odds`,
`dont_pass`, `dont_odds`, `come`, `dont_come`, `come_N`, `come_odds_N`, `dcome_N`, `dcome_odds_N`,
`place_N`, `buy_N`, `lay_N`, `field`, `big6`, `big8`, `hard4`..`hard10`, `any7`, `any_craps`, `two`,
`three`, `eleven`, `twelve`, `horn`, `ce`).

Messages: `shoot` (the shooter rolls; `ready` does the same), `pass_dice`, `take_dice` {`on`} (take
the dice from an NPC: at once if no point is on, else when the point's decided; from a human, after
they seven out), `working` {`on`} (place/buy bets, hardways and come odds work on the come-out).
`rebet` and `auto_rebet` are refused.

| kind | fields | when |
|---|---|---|
| `roll_open` | `shooter`, `point`, `seconds`, `human_shooter` | Bets are open; the shooter rolls when ready (a human within `seconds`, else the dice pass on). |
| `throw` | `shooter`, `dice` [d1, d2], `plan` (each die's path: segments {`k` air/slide, `t0`, `t1`, `x0`, `y0`, `x1`, `y1`, `h`, `f`, `r0`, `r1`} in table coordinates), `out` (seconds the stickman takes to push the dice out first) | Dice are out: no more bets. |
| `roll_result` | `dice`, `total`, `words`, `was` (the point before), `point`, `what` (point_set, point_made, seven_out, natural, craps, roll), `seats` {seat: [{`spot`, `kind` win/lose/return/move, `amount`, `win`, `stays`, `to`}]}, `after` {seat: bets}, `shooter`, `rolls`, `history`, `rest` | The roll's decided and paid (wallets follow). |
| `shooter_change` | `shooter`, `reason` (taken, passed, timeout, no_line_bet, left), `point` | The dice move outside the normal rotation. |
| `dice_queued` | `seat`, `on` | A player is waiting for the dice. |
| `working` | `seat`, `on` | |
| `bets_back` | `seat`, `amount` | Someone got up and their bets that could come down came back. |

The craps `table_state` adds `point`, `shooter`, `want_dice`, `history` (last 12 rolls), `rolls`,
`human_shooter`, `throw` ({`dice`, `plan`, `out`, `elapsed`} while the dice are out) and `rest`
(where the dice lie until they're fetched); seats add `locked` and `working`.

### Slot cabinets (`event.kind`)
Cabinets `slot_1`..`slot_10` (floor.py `SLOTS`) each have one seat and no dealer (`on_duty` is
null). Grid cells are numbered `reel * 4 + row` (row 0 at the top); a reel shows `strip[stop]` on its top row.

A cabinet's `rules` (on `seated`) carry the variant's whole catalogue: `variant`, `name`, `symbols` (tier -> name),
`lines`, `pays` (line bets for 3/4/5, its own tiers: W, H1.., M1.., L1..), `upgrades`, `ladder` (pence), `features`
(the random features it uses), `strips`, `free_strips`, `big_strip`, `buy_cost` (0: no Buy Bonus), `free_games`, `battle` (the wave battle's settings),
`routes` (which bonuses each way in plays: {`BS`, `FS`, `buy`} -> [`trail`/`free`/`battle`], one at random when there are
several; an empty list means that way in plays nothing), the jackpot `tiers`, and for a built slot `theme`: {`colours`, `fonts`
(display/ui, downloaded from the art manifest), `frame` {`style`, `colour`}, `deck` {`style`, `colour`: a tint, or null for the style's own}, `win` (an animation per tier group),
`labels`, `texts` (bonus and free-game names, the launcher, the tagline, the battle's name, hint, enemy and boss), `rules` (the info screen's lines),
`cabinet`, `background`}. Armadillo has no `theme`: the screen draws its own.

Messages: `spin` {`bet`} (one of `ladder`; may cut the last spin's presentation short after 1s),
`buy_bonus` {`bet`} (`buy_cost` bets: straight to one of `routes.buy`'s bonuses, at random if there are several), `trail_fire`, `jackpot_pick` {`index`
0-11}, `battle_fire` {`index`: a ship still there; ignored for the boss}. `bet`/`ready`/`rebet` aren't used.

A paid spin's win is credited at once (the wallet follows the `spin` event; the client holds the
balance until the reels stop). A feature's win is credited when it ends. A player who stands up
or disconnects mid-feature has it played out and paid (those events carry `finished_for_you`).

| kind | fields | when |
|---|---|---|
| `spin` | `seat`, `outcome` {`bet`, `free`, `stops`, `landed`, `after_colossal`, `pre_grid`, `grid`, `trigger` (trail/free/battle/null), `colossal` {`start`, `k`, `stop`, `offset`}, `wild_reels`, `wilds`, `multiplier`, `upgrade` {`from`, `to`, `cells`}, `wins` [{`line`, `sym`, `count`, `mult`, `cells`, `pence`}], `line_win`, `repeat`, `instant`, `total`, `features`, `scatters`}, `meters`, `secs` (how long the screen takes), `features_next` (pick/trail/free/battle still to come) | A paid spin. |
| `bonus_bought` | `bet`, `cost` | Buy Bonus; `trail_start`, `battle_start` or `free_start` follows. |
| `jackpot_start` | `coins` (12) | The Jackpot Pick begins. |
| `jackpot_reveal` | `index`, `tier`, `auto` | A coin turns over (picked, or picked for an idle player). |
| `slot_jackpot_won` | `tier`, `amount`, `name`, `coins` (every coin's tier), `meters` | Third match: paid, the meter resets (a `slot_jackpots` message goes to everyone). |
| `trail_start` | `bought`, `trail` {`bet`, `board` [{`type`, `x`?}], `pos`, `hearts`, `doubled`, `upgraded`, `lightning`, `total`, `done`, `rolls`} | The Trail Bonus begins. |
| `trail_roll` | `roll` {`bullets`, `move`, `from`, `path`, `events` [{`kind` coin/prizepot/heart/heart_used/snake/double/upgrade/lightning/lightning_roll/crate/forward/back, `pos`, `pence`?, `r`?, `n`?}], `done`}, `total`, `hearts`, `upgraded`, `doubled`, `secs` | A shot fired (by the player, or by itself after 6s). |
| `trail_end` | `total`, `prizepot`, `rolls` | Paid. |
| `battle_start` | `bought`, `battle` {`bet`, `wave`, `waves`, `ships` (one bool a ship: still there), `shields`, `max_shields`, `boss_hp` (null until the boss), `boss_max`, `total`, `spins`, `shots`, `cleared`, `won`, `done`} | The wave battle begins. |
| `battle_shot` | `shot` {`target` (a ship's index, or "boss"), `answered`, `events` [{`kind` return_fire {`ship`, `shields`} / shields_down / destroyed {`ship`, `pence` or `spins`} / wave_clear {`wave`, `pence`} / wave_start {`wave`, `ships`, `shields`} / boss_start {`hp`, `shields`} / boss_hit {`hp`} / boss_destroyed {`pence`}}], `done`}, `total`, `spins`, `shields`, `auto`, `secs` | A shot fired (by the player, or by itself after 8s). |
| `battle_end` | `total`, `spins`, `cleared`, `won`, `shots` | Paid. If its ships gave free spins, `free_start` (with that many) follows. |
| `free_start` | `of`, `bet`, `bought`, `source` (scatter/battle) | Combo Free Spins begin. |
| `free_game` | `n`, `of`, `outcome` (as `spin`), `total`, `secs` | Each free game, played by the clock. |
| `free_end` | `total` | Paid. |
| `features_done` | | Back to idle. |

The slots `table_state` adds `variant`, `bet`, `last` (the last spin's outcome), `pending`,
`pick` {`coins`, `done`, `tier` (once won)}, `trail` (as `trail_start`), `trail_ready_in`, `battle` (as `battle_start`), `battle_ready_in`, `free`
{`bet`, `n`, `of`, `total`}, `meters` and `timer`. Server -> client `slot_jackpots` {`meters`
{mini, minor, major, grand}} comes on join, on resync and after every slot jackpot; between those,
every `spin` event carries the meters.

### Every table: dealers on shifts (`event.kind`)
| event | fields | meaning |
|---|---|---|
| `dealer_change` | `dealer` {`id`, `name`, `look`} | A fresh dealer relieves the last one. Shifts are set on the admin page, and a relief only happens while the table is taking bets. |

## Admin HTTP API (`/admin`, also `/maintenance`)
The admin page: Sounds, NPCs, Players, Settings. There's no password: it's LAN-only, like the game.

| method & path | does |
|---|---|
| `GET /api/npcs` | The roster, plus each NPC's `look_id`/`look_url`, `on_floor` {`state`, `table`, `bankroll`, `budget`, `rounds`} or null, and `dealing` (a table id) or null. Also `settings`. |
| `POST /api/npcs` | Create from {`name`, `role`, `look`, `archetype`, `traits`, `settings`, `enabled`}. Checked by `roster.clean`; a 400 says what's wrong. |
| `GET /api/npcs/{id}` | One NPC, plus `visits` (the last 25). |
| `PUT /api/npcs/{id}` | Change any of those fields. A new look or name shows on the floor at once (`entity_update` / `dealer_change`). |
| `DELETE /api/npcs/{id}` | Sends them home if they're here, then deletes them and their visits. |
| `POST /api/npcs/{id}/bring-in`, `/send-home`, `/reset-stats` | In through the door now (cooldown or not), out now, or clear their lifetime figures. |
| `GET /api/npc-options` | The look designer's catalogue (bodies, skins, each slot's options with the bodies they fit and their colours, uniforms), plus the roles, archetypes, modifiers, games and tables. |
| `POST /api/looks/preview` | {`look`} → {`id`, `url`}: builds the sheet (cached). |
| `GET /looks/{id}.png` | A built sheet: immutable, cache it. |
| `GET` / `PUT /api/npc-settings` | Floor `population`, `cooldown_min` and `bust_cooldown_min` ([lo, hi] minutes), `regular_cooldown` (a multiplier), `dealer_shift_min`, `dealer_stagger_min`. |
| `GET /api/players` | Each player's lifetime `wagered`, `returned`, `net`, `bets` and `last_at`, with the same per game, from the ledger. |
| `GET /credits` | LPC art credits for every layer the designer can use. |

## Sound HTTP API (the admin page's Sounds tab)
Plain HTTP on the same server, used by the admin page and the game. See `casino_server/sounds.py`. A `set` is
`casino`, a game key (`blackjack`, `roulette`, ...), `slots`, or `slots.<variant>` (`slots.armadillo`). Every
change sends `sounds_changed` to every joined player.

| method & path | does |
|---|---|
| `GET /api/sounds` | `sections` (page order); `moments` (`{key: {title, when, section, home, loop}}`; `home` is the set it's defined in); `sets` (each `key`, `name`, `parent`, `group`, and its `moments`: rows of `key`, `own`, `from` (the set whose sounds it plays), `files`, `gain_db`, `changed`, `can_inherit`); `folders` (`{folder: {label, sections}}`); the whole `library` (`id`, `group`, `name`, `bytes`). |
| `GET /api/sounds/manifest` | What the game loads: `{version, sets: {set: {parent, moments: {key: {files: [url], gain_db}}}}, tables: {table id: set}}`. A set lists only its own moments; the rest come from the nearest set above. Each URL ends in `?v=<change time>`, so it can be cached for good. |
| `PUT /api/sounds/{set}/{key}` | JSON `{files: [sound id], gain_db}`. Gives the moment its own sounds in that set (deduplicated; gain clamped to -30..+12 dB); `files: []` silences it there, without the set above filling in. Returns its row. |
| `POST /api/sounds/{set}/{key}/inherit` | The moment plays the set above's sounds. Refused in its home set. |
| `DELETE /api/sounds/{set}/{key}` | Puts one moment in one set back to how it came. `POST /api/sounds-reset` with `{set}` resets that set, with `{}` everything. |
| `PUT /api/sound-uploads/{filename}` | The raw file as the body. Saved under `uploads/`; .flac/.m4a/.opus are converted to .ogg with ffmpeg. |
| `DELETE /api/sound-uploads/{filename}` | Deletes an upload, unless a moment still uses it. |
| `GET /sound-files/{sound id}` | The file itself. Sound ids are library paths, e.g. `kenney-casino/chip-lay-1.ogg` or `uploads/my-chip.ogg`. |

