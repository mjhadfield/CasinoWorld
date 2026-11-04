// Stats archive: frozen copies of the casino's figures, taken before NPC stats are wiped (stats_archive.py; the
// admin CLI's archive-stats takes one). Pick an archive on the left; #archive/<id> opens one. Nothing here changes:
// an archive is what the figures were when it was taken. "House" is the house's side: staked less returned.
let H, list = [], archive = null, pick = null;
const sorts = {};   // table key -> {key, dir}

export function init(h) {
  H = h;
  h.top.append(h.el("span", {className: "grow"}), h.el("button", {type: "button", textContent: "Refresh", onclick: load}));
  h.view.append(h.el("div", {className: "wb", style: "grid-template-columns: 300px minmax(0, 1fr)"},
    h.el("div", {className: "panel"}, h.el("div", {className: "ph"}, h.el("b", {textContent: "Archives"})), h.el("div", {className: "pb", id: "arch-list"})),
    h.el("div", {className: "panel"}, h.el("div", {className: "ph", id: "arch-head"}), h.el("div", {className: "pb padded", id: "arch-body"}))));
  window.addEventListener("hashchange", fromHash);
}

export async function load() {
  try {
    list = (await H.api("GET", "/api/stats/archives")).archives;
    drawList();
    const [top, id] = location.hash.slice(1).split("/");
    await open(top === "archive" && id ? id : pick || list[0]?.id);
    H.status(list.length ? "Stats archive loaded." : "No archives yet.");
  } catch (e) { H.status("Couldn't load the Stats archive: " + e.message, "warn"); }
}
export function shown(on) { if (on) fromHash(); }

function fromHash() {
  const [top, id] = location.hash.slice(1).split("/");
  if (top === "archive" && id && id !== pick && list.some(a => a.id === id)) open(id);
}

async function open(id) {
  if (!id) { archive = null; pick = null; return draw(); }
  pick = id;
  drawList();
  try { archive = await H.api("GET", "/api/stats/archives/" + encodeURIComponent(id)); }
  catch (e) { archive = null; H.status("Couldn't load that archive: " + e.message, "warn"); }
  draw();
}

