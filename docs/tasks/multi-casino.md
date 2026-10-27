# Multiple casinos

**Branch:** done on `task/multi-casino` (worktree `.claude/worktrees/multi-casino`), merged into `main` and live
2026-10-27. The git tag `single-casino` (8e684e5) is the code from before.
**Plan:** `~/.claude/plans/new-feature-multiple-casino-shiny-curry.md` (copied below; written 2026-10-27)

## Goal
Players choose a casino after their character. The current plan becomes "Demo", and a new hidden casino, "The
Boulevard", is seeded from blockout C.

## Files
- Server: `floor.py`, `plan.py`, `casino.py`, new `casinos.py` and `resort.py`, `npc.py`, `dealers.py`, `bank.py`,
  `sounds.py`, `table_styles.py`, `seating.py`, `store.py`, `session.py`, `app.py`, `__init__.py`, `protocol.md`, tests.
- Client: `session.gd`, `net.gd`, `front_door.gd`, `casino_floor.gd`, `sfx.gd`.
- Admin: `admin_web/plan/plan.js` and the NPCs, Players, Settings and Tables sections.
- Tools: `tools/shot.py`, `tools/dev.sh`.

## Done when
- [x] 1 `Floor` class; `plan.install` returns a Floor; `Casino(floor)`. No behaviour change. (8c8584e, on main)
- [x] 2 Casinos registry; migration to Demo; a PlanBoard per casino; `?casino=` on the plan API; qualified meta keys. (aae87dc)
- [x] 3 `Resort`: account handling moved, several Casinos, claims, shared jackpots, population per casino, protocol v7,
  `last_casino`, resume. (f871bce, with step 4)
- [x] 4 Publishing reloads only that casino. (f871bce)
- [x] 5 Client: casino chooser, session state, rebuild check, switch mode; `shot.py --casino` and `--door=casino`. (b93f2ce)
- [x] 6 Admin: casino picker and Casinos dialog; per-casino columns and settings. (dc0e7a5)
- [x] 7 The Boulevard seeded (dev first, then live); docs updated. (a3c38f7)
- [x] `tools/dev.sh test` passes (1018); live switch-over done with backups and the git tag `single-casino`.

## Handoff
- **State:** finished and live (2026-10-27). Live has Demo (the old floor, open) and The Boulevard (`boulevard`,
  hidden, no punters; walk round it at `/?casino=boulevard`).
- **Changed from the plan:** `casinos_changed` isn't a message of its own: the server resends `casinos` to everyone
  on the chooser. A new `list_casinos` gives the chooser fresh counts when it's opened from the floor. A `?casino=`
  link sends `pick_character` with `casino` (enters directly). A publish needing a slot built since start still
  restarts the server. A hidden casino's tables all have the generic Dealer (else the Boulevard's 25 tables took
  every free dealer and Demo's shifts stopped changing). The client's socket buffer is 8 MB (`Net.INBOUND_BUFFER`):
  entering the Boulevard overflowed Godot's 64 KB default.
- **Backups:** `server/data/pre-multi-casino-20261027-023501/` (sqlite `.backup` and the old `plan/`), and the
  migration's own `server/data/plan-single-casino-20261027-023519/`. Checked after the switch: every character's
  cash and bank unchanged, Demo's live plan identical, table-style placements now `demo/<table>`.
- **Left for Mike:** the Boulevard's placeholders (blockouts README step 4): slots (all Armadillo), staff looks,
  limits, floors and walls; its blurb; listing it and giving it punters (Floor plan tab › Casinos…).
- **Next task:** send each session only the tables in rooms it can see (architecture "Not done yet"): the Boulevard
  sends 133 table states on entering.
- **Questions for Mike:** none open.

---

### Context

Today the game has one floor plan (`<data>/plan/`) and one `Casino` on `app.state`. Mike wants several casinos that
players can visit:
- The current plan is saved as **"Demo"**.
- A new, larger casino starts from blockout **C · The Boulevard** (`docs/floor_blockouts/blueprints/plan_c.json`).
- After "Choose your character" comes a **"Choose your Casino"** screen.

**Mike's decisions (2026-10-27):**
- **Instancing:** each casino is its own instance in the one server process, with its own floor, tables, world and
  broadcasts. You only see and hear the people in your casino.
