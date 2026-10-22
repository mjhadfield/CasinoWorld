// Slot design: the slot machine builder. The top bar holds the design (and New), the open step's status and
// Prev/Next, the step's own tools, the image model's state and Play; below it, the rail of steps and the open step,
// which lays itself out to fit the window (data-step on .wz-body; wizard.css). The route is the page hash:
// #design/<design>/<step>. Image work runs through Odysseus, which must be running with an image model loaded.
import * as concept from "./steps/concept.js";
import * as art from "./steps/art.js";
import * as ladder from "./steps/ladder.js";
import * as scene from "./steps/scene.js";
import * as features from "./steps/features.js";
import * as bonuses from "./steps/bonuses.js";
import * as sprites from "./steps/sprites.js";
import * as sounds from "./steps/sounds.js";
import * as maths from "./steps/maths.js";
import * as mockup from "./steps/mockup.js";
import * as build from "./steps/build.js";
import {createGame} from "/admin-ui/design/mockup/game.js";
import {designConfig, loadMath} from "/admin-ui/design/mockup/design.js";

const STEPS = {concept, art, ladder, scene, features, bonuses, sprites, sounds, maths, mockup, build};
const ctx = {did: null, data: null, step: null};
let H, shell = null, timer = null, ticks = 0, current = null;

