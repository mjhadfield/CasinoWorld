# Casino World: architecture

How the casino is put together. The rules of each game are in `docs/games/`, the messages in
`server/protocol.md`, and how a table is drawn in `docs/tables.md`.

## The idea

A resort of casinos, each one continuous. Real players and NPCs walk the same floor, and sitting down happens in that world:
the camera glides onto the table, your avatar sits down in a chair, and a dealer opposite deals, calls and pays
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

- **One lifespan for both ports.** `__main__.py` runs the app's lifespan itself, once, and serves HTTP and HTTPS
  from the same app with uvicorn's lifespan off (each port running its own had made two whole Resorts). It
  handles the signals too: on SIGTERM or Ctrl+C every casino halts first (`Resort.close`, while everyone's still
  connected), then the ports stop. See **A stop mid-hand** below.
- **`Resort` (`resort.py`)** is on `app.state` for the app's lifespan. It holds every connected session and the
  casinos (`casinos.py`'s registry, `<data>/casinos.json`: Mike's decisions, 2026-10-27), and what they share,
  made once and handed to each: the store (a character's cash and bank), the card progressive and the slots'
  progressives and figures, and the NPC cast with its **claims** (`casinos.Claims`, npc id -> casino id: a punter
  is claimed from coming in until they've walked out, a dealer for their shift, and the other casinos' directors
  and rosters skip anyone claimed, so nobody is in two at once; the house's generic Dealer fills any gap, and deals
  every table of a hidden casino, so one still being built doesn't keep the cast from the open ones). It
  handles everything before a floor: `join`, characters, bans, and the casino chooser (`casinos`,
  `enter_casino`, `leave_casino`); a session that has entered a casino (`session.casino`) has the rest handled
  by that casino. Every casino in the registry runs all the time, players or not.
- **`Casino` (`casino.py`)** is one casino: its floor (`floor.Floor`), its sessions, the world, the tables, its
  NPC director (counting its own visitors, up to the registry's `population`) and dealer roster. Its broadcasts
  go to its own sessions only, so you only see and hear the casino you're in; a jackpot win is the exception
  (`broadcast_resort`: every casino hears the new pool, and only the one it was won in is told the table).
  `start()`/`stop()` own its background tasks: one runner per table plus the NPC director. Messages are handled
  one at a time on the event loop, so no state needs locks.
- **The Slot design board (`slot_design.py`)** is on `app.state` too, with one background task of its own
  (`run()`, cancelled when the app stops) that works through its generate queue, one picture from the image model (whichever Odysseus has loaded) at a time
  in a worker thread. The board is the only shared state touched from threads (request handlers in the
  threadpool and the worker), so it holds a lock; jobs are saved in each design's `design.json`, so a restart
  carries on where it stopped.
- **Sessions (`session.py`)** each have an outgoing queue, so any handler can message any session without
  awaiting (from an admin request's worker thread too: the push is handed to the event loop). A hidden browser
  tab sends `away` and the server stops sending; on `resync` it sends a fresh snapshot instead of minutes of
  stale events. A client that stops reading without saying so is cut off once 2,000 messages are waiting, and
  reconnects to a fresh snapshot.
- **The world (`world.py`)** is every avatar on the floor: `{id, kind, name, look, x, y, dir, anim, seat,
  walk}`. Players move themselves and report it (`move`, about 10 times a second), and the server relays it.
  NPCs are sent walks instead (`entity_walk {id, target, duration}` to a floor-plan point,
  `point:<room>/<name>`, or a seat). The server times a walk by its distance through the doorways (the casino's
  `floor.Floor`, made from the floor plan); each client paths it on its navigation map at whatever speed arrives on time, so
  everyone sees them arrive together. A walk that comes before the map is ready (the snapshot as the page loads,
  just before the floor's bake reaches the navigation server) waits for it rather than cutting across the tables,
  and every walk is re-pathed whenever the map changes. The server keeps an NPC's `x, y` as where its walk set
  off from (or where it stopped), so a snapshot mid-walk starts them that far along their path rather than at
  the players' spawn point, and they still reach the arrival point they leave by before they're despawned.

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
  action, ticks it, and publishes the events. Each joined session gets the events of the tables near it, so
  they're live to watch from the floor, and a `table_state` snapshot as one comes near: `Floor.near` (from
  `plan.near_tables`) is each room's tables in the rooms it can see (its archway-joined rooms and one door on),
  and `Floor.tables_near` keeps to those within `VIEW` of where you are (`Casino.look` works it out again as you
  move, or from your table while you sit; `Session.sees` holds it). The rest it's only told who sits where
  (`table_seats`), so the far tables' chairs and Find stay right. Entering the Boulevard sends a few tables'
  states rather than all 133.
- **Privacy and money.** Event keys starting `_` never leave the server. Cards only one seat may see go under
  `_private` and reach only that seat's session. `_paid` lists whoever's money the event moved, and they get
  a `wallet` straight after it.
- **A stop mid-hand.** Every machine counts what each participant has down on it that it hasn't settled
  (`riding()`: in `base.py`, stakes go on through `_debit` and come off as a payout row (`_credit`) or a sweep
  (`_lost`: a fold, a bust) settles them, and nothing rides past a hand's end; Craps reads its layout instead, and a
  slot's spin is settled as it's made). The runner keeps the players' figures in the store's `stakes` table as they
  change. `Casino.halt` (the server stopping, or a reload) cancels the tasks, lets each table pay what needs no
  decision (`wind_up`: a slot's bonus plays out), and hands back everything still riding (`TableRunner.hand_back`):
  into a player's hand with a ledger row noted "handed back", told at once with a `notice` if they're there, or
  when they next enter; into an NPC's bankroll before their visit's logged. A halted casino doesn't stand anyone
  up, so leaving can't fold a hand that's no longer dealt. After a crash, the next start hands back whatever the
  `stakes` table still says was riding (`Store.return_stakes`, from `Resort`), before any table deals.
- **Participants (`participants.py`).** A seat holds a participant, human or NPC, with the same `debit`,
  `credit` and `refund`. The machine never knows which kind it's dealing with, so NPCs play by exactly the
  same rules and money moves.
- **A second box** is a real seat, linked to its player's (`Seat.box` / `Seat.box_of` in `base.py`). It holds a
  `BoxParticipant` that spends through its player's own participant but counts its own flow, so the box is dealt,
  decided and settled like any seat and gets a `round_net` of its own. `set_bets`, Ready and queued bets mirror the
  player's onto it; `humans_seated()` and `seat_of()` skip it. In the decide-at-once games its `_private` parts only
  reach its player (as `mine_box`) once their own hand has decided (`_reveal_boxes`, `box_revealed`).
- **Timings** are a dataclass per game. `CASINO_SPEED` scales them, and tests use instant ones.
- **The Master Table (`tables/master.py`)** is a machine that holds another: whichever card game it's been asked
  for, built by the Casino's `_make_machine` and passed everything it doesn't handle itself, so the runner, the NPCs
  and the message handling see an ordinary table of that game (its `game` too: `master_table` only while blank).
  It swaps the inner machine between hands (seats renumbered when the count changes 6↔5: the runner sends everyone
  near it a fresh `table_state` (the rest its `table_seats`), and `Casino.on_reseated` moves sessions, the world's seats and NPCs to their new seats;
  the floor's `seats` follow the seat count). The client swaps in that game's own table scene (`casino_floor.gd`,
  `MasterSwap`).

### NPCs, dealers and the roster

- **The roster** is persistent (`store.py` tables `npcs` and `npc_visits`; `roster.py` for archetypes,
  traits and seeding) and is edited on the admin page. Archived NPCs (`archived_at` set) are left out of
  `store.npcs()` by default, so neither the director nor the dealer roster ever picks them. Roles and uniforms are
  `staff.py`: the built-in roles and uniforms with the admin page's additions and changes laid over them.
- **The NPC director (`npc.py`)** brings punters in to fill the floor population. Each visit has a budget
  they're willing to lose, and they leave bust, done for the day, or ahead depending on their traits, then sit
  out a cooldown. They pick games by preference, play each game's published strategy (with style-dependent
  side bets and believable slips on close calls from `npc_slips.py`, each side bet a share of their main bet that they keep for the visit), and leave
  the seats kept for real players free (`reserved_seats`: the middle seat of a five-seater, the middle two of
  a six-seater, the second place from the left on each side at Craps). A player can ask one for their seat
  (`kick`): they get up at once if nothing's riding, else at their next round boundary (`_time_to_go` says
  `kicked` while `Session.kick` still names them), and `_leave_table` sits the player straight down. The craps table is kept to at least two NPCs. The admin page's NPC switch
  (`npcs_on`, read each tick) turns them off: they leave at their next round boundary (the same check as being
  done for the day) with no cooldown, and come back one at a time when it's turned on.
- **Back-off (`heat.py`)**: one `HeatWatch` on the Resort (shared by its casinos, handed to every Blackjack and
  Master Table machine as `machine.heat`) scores each Blackjack round's main bets against the true count before
  the deal (`BlackjackMachine.count`), warns, then backs off players and NPCs alike. The machine refuses a
  backed-off `sit`, stands a backed-off player after the round and sends `heat`; the Master Table won't change to
  Blackjack for one; the NPC director moves its own on. Held in memory, keyed by character or NPC id. Its
  warnings and back-offs are logged (`casino.heat`; `__main__` sends the `casino.*` loggers to stderr).
- **Dealers (`dealers.py`)** come from the same roster and work staggered shifts, relieved only between
  hands. One archived or deleted while dealing is relieved at the next betting window (`stand_down`), by the house's
  generic Dealer if nobody's free. Their lines are in `dealer_lines.toml` (`dealer.py`), reread on every line.
- **Looks** are built server-side from LPC layers (`art.py`, shared with `tools/build_art.py`) and fetched by
  the client as it meets them.

### Storage and money

`store.py` is SQLite (WAL, so a commit on the event loop costs microseconds; copy it with `.backup`): accounts (one per device token, holding the ban, timeout and Protected state), their characters (the `players` table, up to three an account, each with a name, a look spec, a difficulty and its own money), balances in integer pence, a ledger row for every
change in the same transaction (so balances always reconcile), the roster, and a `meta` table.

A session joins as an account and then picks a character (`Session.account`, then `Session.player`); only a
picked character is on the floor. The ledger, the ATM and the stats all key on the character. A `HumanParticipant`
remembers the character that sat down, so a hand that finishes after a switch pays that one. A new character's bank
comes from the difficulty picked for it (`bank.start_bank`); nothing else about the game changes with difficulty.

A character has two balances. **Cash in hand** (`players.balance`) is what every table bets from and what the HUD's
top left shows. The **bank** (`players.bank`) can go overdrawn. Money moves between them only at the lobby's ATM
(`bank.py`, `Store.transfer`), which writes a ledger row per account (`ledger.account` is `hand` or `bank`), and
the ATM's rules are the admin page's Bank settings: new players' starting bank and cash, withdrawals in £50 notes
only while holding under a limit, the usual per-withdrawal limit, the bigger withdrawal a bank over a threshold
allows (half the bank rounded down to a step, once per wait; `players.last_big_at`), and the wait between
withdrawals while overdrawn. An ATM is any library piece with `"interact": "atm"`: the server checks a player is
standing at one (by their last `move`) before it'll serve them. NPCs keep their own in-memory bankrolls and never
touch the store.

A game's bet and payout rows carry `ledger.detail`, JSON for the stats: a bet row has what went on each spot
(`{"spots": {"bet": 1000, "super_pairs": 300}}`), a payout row each bet it settled with its stake and what came back
(stake and winnings, 0 if lost: `{"spots": {"top_three": {"stake": 300, "returned": 81300}}, "hand": "..."}`), so
side bets can be counted one by one. Every game passes it through `Participant.debit` and `TableMachine._credit`
(`stakes_detail` and `returns_detail` in `tables/base.py`), and a settlement with a detail is written even when it
returned nothing. `_credit` also tallies each winning spot in the machine's `round_book` (cleared as the next hand's
bets are taken; at Craps at each seven-out), which the round summary's highlights come from.
Blackjack adds each hand on the box (`hands`), Craps marks a win whose stake stays up (`stays`) and any `vig`, and a
slot row just names its `machine`. Rows from before the column have none (`Store.adjust` has the full shape).

The table
games share one progressive jackpot (`jackpot.py`), worked out from elapsed time when read, with no
background task. Every card table shows it on its own jackpot sign (docs/tables.md); after a win, the new amount
names the table it was won at, so only that table's sign celebrates. The slots have their own Mini/Minor/Major/Grand meters (`slots/jackpots.py`).

Each card table has limits on its main and side bets: set per table on the floor plan (`plan.py`, item
`props.limits`, else `DEFAULT_LIMITS` in `tables/base.py`), carried in the Floor's `tables` to the table's machine
(`TableMachine.limits`, refreshed on a publish by `Casino.broadcast_world`; a Master Table hands them to each game
it becomes) and in the world message to the client's limits sign. The machine refuses a bet over a maximum and
Ready under a minimum, and hands back a bet still short when betting closes (`_hand_back_short`).

## The client: one world, a camera, an animation queue per table

A Godot 4.7 project exported to the web.

- **Autoloads:** `Net` (the socket, reconnects, away/resync), `Session` (who you are, your balance, the
  jackpot meter), `Sfx` (sounds chosen on the admin page), `Settings` (sound, and the Graphics presets with
  their auto step-down), `LookLoader` and `SlotArt`.
- **Performance** (docs/performance.md): nothing is redrawn every frame unless it's moving and on screen;
  felts are shown as one painted picture each (`FeltCache`), and the floor isn't drawn under the slot screen.
- **Slot variants** (`server/casino_server/slots/`): a variant (`variant.py`) brings its strips, rates and bonus
  settings, and its own pays, upgrade chain, feature list and `routes` (which bonuses 3+ BS, 3+ FS and Buy Bonus
  play; `outcome.pick_bonus` draws one only when there are several, so one bonus per way in spins as it always
  has), defaulting to the house standard in `base.py`, which is Armadillo's. Armadillo is Python; slots built with
  the Slot design wizard are `variants/<id>.json` with frozen strips. The browser's `slots_math.js` takes the same
  tables, so the wizard's mockup spins exactly as the cabinet will (`tests/test_slot_variants_data.py` checks a
  five-royal variant with a shared bonus scatter spin for spin).
- **Built slots** (`slot_builds.py`) join at startup, before the casino is made: their variants, their sound sets
  (`sounds.refresh_sets` rebuilds the sets in place), and their art and fonts in the art manifest.
- **The floor plan** (`plan.py`, `<data>/casinos/<id>/plan/`: each casino in `casinos.py`'s registry has its own, and a
  `PlanBoard`) is a casino's layout as data: rooms side by side on one plan,
  each with its walls, floor, doors and archways, the tables, slot cabinets and pieces placed in it, and the NPCs'
  points (spawn, arrival, wander, with weights and linger times) and no-go zones. The admin page's Floor plan tab
  edits a draft (`draft.json`); publishing copies it to `live.json` (the last 20 publishes kept in `history/`).
  At startup, after the built slots, `plan.install` makes a `floor.Floor` (the Casino's `floor`, and the
  `PlanBoard`'s) from the live plan's placed rooms: the plan itself, every table
  and cabinet (an item's id is its table id, given by the server and never reused; a slot bank is one item whose
  cabinets, `<bank id>_<n>`, are what everything past the plan sees), the points, each seat's
  standing spot, the doorways (`plan.Routes`, for how long an NPC's walk takes) and each table's sound set. A
  publish that only moves things installs a new Floor at once (`Casino.broadcast_world` takes it) and sends everyone
  `world`; one that adds or removes tables reopens just that casino in-process (`Resort.reload`: the old Casino stops
  as at shutdown, a new one starts on the new Floor, and its players get `casino_left` {`reload`} and a fresh
  welcome; the other casinos carry on). Only a slot built since the server started still needs a restart (a start
  is what loads a built slot). The checks
  (`plan.problems`: things off the floor or in each other's way, doors that don't line up, seats and points nobody
  can walk to, by a flood fill over the plan) use the tables' and cabinet's shapes in `plan_catalogue.json`,
  measured from the client's scenes by `tools/plan_catalogue.gd`. The first run seeds the lobby (live) and the
  classic floor and pit (`plan_classic.json`, the old hand-built floor) as unplaced blueprints. The welcome sends
  the placed rooms (`plan.world`), and a preview (`join` with `preview`) gets the draft's instead. Settings kept by
  table id (table styles, seating, an NPC's `avoid_table`) are kept by qualified id, `<casino>/<table>` (each plan
  has its own id serials), and each casino sends its own slice by plain id; they count every table in the plan,
  placed or not, and the sound sets cover every game, so
  taking a room off the floor loses neither.
- **The asset library** (`plan_assets.py`) is the furniture, decor, rugs and floor textures rooms can use: the
  built-ins in `server/plan_assets/` (cut from LPC packs by `tools/build_plan_assets.py`) and uploads in
  `<data>/plan_assets/`. It fills `plan.ASSETS` and `plan.FLOORS` (each asset's footprint, how it stands, its
  pictures per facing), which the checks and the admin page use. The game's `PlanArt` autoload fetches the
  manifest and the pictures at runtime and refetches on `plan_art_changed`, so new art needs no export; a
  `Furniture` node shows a piece (and blocks walking) once its picture is in, and the floor bakes again. Pictures
  and floors are 1:1 pixel art unless they carry a `scale` (the Vegas floor's are 2): those are shrunk to their game
  size and smoothed, and everything about placing them (anchor, footprint, screen) stays in game pixels.
- **Sounds** come in sets (`server/casino_server/sounds.py`): the whole casino, then each table game, and
  Default, then the slot presets made on the admin page, then each machine under the preset it follows. A set
  without its own sound for a moment plays the one above's. Each bonus game (Trail, Battle, Voyage, Expedition)
  has a set of its own that no machine can change; the manifest folds those into Default's, the end of every
  machine's chain, so the game needs no idea of them. The presets and each machine's choice are in
  `sounds.json` beside the picks. The server's manifest lists each set's own moments and which set each table uses; `Sfx` downloads the
  files, resolves a moment up the tree for the table it's played at (`Sfx.focus` is the one you're seated
  at), and loops a copy of a stream for `start_loop` so its one-shot uses stay one-shots.
- **The floor (`scenes/world/casino_floor.gd`)** routes server messages to avatars and tables, and turns
  clicks into requests. Everything on it is under a Y-sorted `World` node, and every position the floor and the
  server use is in World's frame. The camera follows you at zoom 2 while walking and glides onto a table at 2.8
  when you sit. At a table that's turned round (the far row of the Blackjack pit), the glide also turns World
  about the table so it's the right way up, and the Y-sort turns with it (`docs/tables.md`, Turned tables).
  The camera itself never turns, and avatars keep themselves upright. Chairs and sitting down come from the
  server's seating styles (`seating.py`, in the welcome): `scripts/seating.gd` draws every chair (the seat under
  its sitter, its back in a `ChairBack` node just behind them in the Y-sort) and plays the same sit-down and
  getting-up for you, other players and NPCs. The camera, and a slot's full-screen game, wait for your sit. How each
  table looks comes the same way, from the server's table styles (`table_styles.py`: one set for the card tables,
  one for Roulette, one for Craps; in the welcome and in a `table_styles` broadcast): `scripts/table_style.gd`
  holds them and `StyledFelt` paints every table in its style. The floor itself is built from the floor plan in
  the welcome (`world`): a `PlanRoom` (`scenes/world/plan_room.gd`) per room under `World/Rooms`, drawing its floor
  and walls in code (so they stay sharp at any zoom), cutting its doorways (`PlanDoor` swings a door open as
  anyone nears it), and placing its tables, cabinets, pieces (`Furniture`; a piece with a `screen`, the jackpot
  board, gets a `PlanScreen` drawing the live jackpot) and standing figures. Everything standing Y-sorts with the
  people; rugs and wall pieces (items with `mount`) go in its `Rugs` and `WallPieces` layers instead, drawn in the
  plan's order, so the Floor plan's restacking shows in the game. A `world` message rebuilds it,
  after you stand up if you're sitting, and resyncs for fresh table states. Rooms joined by archways show
  together; a room through a door shows once you're in the doorway; hidden rooms keep running (`visible` only),
  people in them are hidden and their sounds go unheard (`Sfx.audible`), and the camera keeps to the rooms on
  show. The navigation region sits outside World, so the nav map stays in World's frame through a turn; a bake
  (every room's outline, less the wall bodies, which leave the doorways open, and everything in group
  `navigation_obstacles`) waits until the floor is upright. A tap walks you along the nav map's path. A zone of
  kind `npc_block` is a static body on collision layer 2: in the navigation bake but not in your way, so NPCs
  path round it and players walk through. An NPCs-only room (a lift) is the other way round: a bar across each of
  its doorways on layer 1, left out of the bake, stops you but not NPCs; its doors don't open for you and it never
  shows, so NPCs arriving there step out of a shut door. Each table's and cabinet's chairs block walking too (a circle round the
  chair's base, `Seating.body_radius()`, on the table's `Chairs` body, so in the bake as part of the table), and so
  does everyone else (`Avatar.add_body()`: collision layer 3, which only your body collides with; out of the bake
  since they move, except the plan's standing figures, which stay put). A preview (`?preview=<room>`) builds the draft's floor to walk round
  alone.
- **Avatars:** `avatar.gd` shows a look, a name tag (an MSDF font) and a speech bubble. `local_player.gd`
  drives you (keys, click-to-walk, click and hold; you slide along whatever you bump into), and
  `entity_avatar.gd` drives everyone else: other players' reported moves are smoothed, and NPC walks are pathed.
  Their bodies block you while they're up and in sight (not while sitting, when the chair blocks instead).
- **Tables (`scenes/table/`)** extend `FloorGame`, and the card tables, Roulette and Craps extend
  `CasinoTable`. `apply_snapshot()` draws a `table_state` at once; `handle_event()` turns each `table_event`
  into animation steps on a queue that plays in order, speeding up if it falls behind. A new snapshot starts
  a new epoch, which cancels every step still pending. Nothing on the client decides an outcome.
  Each says what a click on it would use (`clickable_at()`: a free chair while you walk, your bet spots
  when you're sat), and the floor shows the pointing hand over those and the ATM (`_update_cursor()`).
- **The front door (`scenes/ui/front_door.gd`)** covers everything until you're on the floor: the loading screen
  while connecting, then the character select (`Session.characters` from `account`) and the designer (its look
  controls are `look_editor.gd`, a port of the admin page's NPC designer; the preview is built by the server's
  `POST /api/looks/preview` and fetched by `LookLoader`), then the casino chooser (`Session.casinos` from `casinos`:
  a card per casino, the last one lit). It follows Session: shown whenever you aren't on the floor, hidden by
  `welcome`. From the wallet it opens the chooser in switch mode (fresh counts by `list_casinos`): another casino
  sends `leave_casino` then `enter_casino`, and Change character goes to the select (`leave_character` then
  `pick_character`); the floor's `_off_the_floor()` clears what it showed, it rebuilds when the welcome's casino or
  plan rev differs from what it built, and the next `welcome` starts you at the spawn point. After a dropped
  connection Session picks the same character again with `resume` and the casino it was in, so you come back where
  you were. A page opened with `?casino=<id>` goes straight into that casino on picking (a hidden one too).
- **The HUD (`scenes/ui/hud.tscn`)** keeps Settings and then your name, connection and cash in hand top left
  (`wallet_pill.gd`, with a round's result flashing beside it; clicking it opens the front door's casino chooser to switch
  casino or character), under them while seated the whole table's last round (`round_summary.gd`, from the
  `summary` in server/protocol.md; Settings › Round summary), and the minimap top right, walking or seated. The
  minimap (`scenes/ui/minimap.gd`, signed off on `docs/minimap/mockup/`) draws your room and every room one doorway
  on (an archway's rooms count as one; a room the plan marks off the minimap is left out), with the tables, slot banks and ATM (a square saying ATM) in their kinds'
  colours, full tables faint, other real players as dots and you as an arrow; past a readable scale it pans with you,
  a door to a room further on gets a named tab, and it turns with a turned table. It starts folded to a map button;
  its size (Small by default), table names (the ATM's too) and zoom (steps from its smallest view, two in by default)
  are settings. The floor feeds it each frame (`follow`) and works out its Find: the nearest table of a kind by the
  nav map's path (one with a free seat first), or, clicking a table, bank or ATM the map names, that one; drawn on the
  floor (`scenes/world/route_line.gd`) and the map, with Walk there, until you arrive, sit anywhere, or stop it. Find's
  way is planned like a person would walk it: on a second, roomier nav map (the floor baked again with 24px clearance,
  its own `NavigationServer2D` map), joined to where you stand and to the goal on the tight one, then rounded at each
  corner as wide as the floor allows (every point of the curve checked standable). Walk there walks that exact way.
  On the floor it's a ribbon (brass rails, chevrons flowing on, a beacon at the end) built once per path and animated
  by its shaders, so it never redraws while it plays; the part behind you fades with a shader parameter. On
  the small map Find's list keeps to its width. Walking, standing at a piece
  you can use (furniture in group `interactables`: the ATM) shows a prompt under your feet (E, or click the piece),
  as does standing by a table or slot with a free chair (Play: you sit in the nearest free chair), and the ATM's
  screen (`scenes/ui/atm_panel.gd`, drawn like the slot screen and signed off on `docs/atm/mockup/`) holds you
  still until you leave it. Seated, its betting bar
  (`scenes/ui/betting_bar.gd`, signed off on `docs/betting_ui/mockup/`) takes the foot of the screen: the table's
  name, how many are seated and what you have on the felt on the left, the table's chips dead centre with a line
  above them only when you've a decision on the clock (bets closing, your turn, the sorter, with its draining countdown)
  or a prompt you asked for (a hovered spot's payout) -- it doesn't narrate the hand, Ready (Repeat Bet until you've bet; Craps: the
  dice) on their left, Undo, Clear, Auto rebet and Sit out (Craps: Working) on their right, and a decision in the
  chips' place while it's open, and Stand up at the bar's right edge; Paytable top right left of the minimap (the paytable opens under it, folding the minimap if it was open, and scrolls when a game's rules run past the screen). Each table's `seated_view()` feeds it (an action's `place`: `commit` beside the chips,
  `switch` a switch, else a decision). Game-specific panels (the Pai Gow sorter, the slot screen) sit alongside it.

## Working on it

- **Checks:** the server tests (`tools/dev.sh test`) cover the machines, engines, NPCs and the socket. The
  client has the layout audit (`docs/tables.md`) and `tools/shot.py` for screenshots against a dev instance.
  See CLAUDE.md for how much checking a change needs.
- **Never use the live data for tests:** dev instances use `.dev/data`, and the tests a scratch directory.

## Not done yet

- Staff other than dealers (waiters, pit bosses, cashiers, bar staff) can be designed but don't work the
  floor. A standing figure on the floor plan (the classic pit's pit boss) is decoration, nothing more; the dealer
  delivers the pit's Blackjack back-off.
- Every room of a casino is still built on its clients, and everyone on the floor (NPC walks included) goes to
  everyone in it; only the tables are sent by what's near. A Master Table that's far off shows its old game (Find
  too) until it's near.
- Interactive objects on the floor plan beyond the ATM: an asset's `interact` has only the one kind, and the admin
  page's asset editor doesn't set it (the build scripts for the Modern lobby's and the Vegas floor's pieces do).
- Baccarat's 5 Treasures side bets are in the engine but not on the layout.
- Chat and emotes.
- Trusted HTTPS certificates, and a portrait phone layout.