- **Shared:** a character's cash and bank, the shared NPC cast (roaming), and one jackpot pool.
- **NPCs:** a shared claim stops an NPC (or a dealer) from being in two casinos at once.
- **Empty casinos:** every open casino runs all the time, even with no players inside.
- **Jackpots:** one shared pool, covering the card progressive and the slot meters.

The server is mostly ready for this:
- `Casino` is self-contained.
- The client's `_build_world` already tears down and rebuilds the floor in place.

What blocks it:
- The module globals in `floor.py` (`TABLES/POINTS/SEATS/SPAWN/ROUTES`), `plan._LIVE` / `_DRAFT_TABLES` and
  `sounds.TABLE_SETS`.
- The join/account/character handling sits inside `Casino`.
- The single `PlanBoard`.
- Meta maps keyed by bare table ids (seating, table styles, `npcs.settings.avoid_table`). Table ids repeat across
  plans: every plan has its own `next` serials.

### Behaviour

**Player flow:**
1. **Character select** (unchanged). Play now leads to **Choose your Casino**.
2. **Casino cards:**
   - Each card shows the name, a one-line blurb, "N playing · M at the tables · T tables" and an Enter button.
   - The last casino this character visited is lit.
   - Back returns to the character select.
3. **Welcome:** Enter puts you at that casino's spawn. The welcome carries `casino {id, name}`.
4. **In game:** the wallet pill (on foot) opens the same screen in switch mode, showing the casino cards plus a
   "Change character" button. Leaving puts you back at the chooser.
5. **Reconnect:** a dropped connection, or a server restart, goes straight back into the same casino (`resume`
   carries it).
6. **Hidden casinos** aren't listed. `?casino=<id>` in the URL shows one anyway, so Mike can walk round the
   Boulevard while it's being built. Admin Preview works on any casino.

**Admin:**
- **Floor plan tab:** a casino picker at the start of the bar, so everything else on the tab works on the chosen
  casino. A **Casinos** dialog next to it handles:
  - new: from an empty Modern lobby, or a copy of an existing casino
  - rename, blurb, Open/Hidden, order
  - delete: only when the casino is empty and isn't the last one
- **Publishing** still refuses while there are problems. A publish that adds or removes tables now **reloads only
  that casino in-process**, not the whole server. Its players get a fresh welcome; other casinos carry on.
- **Settings:** "Punters on the floor" becomes per casino. The other NPC settings stay global.
- **Players and NPCs tabs:** each person on the floor shows which casino they're in.
- **Tables designer and Slots tab:** list tables grouped by casino.

### Design

#### Storage (`casinos.py`, new)
- **Registry:** `<data>/casinos.json`: `[{id, name, blurb, open, order, population}]`.
- **Plans:** each casino's plan is in `<data>/casinos/<id>/plan/{draft,live,history}`.
- **Startup migration:**
  - If `<data>/plan` exists and `casinos/` doesn't, back up and move it to `casinos/demo/plan`, then write the
    registry with `{id: "demo", name: "Demo", open: true}` and the current population.
  - With no data at all, seed Demo with `plan.first_plan()`.
- **Meta maps keyed by table id** are migrated once, to `demo/<id>` keys:
  - `seating.tables`
  - `table_styles*.tables`
  - every NPC's `settings.avoid_table`
  - Storage keeps the qualified keys; each casino's welcome sends its own slice unqualified, so client lookups by
    table id don't change.
- **DB:** a new `players.last_casino` column, written on enter. It picks the lit card and is the fallback for
  `resume`.

#### Floor state per casino
- `floor.py` becomes a `Floor` class holding `tables, points, seats, spawn, routes` and the current helpers
  (`arrivals`, `wander_points`, `position`, `distance`, `slots_for_humans`), plus `plan` (the old `_LIVE`) and
  `sound_sets` (the old `sounds.TABLE_SETS`).
