# NPC tracking, history and behaviour overhaul, with a wipe

**Branch:** `main`

## Goal
Make NPC visits closer to a real casino and track far more about how NPCs and players play, then wipe the old NPC
stats so the new figures start clean:
- **Visits:** about 90 minutes, over several games, with one or two favourites and some dabbling.
- **Tracking:** a rolling house edge, actual against EV, for every bet spot.

The full approved plan, with Mike's decisions, the size and performance estimates and the design of each step,
is below.

## Files
- **Step 2:** `participants.py`, `store.py`, `app.py`, new `tracking.py`, `edges.py`, `edges.json` and
  `tools/edges.py`, `engines/craps.py` (the edge table moves in), and `admin_web/` (a new House section, plus the
  NPC and Player stats panels).
- **Step 3:** `roster.py`, `npc.py`, `casino.py` (halt), and the NPC editor and Settings in `admin_web/sections/`.
- **Step 4:** `admin.py`.

## Done when
- [x] Step 1: a backup (`server/data/casino.pre-npc-overhaul-20261104.sqlite`), the Stats archive page and
  `admin archive-stats`, the live archive "Before the NPC overhaul", and the 4 ledger rows put back (3eba437)
- [x] Step 2: per-spot tracking with EV for NPCs and humans, the 30-day NPC bet log, and the House section
- [x] Step 3: time-based visits with tastes, stints and leaving rules; visits resume after a restart
- [x] Step 4: `admin wipe-npc-stats` run on live 4 Nov 02:25 UTC: backup `server/data/casino.pre-npc-wipe-20261104-022543.sqlite`,
  archive "Before the NPC stats wipe"; 33,483 visits cleared, new tastes for 100 punters
- [x] A simulated day on a copy of the live data (the real Resort on a fake clock, a quarter pace, 24 hours'
  worth): 388 visits, mean 90 min, median 90, 2.9 games a visit, 8% on one game; hold vs EV inside ±2σ on every
  game but slots (unpriced at the time); every flush under 50 ms. DB growth was **~300k bet log rows a day, about
  47 MB a day, so ~1.4 GB at 30 days** (twice the plan's estimate: craps' chip-by-chip bets and 90-minute visits)
- [x] `tools/dev.sh test` passes

## Handoff
- **State:** done and live (8093057, then the wipe). Left for Mike: the questions below.
- **Changes from the plan, my calls:**
  - Budgets: the archetypes' default budgets are 3x (a Gambler's 5x) with the stake share cut to match, so the
    stakes on the felt are the same but a budget lasts a 90-minute visit (with the old budgets visits averaged
    44 min: casuals hit their stop-loss and gamblers bust within half an hour). Phil Ivey's hand-set budget now
    stakes a third of what it did.
  - Casual visits are 55-115 min, not 40-100: casuals are half the roster and visit most often, so 40-100 couldn't
    average 90.
  - The variance is stored as `var` (stake² x σ², summed) rather than `stake_sq`, so a Jackpot bet's spread can
    follow the pool.
  - Craps charges its edge per decision: a bet that wins and stays up is charged again.
- **Found on the way:**
  - The Blackjack £1 Jackpot pays back about £2.41 per £1 (house edge −141%): its fixed prizes (£10 flush, £30
    straight, £100 trips, £125 straight flush) are big for how often three cards hit. Not changed; Mike to decide.
  - `_keep_craps_busy` could redirect an NPC mid-walk, making them jump to where they were heading: it now only sends
    NPCs who are standing about.
- **Questions for Mike:** the Blackjack Jackpot paytable; whether 30 days of bet log (~1.4 GB) is fine or Settings
  should keep fewer.

## The plan

### Context

This follows on from the 4 Nov analysis (docs/npc-data-analysis-2026-11-04.md). NPC visits are short: a median
of 12 minutes, and almost always one game. That's because a visit is a single "play" step that ends after a
fixed number of rounds per archetype (gamblers 3–10). NPC money is only recorded per visit, so there's no money
by game, no bet spots, and no table or casino.

Mike wants:
- a rollback backup of the NPC data, and a frozen **Stats archive** page (admin, under Setup) showing things as
  they stand
