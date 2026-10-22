// The Floor plan section (plan.py): the casino's rooms on one plan, and each room's blueprint.
//
//   Plan     every room on the floor, drawn to scale: drag them into place (doorways that meet light green), pick
//            which spawn point players appear at; the library of blueprints down the side (new, duplicate, place on
//            the floor or take off it, delete).
//   Room     one blueprint close up on a grid: drag things in from the palette (tables, slots, pieces, people,
//            furniture), move, turn (R), duplicate (Ctrl+D), copy and paste, delete; drag the walls to resize the
//            room; doors and archways, floor patches, the NPCs' points and no-go zones; the inspector for whatever's
//            picked.
//   Assets   the furniture library (assets.js).
//
// Every change is saved to the draft a moment later (undo and redo work across it); Preview opens the game on the
// draft, and Publish puts it on the live floor. The live check (red outlines) is geom.js's; the problems list is
// the server's, docked along the bottom of the canvas.
//
// Layout: the views, saving, Preview and Publish in the top bar; rooms or the palette | the canvas, filling its box,
// with the tools floating over it | the inspector.
import * as G from "/admin-ui/plan/geom.js";
import { drawRoom, drawItem, drawPaths, drawReach, loadTables, onImage } from "/admin-ui/plan/draw.js";

let $, el, api, status, top;
export function init(h) {
  ({ el, api, status, top } = h);
  app = h.view;
  $ = s => app.querySelector(s) || top.querySelector(s);
}
export function shown(on) { if (on && canvas) { sizeCanvas(); draw(); } }

const S = {
  draft: null, rev: 0, meta: {}, probs: [], npcs: [],
  mode: "plan", room: -1,           // the room (index) being edited
  sel: [],                          // [{t: item|point|zone|door|patch, i}] in the room being edited
  pick: -1,                         // the room picked on the plan
  tool: "select", placing: null, pointKind: "wander", zoneKind: "npc_block",
  layers: { paths: true, reach: false },
  undo: [], redo: [], history: [], timer: null, edits: 0, saving: false, error: "",
  cam: { x: 0, y: 0, s: 0.5 }, mouse: null, drag: null, clip: null, search: "", tab: "Tables",
};
const SNAP = { item: 8, room: 32 };
let app, canvas, ctx, reach = null;

export async function load() {
  app.textContent = "Loading…";
  try {
    const [view, cat, npcs] = await Promise.all([api("GET", "/api/plan"), api("GET", "/api/plan/catalogue"), api("GET", "/api/npcs")]);
    G.setCatalogue(cat);
    S.npcs = npcs.npcs.filter(n => n.look_id);
    take(view, true);
    await loadTables(api).catch(e => status("Tables are drawn plain: " + e.message, "warn"));
  } catch (e) {
    app.textContent = "Couldn't load the floor plan: " + e.message;
    return;
  }
  build();
  onImage(draw);
  loadHistory();
  status("Floor plan loaded.", "ok");
  window.__plan = S;   // (for browser checks)
  fitPlan();
  refresh();
}

// ---------------------------------------------------------------- the draft: edits, undo, saving
function take(view, whole) {
  S.meta = view;
  S.probs = view.problems;
  S.rev = view.draft.rev;
  if (whole) S.draft = view.draft;
}

/** Make a change: kept for undo, saved a moment later. */
function edit(fn, opts = {}) {
  if (!opts.noUndo) { S.undo.push(JSON.stringify(S.draft)); if (S.undo.length > 200) S.undo.shift(); S.redo = []; }
  fn();
  changed();
}

function changed() {
  S.edits++;
  reach = null;
  clearTimeout(S.timer);
  S.timer = setTimeout(() => { S.timer = null; save(); }, 700);
  refresh();
}

function undo(back = true) {
  const from = back ? S.undo : S.redo, to = back ? S.redo : S.undo;
  if (!from.length) return;
  to.push(JSON.stringify(S.draft));
  S.draft = JSON.parse(from.pop());
  S.sel = [];
  if (S.room >= S.draft.rooms.length) setMode("plan");
  changed();
}

async function save() {
  if (S.saving) { clearTimeout(S.timer); S.timer = setTimeout(save, 300); return; }
  S.saving = true;
  const sent = S.edits;
  refreshBar();
  try {
    const view = await api("PUT", "/api/plan/draft", { ...S.draft, base_rev: S.rev });
    take(view, false);
    if (S.edits === sent) S.draft = view.draft;   // nothing changed meanwhile: the server's copy, with its ids
    else adoptIds(view.draft);
    S.error = "";
  } catch (e) {
    S.error = e.message;
  }
  S.saving = false;
  reach = null;
  refresh();
}

/** The ids the server gave things saved while more edits came in (by place in the lists: nothing reorders them). */
function adoptIds(server) {
  S.draft.rooms.forEach((r, i) => {
    const sr = server.rooms[i];
    if (!sr) return;
    if (!r.id) r.id = sr.id;
    for (const k of ["items", "doors"]) r[k].forEach((x, j) => { if (!x.id && sr[k][j] && (k === "doors" || sr[k][j].asset === x.asset)) x.id = sr[k][j].id; });
  });
}

// ---------------------------------------------------------------- layout
function build() {
  app.textContent = "";
  canvas = el("canvas", { className: "pl-canvas", tabIndex: 0 });
  ctx = canvas.getContext("2d");
  top.replaceChildren(el("div", { className: "pl-bar", id: "pl-bar" }));
  app.append(
    el("div", { className: "wb pl-main" },
      el("div", { className: "panel" }, el("div", { className: "pb", id: "pl-side" })),
      el("div", { className: "stagebox pl-stage" }, canvas,
        el("div", { className: "float tl pl-tools", id: "pl-tools" }),
        el("details", { className: "pl-problems", id: "pl-problems", hidden: true })),
      el("div", { className: "panel" }, el("div", { className: "pb", id: "pl-insp" }))),
    el("div", { className: "pl-assets", id: "pl-assets", hidden: true }),
    el("style", { textContent: CSS }));
  new ResizeObserver(() => { if (!app.hidden) { sizeCanvas(); draw(); } }).observe(canvas.parentElement);
  canvas.addEventListener("pointerdown", down);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  canvas.addEventListener("wheel", wheel, { passive: false });
  canvas.addEventListener("dblclick", dbl);
  canvas.addEventListener("contextmenu", e => { e.preventDefault(); S.placing = null; S.tool = "select"; refresh(); });
  canvas.addEventListener("dragover", e => e.preventDefault());
  canvas.addEventListener("drop", e => {
    e.preventDefault();
    const t = e.dataTransfer.getData("text/plain");
    if (S.mode === "room" && t) { S.placing = JSON.parse(t); S.mouse = world(e); place(); }
  });
  document.addEventListener("keydown", key);
}

function sizeCanvas() {
  const r = canvas.parentElement.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  const w = Math.max(200, r.width), h = Math.max(200, r.height);
  canvas.style.width = w + "px"; canvas.style.height = h + "px";
  canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
}

