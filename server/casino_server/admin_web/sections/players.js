// Players: everyone who's played, from the ledger, in one sortable table, with who's on now. A row opens them on the
// right: protect them (then nothing here can delete, ban or time them out), time them out, ban them, let them back in,
// or delete them for good. Their game-by-game figures are on Player stats.
let H, data = null, sort = {key: "wagered", dir: -1}, q = "", selected = null, pollTimer = null;

const COLS = [
  ["name", "Player", ""], ["status", "Now", ""], ["balance", "Cash", "num"], ["bank", "Bank", "num"], ["wagered", "Staked", "num"],
  ["returned", "Returned", "num"], ["net", "Net", "num"], ["bets", "Bets", "num"], ["games", "Games", "num"], ["last_at", "Last played", ""],
];
const TIMEOUTS = [[15, "15 minutes"], [60, "1 hour"], [360, "6 hours"], [1440, "1 day"], [10080, "1 week"]];
const when = t => new Date(t).toLocaleString([], {dateStyle: "medium", timeStyle: "short"});

export function init(h) {
  H = h;
  const search = h.el("input", {type: "search", placeholder: "Find a player", style: "width: 220px"});
  search.addEventListener("input", () => { q = search.value.trim().toLowerCase(); draw(); });
  h.top.append(search, h.el("span", {className: "hint", id: "players-count"}), h.el("span", {className: "grow"}),
    h.el("button", {type: "button", textContent: "Refresh", onclick: load}));
  h.view.append(h.el("div", {className: "wb", style: "grid-template-columns: minmax(0, 1fr) 420px"},
    h.el("div", {className: "panel"}, h.el("div", {className: "pb", id: "players"})),
    h.el("div", {className: "panel", id: "player-card"})));
}

export async function load(quiet) {
  try {
    data = await H.api("GET", "/api/players");
    for (const p of data.players) p.games_n = Object.keys(p.games).length;
    if (selected) selected = data.players.find(p => p.id === selected.id) || null;
    draw(); card();
    if (quiet !== true) H.status("Players loaded.");
  } catch (e) { H.status("Couldn't load players: " + e.message, "warn"); }
}
export function shown(on) {   // who's on now
  clearInterval(pollTimer);
  if (on && data) pollTimer = setInterval(() => { if (!document.hidden && !H.view.querySelector("#player-card .confirm, #player-card input:focus")) load(true); }, 10000);
}

function statusOf(p) {   // [text, class]
  if (p.banned) return ["Banned", "neg"];
  if (p.timeout_until) return ["Timed out till " + new Date(p.timeout_until * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}), "neg"];
  return p.online ? ["Playing", "pos"] : ["", ""];
}

function draw() {
  const {el, money, signed} = H;
  const box = H.view.querySelector("#players");
  if (!data.players.length) { box.replaceChildren(el("p", {className: "empty", textContent: "Nobody's played yet."})); return; }
  const key = sort.key === "games" ? "games_n" : sort.key;
  const val = p => key === "status" ? (p.banned ? 0 : p.timeout_until ? 1 : p.online ? 2 : 3) : p[key];
  const rows = data.players.filter(p => !q || p.name.toLowerCase().includes(q))
    .sort((a, b) => (typeof val(a) === "string" ? String(val(a)).localeCompare(val(b)) : (val(a) ?? 0) - (val(b) ?? 0)) * sort.dir);
  H.top.querySelector("#players-count").textContent = `${rows.length} of ${data.players.length}`;
  const cls = n => n > 0 ? "pos" : n < 0 ? "neg" : "";
  const body = rows.map(p => {
    const [st, stCls] = statusOf(p);
    const tr = el("tr", {className: "click" + (selected && selected.id === p.id ? " sel" : ""), tabIndex: 0},
      el("td", {}, el("b", {textContent: p.name}), p.protected ? el("span", {className: "tag gold", style: "margin-left: 6px", textContent: "Protected"}) : null),
      el("td", {className: stCls, textContent: st}),
      el("td", {className: "num", textContent: money(p.balance)}), el("td", {className: "num " + (p.bank < 0 ? "neg" : ""), textContent: money(p.bank)}),
      el("td", {className: "num", textContent: money(p.wagered)}),
      el("td", {className: "num", textContent: money(p.returned)}), el("td", {className: "num " + cls(p.net), textContent: signed(p.net)}),
      el("td", {className: "num", textContent: p.bets}), el("td", {className: "num", textContent: p.games_n}),
      el("td", {textContent: p.last_at ? when(p.last_at) : "—"}));
    const pick = () => { selected = p; draw(); card(); };
    tr.addEventListener("click", pick);
    tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    return tr;
  });
  const head = el("tr", {}, ...COLS.map(([k, label, c]) => {
    const th = el("th", {className: "sort " + c, textContent: label});
    if (sort.key === k) th.setAttribute("aria-sort", sort.dir > 0 ? "ascending" : "descending");
    th.addEventListener("click", () => { sort = sort.key === k ? {key: k, dir: -sort.dir} : {key: k, dir: k === "name" || k === "status" ? 1 : -1}; draw(); });
    return th;
  }));
  box.replaceChildren(el("table", {}, el("thead", {}, head), el("tbody", {}, ...body)));
}

