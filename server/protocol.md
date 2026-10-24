# Casino World protocol (v6)

Messages are JSON objects with a `type` field, carried over a WebSocket at `/ws`.
The server is authoritative, so the client sends intents and renders what comes back.
Money is always an integer number of **pence**. Cards are codes like `"Qs"` or `"10h"`, and
`"??"` is a face-down card.

## Connecting
A device has an **account** (its token), and an account has up to three **characters**: each with its own name,
look, difficulty, money and stats. Bans, timeouts and the admin page's Protected are the account's.

1. The server sends `hello` {`protocol`}.
2. The client replies `join` {`token`}. On a device's first visit the token is `""`; after that it's the one saved
   from `account`. The reply is `account`: the character select. Nobody is on the floor yet. A banned or timed-out
   account gets `barred` instead.
3. The client makes, changes or deletes characters (`create_character`, `edit_character`, `delete_character`, each
   answered with a fresh `account`) and picks one with `pick_character`. The server then sends, in order:
   - `welcome`
   - `wallet`
   - `jackpot`, `slot_jackpots`
   - `world_snapshot`
   - one `table_state` per table
   - your own `entity_spawn`, which everyone receives
4. `leave_character` takes you off the floor (standing you up first) and back to the select: `character_left`, then
   `account`. Picking a character that's playing in another window takes it over: that window gets
   `character_left` {`reason`: `elsewhere`} and `account`. A reconnect asks with `resume`, which gives way instead.

