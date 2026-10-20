// Step 5, Features: which of the library's random features this slot uses, how often each fires on a paid spin
// and in the free games, and what each can give (its value table). "Show me" plays the mockup with it forced.
import {artSlot, parseTable, specs, tableText, typing} from "./artslot.js";

const ABOUT = {
  wilds: ["Random Wilds", "Wilds land on random cells before the reels stop.", "wild_counts", "how many wilds"],
  wildReels: ["Wild Reels", "Whole reels turn wild; the mascot flies down each one.", "wild_reel_counts", "how many reels"],
  colossal: ["Colossal Reels", "Neighbouring reels fuse and spin one big symbol.", "colossal_sizes", "how many reels wide"],
  multiplier: ["Multiplier", "Every line win this spin is multiplied.", "multipliers", "the multiplier"],
  upgrade: ["Symbol Upgrade", "One symbol on the grid steps up the Value ladder's upgrade chain.", null, ""],
  repeat: ["Repeat Win", "The line wins pay again.", "repeats", "times paid"],
  instant: ["Instant Win", "A cash prize, in multiples of the bet; the Instant Win prize picture shows it.", "instants", "× the bet"],
};
let C;

export function render(ctx, body) {
  C = ctx;
  const {el} = C, f = C.data.features;
  const rows = f.library.map(id => {
    const [name, about, table, unit] = ABOUT[id];
    const on = el("input", {type: "checkbox", checked: f.enabled.includes(id), ariaLabel: `Use ${name}`});
    const pct = v => el("input", {type: "number", min: 0, max: 100, step: 0.1, value: +(v * 100).toFixed(2), className: "wz-num"});
    const base = pct(f.rates[id]), free = pct(f.free_rates[id]);
    base.ariaLabel = `${name}: chance on a paid spin, %`; free.ariaLabel = `${name}: chance in a free game, %`;
    const values = table ? el("input", {value: tableText(f.tables[table]), ariaLabel: `${name}: ${unit}, value:weight`, title: `${unit}: value:weight pairs`}) : null;
    const shown = el("input", {value: f.names[id] === f.default_names[id] ? "" : f.names[id], placeholder: f.default_names[id], maxLength: 22,
      ariaLabel: `${name}: what the screen calls it`, title: "What the side panel calls it (blank: the house name)"});
    return {id, on, base, free, table, values, shown, tr: el("tr", {},
      el("td", {}, el("label", {className: "confirm"}, on, el("b", {textContent: name})), el("div", {className: "hint", textContent: about}),
        el("label", {className: "field"}, el("span", {textContent: "On the screen"}), shown)),
      el("td", {}, base), el("td", {}, free),
      el("td", {}, values ? el("label", {className: "field"}, el("span", {textContent: unit}), values) : el("span", {className: "hint", textContent: "—"})),
      el("td", {}, el("button", {type: "button", textContent: "▶ Show me", title: "Play the mockup with this feature forced on the next spin",
        onclick: () => C.play({rig: {features: [id]}})})))};
  });
  const save = async () => {
    const tables = {}, rates = {}, free_rates = {};
    for (const r of rows) {
      rates[r.id] = +r.base.value / 100; free_rates[r.id] = +r.free.value / 100;
      if (r.table) tables[r.table] = parseTable(r.values.value);
    }
    try {
      await C.api("PATCH", `/api/slot-design/${C.did}/features`, {names: Object.fromEntries(rows.map(r => [r.id, r.shown.value]))});
      if (!C.data.signed_off)   // (a signed-off slot's maths is locked; its names aren't)
        await C.api("PATCH", `/api/slot-design/${C.did}/features`, {enabled: rows.filter(r => r.on.checked).map(r => r.id), rates, free_rates, tables});
      if (C.data.steps.find(s => s.id === "features").status === "todo") await C.setStep("features", "doing"); else await C.refresh();
      C.status("Features saved.", "ok");
    } catch (e) { C.status(e.message, "warn"); }
  };
  body.append(
    el("p", {className: "lead", textContent: "The random features any spin can bring, from Armadillo's library. Chances are per spin; in the free games at least one fires every spin. Value tables are value:weight pairs (2:50 means a value of 2, weighted 50). The Maths step measures what they're worth."}),
    el("div", {className: "card scroll"}, el("table", {className: "wz-table"},
      el("thead", {}, el("tr", {}, ...["Feature", "Paid spin %", "Free game %", "Values", ""].map(t => el("th", {textContent: t})))),
      el("tbody", {}, ...rows.map(r => r.tr))),
      el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save the features", onclick: save}))),
    el("div", {className: "card"}, el("h3", {textContent: "Pictures"}),
      el("div", {className: "wz-slots"}, ...Object.keys(C.data.art).filter(k => C.data.art[k].step === "features").map(k => artSlot(C, k)))),
    specs(C, "feature"));
}

export function update(ctx) {
  C = ctx;
  const body = document.querySelector(".wz-body");
  if (body && !typing(body)) { body.replaceChildren(); render(ctx, body); }
}
