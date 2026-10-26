// The Floor plan section (plan.py): the casino's rooms on one plan, and each room's blueprint.
//
//   Plan     every room on the floor, drawn to scale: drag them into place (doorways that meet light green), pick
//            which spawn point players appear at; the library of blueprints down the side (new, duplicate, place on
//            the floor or take off it, delete).
//   Room     one blueprint close up on a grid: drag things in from the palette (tables, slots, pieces, people,
//            furniture), move, turn (R), duplicate (Ctrl+D), copy and paste, group (Ctrl+G: clicking any of them
//            picks them all, Ctrl+click one on its own), delete; drag the walls to resize the room; doors and
//            archways, floor patches, the NPCs' points and no-go zones; the inspector for whatever's picked.
//            Layers: clicks pick what's drawn on top; Alt+click picks the next thing down, right-click lists all
//            that's there. Floor patches, rugs and wall pieces stack in their lists' order (Ctrl+] / Ctrl+[, the
//            Layers list down the side); standing things go by depth, as the game draws them. Lock keeps the canvas
//            from picking a thing; Hide takes it out of the view while you work (not saved).
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

let $, el, api, status, top, remember;
export function init(h) {
  ({ el, api, status, top, remember } = h);
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
  layers: { paths: true, reach: false, grid: savedGrid() },
  undo: [], redo: [], history: [], timer: null, edits: 0, saving: false, error: "",
  cam: { x: 0, y: 0, s: 0.5 }, mouse: null, drag: null, clip: null, search: "", tab: "Tables",
  hover: null,                      // {t, i}: what a click would pick, or a row pointed at in Layers or the menu
  side: savedSide(),                // the room's side panel: "pieces" (the palette) or "layers"
};
const SNAP = { item: 8, room: 32 };
function savedGrid() { try { return localStorage.getItem("plan.grid") === "1"; } catch { return false; } }
function savedSide() { try { return localStorage.getItem("plan.side") === "layers" ? "layers" : "pieces"; } catch { return "pieces"; } }
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
    const body = JSON.parse(JSON.stringify(S.draft, (k, v) => k === "_hidden" ? undefined : v));   // (hiding is the page's)
    const view = await api("PUT", "/api/plan/draft", { ...body, base_rev: S.rev });
    take(view, false);
    if (S.edits === sent) { keepHidden(S.draft, view.draft); S.draft = view.draft; }   // nothing changed meanwhile: the server's copy, with its ids
    else adoptIds(view.draft);
    S.error = "";
  } catch (e) {
    S.error = e.message;
  }
  S.saving = false;
  reach = null;
  refresh();
}

/** The ids the server gave things saved while more edits came in. An item takes the id of the server's item in
 *  its place in the list, or (restacking moves them) of one of its asset where it stands, never one in use. */
function adoptIds(server) {
  S.draft.rooms.forEach((r, i) => {
    const sr = server.rooms[i];
    if (!sr) return;
    if (!r.id) r.id = sr.id;
    const used = new Set(r.items.map(x => x.id).filter(Boolean)), free = y => y && y.id && !used.has(y.id);
    r.items.forEach((x, j) => {
      if (x.id) return;
      const y = [sr.items[j]].find(y => free(y) && y.asset === x.asset) || sr.items.find(y => free(y) && y.asset === x.asset && y.x === x.x && y.y === x.y);
      if (y) { x.id = y.id; used.add(y.id); }
    });
    r.doors.forEach((x, j) => { if (!x.id && sr.doors[j]) x.id = sr.doors[j].id; });
  });
}

