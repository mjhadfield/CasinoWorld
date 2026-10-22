// Slots: the shared jackpot meters and their settings, each machine's figures (slots/stats.py), the cabinets on the
// floor right now, and what players have had back overall. The machines' art is designed on Slot design.
let H, timer = null;

export function init(h) {
  H = h;
  h.top.append(h.el("span", {className: "hint", id: "slots-since"}), h.el("span", {className: "grow"}),
    h.el("button", {type: "button", textContent: "Refresh", onclick: load}));
  h.view.innerHTML = `
  <div class="wb" style="grid-template-columns: minmax(0, 1fr) 420px">
    <div class="panel">
      <div class="ph">Jackpot meters <span class="grow"></span><span class="hint" id="slots-jrtp"></span></div>
      <div class="pb padded" style="flex: none; overflow: visible"><div id="slot-meters" style="display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--gap)"></div></div>
      <div class="ph" style="border-top: 1px solid var(--line)">Machines</div>
      <div class="pb" id="slot-machines"></div>
    </div>
    <div class="panel">
      <div class="ph">Return to players</div>
      <div class="pb padded" style="flex: none" id="slot-rtp"></div>
      <div class="ph" style="border-top: 1px solid var(--line)">Cabinets now <span class="grow"></span><span class="hint" id="slots-busy"></span></div>
      <div class="pb" id="slot-cabs"></div>
    </div>
  </div>`;
}

export function shown(on) {
  clearInterval(timer);
  if (on) timer = setInterval(() => { if (!document.hidden) load(true); }, 5000);
}

const pct = (r, w) => w ? (100 * r / w).toFixed(2) + "%" : "—";

export async function load(quiet) {
  const {el, money} = H, $ = s => H.view.querySelector(s) || H.top.querySelector(s);
  let o;
  try { o = await H.api("GET", "/api/slots"); } catch (e) { if (!quiet) H.status("Couldn't load slots: " + e.message, "warn"); return; }

  // the meters: redrawn only when not being edited, so polling never eats a half-typed number
  if (!H.view.querySelector("#slot-meters input:focus")) $("#slot-meters").replaceChildren(...o.tiers.map(t => meter(t)));
  $("#slots-jrtp").textContent = `the meters return ${o.jackpot_rtp.toFixed(2)}% of bets, plus growth a second`;

  // each machine
  const m = o.machines || [];
  const th = (t, c = "") => el("th", {className: c, textContent: t});
  $("#slot-machines").replaceChildren(m.length ? el("table", {},
    el("thead", {}, el("tr", {}, th("Machine"), th("Cabinets", "num"), th("Spins", "num"), th("Staked", "num"), th("Returned", "num"),
      th("Return", "num"), th("Bonuses", "num"), th("1 in", "num"), th("Jackpots", "num"), th("Humans · NPCs (spins)", "num"))),
    el("tbody", {}, ...m.map(x => el("tr", {},
      el("td", {}, el("b", {textContent: x.name})),
      el("td", {className: "num", textContent: x.cabinets || "—"}),
      el("td", {className: "num", textContent: x.spins.toLocaleString()}),
      el("td", {className: "num", textContent: money(x.staked)}),
      el("td", {className: "num", textContent: money(x.returned)}),
      el("td", {className: "num " + (x.staked && x.returned > x.staked ? "neg" : ""), textContent: pct(x.returned, x.staked)}),
      el("td", {className: "num", textContent: x.bonuses}),
      el("td", {className: "num", textContent: x.bonuses ? Math.round(x.spins / x.bonuses) : "—"}),
      el("td", {className: "num", textContent: x.jackpots}),
      el("td", {className: "num"}, el("span", {textContent: x.human.spins.toLocaleString()}), el("span", {className: "faint", textContent: " · " + x.npc.spins.toLocaleString()}))))))
    : el("p", {className: "empty", textContent: "No slot machines yet."}));
  $("#slots-since").textContent = o.stats_since ? "Machine figures since " + new Date(o.stats_since).toLocaleString([], {dateStyle: "medium", timeStyle: "short"}) : "Machine figures count from the first spin";

  // players overall (the ledger, humans only)
  const w = o.players.wagered, r = o.players.returned;
  $("#slot-rtp").replaceChildren(el("div", {className: "stats"},
      stat("Staked", money(w)), stat("Paid back", money(r)), stat("Return", pct(r, w))),
    el("p", {className: "hint", textContent: `Players' spins since the casino opened (the ledger). The game is tuned to about 91.5%, plus ${o.jackpot_rtp.toFixed(2)}% from the jackpots' share of bets; short runs swing a long way.`}));

  // the cabinets
  const busy = o.cabinets.filter(c => c.player).length;
  $("#slots-busy").textContent = `${busy} of ${o.cabinets.length} in use`;
  $("#slot-cabs").replaceChildren(el("table", {}, el("thead", {}, el("tr", {}, th("Cabinet"), th("Player"), th("Doing"), th("Bet", "num"))),
    el("tbody", {}, ...o.cabinets.map(c => el("tr", {className: c.player ? "" : "off"},
      el("td", {}, el("span", {textContent: c.name}), el("span", {className: "faint", textContent: " " + c.table})),
      el("td", {textContent: c.player ? c.player + (c.human ? "" : " (NPC)") : "—"}),
      el("td", {textContent: c.player ? c.phase + (c.pending.length ? " → " + c.pending.join(", ") : "") : ""}),
      el("td", {className: "num", textContent: c.player ? money(c.bet) : ""}))))));
  if (!quiet) H.status("Slots loaded.");
}

