// House: how the house is doing at every game, bet line and spot, actual against EV (tracking.py, edges.py), over
// today, the last 7 or 30 days, or all of it; for everyone, NPCs or humans; in one casino or all. A line opens to its
// spots. The chart under it is each day's house win against its EV, every game together.
import {betsTable} from "./bets.js";

let H, data = null;
const view = {period: "7d", who: "all", casino: "all"};
const open = new Set();
const PERIODS = [["1d", "Today"], ["7d", "7 days"], ["30d", "30 days"], ["all", "All"]];
const WHO = [["all", "Everyone"], ["npc", "NPCs"], ["human", "Humans"]];

export function init(h) {
  H = h;
  const {el} = h;
  const seg = (id, opts, key) => el("div", {className: "seg", id}, ...opts.map(([v, label]) => {
    const b = el("button", {type: "button", textContent: label});
    b.dataset.v = v;
    b.addEventListener("click", () => { view[key] = v; load(); });
    return b;
  }));
  h.top.append(seg("house-period", PERIODS, "period"), seg("house-who", WHO, "who"),
    el("select", {id: "house-casino", onchange: e => { view.casino = e.target.value; load(); }}),
    el("span", {className: "grow"}), el("button", {type: "button", textContent: "Refresh", onclick: load}));
  h.view.append(el("div", {className: "panel"}, el("div", {className: "ph", id: "house-head"}), el("div", {className: "pb", id: "house-body"})),
    el("div", {className: "panel"}, el("div", {className: "ph"}, el("b", {textContent: "By day"}),
      el("span", {className: "hint", textContent: "the house's win (bars) against its EV (line), every game"})), el("div", {className: "pb padded", id: "house-days"})));
}

export async function load() {
  try {
    data = await H.api("GET", `/api/house?period=${view.period}&who=${view.who}&casino=${encodeURIComponent(view.casino)}`);
    draw();
    H.status("House figures loaded.");
  } catch (e) { H.status("Couldn't load the House figures: " + e.message, "warn"); }
}
export function shown(on) { if (on) load(); }

function draw() {
  const {el, money, signed} = H;
  const $ = s => H.view.querySelector(s);
  for (const [id, key] of [["#house-period", "period"], ["#house-who", "who"]])
    for (const b of H.top.querySelectorAll(id + " button")) b.setAttribute("aria-pressed", String(b.dataset.v === view[key]));
  const sel = H.top.querySelector("#house-casino");
  sel.replaceChildren(el("option", {value: "all", textContent: "Every casino"}),
    ...Object.entries(data.casinos).map(([id, name]) => el("option", {value: id, textContent: name})));
  sel.value = view.casino;
  const t = data.games.reduce((a, g) => ({staked: a.staked + g.staked, net: a.net + g.net, expected: a.expected + g.expected, v: a.v + g.var}),
    {staked: 0, net: 0, expected: 0, v: 0});
  const since = data.tracking_since ? new Date(data.tracking_since).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric"}) : null;
  $("#house-head").replaceChildren(el("b", {textContent: "Every game"}),
    el("span", {className: "hint", textContent: `staked ${money(t.staked)} · house won ${signed(t.net)} · EV ${money(Math.round(t.expected))}`
      + ` · luck ${signed(Math.round(t.net - t.expected))} ±${money(Math.round(2 * Math.sqrt(t.v)))}` + (since ? ` · tracked since ${since}` : "")}),
    el("span", {className: "grow"}),
    el("span", {className: "hint", textContent: data.edges_made ? `edges from ${data.edges_made}` : "no edges.json: run tools/edges.py"}));
  const body = [betsTable(H, data.games, {open, redraw: draw, empty: "No bets in this period."})];
  if (data.unpriced.length)
    body.push(el("p", {className: "hint", textContent: "Unpriced (no edge yet; run tools/edges.py): " + data.unpriced.join(", ")}));
  $("#house-body").replaceChildren(...body);
  $("#house-days").replaceChildren(chart(data.days));
}

function chart(rows) {
  const {el, money} = H;
  const days = {};
  for (const r of rows) {
    const d = days[r.day] ||= {net: 0, expected: 0};
    d.net += r.staked - r.returned; d.expected += r.expected;
  }
  const list = Object.entries(days).sort();
  if (!list.length) return el("p", {className: "empty", textContent: "No days yet."});
  const W = 900, Hh = 160, pad = 28, bw = Math.max(3, Math.min(28, (W - pad) / list.length - 3));
  const top = Math.max(1, ...list.map(([, d]) => Math.max(Math.abs(d.net), Math.abs(d.expected))));
  const y = v => Hh / 2 - v / top * (Hh / 2 - 8);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${Hh + 18}`);
  svg.setAttribute("style", "width: 100%; max-width: 900px; height: auto");
  const add = (tag, attrs, title) => {
    const n = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (title) { const t = document.createElementNS(ns, "title"); t.textContent = title; n.append(t); }
    svg.append(n);
    return n;
  };
  add("line", {x1: pad, x2: W, y1: y(0), y2: y(0), stroke: "currentColor", "stroke-opacity": 0.3});
  const step = (W - pad) / list.length;
  const pts = [];
  list.forEach(([day, d], i) => {
    const x = pad + i * step + (step - bw) / 2;
    add("rect", {x, width: bw, y: Math.min(y(0), y(d.net)), height: Math.max(1, Math.abs(y(d.net) - y(0))),
      fill: d.net >= 0 ? "var(--accent)" : "var(--warn, #c55)", "fill-opacity": 0.75},
      `${day}: house won ${money(Math.round(d.net))}, EV ${money(Math.round(d.expected))}`);
    pts.push(`${x + bw / 2},${y(d.expected)}`);
    if (list.length <= 14 || i % Math.ceil(list.length / 10) === 0)
      add("text", {x: x + bw / 2, y: Hh + 14, "text-anchor": "middle", "font-size": 10, fill: "currentColor"}).textContent = day.slice(5);
  });
  add("polyline", {points: pts.join(" "), fill: "none", stroke: "currentColor", "stroke-width": 1.5, "stroke-dasharray": "4 3"});
  return svg;
}
