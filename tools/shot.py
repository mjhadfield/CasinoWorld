#!/usr/bin/env python3
"""Screenshots of the web client in headless Chromium, timed by what the server says.

    tools/shot.py [options] [STEP ...]

It opens the game, waits until you're on the floor, then runs the steps in order. With no
steps it takes one shot of the floor. The game's own WebSocket is wrapped, so a step can
wait for a real message or send one, instead of guessing coordinates and timeouts.

Steps:
    sit:TABLE[:SEAT]   sit down (first free seat by default) and wait for `seated`
    until:KIND[:TABLE] wait for a table_event of that kind (at your table once seated, else
                       any), or a message of that type: until:betting_open, until:settle_seat,
                       until:roll:crp_1, until:wallet
    send:JSON          send a message on the game's socket: send:'{"type":"bet","spot":"ante","add":500}'
    key:NAME           press a key (Playwright names: Space, Enter, KeyP, Escape ...)
    click:X,Y          click at viewport pixels
    wait:MS            let an animation finish after an `until`
    shot:NAME[@X,Y,W,H]  save .dev/shots/NAME.png, optionally clipped to that rectangle
    eval:JS            print a JavaScript expression (window.__shot holds the message log)

Example: sit at Craps, bet the Pass Line when betting opens, shoot the roll as it lands:
    tools/shot.py sit:crp_1 until:betting_open \\
        send:'{"type":"bet","spot":"pass","add":500}' send:'{"type":"ready"}' \\
        until:roll wait:1500 shot:craps_roll

By default it uses this checkout's dev instance (start it with `tools/dev.sh server`), so the
screenshot player and its bets land in .dev/data, not the live floor. The browser profile is
kept in .dev/shot-browser, so it's the same named player every run.

Keep shots small: clip to what changed, and look at one only when the step it checks has run.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / "server/.venv"

try:
    from playwright.sync_api import Error as PlaywrightError, sync_playwright
except ImportError:
    if Path(sys.prefix) != VENV and (VENV / "bin/python").exists():
        os.execv(VENV / "bin/python", [str(VENV / "bin/python"), *sys.argv])  # Playwright lives in the server's venv
    sys.exit("shot.py: needs Playwright: server/.venv/bin/pip install -r server/requirements.txt, "
             "then server/.venv/bin/python -m playwright install chromium")

NAME = "Shot"

# Wraps the page's WebSocket before Godot opens one, and logs what the server sends.
HOOK = """
(() => {
  const st = window.__shot = {socket: null, seq: 0, log: [], seated: null, tables: {}, me: null};
  const keep = 400;
  const Native = window.WebSocket;
  window.WebSocket = class extends Native {
    constructor(...args) {
      super(...args);
      if (!String(args[0]).endsWith('/ws')) return;
      st.socket = this;
      const send = this.send.bind(this);
      this.send = (data) => {  // logged as '>type', so a step never waits on our own message
        try { st.log.push({seq: ++st.seq, type: '>' + JSON.parse(data).type, table: null, kind: null, msg: data}); } catch (e) {}
        send(data);
      };
      this.addEventListener('message', (ev) => {
        if (typeof ev.data !== 'string') return;
        let m;
        try { m = JSON.parse(ev.data); } catch (e) { return; }
        const kind = m.type === 'table_event' ? m.event.kind : null;
        if (m.type === 'table_state') st.tables[m.table] = m;
        if (m.type === 'seated') st.seated = {table: m.table, seat: m.seat};
        if (m.type === 'welcome') st.me = m;
        if (kind === 'stood' && st.seated && m.table === st.seated.table && m.event.entity === (st.me || {}).entity_id) st.seated = null;
        st.log.push({seq: ++st.seq, type: m.type, table: m.table || null, kind, msg: m});
        if (st.log.length > keep) st.log.splice(0, st.log.length - keep);
      });
    }
  };
})();
"""

FIND = """([after, kind, table]) => {
  const st = window.__shot;
  if (!table && st.seated) table = st.seated.table;
  return st.log.find(e => e.seq > after && (
    (e.type === 'table_event' && e.kind === kind && (!table || e.table === table)) ||
    (e.type === kind && (!table || !e.table || e.table === table)))) || null;
}"""


def dev_url() -> str:
    port = subprocess.run([str(ROOT / "tools/dev.sh"), "port"], capture_output=True, text=True, check=True).stdout.strip()
    return f"https://localhost:{int(port) + 1}/"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", nargs="*")
    ap.add_argument("--url", help="the game's URL (default: this checkout's dev instance)")
    ap.add_argument("--size", default="1280x720", help="viewport, WxH (default 1280x720)")
    ap.add_argument("--timeout", type=float, default=60, help="seconds an `until` or `sit` may wait (default 60)")
    ap.add_argument("--out", type=Path, default=ROOT / ".dev/shots")
    args = ap.parse_args()
    url = args.url or dev_url()
    w, h = map(int, args.size.split("x"))
    args.out.mkdir(parents=True, exist_ok=True)
    ms = int(args.timeout * 1000)
    errors: list[str] = []

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(ROOT / ".dev/shot-browser"), headless=True, ignore_https_errors=True,
            viewport={"width": w, "height": h},
            args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(HOOK)
        try:
            page.goto(url)
        except PlaywrightError as e:
            sys.exit(f"shot.py: can't open {url} ({e.message.splitlines()[0]}). Is `tools/dev.sh server` running?")

        def wait_for(kind: str, table: str | None = None, after: int = 0) -> dict:
            handle = page.wait_for_function(FIND, arg=[after, kind, table], timeout=ms, polling=100)
            return handle.json_value()

        def seq() -> int:
            return page.evaluate("window.__shot.seq")

        def send(msg: dict) -> None:
            page.evaluate("(m) => window.__shot.socket.send(JSON.stringify(m))", msg)

        def on_floor() -> None:
            welcome = wait_for("welcome")["msg"]
            if welcome.get("needs_name"):
                mark = seq()
                page.wait_for_timeout(500)  # the prompt takes keys once it's drawn
                page.keyboard.type(NAME, delay=40)
                page.keyboard.press("Enter")
                wait_for("welcome", after=mark)
            wait_for("entity_spawn")
            page.wait_for_timeout(1000)  # first frames with everyone drawn
            print(f"on the floor at {url} as {NAME}")

        step, joined = "joining", None
        try:
            on_floor()
            joined = seq()
            for step in args.steps or ["shot:floor"]:
                op, _, arg = step.partition(":")
                if op == "sit":
                    table, _, seat = arg.partition(":")
                    if seat == "":
                        seats = page.evaluate("(t) => (window.__shot.tables[t] || {}).seats", table)
                        if seats is None:
                            sys.exit(f"shot.py: no table {table!r}")
                        free = [i for i, s in enumerate(seats) if s is None]
                        if not free:
                            sys.exit(f"shot.py: {table} is full")
                        seat = free[0]
                    mark = seq()
                    send({"type": "sit", "table": table, "seat": int(seat)})
                    wait_for("seated", table, mark)
                    page.wait_for_timeout(1200)  # the camera glides onto the table
                    print(f"sat at {table} seat {seat}")
                elif op == "until":
                    kind, _, table = arg.partition(":")
                    e = wait_for(kind, table or None, seq())
                    print(f"got {e['kind'] or e['type']} at {e['table'] or '-'}")
                elif op == "send":
                    send(json.loads(arg))
                    print(f"sent {arg}")
                elif op == "key":
                    page.keyboard.press(arg)
                elif op == "click":
                    x, y = map(float, arg.split(","))
                    page.mouse.click(x, y)
                elif op == "wait":
                    page.wait_for_timeout(int(arg))
                elif op == "shot":
                    name, _, clip = arg.partition("@")
                    path = args.out / f"{name or 'shot'}.png"
                    opts = {}
                    if clip:
                        x, y, cw, ch = map(float, clip.split(","))
                        opts["clip"] = {"x": x, "y": y, "width": cw, "height": ch}
                    page.screenshot(path=str(path), **opts)
                    print(f"saved {path}")
                elif op == "eval":
                    print(json.dumps(page.evaluate(arg))[:2000])
                else:
                    sys.exit(f"shot.py: unknown step {step!r} (see --help)")
        except PlaywrightError as e:
            first = e.message.splitlines()[0]
            seen = page.evaluate("""() => { const st = window.__shot, t = st.seated && st.seated.table;
                return [...new Set(st.log.filter(e => e.kind && (!t || e.table === t)).map(e => e.kind))].slice(-15); }""")
            sys.exit(f"shot.py: {step}: {first}\n  table events seen: {', '.join(seen) or 'none'}")
        finally:
            if joined is not None:
                page.wait_for_timeout(300)  # replies to a last `send`
                refused = page.evaluate("(after) => window.__shot.log.filter(e => e.seq > after && e.type === 'error').map(e => e.msg.message)", joined)
                for m in refused[-5:]:
                    print(f"server refused something: {m}")
            if errors:
                print(f"{len(errors)} browser error(s), last few:")
                print("\n".join(f"  {m[:300]}" for m in errors[-5:]))
            ctx.close()


if __name__ == "__main__":
    main()
