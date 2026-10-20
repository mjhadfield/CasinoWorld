// The Slot design wizard (the admin page's Slot design tab): a tab per design plus New, the rail of steps, and the
// open step. The page loads this module the first time the tab opens and hands over its helpers (init). The route
// is the page hash: #design/<design>/<step>.
import * as concept from "./steps/concept.js";
import * as art from "./steps/art.js";
import * as later from "./steps/later.js";

const STEPS = {concept, art};          // built steps; the rest show what they'll do (later.js)
const ctx = {did: null, data: null, step: null};
let H, shell = null, timer = null, ticks = 0, current = null;

export function init(helpers) {
  H = helpers;
  Object.assign(ctx, helpers, {refresh, go, img: p => `/slot-design/${ctx.did}/${p}`, setStep});
  if (!document.getElementById("wz-css"))
    document.head.append(Object.assign(document.createElement("link"), {id: "wz-css", rel: "stylesheet", href: "/slot-design-ui/wizard.css"}));
  window.addEventListener("hashchange", () => { if (location.hash.startsWith("#design")) open(); });
}

const route = () => { const [, did, step] = location.hash.slice(1).split("/"); return {did, step}; };

export function go(did, step) { location.hash = `#design/${did}${step ? "/" + step : ""}`; }

export async function load() {
  try {
    ctx.designs = (await H.api("GET", "/api/slot-design")).designs;
    buildShell();
    await open();
  } catch (e) { H.status("Couldn't load the slot designs: " + e.message, "warn"); }
}

function buildShell() {
  const {el} = H;
  const tabs = el("div", {className: "wz-designs", role: "tablist", ariaLabel: "Slot designs"});
  const form = newDesignForm();
  shell = {
    tabs, form,
    flux: el("span", {className: "tag", textContent: "FLUX…"}),
    queue: el("span", {className: "hint"}),
    rail: el("nav", {className: "wz-rail", ariaLabel: "Steps"}),
    head: el("div", {className: "wz-head"}),
    body: el("div", {className: "wz-body"}),
  };
  document.getElementById("dz-app").replaceChildren(tabs, form,
    el("div", {className: "wz-bar"}, shell.flux, shell.queue),
    el("div", {className: "wz"}, shell.rail, el("div", {className: "wz-step"}, shell.head, shell.body)));
  drawTabs();
}

function drawTabs() {
  const {el} = H;
  shell.tabs.replaceChildren(...ctx.designs.map(d => el("button", {type: "button", role: "tab", textContent: d.name,
      ariaSelected: String(d.id === ctx.did), onclick: () => go(d.id)})),
    el("button", {type: "button", className: "wz-newbtn", textContent: "＋ New design", onclick: () => {
      shell.form.hidden = !shell.form.hidden;
      if (!shell.form.hidden) shell.form.querySelector("input").focus();
    }}));
}

function newDesignForm() {
  const {el} = H;
  const name = el("input", {placeholder: "e.g. Pirates of the Spanish Main", ariaLabel: "Name"});
  const brief = el("textarea", {rows: 2, ariaLabel: "Theme brief",
    placeholder: "The theme in a sentence: it leads every picture FLUX makes for this slot"});
  return el("div", {className: "card wz-new", hidden: true},
    el("div", {className: "card-head"}, el("h3", {textContent: "New slot design"})),
    el("div", {className: "grid2"}, el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
      el("label", {className: "field", style: "grid-column: 1 / -1"}, el("span", {textContent: "Theme brief"}), brief)),
    el("p", {className: "hint", textContent: "It starts with the house standard: 5×4 reels and 25 lines, Royals, two symbol sets, a Wild and two scatters, with starter royals and specials waiting for Generate."}),
    el("div", {className: "controls"},
      el("button", {type: "button", className: "primary", textContent: "Create", onclick: async () => {
        try {
          const {id} = await H.api("POST", "/api/slot-design", {name: name.value, brief: brief.value});
          ctx.designs = (await H.api("GET", "/api/slot-design")).designs;
          shell.form.hidden = true; name.value = brief.value = "";
          H.status("Created: start with the Concept.", "ok");
          go(id, "concept");
        } catch (e) { H.status(e.message, "warn"); }
      }}),
      el("button", {type: "button", textContent: "Cancel", onclick: () => { shell.form.hidden = true; }})));
}

