# Tasks

Each piece of parallel work has one file here, copied from `_template.md`. See `docs/PARALLEL.md` for how they're used.

- **Who writes what.** The coordinating session creates each file and changes its `status:`, on `main`. A worker writes only its own file's Handoff section, on its branch.
- **The board** is the `status:` lines:

  ```bash
  grep -H '^status:' docs/tasks/[!_]*.md
  ```

- **Retiring a file.** Once a task is `merged` or `dropped`, its file stays as the record. Move it to `done/` when this folder gets crowded.
