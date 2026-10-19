# Two or three things at once

Most of the time, one session works in the main folder on `main`. When you want two or three changes going side by side, give each extra session its own git worktree, so they can't overwrite each other.

## Starting one

- **Pick pieces that touch different files.** Server rules, a client scene, and art or sounds usually split cleanly. Some files nearly every feature touches, so don't run two sessions on them at once:
  - the protocol (`server/protocol.md` and both `PROTOCOL_VERSION`s)
  - `client/scenes/world/casino_floor.tscn`, because `.tscn` files merge badly
  - `server/casino_server/store.py`, the database schema
- **Start the session in a worktree.** In the desktop app, start the new session with a worktree. From a terminal:

  ```bash
  git worktree add .claude/worktrees/<id> -b task/<id>
  ```

- **Run `tools/dev.sh setup` in the worktree.** Its own instance is `tools/dev.sh server`, on its own ports from 8670 up with its own `.dev/data`. Add `--live-data` to start from a copy of the real floor. `tools/dev.sh port` prints the port, and `tools/dev.sh list` shows every checkout's.
- **Client changes:** a worktree serves the main client until you run `tools/dev.sh export` there.

## If it will take more than one sitting

Copy `docs/tasks/_template.md` to `docs/tasks/<id>.md` and keep its Handoff section current. Then a fresh session, on either account, can pick it up from "continue docs/tasks/<id>.md" without being re-told everything.

## Finishing

1. Commit on the task branch.
2. Merge from the main folder, then run the tests:

   ```bash
   git merge task/<id>
   ```

3. Restart and export as usual (`tools/dev.sh restart`, `tools/dev.sh export`).
4. Tidy up:

   ```bash
   git worktree remove .claude/worktrees/<id> && git branch -d task/<id>
   ```
