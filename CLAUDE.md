# Casino World

A living 2D multiplayer casino. The client is Godot 4.7 (GDScript, exported to the web) and the server is an authoritative Python FastAPI app.
- **README.md**: setup, running, the admin page, tests and art.
- **docs/architecture.md**: the design.
- **server/protocol.md**: every WebSocket message.
- **docs/slots/README.md**: the slots design record.

## Several sessions work on this at once

Read **docs/PARALLEL.md** before you change anything. In short:

- **One task, one branch, one worktree.** Your task is `docs/tasks/<id>.md`. It says which paths you own. Stay inside them. If you need a file another active task owns, or one of the shared hot spots below, stop and ask Mike.
- **In a worktree, run `tools/dev.sh setup` first.** Run your own instance with `tools/dev.sh server`, which uses its own ports from 8670 up and its own data in `.dev/data`. Use `--live-data` for a copy of the real floor.
- **Before you stop**, fill in the Handoff section of your task file, run `tools/dev.sh test`, and commit on your branch. Don't merge into `main` yourself. The coordinating session does that once Mike has reviewed the work.

## Never

- Don't touch the live server. It's the Citadel service `hub-proj-casino-world` on 8660/8661, run from the main checkout with `server/data/`.
  - Don't restart it, stop it, or point anything at its ports.
  - Don't read or write `server/data/` directly.
  - Only the coordinating session restarts it, and only after Mike says so.
- Don't write sample data, or reset anything, in the live data. Tests already use a scratch database (`server/tests/conftest.py`).
- No `Co-Authored-By: Claude` trailers on commits or PRs.

## Shared hot spots (one task at a time)

These files are touched by nearly every feature, so only the task that claims them in its file may change them:

- **The protocol:** `server/protocol.md`, `server/casino_server/__init__.py` (`PROTOCOL_VERSION`) and `client/autoload/net.gd` (`PROTOCOL_VERSION`). Bump both versions together.
- **The floor:** `server/casino_server/floor.py` and `client/scenes/world/casino_floor.tscn`. `.tscn` files merge badly.
- **The database schema:** `server/casino_server/store.py`.
- **App wiring:** `server/casino_server/app.py`.

## Checking your work

- **Server:** run `tools/dev.sh test`.
- **Client:** run `tools/dev.sh export`, then open your instance in a browser (UI changes need a real browser, not curl). The table layout audit is in README › Layout.
- **The desktop or editor client:** set `CASINO_SERVER_URL=ws://127.0.0.1:<your port>/ws`. Get the port from `tools/dev.sh port`.