- `plan.install(plan)` returns a `Floor` instead of writing globals.
- Every reader takes the casino's floor:
  - `npc.py` (about 15 `floor.*` uses, via `self.casino.floor`)
  - `casino.py` (`__init__` builds runners from `floor.tables`; the Master Table's `on_seats` writes into it)
  - `bank.atms(floor)`
  - `sounds.refresh_sets(floor)`
  - `table_styles.styled_tables()` and `plan.every_table()`, which now go across every casino with qualified ids
- **Sound sets:** the sounds manifest drops `tables`; the welcome carries `sound_sets`.

#### Resort and Casino (`resort.py`, new; `casino.py` slimmed)
- **`Resort`** goes on `app.state` in place of the single Casino. It owns:
  - the shared pieces, made once and passed into each Casino: `Store`, `Jackpot`, `SlotProgressives`,
    `SlotStats`, `roster.seed`
  - the `casinos` dict
  - the `PlanBoard` per casino
  - the **claims** registry (npc id → casino id)
  - every connected session, before and after it has entered a casino
- **Message routing:** the account-level handlers move from `Casino` to `Resort`: `join`, `_send_account`,
  create/edit/delete/pick/leave character, `barred`, `resync` when off any floor. Everything else goes to
  `session.casino.handle`. `Session` gains `casino`.
- **Each `Casino`** keeps its own sessions, world, runners, NPC director and dealer roster. `broadcast_all` and
  `TableRunner.publish` already go to `casino.sessions` only, so the isolation comes almost free.
- **Claims:**
  - `NpcDirector._pick_visitor` and `DealerRoster._off_duty` skip NPCs another casino has claimed.
  - A claim is taken at spawn or shift start and released at `end_visit` or relief.
  - Entity ids gain the casino prefix: `n{id}_{casino}_{serial}`.
  - The house's generic Dealer fills any gap. The Boulevard's 25 tables will lean on it until more dealers are
    made; worth telling Mike.
- **Population** is read per casino from the registry. Each casino counts its own visitors.

#### Protocol v7 (`server/protocol.md`, `__init__.py`, `net.gd`)
- **`pick_character {id}`:** the server now replies with `casinos {list: [{id, name, blurb, players, npcs,
  tables}], last}` instead of `welcome`.
- **`enter_casino {casino}`:** the server replies with `welcome` (plus `casino`), then the snapshots as today.
- **`leave_casino`:** the server sends `casino_left {reason: "leave"}` and then `casinos`.
- **`casinos_changed`:** pushed to sessions on the chooser when the registry changes.
- **`pick_character {id, resume: true, casino}`** enters directly.
- **Reload:** while a casino reloads, its sessions get `casino_left {reason: "reload"}`, then a new `welcome`.

#### Per-casino reload on publish (`plan.PlanBoard.publish`, `Resort.reload`)
- `needs_restart` now means `Resort.reload(id)`:
  1. Stop the old Casino through the same path as today's shutdown (`npcs.close_all("shutdown")`, cancel
     runners, release its claims).
  2. Install the new Floor and build and start a new Casino.
  3. Re-enter its sessions.
- `slot_builds.restart_live("plan")` is no longer called for plans.
- The hot path (positions only) stays `install` plus `broadcast_world` for that casino.

#### Client
- **`session.gd`:**
  - new state `casinos`, `pending_casino`, `casino`
  - signals `casinos_received` and `casino_left`
  - `_resume` remembers the casino
  - `?casino=` read like `?preview=`
- **`front_door.gd`:**
  - a new `"casino"` mode with a `_build_casinos` / `_fill_casinos` card row, using the same `_card_box` and
    `door_ui` helpers as the character cards
  - switch mode opens on the casino cards with "Change character"
  - the loading text "Opening the doors..." is shown while waiting for `casinos`
- **`casino_floor.gd`:**
  - The rebuild check at `:1201` also compares the casino id (`_world_casino`). Revs repeat across plans.
  - `casino_left` runs `_off_the_floor()`.
  - The wallet pill opens the casino chooser.
- **`tools/shot.py`:**
  - `--casino ID` (default `demo`) sends `enter_casino` after the pick
  - `--door=casino` stops at the chooser
- **`tools/dev.sh`:** `--classic` writes into `.dev/data/casinos/demo/plan/`.

