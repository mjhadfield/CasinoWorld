// Tables: design table styles and place them on the floor's tables. The kinds of table (table_styles.KINDS: Card
// Games, Roulette, Craps) are in the top bar, each with its own styles, parts and placement. Styles live on the server
// (table_styles.py); saving one restyles every table using it straight away. House is the default every table of
// its kind uses unless it's given another; the presets are built in (save a copy to change one).
// Three columns: styles and placement | the table, fitted to the window | the design's controls.
import { render, loadAssets, clone, getKey, setKey, distance, GAMES, KINDS, BACK_MAIN } from "/table-styles-ui/render.js";

const BASE = "/table-styles-ui/";
const KIND_NAMES = { cards: "card table", roulette: "roulette table", craps: "craps table" };
let ctx = null;            // the shell's helpers, with $ looking in this section's view and top bar
let kind = "cards";        // which kind of table's styles are shown
let data = null;           // GET /api/table-styles?kind=
let cur = null;            // the style being edited: {id, name, design, builtin}
let saved = "";            // its design as last saved, to tell when it's changed
const VIEW = { cards: { game: "tcp", view: "seated", play: true, lit: true, fixed: false },
  roulette: { view: "table", play: true }, craps: { view: "table", play: true } };
let view = VIEW.cards;     // the stage's settings, kept for each kind
let placing = {};          // table id -> style id ("" for the default), as edited
let placingDefault = "house";
const q = () => "?kind=" + kind;

export function init(h) {
  // The shell's el() sets properties, so attributes like aria-label go through setAttribute here.
  const el = (tag, props = {}, ...kids) => {
    const attrs = Object.entries(props).filter(([k]) => k.includes("-"));
    const node = h.el(tag, Object.fromEntries(Object.entries(props).filter(([k]) => !k.includes("-"))), ...kids);
    for (const [k, v] of attrs) node.setAttribute(k, v);
    return node;
  };
  ctx = { ...h, el, $: s => h.view.querySelector(s) || h.top.querySelector(s) };
}

export async function load() {
  const { status, view: host } = ctx;
  try {
    host.textContent = "Loading…";
    await loadAssets(BASE);
    build();
    try { const k = ctx.remember.get("tables.kind"); if (KINDS[k]) kind = k; } catch (e) { /* (Card Games) */ }
    setKind(kind);
  } catch (e) { host.textContent = "The designer's pictures didn't load: " + e.message; return; }
  await refresh(cur ? cur.id : null);
  status("Table styles loaded.", "ok");
}

export function shown(on) { if (on && cur) drawStage(); }

