// Step 9, Maths & payouts: the pays, each reel's symbol counts and the Colossal mix; Simulate measures the return
// (slots_math.js in a worker, the engine the cabinet uses); Auto-tune turns one control to reach the Concept's
// target; Freeze keeps the strips, once the server has replayed a sample of spins and agrees.
import {designParams, loadMath} from "/admin-ui/design/mockup/design.js";
import {typing} from "./artslot.js";

let C, worker = null, busy = false, last = null, tuned = null, spins = 500000;
const key = p => JSON.stringify([p.pays, p.counts, p.bigCounts, p.features, p.rates, p.freeRates, p.wildCounts, p.wildReelCounts,
  p.colossalSizes, p.multipliers, p.repeats, p.instants, p.trail, p.battle, p.voyage, p.expedition, p.freeGames, p.buyCost, p.routes, p.upgrades]);

function run(msg, onProgress) {
  worker ??= new Worker("/admin-ui/design/mockup/sim_worker.js");
  busy = true;
  return new Promise((res, rej) => {
    worker.onmessage = e => { if (e.data.progress != null && onProgress) onProgress(e.data.progress); if (!("progress" in e.data)) { busy = false; res(e.data); } };
    worker.onerror = e => { busy = false; rej(new Error(e.message)); };
    worker.postMessage(msg);
  });
}

export async function render(ctx, body) {
  C = ctx;
  await loadMath();
  draw(body);
}

export function update(ctx) {
  C = ctx;
  const body = document.querySelector(".wz-body");
  if (body && !busy && !typing(body)) draw(body);
}

const pct = x => x.toFixed(2) + "%";
const oneIn = (n, k) => k ? "1 in " + (n / k).toFixed(n / k < 10 ? 2 : 0) : "never";
const vol = sd => sd < 6 ? "low" : sd < 12 ? "medium" : "high";

function reportTable(r, target) {
  const {el} = C, rt = r.rtp, d = rt.game - target;
  const row = (label, v, cls) => el("tr", {className: cls || ""}, el("td", {textContent: label}), el("td", {className: "num", textContent: v}));
  return el("div", {className: "two"},
    el("table", {}, el("tbody", {},
      row("Line wins, no feature", pct(rt.plain)), row("Line wins with features", pct(rt.featured)), row("Repeat Win extra", pct(rt.repeat)),
      row("Instant Win", pct(rt.instant)), row("Trail bonus", pct(rt.trail)), row("Free games", pct(rt.free)),
      ...(r.battles || rt.battle ? [row("Battle bonus (its free games too)", pct(rt.battle))] : []),
      ...(r.voyages || rt.voyage ? [row("Voyage bonus (its free games too)", pct(rt.voyage))] : []),
      ...(r.expeditions || rt.expedition ? [row("Expedition bonus (its free games too)", pct(rt.expedition))] : []),
      row("The game", pct(rt.game), "strong"), row("Shared jackpots", "+" + pct(rt.jackpot)), row("In all", pct(rt.total), "strong"))),
    el("div", {className: "pane"},
      el("span", {className: "tag " + (Math.abs(d) <= 0.5 ? "ok" : "warn"), textContent: `${d >= 0 ? "+" : ""}${d.toFixed(2)} against the ${target}% target`}),
      el("table", {}, el("tbody", {},
        row("Spins measured", r.spins.toLocaleString("en-GB")), row("A win", oneIn(r.spins, r.hits)), row("A feature", oneIn(r.spins, r.featureSpins)),
        row("The trail bonus", oneIn(r.spins, r.trails)), row("Free games", oneIn(r.spins, r.frees)),
        ...(r.battles ? [row("The battle bonus", oneIn(r.spins, r.battles)), row("Its boss destroyed", r.bosses ? `${(100 * r.bosses / r.battleRun).toFixed(1)}% of battles` : "never")] : []),
        ...(r.voyages ? [row("The voyage bonus", oneIn(r.spins, r.voyages)), row("Its ship sunk", `${(100 * r.voyageRun.sunk / r.voyageRun.n).toFixed(1)}% of voyages`),
          row("All four artefacts", `${(100 * r.voyageRun.legends / r.voyageRun.n).toFixed(1)}% of voyages`)] : []),
        ...(r.expeditions ? [row("The expedition bonus", oneIn(r.spins, r.expeditions)),
          row("Ended by a hazard", `${(100 * r.expeditionRun.ended / r.expeditionRun.n).toFixed(1)}% of expeditions`),
          row("Through a Wormhole", `${(100 * r.expeditionRun.wormholes / r.expeditionRun.n).toFixed(1)}% of expeditions`)] : []),
        row("Biggest win", Math.round(r.max).toLocaleString("en-GB") + "× bet"), row("Volatility (SD)", `${r.sd.toFixed(2)}: ${vol(r.sd)}`),
        row("Buy Bonus returns", r.buy && isFinite(r.buy.rtp) ? pct(r.buy.rtp) : "off"), row("Exact line return (no features)", pct(r.exact))))));
}

