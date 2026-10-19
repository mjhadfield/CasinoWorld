# Casino World — living casino floor and communal Three Card Poker

> **Update (2026-10-17): Blackjack is back.** A Blackjack table (3:2, real 8-deck shoe with a cut
> card, v2's side bets) replaced the second Three Card Poker table. Shared code now lives in
> `server/casino_server/tables/base.py` (seating, betting, the clock) and, on the client,
> `scenes/table/casino_table.gd` and `table_felt.gd`, with reusable `CardShoe`, `CardShuffler` and
> `DiscardRack` fixtures. See `docs/tables.md`, `docs/games/` and `server/protocol.md` for the details.
>
> **Update (2026-10-18): admin page and NPC roster.**
> - `/admin` has tabs: Sounds (with categories), NPCs, Players and Settings.
> - NPCs are a persistent roster (`store.py` `npcs` / `npc_visits`; `roster.py` for traits, profiles and seeding).
>   The director (`npc.py`) spawns them by budget, cooldown and traits.
> - Dealers work shifts (`dealers.py`).
> - Looks are composited server-side (`art.py`, shared with `tools/build_art.py`), and the client fetches them
>   at runtime (`LookLoader`).
>
> **Update (2026-10-18): Roulette**, the first non-card game.
> - **Shape:** its own table shape (`RouTable.shape`, with a dealer's bay) and felt (`rou_felt.gd`).
> - **Wheel:** `RouletteWheel` draws the wheel and choreographs the ball from the server's events.
>   The five landing patterns and their timing are shared with `engines/roulette.py`.
> - **Results sign:** `RouletteSign` stands beside the table.
> - **Opt-in hooks in `CasinoTable`:**
>   - `accepting_bets()`: bets are taken while the ball spins
>   - `can_ready()` and `pulse_spots()`
>   - `_make_stack(seat)`: colour chips per seat (`ChipStack2D.tint`)
>   - an optional shuffler and discard rack
> - **Base machine hooks:** `BETTING_PHASES`, and `_bets_view()` (sparse bets: 157 spots).
> - **Floor:** it grew a fourth column (1800 wide).
> - **Every table:** gained Undo.
>
> **Update (2026-10-18): seating.** Free stools glow with SIT while you walk: click one (you walk over if it's far) or stand on it and press E. The old "press E, then pick a seat" step is gone.

> **Update (2026-10-17): Pai Gow.** Fortune Pai Gow and Face Up Pai Gow tables form a second row
> on an enlarged floor (since shrunk to a compact 1000×820 test room holding just the tables). Players set their hands in a floating HUD sorter
> (`scenes/ui/hand_sorter.gd`), which asks the server for House Way splits and foul checks.

## Context
Phase 1 works, but the concept doesn't match what Mike is imagining. Sitting down currently opens
a separate full-screen game UI with you alone at the table. Mike wants instead:
- **One continuous casino**, with real players and NPCs walking the floor.
- **Sitting at a table happens in the same world.** You walk to a Three Card Poker table and
  press E, the view moves onto the table, and you pick a seat. Your sprite sits there, with a
  sprite dealer opposite.
- **A real-table flow:** everyone bets, the dealer deals each seat in turn, players act in turn,
  and the dealer settles each spot. Hands are exposed at settlement, and every step is animated
  (dealing, chips placed, chips collected, chips paid).
- **Scope is narrowed to one loop:** walk the floor → sit → play rounds → stand up → walk again.
  The other games are parked, and the Blackjack spot is removed.

Mike's decisions on 2026-10-16:
- **Table view:** the camera zooms onto the real table in the world. There is no separate screen.
- **NPCs:** they wander the floor and play at tables.
- **Pace:** real-table pace with timers.
- **Art:** LPC sprites.

**What we keep:**
- the Godot web client and FastAPI server
- HTTPS on 8661
- the SQLite store, ledger and jackpot (`store.py`, `jackpot.py`)
- the ported engine `engines/three_card_poker.py` (`settle_hand`, `Bets`, `should_play`,
  `rules()`) and its v2 parity tests
- the Net/Session autoloads, plus `Money`, `ChipButton.draw_chip` and the CardView drawing code

**What gets replaced:**
- the separate table screen (`scenes/tables/three_card_poker_table.*`)
- the synchronous table class (`tables/three_card_poker.py`)
- the placeholder floor, avatar and tables

## Experience (target)
1. **Walking the floor:** the floor has two Three Card Poker tables, a bar, a cashier cage, slot
   banks and plants. Other people's avatars (real players and NPCs) walk around with name tags.
   The camera is at zoom 2 (an integer zoom, so the pixel art stays crisp). You can watch tables
   live as you pass: chips, cards and the dealer are all visible.
2. **Choosing a seat:** walk up and press E (or tap). The camera glides onto the table at zoom 3.
   Free seats pulse "Sit". Click one, or use ←/→ and E; Esc backs out. Your avatar steps to the
   chair and sits, facing the dealer.
3. **Betting** (opens after the previous round):
   - Pick a chip in the HUD tray and tap the spots *on the felt*: Pair Plus, Ante, Prime, and
     the red Jackpot light.
   - Chips fly from your seat to the spot. Everyone sees everyone's bets as they're placed.
   - Rebet, Clear and Ready buttons.
   - A 15-second countdown starts at the first bet, and it closes early once every human at the
     table is Ready. The dealer says "No more bets".
4. **Deal:** cards fly from the shoe to each seat. Three passes, starting at first base (the
   dealer's left), then the dealer's own three cards face down. Your cards turn face up for you;
   everyone else sees backs.
5. **Turns, in seat order:**
   - The active seat glows, with a 20-second ring.
   - **Play:** the Play chips fly to the Play box.
   - **Fold:** the dealer sweeps the Ante to the tray. The folded cards stay face down unless
     side bets still need resolving.
   - NPCs act after 1–3 seconds. If time runs out, you fold.
6. **Reveal and settle:**
   - The dealer flips their cards: "Dealer has Queen high — qualifies".
   - Then, from third base back to first, each seat in turn: its cards flip face up (exposed to
     everyone); losing bets slide to the tray; winning bets are paid from the tray beside the
     stake; then the whole lot slides to the player, and the balance ticks up.
   - The cards go to the discard rack. Then betting opens again.
7. **Standing up:** the Stand up button (or Esc while betting). Standing mid-hand folds, after a
   confirmation. The avatar stands beside the chair, the camera glides back to zoom 2, and you
   walk on.

## Architecture

### Server: a world of entities, plus tables driven by a timed state machine
**World and presence (`world.py`)**
- `WorldRoom` keeps every entity: `{id, kind: player|npc|dealer, name, look, x, y, dir, anim,
  seat: {table, seat}|null}`.
- Player entity ids are `p<player_id>`.
- On `join` the server sends a `world_snapshot`.
- The client sends `move {x, y, dir, anim}` at 10 Hz or less while moving, plus one on stop.
  Movement is client-authoritative, and the server relays it to the other clients.

**NPC walking.** The server sends `entity_walk {id, target, duration}`, where the target is one
of `point:<name>`, `seat:<table>:<n>` or `exit`. Each client:
- finds the path with Godot's `NavigationAgent2D`
- sets the speed to path length ÷ duration, clamped to 40–140 px/s

So everyone sees the NPC arrive at the same moment, and the server needs no floor geometry. The
named points live in `floor.py`, and each must exist as a `Marker2D` in the client map, in group
`floor_points`. A Godot check asserts they match.

**NPCs (`npc.py`, `NpcDirector`)**
- A target population of 6, configurable.
- Each NPC has a name, a look variant, and a £500–£2,000 bankroll held in memory only.
- The cycle is: arrive at the entrance → wander between points (with pauses) → sit at a table
  that still has at least 2 free seats → play 5–20 rounds → walk to the exit → despawn. A
  replacement arrives later.
- **Betting:** Antes of £5–£25. Pair Plus about 50% of the time, Prime about 20%, Jackpot about
  30%. Bets are placed 1–4 seconds into the betting window.
- **Decisions:** basic strategy, using `should_play()` (Q-6-4).

**Participants.** A seat holds a `Participant`, with two kinds:
- `HumanParticipant` uses the Session and the SQLite wallet.
- `NpcParticipant` uses its in-memory bankroll.

Both expose `name`, `entity_id`, `debit()`, `credit()` and `is_human`, so the table logic doesn't
care which kind it's dealing with.

**Table (`tables/three_card_poker.py`, rewritten)**
- **`ThreeCardPokerMachine`** is pure and synchronous, and is what the tests drive:
  - The phases are `idle → betting → dealing → turns → reveal → settling → clearing → betting…`.
  - Methods: `sit(seat, participant)`, `stand`, `set_bet(seat, spot, amount)`, `ready(seat)`
    and `decide(seat, play)`.
  - `tick(now)` handles deadlines and step pacing.
  - It emits **events**: `bet_changed`, `bets_closed`, `dealt` (the deal order, with each
    viewer's own cards), `turn {seat, seconds}`, `decision`, `dealer_reveal`, `settle_seat`,
    `round_end`, `say` (dealer lines).
  - `settle_seat` carries `{seat, cards, hand, steps: [{spot, action: collect|pay|push, amount,
    payout}], net}`.
  - Money moves at the matching event: upfront bets at `bets_closed`, the Play bet at
    `decision`, payouts at `settle_seat`.
  - `settle_hand()` from the existing engine does the maths, and `ThreeCardPokerRound` is reused
    for the deal.
- **The async driver** is one task per table, started in the Casino's lifespan and kept on
  `app.state` (see `[[project-citadel-background-services]]`). It sleeps until the machine's
  next deadline or an incoming message, calls `tick`, and broadcasts the events.
- **Timings:** a `Timings` dataclass with betting 15s, turn 20s, deal 0.18s per card, about 1.6s
  per settled seat, and a 2s clear. Tests use near-zero timings.
- **Late joiners and passers-by** get a `table_state` snapshot first, then events. Every joined
  session receives every table's events; at this scale broadcasting to everyone is fine.
- **Visibility:** a seat's own cards go only to that seat until `settle_seat`. Folded hands are
  shown only if the seat has side bets.
- **Inactivity:** a human who sits out 3 betting rounds in a row is stood up.

**Protocol v3** (documented in `server/protocol.md`)
- New: `world_snapshot`, `entity_spawn/move/walk/sit/stand/despawn`, `set_name`,
  `sit {table, seat}`, `bet {spot, amount}`, `ready`, `rebet`.
- Reworked: `decide`, `stand`.
- Table events arrive as `{type: "table_event", table, event: {...}}`.

**Casino (`casino.py`)** gains `start()` and `stop()` for the table drivers and the NPC director,
plus world registration on join and disconnect.

### Client: one world, a camera that zooms in, and an animation queue per table
**Art pipeline (`tools/build_sprites.py`)**
- Downloads specific LPC layer PNGs from the generator repo, pinned at commit `9bf06be`, into a
  cache.
- Composites `walk`, `idle` and `sit` with system Pillow, into one sheet per look under
  `client/assets/sprites/characters/`.
- **Looks:**
  - `player_default`: shirt, trousers, shoes, short hair.
  - `dealer`: white formal shirt, black vest, bow tie, formal trousers. This matches the
    reference photo; the formal shirt has no `idle` sheet, so idle uses walk frame 0.
  - About 8 NPC variants, made by recolouring hair and shirts and varying hair styles.
- Writes `client/assets/sprites/CREDITS.md` from the repo's `CREDITS.csv` rows for the files it
  used (CC-BY-SA/GPL attribution).
- **Seated players** face up (away from the camera). If a layer has no `sit` frames, they use
  idle-up, with the table rail drawn over their legs.

**Avatars**
- `scenes/world/avatar.tscn` is shared by local, remote, NPC and dealer avatars. It has an
  `AnimatedSprite2D` whose SpriteFrames are built at runtime from the look's sheet, a name tag
  (a Label using an MSDF font, so it stays crisp under zoom), and a speech bubble.
- **Drivers:** `local_player.gd` (keyboard/tap, sends `move`), `remote_avatar.gd` (interpolates
  `entity_move`) and `npc_avatar.gd` (NavigationAgent2D for `entity_walk`).
- The dealer is a static avatar at the table's Dealer marker.

**Floor (`scenes/world/casino_floor.tscn`)**
- About 1600×1100, with a carpet texture generated by the build script.
- Decor: walls, bar, cage, slot banks and plants, as StaticBody2D obstacles.
- A `NavigationRegion2D` for paths.
- `Marker2D` points in group `floor_points`: entrance, exit, bar, cage, slots_n, plants_w and so
  on.
- Two table instances, `tcp_1` and `tcp_2`.
- Y-sort, so avatars pass in front of and behind each other and the decor correctly.

**World table (`scenes/world/tcp_table.tscn` + `tcp_table.gd`, `@tool`)**
- Draws the half-moon felt and red rail from the reference photo, with "THREE CARD POKER" on the
  felt.
- Each of its 6 seats has Pair Plus, Ante, Play, Prime and a Jackpot light. The positions come
  from editable child `Marker2D`s: `Seat0..5`, `Dealer`, `Shoe`, `ChipTray`, `Discard` and
  per-seat spot anchors. Mike can move any of them in the editor.
- The felt spots are clickable `Area2D`s, which work through the camera.
- Cards (`card_2d.gd`) and chip stacks (`chip_stack_2d.gd`) are Node2Ds drawn in code. The
  existing CardView and `ChipButton.draw_chip` drawing moves into them, so they're crisp at any
  zoom.

**`TableView` (`tcp_table.gd`)**
- Applies a `table_state` snapshot instantly.
- **Event queue:** each `table_event` becomes a sequence of tweens (fly card, flip, slide chips,
  collect, pay, glow seat), played in order. If events arrive faster than they animate, they
  wait their turn. A new snapshot clears the queue and redraws.

**Camera.** `CameraDirector` on the floor tweens the Camera2D. Walking: zoom 2, following you.
Seated: zoom 3, centred on the table and nudged towards your seat.

**HUD (`scenes/ui/hud.tscn`)**
- **Walking:** balance, the jackpot meter, the sit prompt, and the top-up button when you're
  broke.
- **Seated:** adds the chip tray, Rebet/Clear/Ready, Play £X/Fold with a countdown, Stand up and
  a paytable toggle.
- The dealer's lines appear in a speech bubble above the dealer.

**Name.** On a device's first visit, a small "What should we call you?" prompt sends `set_name`,
so the name tags mean something. The name is stored on the player row.

## Milestones
Each milestone ends working and verified.
1. **Art and avatars:**
   - the sprite build script, credits file and carpet texture
   - the avatar scene with walk, idle and sit
   - the local player on the new avatar
   - MSDF fonts, and floor zoom 2
2. **Presence and NPCs on the floor:**
   - WorldRoom, the entity protocol and remote avatars
   - the floor layout with a NavigationRegion2D and named points
   - the NPC director, wandering only
   - the name prompt
3. **The table on the server:**
   - the machine, driver, participants and Timings
   - NPCs sitting and playing
   - `table_event` broadcasting
   - pytest for the full round flow: turn order, timeouts, fold/side-bet reveal, money at each
     event, ledger reconciliation, NPCs never taking the last free seats, stand mid-hand,
     disconnect, 3 sit-outs
4. **Seated in the world:**
   - the world table art and markers, and the dealer avatar
   - the camera zoom, seat picking, and sit/stand animations
   - the seated HUD
   - the animation queue for every event
   - live tables visible from the floor
   - remove the old table screen and the Blackjack spot
5. **Polish and checks:**
   - timing tuning
   - README, `docs/architecture.md`, `protocol.md` and memory
   - the end-to-end checks below

## Verification
- **pytest:**
  - the existing 58 tests, adapted; the v2 parity tests stay unchanged
  - new tests for the machine, driven by `tick(now)` with no sleeps, covering the full round
    with 1 human plus 2 NPCs
  - human timeout → fold
  - money reconciles against the ledger at every step
  - snapshot privacy (no one else's cards before settlement)
  - an NPC seating rule test, and a world presence relay test (two sessions)
- **Headless Godot E2E** (on a scratch server and scratch DB): join → walk to the table → sit in
  a chosen seat → bet → ready → play → settle → stand. Also: the floor's point names match the
  server's, and each animation queue drains.
- **Playwright with two browser contexts over HTTPS on the LAN IP** (scratch server):
  - Both players walk and see each other.
  - Both sit at `tcp_1` alongside NPCs, and each sees the other's bets placed live.
  - Hands are hidden until settlement, then exposed.
  - Screenshots at the floor, seat-pick, deal, turn and settle stages. I'll review them visually
    for layout and crispness at zoom 3.
- Never touch the live `server/data` or Mike's running server. Scratch ports are 8670/8671, with
  `CASINO_DATA_DIR` in the scratchpad.

## Out of scope for this pass
- other games, including Blackjack
- choosing a look and other customisation (the build script makes adding looks easy later)
- chat and emotes
- persistent NPC bankrolls
- trusted HTTPS certificates
- a portrait phone layout
