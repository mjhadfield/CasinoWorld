"""
FastAPI app: serves the Godot web export from build/web, runs the /ws socket,
and serves the sound maintenance page (/maintenance) and its API (sounds.py).

The Casino (casino.py) holds every table, the store and the jackpot, and lives
on app.state for the app's lifespan. Each socket gets a Session; handlers push
messages onto session queues and a per-connection sender task delivers them.
The client never decides a hand -- it sends intents and renders what this sends.

Message shape both ways: a JSON object with a "type" field. See protocol.md.
"""

import asyncio
import contextlib
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from casino_server.art import LookCache
from casino_server.casino import Casino
from casino_server.session import Session
from casino_server import plan, plan_assets, slot_builds, slot_design_art
from casino_server.slot_art import ArtError, SlotArtBoard
from casino_server.slot_design import DEFAULT_DESIGNS_DIR, DesignBoard, DesignError
from casino_server.slots import jackpots as slot_jackpots
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
    plan.install(plan.load_live(data_dir))
    plan_board = plan.PlanBoard(data_dir, builds_dir)
    store = Store(data_dir / "casino.sqlite")
    for p in store.players():
        if p["stored_as"] != "integer":
            print(f"WARNING: {p['name']}'s balance is {p['balance']!r}, which isn't a number of pence; "
                  f"they'll be disconnected when they bet. Fix it with: "
                  f".venv/bin/python -m casino_server.admin set-balance {p['id']} <pounds>")
    # CASINO_SPEED < 1 speeds every table timer and NPC up (handy for demos/tests);
    # CASINO_NPCS sets how many NPCs roam the floor.
    speed = float(os.environ.get("CASINO_SPEED", "1"))
    npcs = os.environ.get("CASINO_NPCS")   # unset: the admin page's floor population
    looks = LookCache(data_dir)
    casino = Casino(store, speed=speed, npc_population=int(npcs) if npcs else None, npc_pace=speed, looks=looks)
    app.state.casino = casino
    app.state.sounds = SoundBoard(data_dir)
    app.state.slot_art = SlotArtBoard(data_dir)
    app.state.plan = plan_board
    app.state.plan_assets = library
    plan_board.on_draft = lambda _draft: casino.preview_changed()
    plan_board.on_publish = lambda _live: casino.broadcast_world()
    casino.preview_world = lambda room_id: plan.preview_world(plan_board.draft(), room_id)
    # CASINO_DESIGNS_DIR points the Slot design board elsewhere (tests and the dev instance use a copy).
    app.state.slot_design = DesignBoard(Path(os.environ.get("CASINO_DESIGNS_DIR") or DEFAULT_DESIGNS_DIR))
    app.state.slot_design.sounds = app.state.sounds
    app.state.slot_design.builds_dir = builds_dir
    design_worker = asyncio.create_task(app.state.slot_design.run())
    app.state.looks = looks
    await asyncio.to_thread(_build_roster_looks, store, looks)   # so nobody waits for a sheet on the floor
    await casino.start()
    try:
        yield
    finally:
        design_worker.cancel()
        await casino.stop()
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
    casino: Casino = ws.app.state.casino
    session = Session()
    sender = asyncio.create_task(_sender(ws, session))
    casino.connect(session)
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
            casino.handle(session, msg)
    except WebSocketDisconnect:
        pass
    finally:
        casino.disconnect(session)
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
# The maintenance page picks the sound for each game moment; games fetch the
# manifest at start and again whenever they're sent "sounds_changed".
MAINTENANCE_PAGE = Path(__file__).resolve().parent / "maintenance.html"
NO_STORE = {"Cache-Control": "no-store"}


def _sounds_changed(request: Request):
    board: SoundBoard = request.app.state.sounds
    request.app.state.casino.broadcast_all({"type": "sounds_changed", "version": board.version})


def _sound_call(fn, *args):
    try:
        return fn(*args)
    except SoundError as e:
        raise HTTPException(400, str(e))


