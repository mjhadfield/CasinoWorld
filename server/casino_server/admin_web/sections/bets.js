// The bets table the House section, the NPC panel and Player stats share: each game, its bet lines (a decision game's
// main line, each side bet) and, opened, each line's spots, against what the house expected to win (tracking.py).
//   House won   staked less returned: the house's actual win (+ the house is up)
//   EV          the house's expected win on what was staked (the spot's edge x stake; a Craps bet that wins and stays
//               up is charged again)
//   Hold, EV hold   each as a share of the stake
//   Luck        House won less EV, and ±2σ: inside the band it's luck. Luck alone lands outside it about 1 time in 20,
//               so a line that stays outside says the play (NPCs' slips, a player's skill) or the edge itself is off
// A line's EV is charged on its first wager (the Ante), so its other spots (Play, Raise, Double) show no EV of their own.

const pct = (n, d) => d ? (n / d * 100).toFixed(2) + "%" : "—";
const cls = n => n > 0 ? "pos" : n < 0 ? "neg" : "";

export function betsTable(H, games, {open = new Set(), redraw = () => {}, empty = "No bets yet."} = {}) {
  const {el, money, signed} = H;
  if (!games.length) return el("p", {className: "empty", textContent: empty});
  const band = r => 2 * Math.sqrt(Math.max(0, r.var));
  const luck = r => {
    const d = r.net - r.expected, b = band(r);
    const out = b > 0 && Math.abs(d) > b;
    return el("td", {className: "num " + (out ? "neg" : ""), title: out ? "Outside ±2σ" : "Within ±2σ"},
      signed(Math.round(d)), el("span", {className: "hint", textContent: b ? ` ±${money(Math.round(b))}` : ""}));
  };
  const cells = (r, priced = true) => [
    el("td", {className: "num", textContent: r.bets.toLocaleString("en-GB")}),
    el("td", {className: "num", textContent: money(r.staked)}),
    el("td", {className: "num " + cls(r.net), textContent: signed(r.net)}),
    el("td", {className: "num", textContent: priced ? money(Math.round(r.expected)) : "—"}),
    el("td", {className: "num", textContent: pct(r.net, r.staked)}),
    el("td", {className: "num", textContent: priced ? pct(r.expected, r.staked) : "unpriced"}),
    priced ? luck(r) : el("td", {className: "num", textContent: "—"}),
  ];
  const rows = [];
  for (const g of games) {
    const head = el("tr", {style: "background: var(--bg-2)"}, el("td", {}, el("b", {textContent: g.name})), ...cells(g));
    for (const td of head.children) td.style.fontWeight = "600";
    rows.push(head);
    for (const l of g.lines) {
      const key = g.game + "/" + l.line, many = l.spots.length > 1;
      const tr = el("tr", {className: many ? "click" : ""},
        el("td", {style: "padding-left: 12px"}, (many ? (open.has(key) ? "▾ " : "▸ ") : "") + l.name), ...cells(l, l.priced));
      if (many) tr.addEventListener("click", () => { open.has(key) ? open.delete(key) : open.add(key); redraw(); });
      rows.push(tr);
      if (many && open.has(key)) for (const s of l.spots)
        rows.push(el("tr", {className: "faint"}, el("td", {style: "padding-left: 30px", textContent: s.spot.replaceAll("_", " ")}), ...cells(s, l.priced)));
    }
  }
  const th = (t, c = "num", title = "") => el("th", {className: c, textContent: t, title});
  return el("table", {},
    el("thead", {}, el("tr", {}, th("Game / bet", ""), th("Bets"), th("Staked"), th("House won", "num", "Staked less returned"),
      th("EV", "num", "What the house expected to win"), th("Hold"), th("EV hold"),
      th("Luck", "num", "House won less EV, with ±2σ"))),
    el("tbody", {}, ...rows));
}
