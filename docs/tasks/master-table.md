# Master Table

**Branch:** `main`

## Goal
A card table placed on the floor plan that starts blank (the Master Table crest, no spots). Sit down and the dealer
asks what you'd like to play; click the dealer to change. It becomes any of the nine swept-bay card games, never
Roulette or Craps. Built from the signed-off mockup: https://claude.ai/artifact/GPAjSj5NTbXaN58X5hFzMN
(`docs/master_table/mockup/`, plan `~/.claude/plans/new-table-master-deep-eich.md`).

Mike's decisions (2026-10-22):
- **Changing:** anyone seated can change the game, but only between hands. Asked mid-hand, the change waits for the
  hand to end. Other seated people get 10 s to agree; silence counts as yes. NPCs don't vote. Each NPC stays if it
  likes the new game, or gets up and leaves.
- **Seats:** Let It Ride and High Card Flush seat five. They're offered only when a seat is free, and the chairs slide
  6↔5 with their sitters.
- **The animation:** all three (Fresh cloth, Dealer's sweep, Gold dust) and the speed (0.5×, 1×, 2×) are per-table
  options on the admin page's Floor plan tab. The default is Fresh cloth at 1×.
- **Empty:** with no person seated, the table keeps its game for 60 s, then NPCs finish and leave and it goes back to
  the crest.

## Design
- **Server:**
  - `tables/master.py` `MasterMachine` holds the chosen game's own machine (`inner`) and forwards to it. It swaps the
    inner machine between hands. It owns the vote, the queued change, the "changing" hold while clients animate, and
    the revert.
  - The plan asset is `table:master_table` (ids `mt_<n>`), with `props.anim` / `props.speed`.
  - The catalogue entry carries both the 6- and 5-seat stands, and `floor.SEATS` follows the seat count.
  - Messages: `choose_game {game}`, `game_vote {accept}`.
  - Events: `master_vote`, `master_vote_end`, `master_queued`, `master_change`, `master_revert`.
  - After `master_change`, the runner sends every session a fresh `table_state`, and sessions, the world and NPCs get
    the remapped seats.
- **Client:**
  - `master_table.tscn` draws the blank table, with the crest in `master_felt.gd`.
  - A chosen game is that game's own table scene, swapped in by the floor.
  - `master_swap.gd` plays the change over the felt from printing-only paintings (`StyledFelt.layer`).
  - The dealer click opens the HUD's game menu.

## Files
- **Server:** `server/casino_server/tables/master.py`, `casino.py`, `tables/runner.py`, `plan.py`, `plan_catalogue.json`,
  `npc.py`, `sounds.py`, `table_styles.py`, `dealer_lines.toml`, `protocol.md`.
- **Admin:** `admin_web/plan/plan.js`, `admin_web/tables/render.js` and `geometry.json`.
- **Client:** `client/scenes/table/master_*`, `styled_felt.gd`, `casino_table.gd`, `scenes/world/casino_floor.gd`,
  `plan_room.gd`, the HUD, `autoload/sfx.gd`.
- **Tools:** `tools/plan_catalogue.gd`, `tools/table_geometry.gd`.

## Done when
- [ ] A Master Table placed in a scratch plan plays every game, changes between them with each animation, and votes,
      queues and reverts, checked in a browser on a dev instance
- [ ] Animation and speed can be picked per table on the Floor plan tab
- [ ] `tools/dev.sh test` passes
- [ ] Docs: `docs/games/master_table.md`, `docs/games/README.md`, `docs/tables.md`, `server/protocol.md`, README

## Handoff
- **State:** started 2026-10-22; server first.
- **Changed:**
- **Checked:**
- **Questions for Mike:**