@app.get("/maintenance", response_class=HTMLResponse)
def maintenance_page():
    return FileResponse(MAINTENANCE_PAGE, headers=NO_STORE)


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return FileResponse(MAINTENANCE_PAGE, headers=NO_STORE)


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
    casino = request.app.state.casino
    cabinets = []
    for table_id, runner in casino.tables.items():
        m = runner.machine
        if m.game != "slots":
            continue
        p = m.seats[0].participant
        cabinets.append({"table": table_id, "variant": m.variant.id, "name": m.variant.name, "phase": m.phase,
                         "player": p.name if p else None, "human": bool(p and p.is_human), "bet": m.bet,
                         "pending": [f[0] for f in m.pending]})
    wagered = returned = 0
    for player in casino.store.player_stats():
        g = player["games"].get("slots")
        if g:
            wagered, returned = wagered + g["wagered"], returned + g["returned"]
    pg = casino.slot_jackpots
    tiers = [{**t, **pg.settings[t["id"]], "amount": pg.amount(t["id"])} for t in slot_jackpots.TIERS]
    return JSONResponse({"tiers": tiers, "cabinets": cabinets, "players": {"wagered": wagered, "returned": returned},
                         "jackpot_rtp": 100 * pg.rtp()}, headers=NO_STORE)


@app.put("/api/slots/jackpot-settings")
async def slots_jackpot_settings(request: Request):
    """Each meter's share of every bet and how much it grows by a second on its own."""
    try:
        changes = slot_jackpots.clean_settings(await request.json())
    except ValueError as e:
        raise HTTPException(400, str(e))
    casino = request.app.state.casino
    settings = casino.slot_jackpots.configure(changes)
    casino.broadcast_all(casino.slot_jackpots.snapshot())   # the games' meters pick up the new speed
    return {"settings": settings, "jackpot_rtp": 100 * casino.slot_jackpots.rtp()}


@app.post("/api/slots/reset-meter/{tier}")
def slots_reset_meter(tier: str, request: Request):
    casino = request.app.state.casino
    if tier not in slot_jackpots.TIER_IDS:
        raise HTTPException(400, f"There's no {tier!r} meter.")
    casino.slot_jackpots.reset(tier)
    casino.broadcast_all(casino.slot_jackpots.snapshot())
    return {"ok": True, "amount": casino.slot_jackpots.amount(tier)}


def _art_call(fn, *args):
    try:
        return fn(*args)
    except ArtError as e:
        raise HTTPException(400, str(e))


def _art_changed(request: Request):
    request.app.state.casino.broadcast_all({"type": "slot_art_changed", "version": request.app.state.slot_art.version})


@app.get("/api/slots/art")
def slot_art_overview(request: Request):
    return JSONResponse(request.app.state.slot_art.overview(), headers=NO_STORE)


@app.get("/api/slots/art/manifest")
def slot_art_manifest(request: Request):
    return JSONResponse(request.app.state.slot_art.manifest(), headers=NO_STORE)


@app.put("/api/slots/art/{variant}/{asset}")
async def slot_art_set(variant: str, asset: str, request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "Expected JSON: {source: 'flux2/H1.png'}")
    source = body.get("source") if isinstance(body, dict) else None
    chosen = _art_call(request.app.state.slot_art.set_choice, variant, asset, source)
    _art_changed(request)
    return {"choice": chosen}


@app.delete("/api/slots/art/{variant}/{asset}")
def slot_art_reset(variant: str, asset: str, request: Request):
    _art_call(request.app.state.slot_art.reset, variant, asset)
    _art_changed(request)
    return {"choice": request.app.state.slot_art.choice(variant, asset)}


@app.put("/api/slot-art-uploads/{variant}/{filename}")
async def slot_art_upload(variant: str, filename: str, request: Request):
    data = await request.body()
    return {"source": _art_call(request.app.state.slot_art.upload, variant, filename, data)}


@app.delete("/api/slot-art-uploads/{variant}/{filename}")
def slot_art_delete_upload(variant: str, filename: str, request: Request):
    _art_call(request.app.state.slot_art.delete_upload, variant, "uploads/" + filename)
    _art_changed(request)
    return {"ok": True}


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


@app.get("/api/plan")
async def plan_view(request: Request):
    return _plan_call(request.app.state.plan.view)


@app.get("/api/plan/catalogue")
async def plan_catalogue(request: Request):
    return _plan_call(plan.catalogue, request.app.state.plan.builds_dir)


