// Players: every character, from the ledger, in one sortable table, with who's on now. A device's account holds up to
// three characters; protecting, timing out, banning and letting back in are the account's, so they cover all of them.
// A row opens the character on the right: protect its account (then nothing here can delete, ban or time it out), time
// it out, ban it, let it back in, or delete the character or the whole account for good. Their game-by-game figures are on Player stats. Tick several (multi.js) to do any of that
// to them all at once from the bar over the table; protected players are skipped by anything that would change them.
import { Picker, each, report } from "/admin-ui/sections/multi.js";
let H, data = null, sort = {key: "wagered", dir: -1}, q = "", selected = null, pollTimer = null, picker;

const COLS = [
  ["name", "Player", ""], ["difficulty", "Difficulty", ""], ["status", "Now", ""], ["balance", "Cash", "num"], ["bank", "Bank", "num"], ["wagered", "Staked", "num"],
  ["returned", "Returned", "num"], ["net", "Net", "num"], ["bets", "Bets", "num"], ["games", "Games", "num"], ["last_at", "Last played", ""],
];
const TIMEOUTS = [[15, "15 minutes"], [60, "1 hour"], [360, "6 hours"], [1440, "1 day"], [10080, "1 week"]];
const when = t => new Date(t).toLocaleString([], {dateStyle: "medium", timeStyle: "short"});
const DIFFICULTY = {easy: "Easy", normal: "Normal", hard: "Hard"};
const sameDevice = p => data.players.filter(o => o.account_id === p.account_id);   // p and its account's other characters

export function init(h) {
  H = h;
  const search = h.el("input", {type: "search", placeholder: "Find a player", style: "width: 220px"});
  search.addEventListener("input", () => { q = search.value.trim().toLowerCase(); draw(); });
  h.top.append(search, h.el("span", {className: "hint", id: "players-count"}), h.el("span", {className: "grow"}),
    h.el("button", {type: "button", textContent: "Refresh", onclick: load}));
  picker = new Picker(h.el, () => { draw(); bulkBar(); });
  h.view.append(h.el("div", {className: "wb", style: "grid-template-columns: minmax(0, 1fr) 420px"},
    h.el("div", {className: "panel"}, h.el("div", {className: "ph", id: "players-bulk", hidden: true}), h.el("div", {className: "pb", id: "players"})),
    h.el("div", {className: "panel", id: "player-card"})));
}

export async function load(quiet) {
  try {
    data = await H.api("GET", "/api/players");
    for (const p of data.players) p.games_n = Object.keys(p.games).length;
    if (selected) selected = data.players.find(p => p.id === selected.id) || null;
    picker.keep(data.players.map(p => p.id));
    draw(); card(); bulkBar();
    if (quiet !== true) H.status("Players loaded.");
  } catch (e) { H.status("Couldn't load players: " + e.message, "warn"); }
}
export function shown(on) {   // who's on now
  clearInterval(pollTimer);
  if (on && data) pollTimer = setInterval(() => { if (!document.hidden && !H.view.querySelector(".confirm, input:focus")) load(true); }, 10000);
}

function statusOf(p) {   // [text, class]
  if (p.banned) return ["Banned", "neg"];
  if (p.timeout_until) return ["Timed out till " + new Date(p.timeout_until * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}), "neg"];
  return p.online ? ["Playing" + (p.casino && Object.keys(data.casinos || {}).length > 1 ? " · " + (data.casinos[p.casino] || p.casino) : ""), "pos"] : ["", ""];
}

