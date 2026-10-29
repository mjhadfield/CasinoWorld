"""
FastAPI app: serves the Godot web export from build/web, runs the /ws socket,
and serves the admin page (/admin, admin_web/) and its APIs.

The Resort (resort.py) holds the casinos (casino.py: each one's tables, floor and
NPCs), the store and the jackpots, and lives on app.state for the app's lifespan.
Each socket gets a Session; handlers push
messages onto session queues and a per-connection sender task delivers them.
The client never decides a hand -- it sends intents and renders what this sends.

Message shape both ways: a JSON object with a "type" field. See protocol.md.
"""

import asyncio
import contextlib
import mimetypes
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from casino_server.art import LookCache
from casino_server.resort import Resort
from casino_server.session import Session
from casino_server import bank, casinos, heat, plan, plan_assets, slot_builds, slot_design_art
from casino_server.slot_art import SlotArtBoard
from casino_server.slot_design import DEFAULT_DESIGNS_DIR, DesignBoard, DesignError
from casino_server.slots import jackpots as slot_jackpots
from casino_server.slots import stats as slot_stats
from casino_server.slots.variants import VARIANTS as SLOT_VARIANTS
from casino_server.sounds import SoundBoard, SoundError
from casino_server.store import Store

# Godot's web export ships .wasm and .pck files -- make sure they're served with
# the types browsers expect (WebAssembly streaming compile requires application/wasm).
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/octet-stream", ".pck")

# CASINO_WEB_DIR serves another export (a scratch build under test, leaving the live one alone).
WEB_EXPORT_DIR = Path(os.environ.get("CASINO_WEB_DIR") or Path(__file__).resolve().parents[2] / "build" / "web")
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

NOT_EXPORTED_PAGE = """<!doctype html><meta charset="utf-8"><title>Casino World</title>
<body style="font-family:sans-serif;background:#111;color:#eee;padding:2rem">
<h1>Casino World server is running</h1>
<p>No web export found yet. In Godot: <b>Project &rsaquo; Export &rsaquo; Web &rsaquo; Export Project</b>
(the preset already points at <code>build/web/index.html</code>), then reload this page.
Installing the export templates alone isn't enough -- the export step writes the files.</p></body>"""



def _build_roster_looks(store: Store, looks: LookCache):
    for npc in store.npcs():
        try:
            looks.ensure(npc["look"])
        except Exception as e:
            print(f"couldn't build {npc['name']}'s look: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_dir = Path(os.environ.get("CASINO_DATA_DIR", DEFAULT_DATA_DIR))
    # Slots built with the Slot design wizard load first (CASINO_SLOT_BUILDS_DIR moves them, for tests and the dev
    # instance), then the floor plan puts its tables and cabinets on the floor, so the casino, the sound board and
    # the art board all see them.
    builds_dir = Path(os.environ.get("CASINO_SLOT_BUILDS_DIR") or slot_builds.DEFAULT_DIR)
    built = slot_builds.install(builds_dir)
    if built:
        print("built slots: " + ", ".join(built))
    library = plan_assets.AssetLibrary(data_dir)   # (first: the plan's checks know the furniture)
    store = Store(data_dir / "casino.sqlite")
    for p in store.players():
        if p["stored_as"] != "integer":
            print(f"WARNING: {p['name']}'s balance is {p['balance']!r}, which isn't a number of pence; "
                  f"they'll be disconnected when they bet. Fix it with: "
                  f".venv/bin/python -m casino_server.admin set-balance {p['id']} <pounds>")
    # CASINO_SPEED < 1 speeds every table timer and NPC up (handy for demos/tests);
    # CASINO_NPCS sets how many NPCs roam each floor (unset: each casino's population, on the admin page).
    speed = float(os.environ.get("CASINO_SPEED", "1"))
    npcs = os.environ.get("CASINO_NPCS")
    looks = LookCache(data_dir)
    resort = Resort(store, data_dir, builds_dir, speed=speed, npc_population=int(npcs) if npcs else None,
                    npc_pace=speed, looks=looks)
    app.state.resort = resort
    app.state.boards = resort.boards
    app.state.sounds = SoundBoard(data_dir)
    app.state.slot_art = SlotArtBoard(data_dir)
    app.state.plan_assets = library
    # CASINO_DESIGNS_DIR points the Slot design board elsewhere (tests and the dev instance use a copy).
    app.state.slot_design = DesignBoard(Path(os.environ.get("CASINO_DESIGNS_DIR") or DEFAULT_DESIGNS_DIR))
    app.state.slot_design.sounds = app.state.sounds
    app.state.slot_design.builds_dir = builds_dir
    app.state.slot_design.cabinets_on_floor = lambda variant: sum(c.floor.cabinets(variant) for c in resort.casinos.values())
    design_worker = asyncio.create_task(app.state.slot_design.run())
    app.state.looks = looks
    await asyncio.to_thread(_build_roster_looks, store, looks)   # so nobody waits for a sheet on the floor
    await resort.start()
    try:
        yield
    finally:
        design_worker.cancel()
        await resort.stop()
        store.close()


app = FastAPI(title="Casino World", lifespan=lifespan)


async def _sender(ws: WebSocket, session: Session):
    """Sends the session's messages until it's cut off (None: see Session.push) or the socket fails, then closes the
    socket, so the receive loop ends too and the client reconnects."""
    try:
        while (msg := await session.queue.get()) is not None:
            await ws.send_json(msg)
    except Exception:  # noqa: BLE001 -- whatever stopped it, the socket is no use now
        pass
    with contextlib.suppress(Exception):
        await ws.close(code=1013)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    resort: Resort = ws.app.state.resort
    session = Session()
    sender = asyncio.create_task(_sender(ws, session))
    resort.connect(session)
    try:
        while True:
            try:
                msg = await ws.receive_json()
            except ValueError:
                session.error("Expected a JSON object")
                continue
            if not isinstance(msg, dict):
                session.error("Expected a JSON object")
                continue
            resort.handle(session, msg)
    except WebSocketDisconnect:
        pass
    finally:
        resort.disconnect(session)
        sender.cancel()


# Checked per request, so a fresh Godot export is picked up without restarting the server.
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # Godot's web build won't start over plain HTTP except on localhost, so send other
    # browsers to the HTTPS port (set by __main__ when it has a certificate).
    https_port = getattr(app.state, "https_port", None)
    host = request.url.hostname or ""
    if request.url.scheme == "http" and https_port and host not in LOCAL_HOSTS:
        return RedirectResponse(f"https://{host}:{https_port}/")
    index_html = WEB_EXPORT_DIR / "index.html"
    if index_html.exists():
        return FileResponse(index_html, headers={"Cache-Control": "no-cache"})
    return NOT_EXPORTED_PAGE


# The engine (a 40 MB wasm, the pck, its loader) as the brotli or gzip copy tools/dev.sh export
# makes, when the browser takes it and the copy isn't older than the file (an export that's still
# compressing serves the plain one). Always revalidated (no-cache), so a reload costs a 304.
ENGINE_FILES = {"index.wasm": "application/wasm", "index.pck": "application/octet-stream",
                "index.js": "text/javascript"}


def _engine_file(name: str, request: Request):
    path = WEB_EXPORT_DIR / name
    if not path.is_file():
        raise HTTPException(404)
    headers = {"Cache-Control": "no-cache", "Vary": "Accept-Encoding"}
    accepts = request.headers.get("accept-encoding", "")
    for encoding, ext in (("br", ".br"), ("gzip", ".gz")):
        packed = path.with_name(name + ext)
        if encoding in accepts and packed.is_file() and packed.stat().st_mtime >= path.stat().st_mtime:
            path, headers["Content-Encoding"] = packed, encoding
            break
    response = FileResponse(path, media_type=ENGINE_FILES[name], headers=headers, stat_result=path.stat())
    etag = response.headers.get("etag")
    if etag and etag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers={"ETag": etag, **headers})
    return response