- NPC behaviour closer to a real casino: about **90-minute** visits (his pick), several games, one or two
  favourites plus some dabbling; gamblers stay longer, hit-and-run leaves sooner, especially when up
- much deeper tracking for NPCs and players, including a **rolling house edge for every bet spot, actual
  against EV**
- then a wipe, so the new figures start clean

His decisions:
- **Wipe scope:** NPC stats only. Player stats and the ledger are untouched.
- **Restarts:** visits resume after a restart instead of being cut short.
- **Visit lengths:** the "Longer, ~90 min" defaults, editable on Settings › NPCs.
- **Bet detail:** daily rollups, plus a 30-day NPC bet log.

### Size and performance

Measured on the live data (about 44k NPC rounds and about 110k NPC money moves a day; rows today: visits 64 B,
ledger 83 B, plus about 100 B of `detail`):

| What | Rows | Growth |
|---|---|---|
| NPC bet log (`npc_ledger`), 30 days, pruned daily | ~110k a day | **~650–700 MB at steady state.** SQLite reuses freed pages, so the file stops growing at about that size |
| Richer `npc_visits` (per-game breakdown) | ~400 a day (25 on the floor, 90-minute visits) | ~60 MB a year |
| `bet_stats` daily rollup (casino × game × spot × who) | ~150–300 a day | ~5–10 MB a year |
| Lifetime per NPC or player × game × spot | ~10k rows, fixed | ~1 MB |
| Human ledger gains casino + table columns | as now | +~5% |

The database is 2.8 MB today. It would grow to about 700 MB in the first month, then by about 70 MB a year.

**CPU:** each money move becomes a few in-memory dict increments (microseconds). Every 30 s, one transaction
writes ~100 rollup upserts plus ~3,000 log rows with `executemany` (a few ms). The prune runs daily in
10k-row chunks so it never holds the write lock for long. That's well under 1% CPU, against the ~0.2% the server
uses now; human bets already write synchronously. None of this touches the client.

### Step 1: backup and Stats archive (do first, ship alone)

- **Backup:** `server/data/casino.pre-npc-overhaul-20261104.sqlite`, made with SQLite's backup API from a
  read-only connection. It's safe while the server is live, and matches the existing `casino.pre-*.sqlite`
  backups.
- **Put back the 4 ledger rows the master relabel deleted** (ids 3123, 3124, 3125 and 3189, 22 Oct; net +£25 to
  Mike). This runs after the backup, so a rollback covers it too.
  - `tools/restore_ledger_rows.py` copies them from `server/data/casino.pre-master-relabel.sqlite` with their
    original id, time, kind, note, amount and balance_after.
  - The later rows' balances already include them, so the chain mends itself and no balance changes.
  - Game: take the one the 25 Oct relabel would have given them. "side bets" on 3124 points to Blackjack. If
    the context doesn't settle it, keep `master_table`.
  - The script is idempotent: it skips ids that are already there, and it's one transaction, safe while live.
  - Check: Mike's `account='hand'` ledger sum equals his cash in hand (£25 short today), with zero balance
    chain breaks.
- **`casino_server/stats_archive.py`:** `build(store, title) -> dict`. It computes the report's figures from the
  store:
  - totals, NPC money by game (attributed from single-game visits), slots by machine, humans by game and player
  - archetypes, traits, how visits end, visit length and hands (overall and by game)
  - the top and bottom NPCs plus every NPC's lifetime row, the daily series, the jackpot pools, and notes on the
    data
  - `save()` writes `server/data/stats_archive/<date>-<slug>.json`, which is immutable, and lists archives.
- **API:** `GET /api/stats/archives` and `GET /api/stats/archives/{id}` in `app.py`, next to `/api/players`.
- **Admin page:**
  - `admin_web/sections/archive.js`, registered in `SECTIONS` in `admin_web/shell.js`, with an
    `<a href="#archive">` "Stats archive" link under `<div class="grp">Setup</div>` in `admin_web/index.html`
  - an archive picker, summary tiles, then the tables
  - built the same way as `sections/stats.js`: `init(h)`/`load()`/`shown()`, `head()` sortable columns, and
    `H.money`/`H.signed`