@app.put("/api/plan/draft")
async def plan_save(request: Request):
    body = await _json_body(request, "{rooms: [...], spawn, base_rev}")
    return _plan_call(request.app.state.plan.save, body, body.get("base_rev"))


@app.post("/api/plan/publish")
async def plan_publish(request: Request):
    return _plan_call(request.app.state.plan.publish)


@app.post("/api/plan/discard")
async def plan_discard(request: Request):
    return _plan_call(request.app.state.plan.discard)


@app.get("/api/plan/history")
async def plan_history(request: Request):
    return _plan_call(request.app.state.plan.history)


@app.post("/api/plan/rollback/{hid}")
async def plan_rollback(request: Request, hid: str):
    return _plan_call(request.app.state.plan.rollback, hid)


# ------------------------------------------------------------------ the floor plan's asset library (plan_assets.py)
def _asset_call(request: Request, fn, *args):
    try:
        out = fn(*args)
    except plan_assets.AssetError as e:
        raise HTTPException(400, str(e))
    lib = request.app.state.plan_assets
    for s in request.app.state.casino.sessions:   # (previews too)
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
    board = request.app.state.plan
    plans = [board.draft(), plan.load_live(board.data_dir)] + [plan._read(p) or {"rooms": []} for p in sorted((board.dir / "history").glob("*.json"))[-3:]]
    _asset_call(request, request.app.state.plan_assets.delete, aid, plans)
    return {"deleted": aid}


# The Floor plan tab's scripts (plan_web/), never cached, so an edit shows on reload.
PLAN_WEB = Path(__file__).resolve().parent / "plan_web"


@app.get("/plan-ui/{rel:path}")
def plan_ui(rel: str):
    path = (PLAN_WEB / rel).resolve()
    if not path.is_relative_to(PLAN_WEB) or not path.is_file():
        raise HTTPException(404, "No such file")
    return FileResponse(path, headers=NO_STORE)


# The Tables tab's designer (table_styles_web/), never cached, so an edit shows on reload.
TABLE_STYLES_WEB = Path(__file__).resolve().parent / "table_styles_web"


@app.get("/table-styles-ui/{rel:path}")
def table_styles_ui(rel: str):
    path = (TABLE_STYLES_WEB / rel).resolve()
    if not path.is_relative_to(TABLE_STYLES_WEB) or not path.is_file():
        raise HTTPException(404, "No such file")
    return FileResponse(path, headers=NO_STORE)


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


# The wizard's own scripts (slot_design_web/), loaded by the Slot design tab; never cached, so an edit shows on reload.
# slots_math.js is the signed-off slot maths, served from its home in docs/slots/mockup (the one source for both).
SLOT_DESIGN_WEB = Path(__file__).resolve().parent / "slot_design_web"
SLOTS_MATH = Path(__file__).resolve().parents[2] / "docs" / "slots" / "mockup" / "slots_math.js"


@app.get("/slot-design-ui/{rel:path}")
def slot_design_ui(rel: str):
    if rel == "slots_math.js":
        return FileResponse(SLOTS_MATH, media_type="text/javascript", headers=NO_STORE)
    path = (SLOT_DESIGN_WEB / rel).resolve()
    if not path.is_relative_to(SLOT_DESIGN_WEB) or not path.is_file():
        raise HTTPException(404, "No such file")
    return FileResponse(path, headers=NO_STORE)


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

from casino_server import art, floor, roster, seating, table_styles  # noqa: E402


def _npc_view(request: Request, rec: dict) -> dict:
    casino = request.app.state.casino
    looks: LookCache = request.app.state.looks
    lid = art.look_id(rec["look"])
    status = casino.npcs.status().get(rec["id"])
    dealing = casino.dealers.status().get(rec["id"])
    return {**rec, "look_id": lid, "look_url": f"/looks/{lid}.png" if looks.path(lid) else None,
            "on_floor": status, "dealing": dealing}


async def _body(request: Request) -> dict:
    try:
        data = await request.json()
    except ValueError:
        raise HTTPException(400, "Expected JSON.")
    if not isinstance(data, dict):
        raise HTTPException(400, "Expected a JSON object.")
    return data