function draw(body) {
  const {el} = C, d = C.data, m = d.maths, lad = d.ladder;
  const params = designParams(d);
  const now = key(params);
  const target = d.concept.target_rtp;
  const name = t => (d.symbols.find(s => s.id === lad.slots[t]) || {}).name || t;
  const thumb = t => { const s = d.symbols.find(x => x.id === lad.slots[t]); return s && s.file ? el("img", {src: C.img(s.file), alt: "", className: "wz-thumb"}) : el("span", {className: "wz-thumb"}); };

  // the pays
  const payTiers = lad.tiers.filter(t => !["BS", "FS"].includes(t));
  const payIn = Object.fromEntries(payTiers.map(t => [t, m.pays[t].map((v, i) => el("input", {type: "number", min: 0, max: 5000, value: v, className: "wz-num", ariaLabel: `${t} pays for ${i + 3}`}))]));
  const pays = el("div", {className: "card"}, el("h3", {textContent: "Pays (line bets for 3, 4 and 5 on a line)"}),
    el("div", {className: "scroll"}, el("table", {}, el("thead", {}, el("tr", {}, ...["", "Tier", "3", "4", "5"].map(x => el("th", {textContent: x})))),
      el("tbody", {}, ...payTiers.map(t => el("tr", {}, el("td", {}, thumb(t)), el("td", {textContent: `${t} · ${name(t)}`}), ...payIn[t].map(i => el("td", {}, i))))))),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save the pays", onclick: () =>
      save({pays: Object.fromEntries(payTiers.map(t => [t, payIn[t].map(i => +i.value)]))}, "Pays saved: the maths is unfrozen until you freeze it again.")})));

  // the reels
  const counts = params.counts, big = params.bigCounts;
  const cIn = counts.map((reel, r) => Object.fromEntries(lad.tiers.map(t => [t, el("input", {type: "number", min: 0, max: 40, value: reel[t] ?? 0, className: "wz-num sm", ariaLabel: `Reel ${r + 1}: ${t}`})])));
  const bIn = Object.fromEntries(payTiers.map(t => [t, el("input", {type: "number", min: 0, max: 20, value: big[t] ?? 0, className: "wz-num sm", ariaLabel: `Colossal: ${t}`})]));
  const lens = el("tr", {}, el("td", {}), el("td", {textContent: "Strip length"}), ...counts.map((reel) => el("td", {className: "num", textContent: Object.values(reel).reduce((a, b) => a + b, 0)})), el("td"));
  const reels = el("div", {className: "card"}, el("h3", {textContent: "Reel strips: how many of each symbol on each reel"}),
    el("p", {className: "hint", textContent: m.counts ? "Saved counts." : "Not saved yet: these are Armadillo's, stretched to this slot's tiers."}),
    el("div", {className: "scroll"}, el("table", {}, el("thead", {}, el("tr", {}, ...["", "Tier", "Reel 1", "2", "3", "4", "5", "Colossal"].map(x => el("th", {textContent: x})))),
      el("tbody", {}, ...lad.tiers.map(t => el("tr", {}, el("td", {}, thumb(t)), el("td", {textContent: `${t} · ${name(t)}`}),
        ...cIn.map(r => el("td", {}, r[t])), el("td", {}, bIn[t] || ""))), lens))),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save the reels", onclick: () =>
      save({counts: cIn.map(r => Object.fromEntries(Object.entries(r).map(([t, i]) => [t, +i.value]))),
            big_counts: Object.fromEntries(Object.entries(bIn).map(([t, i]) => [t, +i.value]))}, "Reels saved: the maths is unfrozen until you freeze it again.")})));

  // simulate, tune, freeze
  const bar = el("progress", {max: 1, value: 0, className: "wz-progress"});
  const out = el("div", {className: "pane"});
  const fresh = last && last.key === now;
  if (fresh) out.append(reportTable(last.result, target));
  else if (m.report && !m.stale) out.append(el("p", {className: "hint", textContent: "The frozen maths' report:"}), reportTable(m.report, target));
  const spinSel = el("select", {ariaLabel: "How many spins"}, ...[200000, 500000, 1000000, 2000000].map(n => el("option", {value: n, textContent: `${(n / 1e6).toLocaleString("en-GB")} million spins`})));
  spinSel.value = spins;
  spinSel.addEventListener("change", () => { spins = +spinSel.value; });
  const simBtn = el("button", {type: "button", className: "primary", textContent: "Simulate", onclick: async () => {
    simBtn.disabled = true; bar.value = 0;
    try {
      const {result} = await run({cmd: "sim", params, spins, buys: 100000}, p => { bar.value = p; });
      last = {key: now, result};
      draw(body);
    } catch (e) { C.status("Simulation failed: " + e.message, "warn"); simBtn.disabled = false; }
  }});
  const control = el("select", {ariaLabel: "What to turn"}, ...[["lows", "How many low symbols (fine steps)"], ["wilds", "How many Wilds (fine steps)"], ["pays", "All the pays together"], ["features", "Feature chances"]]
    .map(([v, t]) => el("option", {value: v, textContent: t})));
  const tuneOut = el("div", {className: "pane"});
  const tuneBtn = el("button", {type: "button", textContent: "Auto-tune to the target", onclick: async () => {
    tuneBtn.disabled = simBtn.disabled = true; bar.value = 0;
    try {
      const {tuned: t} = await run({cmd: "tune", params, control: control.value, target, spins: Math.min(spins, 500000), buys: 60000}, p => { bar.value = p; });
      tuned = {...t, control: control.value};
      draw(body);
    } catch (e) { C.status("Tuning failed: " + e.message, "warn"); }
  }});
  if (tuned && tuned.base === undefined) tuned.base = now;
  if (tuned && tuned.base === now) tuneOut.append(
    el("p", {className: "hint", textContent: tuned.reached ? `${tuned.describe} gives:` : `This control can't reach the target on its own; the nearest (${tuned.describe.toLowerCase()}) gives:`}),
    reportTable(tuned.result, target),
    el("div", {className: "controls"},
      el("button", {type: "button", className: "primary", textContent: "Use these", onclick: async () => {
        const p = tuned.params, body2 = tuned.control === "features" ? null : {pays: p.pays, counts: p.counts, big_counts: p.bigCounts};
        try {
          if (tuned.control === "features") await C.api("PATCH", `/api/slot-design/${C.did}/features`, {rates: p.rates});
          else await C.api("PATCH", `/api/slot-design/${C.did}/maths`, body2);
          last = {key: null, result: tuned.result}; tuned = null;
          await C.refresh();
          last.key = key(designParams(C.data));
          draw(body);
          C.status("Tuned settings saved. Freeze to keep them.", "ok");
        } catch (e) { C.status(e.message, "warn"); }
      }}),
      el("button", {type: "button", textContent: "Discard", onclick: () => { tuned = null; draw(body); }})));
  else tuned = null;

  const done = m.frozen && !m.stale && !!m.counts;
  const freezeBtn = el("button", {type: "button", className: "primary", textContent: done ? "Frozen" : "Freeze the maths", disabled: !fresh || done,
    title: done ? "Already frozen: change something to freeze again" : fresh ? "Keep these strips and this report" : "Simulate these settings first", onclick: async () => {
      freezeBtn.disabled = true;
      try {
        if (!m.counts) await C.api("PATCH", `/api/slot-design/${C.did}/maths`, {counts: params.counts, big_counts: params.bigCounts});
        const {sample} = await run({cmd: "sample", params: {...params, strips: null, freeStrips: null, bigStrip: null}});
        await C.api("POST", `/api/slot-design/${C.did}/maths/freeze`, {...sample, report: last.result});
        if (C.data.steps.find(s => s.id === "maths").status !== "done") await C.setStep("maths", "doing"); else await C.refresh();
        C.status("Frozen: the server replayed the sample spins and agrees.", "ok");
      } catch (e) { C.status(e.message, "warn"); freezeBtn.disabled = false; }
    }});

  const state = m.frozen ? (m.stale ? ["warn", "Frozen, but settings have changed since: simulate and freeze again"] : ["ok", `Frozen ${m.frozen_at.replace("T", " ")}`])
    : ["gold", "Not frozen"];
  const check = m.check ? `Server check: ${m.check.sample} sample spins identical; exact line return ${m.check.exact}%; its own 30,000 spins: ${m.check.python_30k.game}% (short runs swing).` : "";
  body.replaceChildren(
    el("p", {className: "lead", textContent: `What the slot pays and how often. The Concept's target is ${target}% from the game itself, plus about 3.75% from the shared jackpots (Armadillo: 91.5%). Simulate measures it; Auto-tune turns one control to reach it; Freeze keeps the result for the mockup and the build.`}),
    el("div", {className: "card"}, el("div", {className: "controls"}, el("span", {className: "tag " + state[0], textContent: state[1]}), el("span", {className: "grow"}), freezeBtn),
      check ? el("p", {className: "hint", textContent: check}) : null),
    el("div", {className: "card"}, el("div", {className: "controls"}, spinSel, simBtn, el("span", {className: "hint", textContent: "Volatility target: " + d.concept.volatility}), bar), out),
    el("div", {className: "card"}, el("h3", {textContent: "Auto-tune"}), el("div", {className: "controls"}, control, tuneBtn,
      el("span", {className: "hint", textContent: "about two minutes: it tries settings until the return meets the target"})), tuneOut),
    el("div", {className: "wz-cards"}, pays, reels));
}

async function save(body, msg) {
  try {
    await C.api("PATCH", `/api/slot-design/${C.did}/maths`, body);
    if (C.data.steps.find(s => s.id === "maths").status === "todo") await C.setStep("maths", "doing"); else await C.refresh();
    C.status(msg, "ok");
  } catch (e) { C.status(e.message, "warn"); }
}
