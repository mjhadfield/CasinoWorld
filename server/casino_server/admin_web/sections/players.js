// Players: everyone who's played, from the ledger, in one sortable table; a row opens to their games.
let H, data = null, sort = {key: "wagered", dir: -1}, q = "";
const openRows = new Set();

const COLS = [
  ["name", "Player", ""], ["balance", "Cash", "num"], ["bank", "Bank", "num"], ["wagered", "Staked", "num"], ["returned", "Returned", "num"],
  ["net", "Net", "num"], ["bets", "Bets", "num"], ["games", "Games", "num"], ["last_at", "Last played", ""],
];

export function init(h) {
  H = h;
  const search = h.el("input", {type: "search", placeholder: "Find a player", style: "width: 220px"});
  search.addEventListener("input", () => { q = search.value.trim().toLowerCase(); draw(); });
  h.top.append(search, h.el("span", {className: "hint", id: "players-count"}), h.el("span", {className: "grow"}),
    h.el("button", {type: "button", textContent: "Refresh", onclick: load}));
  h.view.append(h.el("div", {className: "wb"}, h.el("div", {className: "panel"}, h.el("div", {className: "pb", id: "players"}))));
}

export async function load() {
  try {
    data = await H.api("GET", "/api/players");
    for (const p of data.players) p.games_n = Object.keys(p.games).length;
    draw();
    H.status("Players loaded.");
  } catch (e) { H.status("Couldn't load players: " + e.message, "warn"); }
}

function draw() {
  const {el, money, signed} = H;
  const box = H.view.querySelector("#players");
  if (!data.players.length) { box.replaceChildren(el("p", {className: "empty", textContent: "Nobody's played yet."})); return; }
  const key = sort.key === "games" ? "games_n" : sort.key;
  const rows = data.players.filter(p => !q || p.name.toLowerCase().includes(q))
    .sort((a, b) => (typeof a[key] === "string" ? String(a[key]).localeCompare(b[key]) : (a[key] ?? 0) - (b[key] ?? 0)) * sort.dir);
  H.top.querySelector("#players-count").textContent = `${rows.length} of ${data.players.length}`;
  const cls = n => n > 0 ? "pos" : n < 0 ? "neg" : "";
  const body = [];
  for (const p of rows) {
    const games = Object.entries(p.games), opened = openRows.has(p.name);
    const tr = el("tr", {className: games.length ? "click" : ""},
      el("td", {}, games.length ? el("span", {className: "faint", textContent: opened ? "▾ " : "▸ "}) : null, el("b", {textContent: p.name})),
      el("td", {className: "num", textContent: money(p.balance)}), el("td", {className: "num " + (p.bank < 0 ? "neg" : ""), textContent: money(p.bank)}),
      el("td", {className: "num", textContent: money(p.wagered)}),
      el("td", {className: "num", textContent: money(p.returned)}), el("td", {className: "num " + cls(p.net), textContent: signed(p.net)}),
      el("td", {className: "num", textContent: p.bets}), el("td", {className: "num", textContent: games.length}),
      el("td", {textContent: p.last_at ? new Date(p.last_at).toLocaleString([], {dateStyle: "medium", timeStyle: "short"}) : "—"}));
    if (games.length) tr.addEventListener("click", () => { opened ? openRows.delete(p.name) : openRows.add(p.name); draw(); });
    body.push(tr);
    if (opened) for (const [g, s] of games.sort((a, b) => b[1].wagered - a[1].wagered)) body.push(el("tr", {},
      el("td", {className: "muted", style: "padding-left: 34px", textContent: data.games[g] || g}), el("td"), el("td"),
      el("td", {className: "num muted", textContent: money(s.wagered)}), el("td"),
      el("td", {className: "num " + cls(s.net), textContent: signed(s.net)}), el("td", {className: "num muted", textContent: s.bets}), el("td"), el("td")));
  }
  const head = el("tr", {}, ...COLS.map(([k, label, c]) => {
    const th = el("th", {className: "sort " + c, textContent: label});
    if (sort.key === k) th.setAttribute("aria-sort", sort.dir > 0 ? "ascending" : "descending");
    th.addEventListener("click", () => { sort = sort.key === k ? {key: k, dir: -sort.dir} : {key: k, dir: k === "name" ? 1 : -1}; draw(); });
    return th;
  }));
  box.replaceChildren(el("table", {}, el("thead", {}, head), el("tbody", {}, ...body)));
}