export function init(helpers) {
  H = helpers;
  Object.assign(ctx, helpers, {refresh, go, img: p => `/slot-design/${ctx.did}/${p}`, setStep, play: playMockup});
  if (!document.getElementById("wz-css"))
    document.head.append(Object.assign(document.createElement("link"), {id: "wz-css", rel: "stylesheet", href: "/admin-ui/design/wizard.css"}));
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

export function shown(on) { polling(on); if (on && current) current.shown?.(); }

function buildShell() {
  const {el} = H;
  const pick = el("select", {className: "wz-pick", ariaLabel: "Slot design"});
  pick.addEventListener("change", () => go(pick.value));
  shell = {
    pick,
    title: el("b", {className: "wz-title"}),
    status: el("div", {className: "seg", role: "group", ariaLabel: "Step status"}),
    prev: el("button", {type: "button", className: "ghost sq"}),
    next: el("button", {type: "button", className: "ghost sq"}),
    tools: el("div", {className: "wz-tools"}),
    queue: el("span", {className: "hint wz-queue"}),
    flux: el("span", {className: "tag", textContent: "Image model…"}),
    play: el("button", {type: "button", className: "primary", textContent: "▶ Play", onclick: () => playMockup(),
      title: "The base game with this design's art and scene (from the Scene step on)"}),
    rail: el("nav", {className: "wz-rail", ariaLabel: "Steps"}),
    body: el("div", {className: "wz-body"}),
    form: newDesignForm(),
  };
  ctx.tools = shell.tools;
  H.top.replaceChildren(pick,
    el("button", {type: "button", className: "ghost sq", textContent: "+", title: "New slot design", onclick: () => { shell.form.showModal(); shell.form.querySelector("input").focus(); }}),
    el("span", {className: "sep"}), shell.title, shell.status, shell.prev, shell.next,
    el("span", {className: "sep"}), shell.tools, el("span", {className: "grow"}), shell.queue, shell.flux, shell.play);
  H.view.replaceChildren(el("div", {className: "wb wz", style: "grid-template-columns: 184px minmax(0, 1fr)"},
    el("div", {className: "panel"}, el("div", {className: "pb"}, shell.rail)), shell.body), shell.form);
  drawPick();
}

function drawPick() {
  const {el} = H;
  shell.pick.replaceChildren(...ctx.designs.map(d => el("option", {value: d.id, textContent: d.name, selected: d.id === ctx.did})));
}

function newDesignForm() {
  const {el} = H;
  const name = el("input", {placeholder: "e.g. Pirates of the Spanish Main", ariaLabel: "Name"});
  const brief = el("textarea", {rows: 3, ariaLabel: "Theme brief",
    placeholder: "The theme in a sentence: it leads every picture the image model makes for this slot"});
  const dlg = el("dialog", {className: "wz-new"},
    el("div", {className: "ph"}, el("b", {textContent: "New slot design"})),
    el("div", {className: "pb padded"},
      el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
      el("label", {className: "field"}, el("span", {textContent: "Theme brief"}), brief),
      el("p", {className: "hint", textContent: "It starts with the house standard: 5×4 reels and 25 lines, Royals, two symbol sets, a Wild and two scatters, with starter royals and specials waiting for Generate."}),
      el("div", {className: "controls"},
        el("button", {type: "button", className: "primary", textContent: "Create", onclick: async () => {
          try {
            const {id} = await H.api("POST", "/api/slot-design", {name: name.value, brief: brief.value});
            ctx.designs = (await H.api("GET", "/api/slot-design")).designs;
            dlg.close(); name.value = brief.value = "";
            H.status("Created: start with the Concept.", "ok");
            go(id, "concept");
          } catch (e) { H.status(e.message, "warn"); }
        }}),
        el("button", {type: "button", textContent: "Cancel", onclick: () => dlg.close()}))));
  return dlg;
}

async function open() {
  if (!shell) return;
  const r = route();
  if (!ctx.designs.length) {
    shell.body.replaceChildren(H.el("p", {className: "empty", textContent: "No designs yet: press + to start one."}));
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
  if (changed) drawPick();
  if (changed || step !== ctx.step) {
    ctx.step = step;
    current?.leave?.();
    current = STEPS[step];
    drawRail(); drawHead();
    shell.tools.replaceChildren();
    shell.body.replaceChildren();
    shell.body.className = "wz-body";
    shell.body.dataset.step = step;
    shell.body.scrollTop = 0;
    current.render(ctx, shell.body);
  } else { drawRail(); drawHead(); current.update?.(ctx); }
  drawBar(); checkFlux();
  H.status(`${ctx.data.name} · ${steps.find(s => s.id === step).title}`);
}

// Reload the design and let the open step redraw what changed. `force` names a symbol to redraw even if focused.
async function refresh(force) {
  ctx.data = await H.api("GET", `/api/slot-design/${ctx.did}`);
  const listed = ctx.designs.find(d => d.id === ctx.did);
  if (listed && listed.name !== ctx.data.name) { listed.name = ctx.data.name; drawPick(); }
  drawRail(); drawHead(); drawBar();
  current.update ? current.update(ctx, force) : (shell.body.replaceChildren(), current.render(ctx, shell.body));
}

function drawRail() {
  const {el} = H;
  shell.rail.replaceChildren(...ctx.data.steps.map((s, i) => el("a", {href: `#design/${ctx.did}/${s.id}`,
    className: `wz-st ${s.status}`, ariaCurrent: s.id === ctx.step ? "step" : null, title: {todo: "To do", doing: "In progress", done: "Done"}[s.status]},
    el("span", {className: "n", textContent: i + 1}), el("span", {className: "t", textContent: s.title}),
    el("span", {className: "dot", ariaLabel: s.status}))));
}

function drawHead() {
  const {el} = H;
  const steps = ctx.data.steps, i = steps.findIndex(s => s.id === ctx.step), s = steps[i];
  shell.title.textContent = `${i + 1} · ${s.title}`;
  shell.status.replaceChildren(...[["todo", "To do"], ["doing", "In progress"], ["done", "Done"]].map(([v, t]) =>
    el("button", {type: "button", textContent: t, ariaPressed: String(s.status === v), onclick: () => setStep(s.id, v)})));
  Object.assign(shell.prev, {textContent: "◀", title: steps[i - 1] ? "Back to " + steps[i - 1].title : "", disabled: i === 0,
    onclick: () => go(ctx.did, steps[i - 1].id)});
  Object.assign(shell.next, {textContent: "▶", title: steps[i + 1] ? "On to " + steps[i + 1].title : "", disabled: i === steps.length - 1,
    onclick: () => go(ctx.did, steps[i + 1].id)});
}

export async function setStep(step, status) {
  try { await H.api("PUT", `/api/slot-design/${ctx.did}/steps/${step}`, {status}); await refresh(); }
  catch (e) { H.status(e.message, "warn"); }
}

function drawBar() {
  const r = ctx.data.running;
  const who = r && (r.symbol ? (ctx.data.symbols.find(s => s.id === r.symbol) || {}).name : "the background");
  const sceneAt = ctx.data.steps.findIndex(s => s.id === "scene");
  shell.play.hidden = !(ctx.data.steps.findIndex(s => s.id === ctx.step) >= sceneAt || ctx.data.steps[sceneAt].status !== "todo");
  shell.queue.textContent = [
    r ? (r.status === "waiting" ? `Waiting for the image model to make ${who}` : `Making ${who}: ${r.done + 1} of ${r.count}`) : "",
    ctx.data.queued ? `${ctx.data.queued} queued` : ""].filter(Boolean).join(" · ");
}

async function checkFlux() {
  try {
    const st = await H.api("GET", `/api/slot-design/${ctx.did}/status`);
    shell.flux.textContent = st.flux ? `${st.model} ready` : "Image model off";
    shell.flux.className = "tag " + (st.flux ? "ok" : "caution");
    shell.flux.title = st.flux ? `${st.model} is loaded in Odysseus and makes the pictures.`
      : "Start an image model (FLUX.2-klein, Qwen-Image-2.1, ...) in Odysseus, with CPU Offload ticked. Queued jobs wait for it.";
  } catch (e) {}
}

// The mockup in a dialog, from the Scene step on: the base game with this design's art, scene and (once tuned) maths.
// opts.rig forces the first spin: {features: [...]} or {trigger: "trail"|"free"|"battle"|"voyage"|"expedition"} or {jackpot: tier}; opts.bonus plays
// a bonus straight away (one no scatter starts).
async function playMockup(opts = {}) {
  const {el} = H;
  await loadMath();
  const canvas = el("canvas", {width: 1280, height: 720, className: "wz-canvas"});
  const dlg = el("dialog", {className: "wz-mock"}, el("div", {className: "wz-mock-head"},
    el("b", {textContent: `${ctx.data.name}: mockup`}), el("span", {className: "hint", textContent: "Click Spin or press Space."}),
    el("button", {type: "button", textContent: "Close", onclick: () => dlg.close()})), canvas);
  document.body.append(dlg);
  const game = createGame(canvas, designConfig(ctx.data, ctx.img));
  dlg.addEventListener("close", () => { game.destroy(); dlg.remove(); });
  dlg.showModal();
  if (opts.rig) {
    game.rig({features: opts.rig.features || [], trigger: opts.rig.trigger || null, jackpot: opts.rig.jackpot || null});
    setTimeout(() => game.spin(), 900);
  } else if (opts.bonus) setTimeout(() => game.bonus(opts.bonus), 900);
}

// While the section is open: follow running jobs (and a step left showing older data, current.behind) every 4 s,
// and check the image model every 20 s otherwise.
function polling(on) {
  clearInterval(timer);
  if (on) timer = setInterval(async () => {
    if (!ctx.data || document.hidden) return;
    ticks++;
    if (ctx.data.running || ctx.data.queued || current?.behind?.()) { await refresh().catch(() => {}); checkFlux(); }
    else if (ticks % 5 === 0) checkFlux();
  }, 4000);
}
