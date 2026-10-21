# Casino World: architecture

How the casino is put together. The rules of each game are in `docs/games/`, the messages in
`server/protocol.md`, and how a table is drawn in `docs/tables.md`.

## The idea

One continuous casino. Real players and NPCs walk the same floor, and sitting down happens in that world:
the camera glides onto the table, your avatar sits on the stool, and a dealer opposite deals, calls and pays
at a real table's pace. Every step is animated, and anyone walking past can watch a table live.

Mike's decisions that shape everything else (2026-10-16):
- **No separate table screen.** The camera zooms onto the table in the world. (The slots are the one
  exception: a cabinet opens a full-screen game that grows out of its little screen.)
- **NPCs** wander the floor and play at the tables.
- **Real-table pace,** with timers.
- **LPC pixel-art sprites,** at integer zoom on the floor so they stay crisp.

## The server: authoritative, one process

A FastAPI app (`app.py`) serves the web export, the admin page and one WebSocket per player at `/ws`. Every
game result and every penny is decided on the server; the client only renders and sends intents.

- **`Casino` (`casino.py`)** holds the sessions, the world, the tables, the NPCs, the store and the jackpot.
  It lives on `app.state` for the app's lifespan, and `start()`/`stop()` own its background tasks: one runner
  per table plus the NPC director. Messages are handled one at a time on the event loop, so no state needs
  locks.
- **The Slot design board (`slot_design.py`)** is on `app.state` too, with one background task of its own
  (`run()`, cancelled when the app stops) that works through its generate queue, one picture from the image model (whichever Odysseus has loaded) at a time
  in a worker thread. The board is the only shared state touched from threads (request handlers in the
  threadpool and the worker), so it holds a lock; jobs are saved in each design's `design.json`, so a restart
  carries on where it stopped.
- **Sessions (`session.py`)** each have an outgoing queue, so any handler can message any session without
  awaiting. A hidden browser tab sends `away` and the server stops sending; on `resync` it sends a fresh
  snapshot instead of minutes of stale events.
- **The world (`world.py`)** is every avatar on the floor: `{id, kind, name, look, x, y, dir, anim, seat,
  walk}`. Players move themselves and report it (`move`, about 10 times a second), and the server relays it.
  NPCs are sent walks instead (`entity_walk {id, target, duration}` to a named point or a seat). Each client
  paths them on its navigation map at whatever speed arrives on time, so everyone sees them arrive
  together and the server needs no floor geometry. The point names live in `floor.py`, and each must exist as
  a `Marker2D` in the client's floor scene.

### Tables: pure machines, driven in real time

- **A table machine** (`tables/<game>.py`, on top of `tables/base.py`) is pure and synchronous. Every method
  takes `now` and returns a list of events; `tick(now)` advances whatever is due, and `next_deadline` says
  when to call it next. `base.py` has what every game shares: seats, betting, Ready, Rebet and Auto rebet,
  bets queued for the next hand, sitting out, and the clock. Each game adds its own phases and events. The
  tests drive machines directly, tick by tick, with no sleeps.
- **The rules** are in `engines/`: ported from v2 (with parity tests to the penny) for the card games, and
  new for Roulette and Craps (tested against the exact arithmetic). `slots/` is the slot engine and its
  variants.
- **`TableRunner` (`tables/runner.py`)** drives one machine: it sleeps until the next deadline or a player's
  action, ticks it, and publishes the events. Every joined session gets every table's events, so tables are
  live to watch from the floor. A late joiner gets a `table_state` snapshot first.
- **Privacy and money.** Event keys starting `_` never leave the server. Cards only one seat may see go under
  `_private` and reach only that seat's session. `_paid` lists whoever's money the event moved, and they get
  a `wallet` straight after it.
- **Participants (`participants.py`).** A seat holds a participant, human or NPC, with the same `debit`,
  `credit` and `refund`. The machine never knows which kind it's dealing with, so NPCs play by exactly the
  same rules and money moves.
- **Timings** are a dataclass per game. `CASINO_SPEED` scales them, and tests use instant ones.

### NPCs, dealers and the roster

- **The roster** is persistent (`store.py` tables `npcs` and `npc_visits`; `roster.py` for archetypes,
  traits and seeding) and is edited on the admin page.
- **The NPC director (`npc.py`)** brings punters in to fill the floor population. Each visit has a budget
  they're willing to lose, and they leave bust, done for the day, or ahead depending on their traits, then sit
  out a cooldown. They pick games by preference, play each game's published strategy (with style-dependent
  mistakes and side bets), and never take a table's last two free seats. The craps table is kept to at least
  two NPCs.
- **Dealers (`dealers.py`)** come from the same roster and work staggered shifts, relieved only between
  hands. Their lines are in `dealer_lines.toml` (`dealer.py`), reread on every line.
- **Looks** are built server-side from LPC layers (`art.py`, shared with `tools/build_art.py`) and fetched by
  the client as it meets them.

### Storage and money

`store.py` is SQLite: players (one per device token), balances in integer pence, a ledger row for every
change in the same transaction (so balances always reconcile), the roster, and a `meta` table. The table
games share one progressive jackpot (`jackpot.py`), worked out from elapsed time when read, with no
background task. The slots have their own Mini/Minor/Major/Grand meters (`slots/jackpots.py`).