function refresh() { refreshBar(); refreshSide(); refreshTools(); refreshInspector(); refreshProblems(); draw(); }

const room = () => S.draft.rooms[S.room];
const placed = () => S.draft.rooms.filter(r => r.placed);

function setMode(mode, roomIndex = S.room) {
  S.mode = mode;
  S.room = roomIndex;
  S.sel = [];
  S.placing = null;
  S.tool = "select";
  $(".pl-main").hidden = mode === "assets";
  $("#pl-assets").hidden = mode !== "assets";
  if (mode === "assets") {
    import("/admin-ui/plan/assets.js").then(m => m.open({ app: $("#pl-assets"), el, api, status, cat: G.CAT, changed: reloadCatalogue }));
  }
  if (mode === "room") fitRoom(); else fitPlan();
  refresh();
}

/** The library changed (an upload, an edit): what the palette offers and how things are drawn. */
async function reloadCatalogue() {
  G.setCatalogue(await api("GET", "/api/plan/catalogue"));
  return G.CAT;
}

// ---------------------------------------------------------------- the bar: views, saving, preview, publish
function refreshBar() {
  const bar = $("#pl-bar");
  if (!bar) return;
  const m = S.meta;
  const state = S.error ? ["warn", "Not saved: " + S.error] : S.saving ? ["", "Saving…"] : ["ok", "Draft saved"];
  const tab = (id, text) => el("button", { className: S.mode === id ? "on" : "", textContent: text, onclick: () => setMode(id, id === "room" ? Math.max(0, S.room) : S.room),
                                           disabled: id === "room" && S.room < 0 });
  const pending = (m.pending || []).length;
  const hist = el("select", { title: "Earlier publishes: put one back in the draft" }, el("option", { value: "", textContent: "History…" }),
    ...S.history.map(h => el("option", { value: h.id, textContent: `${h.id.slice(0, 13).replace(/(\d{4})(\d\d)(\d\d)-(\d\d)(\d\d)/, "$3/$2 $4:$5")}: ${h.rooms.join(", ") || "nothing"}` })));
  hist.onchange = async () => {
    if (!hist.value || !confirm("Put that floor back in the draft? (Publish it to use it.)")) { hist.value = ""; return; }
    take(await api("POST", "/api/plan/rollback/" + hist.value), true);
    S.undo = []; S.redo = []; setMode("plan");
  };
  bar.replaceChildren(
    el("div", { className: "seg" }, tab("plan", "Plan"), tab("room", S.room >= 0 && room() ? "Room: " + room().name : "Room"), tab("assets", "Assets")),
    el("span", { className: "sep" }),
    el("button", { className: "ghost sq", textContent: "↶", title: "Undo (Ctrl+Z)", disabled: !S.undo.length, onclick: () => undo(true) }),
    el("button", { className: "ghost sq", textContent: "↷", title: "Redo (Ctrl+Y)", disabled: !S.redo.length, onclick: () => undo(false) }),
    el("span", { className: "tag " + (state[0] || "caution"), textContent: state[1] }),
    el("span", { className: "pl-grow" }),
    el("button", { textContent: "Preview", title: "Walk round the draft in the game (a new tab)", onclick: preview }),
    hist,
    el("button", { className: "ghost", textContent: "Discard draft", disabled: !pending, onclick: discard }),
    el("button", { className: "primary", textContent: pending ? `Publish (${pending})` : "Published",
                   title: pending ? "Changed: " + m.pending.join(", ") + (m.restart ? ". Tables come or go: the casino restarts." : "") : "The floor is the draft",
                   disabled: !pending || !m.can_publish || S.saving || S.error !== "", onclick: publish }));
}

async function loadHistory() { S.history = await api("GET", "/api/plan/history").catch(() => []); refreshBar(); }

async function preview() {
  if (S.timer || S.saving) await save();
  const r = S.mode === "room" ? room() : S.draft.rooms[S.pick] || placed()[0];
  if (!r || !r.id) return status("Save the room first.", "warn");
  window.open("/?preview=" + encodeURIComponent(r.id), "casino-preview");
}

async function publish() {
  const m = S.meta;
  if (m.restart && !confirm("This adds or takes away tables or slot cabinets, so the casino restarts (everyone playing reconnects in a few seconds). Publish now?")) return;
  try {
    const r = await api("POST", "/api/plan/publish");
    take(r, true);
    status(r.message, "ok");
    loadHistory();
  } catch (e) { status(e.message, "warn"); }
  refresh();
}

async function discard() {
  if (!confirm("Throw the draft away and go back to the floor as it's live?")) return;
  take(await api("POST", "/api/plan/discard"), true);
  S.undo = []; S.redo = [];
  setMode("plan", -1);
}

// ---------------------------------------------------------------- the side: rooms (plan) or the palette (room)
function newRoom() {
  const all = placed(), x1 = all.length ? Math.max(...all.map(r => r.x + r.w)) : 0;
  edit(() => S.draft.rooms.push({ name: "Room " + (S.draft.rooms.length + 1), placed: false, x: x1 + 64, y: 0, w: 1024, h: 640,
    floor: { texture: "carpet", tint: "#ffffff" }, patches: [], walls: { style: "crimson", sign: "", sign_at: 512 }, doors: [], items: [],
    paths: { points: [], zones: [] } }));
  S.pick = S.draft.rooms.length - 1;
}

function duplicateRoom(i) {
  const r = JSON.parse(JSON.stringify(S.draft.rooms[i]));
  delete r.id;
  r.name += " copy"; r.placed = false;
  r.items.forEach(it => delete it.id);
  r.doors.forEach(d => delete d.id);
  edit(() => S.draft.rooms.push(r));
  S.pick = S.draft.rooms.length - 1;
}

