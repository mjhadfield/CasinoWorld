// The bets table the House section, the NPC panel and Player stats share: each game, its bet lines (a decision game's
// main line, each side bet) and, opened, each line's spots, against what the house expected to win (tracking.py).
//   House won   staked less returned: the house's actual win (+ the house is up)
//   EV          the house's expected win on what was staked (the spot's edge x stake; a Craps bet that wins and stays
//               up is charged again)
//   Hold        House won as a share of the stake: what the house actually kept
//   EV hold     EV as a share of the stake: the house edge, what it should keep in the long run
//   Luck        House won less EV, and ±2σ: inside the band it's luck. Luck alone lands outside it about 1 time in 20,
//               so a line that stays outside says the play (NPCs' slips, a player's skill) or the edge itself is off
// A line's EV is charged on its first wager (the Ante), so its other spots (Play, Raise, Double) show no EV of their own.
// Every amount shows to the nearest £ (the percentages keep their decimals).
// Options: `open` holds the opened keys ("<game>/<line>" for a line's spots, "g:<game>" for a game's lines when
// `collapse` is on, so games start shut); `cols` names the table's saved column layout (remembered per browser):
// its columns resize from the grip on each head's right edge (double-click to reset one) and its number columns
// reorder by dragging a head onto another (Game / bet stays first); clicking a head sorts by it (numbers biggest
// first, then smallest, then back to as served; Game / bet A-Z first), the games and, inside each, its lines and
// their spots. resetColumns() forgets a layout.

const pct = (n, d) => d ? (n / d * 100).toFixed(2) + "%" : "—";
const cls = n => n > 0 ? "pos" : n < 0 ? "neg" : "";
export const toPound = p => Math.round(p / 100) * 100;   // pence to the nearest whole pound, still in pence
const WIDTHS = [240, 80, 110, 120, 110, 80, 90, 170];   // Game / bet, Bets, Staked, House won, EV, Hold, EV hold, Luck
const MIN_W = 50;
const NUMS = [1, 2, 3, 4, 5, 6, 7];                     // the columns that reorder (Game / bet stays first)

// What each column sorts by (null sorts last either way): a row's name, then its numbers; unpriced has no EV.
const SORTS = [
  r => (r.name ?? r.spot ?? "").toLowerCase(), r => r.bets, r => r.staked, r => r.net,
  (r, p) => p ? r.expected : null, r => r.staked ? r.net / r.staked : null,
  (r, p) => p && r.staked ? r.expected / r.staked : null, (r, p) => p ? r.net - r.expected : null,
];

// A table's saved layout: widths by column (in their own order), the display order of the number columns, and the
// sort ({col, dir}: dir 1 ascending, -1 descending; null as served).
function layout(H, name) {
  const key = "cols." + name;
  let saved = null;
  try { saved = JSON.parse(H.remember.get(key) || "null"); } catch (e) {}
  const w = Array.isArray(saved) ? saved : saved?.widths;   // an array is the widths-only layout from before ordering
  const widths = WIDTHS.map((d, i) => Array.isArray(w) && w[i] >= MIN_W ? w[i] : d);
  const o = saved?.order;
  const order = Array.isArray(o) && o.length === NUMS.length && NUMS.every(i => o.includes(i)) ? o : [...NUMS];
  const so = saved?.sort;
  const sort = so && SORTS[so.col] && (so.dir === 1 || so.dir === -1) ? {col: so.col, dir: so.dir} : null;
  const lay = {widths, order, sort, save: () => H.remember.set(key, JSON.stringify({widths, order, sort: lay.sort}))};
  return lay;
}
function sorted(list, lay, priced = () => true) {
  if (!lay?.sort) return list;
  const {col, dir} = lay.sort, key = SORTS[col];
  return list.map(r => [r, key(r, priced(r))]).sort(([, a], [, b]) => {
    if (a == null || b == null) return (a == null) - (b == null);
    return (a < b ? -1 : a > b ? 1 : 0) * dir;
  }).map(([r]) => r);
}
export function resetColumns(H, name) { H.remember.set("cols." + name, ""); }

