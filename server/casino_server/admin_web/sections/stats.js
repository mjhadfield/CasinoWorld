// Player stats: the game-by-game figures behind the Players table. Pick a player on the left (or Everyone, every
// player added together) to see what they've staked and got back at each game. #stats/<player id> opens one.
let H, data = null, pick = "all";

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

function draw() {
  if (!data) return;
  const {el, money, signed} = H;
  const cls = n => n > 0 ? "pos" : n < 0 ? "neg" : "";
  const all = everyone(), people = [...data.players].sort((a, b) => b.wagered - a.wagered);
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
    el("thead", {}, el("tr", {}, ...[["Player"], ["Staked", "num"], ["Net", "num"], ["Games", "num"]].map(([t, c]) => el("th", {className: c || "", textContent: t})))),
    el("tbody", {}, row(all), ...people.map(row))));

  const pct = s => s.wagered ? (s.returned / s.wagered * 100).toFixed(1) + "%" : "—";
  const games = Object.entries(chosen.games).sort((a, b) => b[1].wagered - a[1].wagered);
  const line = (label, s, bold) => el("tr", {},
    el("td", {}, bold ? el("b", {textContent: label}) : label), el("td", {className: "num", textContent: money(s.wagered)}),
    el("td", {className: "num", textContent: money(s.returned)}), el("td", {className: "num " + cls(s.net), textContent: signed(s.net)}),
    el("td", {className: "num", textContent: s.bets}), el("td", {className: "num", textContent: pct(s)}));
  H.view.querySelector("#stats-games").replaceChildren(
    el("div", {className: "ph"}, el("b", {textContent: chosen.name}), el("span", {className: "hint", textContent: chosen.id === "all" ? "every player, game by game" : "game by game"})),
    el("div", {className: "pb"}, games.length
      ? el("table", {},
          el("thead", {}, el("tr", {}, ...[["Game"], ["Staked", "num"], ["Returned", "num"], ["Net", "num"], ["Bets", "num"], ["Returned %", "num"]].map(([t, c]) => el("th", {className: c || "", textContent: t})))),
          el("tbody", {}, ...games.map(([g, s]) => line(data.games[g] || g, s)), line("All games", chosen, true)))
      : el("p", {className: "empty", textContent: "No bets yet."})));
}