function deleteRoom(i) {
  const r = S.draft.rooms[i], tables = r.items.filter(it => G.kindOf(it.asset) !== "piece" && G.kindOf(it.asset) !== "furniture").length;
  if (!confirm(`Delete ${r.name}${tables ? ` and its ${tables} tables and cabinets (their ids aren't used again)` : ""}?`)) return;
  edit(() => S.draft.rooms.splice(i, 1));
  S.pick = -1;
  if (S.room === i) setMode("plan", -1);
}

function togglePlaced(i) {
  const r = S.draft.rooms[i];
  edit(() => {
    r.placed = !r.placed;
    if (r.placed && placed().some(o => o !== r && G.overlap(G.outline(o), G.outline(r)))) {   // somewhere free, east of the rest
      const others = placed().filter(o => o !== r);
      r.x = Math.max(...others.map(o => o.x + o.w)) + 64;
      r.y = Math.min(...others.map(o => o.y));
    }
  });
  if (S.mode === "plan") { fitPlan(); draw(); }
}

function refreshSide() {
  const side = $("#pl-side");
  if (!side) return;
  if (S.mode === "plan") {
    const spawns = placed().flatMap(r => r.paths.points.filter(p => p.kind === "spawn").map(p => `${r.id}/${p.name}`));
    side.replaceChildren(
      el("h3", { textContent: "Rooms" }),
      el("ul", { className: "pl-rooms" }, ...S.draft.rooms.map((r, i) => el("li", { className: (i === S.pick ? "on " : "") + (r.placed ? "placed" : "") },
        el("button", { className: "pl-roomname", textContent: r.name, title: r.placed ? "On the floor" : "In the library", onclick: () => { S.pick = i; focusRoom(i); refresh(); },
                       ondblclick: () => setMode("room", i) }),
        el("span", { className: "hint", textContent: r.placed ? "on the floor" : "library" })))),
      el("button", { textContent: "New room", onclick: newRoom }),
      el("h3", { textContent: "Players appear at" }),
      el("select", { onchange: e => edit(() => { S.draft.spawn = e.target.value; }) },
        ...(spawns.length ? spawns : [""]).map(s => el("option", { value: s, textContent: s || "(no spawn point on the floor)", selected: s === S.draft.spawn }))),
      el("p", { className: "hint", textContent: "Drag a room to move it; doorways that meet show green. Double-click a room to edit it." }));
    return;
  }
  // the palette
  const entries = palette(), tabs = [...new Set(entries.map(e => e.cat))];
  if (!tabs.includes(S.tab)) S.tab = tabs[0];
  const q = S.search.toLowerCase(), shown = entries.filter(e => q ? e.name.toLowerCase().includes(q) : e.cat === S.tab);
  side.replaceChildren(
    el("input", { type: "search", placeholder: "Search pieces", value: S.search, oninput: e => { S.search = e.target.value; refreshSide(); $("#pl-side input").focus(); } }),
    el("div", { className: "pl-cats" }, ...tabs.map(t => el("button", { className: t === S.tab && !q ? "on" : "", textContent: t, onclick: () => { S.tab = t; S.search = ""; refreshSide(); } }))),
    el("div", { className: "pl-palette" }, ...shown.map(e => {
      const b = el("button", { className: S.placing && S.placing.key === e.key ? "on" : "", draggable: true, title: e.name + " (click, then click the floor; Esc to stop)",
        onclick: () => { S.placing = S.placing && S.placing.key === e.key ? null : e.tpl; S.tool = "select"; refresh(); } },
        e.icon ? el("img", { src: e.icon, alt: "" }) : el("span", { className: "pl-swatch", style: `background:${e.swatch || "#6b4a2e"}` }),
        el("span", { textContent: e.name }));
      b.addEventListener("dragstart", ev => ev.dataTransfer.setData("text/plain", JSON.stringify(e.tpl)));
      return b;
    })));
}

function palette() {
  const out = [];
  const add = (cat, name, tpl, extra = {}) => out.push({ cat, name, key: tpl.key = JSON.stringify([tpl.asset, tpl.props]), tpl, ...extra });
  for (const [g, c] of Object.entries(G.CAT.games)) add("Tables", c.name, { asset: "table:" + g, rot: 0, props: { label: c.name } }, { swatch: "#8f1d22" });
  for (const [v, name] of Object.entries(G.CAT.slots)) add("Slots", name, { asset: "slot", facing: "down", props: { variant: v } }, { swatch: "#ffb347" });
  for (const [k, p] of Object.entries(G.CAT.pieces)) if (k !== "npc") add(p.category || "Casino", p.name, { asset: k, facing: "down", props: {} });
  add("People", "Standing figure", { asset: "npc", facing: "down", props: { look: "dealer", name: "" } }, { swatch: "#1d1d22" });
  for (const n of S.npcs) add("People", `${n.name} (${n.role.replace("_", " ")})`, { asset: "npc", facing: "down", props: { look: n.look_id, name: n.name } });
  for (const [id, a] of Object.entries(G.CAT.assets)) add(a.category || "Furniture", a.name, { asset: "a:" + id, facing: "down", props: {} },
    { icon: ((a.facings || {}).down || {}).url });
  return out;
}

// ---------------------------------------------------------------- the tools strip above the canvas
function refreshTools() {
  const t = $("#pl-tools");
  if (!t) return;
  const layer = (k, text) => el("label", { className: "pl-check" }, el("input", { type: "checkbox", checked: S.layers[k], onchange: e => { S.layers[k] = e.target.checked; draw(); } }), text);
  const zoom = (f, text) => el("button", { textContent: text, onclick: () => { const c = center(); zoomAt(c, f); } });
  if (S.mode !== "room") {
    t.replaceChildren(zoom(1.25, "+"), zoom(0.8, "−"), el("button", { textContent: "Fit", onclick: () => { fitPlan(); draw(); } }), layer("reach", "Where NPCs can walk"));
    return;
  }
  const tool = (id, text, title) => el("button", { className: S.tool === id && !S.placing ? "on" : "", textContent: text, title, onclick: () => { S.tool = id; S.placing = null; refresh(); } });
  t.replaceChildren(...[
    tool("select", "Select", "Pick, move and box-select things (drag the walls to resize the room)"),
    tool("door", "Door", "Click a wall to put a door or archway in it"),
    tool("point", "Point", "Click the floor: a spawn, arrival or wander point"),
    tool("zone", "Zone", "Drag a no-go zone"),
    tool("patch", "Floor patch", "Drag a patch of different floor"),
    S.tool === "point" ? el("select", { onchange: e => { S.pointKind = e.target.value; } }, ...G.CAT.point_kinds.map(k => el("option", { value: k, textContent: k, selected: k === S.pointKind }))) : null,
    S.tool === "zone" ? el("select", { onchange: e => { S.zoneKind = e.target.value; } }, ...G.CAT.zone_kinds.map(k => el("option", { value: k, textContent: k === "npc_block" ? "NPCs keep out" : "Everyone keeps out", selected: k === S.zoneKind }))) : null,
    el("span", { className: "pl-grow" }),
    layer("paths", "Points & zones"), layer("reach", "Where NPCs can walk"),
    zoom(1.25, "+"), zoom(0.8, "−"), el("button", { textContent: "Fit", onclick: () => { fitRoom(); draw(); } })].filter(Boolean));
}

// ---------------------------------------------------------------- the inspector
function field(label, input) { return el("label", { className: "pl-field" }, el("span", { textContent: label }), input); }
function num(value, set, opts = {}) {
  return el("input", { type: "number", value, step: opts.step || 1, min: opts.min, max: opts.max, onchange: e => { const v = parseFloat(e.target.value); if (!isNaN(v)) edit(() => set(v)); } });
}
function text(value, set, max = 40) { return el("input", { value, maxLength: max, onchange: e => edit(() => set(e.target.value)) }); }
function choose(value, options, set) {
  return el("select", { onchange: e => edit(() => set(e.target.value)) }, ...options.map(([v, t]) => el("option", { value: v, textContent: t, selected: v === value })));
}
function colour(value, set) { return el("input", { type: "color", value, onchange: e => edit(() => set(e.target.value)) }); }

function refreshInspector() {
  const ins = $("#pl-insp");
  if (!ins || S.mode === "assets") return;
  const floors = Object.entries(G.CAT.floors).map(([k, f]) => [k, f.name]);
  if (S.mode === "plan") {
    const r = S.draft.rooms[S.pick];
    if (!r) { ins.replaceChildren(el("h3", { textContent: "The floor" }), el("p", { className: "hint", textContent: `${placed().length} rooms on the floor, ${S.draft.rooms.length - placed().length} in the library. Pick one to see it.` })); return; }
    ins.replaceChildren(el("h3", { textContent: r.name }),
      el("p", { className: "hint", textContent: `${r.w} × ${r.h}, ${r.items.length} things in it. ${r.placed ? `At ${r.x}, ${r.y} on the floor.` : "In the library (not on the floor)."}` }),
      el("div", { className: "pl-buttons" },
        el("button", { className: "primary", textContent: "Edit room", onclick: () => setMode("room", S.pick) }),
        el("button", { textContent: r.placed ? "Take off the floor" : "Place on the floor", onclick: () => togglePlaced(S.pick) }),
        el("button", { textContent: "Duplicate", onclick: () => duplicateRoom(S.pick) }),
        el("button", { className: "danger", textContent: "Delete", onclick: () => deleteRoom(S.pick) })));
    return;
  }
  const r = room();
  if (!r) return;
  if (!S.sel.length) {
    ins.replaceChildren(el("h3", { textContent: "This room" }),
      field("Name", text(r.name, v => { r.name = v || r.name; })),
      field("Width", num(r.w, v => resize(r, "right", r.x + v), { step: 32, min: 320 })),
      field("Height", num(r.h, v => resize(r, "bottom", r.y + v), { step: 32, min: 240 })),
      field("Floor", choose(r.floor.texture, floors, v => { r.floor.texture = v; })),
      field("Floor tint", colour(r.floor.tint, v => { r.floor.tint = v; })),
      field("Walls", choose(r.walls.style, Object.entries(G.CAT.walls.styles).map(([k, s]) => [k, s.name]), v => { r.walls.style = v; })),
      field("Sign", text(r.walls.sign, v => { r.walls.sign = v.toUpperCase(); }, 24)),
      field("Sign at", num(r.walls.sign_at, v => { r.walls.sign_at = v; })),
      el("label", { className: "pl-check" }, el("input", { type: "checkbox", checked: r.placed, onchange: () => togglePlaced(S.room) }), "On the floor"),
      el("p", { className: "hint", textContent: "Drag a wall to resize the room. Click a piece in the palette (or drag it) to put it down; R turns it, Esc stops." }));
    return;
  }
  if (S.sel.length > 1) {
    ins.replaceChildren(el("h3", { textContent: `${S.sel.length} picked` }),
      el("p", { className: "hint", textContent: "Drag to move them together; arrows nudge; Ctrl+C / Ctrl+V; R turns each." }),
      el("button", { className: "danger", textContent: "Delete them", onclick: removeSelected }));
    return;
  }
  const { t, i } = S.sel[0];
  const head = (h, sub) => [el("h3", { textContent: h }), sub ? el("p", { className: "hint", textContent: sub }) : null];
  const del = el("button", { className: "danger", textContent: "Delete", onclick: removeSelected });
  if (t === "item") {
    const it = r.items[i], kind = G.kindOf(it.asset), rows = [];
    rows.push(field("Across", num(it.x, v => { it.x = v; })), field("Down", num(it.y, v => { it.y = v; })));
    if (kind === "table") {
      const rots = G.CAT.games[it.asset.slice(6)].rotations;
      rows.push(field("Name", text(it.props.label, v => { it.props.label = v; }, 32)));
      if (rots.length > 1) rows.push(field("Turned", choose(String(it.rot || 0), rots.map(d => [String(d), d ? `${d}°` : "Upright"]), v => { it.rot = +v; })));
    } else {
      rows.push(field("Facing", choose(it.facing || "down", G.CAT.facings.map(f => [f, f]), v => { it.facing = v; })));
    }
    if (kind === "slot") rows.push(field("Slot", choose(it.props.variant, Object.entries(G.CAT.slots), v => { it.props.variant = v; })));
    if (it.asset === "npc") {
      rows.push(field("Who", choose(it.props.look, [["dealer", "A dealer"], ...S.npcs.map(n => [n.look_id, n.name])], v => {
        it.props.look = v; const n = S.npcs.find(n => n.look_id === v); if (n && !it.props.name) it.props.name = n.name; })));
      rows.push(field("Name", text(it.props.name, v => { it.props.name = v; }, 24)));
    }
    ins.replaceChildren(...head(G.label(it), it.id ? `id ${it.id}` : "new: saved in a moment"), ...rows, del);
  } else if (t === "point") {
    const p = r.paths.points[i];
    ins.replaceChildren(...head("Point " + p.name, { spawn: "Players appear here.", arrival: "NPCs come in (and leave) here.", wander: "NPCs wander here between games." }[p.kind]),
      field("Name", text(p.name, v => { p.name = v; }, 24)),
      field("Kind", choose(p.kind, G.CAT.point_kinds.map(k => [k, k]), v => { p.kind = v; })),
      field("Weight", num(p.weight, v => { p.weight = v; }, { min: 0, max: 100, step: 0.5 })),
      field("Linger (s)", num(p.linger, v => { p.linger = v; }, { min: 0, max: 600 })),
      field("Across", num(p.x, v => { p.x = v; })), field("Down", num(p.y, v => { p.y = v; })), del);
  } else if (t === "zone") {
    const z = r.paths.zones[i];
    ins.replaceChildren(...head("No-go zone"),
      field("Keeps out", choose(z.kind, [["npc_block", "NPCs (players walk through)"], ["block", "Everyone"]], v => { z.kind = v; })),
      field("Across", num(z.x, v => { z.x = v; })), field("Down", num(z.y, v => { z.y = v; })),
      field("Width", num(z.w, v => { z.w = v; })), field("Height", num(z.h, v => { z.h = v; })), del);
  } else if (t === "door") {
    const d = r.doors[i];
    ins.replaceChildren(...head(d.kind === "door" ? "Door" : "Archway", `In the ${d.side} wall. It joins the room whose wall meets it there; with none, it stays shut.`),
      field("Kind", choose(d.kind, [["door", "Door (shut till someone's by)"], ["archway", "Archway (open)"]], v => { d.kind = v; })),
      field("Width", num(d.width, v => { d.width = v; }, { min: 40, max: 600, step: 8 })),
      field("Along", num(d.at, v => { d.at = v; })), del);
  } else if (t === "patch") {
    const p = r.patches[i];
    ins.replaceChildren(...head("Floor patch"),
      field("Floor", choose(p.texture, floors, v => { p.texture = v; })), field("Tint", colour(p.tint, v => { p.tint = v; })),
      field("Across", num(p.x, v => { p.x = v; })), field("Down", num(p.y, v => { p.y = v; })),
      field("Width", num(p.w, v => { p.w = v; })), field("Height", num(p.h, v => { p.h = v; })), del);
  }
}

function refreshProblems() {
  const box = $("#pl-problems");
  if (!box) return;
  if (S.mode === "assets") { box.hidden = true; return; }
  const list = S.probs.filter(p => p.placed || (S.mode === "room" && room() && p.room === room().id));
  box.hidden = !list.length;
  const what = list.some(p => p.placed) ? "keep the draft from publishing" : "in this blueprint";
  box.replaceChildren(el("summary", { textContent: `⚠ ${list.length} problem${list.length > 1 ? "s" : ""} ${what}` }),
    el("ul", {}, ...list.map(p => el("li", {}, el("button", { className: "link", textContent: p.message, onclick: () => goTo(p) })))));
}

function goTo(p) {
  const ri = S.draft.rooms.findIndex(r => r.id === p.room);
  if (ri < 0) return;
  setMode("room", ri);
  const r = room();
  if (p.item && p.item.startsWith("point:")) S.sel = [{ t: "point", i: r.paths.points.findIndex(x => x.name === p.item.slice(6)) }];
  else if (p.item) {
    const i = r.items.findIndex(x => x.id === p.item), d = r.doors.findIndex(x => x.id === p.item);
    S.sel = i >= 0 ? [{ t: "item", i }] : d >= 0 ? [{ t: "door", i: d }] : [];
  }
  refresh();
}

// ---------------------------------------------------------------- the view: camera and drawing
function center() { return { x: canvas.clientWidth / 2, y: canvas.clientHeight / 2 }; }
function world(e) {
  const b = canvas.getBoundingClientRect();
  return [(e.clientX - b.left) / S.cam.s + S.cam.x, (e.clientY - b.top) / S.cam.s + S.cam.y];
}
function fit(box) {
  if (!canvas) return;
  sizeCanvas();
  const w = canvas.clientWidth, h = canvas.clientHeight, pad = 40;
  S.cam.s = Math.min((w - pad) / box[2], (h - pad) / box[3], 2);
  S.cam.x = box[0] - (w / S.cam.s - box[2]) / 2;
  S.cam.y = box[1] - (h / S.cam.s - box[3]) / 2;
}
function fitPlan() {
  const rs = placed().length ? placed() : S.draft.rooms;
  if (!rs.length) return fit([0, 0, 1024, 640]);
  const x0 = Math.min(...rs.map(r => r.x)), y0 = Math.min(...rs.map(r => r.y));
  fit([x0, y0, Math.max(...rs.map(r => r.x + r.w)) - x0, Math.max(...rs.map(r => r.y + r.h)) - y0]);
}
function fitRoom() { const r = room(); if (r) fit([r.x - 20, r.y - 20, r.w + 40, r.h + 40]); }
function focusRoom(i) { const r = S.draft.rooms[i]; if (r && !r.placed) fit([r.x - 20, r.y - 20, r.w + 40, r.h + 40]); }
function zoomAt(p, f) {
  const wx = p.x / S.cam.s + S.cam.x, wy = p.y / S.cam.s + S.cam.y;
  S.cam.s = Math.max(0.05, Math.min(6, S.cam.s * f));
  S.cam.x = wx - p.x / S.cam.s; S.cam.y = wy - p.y / S.cam.s;
  draw();
}

function shownRooms() {
  if (S.mode === "room") {
    const r = room();
    if (!r) return [];
    return r.placed ? placed() : [r];
  }
  const rs = placed().slice();
  const p = S.draft.rooms[S.pick];
  if (p && !p.placed) rs.push(p);   // a library room picked: shown where it would go
  return rs;
}

function draw() {
  if (!canvas || !S.draft) return;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = "#0d1514"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.setTransform(S.cam.s * dpr, 0, 0, S.cam.s * dpr, -S.cam.x * S.cam.s * dpr, -S.cam.y * S.cam.s * dpr);
  const rooms = shownRooms(), { ops, problems } = G.openings(rooms.filter(r => r.placed));
  const cur = S.mode === "room" ? room() : null;
  if (S.mode === "room" && cur) grid(cur);
  for (const r of rooms) drawRoom(ctx, r, ops[r.id] || (r.placed ? [] : G.openings([r]).ops[r.id]), { dim: S.mode === "room" && r !== cur });
  if (S.layers.reach) { reach = reach || G.npcReach(placed()); drawReach(ctx, reach); }
  for (const r of rooms) {
    const bad = r === cur ? new Set(G.roomProblems(r).map(p => p.i)) : new Set();
    const order = r.items.map((it, i) => [i, it]).sort((a, b) => (a[1].y - b[1].y));
    for (const [i, it] of order) drawItem(ctx, r, it, { picked: r === cur && S.sel.some(s => s.t === "item" && s.i === i), bad: bad.has(i) });
    if (r === cur && S.layers.paths) drawPaths(ctx, r, { point: pickedIndex("point"), zone: pickedIndex("zone") });
  }
  if (cur) {
    S.sel.filter(s => s.t === "door").forEach(s => { const d = cur.doors[s.i]; if (d) outlineRect(G.gap(cur, d), "#ffd36b"); });
    S.sel.filter(s => s.t === "patch").forEach(s => { const p = cur.patches[s.i]; if (p) outlineRect([cur.x + p.x, cur.y + p.y, p.w, p.h], "#ffd36b"); });
    if (S.placing && S.mouse && G.inside(S.mouse, G.outline(cur))) drawItem(ctx, cur, ghost(), { ghost: true });
  }
  // the plan: doorways that meet, rooms' names, the one picked
  if (S.mode === "plan") {
    for (const r of rooms) {
      for (const o of ops[r.id] || []) if (o.to && o.owner === r.id) { const g = G.gap(r, o); ctx.fillStyle = "rgba(90,255,140,.8)"; ctx.fillRect(g[0] - 4, g[1] - 4, g[2] + 8, g[3] + 8); }
      ctx.fillStyle = "rgba(0,0,0,.55)"; ctx.font = `bold ${Math.round(16 / S.cam.s)}px sans-serif`; ctx.textAlign = "left"; ctx.textBaseline = "top";
      const tw = ctx.measureText(r.name).width;
      ctx.fillRect(r.x + 10 / S.cam.s, r.y + 80, tw + 12 / S.cam.s, 22 / S.cam.s);
      ctx.fillStyle = "#ffe9b0"; ctx.fillText(r.name, r.x + 16 / S.cam.s, r.y + 80 + 3 / S.cam.s);
      if (S.draft.rooms[S.pick] === r) outlineRect(G.outline(r), "#ffd36b", 4);
      if (!r.placed) outlineRect(G.outline(r), "#9ad", 3, [12, 8]);
    }
    for (const p of problems) { const r = S.draft.rooms.find(x => x.id === p.room), d = r && r.doors.find(x => x.id === p.item); if (d) outlineRect(G.gap(r, d), "#ff5a48", 4); }
  }
  if (S.drag && S.drag.box) {
    const [a, b] = S.drag.box;
    outlineRect([Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])], "#ffd36b", 1.5, [4, 3]);
  }
}

function outlineRect(r, colour, width = 2, dash = []) {
  ctx.save(); ctx.strokeStyle = colour; ctx.lineWidth = width / S.cam.s; ctx.setLineDash(dash.map(d => d / S.cam.s)); ctx.strokeRect(...r); ctx.restore();
}

function grid(r) {
  if (S.cam.s < 0.35) return;
  ctx.save();
  ctx.strokeStyle = "rgba(255,255,255,.05)"; ctx.lineWidth = 1 / S.cam.s;
  for (let x = r.x; x <= r.x + r.w; x += 32) { ctx.beginPath(); ctx.moveTo(x, r.y - 200); ctx.lineTo(x, r.y + r.h + 200); ctx.stroke(); }
  for (let y = r.y; y <= r.y + r.h; y += 32) { ctx.beginPath(); ctx.moveTo(r.x - 200, y); ctx.lineTo(r.x + r.w + 200, y); ctx.stroke(); }
  ctx.restore();
}

const pickedIndex = t => (S.sel.length === 1 && S.sel[0].t === t) ? S.sel[0].i : -1;

// ---------------------------------------------------------------- placing things
const snap = (v, step, free) => free ? Math.round(v * 2) / 2 : Math.round(v / step) * step;

function ghost() {
  const r = room(), t = S.placing;
  return { ...JSON.parse(JSON.stringify(t)), key: undefined, x: snap(S.mouse[0] - r.x, SNAP.item, S.free), y: snap(S.mouse[1] - r.y, SNAP.item, S.free) };
}

function place() {
  const r = room();
  if (!r || !S.mouse) return;
  const it = ghost();
  delete it.key;
  edit(() => r.items.push(it));
  S.sel = [{ t: "item", i: r.items.length - 1 }];
  refresh();
}

function turn(it) {
  if (G.kindOf(it.asset) === "table") {
    const rots = G.CAT.games[it.asset.slice(6)].rotations;
    it.rot = rots[(rots.indexOf(it.rot || 0) + 1) % rots.length];
  } else {   // (a library piece turns only to the facings it has pictures for)
    const p = G.piece(it.asset), order = ["down", "left", "up", "right"].filter(f => !p || !p.facings || p.facings[f]);
    it.facing = order[(order.indexOf(it.facing || "down") + 1) % order.length];
  }
}

function removeSelected() {
  const r = room();
  if (!r || !S.sel.length) return;
  edit(() => {
    const lists = { item: r.items, point: r.paths.points, zone: r.paths.zones, door: r.doors, patch: r.patches };
    for (const s of S.sel.slice().sort((a, b) => b.i - a.i)) lists[s.t].splice(s.i, 1);
  });
  S.sel = [];
  refresh();
}

/** Resize a room by moving one wall to `to` (plan coordinates): what's inside stays where it is on the plan. */
function resize(r, side, to) {
  to = Math.round(to);
  if (side === "right") r.w = Math.max(320, to - r.x);
  else if (side === "bottom") r.h = Math.max(240, to - r.y);
  else {
    const d = side === "left" ? Math.min(to - r.x, r.w - 320) : Math.min(to - r.y, r.h - 240);
    if (!d) return;
    const shift = o => { if (side === "left") o.x -= d; else o.y -= d; };
    if (side === "left") { r.x += d; r.w -= d; r.walls.sign_at -= d; } else { r.y += d; r.h -= d; }
    r.items.forEach(shift); r.paths.points.forEach(shift); r.paths.zones.forEach(shift); r.patches.forEach(shift);
    r.doors.forEach(o => { if ((side === "left") === (o.side === "top" || o.side === "bottom")) o.at -= d; });
  }
}

// ---------------------------------------------------------------- pointer
function hitRoomEdge(r, p) {
  const tol = 8 / S.cam.s, [x, y] = p;
  const inX = x > r.x - tol && x < r.x + r.w + tol, inY = y > r.y - tol && y < r.y + r.h + tol;
  if (inY && Math.abs(x - (r.x + r.w)) < tol) return "right";
  if (inY && Math.abs(x - r.x) < tol) return "left";
  if (inX && Math.abs(y - (r.y + r.h)) < tol) return "bottom";
  if (inX && Math.abs(y - r.y) < tol) return "top";
  return null;
}

function hit(p) {
  const r = room();
  if (!r) return null;
  for (let i = r.doors.length - 1; i >= 0; i--) if (G.inside(p, G.grow(G.gap(r, r.doors[i]), 6 / S.cam.s))) return { t: "door", i };
  if (S.layers.paths) {
    for (let i = r.paths.points.length - 1; i >= 0; i--) { const q = r.paths.points[i]; if (Math.hypot(p[0] - r.x - q.x, p[1] - r.y - q.y) < 14) return { t: "point", i }; }
  }
  const order = r.items.map((it, i) => [i, it]).sort((a, b) => b[1].y - a[1].y);
  for (const [i, it] of order) { const s = G.shapes(r, it); if (s && G.inside(p, s.rect)) return { t: "item", i }; }
  if (S.layers.paths) for (let i = r.paths.zones.length - 1; i >= 0; i--) { const z = r.paths.zones[i]; if (G.inside(p, [r.x + z.x, r.y + z.y, z.w, z.h])) return { t: "zone", i }; }
  for (let i = r.patches.length - 1; i >= 0; i--) { const q = r.patches[i]; if (G.inside(p, [r.x + q.x, r.y + q.y, q.w, q.h])) return { t: "patch", i }; }
  return null;
}

function objOf(r, s) { return { item: r.items, point: r.paths.points, zone: r.paths.zones, door: r.doors, patch: r.patches }[s.t][s.i]; }

function down(e) {
  canvas.focus();
  canvas.setPointerCapture(e.pointerId);
  const p = world(e);
  S.mouse = p; S.free = e.shiftKey;
  if (e.button === 1 || e.button === 2 || S.space) { S.drag = { pan: [e.clientX, e.clientY, S.cam.x, S.cam.y] }; return; }
  if (S.mode === "plan") {
    const rs = shownRooms().slice().reverse(), i = rs.findIndex(r => G.inside(p, G.outline(r)));
    if (i < 0) { S.pick = -1; S.drag = { pan: [e.clientX, e.clientY, S.cam.x, S.cam.y] }; refresh(); return; }
    const r = rs[i];
    S.pick = S.draft.rooms.indexOf(r);
    S.drag = { room: r, from: p, at: [r.x, r.y], snap: JSON.stringify(S.draft) };
    refresh();
    return;
  }
  const r = room();
  if (!r) return;
  if (S.placing) { place(); return; }
  if (S.tool === "door") {
    const side = hitRoomEdge(r, p) || nearestWall(r, p);
    if (side) {
      const along = side === "top" || side === "bottom" ? p[0] - r.x : p[1] - r.y;
      edit(() => r.doors.push({ side, at: snap(along, SNAP.item), width: 64, kind: "door" }));
      S.sel = [{ t: "door", i: r.doors.length - 1 }]; S.tool = "select"; refresh();
    }
    return;
  }
  if (S.tool === "point") {
    const kinds = r.paths.points.filter(q => q.kind === S.pointKind).length;
    edit(() => r.paths.points.push({ name: S.pointKind + (kinds ? "_" + (kinds + 1) : ""), x: snap(p[0] - r.x, SNAP.item), y: snap(p[1] - r.y, SNAP.item), kind: S.pointKind, weight: 1, linger: 0 }));
    S.sel = [{ t: "point", i: r.paths.points.length - 1 }]; refresh();
    return;
  }
  if (S.tool === "zone" || S.tool === "patch") { S.drag = { make: S.tool, from: p, box: [p, p] }; return; }
  const edge = !hit(p) && hitRoomEdge(r, p);
  if (edge) { S.drag = { edge, snap: JSON.stringify(S.draft) }; return; }
  const h = hit(p);
  if (!h) { if (!e.shiftKey) S.sel = []; S.drag = { box: [p, p] }; refresh(); return; }
  const already = S.sel.some(s => s.t === h.t && s.i === h.i);
  if (e.shiftKey) S.sel = already ? S.sel.filter(s => !(s.t === h.t && s.i === h.i)) : [...S.sel, h];
  else if (!already) S.sel = [h];
  S.drag = { move: S.sel.map(s => [s, { ...objOf(r, s) }]), from: p, snap: JSON.stringify(S.draft) };
  refresh();
}

function nearestWall(r, p) {
  const d = { top: Math.abs(p[1] - r.y - G.CAT.walls.top / 2), bottom: Math.abs(p[1] - r.y - r.h), left: Math.abs(p[0] - r.x), right: Math.abs(p[0] - r.x - r.w) };
  const best = Object.entries(d).sort((a, b) => a[1] - b[1])[0];
  return best[1] < 60 ? best[0] : null;
}

function move(e) {
  const p = world(e);
  S.mouse = p; S.free = e.shiftKey;
  const d = S.drag;
  if (!d) {
    if (S.mode === "room" && room() && !S.placing) canvas.style.cursor = (S.tool === "select" && !hit(p) && hitRoomEdge(room(), p)) ? "move" : S.tool === "select" ? "default" : "crosshair";
    if (S.placing) draw();
    return;
  }
  if (d.pan) { S.cam.x = d.pan[2] - (e.clientX - d.pan[0]) / S.cam.s; S.cam.y = d.pan[3] - (e.clientY - d.pan[1]) / S.cam.s; draw(); return; }
  if (d.box) { d.box[1] = p; draw(); return; }
  const r = room();
  if (d.edge) { resize(r, d.edge, snap(d.edge === "left" || d.edge === "right" ? p[0] : p[1], SNAP.room, e.shiftKey)); d.moved = true; draw(); refreshInspector(); return; }
  const dx = p[0] - d.from[0], dy = p[1] - d.from[1];
  if (d.room) {
    d.room.x = snap(d.at[0] + dx, SNAP.room, e.shiftKey); d.room.y = snap(d.at[1] + dy, SNAP.room, e.shiftKey);
    d.moved = true; draw(); return;
  }
  if (d.move) {
    for (const [s, was] of d.move) {
      const o = objOf(r, s);
      if (s.t === "door") {
        const along = o.side === "top" || o.side === "bottom" ? dx : dy;
        o.at = snap(was.at + along, SNAP.item, e.shiftKey);
      } else { o.x = snap(was.x + dx, SNAP.item, e.shiftKey); o.y = snap(was.y + dy, SNAP.item, e.shiftKey); }
    }
    d.moved = true; draw();
  }
}

function up(e) {
  const d = S.drag;
  S.drag = null;
  if (!d) return;
  const r = room();
  if (d.make) {
    const [a, b] = d.box, x = Math.min(a[0], b[0]) - r.x, y = Math.min(a[1], b[1]) - r.y, w = Math.abs(b[0] - a[0]), h = Math.abs(b[1] - a[1]);
    if (w > 4 && h > 4) {
      const box = { x: snap(x, SNAP.item), y: snap(y, SNAP.item), w: Math.max(8, snap(w, SNAP.item)), h: Math.max(8, snap(h, SNAP.item)) };
      if (d.make === "zone") { edit(() => r.paths.zones.push({ ...box, kind: S.zoneKind })); S.sel = [{ t: "zone", i: r.paths.zones.length - 1 }]; }
      else { edit(() => r.patches.push({ ...box, texture: "plain", tint: "#3b2a20" })); S.sel = [{ t: "patch", i: r.patches.length - 1 }]; }
    }
    S.tool = "select";
    refresh();
    return;
  }
  if (d.box && r) {
    const [a, b] = d.box, box = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])];
    if (box[2] > 3 && box[3] > 3) {
      r.items.forEach((it, i) => { const s = G.shapes(r, it); if (s && G.overlap(s.rect, box) && !S.sel.some(x => x.t === "item" && x.i === i)) S.sel.push({ t: "item", i }); });
    }
    refresh();
    return;
  }
  if (d.moved && d.snap) {   // (one undo step for the whole drag)
    S.undo.push(d.snap); S.redo = [];
    changed();
  }
}