async function open() {
  if (!shell) return;
  const r = route();
  if (!ctx.designs.length) {
    shell.body.replaceChildren(H.el("p", {className: "hint", textContent: "No designs yet: press New design."}));
    return;
  }
  const did = ctx.designs.some(d => d.id === r.did) ? r.did : ctx.designs[0].id;
  const changed = did !== ctx.did;
  ctx.did = did;
  ctx.data = await H.api("GET", `/api/slot-design/${did}`);
  const steps = ctx.data.steps;
  const step = steps.some(s => s.id === r.step) ? r.step
    : (steps.find(s => s.status === "doing") || steps.find(s => s.status === "todo") || steps[0]).id;
  if (r.did !== did || r.step !== step) { history.replaceState(null, "", `#design/${did}/${step}`); }
  if (changed) drawTabs();
  if (changed || step !== ctx.step) {
    ctx.step = step;
    current = STEPS[step] || later;
    drawRail(); drawHead();
    shell.body.replaceChildren();
    current.render(ctx, shell.body);
  } else { drawRail(); drawHead(); current.update?.(ctx); }
  drawBar(); checkFlux();
}

// Reload the design and let the open step redraw what changed. `force` names a symbol to redraw even if focused.
async function refresh(force) {
  ctx.data = await H.api("GET", `/api/slot-design/${ctx.did}`);
  const listed = ctx.designs.find(d => d.id === ctx.did);
  if (listed && listed.name !== ctx.data.name) { listed.name = ctx.data.name; drawTabs(); }
  drawRail(); drawHead(); drawBar();
  current.update ? current.update(ctx, force) : (shell.body.replaceChildren(), current.render(ctx, shell.body));
}

const DOT = {todo: "○", doing: "◐", done: "●"};

function drawRail() {
  const {el} = H;
  shell.rail.replaceChildren(...ctx.data.steps.map((s, i) => el("a", {href: `#design/${ctx.did}/${s.id}`,
    className: `wz-st ${s.status}`, ariaCurrent: s.id === ctx.step ? "step" : null, title: s.status},
    el("span", {className: "n", textContent: i + 1}), el("span", {className: "t", textContent: s.title}),
    el("span", {className: "dot", textContent: DOT[s.status], ariaLabel: s.status}))));
}

function drawHead() {
  const {el} = H;
  const steps = ctx.data.steps, i = steps.findIndex(s => s.id === ctx.step), s = steps[i];
  const seg = el("span", {className: "seg", role: "group", ariaLabel: "Step status"},
    ...[["todo", "To do"], ["doing", "In progress"], ["done", "Done"]].map(([v, t]) =>
      el("button", {type: "button", textContent: t, ariaPressed: String(s.status === v), onclick: () => setStep(s.id, v)})));
  shell.head.replaceChildren(el("h2", {}, el("span", {textContent: `${i + 1}. ${s.title}`}),
    el("span", {className: "tag", textContent: ctx.data.name})), seg,
    el("span", {className: "wz-prevnext"},
      el("button", {type: "button", textContent: "◀ " + (steps[i - 1]?.title || ""), disabled: i === 0, onclick: () => go(ctx.did, steps[i - 1].id)}),
      el("button", {type: "button", textContent: (steps[i + 1]?.title || "") + " ▶", disabled: i === steps.length - 1, onclick: () => go(ctx.did, steps[i + 1].id)})));
}

export async function setStep(step, status) {
  try { await H.api("PUT", `/api/slot-design/${ctx.did}/steps/${step}`, {status}); await refresh(); }
  catch (e) { H.status(e.message, "warn"); }
}

function drawBar() {
  const r = ctx.data.running;
  const who = r && (ctx.data.symbols.find(s => s.id === r.symbol) || {}).name;
  shell.queue.textContent = [
    r ? (r.status === "waiting" ? `Waiting for FLUX to make ${who}` : `Making ${who}: ${r.done + 1} of ${r.count}`) : "",
    ctx.data.queued ? `${ctx.data.queued} queued` : ""].filter(Boolean).join(" · ");
}

async function checkFlux() {
  try {
    const st = await H.api("GET", `/api/slot-design/${ctx.did}/status`);
    shell.flux.textContent = st.flux ? "FLUX ready" : "FLUX off";
    shell.flux.className = "tag " + (st.flux ? "ok" : "warn");
    shell.flux.title = st.flux ? "FLUX.2-klein is loaded in Odysseus."
      : "Start FLUX.2-klein from Odysseus's Cookbook, with CPU Offload ticked. Queued jobs wait for it.";
  } catch (e) {}
}

// While the tab is open: follow running jobs every 4 s, and check FLUX every 20 s otherwise.
export function polling(on) {
  clearInterval(timer);
  if (on) timer = setInterval(async () => {
    if (!ctx.data || document.hidden) return;
    ticks++;
    if (ctx.data.running || ctx.data.queued) { await refresh().catch(() => {}); checkFlux(); }
    else if (ticks % 5 === 0) checkFlux();
  }, 4000);
}