@app.get("/api/npc-options")
def npc_options():
    return {**art.catalogue(), "roles": roster.ROLES, "on_the_floor": list(roster.ON_THE_FLOOR),
            "archetypes": roster.ARCHETYPES, "modifiers": roster.MODIFIERS, "games": roster.GAMES,
            "tables": {tid: cfg["name"] for tid, cfg in floor.TABLES.items()}}


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
    store = request.app.state.casino.store
    return {"npcs": [_npc_view(request, r) for r in store.npcs()], "settings": roster.settings(store)}


@app.post("/api/npcs")
async def npcs_create(request: Request):
    data = await _body(request)
    try:
        rec = roster.clean(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await run_in_threadpool(request.app.state.looks.ensure, rec["look"])
    store = request.app.state.casino.store
    return _npc_view(request, store.npc(store.create_npc(rec)))


def _ensure_looks(looks: LookCache, recs: list[dict]) -> list[str]:
    return [looks.ensure(r["look"]) for r in recs]


@app.post("/api/npcs/generate")
async def npcs_generate(request: Request):
    """Bulk creation, step one: random drafts to review (nothing's saved). `taken` is the
    names already in the review, so a second batch doesn't repeat them."""
    data = await _body(request)
    store = request.app.state.casino.store
    taken = {n["name"] for n in store.npcs()} | {str(n) for n in data.get("taken") or []}
    try:
        drafts = roster.generate(int(data.get("count") or 0), data.get("role") or "punter",
                                 data.get("archetype") or "mix", data.get("body") or "", data.get("traits") or [],
                                 taken, bool(data.get("enabled", True)))
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
    store = request.app.state.casino.store
    seen = {n["name"].lower() for n in store.npcs()}
    recs = []
    for i, item in enumerate(items, 1):
        try:
            rec = roster.clean(item if isinstance(item, dict) else {})
        except ValueError as e:
            raise HTTPException(400, f"#{i} {item.get('name') or '(no name)' if isinstance(item, dict) else ''}: {e}")
        if rec["name"].lower() in seen:
            raise HTTPException(400, f"#{i}: there's already someone called {rec['name']}.")
        seen.add(rec["name"].lower())
        recs.append(rec)
    await run_in_threadpool(_ensure_looks, request.app.state.looks, recs)
    return {"npcs": [_npc_view(request, store.npc(store.create_npc(r))) for r in recs]}


def _get_npc(request: Request, npc_id: int) -> dict:
    rec = request.app.state.casino.store.npc(npc_id)
    if rec is None:
        raise HTTPException(404, "No such NPC.")
    return rec


@app.get("/api/npcs/{npc_id}")
async def npcs_get(npc_id: int, request: Request):
    rec = _get_npc(request, npc_id)
    store = request.app.state.casino.store
    return {**_npc_view(request, rec), "visits": store.npc_visits(npc_id, 25)}


@app.put("/api/npcs/{npc_id}")
async def npcs_update(npc_id: int, request: Request):
    old = _get_npc(request, npc_id)
    data = await _body(request)
    try:
        rec = roster.clean(data, existing=old)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await run_in_threadpool(request.app.state.looks.ensure, rec["look"])
    casino = request.app.state.casino
    casino.store.update_npc(npc_id, rec)
    new = casino.store.npc(npc_id)
    if new["look"] != old["look"] or new["name"] != old["name"]:   # on the floor now: they change in front of you
        casino.npcs.restyle(npc_id, new)
        casino.dealers.restyle(new)
    return _npc_view(request, new)


@app.delete("/api/npcs/{npc_id}")
async def npcs_delete(npc_id: int, request: Request):
    _get_npc(request, npc_id)
    casino = request.app.state.casino
    casino.npcs.send_home(npc_id, casino.clock())
    casino.store.delete_npc(npc_id)
    return {"deleted": npc_id}


@app.post("/api/npcs/{npc_id}/bring-in")
async def npcs_bring_in(npc_id: int, request: Request):
    _get_npc(request, npc_id)
    casino = request.app.state.casino
    try:
        casino.npcs.bring_in(npc_id, casino.clock())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _npc_view(request, _get_npc(request, npc_id))


@app.post("/api/npcs/{npc_id}/send-home")
async def npcs_send_home(npc_id: int, request: Request):
    _get_npc(request, npc_id)
    casino = request.app.state.casino
    if not casino.npcs.send_home(npc_id, casino.clock()):
        raise HTTPException(400, "They're not in the casino.")
    return _npc_view(request, _get_npc(request, npc_id))


@app.post("/api/npcs/{npc_id}/reset-stats")
async def npcs_reset(npc_id: int, request: Request):
    _get_npc(request, npc_id)
    request.app.state.casino.store.reset_npc_stats(npc_id)
    return _npc_view(request, _get_npc(request, npc_id))


@app.get("/api/npc-settings")
async def npc_settings_get(request: Request):
    return roster.settings(request.app.state.casino.store)


@app.put("/api/npc-settings")
async def npc_settings_put(request: Request):
    data = await _body(request)
    store = request.app.state.casino.store
    try:
        new = roster.clean_settings(data)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "Those settings don't make sense.")
    store.set_json("npc_settings", {**store.get_json("npc_settings", {}), **new})
    return roster.settings(store)