/** What's hidden in the page's draft, hidden in the server's copy of it too (the lists are in the same order). */
function keepHidden(from, to) {
  from.rooms.forEach((r, i) => {
    const t = to.rooms[i];
    if (t) for (const k of GROUPABLE) listsOf(r)[k].forEach((o, j) => { const o2 = listsOf(t)[k][j]; if (o._hidden && o2) o2._hidden = true; });
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
  canvas.addEventListener("pointerleave", () => { if (S.hover && !S.drag) { S.hover = null; draw(); } });
  canvas.addEventListener("contextmenu", e => { e.preventDefault(); if (S.placing || S.tool !== "select") { S.placing = null; S.tool = "select"; refresh(); } });
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
  closeMenu();
  S.mode = mode;
  S.room = roomIndex;
  S.sel = [];
  S.hover = null;
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
  if (S.mode === "room" && S.room === i) setMode("plan", -1);   // out of it first, so nothing refreshes a room that's gone
  edit(() => { S.draft.rooms.splice(i, 1); S.pick = -1; S.room = S.room === i ? -1 : S.room - (S.room > i); });
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
    const spawns = placed().filter(r => !r.npc_only).flatMap(r => r.paths.points.filter(p => p.kind === "spawn").map(p => `${r.id}/${p.name}`));
    side.replaceChildren(
      el("h3", { textContent: "Rooms" }),
      el("ul", { className: "pl-rooms" }, ...S.draft.rooms.map((r, i) => el("li", { className: (i === S.pick ? "on " : "") + (r.placed ? "placed" : "") },
        el("button", { className: "pl-roomname", textContent: r.name, title: r.placed ? "On the floor" : "In the library", onclick: () => { S.pick = i; focusRoom(i); refresh(); },
                       ondblclick: () => setMode("room", i) }),
        el("span", { className: "hint", textContent: r.placed ? "on the floor" : "library" })))),
      el("button", { textContent: "New room", onclick: newRoom }),
      el("h3", { textContent: "Players appear at" }),
      el("select", { onchange: e => edit(() => { S.draft.spawn = e.target.value; }) },
        // a saved spawn that's gone (its room was removed) shows as a blank pick, not as the first option
        ...(spawns.includes(S.draft.spawn) ? spawns : ["", ...spawns]).map(s => el("option", { value: s,
          textContent: s || (spawns.length ? "(pick one)" : "(no spawn point on the floor)"), selected: s === S.draft.spawn || (!s && !spawns.includes(S.draft.spawn)) }))),
      el("p", { className: "hint", textContent: "Drag a room to move it; doorways that meet show green. Double-click a room to edit it." }));
    return;
  }
  const scroller = side.closest(".pb") || side, scrolled = scroller.scrollTop;   // (it's built afresh: keep its place)
  const sideTab = (id, text) => el("button", { className: S.side === id ? "on" : "", textContent: text, onclick: () => {
    S.side = id; try { localStorage.setItem("plan.side", id); } catch {} refreshSide(); } });
  const tabsBar = el("div", { className: "seg pl-sidetabs" }, sideTab("pieces", "Pieces"), sideTab("layers", "Layers"));
  if (S.side === "layers") {
    side.replaceChildren(tabsBar, ...layersList(room()));
    scroller.scrollTop = scrolled;
    const key = JSON.stringify(S.sel), row = side.querySelector(".pl-layer-row.on");
    if (row && key !== S.listedSel) row.scrollIntoView({ block: "nearest" });   // (a new pick shows in the list)
    S.listedSel = key;
    return;
  }
  // the palette
  const entries = palette(), tabs = [...new Set(entries.map(e => e.cat))];
  if (!tabs.includes(S.tab)) S.tab = tabs[0];
  const q = S.search.toLowerCase(), shown = entries.filter(e => q ? e.name.toLowerCase().includes(q) : e.cat === S.tab);
  side.replaceChildren(tabsBar,
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
  const first = Object.keys(G.CAT.slots)[0];   // (a new bank starts with every cabinet on the first slot)
  if (first) for (const [size, b] of Object.entries(G.CAT.banks))
    add("Slot banks", b.name, { asset: "bank:" + size, facing: "down", props: { slots: b.cabinets.map(() => first) } }, { swatch: "#ffb347" });
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
  const layer = (k, text) => el("label", { className: "pl-check" }, el("input", { type: "checkbox", checked: S.layers[k], onchange: e => {
    S.layers[k] = e.target.checked;
    if (k === "grid") try { localStorage.setItem("plan.grid", e.target.checked ? "1" : "0"); } catch {}
    if (k === "paths") refreshSide();   // (the Layers list shows points and zones only with them)
    draw();
  } }), text);
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
    hiddenCount(room()) ? el("button", { className: "pl-hidden", textContent: `${hiddenCount(room())} hidden · Show all`, title: "Hidden here while you work (they're still in the game)",
                                     onclick: () => { GROUPABLE.forEach(k => listsOf(room())[k].forEach(o => { delete o._hidden; })); refresh(); } }) : null,
    layer("grid", "Show grid"), layer("paths", "Points & zones"), layer("reach", "Where NPCs can walk"),
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
// A card table's limits (plan.py's _clean_limits): main and side bets, each a minimum and maximum in whole pounds.
// A table with none set shows the defaults; changing either row stores both.
const DEFAULT_LIMITS = { main: [500, 50000], side: [100, 5000] };
function limitRows(it) {
  const lim = () => it.props.limits || DEFAULT_LIMITS;
  const pounds = (kind, i) => el("input", { type: "number", min: 1, max: 10000, step: 1, value: lim()[kind][i] / 100,
    onchange: e => { const v = Math.round(+e.target.value); if (!(v >= 1)) return;
      edit(() => { const next = JSON.parse(JSON.stringify(lim())); next[kind][i] = v * 100; it.props.limits = next; }); } });
  const pair = kind => el("span", { className: "pl-pair" }, el("span", { textContent: "£" }), pounds(kind, 0),
    el("span", { textContent: "to £" }), pounds(kind, 1));
  return [field("Main bets", pair("main")), field("Side bets", pair("side"))];
}
function colour(value, set) { return el("input", { type: "color", value, onchange: e => edit(() => set(e.target.value)) }); }
/** A texture's tint (multiplied in, so white is none): the colour, and None to take it off. */
function tint(value, set) {
  return el("span", { className: "pl-tint" }, colour(value, set),
    el("button", { textContent: "None", disabled: value.toLowerCase() === "#ffffff", title: "No tint: the texture as it is", onclick: e => { e.preventDefault(); edit(() => set("#ffffff")); } }));
}
const PLAIN = "#3b2a20";   // a plain patch's colour to start with
/** Floor textures to pick from; going from plain to a texture takes the plain colour off as a tint. */
function texture(obj) {
  return choose(obj.texture, Object.entries(G.CAT.floors).map(([k, f]) => [k, f.name]), v => {
    if (obj.texture === "plain" && v !== "plain") obj.tint = "#ffffff";
    else if (v === "plain" && obj.tint.toLowerCase() === "#ffffff") obj.tint = PLAIN;
    obj.texture = v;
  });
}
const pick = cat => Object.entries(G.CAT[cat]);

function refreshInspector() {
  const ins = $("#pl-insp");
  if (!ins || S.mode === "assets") return;
  if (S.mode === "plan") {
    const r = S.draft.rooms[S.pick];
    if (!r) { ins.replaceChildren(el("h3", { textContent: "The floor" }), el("p", { className: "hint", textContent: `${placed().length} rooms on the floor, ${S.draft.rooms.length - placed().length} in the library. Pick one to see it.` })); return; }
    ins.replaceChildren(el("h3", { textContent: r.name }),
      el("p", { className: "hint", textContent: `${r.w} × ${r.h}, ${r.items.length} things in it.${r.npc_only ? " NPCs only." : ""}${r.map_hidden ? " Not on the minimap." : ""} ${r.placed ? `At ${r.x}, ${r.y} on the floor.` : "In the library (not on the floor)."}` }),
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
      field("Minimap name", Object.assign(text(r.map_name || "", v => { if (v.trim()) r.map_name = v; else delete r.map_name; }),
        { placeholder: r.name, title: "What players see it called, on the minimap and its door tabs. Blank: its name." })),
      field("Width", num(r.w, v => resize(r, "right", r.x + v), { step: 32, min: G.CAT.min_width })),
      field("Height", num(r.h, v => resize(r, "bottom", r.y + v), { step: 32, min: G.minHeight(r) })),
      field("Floor", texture(r.floor)),
      field(r.floor.texture === "plain" ? "Floor colour" : "Floor tint", r.floor.texture === "plain" ? colour(r.floor.tint, v => { r.floor.tint = v; }) : tint(r.floor.tint, v => { r.floor.tint = v; })),
      field("Back wall", choose(r.walls.back === "thin" ? "thin" : "full", [["full", "Full height"], ["thin", "Thin (a border, like the sides)"]], v => {
        if (v === "thin") r.walls.back = "thin"; else { delete r.walls.back; r.h = Math.max(r.h, G.minHeight(r)); } })),
      field("Walls", choose(r.walls.style, Object.entries(G.CAT.walls.styles).map(([k, s]) => [k, s.name]), v => { r.walls.style = v; })),
      field("Sign", text(r.walls.sign, v => { r.walls.sign = v.toUpperCase(); }, 24)),
      field("Sign at", num(r.walls.sign_at, v => { r.walls.sign_at = v; })),
      el("label", { className: "pl-check" }, el("input", { type: "checkbox", checked: r.placed, onchange: () => togglePlaced(S.room) }), "On the floor"),
      el("label", { className: "pl-check", title: "A lift or back room: NPCs given an arrival point here come out of its door and leave back through it. Players can't go in or see inside." },
        el("input", { type: "checkbox", checked: !!r.npc_only, onchange: e => edit(() => { if (e.target.checked) r.npc_only = true; else delete r.npc_only; }) }), "NPCs only (players can't go in)"),
      el("label", { className: "pl-check", title: "Unticked, the minimap leaves this room out: it isn't drawn, nor what's in it, and no door tab names it. Find still knows its tables." },
        el("input", { type: "checkbox", checked: !r.map_hidden, onchange: e => edit(() => { if (e.target.checked) delete r.map_hidden; else r.map_hidden = true; }) }), "Show on minimap"),
      el("p", { className: "hint", textContent: "Drag a wall to resize the room. Click a piece in the palette (or drag it) to put it down; R turns it, Esc stops." }));
    return;
  }
  if (S.sel.length > 1) {
    const groups = new Set(S.sel.map(s => objOf(r, s).group).filter(Boolean));
    const loose = S.sel.filter(s => GROUPABLE.includes(s.t) && !objOf(r, s).group).length;
    const one = groups.size === 1 && !loose;
    ins.replaceChildren(el("h3", { textContent: one ? `A group of ${S.sel.length}` : `${S.sel.length} picked` }),
      el("p", { className: "hint", textContent: "Drag to move them together; arrows nudge; Ctrl+C / Ctrl+V; R turns each. "
        + (groups.size ? "Clicking anything in a group picks all of it; Ctrl+click picks one thing on its own." : "Group them to pick and move them as one.") }),
      el("div", { className: "pl-buttons" },
        el("button", { textContent: "Group", title: "Ctrl+G: clicking any of them then picks them all", onclick: groupSelected,
                       disabled: one || loose + groups.size < 2 }),
        groups.size ? el("button", { textContent: "Ungroup", title: "Ctrl+Shift+G", onclick: ungroupSelected }) : null,
        el("button", { textContent: "Duplicate", title: "Ctrl+D (doors stay put)", onclick: duplicateSelected }),
        ...flagButtons(r),
        el("button", { className: "danger", textContent: "Delete them", onclick: removeSelected })),
      ...[layerRow(r)].filter(Boolean));
    return;
  }
  const { t, i } = S.sel[0];
  const head = (h, sub) => [el("h3", { textContent: h }), sub ? el("p", { className: "hint", textContent: sub }) : null];
  const del = el("div", { className: "pl-buttons" },
    objOf(r, S.sel[0]).group ? el("button", { textContent: "Leave the group", title: "It's in a group (Ctrl+click picked it on its own): take it out", onclick: ungroupSelected }) : null,
    t !== "door" ? el("button", { textContent: "Duplicate", title: "Ctrl+D", onclick: duplicateSelected }) : null,
    ...flagButtons(r),
    el("button", { className: "danger", textContent: "Delete", onclick: removeSelected }));
  const tail = [layerRow(r), del].filter(Boolean);   // (under each inspector's fields)
  if (t === "item") {
    const it = r.items[i], kind = G.kindOf(it.asset), rows = [];
    rows.push(field("Across", num(it.x, v => { it.x = v; })), field("Down", num(it.y, v => { it.y = v; })));
    if (kind === "table") {
      const rots = G.CAT.games[it.asset.slice(6)].rotations;
      rows.push(field("Name", text(it.props.label, v => { it.props.label = v; }, 32)));
      if (rots.length > 1) rows.push(field("Turned", choose(String(it.rot || 0), rots.map(d => [String(d), d ? `${d}°` : "Upright"]), v => { turnTo(it, +v); })));
      if (G.CAT.games[it.asset.slice(6)].at["0"].sign)
        rows.push(field("Sign", choose(G.signSide(it), ["right", "left"].map(side => [side, signEnd(it, side)]), v => { it.props.sign = v; })));
      if (!["table:roulette", "table:craps"].includes(it.asset)) rows.push(...limitRows(it));
      if (it.asset === "table:master_table") {   // how it changes from one game to another (tables/master.py)
        rows.push(field("Changes with", choose(it.props.anim || "cloth", [["cloth", "Fresh cloth"], ["sweep", "Dealer's sweep"], ["dust", "Gold dust"]],
          v => { it.props.anim = v; })));
        rows.push(field("Speed", choose(String(it.props.speed || 1), [["0.5", "0.5×"], ["1", "1×"], ["2", "2×"]], v => { it.props.speed = +v; })));
      }
    } else if (kind === "bank") {   // (its size is what it is: another size is another bank)
      const b = G.CAT.banks[it.asset.slice(5)];
      if (b.facings.length > 1) rows.push(field("Facing", choose(it.facing || "down", b.facings.map(f => [f, f]), v => { it.facing = v; })));
      b.cabinets.forEach(([, , , name], n) => rows.push(field(name, choose(it.props.slots[n], Object.entries(G.CAT.slots), v => { it.props.slots[n] = v; }))));
    } else {
      rows.push(field("Facing", choose(it.facing || "down", G.CAT.facings.map(f => [f, f]), v => { it.facing = v; })));
    }
    if (kind === "slot") rows.push(field("Slot", choose(it.props.variant, Object.entries(G.CAT.slots), v => { it.props.variant = v; })));
    if (it.asset === "npc") {
      rows.push(field("Who", choose(it.props.look, [["dealer", "A dealer"], ...S.npcs.map(n => [n.look_id, n.name])], v => {
        it.props.look = v; const n = S.npcs.find(n => n.look_id === v); if (n && !it.props.name) it.props.name = n.name; })));
      rows.push(field("Name", text(it.props.name, v => { it.props.name = v; }, 24)));
    }
    ins.replaceChildren(...head(G.label(it), it.id ? `id ${it.id}` : "new: saved in a moment"), ...rows, ...tail);
  } else if (t === "point") {
    const p = r.paths.points[i];
    ins.replaceChildren(...head("Point " + p.name, { spawn: "Players appear here.", arrival: "NPCs come in (and leave) here.", wander: "NPCs wander here between games." }[p.kind]),
      field("Name", text(p.name, v => { p.name = v; }, 24)),
      field("Kind", choose(p.kind, G.CAT.point_kinds.map(k => [k, k]), v => { p.kind = v; })),
      field("Weight", num(p.weight, v => { p.weight = v; }, { min: 0, max: 100, step: 0.5 })),
      field("Linger (s)", num(p.linger, v => { p.linger = v; }, { min: 0, max: 600 })),
      field("Across", num(p.x, v => { p.x = v; })), field("Down", num(p.y, v => { p.y = v; })), ...tail);
  } else if (t === "zone") {
    const z = r.paths.zones[i];
    ins.replaceChildren(...head("No-go zone", "Drag its edges or corners to resize it (Shift for free)."),
      field("Keeps out", choose(z.kind, [["npc_block", "NPCs (players walk through)"], ["block", "Everyone"]], v => { z.kind = v; })),
      field("Across", num(z.x, v => { z.x = v; })), field("Down", num(z.y, v => { z.y = v; })),
      field("Width", num(z.w, v => { z.w = v; })), field("Height", num(z.h, v => { z.h = v; })), ...tail);
  } else if (t === "door") {
    const d = r.doors[i];
    ins.replaceChildren(...head(d.kind === "door" ? "Door" : "Archway", `In the ${d.side} wall. It joins the room whose wall meets it there; with none, it stays shut.`),
      field("Kind", choose(d.kind, [["door", "Door (shut till someone's by)"], ["archway", "Archway (open)"]], v => { d.kind = v; })),
      field("Width", num(d.width, v => { d.width = v; }, { min: 40, max: 600, step: 8 })),
      field("Along", num(d.at, v => { d.at = v; })), ...tail);
  } else if (t === "patch") {
    const p = r.patches[i];
    for (const [k, v] of Object.entries(newPatch({}))) if (p[k] === undefined) p[k] = structuredClone(v);   // (made before patches had a look)
    const pat = p.pattern, bor = p.border, plain = p.texture === "plain";
    ins.replaceChildren(...head("Floor patch", "Drag an edge or corner to resize it."),
      field("Floor", texture(p)),
      field(plain ? "Colour" : "Tint", plain ? colour(p.tint, v => { p.tint = v; }) : tint(p.tint, v => { p.tint = v; })),
      field("Shape", choose(p.shape, pick("patch_shapes"), v => { p.shape = v; })),
      p.shape === "rounded" ? field("Corner", num(p.radius, v => { p.radius = v; }, { min: 0, max: 400 })) : null,
      field("Pattern", choose(pat.kind, pick("patch_patterns"), v => { pat.kind = v; })),
      ...(pat.kind === "none" ? [] : [
        field("Pattern colour", colour(pat.colour, v => { pat.colour = v; })),
        field("Pattern size", num(pat.size, v => { pat.size = v; }, { min: 8, max: 512 })),
        field("Opacity %", num(pat.opacity, v => { pat.opacity = v; }, { min: 0, max: 100, step: 5 }))]),
      field("Border", choose(bor.style, pick("patch_borders"), v => { bor.style = v; })),
      ...(bor.style === "none" ? [] : [
        field("Border colour", colour(bor.colour, v => { bor.colour = v; })),
        field("Border width", num(bor.width, v => { bor.width = v; }, { min: 1, max: 64 }))]),
      field("Across", num(p.x, v => { p.x = v; })), field("Down", num(p.y, v => { p.y = v; })),
      field("Width", num(p.w, v => { p.w = v; })), field("Height", num(p.h, v => { p.h = v; })), ...tail);
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
    for (const i of stack(r).reverse()) {   // (bottom first: as the game layers them)
      const it = r.items[i];
      if (!it._hidden) drawItem(ctx, r, it, { picked: r === cur && S.sel.some(s => s.t === "item" && s.i === i), bad: bad.has(i) });
    }
    if (r === cur && S.layers.paths) drawPaths(ctx, r, { point: pickedIndex("point"), zone: pickedIndex("zone") });
  }
  if (cur && S.layers.grid) overlayGrid(cur);
  if (cur && S.hover && objOf(cur, S.hover) && !S.sel.some(s => s.t === S.hover.t && s.i === S.hover.i))   // what a click would pick
    for (const q of boundsOf(cur, S.hover)) outlineRect(G.grow(q, 2 / S.cam.s), "#7fe3ff", 1.5, [3, 3]);
  if (cur) {
    S.sel.filter(s => s.t === "door").forEach(s => { const d = cur.doors[s.i]; if (d) outlineRect(G.gap(cur, d), "#ffd36b"); });
    S.sel.filter(s => s.t === "patch").forEach(s => { const p = cur.patches[s.i]; if (p) outlineRect([cur.x + p.x, cur.y + p.y, p.w, p.h], "#ffd36b"); });
    for (const g of new Set(S.sel.map(s => objOf(cur, s)?.group).filter(Boolean))) {   // a group picked: a dashed box round all of it
      const rs = members(cur, g).flatMap(m => boundsOf(cur, m));
      const x0 = Math.min(...rs.map(q => q[0])), y0 = Math.min(...rs.map(q => q[1]));
      if (rs.length) outlineRect(G.grow([x0, y0, Math.max(...rs.map(q => q[0] + q[2])) - x0, Math.max(...rs.map(q => q[1] + q[3])) - y0], 10 / S.cam.s), "#ffd36b", 1.5, [8, 5]);
    }
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

// "Show grid": drawn over the floor and everything on it, inside the room. Lines every 32px, and every 8px (the snap
// step) once they're far enough apart to read; the room's top-left corner is the origin, as positions are.
function overlayGrid(r) {
  ctx.save();
  ctx.beginPath(); ctx.rect(...G.outline(r)); ctx.clip();
  const lines = (step, colour) => {
    ctx.strokeStyle = colour; ctx.beginPath();
    for (let x = r.x + step; x < r.x + r.w; x += step) { ctx.moveTo(x, r.y); ctx.lineTo(x, r.y + r.h); }
    for (let y = r.y + step; y < r.y + r.h; y += step) { ctx.moveTo(r.x, y); ctx.lineTo(r.x + r.w, y); }
    ctx.stroke();
  };
  ctx.lineWidth = 1 / S.cam.s;
  if (SNAP.item * S.cam.s >= 6) lines(SNAP.item, "rgba(255,255,255,.10)");
  lines(32, "rgba(255,255,255,.28)");
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
    turnTo(it, rots[(rots.indexOf(it.rot || 0) + 1) % rots.length]);
  } else {   // (a library piece turns only to the facings it has pictures for, a slot bank to its own)
    const p = G.piece(it.asset), bank = G.kindOf(it.asset) === "bank" && G.CAT.banks[it.asset.slice(5)];
    const order = ["down", "left", "up", "right"].filter(f => bank ? bank.facings.includes(f) : !p || !p.facings || p.facings[f]);
    it.facing = order[(order.indexOf(it.facing || "down") + 1) % order.length];
  }
}

/** Turn a table to `rot` about its middle, so it stays where it was (it turns about its seats' row otherwise). */
function turnTo(it, rot) {
  const at = G.CAT.games[it.asset.slice(6)].at, mid = r => { const b = (at[String(r)] || at["0"]).body; return [b[0] + b[2] / 2, b[1] + b[3] / 2]; };
  const [a, b] = [mid(it.rot || 0), mid(rot)];
  if (typeof it.x === "number") { it.x = Math.round(it.x + a[0] - b[0]); it.y = Math.round(it.y + a[1] - b[1]); }
  it.rot = rot;
}

/** Where a table's sign end (`side`, as its players see it) shows on the plan, turned as it is. */
function signEnd(it, side) {
  const k = ((it.rot || 0) / 90 + (side === "left" ? 2 : 0)) % 4;
  return ["Right end", "Bottom end", "Left end", "Top end"][k];
}

function removeSelected() {
  const r = room();
  if (!r || !S.sel.length) return;
  edit(() => {
    const lists = listsOf(r);
    for (const s of S.sel.slice().sort((a, b) => b.i - a.i)) lists[s.t].splice(s.i, 1);
    S.sel = [];   // before edit() refreshes: the inspector would otherwise look up what's just gone
    tidyGroups(r);
  });
}

function duplicateSelected() {
  const r = room();
  if (r && S.sel.length) putDown(r, copyPicked(r), null);
}

/** The picked things (not doors: they belong to their wall), copied without their ids: [{t, o}]. */
function copyPicked(r) {
  return S.sel.filter(s => s.t !== "door").map(s => { const o = JSON.parse(JSON.stringify(objOf(r, s))); delete o.id; return { t: s.t, o }; });
}

/** Put copies down in room r with their middle at `at` (room coordinates), or 32 down and right of where they were
 *  copied from; each group they were in becomes a new group of the copies. They're picked after. */
function putDown(r, clip, at) {
  if (!clip.length) return;
  const cx = clip.reduce((a, c) => a + c.o.x, 0) / clip.length, cy = clip.reduce((a, c) => a + c.o.y, 0) / clip.length;
  const dx = at ? snap(at[0] - cx, SNAP.item) : 32, dy = at ? snap(at[1] - cy, SNAP.item) : 32;   // (one step for all: they keep their spacing)
  edit(() => {
    const lists = listsOf(r), next = groupMaker(r), fresh = {};
    S.sel = clip.map(({ t, o }) => {
      const c = { ...JSON.parse(JSON.stringify(o)), x: o.x + dx, y: o.y + dy };
      if (c.group) c.group = fresh[c.group] ||= next();
      lists[t].push(c);
      return { t, i: lists[t].length - 1 };
    });
  });
}

// ---------------------------------------------------------------- groups: things picked and moved as one
const GROUPABLE = ["item", "point", "zone", "patch"];   // (not doors: they slide along their wall)
const listsOf = r => ({ item: r.items, point: r.paths.points, zone: r.paths.zones, door: r.doors, patch: r.patches });

/** Everything in group g: [{t, i}]. */
function members(r, g) {
  const lists = listsOf(r);
  return GROUPABLE.flatMap(t => lists[t].flatMap((o, i) => o.group === g ? [{ t, i }] : []));
}

/** sel, with the rest of every group anything in it is in. */
function withGroups(r, sel) {
  const out = sel.slice();
  for (const g of new Set(sel.map(s => objOf(r, s).group).filter(Boolean)))
    for (const m of members(r, g)) if (!out.some(s => s.t === m.t && s.i === m.i)) out.push(m);
  return out;
}

/** Hands out group ids the room hasn't used: g1, g2... */
function groupMaker(r) {
  const lists = listsOf(r);
  let n = Math.max(0, ...GROUPABLE.flatMap(t => lists[t].map(o => +((/^g(\d+)$/.exec(o.group || "") || [])[1] || 0)))) + 1;
  return () => "g" + n++;
}

/** A group down to one thing isn't one any more. */
function tidyGroups(r) {
  const lists = listsOf(r), count = {};
  GROUPABLE.forEach(t => lists[t].forEach(o => { if (o.group) count[o.group] = (count[o.group] || 0) + 1; }));
  GROUPABLE.forEach(t => lists[t].forEach(o => { if (o.group && count[o.group] < 2) delete o.group; }));
}

function groupSelected() {
  const r = room(), sel = S.sel.filter(s => GROUPABLE.includes(s.t));
  if (!r || sel.length < 2) return;
  edit(() => { const g = groupMaker(r)(); sel.forEach(s => { objOf(r, s).group = g; }); tidyGroups(r); });
  status(`Grouped ${sel.length}: clicking any of them picks them all (Ctrl+click one on its own).`, "ok");
}

/** Ungroup what's picked (one thing Ctrl+clicked out of its group just leaves it). */
function ungroupSelected() {
  const r = room();
  if (!r || !S.sel.some(s => objOf(r, s).group)) return;
  edit(() => { S.sel.forEach(s => { delete objOf(r, s).group; }); tidyGroups(r); });
}

/** Where a thing is on the plan, for the box round its group: rects. */
function boundsOf(r, s) { return rectsOf(r, s.t, objOf(r, s)); }
function rectsOf(r, t, o) {
  if (t === "item") { const sh = G.shapes(r, o); return sh ? G.covers(sh) : []; }
  if (t === "point") return [[r.x + o.x - 10, r.y + o.y - 10, 20, 20]];
  if (t === "door") return [G.gap(r, o)];
  return [[r.x + o.x, r.y + o.y, o.w, o.h]];
}

// ---------------------------------------------------------------- layers: what's on top, and arranging the stacks
// The game draws a room's floor patches in their list's order, then rugs and other flat pieces in the items' order,
// then wall pieces in the items' order, then everything standing by depth, nearest last (plan_room.gd). The first
// three can be restacked; standing things can't (move one down the room to bring it in front).

/** How an item stacks: "flat" (rugs, on the floor), "wall" (hung on it) or "stand" (by depth). */
const layerOf = it => ({ flat: "flat", wall: "wall" }[(G.piece(it.asset) || {}).mount] || "stand");

/** The room's items, top first: standing ones nearest first, then wall pieces, then rugs, last in the list first. */
function stack(r) {
  const rank = { stand: 0, wall: 1, flat: 2 };
  return r.items.map((it, i) => [i, it, layerOf(it)])
    .sort((a, b) => rank[a[2]] - rank[b[2]] || (a[2] === "stand" ? b[1].y - a[1].y : 0) || b[0] - a[0]).map(([i]) => i);
}

/** The stack a picked thing can be rearranged in: "patch", "flat", "wall", or null (standing, a point, a zone, a door). */
function stackOf(r, s) {
  if (s.t === "patch") return "patch";
  return s.t === "item" && layerOf(r.items[s.i]) !== "stand" ? layerOf(r.items[s.i]) : null;
}
/** Stack k's things, bottom first. */
const stackList = (r, k) => k === "patch" ? r.patches.slice() : r.items.filter(it => layerOf(it) === k);
/** Put stack k in the order `objs` (bottom first); everything else keeps its place in its list. */
function setStack(r, k, objs) {
  if (k === "patch") { r.patches.splice(0, r.patches.length, ...objs); return; }
  let n = 0;
  r.items.forEach((it, i) => { if (layerOf(it) === k) r.items[i] = objs[n++]; });
}
/** Run fn (which moves things round their lists), keeping the same things picked. */
function keepPicks(r, fn) {
  const picked = S.sel.map(s => [s.t, objOf(r, s)]);
  fn();
  S.sel = picked.map(([t, o]) => ({ t, i: listsOf(r)[t].indexOf(o) })).filter(s => s.i >= 0);
  S.hover = null;
}

const LAYER_CMDS = [["front", "Bring to front", "Ctrl+Shift+]", "⤒"], ["forward", "Bring forward", "Ctrl+]", "↑"],
                    ["backward", "Send backward", "Ctrl+[", "↓"], ["back", "Send to back", "Ctrl+Shift+[", "⤓"]];

/** Move what's picked up or down its stack (each in its own). Forward and backward go past the next thing that
 *  overlaps it, skipping those that don't (moving past them would change nothing you can see). */
function restack(dir) {
  const r = room();
  if (!r) return;
  const kinds = [...new Set(S.sel.map(s => stackOf(r, s)).filter(Boolean))];
  if (!kinds.length) {
    if (S.sel.length) status("Standing things are drawn by depth, as in the game: move one down the room to bring it in front.", "ok");
    return;
  }
  const picked = new Set(S.sel.map(s => objOf(r, s)));
  const touch = (t, a, b) => rectsOf(r, t, a).some(x => rectsOf(r, t, b).some(y => G.overlap(x, y)));
  const next = kinds.map(k => {
    const t = k === "patch" ? "patch" : "item", list = stackList(r, k), was = list.slice();
    if (dir === "front" || dir === "back") {
      const mine = list.filter(o => picked.has(o)), rest = list.filter(o => !picked.has(o));
      list.splice(0, list.length, ...(dir === "front" ? [...rest, ...mine] : [...mine, ...rest]));
    } else {
      const up = dir === "forward", order = list.filter(o => picked.has(o));
      if (up) order.reverse();   // (the one nearest where they're going first, so they don't jump each other)
      for (const o of order) {
        const j = list.indexOf(o);
        for (let n = j + (up ? 1 : -1); n >= 0 && n < list.length; n += up ? 1 : -1)
          if (!picked.has(list[n]) && touch(t, o, list[n])) { list.splice(j, 1); list.splice(n, 0, o); break; }
      }
    }
    return [k, list, list.some((o, n) => o !== was[n])];
  });
  if (!next.some(x => x[2])) {
    status({ front: "Already at the front.", back: "Already at the back.", forward: "Already in front of everything it overlaps.",
             backward: "Already behind everything it overlaps." }[dir], "ok");
    return;
  }
  edit(() => keepPicks(r, () => next.forEach(([k, list]) => setStack(r, k, list))));
}

/** Move `o` in stack k to just above (or below) `target`: a row dragged in the Layers list. */
function moveInStack(r, k, o, target, above) {
  const list = stackList(r, k).filter(x => x !== o), n = list.indexOf(target);
  if (n < 0) return;
  list.splice(above ? n + 1 : n, 0, o);   // (bottom first: above is after)
  if (list.every((x, j) => x === stackList(r, k)[j])) return;
  edit(() => keepPicks(r, () => setStack(r, k, list)));
}

/** The inspector's Layer row: the four moves, or why a standing thing has none. */
function layerRow(r) {
  if (S.sel.some(s => stackOf(r, s)))
    return field("Layer", el("span", { className: "pl-layer" }, ...LAYER_CMDS.map(([dir, text, keys, glyph]) =>
      el("button", { className: "sq", textContent: glyph, title: `${text} (${keys})`, onclick: () => restack(dir) }))));
  if (S.sel.some(s => s.t === "item")) return el("p", { className: "hint", textContent: "Drawn by depth, as in the game: move it down the room to bring it in front." });
  return null;
}

/** Lock and Hide for what's picked (not doors). */
function flagButtons(r) {
  const objs = S.sel.filter(s => s.t !== "door").map(s => objOf(r, s));
  if (!objs.length) return [];
  const locked = objs.every(o => o.locked), hidden = objs.every(o => o._hidden);
  return [el("button", { textContent: locked ? "Unlock" : "Lock", onclick: () => setLocked(objs, !locked),
                         title: "Locked, the canvas doesn't pick or drag it (clicks go through to what's under it); pick it in Layers" }),
          el("button", { textContent: hidden ? "Show" : "Hide", onclick: () => setHidden(objs, !hidden),
                         title: "Hide it here while you work (it's still in the game; it's back when the page reloads)" })];
}
function setLocked(objs, on) { edit(() => objs.forEach(o => { if (on) o.locked = true; else delete o.locked; })); }
function setHidden(objs, on) { objs.forEach(o => { if (on) o._hidden = true; else delete o._hidden; }); S.hover = null; refresh(); }
const hiddenCount = r => r ? GROUPABLE.reduce((n, k) => n + listsOf(r)[k].filter(o => o._hidden).length, 0) : 0;

/** A thing's name in Layers and the menu. */
function describe(r, s) {
  const o = objOf(r, s);
  if (s.t === "item") { const t = G.label(o).replace(/^the /, ""); return t[0].toUpperCase() + t.slice(1); }
  if (s.t === "patch") return `Patch ${s.i + 1} · ${(G.CAT.floors[o.texture] || {}).name || o.texture}`;
  if (s.t === "zone") return `Zone ${s.i + 1} · ${o.kind === "block" ? "everyone keeps out" : "NPCs keep out"}`;
  if (s.t === "point") return `Point ${o.name} (${o.kind})`;
  return `${o.kind === "door" ? "Door" : "Archway"} in the ${o.side} wall`;
}

/** Centre the view on a thing (double-click its row). */
function centreOn(r, s) {
  const rs = boundsOf(r, s);
  if (!rs.length) return;
  const x0 = Math.min(...rs.map(q => q[0])), y0 = Math.min(...rs.map(q => q[1]));
  const cx = (x0 + Math.max(...rs.map(q => q[0] + q[2]))) / 2, cy = (y0 + Math.max(...rs.map(q => q[1] + q[3]))) / 2;
  S.cam.x = cx - canvas.clientWidth / 2 / S.cam.s; S.cam.y = cy - canvas.clientHeight / 2 / S.cam.s;
  draw();
}

/** Pick s from a list (Layers): as a click on the canvas would, Shift adding and Ctrl taking it out of its group. */
function pickFromList(r, s, e) {
  const unit = e.ctrlKey || e.metaKey ? [s] : withGroups(r, [s]), inUnit = x => unit.some(u => u.t === x.t && u.i === x.i);
  const already = S.sel.some(x => x.t === s.t && x.i === s.i);
  S.sel = e.shiftKey ? (already ? S.sel.filter(x => !inUnit(x)) : [...S.sel.filter(x => !inUnit(x)), ...unit]) : unit;
  refresh();
}

/** The Layers list: everything in the room, top of the stack first, in sections. Rugs, wall pieces and patches
 *  drag up and down their sections to restack. */
function layersList(r) {
  if (!r) return [];
  const rev = n => [...Array(n).keys()].reverse(), paths = S.layers.paths, byLayer = k => stack(r).filter(i => layerOf(r.items[i]) === k);
  const sections = [
    ["Doors", "", null, rev(r.doors.length).map(i => ({ t: "door", i }))],
    ["Points", "", null, paths ? rev(r.paths.points.length).map(i => ({ t: "point", i })) : []],
    ["Standing", "by depth: nearest in front", null, byLayer("stand").map(i => ({ t: "item", i }))],
    ["On the wall", "drag to restack", "wall", byLayer("wall").map(i => ({ t: "item", i }))],
    ["On the floor", "rugs: drag to restack", "flat", byLayer("flat").map(i => ({ t: "item", i }))],
    ["No-go zones", "", null, paths ? rev(r.paths.zones.length).map(i => ({ t: "zone", i })) : []],
    ["Floor patches", "drag to restack", "patch", rev(r.patches.length).map(i => ({ t: "patch", i }))]];
  const out = [];
  for (const [title, hint, k, rows] of sections) {
    if (!rows.length) continue;
    out.push(el("h3", {}, title, hint ? el("span", { className: "pl-h3-hint", textContent: " · " + hint }) : null));
    out.push(el("div", { className: "pl-layers" }, ...rows.map(s => layerRowEl(r, s, k))));
  }
  if (!out.length) out.push(el("p", { className: "hint", textContent: "Nothing in this room yet." }));
  else out.push(el("p", { className: "hint", textContent: "Click to pick (Shift adds, Ctrl picks one out of a group), double-click to find it. On the canvas, Alt+click picks what's under what's picked; right-click lists everything there." }));
  return out;
}

const ICONS = {
  eye: '<path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/>',
  shut: '<path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><path d="M2.5 13.5l11-11"/>',
  lock: '<rect x="3.5" y="7" width="9" height="6.5" rx="1"/><path d="M5.5 7V5a2.5 2.5 0 015 0v2"/>',
  open: '<rect x="3.5" y="7" width="9" height="6.5" rx="1"/><path d="M5.5 7V5a2.5 2.5 0 014.8-1"/>',
};
function icon(name) {
  const s = el("span", { className: "pl-ico" });
  s.innerHTML = `<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  return s;
}

function layerRowEl(r, s, k) {
  const o = objOf(r, s), on = S.sel.some(x => x.t === s.t && x.i === s.i);
  const row = el("div", { className: "pl-layer-row" + (on ? " on" : "") + (o._hidden ? " off" : ""), draggable: !!k,
    onpointerenter: () => { S.hover = s; draw(); }, onpointerleave: () => { S.hover = null; draw(); } },
    k ? el("span", { className: "pl-grip", textContent: "⋮⋮", title: "Drag to restack" }) : null,
    el("button", { className: "pl-layer-name", textContent: describe(r, s), title: describe(r, s),
                   onclick: e => pickFromList(r, s, e), ondblclick: () => centreOn(r, s) }),
    o.group ? el("span", { className: "pl-tag", textContent: o.group, title: "In group " + o.group }) : null,
    s.t !== "door" ? el("button", { className: "pl-flag" + (o._hidden ? " set" : ""), title: o._hidden ? "Show it" : "Hide it here while you work",
                                    onclick: () => setHidden([o], !o._hidden) }, icon(o._hidden ? "shut" : "eye")) : null,
    s.t !== "door" ? el("button", { className: "pl-flag" + (o.locked ? " set" : ""), title: o.locked ? "Unlock it" : "Lock it: the canvas won't pick or drag it",
                                    onclick: () => setLocked([o], !o.locked) }, icon(o.locked ? "lock" : "open")) : null);
  if (!k) return row;
  row.addEventListener("dragstart", e => { S.rowDrag = { k, o }; e.dataTransfer.setData("application/x-plan-layer", "1"); e.dataTransfer.effectAllowed = "move"; });
  row.addEventListener("dragend", () => { S.rowDrag = null; });
  row.addEventListener("dragover", e => {
    if (!S.rowDrag || S.rowDrag.k !== k || S.rowDrag.o === o) return;
    e.preventDefault();
    const above = e.clientY - row.getBoundingClientRect().top < row.offsetHeight / 2;   // (over the top half: above it)
    row.classList.toggle("drop-above", above); row.classList.toggle("drop-below", !above);
  });
  row.addEventListener("dragleave", () => row.classList.remove("drop-above", "drop-below"));
  row.addEventListener("drop", e => {
    e.preventDefault();
    const d = S.rowDrag, above = row.classList.contains("drop-above");
    row.classList.remove("drop-above", "drop-below");
    S.rowDrag = null;
    if (d && d.k === k) moveInStack(r, k, d.o, o, above);
  });
  return row;
}

// ---------------------------------------------------------------- the right-click menu: everything under the pointer
function closeMenu() { const m = document.getElementById("pl-menu"); if (m) m.remove(); }

function openMenu(e, p) {
  closeMenu();
  const r = room();
  if (!r) return;
  const all = hitAll(p, { locked: true });   // (locked things too: picking one here is on purpose)
  const isPicked = h => S.sel.some(s => s.t === h.t && s.i === h.i);
  const top = hitAll(p)[0];   // (the moves are for what's picked there, or else what's on top)
  if (top && !all.some(isPicked)) { S.sel = withGroups(r, [top]); refresh(); }
  const canStack = S.sel.some(s => stackOf(r, s));
  const menu = el("div", { className: "pl-menu", id: "pl-menu", oncontextmenu: ev => ev.preventDefault() },
    el("div", { className: "pl-menu-head", textContent: all.length ? "Here, top first" : "Nothing here" }),
    ...all.map(h => el("button", { className: "pl-menu-row" + (isPicked(h) ? " on" : ""),
        onclick: () => { closeMenu(); S.sel = [h]; refresh(); },
        onpointerenter: () => { S.hover = h; draw(); }, onpointerleave: () => { S.hover = null; draw(); } },
      el("span", { className: "pl-menu-tick", textContent: isPicked(h) ? "✓" : "" }), el("span", { textContent: describe(r, h) }),
      objOf(r, h).locked ? icon("lock") : null)),
    canStack ? el("div", { className: "pl-menu-sep" }) : null,
    ...(canStack ? LAYER_CMDS.map(([dir, text, keys, glyph]) => el("button", { className: "pl-menu-row", onclick: () => { closeMenu(); restack(dir); } },
      el("span", { className: "pl-menu-tick", textContent: glyph }), el("span", { textContent: text }), el("kbd", { textContent: keys }))) : []));
  const stage = canvas.parentElement, b = stage.getBoundingClientRect();
  stage.append(menu);
  menu.style.left = Math.max(4, Math.min(e.clientX - b.left, b.width - menu.offsetWidth - 4)) + "px";
  menu.style.top = Math.max(4, Math.min(e.clientY - b.top, b.height - menu.offsetHeight - 4)) + "px";
  const away = ev => {   // (a press anywhere else closes it; once it's gone, by whatever way, this goes too)
    if (document.getElementById("pl-menu") === menu && menu.contains(ev.target)) return;
    if (document.getElementById("pl-menu") === menu) closeMenu();
    document.removeEventListener("pointerdown", away, true);
  };
  setTimeout(() => document.addEventListener("pointerdown", away, true));
}

/** Resize a room by moving one wall to `to` (plan coordinates): what's inside stays where it is on the plan. */
function resize(r, side, to) {
  to = Math.round(to);
  const minW = G.CAT.min_width, minH = G.minHeight(r);
  if (side === "right") { r.w = Math.max(minW, to - r.x); r.walls.sign_at = Math.min(r.walls.sign_at, r.w); }
  else if (side === "bottom") r.h = Math.max(minH, to - r.y);
  else {
    const d = side === "left" ? Math.min(to - r.x, r.w - minW) : Math.min(to - r.y, r.h - minH);
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

/** Which edges (or corner) of the box q (room coordinates) p is on: ["left", "top"]..., or null. */
function boxSides(r, q, p) {
  const tol = 6 / S.cam.s, [x, y] = p, x0 = r.x + q.x, y0 = r.y + q.y, x1 = x0 + q.w, y1 = y0 + q.h;
  if (x < x0 - tol || x > x1 + tol || y < y0 - tol || y > y1 + tol) return null;
  const sides = [];
  if (Math.abs(x - x0) < tol) sides.push("left"); else if (Math.abs(x - x1) < tol) sides.push("right");
  if (Math.abs(y - y0) < tol) sides.push("top"); else if (Math.abs(y - y1) < tol) sides.push("bottom");
  return sides.length ? sides : null;
}

/** The floor patch edge (or corner) under p: {i, sides}, the picked patch before the others. */
function patchEdge(r, p) {
  const picked = S.sel.filter(s => s.t === "patch").map(s => s.i);
  const order = [...picked, ...r.patches.map((_, i) => r.patches.length - 1 - i).filter(i => !picked.includes(i))];
  for (const i of order) {
    if (r.patches[i].locked || r.patches[i]._hidden) continue;
    const sides = boxSides(r, r.patches[i], p);
    if (sides) return { i, sides };
  }
  return null;
}

/** Something under p to drag out: a wall ({edge}), a patch's edge ({patch}) or a picked zone's edge ({zone}). A picked
 *  zone's edge beats everything; a picked patch's edge beats a wall, a wall beats any other patch's edge; anything
 *  standing on top (an item, a point, a door, a zone) beats those. */
function grabAt(r, p) {
  if (S.layers.paths) for (const s of S.sel) {
    const z = s.t === "zone" && r.paths.zones[s.i], sides = z && !z.locked && !z._hidden && boxSides(r, z, p);
    if (sides) return { zone: { i: s.i, sides } };
  }
  const h = hit(p);
  if (h && h.t !== "patch") return null;
  const pe = patchEdge(r, p), wall = hitRoomEdge(r, p);
  if (pe && (!wall || S.sel.some(s => s.t === "patch" && s.i === pe.i))) return { patch: pe };
  return wall ? { edge: wall } : null;
}

const RESIZE = { left: "ew-resize", right: "ew-resize", top: "ns-resize", bottom: "ns-resize",
                 "left top": "nwse-resize", "right bottom": "nwse-resize", "right top": "nesw-resize", "left bottom": "nesw-resize" };
const grabCursor = g => RESIZE[g.edge || (g.patch || g.zone).sides.join(" ")];

/** A plain patch over `box`, with its look's defaults (as plan.py's _patch fills them in). */
const newPatch = box => ({ ...box, texture: "plain", tint: PLAIN, shape: "rect", radius: 24,
                           pattern: { kind: "none", colour: "#000000", size: 32, opacity: 30 },
                           border: { style: "none", colour: "#c9a24a", width: 6 } });

/** Drag a patch's (or zone's) edges to `to` (room coordinates); the opposite edges stay where they were. */
function resizePatch(q, was, sides, to, free) {
  const MIN = 8, x = snap(to[0], SNAP.item, free), y = snap(to[1], SNAP.item, free);
  if (sides.includes("left")) { q.x = Math.min(x, was.x + was.w - MIN); q.w = was.x + was.w - q.x; }
  if (sides.includes("right")) q.w = Math.max(MIN, x - was.x);
  if (sides.includes("top")) { q.y = Math.min(y, was.y + was.h - MIN); q.h = was.y + was.h - q.y; }
  if (sides.includes("bottom")) q.h = Math.max(MIN, y - was.y);
}

/** Everything under p, top first, as it's drawn: doors, points, the items (stack()), zones, patches. Hidden things
 *  aren't there, nor locked ones unless opts.locked. */
function hitAll(p, opts = {}) {
  const r = room();
  if (!r) return [];
  const out = [], ok = o => !o._hidden && (opts.locked || !o.locked);
  for (let i = r.doors.length - 1; i >= 0; i--) if (G.inside(p, G.grow(G.gap(r, r.doors[i]), 6 / S.cam.s))) out.push({ t: "door", i });
  if (S.layers.paths) {
    for (let i = r.paths.points.length - 1; i >= 0; i--) { const q = r.paths.points[i]; if (ok(q) && Math.hypot(p[0] - r.x - q.x, p[1] - r.y - q.y) < 14) out.push({ t: "point", i }); }
  }
  for (const i of stack(r)) { const it = r.items[i], s = ok(it) && G.shapes(r, it); if (s && G.covers(s).some(c => G.inside(p, c))) out.push({ t: "item", i }); }
  if (S.layers.paths) for (let i = r.paths.zones.length - 1; i >= 0; i--) { const z = r.paths.zones[i]; if (ok(z) && G.inside(p, [r.x + z.x, r.y + z.y, z.w, z.h])) out.push({ t: "zone", i }); }
  for (let i = r.patches.length - 1; i >= 0; i--) { const q = r.patches[i]; if (ok(q) && G.inside(p, [r.x + q.x, r.y + q.y, q.w, q.h])) out.push({ t: "patch", i }); }
  return out;
}
const hit = p => hitAll(p)[0] || null;

/** What Alt+click at p picks: the next thing down from the lowest of those picked there, round to the top again. */
function hitBelow(p) {
  const all = hitAll(p);
  if (!all.length) return null;
  const at = all.findLastIndex(h => S.sel.some(s => s.t === h.t && s.i === h.i));
  return all[(at + 1) % all.length];
}

function objOf(r, s) { return listsOf(r)[s.t][s.i]; }

function down(e) {
  canvas.focus();
  canvas.setPointerCapture(e.pointerId);
  const p = world(e);
  S.mouse = p; S.free = e.shiftKey;
  closeMenu();
  if (e.button === 1 || e.button === 2 || S.space) {   // (a right-click that doesn't pan opens the menu, once it's let go)
    S.drag = { pan: [e.clientX, e.clientY, S.cam.x, S.cam.y], menu: e.button === 2 && !S.space && S.mode === "room" && !S.placing && S.tool === "select" };
    return;
  }
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
  if (e.altKey) {   // the next thing down under the pointer (it can be dragged from there)
    e.preventDefault();
    const h = hitBelow(p);
    if (!h) return;
    S.sel = e.shiftKey ? [...S.sel.filter(s => s.t !== h.t || s.i !== h.i), h] : [h];
    status(`Picked ${describe(r, h)}${hitAll(p).length > 1 ? ": Alt+click again for what's under it" : ""}.`, "ok");
    S.drag = { move: S.sel.filter(s => !objOf(r, s).locked).map(s => [s, { ...objOf(r, s) }]), from: p, snap: JSON.stringify(S.draft) };
    refresh();
    return;
  }
  const grab = grabAt(r, p);
  if (grab && grab.edge) { S.drag = { edge: grab.edge, snap: JSON.stringify(S.draft) }; return; }
  if (grab && grab.zone) {
    S.sel = [{ t: "zone", i: grab.zone.i }];
    S.drag = { zone: grab.zone, was: { ...r.paths.zones[grab.zone.i] }, snap: JSON.stringify(S.draft) };
    refresh();
    return;
  }
  if (grab) {
    S.sel = [{ t: "patch", i: grab.patch.i }];
    S.drag = { patch: grab.patch, was: { ...r.patches[grab.patch.i] }, snap: JSON.stringify(S.draft) };
    refresh();
    return;
  }
  const h = hit(p);
  if (!h) { if (!e.shiftKey) S.sel = []; S.drag = { box: [p, p] }; refresh(); return; }
  const one = e.ctrlKey || e.metaKey, unit = one ? [h] : withGroups(r, [h]);   // (its whole group; Ctrl+click: just it)
  const already = S.sel.some(s => s.t === h.t && s.i === h.i), inUnit = s => unit.some(u => u.t === s.t && u.i === s.i);
  if (e.shiftKey) S.sel = already ? S.sel.filter(s => !inUnit(s)) : [...S.sel.filter(s => !inUnit(s)), ...unit];
  else if (!already || one) S.sel = unit;
  S.drag = { move: S.sel.filter(s => !objOf(r, s).locked).map(s => [s, { ...objOf(r, s) }]), from: p, snap: JSON.stringify(S.draft) };   // (locked: stays put)
  refresh();
}

function nearestWall(r, p) {
  const d = { top: Math.abs(p[1] - r.y - G.wallTop(r) / 2), bottom: Math.abs(p[1] - r.y - r.h), left: Math.abs(p[0] - r.x), right: Math.abs(p[0] - r.x - r.w) };
  const best = Object.entries(d).sort((a, b) => a[1] - b[1])[0];
  return best[1] < 60 ? best[0] : null;
}

function move(e) {
  const p = world(e);
  S.mouse = p; S.free = e.shiftKey;
  const d = S.drag;
  if (!d) {
    if (S.mode === "room" && room() && !S.placing) {
      const g = S.tool === "select" && grabAt(room(), p);
      canvas.style.cursor = g ? grabCursor(g) : S.tool === "select" ? "default" : "crosshair";
      const h = S.tool === "select" && !g ? (e.altKey ? hitBelow(p) : hit(p)) : null;   // (outlined: what a click would pick)
      if (JSON.stringify(h) !== JSON.stringify(S.hover) && !document.getElementById("pl-menu")) { S.hover = h; draw(); }
    }
    if (S.placing) draw();
    return;
  }
  if (d.pan) {
    if (Math.hypot(e.clientX - d.pan[0], e.clientY - d.pan[1]) > 4) d.menu = false;   // (it's a pan)
    S.cam.x = d.pan[2] - (e.clientX - d.pan[0]) / S.cam.s; S.cam.y = d.pan[3] - (e.clientY - d.pan[1]) / S.cam.s; draw(); return;
  }
  if (d.box) { d.box[1] = p; draw(); return; }
  const r = room();
  if (d.edge) { resize(r, d.edge, snap(d.edge === "left" || d.edge === "right" ? p[0] : p[1], SNAP.room, e.shiftKey)); d.moved = true; draw(); refreshInspector(); return; }
  if (d.patch) { resizePatch(r.patches[d.patch.i], d.was, d.patch.sides, [p[0] - r.x, p[1] - r.y], e.shiftKey); d.moved = true; draw(); refreshInspector(); return; }
  if (d.zone) { resizePatch(r.paths.zones[d.zone.i], d.was, d.zone.sides, [p[0] - r.x, p[1] - r.y], e.shiftKey); d.moved = true; draw(); refreshInspector(); return; }
  const dx = p[0] - d.from[0], dy = p[1] - d.from[1];
  if (d.room) {
    d.room.x = snap(d.at[0] + dx, SNAP.room, e.shiftKey); d.room.y = snap(d.at[1] + dy, SNAP.room, e.shiftKey);
    d.moved = true; draw(); return;
  }
  if (d.move && d.move.length) {
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
  if (d.menu) { openMenu(e, world(e)); return; }
  const r = room();
  if (d.make) {
    const [a, b] = d.box, x = Math.min(a[0], b[0]) - r.x, y = Math.min(a[1], b[1]) - r.y, w = Math.abs(b[0] - a[0]), h = Math.abs(b[1] - a[1]);
    if (w > 4 && h > 4) {
      const box = { x: snap(x, SNAP.item), y: snap(y, SNAP.item), w: Math.max(8, snap(w, SNAP.item)), h: Math.max(8, snap(h, SNAP.item)) };
      if (d.make === "zone") { edit(() => r.paths.zones.push({ ...box, kind: S.zoneKind })); S.sel = [{ t: "zone", i: r.paths.zones.length - 1 }]; }
      else { edit(() => r.patches.push(newPatch(box))); S.sel = [{ t: "patch", i: r.patches.length - 1 }]; }
    }
    S.tool = "select";
    refresh();
    return;
  }
  if (d.box && r) {
    const [a, b] = d.box, box = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])];
    if (box[2] > 3 && box[3] > 3) {
      const free = o => !o.locked && !o._hidden;   // (locked and hidden things aren't box-picked)
      r.items.forEach((it, i) => { const s = free(it) && G.shapes(r, it); if (s && G.covers(s).some(c => G.overlap(c, box)) && !S.sel.some(x => x.t === "item" && x.i === i)) S.sel.push({ t: "item", i }); });
      if (S.layers.paths) r.paths.zones.forEach((z, i) => {   // a zone only when the box takes in all of it (a big one sits under everything)
        const zx = r.x + z.x, zy = r.y + z.y;
        if (free(z) && zx >= box[0] && zy >= box[1] && zx + z.w <= box[0] + box[2] && zy + z.h <= box[1] + box[3] && !S.sel.some(x => x.t === "zone" && x.i === i)) S.sel.push({ t: "zone", i });
      });
      S.sel = withGroups(r, S.sel);
    }
    refresh();
    return;
  }
  if (d.moved && d.snap) {   // (one undo step for the whole drag)
    S.undo.push(d.snap); S.redo = [];
    changed();
  }
}

/** Double-click a room to edit it: on the plan, or (editing a room) one of the dimmed rooms beside it. */
function dbl(e) {
  if (S.mode !== "plan" && S.mode !== "room") return;
  const p = world(e), cur = S.mode === "room" ? room() : null;
  if (cur && (S.placing || G.inside(p, G.outline(cur)))) return;
  const r = shownRooms().slice().reverse().find(r => r !== cur && G.inside(p, G.outline(r)));
  if (r) setMode("room", S.draft.rooms.indexOf(r));
}

// Each wheel notch zooms by Settings › Floor plan's "Scroll zoom" (per cent, this browser only).
export const ZOOM_STEP = { min: 2, max: 25, default: 8 };
function wheel(e) {
  e.preventDefault();
  closeMenu();
  const b = canvas.getBoundingClientRect(), pc = +remember.get("zoom_step");
  const f = 1 + (pc >= ZOOM_STEP.min && pc <= ZOOM_STEP.max ? pc : ZOOM_STEP.default) / 100;
  zoomAt({ x: e.clientX - b.left, y: e.clientY - b.top }, e.deltaY < 0 ? f : 1 / f);
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
  if (e.key === "Escape" && document.getElementById("pl-menu")) { closeMenu(); return; }
  if (ctrl && (e.code === "BracketRight" || e.code === "BracketLeft")) {   // (by key, not character: Shift changes it)
    e.preventDefault();
    restack(e.code === "BracketRight" ? (e.shiftKey ? "front" : "forward") : (e.shiftKey ? "back" : "backward"));
    return;
  }
  if (e.key === "Escape") { S.placing = null; S.tool = "select"; S.sel = []; refresh(); return; }
  if (e.key === "r" || e.key === "R") {
    e.preventDefault();
    if (S.placing) { turn(S.placing); draw(); return; }
    const items = S.sel.filter(s => s.t === "item");
    if (items.length) edit(() => items.forEach(s => turn(r.items[s.i])));
    return;
  }
  if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); removeSelected(); return; }
  const k = e.key.toLowerCase();
  if (ctrl && k === "c") { e.preventDefault(); S.clip = copyPicked(r); status(`Copied ${S.clip.length}.`, "ok"); return; }
  if (ctrl && k === "d") { e.preventDefault(); duplicateSelected(); return; }
  if (ctrl && k === "v" && S.clip && S.clip.length) { e.preventDefault(); putDown(r, S.clip, S.mouse && [S.mouse[0] - r.x, S.mouse[1] - r.y]); return; }
  if (ctrl && k === "g") { e.preventDefault(); if (e.shiftKey) ungroupSelected(); else groupSelected(); return; }
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
  .pl-tint { display: flex; gap: 6px; align-items: center; }
  .pl-pair { display: flex; gap: 4px; align-items: center; }
  .pl-pair input { flex: 1; min-width: 0; font-variant-numeric: tabular-nums; }
  .pl-tint input { flex: 1; min-width: 0; }
  .pl-field { display: grid; grid-template-columns: 86px minmax(0, 1fr); gap: 6px; align-items: center; font-size: var(--fs-s); color: var(--fg-muted); }
  .pl-field input, .pl-field select { width: 100%; min-width: 0; }
  .pl-buttons { display: flex; flex-wrap: wrap; gap: 6px; }
  .pl-problems { position: absolute; left: 10px; right: 10px; bottom: 10px; z-index: 2; border: 1px solid color-mix(in srgb, var(--caution) 45%, var(--line)); border-radius: 8px;
    background: color-mix(in srgb, var(--bg-1) 92%, transparent); backdrop-filter: blur(6px); font-size: var(--fs-s); max-height: 40%; overflow: auto; }
  .pl-problems summary { padding: 6px 10px; color: var(--caution); }
  .pl-problems ul { margin: 0; padding: 0 10px 10px 28px; display: grid; gap: 3px; }
  .pl-problems button.link { color: var(--fg-muted); text-align: left; white-space: normal; }
  .pl-sidetabs { justify-self: start; }
  .pl-h3-hint { text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--fg-faint); }
  .pl-layers { display: grid; gap: 1px; }
  .pl-layer-row { display: flex; align-items: center; gap: 2px; padding: 0 2px 0 4px; border-radius: var(--radius); }
  .pl-layer-row:hover { background: var(--bg-2); }
  .pl-layer-row.on { background: var(--accent-soft); box-shadow: inset 2px 0 0 var(--accent); }
  .pl-layer-row.off .pl-layer-name { opacity: .45; font-style: italic; }
  .pl-layer-row.drop-above { box-shadow: inset 0 2px 0 var(--accent); }
  .pl-layer-row.drop-below { box-shadow: inset 0 -2px 0 var(--accent); }
  .pl-grip { cursor: grab; color: var(--fg-faint); font-size: 10px; letter-spacing: -2px; padding-right: 2px; }
  .pl-layer-name { flex: 1; min-width: 0; justify-content: flex-start; height: 26px; border: 0; background: none; padding: 0 2px; overflow: hidden; text-overflow: ellipsis; }
  .pl-layer-name:hover { background: none; }
  .pl-tag { font-size: 10px; color: var(--fg-muted); border: 1px solid var(--line-2); border-radius: 4px; padding: 0 4px; }
  .pl-flag { width: 22px; height: 22px; padding: 0; border: 0; background: none; color: var(--fg-muted); opacity: .3; }
  .pl-flag:hover { background: var(--bg-3); }
  .pl-layer-row:hover .pl-flag { opacity: .75; }
  .pl-flag.set, .pl-layer-row:hover .pl-flag.set { opacity: 1; color: var(--accent-strong); }
  .pl-ico { display: inline-flex; }
  .pl-layer { display: flex; gap: 4px; }
  .pl-layer button { font-size: 15px; }
  .pl-hidden { color: var(--caution); }
  .pl-menu { position: absolute; z-index: 5; min-width: 230px; max-width: 340px; max-height: 70%; overflow: auto; padding: 4px; display: grid;
    border-radius: 8px; background: var(--bg-3); border: 1px solid var(--line-2); box-shadow: var(--shadow); }
  .pl-menu-head { padding: 4px 8px; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .1em; color: var(--fg-muted); }
  .pl-menu-row { display: grid; grid-template-columns: 16px minmax(0, 1fr) auto; gap: 6px; justify-content: stretch; text-align: left; height: 28px; padding: 0 8px; border: 0; background: none; }
  .pl-menu-row span { overflow: hidden; text-overflow: ellipsis; }
  .pl-menu-row:hover { background: var(--bg-2); }
  .pl-menu-row.on { color: var(--accent-strong); }
  .pl-menu-row kbd { font: inherit; font-size: var(--fs-xs); color: var(--fg-muted); }
  .pl-menu-tick { text-align: center; }
  .pl-menu-sep { height: 1px; margin: 4px 0; background: var(--line); }
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
