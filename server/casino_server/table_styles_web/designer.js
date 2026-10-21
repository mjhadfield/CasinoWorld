// The admin page's Tables tab: design table styles and place them on the floor's card tables.
// Styles live on the server (table_styles.py); saving one restyles every table using it straight away.
// House is the default every card table uses unless it's given another; the four mockup presets are built in
// (save a copy to change one). Roulette and Craps keep their own look and aren't listed.
import { render, loadAssets, clone, getKey, setKey, distance, SLOTS, GAMES, VIEWS, BACK_MAIN } from "./render.js";

const BASE = "/table-styles-ui/";
let ctx = null;            // {$, el, api, status} from the admin page
let data = null;           // GET /api/table-styles
let cur = null;            // the style being edited: {id, name, design, builtin}
let saved = "";            // its design as last saved, to tell when it's changed
let view = { game: "tcp", view: "seated", play: true, lit: true, fixed: false };
let placing = {};          // table id -> style id ("" for the default), as edited
let placingDefault = "house";

export function init(c) {
  // The admin page's el() sets properties, so attributes like aria-label go through setAttribute here.
  const el = (tag, props = {}, ...kids) => {
    const attrs = Object.entries(props).filter(([k]) => k.includes("-"));
    const node = c.el(tag, Object.fromEntries(Object.entries(props).filter(([k]) => !k.includes("-"))), ...kids);
    for (const [k, v] of attrs) node.setAttribute(k, v);
    return node;
  };
  ctx = { ...c, el };
}

export async function load() {
  const { $, status } = ctx;
  const app = $("#tables-app");
  try { if (!app.dataset.built) { app.textContent = "Loading…"; await loadAssets(BASE); build(app); app.dataset.built = "1"; } }
  catch (e) { app.textContent = "The designer's pictures didn't load: " + e.message; return; }
  await refresh(cur ? cur.id : null);
  status("Table styles loaded.", "ok");
}

async function refresh(keep) {
  data = await ctx.api("GET", "/api/table-styles");
  placing = { ...data.tables };
  placingDefault = data.default;
  pick(keep && data.styles[keep] ? keep : data.default);
}

function pick(id) {
  const s = data.styles[id];
  cur = { id, name: s.name, design: clone(s.design), builtin: s.builtin };
  saved = JSON.stringify(s.design);
  const first = Object.entries(data.games).find(([tid]) => (placing[tid] || placingDefault) === id);
  if (first) view.game = first[1].layout;
  drawAll();
}

// ---------------------------------------------------------------- building the tab
function build(app) {
  const { el } = ctx;
  app.textContent = "";
  app.append(
    el("div", { className: "ts" },
      el("div", { className: "ts-side pane" },
        el("h2", {}, "Styles", el("button", { id: "ts-new", type: "button", title: "A new style, starting from the one shown" }, "New style")),
        el("div", { className: "card ts-list", id: "ts-list" }),
        el("h2", {}, "Placement"),
        el("div", { className: "card ts-place" },
          el("label", { className: "field" }, el("span", {}, "Default for every card table"), el("select", { id: "ts-default" })),
          el("div", { id: "ts-tables", className: "ts-tables" }),
          el("div", { className: "controls" }, el("button", { id: "ts-place-save", type: "button", className: "primary" }, "Save placement")))),
      el("div", { className: "ts-stage pane" },
        el("div", { className: "seg", id: "ts-games", role: "group", "aria-label": "Game" }),
        el("div", { className: "controls" },
          el("div", { className: "seg", id: "ts-views", role: "group", "aria-label": "View" }),
          toggle("ts-play", "Hand in play", "play"), toggle("ts-lit", "Jackpot lit", "lit"), toggle("ts-fixed", "Fixed layout", "fixed")),
        el("div", { className: "ts-canvas" }, el("canvas", { id: "ts-stage" }), el("div", { className: "ts-warn", id: "ts-warn", hidden: true })),
        el("p", { className: "hint", id: "ts-legend", hidden: true }, "Dashed: every spot, card and machine where the game puts it. Styles never move them."),
        el("div", { className: "ts-compare" },
          compareFig("ledge", "Dealer's ledge", "The rail sweeps across the bay; the tray is cut into it."),
          compareFig("sunk", "Sunk in", "Where the tray has always been, with a metal lip."))),
      el("div", { className: "ts-ctl pane" },
        el("h2", {}, "Design"),
        el("div", { className: "card" },
          el("label", { className: "field" }, el("span", {}, "Name"), el("input", { id: "ts-name", maxLength: 40 })),
          el("p", { className: "hint", id: "ts-note" }),
          el("div", { className: "controls" },
            el("button", { id: "ts-save", type: "button", className: "primary" }, "Save"),
            el("button", { id: "ts-copy", type: "button" }, "Save as new"),
            el("button", { id: "ts-revert", type: "button" }, "Undo changes"),
            el("button", { id: "ts-delete", type: "button" }, "Delete"))),
        el("div", { className: "card ts-slots", id: "ts-slots" }))));

  for (const [id, label] of GAMES) segButton("#ts-games", id, label, () => { view.game = id; drawAll(); });
  for (const [id, [label]] of Object.entries(VIEWS)) segButton("#ts-views", id, label, () => { view.view = id; drawAll(); });
  buildSlots();
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
  window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => { if (ctx.$("#tab-tables").classList.contains("on")) drawStage(); }, 150); });
}