function setKind(k) {
  kind = k;
  view = VIEW[k];
  ctx.top.querySelectorAll("#ts-kinds button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.kind === k)));
  const cards = k === "cards";
  for (const sel of ["#ts-games", "#ts-lit-box", "#ts-fixed-box"]) ctx.$(sel).hidden = !cards;
  ctx.$("#ts-default-label").textContent = `Default for every ${KIND_NAMES[k]}`;
  ctx.$("#ts-play-label").textContent = cards ? "Hand in play" : "Bets down";
  ctx.$("#ts-play").checked = view.play;
  ctx.$("#ts-views").replaceChildren();
  for (const [id, [label]] of Object.entries(KINDS[k].views)) segButton("#ts-views", id, label, () => { view.view = id; drawStage(); });
  buildSlots();
}

async function refresh(keep) {
  data = await ctx.api("GET", "/api/table-styles" + q());
  placing = { ...data.tables };
  placingDefault = data.default;
  pick(keep && data.styles[keep] ? keep : data.default);
}

function pick(id) {
  const s = data.styles[id];
  cur = { id, name: s.name, design: clone(s.design), builtin: s.builtin };
  saved = JSON.stringify(s.design);
  const first = Object.entries(data.games).find(([tid]) => (placing[tid] || placingDefault) === id);
  if (first && kind === "cards") view.game = first[1].layout;
  drawAll();
}

// ---------------------------------------------------------------- building the section
function build() {
  const { el, view: host, top } = ctx;
  // the top bar: the kinds, and the card games
  const kinds = el("div", { className: "seg", id: "ts-kinds", role: "group", "aria-label": "Kind of table" },
    ...[["cards", "Card Games"], ["roulette", "Roulette"], ["craps", "Craps"]].map(([k, label]) => {
      const b = el("button", { type: "button" }, label);
      b.dataset.kind = k;
      b.addEventListener("click", () => switchKind(b));
      return b;
    }));
  top.replaceChildren(kinds, el("span", { className: "sep" }), el("div", { className: "seg", id: "ts-games", role: "group", "aria-label": "Game" }));
  for (const [id, label] of GAMES) segButton("#ts-games", id, label, () => { view.game = id; drawStage(); syncButtons(); });

  host.textContent = "";
  host.append(el("div", { className: "wb", style: "grid-template-columns: 330px minmax(0, 1fr) 400px" },
    el("div", { className: "panel" },
      el("div", { className: "ph" }, "Styles", el("span", { className: "grow" }), el("button", { id: "ts-new", type: "button", className: "ghost", title: "A new style, starting from the one shown" }, "+ New")),
      el("div", { className: "ts-list", id: "ts-list" }),
      el("div", { className: "ph", style: "border-top: 1px solid var(--line)" }, "Placement", el("span", { className: "grow" }),
        el("button", { id: "ts-place-save", type: "button", className: "primary" }, "Save")),
      el("div", { className: "pb" },
        el("label", { className: "field ts-default" }, el("span", { id: "ts-default-label" }, "Default for every card table"), el("select", { id: "ts-default" })),
        el("div", { id: "ts-tables" }))),
    el("div", { className: "stagebox", id: "ts-box" },
      el("canvas", { id: "ts-stage" }),
      el("div", { className: "float tl" },
        el("div", { className: "seg", id: "ts-views", role: "group", "aria-label": "View" }),
        toggle("ts-play", "Hand in play", "play"), toggle("ts-lit", "Jackpot lit", "lit"), toggle("ts-fixed", "Fixed layout", "fixed")),
      el("div", { className: "float bl ts-warn", id: "ts-warn", hidden: true }),
      el("div", { className: "float br hint", id: "ts-legend", hidden: true }, "Dashed: every spot, card and machine where the game puts it. Styles never move them.")),
    el("div", { className: "panel" },
      el("div", { className: "ph" }, "Design", el("span", { className: "grow" }),
        el("button", { id: "ts-revert", type: "button", className: "ghost" }, "Undo changes"),
        el("button", { id: "ts-delete", type: "button", className: "ghost danger" }, "Delete")),
      el("div", { className: "ts-head" },
        el("div", { className: "controls" }, el("input", { id: "ts-name", maxLength: 40, "aria-label": "Name", style: "flex: 1" }),
          el("button", { id: "ts-copy", type: "button" }, "Save as new"),
          el("button", { id: "ts-save", type: "button", className: "primary" }, "Save")),
        el("p", { className: "hint", id: "ts-note" })),
      el("div", { className: "pb", id: "ts-slots" }))),
    el("style", {}, CSS));

  ctx.$("#ts-name").addEventListener("input", e => { cur.name = e.target.value; syncButtons(); });
  ctx.$("#ts-save").addEventListener("click", () => save(false));
  ctx.$("#ts-copy").addEventListener("click", () => save(true));
  ctx.$("#ts-revert").addEventListener("click", () => pick(cur.id));
  ctx.$("#ts-delete").addEventListener("click", remove);
  ctx.$("#ts-new").addEventListener("click", () => {
    cur = { id: null, name: "New style", design: clone(cur.design), builtin: false };
    saved = "";
    drawAll();
    ctx.$("#ts-name").focus(); ctx.$("#ts-name").select();
  });
  ctx.$("#ts-default").addEventListener("change", e => { placingDefault = e.target.value; drawPlacement(); });
  ctx.$("#ts-place-save").addEventListener("click", savePlacement);
  let t;
  new ResizeObserver(() => { clearTimeout(t); t = setTimeout(() => { if (!host.hidden) drawStage(); }, 60); }).observe(ctx.$("#ts-box"));
}

const CSS = `
  .ts-list { padding: 6px; display: grid; gap: 1px; flex: none; max-height: 40%; overflow-y: auto; }
  .ts-style { justify-content: flex-start; flex-wrap: wrap; width: 100%; height: auto; min-height: 30px; padding: 4px 8px; gap: 4px 6px; border: 0; background: none; text-align: left; }
  .ts-style:hover { background: var(--bg-2); }
  .ts-style > span:first-child { flex: 1 1 auto; font-weight: 600; font-size: var(--fs-s); }
  .ts-style.picked { background: var(--accent-soft); box-shadow: inset 2px 0 0 var(--accent); }
  .ts-default { padding: var(--pad); border-bottom: 1px solid var(--line); }
  #ts-tables .ts-table { display: grid; grid-template-columns: minmax(0, 1fr) 140px auto; gap: 6px; align-items: center; padding: 3px var(--pad); font-size: var(--fs-s); }
  #ts-tables .ts-table small { color: var(--fg-faint); }
  #ts-tables .ts-table select { width: 100%; height: 26px; }
  #ts-box canvas#ts-stage { display: block; border-radius: 4px; }
  .ts-warn { color: var(--danger); font-size: var(--fs-s); padding: 4px 8px; }
  #ts-legend { padding: 4px 8px; }
  .ts-toggle { display: inline-flex; gap: 4px; align-items: center; font-size: var(--fs-s); color: var(--fg-muted); padding: 0 4px; white-space: nowrap; }
  .ts-head { padding: var(--pad); display: grid; gap: 6px; border-bottom: 1px solid var(--line); flex: none; }
  .ts-field { display: grid; gap: 4px; }
  .ts-field > .hint { font-size: var(--fs-xs); }
  .ts-field .seg { flex-wrap: wrap; }
  .ts-swatches { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
  .ts-sw { width: 24px; height: 24px; border-radius: 5px; border: 1px solid var(--line-2); padding: 0; }
  .ts-sw[aria-pressed="true"] { box-shadow: 0 0 0 2px var(--bg-1), 0 0 0 3.5px var(--accent); }
  .ts-field input[type="range"] { width: 100%; }
  .ts-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .ts-compare figure { margin: 0; padding: 4px; cursor: pointer; border: 1px solid var(--line); border-radius: var(--radius); display: grid; gap: 3px; background: var(--bg-2); }
  .ts-compare figure[aria-pressed="true"] { border-color: var(--accent); }
  .ts-compare canvas { display: block; width: 100%; height: auto; border-radius: 3px; }
  .ts-compare figcaption { font-size: var(--fs-xs); }
`;

async function switchKind(b) {
  if (b.dataset.kind === kind) return;
  if (dirty() && !confirmLeave(b)) return;
  setKind(b.dataset.kind);
  ctx.remember.set("tables.kind", kind);
  cur = null;
  try { await refresh(null); } catch (e) { ctx.status(e.message, "warn"); }
}

function toggle(id, label, key) {
  const { el } = ctx;
  const box = el("input", { type: "checkbox", id, checked: view[key] });
  box.addEventListener("change", () => { view[key] = box.checked; drawStage(); });
  return el("label", { className: "ts-toggle", id: id + "-box" }, box, el("span", { id: id + "-label" }, label));
}

function compareFig(mode, title, blurb) {
  const { el } = ctx;
  const fig = el("figure", { tabIndex: 0, role: "button", title: blurb }, el("canvas", { id: "ts-cmp-" + mode }), el("figcaption", {}, title));
  fig.dataset.tray = mode;
  const choose = () => change("tray.mode", mode);
  fig.addEventListener("click", choose);
  fig.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); } });
  return fig;
}