## The client: one world, a camera, an animation queue per table

A Godot 4.7 project exported to the web.

- **Autoloads:** `Net` (the socket, reconnects, away/resync), `Session` (who you are, your balance, the
  jackpot meter), `Sfx` (sounds chosen on the admin page), `Settings`, `LookLoader` and `SlotArt`.
- **Slot variants** (`server/casino_server/slots/`): a variant (`variant.py`) brings its strips, rates and bonus
  settings, and its own pays, upgrade chain, feature list and `routes` (which bonuses 3+ BS, 3+ FS and Buy Bonus
  play; `outcome.pick_bonus` draws one only when there are several, so one bonus per way in spins as it always
  has), defaulting to the house standard in `base.py`, which is Armadillo's. Armadillo is Python; slots built with
  the Slot design wizard are `variants/<id>.json` with frozen strips. The browser's `slots_math.js` takes the same
  tables, so the wizard's mockup spins exactly as the cabinet will (`tests/test_slot_variants_data.py` checks a
  five-royal variant with a shared bonus scatter spin for spin).
- **Built slots** (`slot_builds.py`) join at startup, before the casino is made: their variants, their sound sets
  (`sounds.refresh_sets` rebuilds the sets in place), and their art and fonts in the art manifest.
- **Slot banks** (`slot_banks.py`, `<data>/slot_banks.json`) put the cabinets on the floor: a bank is any mix of
  slots, each cabinet facing any way, made and dragged into place on the admin page's Floor tab. At startup, after
  the built slots, each cabinet whose slot is loaded becomes a one-seat table in `floor.TABLES` (its id is its table
  id, kept through moves and re-slotting). Saving checks the banks against `floor_map.json` (the room, the tables'
  footprints and the floor points, measured from the client scene by `tools/floor_map.gd`) and each cabinet's
  shape; the floor changes when the server restarts (the tab's Apply). The welcome message lists every cabinet, and
  the client adds, remakes or removes its own to match. Both `install()`s undo their last run first, so tests can
  run them again.
- **Sounds** come in sets (`server/casino_server/sounds.py`): the whole casino, then each table game, and
  every slot machine, then each machine. A set without its own sound for a moment plays the one above's.
  The server's manifest lists each set's own moments and which set each table uses; `Sfx` downloads the
  files, resolves a moment up the tree for the table it's played at (`Sfx.focus` is the one you're seated
  at), and loops a copy of a stream for `start_loop` so its one-shot uses stay one-shots.
- **The floor (`scenes/world/casino_floor.gd`)** routes server messages to avatars and tables, and turns
  clicks into requests. Everything on it is under a Y-sorted `World` node, and every position the floor and the
  server use is in World's frame. The camera follows you at zoom 2 while walking and glides onto a table at 2.8
  when you sit. At a table that's turned round (the far row of the Blackjack pit), the glide also turns World
  about the table so it's the right way up, and the Y-sort turns with it (`docs/tables.md`, Turned tables).
  The camera itself never turns, and avatars keep themselves upright. The navigation region sits outside World,
  so the nav map stays in World's frame through a turn; a bake waits until the floor is upright. The rooms
  (the main floor and the Blackjack pit room, joined by a doorway), the tables and the felt are drawn in code,
  so they stay sharp at any zoom.
- **Avatars:** `avatar.gd` shows a look, a name tag (an MSDF font) and a speech bubble. `local_player.gd`
  drives you (keys, click-to-walk, click and hold), and `entity_avatar.gd` drives everyone else: other
  players' reported moves are smoothed, and NPC walks are pathed.
- **Tables (`scenes/table/`)** extend `FloorGame`, and the card tables, Roulette and Craps extend
  `CasinoTable`. `apply_snapshot()` draws a `table_state` at once; `handle_event()` turns each `table_event`
  into animation steps on a queue that plays in order, speeding up if it falls behind. A new snapshot starts
  a new epoch, which cancels every step still pending. Nothing on the client decides an outcome.
- **The HUD (`scenes/ui/hud.tscn`)** has the balance and jackpot while walking, and the chip tray, bet
  buttons, decisions and countdown while seated. Game-specific panels (the Pai Gow sorter, the slot screen)
  sit alongside it.

## Working on it

- **Checks:** the server tests (`tools/dev.sh test`) cover the machines, engines, NPCs and the socket. The
  client has the layout audit (`docs/tables.md`) and `tools/shot.py` for screenshots against a dev instance.
  See CLAUDE.md for how much checking a change needs.
- **Never use the live data for tests:** dev instances use `.dev/data`, and the tests a scratch directory.

## Not done yet

- Staff other than dealers (waiters, pit bosses, cashiers, bar staff) can be designed but don't work the
  floor. The pit room's pit boss is a figure at a podium, nothing more.
- Slot banks can only go on the main floor (`floor_map.json`'s `walkable` is that room).
- Baccarat's 5 Treasures side bets are in the engine but not on the layout.
- Customising your own look, chat and emotes.
- Trusted HTTPS certificates, and a portrait phone layout.
- A floor redesign with decor (a bar, a cashier's cage, plants): the rooms are still just the tables, so NPCs
  wander between aisle points.
