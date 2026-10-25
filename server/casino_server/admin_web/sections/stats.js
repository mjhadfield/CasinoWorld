// Player stats: the game-by-game figures behind the Players table. Pick a player on the left (or Everyone, every
// player added together) to see what they've staked and got back at each game. #stats/<player id> opens one.
let H, data = null, pick = "all", whoSort = {key: "wagered", dir: -1}, gameSort = {key: "wagered", dir: -1};

export function init(h) {
  H = h;
  h.top.append(h.el("span", {className: "grow"}), h.el("button", {type: "button", textContent: "Refresh", onclick: load}));
  h.view.append(h.el("div", {className: "wb", style: "grid-template-columns: 420px minmax(0, 1fr)"},
    h.el("div", {className: "panel"}, h.el("div", {className: "pb", id: "stats-who"})),
    h.el("div", {className: "panel", id: "stats-games"})));
  window.addEventListener("hashchange", fromHash);
}

export async function load() {
  try {
    data = await H.api("GET", "/api/players");
    fromHash(); draw();
    H.status("Player stats loaded.");
  } catch (e) { H.status("Couldn't load player stats: " + e.message, "warn"); }
}
export function shown(on) { if (on && data) { fromHash(); draw(); } }

function fromHash() {
  const [top, id] = location.hash.slice(1).split("/");
  if (top !== "stats" || !id || !data) return;
  if (data.players.some(p => String(p.id) === id)) { pick = +id; draw(); }
}

function everyone() {   // every player's games added together
  const games = {};
  for (const p of data.players) for (const [g, s] of Object.entries(p.games)) {
    const t = games[g] ||= {wagered: 0, returned: 0, net: 0, bets: 0};
    t.wagered += s.wagered; t.returned += s.returned; t.net += s.net; t.bets += s.bets;
  }
  const sum = k => data.players.reduce((n, p) => n + p[k], 0);
  return {id: "all", name: "Everyone", games, wagered: sum("wagered"), returned: sum("returned"), net: sum("net"), bets: sum("bets")};
}

// Click a heading to sort by it; click again to flip. Names start A→Z, figures biggest first.
function head(cols, sort, set) {
  return H.el("thead", {}, H.el("tr", {}, ...cols.map(([label, k, c]) => {
    const th = H.el("th", {className: "sort " + (c || ""), textContent: label});
    if (sort.key === k) th.setAttribute("aria-sort", sort.dir > 0 ? "ascending" : "descending");
    th.addEventListener("click", () => { set(sort.key === k ? {key: k, dir: -sort.dir} : {key: k, dir: k === "name" ? 1 : -1}); draw(); });
    return th;
  })));
}
const by = (sort, val) => (a, b) => {
  const x = val(a, sort.key), y = val(b, sort.key);
  return (typeof x === "string" ? x.localeCompare(y) : (x ?? -1) - (y ?? -1)) * sort.dir;
};

function draw() {
  if (!data) return;
  const {el, money, signed} = H;
  const cls = n => n > 0 ? "pos" : n < 0 ? "neg" : "";
  const all = everyone(), people = [...data.players].sort(by(whoSort, (p, k) => k === "games" ? Object.keys(p.games).length : p[k]));
  const chosen = pick === "all" ? all : data.players.find(p => p.id === pick) || all;
  const row = p => {
    const tr = el("tr", {className: "click" + (chosen === p ? " sel" : ""), tabIndex: 0},
      el("td", {}, el("b", {textContent: p.name})), el("td", {className: "num", textContent: money(p.wagered)}),
      el("td", {className: "num " + cls(p.net), textContent: signed(p.net)}), el("td", {className: "num", textContent: Object.keys(p.games).length}));
    const go = () => { pick = p.id; history.replaceState(null, "", p.id === "all" ? "#stats" : "#stats/" + p.id); draw(); };
    tr.addEventListener("click", go);
    tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    return tr;
  };
  H.view.querySelector("#stats-who").replaceChildren(el("table", {},
    head([["Player", "name"], ["Staked", "wagered", "num"], ["Net", "net", "num"], ["Games", "games", "num"]], whoSort, s => whoSort = s),
    el("tbody", {}, row(all), ...people.map(row))));

  const pct = s => s.wagered ? (s.returned / s.wagered * 100).toFixed(1) + "%" : "—";
  const games = Object.entries(chosen.games).sort(by(gameSort, ([g, s], k) =>
    k === "name" ? data.games[g] || g : k === "pct" ? (s.wagered ? s.returned / s.wagered : null) : s[k]));
  const line = (label, s, bold) => el("tr", {},
    el("td", {}, bold ? el("b", {textContent: label}) : label), el("td", {className: "num", textContent: money(s.wagered)}),
    el("td", {className: "num", textContent: money(s.returned)}), el("td", {className: "num " + cls(s.net), textContent: signed(s.net)}),
    el("td", {className: "num", textContent: s.bets}), el("td", {className: "num", textContent: pct(s)}));
  H.view.querySelector("#stats-games").replaceChildren(
    el("div", {className: "ph"}, el("b", {textContent: chosen.name}), el("span", {className: "hint", textContent: chosen.id === "all" ? "every player, game by game" : "game by game"})),
    el("div", {className: "pb"}, games.length
      ? el("table", {},
          head([["Game", "name"], ["Staked", "wagered", "num"], ["Returned", "returned", "num"], ["Net", "net", "num"], ["Bets", "bets", "num"],
            ["Returned %", "pct", "num"]], gameSort, s => gameSort = s),
          el("tbody", {}, ...games.map(([g, s]) => line(data.games[g] || g, s)), line("All games", chosen, true)))
      : el("p", {className: "empty", textContent: "No bets yet."})));
}