def _engine_route(name: str):
    def serve(request: Request):
        return _engine_file(name, request)
    return serve


for _name in ENGINE_FILES:
    app.add_api_route(f"/{_name}", _engine_route(_name), methods=["GET", "HEAD"], include_in_schema=False)


# ------------------------------------------------------------------ sounds
# The admin page picks the sound for each game moment; games fetch the
# manifest at start and again whenever they're sent "sounds_changed".
NO_STORE = {"Cache-Control": "no-store"}


def _sounds_changed(request: Request):
    board: SoundBoard = request.app.state.sounds
    request.app.state.resort.broadcast_all({"type": "sounds_changed", "version": board.version})


def _sound_call(fn, *args):
    try:
        return fn(*args)
    except SoundError as e:
        raise HTTPException(400, str(e))


# The admin page (admin_web/) and its scripts, never cached, so an edit shows on reload.
# design/slots_math.js is the signed-off slot maths, served from its home in docs/slots/mockup (the one source for both).
ADMIN_WEB = Path(__file__).resolve().parent / "admin_web"
SLOTS_MATH = Path(__file__).resolve().parents[2] / "docs" / "slots" / "mockup" / "slots_math.js"


@app.get("/admin", response_class=HTMLResponse)
@app.get("/maintenance", response_class=HTMLResponse)
def admin_page():
    return FileResponse(ADMIN_WEB / "index.html", headers=NO_STORE)


@app.get("/admin/next")
def admin_next_page():
    return RedirectResponse("/admin")   # where the new page was reviewed


@app.get("/admin-ui/{rel:path}")
def admin_ui(rel: str):
    if rel == "design/slots_math.js":
        return FileResponse(SLOTS_MATH, media_type="text/javascript", headers=NO_STORE)
    path = (ADMIN_WEB / rel).resolve()
    if not path.is_relative_to(ADMIN_WEB) or not path.is_file():
        raise HTTPException(404, "No such file")
    return FileResponse(path, headers=NO_STORE)


@app.get("/api/sounds")
def sounds_overview(request: Request):
    return JSONResponse(request.app.state.sounds.overview(), headers=NO_STORE)


@app.get("/api/sounds/manifest")
def sounds_manifest(request: Request):
    return JSONResponse(request.app.state.sounds.manifest(), headers=NO_STORE)


async def _json_body(request: Request, shape: str) -> dict:
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise HTTPException(400, f"Expected JSON: {shape}")
    return body


@app.put("/api/sounds/{set_key}/{key}")
async def sounds_set(set_key: str, key: str, request: Request):
    """Give a moment its own sounds in a set."""
    body = await _json_body(request, "{files: [...], gain_db: 0}")
    row = _sound_call(request.app.state.sounds.set_choice, set_key, key, body.get("files"), body.get("gain_db", 0))
    _sounds_changed(request)
    return row


@app.post("/api/sounds/{set_key}/{key}/inherit")
def sounds_inherit(set_key: str, key: str, request: Request):
    """Play the set above's sounds for this moment."""
    row = _sound_call(request.app.state.sounds.inherit, set_key, key)
    _sounds_changed(request)
    return row


@app.delete("/api/sounds/{set_key}/{key}")
def sounds_reset_one(set_key: str, key: str, request: Request):
    """Put one moment in one set back to how it came."""
    board: SoundBoard = request.app.state.sounds
    _sound_call(board.reset, set_key, key)
    _sounds_changed(request)
    return board.row(set_key, key)


@app.post("/api/sounds-reset")
async def sounds_reset(request: Request):
    """Back to how it came: `{set}` for one set, `{}` for everything."""
    body = await _json_body(request, "{set: key} or {}") if await request.body() else {}
    _sound_call(request.app.state.sounds.reset, body.get("set"))
    _sounds_changed(request)
    return {"ok": True}


@app.post("/api/sounds/{set_key}/inherit-all")
def sounds_inherit_all(set_key: str, request: Request):
    """A machine (or preset) plays the set above's sounds for every moment: its preset, untweaked."""
    _sound_call(request.app.state.sounds.inherit_all, set_key)
    _sounds_changed(request)
    return {"ok": True}


@app.post("/api/sound-presets")
async def sound_presets_create(request: Request):
    """A new slot preset: `{name}`, or `{name, from}` to start from a preset (a copy) or a machine (its sounds move in)."""
    body = await _json_body(request, "{name, from?}")
    key = _sound_call(request.app.state.sounds.create_preset, body.get("name"), body.get("from"))
    _sounds_changed(request)
    return {"key": key}


@app.patch("/api/sound-presets/{key}")
async def sound_presets_rename(key: str, request: Request):
    body = await _json_body(request, "{name}")
    _sound_call(request.app.state.sounds.rename_preset, key, body.get("name"))
    return {"ok": True}


@app.delete("/api/sound-presets/{key}")
def sound_presets_delete(key: str, request: Request):
    """Remove a preset; the machines on it go back to Default."""
    moved = _sound_call(request.app.state.sounds.delete_preset, key)
    _sounds_changed(request)
    return {"moved": moved}


@app.put("/api/sound-machines/{machine}")
async def sound_machine_preset(machine: str, request: Request):
    """Which preset a slot machine follows: `{preset}` ("slots" for Default)."""
    body = await _json_body(request, "{preset}")
    _sound_call(request.app.state.sounds.set_machine_preset, machine, body.get("preset"))
    _sounds_changed(request)
    return {"ok": True}


@app.put("/api/sound-uploads/{filename}")
async def sounds_upload(filename: str, request: Request):
    data = await request.body()
    return _sound_call(request.app.state.sounds.upload, filename, data)


@app.delete("/api/sound-uploads/{filename}")
def sounds_delete_upload(filename: str, request: Request):
    _sound_call(request.app.state.sounds.delete_upload, "uploads/" + filename)
    return {"ok": True}


@app.get("/sound-files/{sound_id:path}")
def sound_file(sound_id: str, request: Request):
    path = request.app.state.sounds.file_path(sound_id)
    if path is None:
        raise HTTPException(404, "No such sound")
    # The game asks with ?v=<file's change time>, so those can be cached for good; the page asks without.
    cache = "public, max-age=31536000, immutable" if "v" in request.query_params else "no-cache"
    return FileResponse(path, headers={"Cache-Control": cache})




# ------------------------------------------------------------------ slots (the admin page's Slots tab)
@app.get("/api/slots")
def slots_overview(request: Request):
    """The shared meters, each cabinet (who's on it, what it's doing) and what slots have returned."""
    resort = request.app.state.resort
    cabinets = []
    for table_id, runner in ((t, r) for c in resort.casinos.values() for t, r in c.tables.items()):
        m = runner.machine
        if m.game != "slots":
            continue
        p = m.seats[0].participant
        cabinets.append({"table": table_id, "casino": runner.casino.id, "variant": m.variant.id, "name": m.variant.name, "phase": m.phase,
                         "player": p.name if p else None, "human": bool(p and p.is_human), "bet": m.bet,
                         "pending": [f[0] for f in m.pending]})
    wagered = returned = 0
    for player in resort.store.player_stats():
        g = player["games"].get("slots")
        if g:
            wagered, returned = wagered + g["wagered"], returned + g["returned"]
    pg = resort.slot_jackpots
    tiers = [{**t, **pg.settings[t["id"]], "amount": pg.amount(t["id"])} for t in slot_jackpots.TIERS]
    return JSONResponse({"tiers": tiers, "cabinets": cabinets, "players": {"wagered": wagered, "returned": returned},
                         "jackpot_rtp": 100 * pg.rtp(), "machines": _slot_machines(resort, cabinets),
                         "casinos": {c["id"]: c["name"] for c in resort.registry},
                         "stats_since": resort.slot_stats.since()}, headers=NO_STORE)