function dbl(e) {
  if (S.mode !== "plan") return;
  const p = world(e), r = shownRooms().slice().reverse().find(r => G.inside(p, G.outline(r)));
  if (r) setMode("room", S.draft.rooms.indexOf(r));
}

function wheel(e) {
  e.preventDefault();
  const b = canvas.getBoundingClientRect();
  zoomAt({ x: e.clientX - b.left, y: e.clientY - b.top }, e.deltaY < 0 ? 1.15 : 1 / 1.15);
}

// ---------------------------------------------------------------- keys
function key(e) {
  if (!app || app.hidden) return;
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) return;
  const ctrl = e.ctrlKey || e.metaKey, r = room();
  if (e.key === " ") { S.space = e.type === "keydown"; }
  if (ctrl && e.key.toLowerCase() === "z") { e.preventDefault(); undo(!e.shiftKey); return; }
  if (ctrl && e.key.toLowerCase() === "y") { e.preventDefault(); undo(false); return; }
  if (S.mode !== "room" || !r) return;
  if (e.key === "Escape") { S.placing = null; S.tool = "select"; S.sel = []; refresh(); return; }
  if (e.key === "r" || e.key === "R") {
    e.preventDefault();
    if (S.placing) { turn(S.placing); draw(); return; }
    const items = S.sel.filter(s => s.t === "item");
    if (items.length) edit(() => items.forEach(s => turn(r.items[s.i])));
    return;
  }
  if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); removeSelected(); return; }
  if (ctrl && (e.key.toLowerCase() === "c" || e.key.toLowerCase() === "d")) {
    e.preventDefault();
    S.clip = S.sel.filter(s => s.t === "item").map(s => { const it = JSON.parse(JSON.stringify(r.items[s.i])); delete it.id; return it; });
    if (e.key.toLowerCase() === "c") { status(`Copied ${S.clip.length}.`, "ok"); return; }
  }
  if (ctrl && (e.key.toLowerCase() === "v" || e.key.toLowerCase() === "d") && S.clip && S.clip.length) {
    e.preventDefault();
    const off = e.key.toLowerCase() === "d" ? 32 : 0, mx = S.mouse && !off ? S.mouse[0] - r.x : null, my = S.mouse && !off ? S.mouse[1] - r.y : null;
    const cx = S.clip.reduce((a, it) => a + it.x, 0) / S.clip.length, cy = S.clip.reduce((a, it) => a + it.y, 0) / S.clip.length;
    edit(() => {
      const start = r.items.length;
      S.clip.forEach(it => r.items.push({ ...JSON.parse(JSON.stringify(it)),
        x: snap(mx === null ? it.x + off : it.x - cx + mx, SNAP.item), y: snap(my === null ? it.y + off : it.y - cy + my, SNAP.item) }));
      S.sel = S.clip.map((_, k) => ({ t: "item", i: start + k }));
    });
    return;
  }
  const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
  if (arrows && S.sel.length) {
    e.preventDefault();
    const step = e.shiftKey ? 1 : SNAP.item;
    edit(() => S.sel.forEach(s => {
      const o = objOf(r, s);
      if (s.t === "door") o.at += (o.side === "top" || o.side === "bottom" ? arrows[0] : arrows[1]) * step;
      else { o.x += arrows[0] * step; o.y += arrows[1] * step; }
    }));
  }
}
document.addEventListener("keyup", e => { if (e.key === " ") S.space = false; });

