# Working in parallel

Several Claude sessions build Casino World at once. One coordinates; the rest work, each on its own task. The context they share lives in this repo, not in any conversation. If a session dies, hits a usage limit, or runs on the other account, a fresh one carries on from the files.

## The roles

- **Mike** decides what to build, answers the workers' questions, reviews diffs, and says when to merge and restart the live server.
- **The coordinating session** runs in the main checkout (`~/Projects/CasinoWorld`, on `main`). It:
  - turns a feature into tasks and writes the task files
  - starts one worker per task
  - reviews what comes back
  - merges into `main`, re-exports the web client, and restarts the live server when Mike says so
- **The workers** each run in their own git worktree on branch `task/<id>`. A worker:
  - changes only the paths its task owns
  - runs its own dev instance
  - commits on its branch and writes a handoff

## Starting a feature

1. Tell the coordinating session what you want.
2. It splits the feature into tasks whose **Owns** lists don't overlap. Usually that's by area: server rules, client scene, admin, art or sounds. Where two pieces both need a shared hot spot (CLAUDE.md), they run one after the other, not side by side.
3. It writes `docs/tasks/<id>.md` for each task, sets them `active`, and commits on `main`. Worktrees start from `main`, so every worker sees every task file.
4. It starts one session per task, each in a new worktree. In the Claude desktop app, a session started from the coordinating session in a worktree shows in the sidebar and reports back when it finishes a turn.

   Doing it by hand from a terminal instead:

   ```bash
   git worktree add .claude/worktrees/<id> -b task/<id>
   cd .claude/worktrees/<id> && tools/dev.sh setup && claude
   ```

## While workers run

- Each worker runs `tools/dev.sh server` in the background on its own port pair, from 8670 up. `tools/dev.sh list` shows every checkout's port and whether it's running.
- To try one yourself, use `https://<LAN IP>:<port + 1>`. Its admin page is `/admin` on the same instance.
- A blocked worker asks you in its own session, or messages the coordinating session.

## Finishing a task

1. The worker fills in **Handoff**, runs the tests, commits, and sets its status to `review` in its own task file.
2. The coordinating session reads the handoff and the diff (`git diff main...task/<id>`) and tells you what changed and how it was checked.
3. Once you've approved, the coordinating session:
   1. runs `git merge --no-ff task/<id>` on `main`, then the tests again
   2. sets the task to `merged`
   3. removes the worktree: `git worktree remove .claude/worktrees/<id>`, then `git branch -d task/<id>`
4. **Going live:** when the client changed, the coordinating session runs `tools/dev.sh export` in the main checkout. Then, on your word, it restarts `hub-proj-casino-world` (or you restart it from Citadel).

Merging puts the new code on disk under the live server straight away. It only runs the new code after a restart. One exception: `dealer_lines.toml` reloads without a restart.

## Notes

- **Two accounts.** Transcripts and memory are stored locally in `~/.claude`, and the task files are in git, so switching accounts loses nothing. A worker that runs out of usage can be resumed, or replaced by a fresh session told "continue `docs/tasks/<id>.md`".
- **Worktree caches.** A worktree has no `.venv` or `lpc_cache` of its own; `tools/dev.sh setup` links the main checkout's.
- **The client in a worktree.** It has no `build/web` until `tools/dev.sh export`, so its server serves the main client until then. The first export imports every asset into `client/.godot/`, which takes a minute.
- **Live data.** `--live-data` copies `server/data/` into `.dev/data` once, with a consistent SQLite snapshot. Delete `.dev/data` to start over.
- **Not in git:** `server/data/` (live), `server/lpc_cache/` (a download cache), `build/`, and `docs/slots/flux_raw/` (the raw FLUX outputs, kept in the main checkout only).