A floor-plan preview (the admin page's Preview button, `/?preview=<room>`) sends `join` {`token`, `preview`: room id}
instead: it gets only `welcome` (with the draft's floor) and `wallet`, has no body on the floor, isn't sent the
casino's goings-on, and everything else it sends is ignored.

## Client → server
| type | fields | meaning |
|---|---|---|
| `join` | `token`, `preview` (optional room id) | Identify the device's account, or make a new one (an empty or unknown token). Must come first. The reply is `account`. With `preview`, a look round the floor plan's draft instead (see Connecting). |
| `create_character` | `name`, `look`, `difficulty` | A new character (at most `account.max`). `name`: up to 16 characters, spaces squashed, not the same as another of yours. `look`: a look spec (art.py: `body`, `skin`, and each slot's [option, colour] or null). `difficulty`: `easy`, `normal` or `hard`, which sets the starting bank (`account.difficulties`). The reply is `character_made` {`id`} and `account`, or an `error` saying what's wrong. |
| `edit_character` | `id`, `name`, `look` | Change one of your characters' name and look (checked as above). Refused while it's on the floor. The reply is `account`. |
| `delete_character` | `id` | Delete one of your characters, its money and history. Refused while it's on the floor. The reply is `account`. |
| `pick_character` | `id`, `resume` (optional bool) | Onto the floor as that character (see Connecting). If it's playing in another window it's taken over from there; with `resume` (a reconnect) the reply is `character_left` {`reason`: `elsewhere`} and `account` instead. |
| `leave_character` | | Off the floor and back to the character select (standing you up first). A hand you're in plays out for that character. The reply is `character_left` {`reason`: `switch`} and `account`. |
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
| `atm_open` | | The lobby's ATM (bank.py): its screen's state. Only on foot, standing at an ATM (within 64px of its base, by your last `move`); otherwise an `error`. The reply is `atm`. |
| `atm_withdraw` | `amount` | Take `amount` pence from your bank into your cash in hand. It must be whole £50 notes, within the withdrawal limit (`cap`), while you hold less than the limit on hand and, when overdrawn, not within the wait since your last withdrawal (`atm`'s fields). The reply is `wallet` and then `atm` with `done`, or `atm` with the `error` its screen shows. Same place rules as `atm_open`. |
| `atm_deposit` | `amount` | Pay `amount` pence of your cash in hand into your bank (any amount you hold). Replies as `atm_withdraw`. |
| `ping` | `t` | A latency check. |
| `away` | | The tab was hidden. The server sends nothing more until `resync`; you stay on the floor (and seated). |
| `resync` | | The tab is visible again. Drop every message until the `resync` reply; the full state follows it. |
| `choose_game` | `game` | Master Table: ask for a card game (`three_card_poker` … `baccarat`). Anyone else seated is asked first (`master_vote`); otherwise it changes between hands. |
| `game_vote` | `accept` (bool) | Master Table: agree to, or turn down, the game someone asked for. |
| `cancel_game_change` | | Master Table: stay on this game instead of the one agreed for after this hand. |
| `second_box` | `seat` | Play the free seat beside you as a second box (see "A second box" below). |
| `drop_box` | | Give your second box back. Refused while it's in the hand being played. |

## Server → client
| type | fields | when |
|---|---|---|
| `account` | `token`, `characters` [{`id`, `name`, `look`, `spec`, `difficulty`, `balance`, `bank`, `online`}], `max`, `difficulties` {`easy`, `normal`, `hard`: starting bank, pence}, `last` (id last played, or null) | The character select: the reply to `join` and to every character message, and what a resync sends before you've picked. Save `token`. A character's `look` is its sheet's id (`x_…`, or `player_default` for one with no look of its own) and `spec` the look spec it was built from (null for none); `online` means it's on the floor somewhere. |
| `character_made` | `id` | The character `create_character` made (an `account` follows). |
| `character_left` | `reason` (`switch` \| `elsewhere`), `name` | You're off the floor (you left, or the character was picked in another window), or a `resume` gave way. An `account` follows. |
| `welcome` | `player` {`id`, `name`, `difficulty`}, `entity_id`, `look`, `world`, `preview`, `seating`, `table_styles` | The reply to `pick_character`. `look` is the character's sheet. `world` is the floor to build (the floor plan's placed rooms, plan.py `world()`; see "The world" below). `preview` is the room id a preview shows, else null. `seating` is {`styles` {id: style}, `tables` {table id: style id}}: how the chairs look, how people sit down and the craps standing spots (seating.py lists a style's fields). A table not in `tables` uses the `default` style. `table_styles` is {`cards`, `roulette`, `craps`}, each {`styles` {id: {`name`, `design`, `builtin`}}, `tables` {table id: style id}, `default`}: how each kind of table looks (table_styles.py KINDS lists each kind's design choices). A table not in its kind's `tables` uses that kind's `default` style (House unless the admin page changes it). |
| `wallet` | `balance` | Your cash in hand (what you bet with; your bank balance is only on the ATM's `atm`). Sent on join, after each money-moving table event (straight after that event), and after an ATM withdrawal or deposit. |
| `atm` | `bank`, `can`, `why` (`""`, `carrying`, `overdrawn`), `cap`, `wait` (seconds), `big`, `big_wait` (seconds), `threshold`, `hand_under`, `cooldown_min`, `big_wait_min`, `history` [{`kind` withdraw/deposit, `amount`, `t` (unix)}], `done` {`kind`, `amount`}, `error` | The reply to `atm_open`, `atm_withdraw` and `atm_deposit`: your bank balance (pence, negative when overdrawn); whether you can withdraw now and, if not, why (holding `hand_under` or more, or overdrawn and `wait` seconds from the next); the most a withdrawal can be (`cap`: the usual limit, or with `big` the bigger one, half the bank rounded down, which a bank at `threshold` or more allows once every `big_wait_min` minutes; `big_wait` is how long until it's back, while the usual limit applies in between); the overdrawn wait in minutes; your last four ATM moves, newest first. `done` comes after a withdrawal or deposit went through, `error` when it didn't. |
| `jackpot` | `amount`, `rate` (pence/s), `ceiling`, `table` | Sent on join and after a jackpot win. The client extrapolates the meter between updates. After a win, `table` is the table it was won at: that table's jackpot sign keeps showing the old amount until its `jackpot_won` event plays (then celebrates), while every other table's sign takes the new amount straight away. |
| `world_snapshot` | `entities[]` | Everyone already on the floor. Each has `id`, `kind`, `name`, `look`, `x`, `y`, `dir`, `anim`, `seat`, and an NPC on the move `walk` {`target`, `duration`, `remaining`}. An NPC's `x`, `y` is where its walk set off from (or where it is, when it isn't walking): the client starts it that far along its path (`duration` − `remaining`) and walks the rest in `remaining`. A player's is null until their first move. |
| `entity_spawn` | `entity`, `at` | Someone arrived. `at` is where, as a walk target (`point:<room>/<name>`: a player at the spawn point, an NPC at the arrival point it came in by), used while `x` is null (a player's, until they first move). |
| `entity_move` | `id`, `x`, `y`, `dir`, `anim` | Another player moved. |
| `entity_walk` | `id`, `target`, `duration` | An NPC heads for `point:<name>` or `seat:<table>:<n>`. The client paths them there in `duration` seconds. |
| `entity_update` | `id`, `name`?, `look`? | Someone renamed, or an NPC was restyled on the admin page (a `look` id starting `x_` is a server-built sheet at `/looks/<id>.png`). |
| `entity_despawn` | `id` | Someone left. |
| `seated` | `table`, `seat`, `rules` | You sat down. `rules` holds the paytable, `chips`, `min_ante` and `seats`. A `table_state` follows. |
| `table_state` | `table`, `game`, `phase`, `seats[]`, `dealer` (the game's dealer state), `timer`, `my_seat`, `my_box` (your second box's seat, or null), `second_box` (whether this table offers one), `on_duty` {`id`, `name`, `look`} for who's dealing (from the dealer roster), plus at Blackjack `turn`, `shoe`, `discards` | The whole table as you may see it. Sent on join, and when you sit. |
| `table_event` | `table`, `event` | Something happened at a table. Every joined player gets every table's events (see below). |
| `notice` / `error` | `message` | Information, or a rejected action. |
| `barred` | `kind` (`ban` \| `timeout` \| `removed`), `reason`, `retry_in` (seconds, or null) | The admin page has shut this account out: the reply to `join` (or `pick_character`) from a banned or timed-out account, or sent to anyone on it when it happens, at the character select too (`removed`: the account, or the character being played, was deleted). The server hangs up straight after. The client shows why and doesn't reconnect until `retry_in` has passed (never, without a reload, when it's null). |
| `pong` | `t` | The reply to `ping`. |
| `resync` | `table`, `seat` | The reply to `resync`: where you're seated now (null if you were stood up while away). Then `welcome`, `wallet`, `jackpot`, `slot_jackpots`, `world_snapshot` and one `table_state` per table, as on picking. At the character select it's followed by `account`, and before joining by `hello`. |
| `world` | `world` | The floor plan changed: a publish that moved things but added or removed no tables (adding or removing tables restarts the server instead), or, to a preview, the draft was saved. The client rebuilds the floor (once its player stands up). |
| `plan_art_changed` | `version` | The floor plan's asset library changed (an upload, an edit, a delete). The client refetches `GET /api/plan/art`. Previews get it too. |
| `sounds_changed` | `version` | The sound choices changed on the admin page. The client refetches `GET /api/sounds/manifest`. |
| `seating` | `seating` | The seating styles changed on the admin page (as in `welcome`). The client redraws every chair. |
| `table_styles` | `table_styles` | The table styles or their placement changed on the admin page (as in `welcome`, every kind). The client redraws every table: the card tables with their machines, chips and cards, Roulette with its wheel, Craps with its dice. |

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
| `betting_timer` | `seconds`, `quiet`? | The first bet went down, and betting closes in this many seconds (sooner once every human is Ready). `quiet: true` after a rebet: no countdown ticks. Craps: a real player's bet went down with under 5 seconds before the dice go out, and the countdown's back to `seconds`. |
| `auto_rebet` | `seat`, `on`, `reason`? | A seat's Auto rebet was ticked or unticked. `reason` says why it went off by itself: `timeout`, or the rebet's error (such as the balance not covering it). Seat entries in snapshots carry `auto_rebet` too. |
| `ready` | `seat` | That seat locked in. |
| `bets_closed` | `seats`, `jackpots` | Bets are closed (the card-game dealers don't call it; only Roulette's says "No more bets"). Upfront bets have been taken. For the seats in `jackpots`, the dealer locks the Jackpot bets in: the lights under the plastic Jackpot discs go from flashing to solid red, and the Jackpot chips are lifted off the table before the deal. Each light stays on until that player is settled. |
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
| `side_bets` | `seats[]` {`seat`, `steps[]` {`spot`, `action`, `amount`, `payout`}, `hand`, `returned`}, `pause`, `step`, `sweep_gap` | Super Pairs, 21+3, Top 3 and the Jackpot settle straight after the deal off the first two cards and the up-card, `pause` seconds in: each box's losers (`collect`, listed first) swept together, `sweep_gap` apart, in one `step`, then its winners paid (`pay`) a `step` each beside their spots, where stake and winnings stay until `round_end`. |
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
| `settle_seat` | `seat`, `hands[]` {`hand`, `outcome`, `label`, `action`, `amount`, `payout`}, `say`, `pause`, `total_returned` | One box settled, third base back to first, hand by hand: losers swept, pushes left, winners paid beside the bet (Blackjack 3:2). The cards go to the discard rack last. When a Dealer Blackjack beats every box, they all come at once with `sweep` (the seconds between boxes) in place of `pause`, and an empty `say`: each box's stake and cards go straight in. |
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
what's already paid for. New chips are paid for when the dice go out (one debit per seat per roll),
with the vig on new lay bets; taking a paid-for bet down refunds it at once, a lay bet's vig with it
(`bet_changed` then carries `vig_back`, the pence of vig that came back). Spot ids: see `engines/craps.py` (`pass`, `pass_odds`,
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
| `throw` | `shooter`, `dice` [d1, d2], `plan` (each die's path: segments {`k` air/slide, `t0`, `t1`, `x0`, `y0`, `x1`, `y1`, `h`, `f`, `r0`, `r1`} in table coordinates), `out` (seconds the stickman takes to push the dice out first), `vig` {seat: {lay spot: pence}} (the vig each player handed over with their lay bets) | Dice are out: no more bets. |
| `roll_result` | `dice`, `total`, `words`, `was` (the point before), `point`, `what` (point_set, point_made, seven_out, natural, craps, roll), `seats` {seat: [{`spot`, `kind` win/lose/return/move, `amount`, `win` (what's paid, after any vig), `vig` (taken off a buy or lay bet's win), `stays`, `to`}]}, `after` {seat: bets}, `shooter`, `rolls`, `history`, `rest` | The roll's decided and paid (wallets follow). |
| `shooter_change` | `shooter`, `reason` (taken, passed, timeout, no_line_bet, left), `point` | The dice move outside the normal rotation. |
| `dice_queued` | `seat`, `on` | A player is waiting for the dice. |
| `working` | `seat`, `on` | |
| `bets_back` | `seat`, `amount` | Someone got up and their bets that could come down came back. |

The craps `table_state` adds `point`, `shooter`, `want_dice`, `history` (last 12 rolls), `rolls`,
`human_shooter`, `throw` ({`dice`, `plan`, `out`, `elapsed`} while the dice are out) and `rest`
(where the dice lie until they're fetched); seats add `locked` and `working`.

### Slot cabinets (`event.kind`)
Cabinets (`slot_1`.., placed on the floor plan, plan.py) each have one seat and no dealer (`on_duty` is
null). Grid cells are numbered `reel * 4 + row` (row 0 at the top); a reel shows `strip[stop]` on its top row.

A cabinet's `rules` (on `seated`) carry the variant's whole catalogue: `variant`, `name`, `symbols` (tier -> name),
`lines`, `pays` (line bets for 3/4/5, its own tiers: W, H1.., M1.., L1..), `upgrades`, `ladder` (pence), `features`
(the random features it uses), `strips`, `free_strips`, `big_strip`, `buy_cost` (0: no Buy Bonus), `free_games`, `battle` (the wave battle's settings), `voyage` (the island voyage's), `expedition` (the expedition's),
`routes` (which bonuses each way in plays: {`BS`, `FS`, `buy`} -> [`trail`/`free`/`battle`/`voyage`/`expedition`], one at random when there are
several; an empty list means that way in plays nothing), the jackpot `tiers`, and for a built slot `theme`: {`colours`, `fonts`
(display/ui, downloaded from the art manifest), `frame` {`style`, `colour`}, `deck` {`style`, `colour`: a tint, or null for the style's own}, `win` (an animation per tier group),
`labels`, `texts` (bonus and free-game names, the launcher, the tagline, the battle's name, hint, enemy and boss, the voyage's name, hint, start and final island, island names and artefacts, the expedition's name, hints, start, final destination, levels, tech, specials and hazards), `rules` (the info screen's lines),
`cabinet`, `background`}. Armadillo has no `theme`: the screen draws its own.

Messages: `spin` {`bet`} (one of `ladder`; may cut the last spin's presentation short after 1s),
`buy_bonus` {`bet`} (`buy_cost` bets: straight to one of `routes.buy`'s bonuses, at random if there are several), `trail_fire`, `jackpot_pick` {`index`
0-11}, `battle_fire` {`index`: a ship still there; ignored for the boss}, `voyage_choose` {`choice`: one of the voyage's
`options`: an island's row 0-2 on the next leg, `final`, or at Port Royal `artefact`/`key`/`spins`/`sell`/`leave`}, `expedition_choose` {`choice`: one of the
expedition's `options`: a route 0-2 at the chart, else a planet 0-2 not yet explored in this sector}. `bet`/`ready`/`rebet` aren't used.

A paid spin's win is credited at once (the wallet follows the `spin` event; the client holds the
balance until the reels stop). A feature's win is credited when it ends. A player who stands up
or disconnects mid-feature has it played out and paid (those events carry `finished_for_you`).

| kind | fields | when |
|---|---|---|
| `spin` | `seat`, `outcome` {`bet`, `free`, `stops`, `landed`, `after_colossal`, `pre_grid`, `grid`, `trigger` (trail/free/battle/voyage/expedition/null), `colossal` {`start`, `k`, `stop`, `offset`}, `wild_reels`, `wilds`, `multiplier`, `upgrade` {`from`, `to`, `cells`}, `wins` [{`line`, `sym`, `count`, `mult`, `cells`, `pence`}], `line_win`, `repeat`, `instant`, `total`, `features`, `scatters`}, `meters`, `secs` (how long the screen takes), `features_next` (pick/trail/free/battle/voyage/expedition still to come) | A paid spin. |
| `bonus_bought` | `bet`, `cost` | Buy Bonus; `trail_start`, `battle_start`, `voyage_start`, `expedition_start` or `free_start` follows. |
| `jackpot_start` | `coins` (12) | The Jackpot Pick begins. |
| `jackpot_reveal` | `index`, `tier`, `auto` | A coin turns over (picked, or picked for an idle player). |
| `slot_jackpot_won` | `tier`, `amount`, `name`, `coins` (every coin's tier), `meters` | Third match: paid, the meter resets (a `slot_jackpots` message goes to everyone). |
| `trail_start` | `bought`, `trail` {`bet`, `board` [{`type`, `x`?}], `pos`, `hearts`, `doubled`, `upgraded`, `lightning`, `total`, `done`, `rolls`} | The Trail Bonus begins. |
| `trail_roll` | `roll` {`bullets`, `move`, `from`, `path`, `events` [{`kind` coin/prizepot/heart/heart_used/snake/double/upgrade/lightning/lightning_roll/crate/forward/back, `pos`, `pence`?, `r`?, `n`?}], `done`}, `total`, `hearts`, `upgraded`, `doubled`, `secs` | A shot fired (by the player, or by itself after 6s). |
| `trail_end` | `total`, `prizepot`, `rolls` | Paid. |
| `battle_start` | `bought`, `battle` {`bet`, `wave`, `waves`, `ships` (one bool a ship: still there), `shields`, `max_shields`, `boss_hp` (null until the boss), `boss_max`, `total`, `spins`, `shots`, `cleared`, `won`, `done`} | The wave battle begins. |
| `battle_shot` | `shot` {`target` (a ship's index, or "boss"), `answered`, `events` [{`kind` return_fire {`ship`, `shields`} / shields_down / destroyed {`ship`, `pence` or `spins`} / wave_clear {`wave`, `pence`} / wave_start {`wave`, `ships`, `shields`} / boss_start {`hp`, `shields`} / boss_hit {`hp`} / boss_destroyed {`pence`}}], `done`}, `total`, `spins`, `shields`, `auto`, `secs` | A shot fired (by the player, or by itself after 8s). |
| `battle_end` | `total`, `spins`, `cleared`, `won`, `shots` | Paid. If its ships gave free spins, `free_start` (with that many) follows. |
| `voyage_start` | `bought`, `voyage` {`bet`, `map` (a list of legs, each three islands top to bottom: treasure/wreck/skull/port/cove), `legs`, `leg` (-1 at the start port), `row`, `route` (the row taken on each leg), `relics`, `keys`, `artefacts` (one bool each), `spins`, `total`, `awaiting` (sail/trade/null), `sunk`, `treasure` (the final island's pay, once there), `steps`, `done`, `options` (what `voyage_choose` takes now)} | The island voyage begins. |
| `voyage_step` | `step` {`action` (sail/trade/final), `choice`, `events` [{`kind` arrive {`leg`, `row`, `island`} / treasure, skull, cove {`pence`} / relics {`n`} / key / artefact {`i`} / unlock / sunk / port {`deals`} / bought {`deal`, `cost`} / sold {`n`, `pence`} / leave / final {`chest`, `parts`, `legend`, `relics`, `pence`}}], `done`}, `voyage` (as `voyage_start`, after the step), `auto`, `secs` | A choice made (by the player, or for them after 12s). |
| `voyage_end` | `total`, `spins`, `sunk`, `treasure`, `steps` | Paid. If it bought free games, `free_start` (with that many) follows. |
| `expedition_start` | `bought`, `expedition` {`bet`, `routes` [{`length`, `level` (0-2), `final` (bets)}], `route` (the one chosen, or null), `sector` (-1 at the chart), `planets` (this sector's three: {`kind` credits/mult/scanner/shuttle/shields/artefact/wormhole/spins/hazard, `x`? (bets) or `n`?, `pence`?, `seen`, `by` (ship/shuttle/null)}; one not yet seen is just {`kind`: null, `seen`: false, `by`: null}), `found` (each sector's kinds explored), `awaiting` (route/planet/shuttle/null), `mult`, `scanners`, `shuttles`, `shields`, `scanned`, `shuttle_now`, `spins`, `total`, `ended`, `wormhole`, `final` (pence, once there), `steps`, `done`, `options` (what `expedition_choose` takes now)} | The expedition begins. |
| `expedition_step` | `step` {`action` (route/explore/shuttle), `choice`, `events` [{`kind` route {`i`} / warp {`sector`} / scan {`planets`} / shuttle / reveal {`i`, `by`, `planet`} / credits, artefact {`pence`} / mult {`n`, `mult`} / tech {`tech`} / spins {`n`} / wormhole / shielded / shuttle_lost / hazard / missed {`planets` [[`i`, planet]]} / final {`pence`, `mult`, `wormhole`}}], `done`}, `expedition` (as `expedition_start`, after the step), `auto`, `secs` | A choice made (by the player, or for them after 12s). |
| `expedition_end` | `total`, `spins`, `ended`, `wormhole`, `final`, `mult`, `steps` | Paid. If it found free games, `free_start` (with that many) follows. |
| `free_start` | `of`, `bet`, `bought`, `source` (scatter/battle/voyage/expedition) | Combo Free Spins begin. |
| `free_game` | `n`, `of`, `outcome` (as `spin`), `total`, `secs` | Each free game, played by the clock. |
| `free_end` | `total` | Paid. |
| `features_done` | | Back to idle. |

The slots `table_state` adds `variant`, `bet`, `last` (the last spin's outcome), `pending`,
`pick` {`coins`, `done`, `tier` (once won)}, `trail` (as `trail_start`), `trail_ready_in`, `battle` (as `battle_start`), `battle_ready_in`, `voyage` (as `voyage_start`), `voyage_ready_in`,
`expedition` (as `expedition_start`), `expedition_ready_in`, `free`
{`bet`, `n`, `of`, `total`}, `meters` and `timer`. Server -> client `slot_jackpots` {`meters`
{mini, minor, major, grand}} comes on join, on resync and after every slot jackpot; between those,
every `spin` event carries the meters.

### Master Table (`event.kind`)
A Master Table's `table_state` is its game's own snapshot (or, blank, `game: "master_table"`, `phase: "idle"` and the
seats) plus `master` {`game` ("" blank), `anim`, `speed`, `games`, `seats_by_game`, `rules`, `queued`, `vote`
{`game`, `by`, `voters`, `agreed`, `seconds`} or null, `changing` (seconds left) or null, `revert` (seconds) or null}.
While it changes, `phase` is `changing` and every bet is refused.
| event | fields | meaning |
|---|---|---|
| `master_vote` | `game`, `by` (seat), `name`, `voters` (seats), `seconds` | Someone asked for a game: the others seated have `seconds` to answer. |
| `master_vote_cast` | `seat`, `accept` | One of them agreed. |
| `master_vote_end` | `ok`, `game`, and `seat`, `name` for a no | Agreed (the change follows), or turned down. |
| `master_queued` | `game` or null | The game agreed on for after this hand, or none any more. |
| `master_change` | `game` ("" back to blank), `seats` (6 or 5), `map` (each new seat's old seat, or -1), `anim`, `speed`, `seconds`, `rules` | The table becomes `game` now: the client swaps in that game's table and animates it. A fresh `table_state` follows for every session (seats renumbered). Betting opens on it after `seconds`. |
| `master_revert` | `seconds` or null | Nobody's seated: back to the crest in `seconds` (null: someone sat down again). |

### Every table: dealers on shifts (`event.kind`)
| event | fields | meaning |
|---|---|---|
| `dealer_change` | `dealer` {`id`, `name`, `look`} | A fresh dealer relieves the last one. Shifts are set on the admin page, and a relief only happens while the table is taking bets. |

### Every card table but Pai Gow and Baccarat: a second box
A seated player can also play the free seat right beside them as a second box: Three Card Poker, Blackjack,
Mississippi Stud, Ultimate Texas Hold'em, Let It Ride and High Card Flush, and a Master Table while it's one of
those. The box is a seat of its own, dealt, decided and settled like any other, with its own `round_net`, but its
money is its player's: every bet they make is matched on it (`bet`, `clear_bets`, `rebet`, Auto rebet, `ready`,
queued bets), and a bet they can't cover on both boxes is refused. Its seat entry in snapshots carries `box_of`
(the player's own seat); nobody's avatar sits there.

Decisions for the box are the usual messages (`decide`, `act`, `insure`) with `seat` set to the box's seat. In the
games where everyone decides at once, its cards stay hidden from its player until their own hand has decided, and on
every street or stage their own hand decides first ("Decide Box 1 first."). Blackjack's cards are face up and its
turns go seat by seat, so nothing waits there.

| event | fields | meaning |
|---|---|---|
| `box_taken` | `seat`, `of`, `entity`, `name` | The player in seat `of` is playing `seat` as a second box. Their bets follow at once as `bet_changed` for it. |
| `box_dropped` | `seat`, `of`, `reason` | The box is given back: `dropped`, `stood` (they stood up, or were stood up), or `game_change` (a Master Table changing game). Standing up mid-hand treats the box as the seat itself would be. |
| `box_revealed` | `seat`, `of`, `mine_box` | The player's own hand has decided: the box's private cards, as `dealt` gave them for a seat of your own (`cards`, `hand`, and at High Card Flush `flush`, `max_raise`). |

Any event with private parts carries `mine_box` alongside `mine` for the player's second box, once it's been shown.

### Every table but Craps: each seat's result for the hand
The runner (`tables/runner.py`) adds what the hand won or lost each seat's player, counted from their balance when bets were taken, so it covers side bets, raises, doubles and jackpots. The client floats it, green or red, off the back of that seat's chair.

| event | added field | meaning |
|---|---|---|
| `settle_seat` | `round_net` | The seat's net for the hand, in pence (+ won, − lost). |
| `round_end` | `round_nets[]` {`seat`, `net`} | The seats that played but had no `settle_seat` of their own: a bust or folded hand, a Blackjack paid early, a losing Roulette seat. |

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
| `GET /api/look-options` | The game's character designer's catalogue: `bodies`, `skins`, and `slots` [{`slot`, `label`, `required`, `options` [{`id`, `label`, `bodies`, `colours`}]}]. |
| `GET /api/npc-options` | The look designer's catalogue (bodies, skins, each slot's options with the bodies they fit and their colours, uniforms), plus the roles, archetypes, modifiers, games and tables. |
| `POST /api/looks/preview` | {`look`} → {`id`, `url`}: builds the sheet (cached). |
| `GET /looks/{id}.png` | A built sheet: immutable, cache it. |
| `GET` / `PUT /api/npc-settings` | Floor `population`, `cooldown_min` and `bust_cooldown_min` ([lo, hi] minutes), `regular_cooldown` (a multiplier), `dealer_shift_min`, `dealer_stagger_min`. |
| `GET /api/players` | Every character: `account_id`, `difficulty`, `balance`, `bank`, its account's `protected`, `banned`, `timeout_until`, `bar_reason`, `online`, and its lifetime `wagered`, `returned`, `net`, `bets` and `last_at`, with the same per game, from the ledger. |
| `POST /api/players/{id}/protect` | {`on`}: protect (or not) the character's account: nothing here can ban, time out or delete it, or any character on it. |
| `POST /api/players/{id}/ban`, `/timeout`, `/lift` | Ban the character's account ({`reason`}), time it out ({`minutes` 1 to a year, `reason`}), or let it back in. Anyone on it is sent `barred` and hung up on. Refused (400) while protected. |
| `DELETE /api/players/{id}` | Delete that character, its money and its ledger. Refused while protected. |
| `DELETE /api/accounts/{id}` | Delete an account and every character on it. Its device comes back as a new account. |
| `GET` / `PUT /api/bank-settings` | The Bank settings (whole pounds; minutes for the waits): `start_bank_easy`, `start_bank` (Normal), `start_bank_hard`, `start_hand`, and the ATM's `hand_under`, `low_cap`, `threshold`, `big_wait_min`, `big_step`, `cooldown_min`. |
| `GET /credits` | LPC art credits for every layer the designer can use. |

## The world
`world` (in `welcome` and the `world` message) is `{rev, spawn, rooms, walls, styles}`, plus `start` {`x`, `y`} in a
preview (where to put the viewer). `walls` gives the wall sizes ({`top` 70, `side` 8, `bottom` 10}) and `styles` the
wall looks by style id ({`name`, `paper`, `stripe`, `wainscot`, `trim`, `edge`} colours; `none` has only a name and
draws no walls). Each room is
{`id`, `name`, `x`, `y`, `w`, `h` (on the plan, walls included), `floor` {`texture`, `tint`}, `patches`,
`walls` {`style`, `sign`, `sign_at`, `back`: `thin` when the back wall is a border as deep as the side walls
rather than `walls.top`}, `npc_only` (a lift or back room: NPCs come and go through it, players are
kept out and never shown it), `openings`, `items`, `points`, `zones`}. Everything in a room is placed from its
top-left corner.
- `openings`: its doorways, its own and its neighbours' through its walls: {`side`, `at` (the middle, along the
  wall), `width`, `kind` (`door` | `archway`), `to` (the room beyond, or null for a shut outside door), `door`,
  `owner`}.
- `items`: {`id`, `asset`, `x`, `y`, `rot` (tables) or `facing`, `props`}. A table (`table:<game>`, its id the
  table id) also has `game`, `name`, `seats`; a slot cabinet (`slot`) `name` and `cabinet` (its look: `body`,
  `trim`, `title`, `lines`; empty for Armadillo); built-in pieces are `podium` and `npc` (props `look`, `name`).
- `points`: {`name`, `x`, `y`, `kind` (`spawn` | `arrival` | `wander`), `weight`, `linger`}. NPC walks go to
  `point:<room>/<name>`.
- `zones`: {`x`, `y`, `w`, `h`, `kind`}: `block` keeps everyone out, `npc_block` only NPCs (their paths).

## Floor plan HTTP API (the admin page's Floor plan tab)
See `casino_server/plan.py`. Errors are 400 with the reason (409 when the draft was saved from another tab since).

| method & path | does |
|---|---|
| `GET /api/plan` | `draft` (the whole plan), `problems` [{`room`, `item`, `message`, `placed`}], `live_rev`, `pending` (the placed rooms the draft changes, by name), `restart` (publishing would restart the casino), `can_publish`, `live`. |
| `GET /api/plan/catalogue` | What can be placed: `games` (each with its `rotations` and its shapes `at` each turn: `rect`, `body`, `stands`), `cabinet` (shapes by facing), `pieces`, `assets`, `walls`, `floors`, `slots`, and the kinds of point, zone and door. |
| `PUT /api/plan/draft` | The draft `{rooms, spawn, base_rev}`. New rooms, doors and things come without ids and are given them. Saved even with problems. Previews are sent the new draft. Returns as `GET`. |
| `POST /api/plan/publish` | The draft goes live, if its placed rooms have no problems. Without new or removed tables everyone gets `world`; otherwise the casino restarts (only the live server; a dev instance says to restart it). `{message, restart, ...view}`. |
| `POST /api/plan/discard` | The draft goes back to the live plan. |
| `GET /api/plan/history` | The last 20 publishes: [{`id`, `rooms`, `tables`}], newest first. |
| `POST /api/plan/rollback/{id}` | Puts that publish back in the draft (publish it to use it). |

### The asset library (`casino_server/plan_assets.py`)

| method & path | does |
|---|---|
| `GET /api/plan/art` | What the game draws furniture and floors with: `{version, assets: {id: {mount, body, by_facing, facings: {facing: {url, anchor, mirror}}}}, floors: {id: url}}`. URLs end in `?v=`, so they cache for good. |
| `GET /plan-art/{file}` | A built-in picture (`fountain.png`, `floors/herringbone.png`) or an upload (`u/<file>`). |
| `PUT /api/plan-assets/{filename}` | The raw picture as the body (`?kind=floor` for a floor texture). At most 8 MB and 512px a side; a piece is trimmed to what's drawn. Returns `{id}` (`u_<name>`). |
| `PUT /api/plan-assets/{id}/facings/{up|left|right}` | Another way an upload faces: its picture. |
| `PATCH /api/plan-assets/{id}` | An upload's `name`, `category`, `credit`, `mount` (floor, flat, wall), `anchor` [x, y] on the picture, `body` [x, y, w, h] about the anchor, `mirror` {facing: of}. |
| `DELETE /api/plan-assets/{id}` | Deletes an upload, unless a room uses it (in the draft, live, or a recent publish). |
| `GET /plan-art-credits` | The built-in pieces' pack credits, in full. |

Library items on the plan are `a:<id>` (catalogue entries carry their `rect`, `body`, `mount` and `facings`).

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