- **CLI:** `python -m casino_server.admin archive-stats "<title>"` (`admin.py` `main()`).
- **Now:** run it against the live data, after the ledger repair, so the archive's human figures reconcile →
  "Before the NPC overhaul (16 Oct – <today>)". Note the repair in docs/npc-data-analysis-2026-11-04.md's
  Problems section.

### Step 2: tracking (NPCs and players)

- **`casino_server/edges.py` + `tools/edges.py` → `casino_server/edges.json` (committed).** Each spot has a
  house edge and a σ per unit staked, with a source:
  - **Exact:** craps (move the `EDGES` table from `tests/test_craps.py` into `engines/craps.py`), roulette
    (1/37, La Partage), and baccarat.
  - **By enumeration from the engines' paytables:** the fixed side bets (Pair Plus, Prime, 21+3, Super Pairs,
    Top 3, Trips, the Let It Ride bonus, the High Card Flush flush and straight-flush bets, the 3 Card Bonus,
    Fortune, Envy, Dragon).
  - **Simulated with the NPC optimal strategy:** each decision game's **main line**. The EV is charged on the
    first wager (Ante), and Play, Raise, Double and Split add stake at 0 EV. "Actual vs EV" then shows skill
    plus luck, so NPC slips and Mike's play show up.
  - **The progressive Jackpot:** tier probabilities are stored, and the EV is worked out when the bet goes down,
    from the pool at that moment.
  - **Slots:** 1 − RTP for each machine, using the existing `slots/base.exact_line_rtp`, `slots/sim.py` and
    `slots/jackpots.rtp`.
- **`casino_server/tracking.py`, a `Tracker`:**
  - It lives on `app.state` and the Casino, per lifespan, never as a module global (Citadel pattern). Like
    `slots/stats.py` `SlotStats`, it keeps pending counts in memory and saves every 30 s and on
    `Casino.halt()`.
  - **Hooks:** `Participant.debit/credit/refund` and `NpcParticipant` in `participants.py`. These already
    receive the `detail` spots from `TableMachine._debit/_credit` (`tables/base.py`), craps
    (`tables/craps.py:388`) and slots. The participant learns its casino and table at sit time.
  - **What it records:** staked, returned, the expected house win (stake × edge) and the sum of stake² (for
    ±2σ bands).
- **New tables, set up in `store.py`'s schema:**
  - `bet_stats(day, casino, game, spot, who, bets, staked, returned, expected, stake_sq)`
  - `npc_game_stats(npc_id, game, spot, …, rounds, seconds)` and `player_game_stats(player_id, …)`, lifetime
  - `npc_ledger`: the same columns as `ledger`, plus npc_id, visit key, casino and table_id. It's pruned past
    `bet_log_days` (default 30, set on Settings › NPCs)
  - `npc_visits` gains `casino` and a per-game JSON
    `{game: {rounds, seconds, wagered, returned, expected, spins?}}`
  - `ledger` gains nullable `casino` and `table_id`