export function betsTable(H, games, {open = new Set(), redraw = () => {}, empty = "No bets yet.", collapse = false, cols = ""} = {}) {
  const {el} = H;
  const money = p => H.money(toPound(p)), signed = p => H.signed(toPound(p));   // every amount to the nearest £
  if (!games.length) return el("p", {className: "empty", textContent: empty});
  const band = r => 2 * Math.sqrt(Math.max(0, r.var));
  const luck = r => {
    const d = r.net - r.expected, b = band(r);
    const out = b > 0 && Math.abs(d) > b;
    return el("td", {className: "num " + (out ? "neg" : ""), title: out ? "Outside ±2σ" : "Within ±2σ"},
      signed(d), el("span", {className: "hint", textContent: b ? ` ±${money(b)}` : ""}));
  };
  const lay = cols ? layout(H, cols) : null;
  const arrange = list => lay ? [list[0], ...lay.order.map(i => list[i]), list[8]] : list.slice(0, 8);
  const cells = (r, priced = true) => [
    el("td", {className: "num", textContent: r.bets.toLocaleString("en-GB")}),
    el("td", {className: "num", textContent: money(r.staked)}),
    el("td", {className: "num " + cls(toPound(r.net)), textContent: signed(r.net)}),
    el("td", {className: "num", textContent: priced ? money(r.expected) : "—"}),
    el("td", {className: "num", textContent: pct(r.net, r.staked)}),
    el("td", {className: "num", textContent: priced ? pct(r.expected, r.staked) : "unpriced"}),
    priced ? luck(r) : el("td", {className: "num", textContent: "—"}),
  ];
  const row = (attrs, first, r, priced) => el("tr", attrs, ...arrange([first, ...cells(r, priced), el("td", {className: "fill"})]));
  const toggle = key => { open.has(key) ? open.delete(key) : open.add(key); redraw(); };
  const rows = [];
  for (const g of sorted(games, lay)) {
    const gkey = "g:" + g.game, shut = collapse && !open.has(gkey);
    const head = row({style: "background: var(--bg-2)", className: collapse ? "click" : ""},
      el("td", {}, el("b", {textContent: (collapse ? (shut ? "▸ " : "▾ ") : "") + g.name})), g);
    for (const td of head.children) td.style.fontWeight = "600";
    if (collapse) head.addEventListener("click", () => toggle(gkey));
    rows.push(head);
    if (shut) continue;
    for (const l of sorted(g.lines, lay, l => l.priced)) {
      const key = g.game + "/" + l.line, many = l.spots.length > 1;
      const tr = row({className: many ? "click" : ""},
        el("td", {style: "padding-left: 12px"}, (many ? (open.has(key) ? "▾ " : "▸ ") : "") + l.name), l, l.priced);
      if (many) tr.addEventListener("click", () => toggle(key));
      rows.push(tr);
      if (many && open.has(key)) for (const s of sorted(l.spots, lay, () => l.priced))
        rows.push(row({className: "faint"}, el("td", {style: "padding-left: 30px", textContent: s.spot.replaceAll("_", " ")}), s, l.priced));
    }
  }
  const th = (t, c = "num", title = "") => el("th", {className: c, textContent: t, title});
  const heads = [th("Game / bet", ""), th("Bets"), th("Staked"), th("House won", "num", "Staked less returned"),
    th("EV", "num", "What the house expected to win"),
    th("Hold", "num", "House won ÷ staked: the share of the stake the house actually kept"),
    th("EV hold", "num", "EV ÷ staked: the house edge, the share it should keep in the long run"),
    th("Luck", "num", "House won less EV, with ±2σ"), el("th", {className: "fill"})];
  const table = el("table", {}, el("thead", {}, el("tr", {}, ...arrange(heads))), el("tbody", {}, ...rows));
  if (lay) arrangeable(H, table, heads, lay, redraw);
  return table;
}