def _slot_machines(resort, cabinets: list) -> list:
    """Each slot machine on the floor or with figures: its cabinets, and its spins, stakes, returns, bonuses and
    jackpots in all and split between humans and NPCs (slots/stats.py)."""
    blank = dict.fromkeys(slot_stats.FIELDS, 0)
    out = {}
    def machine(variant):
        if variant not in out:
            v = SLOT_VARIANTS.get(variant)
            out[variant] = {"variant": variant, "name": v.name if v else variant, "cabinets": 0,
                            **blank, "human": dict(blank), "npc": dict(blank)}
        return out[variant]
    for c in cabinets:
        machine(c["variant"])["cabinets"] += 1
    for r in resort.slot_stats.rows():
        m = machine(r["variant"])
        for k in slot_stats.FIELDS:
            m[k] += r[k]
            m[r["who"]][k] += r[k]
    return sorted(out.values(), key=lambda m: (-m["cabinets"], m["name"]))


@app.put("/api/slots/jackpot-settings")
async def slots_jackpot_settings(request: Request):
    """Each meter's share of every bet and how much it grows by a second on its own."""
    try:
        changes = slot_jackpots.clean_settings(await request.json())
    except ValueError as e:
        raise HTTPException(400, str(e))
    resort = request.app.state.resort
    settings = resort.slot_jackpots.configure(changes)
    resort.broadcast_all(resort.slot_jackpots.snapshot())   # the games' meters pick up the new speed
    return {"settings": settings, "jackpot_rtp": 100 * resort.slot_jackpots.rtp()}


@app.post("/api/slots/reset-meter/{tier}")
def slots_reset_meter(tier: str, request: Request):
    resort = request.app.state.resort
    if tier not in slot_jackpots.TIER_IDS:
        raise HTTPException(400, f"There's no {tier!r} meter.")
    resort.slot_jackpots.reset(tier)
    resort.broadcast_all(resort.slot_jackpots.snapshot())
    return {"ok": True, "amount": resort.slot_jackpots.amount(tier)}


@app.get("/api/slots/art/manifest")
def slot_art_manifest(request: Request):
    return JSONResponse(request.app.state.slot_art.manifest(), headers=NO_STORE)


@app.get("/slot-art/{variant}/{source:path}")
def slot_art_file(variant: str, source: str, request: Request):
    path = request.app.state.slot_art.file_path(variant, source)
    if path is None:
        raise HTTPException(404, "No such image")
    cache = "public, max-age=31536000, immutable" if "v" in request.query_params else "no-cache"
    kind = {".ttf": "font/ttf", ".otf": "font/otf"}.get(path.suffix.lower(), "image/png")
    return FileResponse(path, media_type=kind, headers={"Cache-Control": cache})


# ------------------------------------------------------------------ the floor plan (the admin page's Floor plan tab)
# (The changes run on the event loop, not the threadpool: a publish changes the floor the NPCs are walking.)
def _plan_call(fn, *args):
    try:
        return JSONResponse(fn(*args), headers=NO_STORE)
    except plan.PlanConflict as e:
        raise HTTPException(409, str(e))
    except plan.PlanError as e:
        raise HTTPException(400, str(e))


# Each takes ?casino=<id> (the default: Demo): every casino has its own plan.
def _board(request: Request, casino: str) -> plan.PlanBoard:
    board = request.app.state.boards.get(casino)
    if board is None:
        raise HTTPException(404, f"There's no casino {casino!r}.")
    return board


@app.get("/api/plan")
async def plan_view(request: Request, casino: str = casinos.DEMO):
    return _plan_call(_board(request, casino).view)


@app.get("/api/plan/catalogue")
async def plan_catalogue(request: Request, casino: str = casinos.DEMO):
    return _plan_call(plan.catalogue, _board(request, casino).builds_dir)


@app.put("/api/plan/draft")
async def plan_save(request: Request, casino: str = casinos.DEMO):
    body = await _json_body(request, "{rooms: [...], spawn, base_rev}")
    return _plan_call(_board(request, casino).save, body, body.get("base_rev"))


@app.post("/api/plan/publish")
async def plan_publish(request: Request, casino: str = casinos.DEMO):
    return _plan_call(_board(request, casino).publish)


@app.post("/api/plan/discard")
async def plan_discard(request: Request, casino: str = casinos.DEMO):
    return _plan_call(_board(request, casino).discard)


@app.get("/api/plan/history")
async def plan_history(request: Request, casino: str = casinos.DEMO):
    return _plan_call(_board(request, casino).history)


@app.post("/api/plan/rollback/{hid}")
async def plan_rollback(request: Request, hid: str, casino: str = casinos.DEMO):
    return _plan_call(_board(request, casino).rollback, hid)


# ------------------------------------------------------------------ the casinos (resort.py; the Floor plan tab's Casinos)
def _casino_call(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, "There's no such casino.")
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/casinos")
async def casinos_list(request: Request):
    return JSONResponse({"casinos": request.app.state.resort.overview()}, headers=NO_STORE)


@app.post("/api/casinos")
async def casinos_add(request: Request):
    """{name, blurb, start: "lobby" | "copy:<id>"}: a new hidden casino."""
    body = await _json_body(request, "{name, blurb, start}")
    resort = request.app.state.resort
    cid = _casino_call(resort.add_casino, body.get("name"), body.get("blurb", ""), str(body.get("start") or "lobby"))
    return {"id": cid, "casinos": resort.overview()}


@app.put("/api/casinos/{cid}")
async def casinos_change(cid: str, request: Request):
    """Any of {name, blurb, open, population, order}."""
    body = await _json_body(request, "{name, blurb, open, population, order}")
    resort = request.app.state.resort
    _casino_call(resort.change_casino, cid, body)
    return {"casinos": resort.overview()}


@app.delete("/api/casinos/{cid}")
async def casinos_delete(cid: str, request: Request):
    resort = request.app.state.resort
    _casino_call(resort.delete_casino, cid)
    return {"casinos": resort.overview()}


# ------------------------------------------------------------------ the floor plan's asset library (plan_assets.py)
def _asset_call(request: Request, fn, *args):
    try:
        out = fn(*args)
    except plan_assets.AssetError as e:
        raise HTTPException(400, str(e))
    lib = request.app.state.plan_assets
    for s in request.app.state.resort.sessions:   # (previews too)
        if s.player is not None:
            s.push({"type": "plan_art_changed", "version": lib.version})
    return out


@app.get("/api/plan/art")
async def plan_art_manifest(request: Request):
    return JSONResponse(request.app.state.plan_assets.manifest(), headers=NO_STORE)


@app.get("/plan-art/{rel:path}")
def plan_art_file(rel: str, request: Request):
    path = request.app.state.plan_assets.file_path(rel)
    if path is None:
        raise HTTPException(404, "No such picture")
    cache = "public, max-age=31536000, immutable" if "v" in request.query_params else "no-cache"
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": cache})


@app.get("/plan-art-credits")
def plan_art_credits():
    return FileResponse(plan_assets.BUILTIN_DIR / "CREDITS.md", media_type="text/plain; charset=utf-8")


@app.put("/api/plan-assets/{aid}/facings/{facing}")
async def plan_asset_facing(aid: str, facing: str, request: Request):
    return _asset_call(request, request.app.state.plan_assets.upload_facing, aid, facing, await request.body())


@app.put("/api/plan-assets/{filename}")
async def plan_asset_upload(filename: str, request: Request, kind: str = "asset"):
    return _asset_call(request, request.app.state.plan_assets.upload, filename, await request.body(), kind)


@app.patch("/api/plan-assets/{aid}")
async def plan_asset_update(aid: str, request: Request):
    return _asset_call(request, request.app.state.plan_assets.update, aid, await _json_body(request, "{name, category, ...}"))