# ------------------------------------------------------------------ seating
def _seating_changed(request: Request) -> dict:
    """Every client redraws its chairs from the new styles."""
    current = seating.load(request.app.state.casino.store)
    request.app.state.casino.broadcast_all({"type": "seating", "seating": current})
    return current


@app.get("/api/seating")
async def seating_get(request: Request):
    return {**seating.load(request.app.state.casino.store), "choices": seating.CHOICES, "ranges": seating.RANGES}


@app.put("/api/seating/styles/{style_id}")
async def seating_style_put(style_id: str, request: Request):
    data = await _body(request)
    try:
        seating.save_style(request.app.state.casino.store, style_id, data)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "That style doesn't make sense.")
    return _seating_changed(request)


@app.delete("/api/seating/styles/{style_id}")
async def seating_style_delete(style_id: str, request: Request):
    try:
        seating.delete_style(request.app.state.casino.store, style_id)
    except KeyError:
        raise HTTPException(404, "No such style.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _seating_changed(request)


@app.put("/api/seating/tables")
async def seating_tables_put(request: Request):
    try:
        seating.assign(request.app.state.casino.store, await _body(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _seating_changed(request)


# ------------------------------------------------------------------ table styles
def _table_styles_changed(request: Request, kind: str) -> dict:
    """Every client restyles its tables; the admin page gets the kind it changed back."""
    store = request.app.state.casino.store
    request.app.state.casino.broadcast_all({"type": "table_styles", "table_styles": table_styles.load_all(store)})
    return table_styles.load(store, kind)


def _style_kind(kind: str) -> str:
    if kind not in table_styles.KINDS:
        raise HTTPException(404, f"No kind of table called {kind!r}.")
    return kind


# Each takes ?kind=cards (the default), roulette or craps: each kind has its own styles and placement.
@app.get("/api/table-styles")
async def table_styles_get(request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    return JSONResponse({**table_styles.load(request.app.state.casino.store, kind), "kind": kind,
                         "games": table_styles.styled_tables(kind), "choices": table_styles.KINDS[kind]["choices"]},
                        headers=NO_STORE)


@app.put("/api/table-styles/styles/{style_id}")
async def table_style_put(style_id: str, request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    try:
        table_styles.save_style(request.app.state.casino.store, style_id, await _body(request), kind)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e) or "That style doesn't make sense.")
    return _table_styles_changed(request, kind)


@app.delete("/api/table-styles/styles/{style_id}")
async def table_style_delete(style_id: str, request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    try:
        table_styles.delete_style(request.app.state.casino.store, style_id, kind)
    except KeyError:
        raise HTTPException(404, "No such style.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _table_styles_changed(request, kind)


@app.put("/api/table-styles/tables")
async def table_styles_tables_put(request: Request, kind: str = "cards"):
    kind = _style_kind(kind)
    try:
        table_styles.assign(request.app.state.casino.store, await _body(request), kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _table_styles_changed(request, kind)


@app.get("/api/players")
async def players_stats(request: Request):
    return {"players": request.app.state.casino.store.player_stats(), "games": roster.GAMES}


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