function segButton(sel, value, label, onClick) {
  const b = ctx.el("button", { type: "button" }, label);
  b.dataset.v = value;
  b.addEventListener("click", onClick);
  ctx.$(sel).append(b);
}

// The design's controls, one group per part of the table (render.js KINDS[kind].slots). The card tables' chip tray
// group also holds the two trays side by side, to pick one by eye.
function buildSlots() {
  const { el, $ } = ctx;
  const host = $("#ts-slots");
  host.replaceChildren();
  for (const slot of KINDS[kind].slots) {
    const group = el("details", { className: "grp-c", open: ["felt", "rail", "tray", "numbers", "print"].includes(slot.id) && (kind !== "cards" || slot.id !== "print") },
      el("summary", {}, slot.label, slot.hint ? el("span", { className: "hint" }, slot.hint) : null));
    group.dataset.slot = slot.id;
    const body = el("div", { className: "grp-b" });
    for (const c of slot.ctl) {
      const box = el("div", { className: "ts-field" }, c.label ? el("span", { className: "hint" }, c.label) : null);
      if (c.type === "seg") {
        const seg = el("div", { className: "seg wrap" });
        seg.dataset.key = c.key;
        for (const [v, label] of c.options) {
          const b = el("button", { type: "button" }, label);
          b.dataset.v = v;
          b.addEventListener("click", () => change(c.key, v));
          seg.append(b);
        }
        box.append(seg);
      } else if (c.type === "swatch") {
        const sw = el("div", { className: "ts-swatches" });
        sw.dataset.key = c.key;
        for (const [name, v] of c.options) {
          const b = el("button", { type: "button", className: "ts-sw", title: name, "aria-label": name });
          b.style.background = v;
          b.dataset.v = v;
          b.addEventListener("click", () => change(c.key, v));
          sw.append(b);
        }
        if (c.custom) {
          const inp = el("input", { type: "color", title: "Any colour", "aria-label": (c.label || slot.label) + ": any colour" });
          inp.addEventListener("input", () => change(c.key, inp.value));
          sw.append(inp);
        }
        box.append(sw);
      } else if (c.type === "range") {
        const r = el("input", { type: "range", min: 0, max: 1, step: 0.05 });
        r.dataset.key = c.key;
        r.addEventListener("input", () => change(c.key, +r.value));
        box.append(r);
      }
      body.append(box);
    }
    if (kind === "cards" && slot.id === "tray") body.append(el("div", { className: "ts-compare" },
      compareFig("ledge", "Dealer's ledge", "The rail sweeps across the bay; the tray is cut into it."),
      compareFig("sunk", "Sunk in", "Where the tray has always been, with a metal lip.")));
    group.append(body);
    group.addEventListener("toggle", () => { if (group.open && slot.id === "tray") drawStage(); });
    host.append(group);
  }
}