const CSS = `
  .pl-bar { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
  .pl-grow { flex: 1 1 0; }
  .pl-main { grid-template-columns: 250px minmax(0, 1fr) 310px; }
  #pl-side, #pl-insp { padding: var(--pad); display: grid; gap: 8px; align-content: start; }
  #pl-side h3, #pl-insp h3 { margin: 6px 0 0; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .1em; color: var(--fg-muted); }
  #pl-side h3:first-child, #pl-insp h3:first-child { margin-top: 0; }
  #pl-insp h3:first-child { font-size: var(--fs-h); text-transform: none; letter-spacing: 0; color: var(--fg); }
  .pl-stage { place-items: stretch; }
  .pl-canvas { display: block; touch-action: none; user-select: none; outline: none; max-width: none !important; max-height: none !important; }
  .pl-tools { flex-wrap: wrap; max-width: calc(100% - 20px); }
  .pl-tools button { height: 26px; }
  .pl-tools button.on { background: var(--accent-soft); border-color: var(--accent-line); color: var(--accent-strong); }
  .pl-check { display: inline-flex; gap: 5px; align-items: center; font-size: var(--fs-s); color: var(--fg-muted); padding: 0 4px; }
  .pl-rooms { list-style: none; margin: 0; padding: 0; display: grid; gap: 1px; }
  .pl-rooms li { display: flex; align-items: center; gap: 6px; padding: 0 6px; border-radius: var(--radius); }
  .pl-rooms li:hover { background: var(--bg-2); }
  .pl-rooms li.on { background: var(--accent-soft); box-shadow: inset 2px 0 0 var(--accent); }
  .pl-roomname { flex: 1; justify-content: flex-start; height: 28px; border: 0; background: none; padding: 0 2px; font-weight: 600; }
  .pl-roomname:hover { background: none; }
  .pl-rooms li:not(.placed) .pl-roomname { font-weight: 400; color: var(--fg-muted); }
  .pl-cats { display: flex; flex-wrap: wrap; gap: 4px; }
  .pl-cats button { height: 24px; padding: 0 8px; }
  .pl-cats button.on, .pl-palette button.on { background: var(--accent-soft); border-color: var(--accent-line); color: var(--accent-strong); }
  .pl-palette { display: grid; gap: 2px; }
  .pl-palette button { justify-content: flex-start; height: 36px; padding: 0 6px; gap: 8px; text-align: left; border-color: transparent; background: none; }
  .pl-palette button:hover { background: var(--bg-2); }
  .pl-palette img { width: 30px; height: 30px; object-fit: contain; image-rendering: pixelated; }
  .pl-swatch { width: 18px; height: 18px; border-radius: 4px; flex: none; }
  .pl-field { display: grid; grid-template-columns: 86px minmax(0, 1fr); gap: 6px; align-items: center; font-size: var(--fs-s); color: var(--fg-muted); }
  .pl-field input, .pl-field select { width: 100%; min-width: 0; }
  .pl-buttons { display: flex; flex-wrap: wrap; gap: 6px; }
  .pl-problems { position: absolute; left: 10px; right: 10px; bottom: 10px; z-index: 2; border: 1px solid color-mix(in srgb, var(--caution) 45%, var(--line)); border-radius: 8px;
    background: color-mix(in srgb, var(--bg-1) 92%, transparent); backdrop-filter: blur(6px); font-size: var(--fs-s); max-height: 40%; overflow: auto; }
  .pl-problems summary { padding: 6px 10px; color: var(--caution); }
  .pl-problems ul { margin: 0; padding: 0 10px 10px 28px; display: grid; gap: 3px; }
  .pl-problems button.link { color: var(--fg-muted); text-align: left; white-space: normal; }
  .pl-assets { height: 100%; }
  .pl-asset-main { height: 100%; display: grid; grid-template-columns: minmax(0, 1fr) 400px; }
  .pl-asset-main > .panel { display: block; overflow: auto; padding: var(--pad); }
  .pl-asset-main > .panel + .panel { border-left: 1px solid var(--line); }
  .pl-asset-list .pl-bar { margin-bottom: 8px; }
  .pl-asset-list h3 { margin: 14px 0 6px; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .1em; color: var(--fg-muted); }
  .pl-asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 6px; }
  .pl-asset { display: grid; justify-items: center; gap: 2px; height: auto; padding: 5px 4px; font-size: var(--fs-xs); text-align: center; white-space: normal; }
  .pl-asset img { width: 64px; height: 64px; object-fit: contain; image-rendering: pixelated; background: var(--stage); border-radius: 4px; }
  .pl-asset small { color: var(--accent-strong); font-size: 10px; }
  .pl-asset.on { border-color: var(--accent); background: var(--accent-soft); }
  .pl-asset-detail { display: grid !important; gap: 8px; align-content: start; }
  .pl-asset-edit { display: grid; gap: 8px; } .pl-asset-edit h3, .pl-asset-edit h4 { margin: 0; }
  .pl-stage-pic { max-width: 100%; border-radius: 8px; touch-action: none; cursor: crosshair; }
  .pl-facings { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
  .pl-facing { display: grid; gap: 3px; justify-items: start; font-size: var(--fs-xs); }
  .pl-facing img { height: 48px; image-rendering: pixelated; background: var(--stage); border-radius: 4px; }
  .pl-floor-preview { height: 160px; border-radius: 8px; background-repeat: repeat; image-rendering: pixelated; }
`;