#### Admin (`admin_web/plan/plan.js`, `shell.js`, sections)
- **Floor plan tab:**
  - `S.casino` is remembered in `cw.admin.plan.casino`.
  - The picker and the Casinos button go at the start of `#pl-bar` in `refreshBar()`.
  - Every `/api/plan*` call sends `?casino=` (the server defaults to `demo`).
  - Preview opens `/?preview=<room>&casino=<id>`.
- **New endpoints:** `GET/POST/PUT/DELETE /api/casinos`.
- **Plan asset delete:** the in-use check scans every casino's draft, live and history.
- **NPCs tab** (`_npc_view`) and **Players tab** (`online_players`) gain a casino column.
- **Settings tab:** population per casino.
- **Tables designer** (`designer.js`): tables grouped by casino, saved with qualified ids.

#### The Boulevard
- **Seeding:** a new hidden casino, id `boulevard`, named "The Boulevard" (Mike can rename it). It's seeded on the
  dev instance first, then live:
  - Demo's live `modern_lobby` and the lifts rooms, copied
  - every `plan_c.json` room, placed, with the lobby's top door turned into a 192-wide archway (`lobby_change`)
  - spawn `modern_lobby/spawn`
  - draft = live
  - `plan.problems` must stay at 0
- **Left for Mike to fill in later** (as in the blockouts README): the placeholder slots (all Armadillo), the
  stand-in staff looks, limits, floors and walls.
- **Not in this change:** sending each session only the tables in rooms it can see (architecture "Not done yet").
  The Boulevard's 25 tables and 108 slots make that the natural next task. It will be noted in the handoff.

### Order of work

Each step is a commit; `tools/dev.sh test` passes at each one.
1. `Floor` class, `plan.install` → Floor, `Casino(floor)`. No behaviour change.
2. Casinos registry, migration, PlanBoard per casino, `?casino=` on the plan API, qualified meta keys.
3. `Resort`: account handling moved, several Casinos, claims, shared jackpots, population per casino, protocol v7,
   `last_casino`, resume.
4. Per-casino reload on publish.
5. Client: the chooser, session state, the rebuild check, switch mode; `shot.py`.
6. Admin: casino picker, Casinos dialog, per-casino columns and settings.
7. Seed the Boulevard. Docs.

A handoff goes in `docs/tasks/multi-casino.md`, since this is more than one sitting.

**Docs, in the same commits:**
- `docs/architecture.md`: the Resort/Casino split, claims, storage.
- `server/protocol.md`
- `README.md`: admin, `dev.sh`, code map.
- `plan.py` docstring: the storage layout.

**Going live:**
- `tools/dev.sh hold` isn't needed, but first take a sqlite `.backup` plus a copy of `server/data/plan/` and the
  meta rows, and tag git `single-casino`.
- Until switching over, export the client to the scratchpad and run the dev instance with `CASINO_WEB_DIR`. This
  is a protocol change, so a normal `export` would break the live game.
- To go live: export, then `tools/dev.sh restart`.

### Verification

- **New `tests/test_casinos.py`:**
  - migrating a single-plan data dir to Demo, including the qualified meta keys
  - two casinos with clashing table ids (`tcp_1` in both) run side by side
  - a session in one casino gets none of the other's `table_event` / `entity_*` messages
  - an NPC and a dealer are never claimed by two casinos at once
  - pick → casinos → enter → leave → enter the other casino
  - `resume` goes back into the same casino
  - publishing table changes reloads only that casino; the other's runners keep their tasks
  - the jackpot is shared
- **Existing tests updated:** `conftest.enter()` adds `enter_casino`; the `classic_plan` fixture writes
  `casinos/demo`. `test_characters`, `test_ws`, `test_plan`, `test_table_styles` and `test_admin_people` adjusted.
  Full `tools/dev.sh test` passes.
- **Dev instance checks:**
  - `shot.py --door=casino`: one shot of the chooser
  - `shot.py --casino demo` and `--casino boulevard`: one floor shot each
  - a two-socket bot check (in Demo and the Boulevard) that neither sees the other
- **Admin (Playwright on dev):** switch casino on the Floor plan tab, create a casino, publish a table change, and
  confirm only that casino reloads.
- **After going live:** Mike's character resumes into Demo after the restart, and the Demo floor and wallet are
  unchanged.