@app.delete("/api/plan-assets/{aid}")
async def plan_asset_delete(aid: str, request: Request):
    plans = [p for board in request.app.state.boards.values()   # (every casino's)
             for p in [board.draft(), plan.load_live(board.data_dir)]
             + [plan._read(h) or {"rooms": []} for h in sorted((board.dir / "history").glob("*.json"))[-3:]]]
    _asset_call(request, request.app.state.plan_assets.delete, aid, plans)
    return {"deleted": aid}


# ------------------------------------------------------------------ slot design (the admin page)
# The Slot design tab's board (slot_design.py). Generating runs in the board's own background task.
def _design_call(fn, *args):
    try:
        return fn(*args)
    except DesignError as e:
        raise HTTPException(400, str(e))


@app.get("/api/slot-design")
def slot_design_list(request: Request):
    return JSONResponse({"designs": request.app.state.slot_design.listing()}, headers=NO_STORE)


@app.post("/api/slot-design")
async def slot_design_create(request: Request):
    body = await _json_body(request, "{name, brief}")
    return {"id": await run_in_threadpool(_design_call, request.app.state.slot_design.create_design,
                                          body.get("name"), body.get("brief", ""))}


@app.get("/api/slot-design/{design}")
def slot_design_overview(design: str, request: Request):
    return JSONResponse(_design_call(request.app.state.slot_design.overview, design), headers=NO_STORE)


@app.get("/api/slot-design/{design}/status")
def slot_design_status(design: str, request: Request):
    return JSONResponse(_design_call(request.app.state.slot_design.status, design), headers=NO_STORE)


@app.patch("/api/slot-design/{design}/symbols/{sid}")
async def slot_design_update(design: str, sid: str, request: Request):
    body = await _json_body(request, "{choice, hue, keep, reiterate, note, base, add_ref, remove_ref, ...}")
    await run_in_threadpool(_design_call, request.app.state.slot_design.update_symbol, design, sid, body)
    return {"ok": True}


@app.post("/api/slot-design/{design}/symbols")
async def slot_design_add(design: str, request: Request):
    body = await _json_body(request, "{name, category, kind, prompt, key, ref}")
    return {"id": await run_in_threadpool(_design_call, request.app.state.slot_design.add_symbol, design, body)}


@app.delete("/api/slot-design/{design}/symbols/{sid}")
def slot_design_delete(design: str, sid: str, request: Request):
    _design_call(request.app.state.slot_design.delete_symbol, design, sid)
    return {"ok": True}


@app.patch("/api/slot-design/{design}/categories/{cid}")
async def slot_design_category(design: str, cid: str, request: Request):
    body = await _json_body(request, "{required, title}")
    _design_call(request.app.state.slot_design.update_category, design, cid, body)
    return {"ok": True}


@app.put("/api/slot-design/{design}/links/{filename}")
async def slot_design_link_upload(design: str, filename: str, request: Request):
    data = await request.body()
    return {"path": await run_in_threadpool(_design_call, request.app.state.slot_design.link_image, design, filename, data)}


@app.post("/api/slot-design/{design}/links")
async def slot_design_link_url(design: str, request: Request):
    body = await _json_body(request, "{url}")
    return {"path": await run_in_threadpool(_design_call, request.app.state.slot_design.link_url, design, body.get("url"))}


@app.patch("/api/slot-design/{design}/concept")
async def slot_design_concept(design: str, request: Request):
    body = await _json_body(request, "{name, brief, style, tiers, target_rtp, volatility}")
    _design_call(request.app.state.slot_design.update_concept, design, body)
    return {"ok": True}


@app.patch("/api/slot-design/{design}/prompts")
async def slot_design_prompts(design: str, request: Request):
    body = await _json_body(request, "{first_takes, redraw: {i: text}, text: {i: text}, bust, special, royal, lettering}")
    _design_call(request.app.state.slot_design.update_prompts, design, body)
    return {"ok": True}


@app.post("/api/slot-design/{design}/lettering-preview")
async def slot_design_lettering_preview(design: str, request: Request):
    """A sample of the shared lettering, as saved or with the {special_font, royal_font, top, bottom, outline} given."""
    body = await _json_body(request, "{special_font, royal_font, top, bottom, outline}")
    png = await run_in_threadpool(_design_call, request.app.state.slot_design.lettering_preview, design, body)
    return Response(png, media_type="image/png", headers=NO_STORE)


@app.put("/api/slot-design/{design}/steps/{step}")
async def slot_design_step(design: str, step: str, request: Request):
    body = await _json_body(request, "{status: todo|doing|done}")
    _design_call(request.app.state.slot_design.set_step, design, step, body.get("status"))
    return {"ok": True}


@app.put("/api/slot-design/{design}/sources/{filename}")
async def slot_design_source(design: str, filename: str, request: Request):
    data = await request.body()
    return {"path": await run_in_threadpool(_design_call, request.app.state.slot_design.add_source, design, filename, data)}


@app.post("/api/slot-design/{design}/cuts")
async def slot_design_cuts(design: str, request: Request):
    body = await _json_body(request, "{sheet, boxes: [{x, y, w, h, name, category, kind, key}]}")
    return {"made": await run_in_threadpool(_design_call, request.app.state.slot_design.cut_sheet, design,
                                            body.get("sheet"), body.get("boxes"))}


@app.post("/api/slot-design/{design}/symbols/{sid}/{action}")
async def slot_design_variant_action(design: str, sid: str, action: str, request: Request):
    """bin / restore {variant}; refine {variant, instruction}; fit {variant, fit}; fit-preview {variant, fit, hue};
    queue {} (Generate for this symbol alone); split {variant, name?} (a take into a new symbol of its own)."""
    body = await _json_body(request, "{variant, ...}")
    board, vid = request.app.state.slot_design, body.get("variant")
    if action == "bin":
        await run_in_threadpool(_design_call, board.bin_variant, design, sid, vid)
    elif action == "restore":
        await run_in_threadpool(_design_call, board.restore_variant, design, sid, vid)
    elif action == "refine":
        return {"job": await run_in_threadpool(_design_call, board.refine, design, sid, vid, body.get("instruction"))}
    elif action == "fit":
        return {"variant": await run_in_threadpool(_design_call, board.fit_save, design, sid, vid, body.get("fit"))}
    elif action == "split":
        return {"id": await run_in_threadpool(_design_call, board.split_variant, design, sid, vid, body.get("name"))}
    elif action == "queue":
        return {"queued": await run_in_threadpool(_design_call, board.generate, design, sid)}
    elif action == "fit-preview":
        png = await run_in_threadpool(_design_call, board.fit_preview, design, sid, vid, body.get("fit"), body.get("hue", "gold"))
        return Response(png, media_type="image/png", headers=NO_STORE)
    else:
        raise HTTPException(404, f"No action {action!r}")
    return {"ok": True}


@app.put("/api/slot-design/{design}/ladder")
async def slot_design_ladder(design: str, request: Request):
    body = await _json_body(request, "{slots: {tier: symbol}, upgrades: {tier: tier}}")
    return await run_in_threadpool(_design_call, request.app.state.slot_design.set_ladder, design,
                                   body.get("slots"), body.get("upgrades"))


@app.patch("/api/slot-design/{design}/scene")
async def slot_design_scene(design: str, request: Request):
    body = await _json_body(request, "{background, logo_file, frame}")
    await run_in_threadpool(_design_call, request.app.state.slot_design.update_scene, design, body)
    return {"ok": True}


@app.post("/api/slot-design/{design}/scene/backgrounds")
async def slot_design_background_job(design: str, request: Request):
    body = await _json_body(request, "{description} or {path}")
    board = request.app.state.slot_design
    if body.get("path"):
        return {"path": await run_in_threadpool(_design_call, board.add_background, design, "", b"", body["path"])}
    return {"job": await run_in_threadpool(_design_call, board.queue_background, design, body.get("description"))}