// Fixed layout from a colgroup of saved widths, a grip on each head's right edge, and a filler column so the table
// still fills its panel (it grows past the panel, which scrolls sideways, once the columns add up to more). A number
// column's head drags onto another to move it there, and a click on a head sorts by it.
function arrangeable(H, table, heads, lay, redraw) {
  const {widths, order, save} = lay;
  const cols = widths.map(w => H.el("col", {style: `width: ${w}px`}));
  table.prepend(H.el("colgroup", {}, cols[0], ...order.map(i => cols[i]), H.el("col", {})));
  table.classList.add("resizable");
  const fit = () => { table.style.minWidth = widths.reduce((a, w) => a + w, 0) + "px"; };
  const set = (i, w) => { widths[i] = Math.max(MIN_W, Math.round(w)); cols[i].style.width = widths[i] + "px"; fit(); };
  fit();
  let resizing = false, dragged = null;
  const clear = () => { for (const h of heads) h.classList.remove("drop-l", "drop-r", "dragging"); };
  heads.slice(0, 8).forEach((head, i) => {
    const grip = H.el("span", {className: "col-grip", title: "Drag to resize, double-click to reset"});
    grip.addEventListener("click", e => e.stopPropagation());
    grip.addEventListener("dblclick", e => { e.stopPropagation(); set(i, WIDTHS[i]); save(); });
    grip.addEventListener("pointerdown", e => {
      e.preventDefault(); e.stopPropagation();
      resizing = true;
      const x0 = e.clientX, w0 = widths[i];
      grip.setPointerCapture(e.pointerId);
      grip.classList.add("drag");
      const move = ev => set(i, w0 + ev.clientX - x0);
      const up = () => {
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", up);
        grip.removeEventListener("pointercancel", up);
        grip.classList.remove("drag");
        resizing = false;
        save();
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up);
      grip.addEventListener("pointercancel", up);
    });
    head.append(grip);
    head.classList.add("sort");
    if (lay.sort?.col === i) head.setAttribute("aria-sort", lay.sort.dir > 0 ? "ascending" : "descending");
    head.addEventListener("click", () => {
      const first = i ? -1 : 1;   // numbers biggest first, names A-Z first
      const cur = lay.sort?.col === i ? lay.sort.dir : 0;
      lay.sort = !cur ? {col: i, dir: first} : cur === first ? {col: i, dir: -first} : null;
      save(); redraw();
    });
    if (!i) { head.title = "Click to sort"; return; }   // Game / bet stays first
    head.draggable = true;
    head.classList.add("movable");
    head.title = (head.title ? head.title + " · " : "") + "click to sort, drag to move";
    head.addEventListener("dragstart", e => {
      if (resizing) { e.preventDefault(); return; }
      dragged = i;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(i));
      head.classList.add("dragging");
    });
    head.addEventListener("dragend", () => { dragged = null; clear(); });
    const side = e => { const r = head.getBoundingClientRect(); return e.clientX < r.left + r.width / 2 ? "l" : "r"; };
    head.addEventListener("dragover", e => {
      if (dragged == null || dragged === i) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const s = side(e);
      head.classList.toggle("drop-l", s === "l"); head.classList.toggle("drop-r", s === "r");
    });
    head.addEventListener("dragleave", () => head.classList.remove("drop-l", "drop-r"));
    head.addEventListener("drop", e => {
      if (dragged == null || dragged === i) return;
      e.preventDefault();
      const from = dragged, after = side(e) === "r";
      order.splice(order.indexOf(from), 1);
      order.splice(order.indexOf(i) + (after ? 1 : 0), 0, from);
      dragged = null; clear(); save(); redraw();
    });
  });
}