function toggle(id, label, key) {
  const { el } = ctx;
  const box = el("input", { type: "checkbox", id, checked: view[key] });
  box.addEventListener("change", () => { view[key] = box.checked; drawStage(); });
  return el("label", { className: "ts-toggle" }, box, " " + label);
}

function compareFig(mode, title, blurb) {
  const { el } = ctx;
  const fig = el("figure", { className: "card", tabIndex: 0, role: "button" }, el("canvas", { id: "ts-cmp-" + mode }),
    el("figcaption", {}, el("b", {}, title), " ", el("span", { className: "hint" }, blurb)));
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

// The design's controls, one group per part of the table (render.js SLOTS, as on the mockup).
function buildSlots() {
  const { el, $ } = ctx;
  const host = $("#ts-slots");
  for (const slot of SLOTS) {
    const group = el("details", { className: "ts-slot", open: ["felt", "rail", "tray"].includes(slot.id) },
      el("summary", {}, slot.label, slot.hint ? el("span", { className: "hint" }, " · " + slot.hint) : null));
    group.dataset.slot = slot.id;
    for (const c of slot.ctl) {
      const box = el("div", { className: "ts-field" }, c.label ? el("span", { className: "hint" }, c.label) : null);
      if (c.type === "seg") {
        const seg = el("div", { className: "seg" });
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
      group.append(box);
    }
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

// Leaving unsaved changes takes a second click (the admin page has no dialogs).
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
    const show = el("button", { type: "button", className: "icon", title: "Preview this game" }, "▸");
    show.addEventListener("click", () => { view.game = t.layout; drawStage(); syncButtons(); });
    host.append(el("label", { className: "ts-table" }, el("span", {}, t.name, el("small", { className: "hint" }, " " + tid)), sel, show));
  }
}

function drawControls() {
  const { $ } = ctx;
  $("#ts-name").value = cur.name;
  document.querySelectorAll("#ts-slots [data-key]").forEach(node => {
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
    : cur.id === "house" ? "House is the casino's own style. Saving it restyles every table that uses it straight away."
    : "Saving restyles every table that uses it straight away.";
  document.querySelectorAll("#ts-games button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === view.game)));
  document.querySelectorAll("#ts-views button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === view.view)));
  document.querySelectorAll(".ts-compare figure").forEach(f => f.setAttribute("aria-pressed", String(f.dataset.tray === cur.design.tray.mode)));
}

function viewRect() {
  if (view.view !== "seat") return VIEWS[view.view][1];
  return [24.5 - 41, -100, 82, 108];   // seat 2's column
}

function drawStage() {
  const { $ } = ctx;
  if (!cur) return;
  render($("#ts-stage"), cur.design, view.game, viewRect(), { play: view.play, lit: view.lit, fixed: view.fixed });
  for (const mode of ["ledge", "sunk"]) {
    render($("#ts-cmp-" + mode), { ...cur.design, tray: { ...cur.design.tray, mode } }, view.game, VIEWS.bay[1], { play: view.play });
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
    data = { ...data, ...(await api("PUT", `/api/table-styles/styles/${id}`, { name: saveName, design: cur.design })) };
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
    await api("DELETE", `/api/table-styles/styles/${cur.id}`);
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
    await api("PUT", "/api/table-styles/tables", { tables, default: placingDefault });
    status("Placement saved: the floor's tables are restyled.", "ok");
    await refresh(cur && cur.id);
  } catch (e) { status(e.message, "warn"); }
}