@app.put("/api/slot-design/{design}/scene/backgrounds/{filename}")
async def slot_design_background_upload(design: str, filename: str, request: Request):
    data = await request.body()
    return {"path": await run_in_threadpool(_design_call, request.app.state.slot_design.add_background, design, filename, data)}


@app.post("/api/slot-design/{design}/scene/bin")
async def slot_design_scene_bin(design: str, request: Request):
    body = await _json_body(request, "{path}")
    await run_in_threadpool(_design_call, request.app.state.slot_design.bin_scene, design, body.get("path"))
    return {"ok": True}


@app.post("/api/slot-design/{design}/scene/restore")
async def slot_design_scene_restore(design: str, request: Request):
    body = await _json_body(request, "{path}")
    await run_in_threadpool(_design_call, request.app.state.slot_design.restore_scene, design, body.get("path"))
    return {"ok": True}


@app.post("/api/slot-design/{design}/scene/logo/generate")
async def slot_design_logo_job(design: str, request: Request):
    body = await _json_body(request, "{how: stylise|generate, lines, font, style}")
    return {"job": await run_in_threadpool(_design_call, request.app.state.slot_design.queue_logo, design, body)}


@app.post("/api/slot-design/{design}/scene/logo")
async def slot_design_logo(design: str, request: Request):
    body = await _json_body(request, "{lines, font, top, bottom, outline, emblem}")
    return {"path": await run_in_threadpool(_design_call, request.app.state.slot_design.render_logo, design, body)}


@app.post("/api/slot-design/{design}/scene/skins")
async def slot_design_skin_new(design: str, request: Request):
    body = await _json_body(request, "a skin (docs/slots/scenes.md)")
    return {"slug": await run_in_threadpool(_design_call, request.app.state.slot_design.put_skin, design, None, body)}


@app.put("/api/slot-design/{design}/scene/skins/{slug}")
async def slot_design_skin_put(design: str, slug: str, request: Request):
    body = await _json_body(request, "a skin (docs/slots/scenes.md)")
    return {"slug": await run_in_threadpool(_design_call, request.app.state.slot_design.put_skin, design, slug, body)}


@app.patch("/api/slot-design/{design}/scene/skins/{slug}")
async def slot_design_skin_patch(design: str, slug: str, request: Request):
    body = await _json_body(request, "{colours, palette, glass, parts, decor, fonts, texts, name, note, base}")
    await run_in_threadpool(_design_call, request.app.state.slot_design.update_skin, design, slug, body)
    return {"ok": True}


@app.post("/api/slot-design/{design}/scene/skins/{slug}/{action}")
async def slot_design_skin_action(design: str, slug: str, action: str, request: Request):
    body = await _json_body(request, "{name?, base?}") if (await request.body()) else {}
    return {"slug": await run_in_threadpool(_design_call, request.app.state.slot_design.skin_action, design, slug, action, body)}


@app.patch("/api/slot-design/{design}/scene/brief")
async def slot_design_brief(design: str, request: Request):
    body = await _json_body(request, "{text?, refs?, ask?, withdraw?}")
    await run_in_threadpool(_design_call, request.app.state.slot_design.update_brief, design, body)
    return {"ok": True}


@app.put("/api/slot-design/{design}/scene/brief/{filename}")
async def slot_design_brief_ref(design: str, filename: str, request: Request):
    data = await request.body()
    return {"path": await run_in_threadpool(_design_call, request.app.state.slot_design.add_brief_ref, design, filename, data)}


@app.put("/api/slot-design/{design}/fonts/{filename}")
async def slot_design_font(design: str, filename: str, request: Request):
    data = await request.body()
    return {"font": await run_in_threadpool(_design_call, request.app.state.slot_design.add_font, design, filename, data)}


@app.patch("/api/slot-design/{design}/features")
async def slot_design_features(design: str, request: Request):
    body = await _json_body(request, "{enabled, rates, free_rates, tables}")
    _design_call(request.app.state.slot_design.update_features, design, body)
    return {"ok": True}


@app.patch("/api/slot-design/{design}/bonuses")
async def slot_design_bonuses(design: str, request: Request):
    body = await _json_body(request, "{trail, free, buy}")
    _design_call(request.app.state.slot_design.update_bonuses, design, body)
    return {"ok": True}


@app.put("/api/slot-design/{design}/art-slots/{key}")
async def slot_design_art_slot(design: str, key: str, request: Request):
    body = await _json_body(request, "{value?: a board path, 'sym:<id>' or null, adjust?: {scale, dx, dy, rot, mirror, flip, bright, sat} or null}")
    _design_call(request.app.state.slot_design.set_art_slot, design, key, body)
    return {"ok": True}


@app.post("/api/slot-design/{design}/specs")
async def slot_design_add_spec(design: str, request: Request):
    body = await _json_body(request, "{kind: feature|bonus, name, description, timing, art}")
    return _design_call(request.app.state.slot_design.add_spec, design, body)


@app.delete("/api/slot-design/{design}/specs/{spec_id}")
def slot_design_remove_spec(design: str, spec_id: int, request: Request):
    _design_call(request.app.state.slot_design.remove_spec, design, spec_id)
    return {"ok": True}


@app.patch("/api/slot-design/{design}/sprites")
async def slot_design_sprites(design: str, request: Request):
    body = await _json_body(request, "{win, colours, fonts, cabinet}")
    _design_call(request.app.state.slot_design.update_sprites, design, body)
    return {"ok": True}


@app.get("/slot-design-font/{design}/{name}")
def slot_design_font_file(design: str, name: str, request: Request):
    path = _design_call(request.app.state.slot_design.font_file, design, name)
    return Response(slot_design_art.web_font(path.read_bytes()), media_type="font/otf" if name.lower().endswith(".otf") else "font/ttf")


@app.put("/api/slot-design/{design}/sounds/{key}")
async def slot_design_sound(design: str, key: str, request: Request):
    body = await _json_body(request, "{files: [sound ids], gain_db}")
    _design_call(request.app.state.slot_design.set_sound, design, key, body.get("files"), body.get("gain_db", 0.0))
    return {"ok": True}


@app.put("/api/slot-design/{design}/sound-preset")
async def slot_design_sound_preset(design: str, request: Request):
    """The slot preset the slot starts on: `{preset}` ("slots" for Default)."""
    body = await _json_body(request, "{preset}")
    _design_call(request.app.state.slot_design.set_sound_preset, design, body.get("preset"))
    return {"ok": True}


@app.delete("/api/slot-design/{design}/sounds/{key}")
def slot_design_sound_inherit(design: str, key: str, request: Request):
    _design_call(request.app.state.slot_design.inherit_sound, design, key)
    return {"ok": True}


@app.patch("/api/slot-design/{design}/maths")
async def slot_design_maths(design: str, request: Request):
    body = await _json_body(request, "{pays, counts, big_counts}")
    _design_call(request.app.state.slot_design.update_maths, design, body)
    return {"ok": True}


@app.post("/api/slot-design/{design}/maths/freeze")
async def slot_design_freeze(design: str, request: Request):
    body = await _json_body(request, "{strips, free_strips, big_strip, report, sample, exact}")
    return await run_in_threadpool(_design_call, request.app.state.slot_design.freeze_maths, design, body)


@app.put("/api/slot-design/{design}/rules")
async def slot_design_rules(design: str, request: Request):
    body = await _json_body(request, "{lines: [...]} (null: back to the written ones)")
    _design_call(request.app.state.slot_design.set_rules, design, body.get("lines"))
    return {"ok": True}


@app.post("/api/slot-design/{design}/sign-off")
def slot_design_sign_off(design: str, request: Request):
    return _design_call(request.app.state.slot_design.sign_off, design)


@app.post("/api/slot-design/{design}/reopen")
def slot_design_reopen(design: str, request: Request):
    _design_call(request.app.state.slot_design.reopen, design)
    return {"ok": True}


