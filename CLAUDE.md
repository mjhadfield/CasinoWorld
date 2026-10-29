# Casino World

Mike's living 2D multiplayer casino. The client is Godot 4.7 (GDScript, exported to the web) and the server is an authoritative Python FastAPI app.
- **docs/development.md**: setup, running, the admin page, tests, screenshots and a code map.
- **README.md** is the public overview on GitHub, written in Mike's voice. Keep working notes out of it.
- **docs/games/**: how each game plays, one file per game. Read the one you're working on, not all of them.
- **docs/architecture.md**: the design.
- **server/protocol.md**: every WebSocket message.
- **docs/tables.md**: building a table, the layout rules and the layout audit.
- **docs/slots/README.md**: the slots design record. **docs/slots/scenes.md**: designing a slot's scene, when Mike says
  "design the X scene" (his brief is on the Scene step).

## The running server

The live server is Citadel's unit `hub-proj-casino-world` on 8660 (HTTP) and 8661 (HTTPS). It runs from this folder with `server/data/`.

- **Server changes:** restart it with `tools/dev.sh restart` when they need it. No need to ask first; a hand Mike's playing is void and the stake on it comes back.
- **Client changes:** `tools/dev.sh export`, then reload the page. No restart is needed.
- **Browser checks** run against a dev instance (`tools/dev.sh server`, in the background), which is what `tools/shot.py` uses by default. It serves this checkout's export and keeps its data in `.dev/data`, so the live floor and Mike's wallet are untouched.
- **If a check must use the live server** and needs it to stay up, run `tools/dev.sh hold "what you're testing"` first and `tools/dev.sh release` after. `restart` won't restart a held server. If `restart` says it's held, wait or ask.

## Checking work

Match the check to the change, and stop once it passes.

- **While working:** run the tests for what you're changing (`tools/dev.sh test tests/test_craps.py`, or `-k name`), not the whole suite.
- **Before committing a server change:** `tools/dev.sh test` (about 35s). Add `--all` only after changing the slots maths; it adds a 2-minute simulation.
- **Client layout:** the layout audit (docs/tables.md) first. It's headless and gives numbers.
- **Client visuals:** take one `tools/shot.py` screenshot of the result, clipped to what changed (`shot:name@x,y,w,h`), timed with `until:` on the event you're checking rather than `wait:`. Don't loop on screenshots for small tweaks: if a shot doesn't settle it, say what to look at and ask Mike, who usually has the game open.
- **Server logic** the tests cover doesn't need a browser at all.

## Keeping the docs current

The docs drifted badly once (the README missed two games, architecture.md was still the first plan), so they're part of finishing a change, not a separate job. Before committing, update whichever of these the change touches, in the same commit:

| If you changed | Update |
|---|---|
| A game's rules, bets, payouts, timings or NPC play | its file in `docs/games/` |
| A new game or table | a new `docs/games/<game>.md`, the table in `docs/games/README.md`, the floor rows there, and the code map in `docs/development.md` |
| A WebSocket message or event | `server/protocol.md` |
| How a table is drawn, a shared table piece, the layout rules | `docs/tables.md` |
| Something structural (a new module, autoload or background task, how state or money flows) | `docs/architecture.md`, and its "Not done yet" list when something on it lands |
| Setup, `tools/dev.sh`, env vars, the admin page, tests, art scripts, or where code lives | `docs/development.md` |
| How sessions should work | this file |

Write each doc as how things are now: rewrite the section in place rather than adding a dated "Update" note on top, and delete what's no longer true. Git keeps the history. If you notice something stale in passing, fix it or mention it to Mike.

## Git

- Work on `main`. Commit each finished, working change with a plain message saying what changed and why. The GitHub remote is public: push only when Mike asks.
- If a session stops partway through something, commit what's there or say what's uncommitted.
- No `Co-Authored-By: Claude` trailers.

## Session length

Every turn re-reads the whole conversation, so a long session costs far more per step than a fresh one. Once a feature is committed, suggest starting a fresh session for the next one. For anything that won't finish in one sitting, keep a `docs/tasks/<id>.md` handoff (docs/PARALLEL.md) so a new session can pick it up.

## Two things at once

Occasionally Mike runs two or three sessions side by side. A session started in a git worktree is one of those, so follow **docs/PARALLEL.md**: its own branch, its own dev instance, and leave the files the other session is working on alone.
