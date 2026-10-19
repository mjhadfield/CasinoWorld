# Casino World

Mike's living 2D multiplayer casino. It's a hobby project worked on part time, usually one thing at a time. The client is Godot 4.7 (GDScript, exported to the web) and the server is an authoritative Python FastAPI app.
- **README.md**: setup, running, the admin page, tests and art.
- **docs/architecture.md**: the design.
- **server/protocol.md**: every WebSocket message.
- **docs/slots/README.md**: the slots design record.

## The running server

The live server is Citadel's unit `hub-proj-casino-world` on 8660 (HTTP) and 8661 (HTTPS). It runs from this folder with `server/data/`.

- **Server changes:** restart it with `tools/dev.sh restart` when they need it. No need to ask first; the worst case is interrupting a hand Mike's playing.
- **Client changes:** `tools/dev.sh export`, then reload the page. No restart is needed.
- **Long checks against the live server:** if a check needs the server to stay up (a browser walkthrough, a timed round), run `tools/dev.sh hold "what you're testing"` first and `tools/dev.sh release` after. `restart` won't restart a held server, so another session can't pull it out from under you. If `restart` says it's held, wait or ask.

## Checking work

- **Server:** `tools/dev.sh test`. The tests use a scratch database.
- **Client:** layout or UI changes need a look in a real browser, not curl. The table layout audit is in README › Layout.

## Git

- Work on `main`. Commit each finished, working change with a plain message saying what changed and why. There's no remote, so nothing to push.
- If a session stops partway through something, commit what's there or say what's uncommitted.
- No `Co-Authored-By: Claude` trailers.

## Two things at once

Occasionally Mike runs two or three sessions side by side. A session started in a git worktree is one of those, so follow **docs/PARALLEL.md**: its own branch, its own dev instance, and leave the files the other session is working on alone.