@app.post("/api/slot-design/{design}/build")
async def slot_design_build(design: str, request: Request):
    return await run_in_threadpool(_design_call, request.app.state.slot_design.build, design)


@app.post("/api/slot-design/{design}/install")
def slot_design_install(design: str, request: Request):
    return {"message": _design_call(request.app.state.slot_design.install, design)}


@app.post("/api/slot-design/{design}/generate")
def slot_design_generate(design: str, request: Request):
    return {"queued": _design_call(request.app.state.slot_design.generate, design)}


@app.delete("/api/slot-design/{design}/jobs")
def slot_design_cancel_all(design: str, request: Request):
    return {"cancelled": _design_call(request.app.state.slot_design.cancel_all, design)}


@app.post("/api/slot-design/{design}/hide-unused")
def slot_design_hide_unused(design: str, request: Request):
    return {"hidden": _design_call(request.app.state.slot_design.hide_unused, design)}


@app.post("/api/slot-design/{design}/jobs/{job_id}/retry")
def slot_design_retry(design: str, job_id: int, request: Request):
    _design_call(request.app.state.slot_design.retry, design, job_id)
    return {"ok": True}


@app.delete("/api/slot-design/{design}/jobs/{job_id}")
def slot_design_cancel(design: str, job_id: int, request: Request):
    _design_call(request.app.state.slot_design.cancel, design, job_id)
    return {"ok": True}


@app.get("/slot-design/{design}/{rel:path}")
def slot_design_file(design: str, rel: str, request: Request):
    d = request.app.state.slot_design.designs.get(design)
    path = d.path(rel) if d else None
    if path is None:
        raise HTTPException(404, "No such image")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------ NPCs (the admin page)
# Anything touching the casino or the store runs here on the event loop; only
# building a sprite sheet (pure image work) goes to a worker thread.
from fastapi.concurrency import run_in_threadpool  # noqa: E402

from casino_server import art, roster, seating, staff, table_styles  # noqa: E402


def _npc_view(request: Request, rec: dict) -> dict:
    casino = request.app.state.resort.npc_casino(rec["id"])   # (the one they're in, if any)
    looks: LookCache = request.app.state.looks
    lid = art.look_id(rec["look"])
    status = casino.npcs.status().get(rec["id"]) if casino else None
    dealing = casino.dealers.status().get(rec["id"]) if casino else None
    return {**rec, "look_id": lid, "look_url": f"/looks/{lid}.png" if looks.path(lid) else None,
            "on_floor": status, "dealing": dealing, "casino": casino.id if casino and (status or dealing) else None}


async def _body(request: Request) -> dict:
    try:
        data = await request.json()
    except ValueError:
        raise HTTPException(400, "Expected JSON.")
    if not isinstance(data, dict):
        raise HTTPException(400, "Expected a JSON object.")
    return data


@app.get("/api/npc-options")
def npc_options(request: Request):
    crew = staff.load(request.app.state.resort.store)
    return {**art.catalogue(), "roles": {k: r["label"] for k, r in crew["roles"].items()}, "staff": crew["roles"],
            "uniforms": crew["uniforms"], "uniform_slots": list(staff.UNIFORM_SLOTS), "on_the_floor": list(roster.ON_THE_FLOOR),
            "archetypes": roster.ARCHETYPES, "modifiers": roster.MODIFIERS, "games": roster.GAMES,
            "tables": {casinos.qualify(c.id, tid): cfg["name"] for c in request.app.state.resort.casinos.values()
                       for tid, cfg in c.floor.tables.items()},
            "casinos": {c["id"]: c["name"] for c in request.app.state.resort.registry}}


@app.get("/api/look-options")
def look_options():
    """What the game's character designer offers (art.catalogue())."""
    return art.catalogue()


@app.post("/api/looks/preview")
async def look_preview(request: Request):
    data = await _body(request)
    looks: LookCache = request.app.state.looks
    try:
        lid = await run_in_threadpool(looks.ensure, data.get("look") or {})
    except art.ArtError as e:
        raise HTTPException(400, str(e))
    return {"id": lid, "url": f"/looks/{lid}.png"}


@app.get("/looks/{look}.png")
def look_sheet(look: str, request: Request):
    looks: LookCache = request.app.state.looks
    path = looks.path(look) if look.startswith("x_") and look[2:].isalnum() else None
    if path is None:
        raise HTTPException(404, "No such look.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/api/npcs")
async def npcs_list(request: Request):
    store = request.app.state.resort.store
    return {"npcs": [_npc_view(request, r) for r in store.npcs()],
            "archived": [_npc_view(request, r) for r in store.npcs(archived=True)], "settings": roster.settings(store)}


def _roles(request: Request) -> dict:
    return staff.roles(request.app.state.resort.store)


@app.post("/api/npcs")
async def npcs_create(request: Request):
    data = await _body(request)
    try:
        rec = roster.clean(data, roles=_roles(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    await run_in_threadpool(request.app.state.looks.ensure, rec["look"])
    store = request.app.state.resort.store
    return _npc_view(request, store.npc(store.create_npc(rec)))


def _ensure_looks(looks: LookCache, recs: list[dict]) -> list[str]:
    return [looks.ensure(r["look"]) for r in recs]


@app.post("/api/npcs/generate")
async def npcs_generate(request: Request):
    """Bulk creation, step one: random drafts to review (nothing's saved). `taken` is the
    names already in the review, so a second batch doesn't repeat them."""
    data = await _body(request)
    store = request.app.state.resort.store
    taken = {n["name"] for n in store.npcs(archived=None)} | {str(n) for n in data.get("taken") or []}
    role = data.get("role") or "punter"
    try:
        drafts = roster.generate(int(data.get("count") or 0), role,
                                 data.get("archetype") or "mix", data.get("body") or "", data.get("traits") or [],
                                 taken, bool(data.get("enabled", True)), roles=_roles(request),
                                 uniform=staff.role_uniform(store, role))
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e))
    ids = await run_in_threadpool(_ensure_looks, request.app.state.looks, drafts)
    return {"drafts": [{**d, "look_url": f"/looks/{lid}.png"} for d, lid in zip(drafts, ids)]}


@app.post("/api/npcs/bulk")
async def npcs_bulk(request: Request):
    """Bulk creation, step two: the reviewed drafts, all or nothing."""
    data = await _body(request)
    items = data.get("npcs")
    if not isinstance(items, list) or not 1 <= len(items) <= roster.MAX_BULK:
        raise HTTPException(400, f"Send 1-{roster.MAX_BULK} NPCs.")
    store = request.app.state.resort.store
    seen = {n["name"].lower() for n in store.npcs(archived=None)}
    roles = _roles(request)
    recs = []
    for i, item in enumerate(items, 1):
        try:
            rec = roster.clean(item if isinstance(item, dict) else {}, roles=roles)
        except ValueError as e:
            raise HTTPException(400, f"#{i} {item.get('name') or '(no name)' if isinstance(item, dict) else ''}: {e}")
        if rec["name"].lower() in seen:
            raise HTTPException(400, f"#{i}: there's already someone called {rec['name']}.")
        seen.add(rec["name"].lower())
        recs.append(rec)
    await run_in_threadpool(_ensure_looks, request.app.state.looks, recs)
    return {"npcs": [_npc_view(request, store.npc(store.create_npc(r))) for r in recs]}


def _get_npc(request: Request, npc_id: int) -> dict:
    rec = request.app.state.resort.store.npc(npc_id)
    if rec is None:
        raise HTTPException(404, "No such NPC.")
    return rec


@app.get("/api/npcs/{npc_id}")
async def npcs_get(npc_id: int, request: Request):
    rec = _get_npc(request, npc_id)
    store = request.app.state.resort.store
    return {**_npc_view(request, rec), "visits": store.npc_visits(npc_id, 25)}