function pitOf(p) {   // [text, class]: what the Blackjack pit thinks of them (heat.py; held in memory, a restart forgives)
  const pit = p.pit || {heat: 0};
  if (pit.backed_off_min != null) return [`Backed off · ${pit.backed_off_min} min`, "neg"];
  if (pit.warned) return [`Warned · heat ${pit.heat}`, "neg"];
  return [pit.heat ? `Heat ${pit.heat}` : "Cool", ""];
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
  picker.shown(rows.map(p => p.id));
  const cls = n => n > 0 ? "pos" : n < 0 ? "neg" : "";
  const body = rows.map(p => {
    const [st, stCls] = statusOf(p);
    const tr = el("tr", {className: "click" + (selected && selected.id === p.id ? " sel" : ""), tabIndex: 0},
      picker.box(p.id, p.name),
      el("td", {}, el("b", {textContent: p.name}), p.protected ? el("span", {className: "tag gold", style: "margin-left: 6px", textContent: "Protected"}) : null),
      el("td", {textContent: DIFFICULTY[p.difficulty] || p.difficulty}),
      el("td", {className: stCls, textContent: st}),
      el("td", {className: "num", textContent: money(p.balance)}), el("td", {className: "num " + (p.bank < 0 ? "neg" : ""), textContent: money(p.bank)}),
      el("td", {className: "num", textContent: money(p.wagered)}),
      el("td", {className: "num", textContent: money(p.returned)}), el("td", {className: "num " + cls(p.net), textContent: signed(p.net)}),
      el("td", {className: "num", textContent: p.bets}), el("td", {className: "num", textContent: p.games_n}),
      el("td", {textContent: p.last_at ? when(p.last_at) : "—"}));
    const pick = () => { selected = p; draw(); card(); };
    picker.row(tr, p.id, pick);
    tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    return tr;
  });
  const head = el("tr", {}, picker.head(), ...COLS.map(([k, label, c]) => {
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
  const p = selected, locked = p.protected, others = sameDevice(p).filter(o => o.id !== p.id);
  const device = others.length ? `${p.name}'s device (all ${others.length + 1} characters)` : p.name;
  const stat = (label, value, c = "") => el("div", {className: "stat"}, el("small", {textContent: label}), el("b", {className: c, textContent: value}));
  const protect = el("input", {type: "checkbox", id: "pl-protect", checked: p.protected});
  protect.addEventListener("change", () => act("protect", {on: protect.checked},
    protect.checked ? `${device} is protected: nothing here can delete, ban or time them out.` : `${device} isn't protected any more.`));

  const sections = [];
  if (p.banned || p.timeout_until) {
    const lift = el("button", {type: "button", id: "pl-lift", textContent: "Let them back in", disabled: locked, onclick: () => act("lift", undefined, `${device} can come back in.`)});
    sections.push(el("div", {className: "card"},
      el("b", {className: "neg", textContent: p.banned ? "Banned" : "Timed out till " + when(p.timeout_until * 1000)}),
      p.bar_reason ? el("p", {className: "hint", style: "margin: 4px 0 0", textContent: "Reason: " + p.bar_reason}) : null,
      el("div", {className: "controls", style: "margin-top: 8px"}, lift)));
  }
  const reason = el("input", {id: "pl-reason", maxLength: 200, placeholder: "Optional: they see it", disabled: locked});
  const length = el("select", {id: "pl-length", disabled: locked}, ...TIMEOUTS.map(([m, t]) => el("option", {value: m, textContent: t, selected: m === 60})));
  const timeout = el("button", {type: "button", id: "pl-timeout", textContent: "Time out", disabled: locked});
  timeout.addEventListener("click", () => act("timeout", {minutes: +length.value, reason: reason.value},
    `${device} is timed out for ${length.selectedOptions[0].textContent}${p.online ? ": they've been sent out" : ""}.`));
  const ban = el("button", {type: "button", className: "danger", id: "pl-ban", textContent: "Ban", disabled: locked || p.banned});
  ban.addEventListener("click", () => confirm(ban, `Ban ${device}? They can't come in until you let them back.`,
    () => act("ban", {reason: reason.value}, `${device} is banned${p.online ? ": they've been sent out" : ""}.`)));
  const del = el("button", {type: "button", className: "ghost danger", id: "pl-delete", textContent: "Delete character", disabled: locked});
  del.addEventListener("click", () => confirm(del, `Delete ${p.name}, their money and history, for good? This can't be undone.`, remove));
  const delAll = others.length ? el("button", {type: "button", className: "ghost danger", id: "pl-delete-account", textContent: "Delete the whole account", disabled: locked}) : null;
  delAll?.addEventListener("click", () => confirm(delAll, `Delete ${p.name}, ${others.map(o => o.name).join(", ")} and the device's account, for good? This can't be undone.`, removeAccount));
  const stats = el("a", {href: "#stats/" + p.id, textContent: "Game by game on Player stats"});

  box.replaceChildren(
    el("div", {className: "ph"}, el("b", {textContent: p.name}), p.protected ? el("span", {className: "tag gold", textContent: "Protected"}) : null),
    el("div", {className: "pb padded", style: "display: grid; gap: var(--gap); align-content: start"},
      el("div", {className: "stats"}, stat("Now", statusOf(p)[0] || "Not playing", statusOf(p)[1]), stat("Cash", money(p.balance)), stat("Bank", money(p.bank), p.bank < 0 ? "neg" : ""),
        stat("Net", signed(p.net), p.net > 0 ? "pos" : p.net < 0 ? "neg" : ""), stat("Pit", ...pitOf(p)), stat("Difficulty", DIFFICULTY[p.difficulty] || p.difficulty),
        stat("Made", p.created_at ? when(p.created_at) : "—"), stat("Player no.", p.id), stat("Account no.", p.account_id)),
      el("p", {className: "hint", style: "margin: 0", textContent: others.length ? "Also on this device: " + others.map(o => o.name).join(", ") : "The only character on this device."}),
      stats,
      el("label", {className: "controls"}, protect, el("span", {}, el("b", {textContent: "Protected"}), el("span", {className: "hint", textContent: " — the device's account: can't be deleted, banned or timed out (untick first)"}))),
      ...sections,
      el("div", {className: "card", style: "display: grid; gap: var(--gap)" + (locked ? "; opacity: .55" : "")},
        el("label", {className: "field"}, el("span", {textContent: "Reason (for a timeout or ban)"}), reason),
        el("div", {className: "controls"}, length, timeout, el("span", {className: "grow", style: "flex: 1"}), ban),
        el("p", {className: "hint", style: "margin: 0", textContent: "Either sends them out at once if they're playing (a hand they're in plays out without them). Bans and timeouts are the device's account's, so they cover every character on it; a new browser comes in as a new account."})),
      el("div", {className: "controls"}, del, delAll),
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
async function removeAccount() {
  const names = sameDevice(selected).map(o => o.name).join(", ");
  try {
    await H.api("DELETE", "/api/accounts/" + selected.account_id);
    selected = null;
    H.status(`Deleted ${names} and their account for good.`, "ok");
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

// ------------------------------------------------------------ the ticked players, all at once
function bulkBar() {
  const {el} = H;
  const bar = H.view.querySelector("#players-bulk");
  bar.hidden = !picker.size;
  if (!picker.size) return;
  const picked = data.players.filter(p => picker.has(p.id)), n = picked.length;
  const who = n === 1 ? "1 player" : n + " players";
  const reason = el("input", {placeholder: "Reason (optional)", maxLength: 200, style: "width: 180px", ariaLabel: "Reason"});
  const length = el("select", {ariaLabel: "How long"}, ...TIMEOUTS.map(([m, t]) => el("option", {value: m, textContent: t, selected: m === 60})));
  const btn = (text, fn, cls = "") => el("button", {type: "button", className: cls, textContent: text, onclick: fn});
  const ask = (b, question, yes) => {
    const y = el("button", {type: "button", className: "primary", textContent: "Yes"}), no = el("button", {type: "button", textContent: "No"});
    b.replaceWith(el("span", {className: "confirm"}, question, y, no));
    y.addEventListener("click", yes); no.addEventListener("click", bulkBar);
  };
  const run = async (verb, call) => {
    bar.querySelectorAll("button").forEach(b => { b.disabled = true; });
    const r = await each(picked, call);
    H.status(report(verb, r), r.skipped.length ? "warn" : "ok");
    if (selected && r.done.includes(selected.name) && verb === "Deleted") selected = null;
    picker.ids.clear();
    await load(true);
  };
  const post = (what, body) => p => H.api("POST", `/api/players/${p.id}/${what}`, body ?? {});
  const ban = btn("Ban", null, "danger");
  ban.onclick = () => ask(ban, `Ban ${who}?`, () => run("Banned", post("ban", {reason: reason.value})));
  const del = btn("Delete for good", null, "ghost danger");
  del.onclick = () => ask(del, `Delete ${who}, their money and history, for good?`, () => run("Deleted", p => H.api("DELETE", "/api/players/" + p.id)));
  bar.replaceChildren(el("b", {textContent: who + " ticked"}),
    btn("Protect", () => run("Protected", post("protect", {on: true}))),
    btn("Unprotect", () => run("Unprotected", post("protect", {on: false}))),
    el("span", {className: "sep"}), reason, length,
    btn("Time out", () => run("Timed out", post("timeout", {minutes: +length.value, reason: reason.value}))),
    ban, btn("Let back in", () => run("Let back in", post("lift"))),
    el("span", {className: "sep"}), del,
    el("span", {className: "grow"}), btn("Clear", () => picker.clear(), "ghost"));
}