const day = iso => iso ? new Date(iso).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric"}) : "—";
const when = iso => iso ? new Date(iso).toLocaleString("en-GB", {day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"}) : "—";
const n = v => v == null ? "—" : Number(v).toLocaleString("en-GB");
const pct = v => v == null ? "—" : v.toFixed(2) + "%";
const cls = v => v > 0 ? "pos" : v < 0 ? "neg" : "";

function drawList() {
  const {el} = H;
  H.view.querySelector("#arch-list").replaceChildren(list.length
    ? el("table", {}, el("tbody", {}, ...list.map(a => {
        const tr = el("tr", {className: "click" + (a.id === pick ? " sel" : ""), tabIndex: 0},
          el("td", {className: "wrap"}, el("b", {textContent: a.title}), el("div", {className: "hint", textContent: `${day(a.period?.from)} – ${day(a.period?.to)}`})));
        const go = () => { history.replaceState(null, "", "#archive/" + a.id); open(a.id); };
        tr.addEventListener("click", go);
        tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
        return tr;
      })))
    : el("p", {className: "empty", textContent: "No archives yet. Take one with: python -m casino_server.admin archive-stats \"title\""}));
}

// A sortable table: cols are [label, key, kind] (kind: "money", "signed", "pct", "n", "text"); rows are objects.
// Click a heading to sort by it, again to flip. Text starts A→Z, figures biggest first.
function table(id, cols, rows, opts = {}) {
  const {el, money, signed} = H;
  const sort = sorts[id] ||= opts.sort || {key: null, dir: -1};
  const val = (r, k) => (opts.value ? opts.value(r, k) : undefined) ?? r[k];
  const sorted = sort.key == null ? rows : [...rows].sort((a, b) => {
    const x = val(a, sort.key), y = val(b, sort.key);
    return (typeof x === "string" || typeof y === "string" ? String(x ?? "").localeCompare(String(y ?? "")) : (x ?? -Infinity) - (y ?? -Infinity)) * sort.dir;
  });
  const cell = (r, [, k, kind]) => {
    const v = val(r, k), num = kind && kind !== "text";
    const text = kind === "money" ? (v == null ? "—" : money(v)) : kind === "signed" ? (v == null ? "—" : signed(v))
      : kind === "pct" ? pct(v) : kind === "n" ? n(v) : (opts.show ? opts.show(r, k) : v) ?? "—";
    return el("td", {className: (num ? "num " : "") + (kind === "signed" || kind === "pct" ? cls(v) : ""), textContent: text});
  };
  return el("div", {className: "scroll"}, el("table", {},
    el("thead", {}, el("tr", {}, ...cols.map(([label, k, kind]) => {
      const th = el("th", {className: "sort" + (kind && kind !== "text" ? " num" : ""), textContent: label});
      if (sort.key === k) th.setAttribute("aria-sort", sort.dir > 0 ? "ascending" : "descending");
      th.addEventListener("click", () => { sorts[id] = sort.key === k ? {key: k, dir: -sort.dir} : {key: k, dir: kind && kind !== "text" ? -1 : 1}; draw(); });
      return th;
    }))),
    el("tbody", {}, ...sorted.map(r => el("tr", {className: opts.rowClass?.(r) || ""}, ...cols.map(c => cell(r, c)))))));
}

function card(title, hint, ...body) {
  const {el} = H;
  return el("div", {className: "card"}, el("div", {className: "card-head"}, el("h3", {textContent: title}), hint ? el("span", {className: "hint", textContent: hint}) : ""), ...body);
}

function stat(label, value, c = "") {
  return H.el("div", {className: "stat"}, H.el("small", {textContent: label}), H.el("b", {className: c, textContent: value}));
}

function draw() {
  const {el, money, signed} = H;
  const head = H.view.querySelector("#arch-head"), body = H.view.querySelector("#arch-body");
  if (!archive) {
    head.replaceChildren(el("b", {textContent: "Stats archive"}));
    body.replaceChildren(el("p", {className: "empty", textContent: list.length ? "Pick an archive." : "No archives yet."}));
    return;
  }
  const a = archive, s = a.summary, games = a.games || {};
  const gameName = g => games[g] || g;
  head.replaceChildren(el("b", {textContent: a.title}), el("span", {className: "hint", textContent: `${day(a.period?.from)} – ${day(a.period?.to)} · taken ${when(a.created)}`}));
  const traitLabel = t => a.labels?.[t] || (t === "(none)" ? "(none)" : t.replace(/_/g, " ").replace(/^./, c => c.toUpperCase()));
  const pounds = v => money(Math.round(v / 100) * 100), plus = v => signed(Math.round(v / 100) * 100);   // (tiles: whole pounds)
  const vl = a.visit_length;

  const poolRows = Object.entries(s.pools || {}).filter(([, v]) => v).map(([k, v]) =>
    stat(k === "jackpot" ? "Jackpot pool" : "Slot " + k.replace("slots_", ""), pounds(v)));
  body.replaceChildren(
    card("Summary", "",
      el("div", {className: "stats"},
        stat("NPC staked", pounds(s.npc.wagered)), stat("NPC house net", plus(s.npc.house), cls(s.npc.house)), stat("NPC hold", pct(s.npc.hold), cls(s.npc.hold)),
        stat("NPC visits", n(s.npc.visits)), stat("NPC rounds", n(s.npc.rounds)), stat("NPC hours", n(s.npc.hours)),
        stat("Punters ahead", `${s.npc.in_profit} / ${s.npc.punters}`),
        stat("Human staked", pounds(s.human.wagered)), stat("Human house net", plus(s.human.house), cls(s.human.house)), stat("Human hold", pct(s.human.hold), cls(s.human.hold)),
        stat("Human bets", n(s.human.bets)), ...poolRows)),

    card("NPCs by game", `money from visits that played one game: ${pct(a.npc_games_coverage)} of NPC stake`,
      table("npc_games", [["Game", "name", "text"], ["Rounds", "rounds", "n"], ["1-game visits", "single_visits", "n"], ["Staked", "wagered", "money"],
        ["House net", "house", "signed"], ["Hold", "hold", "pct"], ["Per round", "per_round", "money"], ["Avg min", "avg_minutes", "n"], ["Avg rounds", "avg_rounds", "n"]],
        a.npc_games, {value: (r, k) => k === "name" ? gameName(r.game) : undefined})),

    card("Slots by machine", a.slots_since ? `counted since ${when(a.slots_since)}` : "",
      table("slots", [["Machine", "name", "text"], ["Who", "who", "text"], ["Spins", "spins", "n"], ["Staked", "wagered", "money"], ["Returned", "returned", "money"],
        ["House net", "house", "signed"], ["Hold", "hold", "pct"], ["Bonuses", "bonuses", "n"], ["Jackpots", "jackpots", "n"]], a.slots)),

    card("Humans by game", "from the ledger",
      table("human_games", [["Game", "name", "text"], ["Bets", "bets", "n"], ["Staked", "wagered", "money"], ["Returned", "returned", "money"],
        ["House net", "house", "signed"], ["Hold", "hold", "pct"]], a.human_games, {value: (r, k) => k === "name" ? gameName(r.game) : undefined})),

    card("Humans by player", "",
      table("human_players", [["Player", "name", "text"], ["Staked", "wagered", "money"], ["Returned", "returned", "money"], ["House net", "house", "signed"],
        ["Hold", "hold", "pct"], ["Games", "games", "n"]], a.human_players, {value: (r, k) => k === "games" ? r.games.length : undefined}),
      el("details", {}, el("summary", {className: "hint", textContent: "Biggest payouts"}),
        table("biggest", [["Player", "name", "text"], ["When", "at", "text"], ["Game", "game", "text"], ["Paid", "amount", "money"]], a.biggest_payouts,
          {show: (r, k) => k === "at" ? when(r.at) : k === "game" ? gameName(r.game) : r[k]}))),

    card("NPC archetypes", "",
      table("archetypes", [["Archetype", "key", "text"], ["Visits", "visits", "n"], ["Staked", "wagered", "money"], ["House net", "house", "signed"], ["Hold", "hold", "pct"],
        ["Bust %", "bust_pct", "n"], ["Avg budget", "avg_budget", "money"], ["Avg min", "avg_minutes", "n"], ["Avg rounds", "avg_rounds", "n"]], a.archetypes,
        {show: (r, k) => k === "key" ? traitLabel(r.key) : r[k]})),

    card("NPC traits", "visits by NPCs with each trait; an NPC with several counts under each",
      table("traits", [["Trait", "key", "text"], ["Visits", "visits", "n"], ["Staked", "wagered", "money"], ["House net", "house", "signed"], ["Hold", "hold", "pct"],
        ["Bust %", "bust_pct", "n"], ["Avg min", "avg_minutes", "n"]], a.traits, {show: (r, k) => k === "key" ? traitLabel(r.key) : r[k]})),

    card("How NPC visits ended", "",
      table("reasons", [["Reason", "key", "text"], ["Visits", "visits", "n"], ["Staked", "wagered", "money"], ["House net", "house", "signed"], ["Hold", "hold", "pct"],
        ["Avg min", "avg_minutes", "n"], ["Avg rounds", "avg_rounds", "n"]], a.reasons, {show: (r, k) => k === "key" ? traitLabel(r.key) : r[k]})),

    card("NPC visit length", "",
      el("div", {className: "stats"},
        stat("Avg min (all)", n(vl.all.avg_minutes)), stat("Avg rounds (all)", n(vl.all.avg_rounds)),
        stat("Avg min (played)", n(vl.played.avg_minutes)), stat("Avg rounds (played)", n(vl.played.avg_rounds)),
        stat("Median min (played)", n(vl.median_minutes)), stat("Median rounds", n(vl.median_rounds)),
        stat("Median budget", money(a.budgets.median ?? 0)), stat("Budget p90", money(a.budgets.p90 ?? 0)),
        ...Object.entries(a.games_per_visit).map(([k, v]) => stat(`${k} game${k === "1" ? "" : "s"}`, n(v) + " visits")))),

    card("Punters", `every punter's lifetime figures; the ${a.best_npcs.length} furthest ahead and behind are marked`,
      table("npcs", [["Name", "name", "text"], ["Archetype", "archetype", "text"], ["Traits", "traits", "text"], ["Visits", "visits", "n"], ["Rounds", "rounds", "n"],
        ["Staked", "wagered", "money"], ["Their net", "net", "signed"], ["Busts", "busts", "n"], ["Best visit", "biggest_win", "money"]], a.npcs,
        {sort: {key: "net", dir: -1},
         value: (r, k) => k === "traits" ? r.traits.map(traitLabel).join(", ") : k === "archetype" ? traitLabel(r.archetype) : undefined,
         rowClass: r => a.best_npcs.includes(r.id) || a.worst_npcs.includes(r.id) ? "sel" : r.archived ? "off" : ""})),

    card("NPCs by day", "",
      table("daily", [["Day", "day", "text"], ["Visits", "visits", "n"], ["Rounds", "rounds", "n"], ["Staked", "wagered", "money"], ["House net", "house", "signed"], ["Hold", "hold", "pct"]],
        a.daily, {sort: {key: "day", dir: 1}})),
  );
}