function change(key, value) {
  setKey(cur.design, key, value);
  drawAll();
}

// ---------------------------------------------------------------- drawing it
function drawAll() {
  drawList();
  drawPlacement();
  drawControls();
  drawStage();
}

function drawList() {
  const { $, el } = ctx;
  const list = $("#ts-list");
  list.replaceChildren();
  const ids = Object.keys(data.styles).sort((a, b) => (data.styles[a].builtin - data.styles[b].builtin) || (a === "house" ? -1 : b === "house" ? 1 : data.styles[a].name.localeCompare(data.styles[b].name)));
  for (const id of ids) {
    const s = data.styles[id];
    const using = Object.keys(data.games).filter(t => (data.tables[t] || data.default) === id).length;
    const b = el("button", { type: "button", className: "ts-style" + (cur && cur.id === id ? " picked" : "") },
      el("span", {}, s.name),
      id === data.default ? el("span", { className: "tag gold" }, "default") : null,
      s.builtin ? el("span", { className: "tag" }, "built in") : null,
      using ? el("span", { className: "tag ok" }, `${using} table${using > 1 ? "s" : ""}`) : null);
    b.addEventListener("click", () => {
      if (dirty() && !confirmLeave(b)) return;
      pick(id);
    });
    list.append(b);
  }
  if (cur && !cur.id) list.append(el("div", { className: "ts-style picked" }, el("span", {}, cur.name || "New style"), el("span", { className: "tag warn" }, "not saved")));
}

// Leaving unsaved changes takes a second click (the page has no dialogs).
function confirmLeave(button) {
  if (button.dataset.sure) return true;
  button.dataset.sure = "1";
  ctx.status("This style has unsaved changes: click again to leave them.", "warn");
  setTimeout(() => delete button.dataset.sure, 4000);
  return false;
}

function drawPlacement() {
  const { $, el } = ctx;
  const options = (sel, value, withDefault) => {
    sel.replaceChildren();
    if (withDefault) sel.append(el("option", { value: "" }, `Default (${data.styles[placingDefault].name})`));
    for (const [id, s] of Object.entries(data.styles)) sel.append(el("option", { value: id }, s.name));
    sel.value = value;
  };
  options($("#ts-default"), placingDefault, false);
  const host = $("#ts-tables");
  host.replaceChildren();
  for (const [tid, t] of Object.entries(data.games)) {
    const sel = el("select", { "aria-label": `${t.name} (${tid})` });
    options(sel, placing[tid] || "", true);
    sel.addEventListener("change", () => { if (sel.value) placing[tid] = sel.value; else delete placing[tid]; });
    const show = el("button", { type: "button", className: "ghost sq", title: "Show this game", hidden: kind !== "cards", style: "height: 24px; width: 24px" }, "▸");
    show.addEventListener("click", () => { view.game = t.layout; drawStage(); syncButtons(); });
    host.append(el("label", { className: "ts-table" }, el("span", {}, t.name, el("small", {}, " " + tid)), sel, show));
  }
}