function stat(label, value) { return H.el("div", {className: "stat"}, H.el("small", {textContent: label}), H.el("b", {textContent: value})); }

function meter(t) {
  const {el, money} = H;
  const rate = el("input", {type: "number", min: 0, max: 5, step: 0.05, value: +(t.rate * 100).toFixed(3), style: "width: 100%"});
  const pps = el("input", {type: "number", min: 0, max: 10, step: 0.001, value: +(t.per_second / 100).toFixed(4), style: "width: 100%"});
  const hour = el("span", {className: "hint"});
  const showHour = () => { hour.textContent = +pps.value > 0 ? `${money(Math.round(+pps.value * 100 * 3600))} an hour` : "no growth"; };
  pps.addEventListener("input", showHour); showHour();
  const save = async () => {
    try {
      const r = await H.api("PUT", "/api/slots/jackpot-settings", {[t.id]: {rate: +rate.value / 100, per_second: Math.round(+pps.value * 100 * 1000) / 1000}});
      H.status(`${t.name} saved. The jackpots now return ${r.jackpot_rtp.toFixed(2)}% of bets, plus the growth a second.`, "ok"); load(true);
    } catch (e) { H.status(e.message, "warn"); }
  };
  const reset = el("button", {type: "button", className: "ghost", textContent: "Reset to seed"});
  reset.addEventListener("click", () => {
    const yes = el("button", {type: "button", className: "primary", textContent: "Reset"}), no = el("button", {type: "button", textContent: "Keep"});
    const box = el("span", {className: "confirm"}, yes, no);
    yes.addEventListener("click", async () => { await H.api("POST", `/api/slots/reset-meter/${t.id}`); H.status(`${t.name} reset to ${money(t.seed)}.`, "ok"); load(true); });
    no.addEventListener("click", () => box.replaceWith(reset));
    reset.replaceWith(box);
  });
  return el("div", {className: "card"},
    el("div", {className: "card-head"}, el("span", {className: "tag gold", textContent: t.name}), el("span", {className: "grow", style: "flex:1"}),
      el("span", {className: "hint", textContent: "seed " + money(t.seed)})),
    el("b", {className: "num", style: "font-size: var(--fs-big)", textContent: money(t.amount)}),
    el("div", {className: "grid2", style: "grid-template-columns: 1fr 1fr"},
      el("label", {className: "field"}, el("span", {textContent: "% of every bet"}), rate),
      el("label", {className: "field"}, el("span", {textContent: "Plus £ a second"}), pps)),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save", onclick: save}), reset, hour));
}