@app.put("/api/npcs/{npc_id}")
async def npcs_update(npc_id: int, request: Request):
    old = _get_npc(request, npc_id)
    data = await _body(request)
    try:
        rec = roster.clean(data, existing=old, roles=_roles(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    await run_in_threadpool(request.app.state.looks.ensure, rec["look"])
    resort = request.app.state.resort
    resort.store.update_npc(npc_id, rec)
    new = resort.store.npc(npc_id)
    if new["look"] != old["look"] or new["name"] != old["name"]:   # on the floor now: they change in front of you
        resort.restyle(new)
    return _npc_view(request, new)


@app.delete("/api/npcs/{npc_id}")
async def npcs_delete(npc_id: int, request: Request):
    """For good: only from the archive."""
    if not _get_npc(request, npc_id)["archived_at"]:
        raise HTTPException(400, "Archive them first: only archived NPCs can be deleted for good.")
    request.app.state.resort.store.delete_npc(npc_id)
    return {"deleted": npc_id}


@app.post("/api/npcs/{npc_id}/archive")
async def npcs_archive(npc_id: int, request: Request):
    """Into the archive: off the floor (a punter finishes their round and leaves, a dealer is relieved at the next
    betting window), out of the roster, and not picked for visits or shifts until restored."""
    _get_npc(request, npc_id)
    resort = request.app.state.resort
    for casino in resort.casinos.values():
        casino.npcs.send_home(npc_id, casino.clock())
        casino.dealers.stand_down(npc_id)
    resort.store.set_archived(npc_id, True)
    return _npc_view(request, _get_npc(request, npc_id))


@app.post("/api/npcs/{npc_id}/restore")
async def npcs_restore(npc_id: int, request: Request):
    rec = _get_npc(request, npc_id)
    resort = request.app.state.resort
    if rec["role"] not in _roles(request):
        raise HTTPException(400, "Their role's been deleted: give them another one first.")
    resort.store.set_archived(npc_id, False)
    for casino in resort.casinos.values():
        casino.dealers.dismissed.discard(npc_id)
    return _npc_view(request, _get_npc(request, npc_id))


@app.post("/api/npcs/{npc_id}/bring-in")
async def npcs_bring_in(npc_id: int, request: Request, casino: str = casinos.DEMO):
    """In through a casino's door now (?casino=<id>: Demo if unset)."""
    if _get_npc(request, npc_id)["archived_at"]:
        raise HTTPException(400, "They're archived: restore them first.")
    casino = request.app.state.resort.casinos.get(casino)
    if casino is None:
        raise HTTPException(404, "There's no such casino.")
    try:
        casino.npcs.bring_in(npc_id, casino.clock())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _npc_view(request, _get_npc(request, npc_id))


@app.post("/api/npcs/{npc_id}/send-home")
async def npcs_send_home(npc_id: int, request: Request):
    _get_npc(request, npc_id)
    casino = request.app.state.resort.npc_casino(npc_id)
    if casino is None or not casino.npcs.send_home(npc_id, casino.clock()):
        raise HTTPException(400, "They're not in a casino.")
    return _npc_view(request, _get_npc(request, npc_id))


@app.post("/api/npcs/{npc_id}/reset-stats")
async def npcs_reset(npc_id: int, request: Request):
    _get_npc(request, npc_id)
    request.app.state.resort.store.reset_npc_stats(npc_id)
    return _npc_view(request, _get_npc(request, npc_id))


@app.get("/api/npc-settings")
async def npc_settings_get(request: Request):
    return roster.settings(request.app.state.resort.store)


@app.put("/api/npc-settings")
async def npc_settings_put(request: Request):
    data = await _body(request)
    store = request.app.state.resort.store
    try:
        new = roster.clean_settings(data)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "Those settings don't make sense.")
    store.set_json("npc_settings", {**store.get_json("npc_settings", {}), **new})
    return roster.settings(store)


# ------------------------------------------------------------------ staff roles and uniforms (the NPCs tab)
def _staff_call(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, "No such role or uniform.")
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/staff")
async def staff_get(request: Request):
    return staff.load(request.app.state.resort.store)


@app.post("/api/staff/roles")
async def staff_role_add(request: Request):
    key = _staff_call(staff.save_role, request.app.state.resort.store, None, await _body(request))
    return {"key": key, **staff.load(request.app.state.resort.store)}


@app.put("/api/staff/roles/{key}")
async def staff_role_put(key: str, request: Request):
    _staff_call(staff.save_role, request.app.state.resort.store, key, await _body(request))
    return {"key": key, **staff.load(request.app.state.resort.store)}


@app.delete("/api/staff/roles/{key}")
async def staff_role_delete(key: str, request: Request):
    store = request.app.state.resort.store
    _staff_call(staff.delete_role, store, key, sum(n["role"] == key for n in store.npcs(archived=None)))
    return staff.load(store)


@app.post("/api/staff/uniforms")
async def staff_uniform_add(request: Request):
    key = _staff_call(staff.save_uniform, request.app.state.resort.store, None, await _body(request))
    return {"key": key, **staff.load(request.app.state.resort.store)}


@app.put("/api/staff/uniforms/{key}")
async def staff_uniform_put(key: str, request: Request):
    _staff_call(staff.save_uniform, request.app.state.resort.store, key, await _body(request))
    return {"key": key, **staff.load(request.app.state.resort.store)}


@app.delete("/api/staff/uniforms/{key}")
async def staff_uniform_delete(key: str, request: Request):
    _staff_call(staff.delete_uniform, request.app.state.resort.store, key)
    return staff.load(request.app.state.resort.store)


@app.post("/api/staff/uniforms/{key}/dress")
async def staff_uniform_dress(key: str, request: Request):
    """Put everyone (on the roster) whose role wears this uniform into it as it is now; on the floor, they change
    in front of you."""
    resort = request.app.state.resort
    crew = staff.load(resort.store)
    if key not in crew["uniforms"]:
        raise HTTPException(404, "No such uniform.")
    uniform = crew["uniforms"][key]
    roles = {k for k, r in crew["roles"].items() if r["uniform"] == key}
    changed = []
    for rec in resort.store.npcs():
        if rec["role"] not in roles:
            continue
        look = staff.dress(rec["look"], uniform[rec["look"]["body"]])
        try:
            look = art.validate(look)
        except art.ArtError as e:
            raise HTTPException(400, f"{rec['name']}: {e}")
        if look != rec["look"]:
            changed.append((rec, look))
    await run_in_threadpool(_ensure_looks, request.app.state.looks, [{"look": look} for _, look in changed])
    for rec, look in changed:
        resort.store.update_npc(rec["id"], {"look": look})
        resort.restyle(resort.store.npc(rec["id"]))
    return {"dressed": [rec["name"] for rec, _ in changed]}


@app.get("/api/bank-settings")
async def bank_settings_get(request: Request):
    return bank.settings(request.app.state.resort.store)


@app.put("/api/bank-settings")
async def bank_settings_put(request: Request):
    data = await _body(request)
    store = request.app.state.resort.store
    try:
        new = bank.clean_settings(data)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "Those settings don't make sense.")
    store.set_json("bank_settings", {**store.get_json("bank_settings", {}), **new})
    return bank.settings(store)


@app.get("/api/heat-settings")
async def heat_settings_get(request: Request):
    return heat.settings(request.app.state.resort.store)


@app.put("/api/heat-settings")
async def heat_settings_put(request: Request):
    data = await _body(request)
    store = request.app.state.resort.store
    try:
        new = heat.clean_settings({**heat.settings(store), **data})
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "Those settings don't make sense.")
    store.set_json("heat_settings", new)
    return heat.settings(store)


# ------------------------------------------------------------------ seating
def _seating_changed(request: Request) -> dict:
    """Every client redraws its chairs from the new styles."""
    resort = request.app.state.resort
    for casino in resort.casinos.values():
        casino.broadcast_all({"type": "seating", "seating": casino.seating_view()})
    return seating.load(resort.store)