function drawControls() {
  const { $ } = ctx;
  $("#ts-name").value = cur.name;
  ctx.view.querySelectorAll("#ts-slots [data-key]").forEach(node => {
    const v = getKey(cur.design, node.dataset.key);
    if (node.type === "range") node.value = v;
    else node.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
    const inp = node.querySelector('input[type="color"]');
    if (inp && /^#[0-9a-f]{6}$/i.test(v)) inp.value = v;
  });
  syncButtons();
}

function dirty() { return cur && (!cur.id || JSON.stringify(cur.design) !== saved || cur.name !== data.styles[cur.id]?.name); }

function syncButtons() {
  const { $ } = ctx;
  const ch = dirty();
  $("#ts-save").disabled = cur.builtin || !ch;
  $("#ts-revert").disabled = !ch || !cur.id;
  $("#ts-delete").disabled = !cur.id || cur.builtin || cur.id === "house";
  $("#ts-note").textContent = cur.builtin ? "A built-in style: change it, then Save as new to keep your version."
    : !cur.id ? "Not saved yet: Save adds it to the styles."
    : cur.id === "house" ? `The casino's own ${KIND_NAMES[kind]} style: saving restyles every table that uses it.`
    : "Saving restyles every table that uses it straight away.";
  ctx.top.querySelectorAll("#ts-games button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === view.game)));
  ctx.view.querySelectorAll("#ts-views button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === view.view)));
  if (kind === "cards") ctx.view.querySelectorAll(".ts-compare figure").forEach(f => f.setAttribute("aria-pressed", String(f.dataset.tray === cur.design.tray.mode)));
}

function viewRect() {
  const views = KINDS[kind].views;
  if (view.view !== "seat") return (views[view.view] || Object.values(views)[0])[1];
  return [24.5 - 41, -100, 82, 108];   // seat 2's column
}

// The table fills its box: as wide as it can be without being taller than the box (render() sizes from the width).
function fit(canvas, rect) {
  const box = ctx.$("#ts-box").getBoundingClientRect();
  const w = Math.max(200, Math.min(box.width - 32, (box.height - 32) * rect[2] / rect[3]));
  canvas.style.width = Math.floor(w) + "px";
}

function drawStage() {
  const { $ } = ctx;
  if (!cur || ctx.view.hidden) return;
  const rect = viewRect(), canvas = $("#ts-stage");
  fit(canvas, rect);
  if (kind !== "cards") {
    render(canvas, cur.design, KINDS[kind].game, rect, { play: view.play });
    $("#ts-legend").hidden = true;
    $("#ts-warn").hidden = true;
    syncButtons();
    return;
  }
  render(canvas, cur.design, view.game, rect, { play: view.play, lit: view.lit, fixed: view.fixed });
  if (ctx.view.querySelector('[data-slot="tray"]')?.open) for (const mode of ["ledge", "sunk"]) {
    render($("#ts-cmp-" + mode), { ...cur.design, tray: { ...cur.design.tray, mode } }, view.game, KINDS.cards.views.bay[1], { play: view.play });
  }
  $("#ts-legend").hidden = !view.fixed;
  const warn = $("#ts-warn");
  warn.hidden = distance(BACK_MAIN[cur.design.back], cur.design.felt.colour) >= 22;
  warn.textContent = "This card back is close to the felt's colour: face-down cards may blend in.";
  syncButtons();
}

// ---------------------------------------------------------------- saving
function newId(name) {
  const base = (name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "style").slice(0, 26);
  let id = base, n = 2;
  while (data.styles[id]) id = `${base}_${n++}`;
  return id;
}

async function save(asNew) {
  const { api, status } = ctx;
  const name = cur.name.trim();
  if (!name) { status("Give the style a name first.", "warn"); ctx.$("#ts-name").focus(); return; }
  let id = cur.id;
  let saveName = name;
  if (asNew || !id || cur.builtin) {
    if (asNew && id && name === data.styles[id]?.name) saveName = name + " copy";
    id = newId(saveName);
  }
  try {
    data = { ...data, ...(await api("PUT", `/api/table-styles/styles/${id}${q()}`, { name: saveName, design: cur.design })) };
    status(`Saved "${saveName}". Tables using it are restyled.`, "ok");
    await refresh(id);
  } catch (e) { status(e.message, "warn"); }
}

async function remove() {
  const { api, status } = ctx;
  const b = ctx.$("#ts-delete");
  if (!b.dataset.sure) {
    b.dataset.sure = "1";
    b.textContent = "Delete: sure?";
    setTimeout(() => { delete b.dataset.sure; b.textContent = "Delete"; }, 4000);
    return;
  }
  delete b.dataset.sure;
  b.textContent = "Delete";
  try {
    await api("DELETE", `/api/table-styles/styles/${cur.id}${q()}`);
    status(`Deleted "${cur.name}". Its tables are back on the default.`, "ok");
    cur = null;
    await refresh(null);
  } catch (e) { status(e.message, "warn"); }
}

async function savePlacement() {
  const { api, status } = ctx;
  const tables = {};
  for (const tid of Object.keys(data.games)) tables[tid] = placing[tid] || null;
  try {
    await api("PUT", "/api/table-styles/tables" + q(), { tables, default: placingDefault });
    status("Placement saved: the floor's tables are restyled.", "ok");
    await refresh(cur && cur.id);
  } catch (e) { status(e.message, "warn"); }
}
