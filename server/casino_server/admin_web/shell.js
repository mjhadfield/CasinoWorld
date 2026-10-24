// The admin page's shell: the section menu, the top bar, the status line and the Display menu. Each section is a
// module loaded the first time it opens. It gets a view (its workbench) and a strip of the top bar for its own
// controls, plus the helpers below. The route is the hash: #<section>[/...], e.g. #design/<design>/<step>.
//
// A section module exports init(h) (h: the helpers, h.view, h.top), load() (first open), and optionally
// shown(on) (opened or left: start and stop polling).

export const $ = s => document.querySelector(s);
export const el = (tag, props = {}, ...kids) => {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...kids.filter(k => k !== null && k !== undefined && k !== false));
  return e;
};
export const money = p => (p < 0 ? "−" : "") + "£" + (Math.abs(p) / 100).toLocaleString("en-GB", {minimumFractionDigits: Math.abs(p) % 100 ? 2 : 0, maximumFractionDigits: 2});
export const signed = p => (p > 0 ? "+" : "") + money(p);

let toastTimer = null;
export function status(text, kind = "") {
  const s = $("#status");
  s.textContent = text; s.className = kind;
  document.querySelector(".toast")?.remove();
  clearTimeout(toastTimer);
  if (kind === "warn") {
    const t = el("div", {className: "toast", role: "alert", textContent: text});
    document.body.append(t);
    toastTimer = setTimeout(() => t.remove(), 7000);
  }
}

export async function api(method, url, body, raw) {
  const r = await fetch(url, {method, body: raw ? body : body === undefined ? undefined : JSON.stringify(body),
                              headers: raw ? {} : {"Content-Type": "application/json"}});
  const text = await r.text();
  let json = null; try { json = JSON.parse(text); } catch (e) {}
  if (!r.ok) throw new Error((json && json.detail) || text || r.statusText);
  return json;
}

// An ⓘ that shows its text on hover: what used to be a section's intro paragraph.
export function info(tip, left) {
  const s = el("span", {className: "info" + (left ? " left" : ""), textContent: "i", tabIndex: 0});
  s.dataset.tip = tip; s.setAttribute("aria-label", tip);
  return s;
}

export const remember = {
  get: k => { try { return localStorage.getItem("cw.admin." + k); } catch (e) { return null; } },
  set: (k, v) => { try { localStorage.setItem("cw.admin." + k, v); } catch (e) {} },
};

// ---------------------------------------------------------------- sections
const SECTIONS = {
  plan: {title: "Floor plan", src: "./plan/plan.js"},
  tables: {title: "Tables", src: "./tables/designer.js"},
  design: {title: "Slot design", src: "./design/wizard.js"},
  slots: {title: "Slots", src: "./sections/slots.js"},
  npcs: {title: "NPCs", src: "./sections/npcs.js"},
  players: {title: "Players", src: "./sections/players.js"},
  stats: {title: "Player stats", src: "./sections/stats.js"},
  sounds: {title: "Sounds", src: "./sections/sounds.js"},
  settings: {title: "Settings", src: "./sections/settings.js"},
};
const DEFAULT = "plan";
const open = {};     // key -> {mod, view, top} once loaded
let current = null;

function section(key) {
  if (open[key]) return open[key];
  const view = el("section", {className: "view", id: "view-" + key, hidden: true});
  const top = el("div", {className: "top-ctl", id: "top-" + key, hidden: true});
  $("#views").append(view); $("#top-ctl").append(top);
  const entry = open[key] = {view, top, mod: null};
  entry.ready = import(SECTIONS[key].src).then(async mod => {
    entry.mod = mod;
    mod.init({$, el, api, status, money, signed, info, remember, view, top});
    await mod.load();
  }).catch(e => { console.error(e); status(`Couldn't load ${SECTIONS[key].title}: ${e.message}`, "warn"); });
  return entry;
}

function route() {
  const top = location.hash.slice(1).split("/")[0];
  const key = SECTIONS[top] ? top : DEFAULT;
  if (key === current) return;
  const was = current && open[current];
  if (was) { was.view.hidden = true; was.top.hidden = true; was.mod?.shown?.(false); }
  current = key;
  const s = section(key);
  s.view.hidden = false; s.top.hidden = false;
  $("#title").textContent = SECTIONS[key].title;
  document.title = SECTIONS[key].title + " · Casino World Admin";
  for (const a of document.querySelectorAll("#nav a")) {
    if (a.dataset.view === key) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  s.ready.then(() => { if (current === key) s.mod?.shown?.(true); });
}
window.addEventListener("hashchange", route);

// ---------------------------------------------------------------- Display: colours, density, the menu's width
function setDisplay(k, v) { document.documentElement.dataset[k] = v; remember.set(k, v); syncDisplay(); window.dispatchEvent(new Event("resize")); }
function syncDisplay() {
  const d = document.documentElement.dataset;
  for (const b of document.querySelectorAll("#skins .skin")) b.setAttribute("aria-pressed", String(b.dataset.skin === (d.skin || "amethyst")));
  for (const b of document.querySelectorAll("#densities button")) b.setAttribute("aria-pressed", String(b.dataset.density === (d.density || "compact")));
  $("#rail-toggle .lbl").textContent = d.rail === "icons" ? "Expand" : "Collapse";
  $("#rail-toggle").title = d.rail === "icons" ? "Expand the menu" : "Collapse the menu";
}
for (const b of document.querySelectorAll("#skins .skin")) b.addEventListener("click", () => setDisplay("skin", b.dataset.skin));
for (const b of document.querySelectorAll("#densities button")) b.addEventListener("click", () => setDisplay("density", b.dataset.density));
$("#rail-toggle").addEventListener("click", () => {
  peek(false); peekHeld = true;  // just collapsed with the mouse on it: don't reopen until the mouse leaves
  setDisplay("rail", document.documentElement.dataset.rail === "icons" ? "labels" : "icons");
});
// Collapsed, hovering an icon opens the menu for as long as the mouse stays on it.
const rail = $(".rail");
let peekTimer = null, peekHeld = false;
function peek(on) { clearTimeout(peekTimer); rail.classList.toggle("peek", on); }
rail.addEventListener("mouseover", e => {
  if (document.documentElement.dataset.rail !== "icons" || peekHeld || rail.classList.contains("peek") || !e.target.closest("a, button")) return;
  clearTimeout(peekTimer); peekTimer = setTimeout(() => peek(true), 120);
});
rail.addEventListener("mouseleave", () => { peekHeld = false; peek(false); });
const menu = $("#display-menu"), menuBtn = $("#display-btn");
menuBtn.addEventListener("click", e => { e.stopPropagation(); menu.hidden = !menu.hidden; menuBtn.setAttribute("aria-expanded", String(!menu.hidden)); });
document.addEventListener("click", e => { if (!menu.hidden && !menu.contains(e.target)) { menu.hidden = true; menuBtn.setAttribute("aria-expanded", "false"); } });
document.addEventListener("keydown", e => { if (e.key === "Escape" && !menu.hidden) { menu.hidden = true; menuBtn.setAttribute("aria-expanded", "false"); } });
syncDisplay();

route();