@app.get("/api/seating")
async def seating_get(request: Request):
    return {**seating.load(request.app.state.resort.store), "choices": seating.CHOICES, "ranges": seating.RANGES}


@app.put("/api/seating/styles/{style_id}")
async def seating_style_put(style_id: str, request: Request):
    data = await _body(request)
    try:
        seating.save_style(request.app.state.resort.store, style_id, data)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "That style doesn't make sense.")
    return _seating_changed(request)


@app.delete("/api/seating/styles/{style_id}")
async def seating_style_delete(style_id: str, request: Request):
    try:
        seating.delete_style(request.app.state.resort.store, style_id)
    except KeyError:
        raise HTTPException(404, "No such style.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _seating_changed(request)


@app.put("/api/seating/tables")
async def seating_tables_put(request: Request):
    try:
        seating.assign(request.app.state.resort.store, await _body(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _seating_changed(request)


# ------------------------------------------------------------------ table styles
def _table_styles_changed(request: Request, kind: str) -> dict:
    """Every client restyles its tables; the admin page gets the kind it changed back."""
    resort = request.app.state.resort
    for casino in resort.casinos.values():
        casino.broadcast_all({"type": "table_styles", "table_styles": casino.styles_view()})
    return table_styles.load(resort.store, kind, casinos.every_table(request.app.state.boards))


def _style_kind(kind: str) -> str:
    if kind not in table_styles.KINDS:
        raise HTTPException(404, f"No kind of table called {kind!r}.")
    return kind


# Each takes ?kind=cards (the default), roulette or craps: each kind has its own styles and placement.
@app.get("/api/table-styles")
async def table_styles_get(request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    every = casinos.every_table(request.app.state.boards)
    return JSONResponse({**table_styles.load(request.app.state.resort.store, kind, every), "kind": kind,
                         "games": table_styles.styled_tables(every, kind), "choices": table_styles.KINDS[kind]["choices"],
                         "casinos": {c["id"]: c["name"] for c in request.app.state.resort.registry}},
                        headers=NO_STORE)


@app.put("/api/table-styles/styles/{style_id}")
async def table_style_put(style_id: str, request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    try:
        table_styles.save_style(request.app.state.resort.store, style_id, await _body(request), kind)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "That style doesn't make sense.")
    return _table_styles_changed(request, kind)


@app.delete("/api/table-styles/styles/{style_id}")
async def table_style_delete(style_id: str, request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    try:
        table_styles.delete_style(request.app.state.resort.store, style_id, kind)
    except KeyError:
        raise HTTPException(404, "No such style.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _table_styles_changed(request, kind)


@app.put("/api/table-styles/tables")
async def table_styles_tables_put(request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    try:
        table_styles.assign(request.app.state.resort.store, await _body(request), casinos.every_table(request.app.state.boards), kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _table_styles_changed(request, kind)


@app.get("/api/players")
async def players_stats(request: Request):
    resort = request.app.state.resort
    online = resort.online_players()
    now = time.time()
    players = resort.store.player_stats()
    for p in players:
        p["online"] = p["id"] in online
        p["casino"] = resort.where(p["id"])
        p["pit"] = resort.heat.status(("player", p["id"]))   # (Blackjack back-off, heat.py)
        if p["timeout_until"] and p["timeout_until"] <= now:   # (a timeout that's run out)
            p["timeout_until"] = None
    return {"players": players, "games": roster.GAMES, "now": now, "casinos": {c["id"]: c["name"] for c in resort.registry}}


# Player management. Protected, bans and timeouts are the account's (the device's), so they cover all its characters;
# a player id names a character, and acts on its account. A protected account can't be deleted, banned or timed out
# until it's unprotected.
MAX_TIMEOUT_MIN = 60 * 24 * 365


def _player(request: Request, player_id: int, change: bool = True) -> dict:
    p = request.app.state.resort.store.player(player_id)
    if p is None:
        raise HTTPException(404, "No such player.")
    if change and p["protected"]:
        raise HTTPException(400, f"{p['name']} is protected: unprotect them first.")
    return p


def _reason(data: dict) -> str:
    return " ".join(str(data.get("reason") or "").split())[:200]


@app.post("/api/players/{player_id}/protect")
async def players_protect(player_id: int, request: Request):
    data = await _body(request)
    p = _player(request, player_id, change=False)
    request.app.state.resort.store.set_protected(p["account_id"], bool(data.get("on", True)))
    return request.app.state.resort.store.player(player_id)


@app.post("/api/players/{player_id}/ban")
async def players_ban(player_id: int, request: Request):
    data = await _body(request)
    p = _player(request, player_id)
    resort = request.app.state.resort
    resort.store.set_bar(p["account_id"], banned=True, reason=_reason(data))
    resort.send_off(p["account_id"], "ban", reason=_reason(data))
    return resort.store.player(player_id)


@app.post("/api/players/{player_id}/timeout")
async def players_timeout(player_id: int, request: Request):
    data = await _body(request)
    p = _player(request, player_id)
    try:
        minutes = float(data.get("minutes"))
    except (TypeError, ValueError):
        minutes = 0
    if not 1 <= minutes <= MAX_TIMEOUT_MIN:
        raise HTTPException(400, "A timeout is a minute to a year.")
    resort = request.app.state.resort
    until = time.time() + minutes * 60
    resort.store.set_bar(p["account_id"], until=until, reason=_reason(data))
    resort.send_off(p["account_id"], "timeout", until=until, reason=_reason(data))
    return resort.store.player(player_id)


@app.post("/api/players/{player_id}/lift")
async def players_lift(player_id: int, request: Request):
    """Let their account back in (a ban or a timeout)."""
    p = _player(request, player_id)
    request.app.state.resort.store.set_bar(p["account_id"])
    return request.app.state.resort.store.player(player_id)


@app.delete("/api/players/{player_id}")
async def players_delete(player_id: int, request: Request):
    """One character gone for good, ledger and all (the account keeps its others). If it's playing, that session
    is hung up on."""
    p = _player(request, player_id)
    resort = request.app.state.resort
    resort.send_off(p["account_id"], "removed", player_id=player_id)
    resort.store.delete_player(player_id)
    return {"deleted": p["id"], "name": p["name"]}


@app.delete("/api/accounts/{account_id}")
async def accounts_delete(account_id: int, request: Request):
    """An account and every character on it gone for good. Anyone on it is hung up on; the device comes back as a
    new account with no characters."""
    store = request.app.state.resort.store
    a = store.account(account_id)
    if a is None:
        raise HTTPException(404, "No such account.")
    if a["protected"]:
        raise HTTPException(400, "That account is protected: unprotect it first.")
    names = [p.name for p in store.characters(account_id)]
    request.app.state.resort.send_off(account_id, "removed")
    store.delete_account(account_id)
    return {"deleted": account_id, "names": names}


@app.get("/credits", response_class=HTMLResponse)
def credits_page():
    rows = "".join(
        f"<li><b>{c['name']}</b> <code>{c['file']}</code> — {', '.join(c['authors'])} "
        f"({', '.join(c['licenses'])})</li>" for c in art.credits())
    return (f"<!doctype html><meta charset='utf-8'><title>Casino World credits</title>"
            f"<body style='font:15px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem'>"
            f"<h1>Character art credits</h1><p>Built from the Universal LPC Spritesheet Character Generator "
            f"(commit {art.COMMIT[:10]}). Licences as listed; derived sprite sheets carry the same licences.</p>"
            f"<ul>{rows}</ul><h1>Furniture and decor credits</h1><p>The floor plan's built-in furniture, rugs and floors "
            f"are cut from LPC packs on OpenGameArt: <a href='/plan-art-credits'>their credits in full</a>.</p></body>")


WEB_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=WEB_EXPORT_DIR, check_dir=False), name="web")
