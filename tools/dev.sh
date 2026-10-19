#!/usr/bin/env bash
# Runs a Casino World dev instance for this checkout (normally a git worktree), isolated
# from the live server: its own port pair and its own data folder. See docs/PARALLEL.md.
#
#   tools/dev.sh setup                 link the main checkout's .venv and lpc_cache in here
#   tools/dev.sh port                  print this checkout's HTTP port (HTTPS is port + 1)
#   tools/dev.sh server [--live-data]  run the server (foreground; log in .dev/server.log)
#   tools/dev.sh export                export the web client into this checkout's build/web
#   tools/dev.sh test [pytest args]    run the server tests
#   tools/dev.sh list                  every checkout's port, and whether it is running
#
# The live server is the Citadel service on 8660/8661, run from the main checkout with
# server/data/. This script never uses either: dev ports start at 8670, and the data
# folder is .dev/data. --live-data copies the live data in once (a copy, never a link);
# delete .dev/data to start over.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
MAIN=$(cd "$(git rev-parse --path-format=absolute --git-common-dir)/.." && pwd)
DEV="$ROOT/.dev"
LIVE_PORT=8660
FIRST_PORT=8670
LAST_PORT=8698

die() { echo "dev.sh: $*" >&2; exit 1; }

listening() { ss -ltnH "sport = :$1" | grep -q .; }

setup() {
    mkdir -p "$DEV"
    [[ "$ROOT" == "$MAIN" ]] && return
    local name
    for name in .venv lpc_cache; do
        if [[ ! -e "$ROOT/server/$name" ]]; then
            [[ -e "$MAIN/server/$name" ]] || die "the main checkout has no server/$name (see README Setup)"
            ln -s "$MAIN/server/$name" "$ROOT/server/$name"
        fi
    done
}

# Ports other checkouts have claimed, one per line.
claimed() {
    git worktree list --porcelain | sed -n 's/^worktree //p' | while read -r wt; do
        if [[ "$wt" != "$ROOT" && -f "$wt/.dev/port" ]]; then cat "$wt/.dev/port"; fi
    done
}

port() {
    if [[ -f "$DEV/port" ]]; then
        cat "$DEV/port"
        return
    fi
    mkdir -p "$DEV"
    local taken p
    taken=$(claimed)
    for ((p = FIRST_PORT; p <= LAST_PORT; p += 2)); do
        grep -qx "$p" <<<"$taken" && continue
        listening "$p" || listening $((p + 1)) || { echo "$p" >"$DEV/port"; echo "$p"; return; }
    done
    die "no free port pair in $FIRST_PORT-$((LAST_PORT + 1))"
}

copy_live_data() {
    local live="$MAIN/server/data" data="$DEV/data"
    [[ -f "$data/casino.sqlite" ]] && { echo "dev.sh: .dev/data already exists; keeping it"; return; }
    [[ -f "$live/casino.sqlite" ]] || die "no live data at $live"
    mkdir -p "$data"
    # .backup takes a consistent snapshot even while the live server is writing.
    sqlite3 "$live/casino.sqlite" ".backup '$data/casino.sqlite'"
    local item
    for item in "$live"/*; do
        case $(basename "$item") in
            casino.sqlite*|tls) ;;
            *) cp -r "$item" "$data/" ;;
        esac
    done
    echo "dev.sh: copied the live data into .dev/data"
}

server() {
    setup
    [[ "${1:-}" == "--live-data" ]] && copy_live_data
    local p web
    p=$(port)
    [[ "$p" == "$LIVE_PORT" ]] && die "refusing to use the live port"
    listening "$p" && die "port $p is already in use (another dev.sh server here?)"
    web="$ROOT/build/web"
    if [[ ! -f "$web/index.html" ]]; then
        web="$MAIN/build/web"
        echo "dev.sh: no build/web here, so serving the main checkout's client; run 'tools/dev.sh export' to test client changes"
    fi
    mkdir -p "$DEV/data"
    echo "dev.sh: http://127.0.0.1:$p (editor/desktop: CASINO_SERVER_URL=ws://127.0.0.1:$p/ws)"
    echo "dev.sh: https://localhost:$((p + 1)) (browser)  admin: http://127.0.0.1:$p/admin"
    cd "$ROOT/server"
    CASINO_PORT=$p CASINO_DATA_DIR="$DEV/data" CASINO_WEB_DIR="$web" \
        .venv/bin/python -m casino_server 2>&1 | tee "$DEV/server.log"
}

export_web() {
    mkdir -p "$ROOT/build/web"
    cd "$ROOT/client"
    godot --headless --export-release Web ../build/web/index.html
}

run_tests() {
    setup
    cd "$ROOT/server"
    exec .venv/bin/python -m pytest -q "$@"
}

list() {
    printf '%-6s %-8s %-28s %s\n' PORT STATE BRANCH CHECKOUT
    local wt="" branch="" p state
    while read -r key value; do
        case $key in
            worktree) wt=$value ;;
            branch) branch=${value#refs/heads/} ;;
            "")
                [[ -z "$wt" ]] && continue
                p=$( [[ -f "$wt/.dev/port" ]] && cat "$wt/.dev/port" || echo - )
                [[ "$wt" == "$MAIN" ]] && p="$LIVE_PORT*"
                state=-
                [[ "$p" != - ]] && { listening "${p%\*}" && state=running || state=stopped; }
                printf '%-6s %-8s %-28s %s\n' "$p" "$state" "$branch" "$wt"
                wt="" branch="" ;;
        esac
    done < <(git worktree list --porcelain; echo)
    echo "(* the main checkout: the live server, run by Citadel)"
}

case "${1:-}" in
    setup) setup ;;
    port) port ;;
    server) shift; server "$@" ;;
    export) export_web ;;
    test) shift; run_tests "$@" ;;
    list) list ;;
    *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