// ------------------------------------------------------------ the selected player
function card() {
  const {el, money, signed} = H;
  const box = H.view.querySelector("#player-card");
  if (!selected) {
    box.replaceChildren(el("div", {className: "ph", textContent: "Player"}), el("p", {className: "empty", textContent: "Pick a player to protect, time out, ban or delete them."}));
    return;
  }
  const p = selected, locked = p.protected;
  const stat = (label, value, c = "") => el("div", {className: "stat"}, el("small", {textContent: label}), el("b", {className: c, textContent: value}));
  const protect = el("input", {type: "checkbox", id: "pl-protect", checked: p.protected});
  protect.addEventListener("change", () => act("protect", {on: protect.checked},
    protect.checked ? `${p.name} is protected: nothing here can delete, ban or time them out.` : `${p.name} isn't protected any more.`));

  const sections = [];
  if (p.banned || p.timeout_until) {
    const lift = el("button", {type: "button", id: "pl-lift", textContent: "Let them back in", disabled: locked, onclick: () => act("lift", undefined, `${p.name} can come back in.`)});
    sections.push(el("div", {className: "card"},
      el("b", {className: "neg", textContent: p.banned ? "Banned" : "Timed out till " + when(p.timeout_until * 1000)}),
      p.bar_reason ? el("p", {className: "hint", style: "margin: 4px 0 0", textContent: "Reason: " + p.bar_reason}) : null,
      el("div", {className: "controls", style: "margin-top: 8px"}, lift)));
  }
  const reason = el("input", {id: "pl-reason", maxLength: 200, placeholder: "Optional: they see it", disabled: locked});
  const length = el("select", {id: "pl-length", disabled: locked}, ...TIMEOUTS.map(([m, t]) => el("option", {value: m, textContent: t, selected: m === 60})));
  const timeout = el("button", {type: "button", id: "pl-timeout", textContent: "Time out", disabled: locked});
  timeout.addEventListener("click", () => act("timeout", {minutes: +length.value, reason: reason.value},
    `${p.name} is timed out for ${length.selectedOptions[0].textContent}${p.online ? ": they've been sent out" : ""}.`));
  const ban = el("button", {type: "button", className: "danger", id: "pl-ban", textContent: "Ban", disabled: locked || p.banned});
  ban.addEventListener("click", () => confirm(ban, `Ban ${p.name}? They can't come in until you let them back.`,
    () => act("ban", {reason: reason.value}, `${p.name} is banned${p.online ? ": they've been sent out" : ""}.`)));
  const del = el("button", {type: "button", className: "ghost danger", id: "pl-delete", textContent: "Delete for good", disabled: locked});
  del.addEventListener("click", () => confirm(del, `Delete ${p.name}, their money and history, for good? This can't be undone.`, remove));
  const stats = el("a", {href: "#stats/" + p.id, textContent: "Game by game on Player stats"});

  box.replaceChildren(
    el("div", {className: "ph"}, el("b", {textContent: p.name}), p.protected ? el("span", {className: "tag gold", textContent: "Protected"}) : null),
    el("div", {className: "pb padded", style: "display: grid; gap: var(--gap); align-content: start"},
      el("div", {className: "stats"}, stat("Now", statusOf(p)[0] || "Not playing", statusOf(p)[1]), stat("Cash", money(p.balance)), stat("Bank", money(p.bank), p.bank < 0 ? "neg" : ""),
        stat("Net", signed(p.net), p.net > 0 ? "pos" : p.net < 0 ? "neg" : ""), stat("First came", p.created_at ? when(p.created_at) : "—"), stat("Player no.", p.id)),
      stats,
      el("label", {className: "controls"}, protect, el("span", {}, el("b", {textContent: "Protected"}), el("span", {className: "hint", textContent: " — can't be deleted, banned or timed out (untick first)"}))),
      ...sections,
      el("div", {className: "card", style: "display: grid; gap: var(--gap)" + (locked ? "; opacity: .55" : "")},
        el("label", {className: "field"}, el("span", {textContent: "Reason (for a timeout or ban)"}), reason),
        el("div", {className: "controls"}, length, timeout, el("span", {className: "grow", style: "flex: 1"}), ban),
        el("p", {className: "hint", style: "margin: 0", textContent: "Either sends them out at once if they're playing (a hand they're in plays out without them). Bans and timeouts follow their device's account: a new browser comes in as a new player."})),
      el("div", {className: "controls"}, del),
      locked ? el("p", {className: "hint", style: "margin: 0", textContent: "Protected: untick Protected to time out, ban or delete them."}) : null));
}

function confirm(btn, question, yes) {
  const {el} = H;
  const y = el("button", {type: "button", className: "primary", textContent: "Yes"}), n = el("button", {type: "button", textContent: "No"});
  btn.replaceWith(el("span", {className: "confirm"}, question, y, n));
  y.addEventListener("click", yes); n.addEventListener("click", card);
}
async function act(what, body, message) {
  try {
    await H.api("POST", `/api/players/${selected.id}/${what}`, body ?? {});
    H.status(message, "ok");
  } catch (e) { H.status(e.message, "warn"); }
  await load(true);
}
async function remove() {
  const name = selected.name;
  try {
    await H.api("DELETE", "/api/players/" + selected.id);
    selected = null;
    H.status(`Deleted ${name} for good.`, "ok");
  } catch (e) { H.status(e.message, "warn"); }
  await load(true);
}