- **Admin:**
  - a new **House** section (#house): game → spots, staked, actual hold, EV hold, actual/EV with a ±2σ band;
    1d, 7d, 30d or all; All, NPCs or Humans; and casino
  - the NPC detail panel (`sections/npcs.js`): per-game and per-spot figures, and visits with their games and
    durations
  - Player stats: a per-spot breakdown with hold vs EV

### Step 3: behaviour

- **`roster.py`:**
  - `_SESSIONS[...]["rounds"]` becomes `"visit_min"`: grinder 75–165, casual 40–100, gambler 70–180, giving
    about 90 minutes across the archetype mix
  - stint lengths: favourite 20–60 min, dabble 8–20 min
  - all of it is editable through `DEFAULT_SETTINGS`/`clean_settings`
  - `Profile` gains `visit_seconds` and `tastes`
- **Tastes:**
  - `settings.tastes = {game: "fav" | "dabble" | "never"}`: 1–2 favourites and 0–3 dabbles, generated with an
    archetype bias:
    - grinders: Blackjack, craps, baccarat, Pai Gow, Ultimate Texas Hold'em
    - casuals: slots, roulette, Three Card Poker, Let It Ride, Mississippi Stud, High Card Flush
    - gamblers: craps, roulette, baccarat, slots, Mississippi Stud
  - Card counters get Blackjack as a favourite; superstitious NPCs get roulette or craps.
  - Existing `favourite_games` become favourites.
  - The NPC editor's favourites picker becomes three-state chips per game.
- **`npc.py` `NpcDirector`:**
  - `spawn` sets the visit's end.
  - **Picking a seat:** `_head_for_seat` picks a game by taste-weighted random choice (fav ≫ dabble ≫
    unlisted), not the strict favourites-first sort.
  - **Stints:** sitting down starts a stint. **`_time_to_go`** is already checked at every betting window in
    every game. It returns `"switch"` when the stint is over, which means `_move_on` (sometimes after a wander
    break), and `"done"` when the visit is over.
  - **Hit-and-run:** visit length × 0.5. They leave once up 10–30%, the existing `hit_and_run_pct` overrides
    that, and the chance to leave rises the further up they are.
  - **Gamblers:** longer visits; "riches" and "bust" still end them.
  - **Chasers:** they stay up to +50% past their time while down.
  - **Casuals:** a stop-loss at 60–80% of their budget.
  - `leavers()` (the Master Table) and `_keep_craps_busy` (which prefers NPCs who like craps) use tastes.
- **Resuming across restarts:**
  - `Casino.halt()` saves each NPC's open visit (Profile, bankroll, figures, time left, current stint) to a new
    `npc_open_visits` table, instead of logging "shutdown". Riding stakes still come back first
    (`TableRunner.hand_back`).
  - On start, the director brings those NPCs in first, with the downtime excluded. A visit saved more than 2
    hours ago is logged as "shutdown".

### Step 4: wipe (once steps 2 and 3 are live)

`python -m casino_server.admin wipe-npc-stats`. It refuses to run while port 8660 is listening.

1. `systemctl --user stop hub-proj-casino-world`
2. The command makes a fresh backup and a second archive (covering the days since step 1), then:
   - deletes `npc_visits`, `npc_open_visits`, `npc_ledger`, the NPC rows of `bet_stats`, `npc_game_stats` and
     the NPC rows of `slot_stats`
   - zeroes the `npcs` counters and cooldowns
   - sets `meta.npc_stats_since`
   - regenerates tastes; `--keep-tastes` keeps them instead
3. Start the server again.

Wallets, the ledger and player stats aren't touched.

**Rollback:** stop the server, `ATTACH` the backup, copy `npc_visits`, the `npcs` counters and the NPC rows of
`slot_stats` back, then start. The steps go into docs/development.md.

### Docs (same commits)

- docs/architecture.md: the Tracker, how money flows into stats, and resuming visits.
- docs/development.md: the admin sections, the CLI commands, retention, rollback.
- The NPC behaviour notes wherever they're documented (docs/games/*, "NPC play").

### Verification

- **Tests** (`tools/dev.sh test <file>` while working, the full suite before each commit):
  - `test_stats_archive`: on a copy of the snapshot, the figures equal the 4 Nov report.
  - `test_edges`: every spot each machine can emit has an edge; craps and roulette are exact; the Jackpot EV
    follows the pool.
  - `test_tracking`: human rollups equal the ledger sums; NPC detail is captured; EV builds up; flush and prune
    work.
  - `test_npc_visits`: with a fake clock, the average visit is about 90 minutes and averages more than one game;
    hit-and-run visits are shorter and gamblers' longer.
  - `test_resume`: halt, then a new director picks the visit up with the downtime excluded.
- **Simulation on scratch:** `tools/dev.sh server --live-data` (a copy of the live data, never the live config)
  at high speed for a simulated day. Check the visit durations, games per visit, hold vs EV on the House page,
  the flush timings (logged in ms) and the database growth, then compare against the estimates above.
- **UI:** one `tools/shot.py` screenshot each of Stats archive, House and the NPC panel on the dev instance.
- **Live:** after step 1, open https://192.168.0.66:8661/maintenance#archive.
