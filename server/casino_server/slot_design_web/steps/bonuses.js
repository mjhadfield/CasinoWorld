// Step 6, Bonus games: a card per library bonus (the Trail bonus, the free games) with everything about it: on or off,
// how players get in (a scatter, Buy Bonus, or both; bonuses sharing a way in play one at random), its settings and
// its pictures. Then Buy Bonus's price and the shared Jackpot Pick. "Try it" plays the mockup straight into a bonus.
import {SHORT, STAND_IN, artSlot, parseTable, specs, tableText, typing} from "./artslot.js";

const SPACES = [["snake", "Hazards"], ["heart", "Hearts"], ["forward", "Forward"], ["back", "Back"], ["lightning", "Lightning rolls"], ["crate", "Coin crates"]];
const TRAIL_ART = ["armadillo", "cylinder", "t_coin", "t_gold", "t_snake", "t_heart", "t_forward", "t_lightning", "t_crate", "t_upgrade", "t_double"];
const SCATTERS = [["BS", "bonus scatter"], ["FS", "free-spins scatter"]];
let C, picked = null;          // the trail picture open for changing
const opened = new Set();      // <details> left open, kept across redraws

export function render(ctx, body) {
  C = ctx;
  const {el} = C, b = C.data.bonuses;
  body.append(
    el("p", {className: "lead", textContent: "The bonus games: switch each on or off, choose how players get in, and set how it plays and looks. Bonuses that share a way in take turns at random. What they're worth is measured on the Maths step."}),
    waysCard(),
    el("div", {className: "wz-cards"}, trailCard(b.trail), el("div", {className: "pane"}, freeCard(b.free), buyCard(b.buy), pickCard())),
    folded("ideas", "New bonus ideas", ideas()));
}

export function update(ctx) {
  C = ctx;
  const body = document.querySelector(".wz-body");
  if (body && !typing(body)) { body.replaceChildren(); render(ctx, body); }
}

// The ideas card's contents, folded away under its own heading.
function ideas() {
  const s = specs(C, "bonus");
  s.className = "pane";
  s.querySelector("h3").remove();
  return s;
}

// ------------------------------------------------------------------ helpers
const TITLE = {trail: "The trail bonus", free: "The free games"};
const field = (label, input) => C.el("label", {className: "field"}, C.el("span", {textContent: label}), input);
const num = (v, min, max, step = 1, label = "") => C.el("input", {type: "number", min, max, step, value: v, className: "wz-num", ariaLabel: label});
const txt = (v, label = "") => C.el("input", {value: v, ariaLabel: label});

async function save(body, msg) {
  try {
    await C.api("PATCH", `/api/slot-design/${C.did}/bonuses`, body);
    if (C.data.steps.find(s => s.id === "bonuses").status === "todo") await C.setStep("bonuses", "doing"); else await C.refresh();
    C.status(msg, "ok");
  } catch (e) { C.status(e.message, "warn"); }
}

// A scatter's symbol on the Value ladder (or Armadillo's picture of it, until one's placed).
function scatterSym(t) {
  const sid = C.data.ladder.slots[t] || C.data.ladder.scatters[t];
  return C.data.symbols.find(s => s.id === sid) || null;
}
const scatterName = t => scatterSym(t)?.name || (t === "BS" ? "Bonus" : "Free Spins");
const scatterImg = t => { const s = scatterSym(t); return s && s.file ? C.img(s.file) : STAND_IN(t); };

// What a way in plays, in words: one bonus, or several "at random".
function plays(kinds) {
  const b = C.data.bonuses, name = k => k === "trail" ? b.trail.name : `${b.free.games} ${b.free.name}`;
  return kinds.length ? kinds.map(name).join(" or ") + (kinds.length > 1 ? ", at random" : "") : null;
}

function folded(id, title, ...content) {
  const d = C.el("details", {className: "card", open: opened.has(id)}, C.el("summary", {}, C.el("b", {textContent: title})), ...content);
  d.addEventListener("toggle", () => { if (d.open) opened.add(id); else opened.delete(id); });
  return d;
}

// ------------------------------------------------------------------ how players get in
function waysCard() {
  const {el} = C, b = C.data.bonuses, r = b.routes;
  const row = (icon, way, what, off) => el("div", {className: "wz-way" + (off ? " off" : "")},
    icon ? el("img", {src: icon, alt: ""}) : el("span", {className: "wz-way-icon", textContent: "£"}),
    el("b", {textContent: way}), el("span", {textContent: "→"}), el("span", {textContent: what}));
  return el("div", {className: "card"}, el("div", {className: "card-head"}, el("h3", {textContent: "How players get in"})),
    el("div", {className: "wz-ways"},
      ...SCATTERS.map(([t]) => row(scatterImg(t), `3+ ${scatterName(t)}`, plays(r[t]) || "nothing: it's off the reels and the Value ladder", !r[t].length)),
      row(null, `Buy Bonus (${b.buy.cost}× the bet)`, !b.buy.enabled ? "off" : plays(r.buy) || "nothing yet: tick “Buy Bonus can give it” on a bonus", !r.buy.length)));
}

// A bonus's head (its switch and Try it) and its ways in (the scatter that starts it; whether Buy Bonus can give it).
function bonusHead(kind, x, title, sub) {
  const {el} = C;
  const on = el("input", {type: "checkbox", checked: x.enabled, ariaLabel: `${TITLE[kind]}: on`,
    onchange: () => save({[kind]: {enabled: on.checked}}, `${TITLE[kind]} ${on.checked ? "on" : "off"}.`)});
  const tryIt = el("button", {type: "button", textContent: "▶ Try it", disabled: !x.enabled,
    title: x.scatter ? "Play the mockup with its scatters landing" : "Play the mockup straight into it",
    onclick: () => C.play(x.scatter ? {rig: {trigger: kind}} : {bonus: kind})});
  return el("div", {className: "card-head"}, el("h3", {textContent: title}), el("span", {className: "hint", textContent: sub}),
    el("label", {className: "confirm", style: "margin-left:auto"}, on, "On"), tryIt);
}

function waysIn(kind, x) {
  const {el} = C, b = C.data.bonuses;
  const sel = el("select", {ariaLabel: `${TITLE[kind]}: started by`, disabled: !x.enabled},
    ...SCATTERS.map(([t, what]) => el("option", {value: t, textContent: `3+ ${scatterName(t)} (the ${what})`})),
    el("option", {value: "", textContent: "No scatter: Buy Bonus only"}));
  sel.value = x.scatter || "";
  sel.addEventListener("change", () => save({[kind]: {scatter: sel.value || null}}, `${TITLE[kind]}: way in saved.`));
  const buy = el("input", {type: "checkbox", checked: x.buyable, disabled: !x.enabled,
    onchange: () => save({[kind]: {buyable: buy.checked}}, `${TITLE[kind]}: Buy Bonus ${buy.checked ? "can" : "can't"} give it now.`)});
  const other = kind === "trail" ? "free" : "trail";
  const shared = x.enabled && x.scatter && b[other].enabled && b[other].scatter === x.scatter;
  return el("div", {className: "wz-in"},
    el("label", {className: "field"}, el("span", {textContent: "Started by"}), sel),
    el("label", {className: "confirm"}, buy, "Buy Bonus can give it"),
    shared ? el("span", {className: "tag gold", textContent: `shares ${scatterName(x.scatter)} with ${TITLE[other].toLowerCase()}: one at random`}) : null);
}

const offNote = what => C.el("p", {className: "hint", textContent: `Off: nothing plays ${what}, and its pictures aren't needed. Its settings are kept.`});

// ------------------------------------------------------------------ the Trail bonus
function trailCard(t) {
  const {el} = C, card = el("div", {className: "card" + (t.enabled ? "" : " wz-off")},
    bonusHead("trail", t, "Trail bonus", "the mascot walks a trail of prizes"), waysIn("trail", t));
  if (!t.enabled) { card.append(offNote("it")); return card; }
  const T = {name: txt(t.name, "Its name"), launcher: txt(t.launcher, "The launcher's name"), hint: txt(t.hint, "Hint on its banner"),
    length: num(t.length, 40, 200, 1, "Trail length"), prizepot: num(t.prizepot, 100, 10000, 50, "Prizepot"),
    upgrade: num(+(t.upgrade_chance * 100).toFixed(1), 0, 100, 0.5, "Spin Upgrade chance"), double: num(+(t.double_chance * 100).toFixed(1), 0, 100, 0.5, "Coins Doubled chance"),
    coins: txt(tableText(t.coins), "Coin values"), crate: txt(tableText(t.crate_radius), "Crate reach"),
    counts: Object.fromEntries(SPACES.map(([k, label]) => [k, num(t.counts[k] ?? 0, 0, 40, 1, label)]))};
  card.append(
    el("p", {className: "hint", textContent: "Each shot moves the mascot 1 to 6 spaces along a trail of coin prizes to the prizepot. Hazards cost a heart or end it."}),
    pictures(TRAIL_ART),
    el("div", {className: "grid2"}, field("Its name", T.name), field("The launcher's name", T.launcher), field("Hint on its banner", T.hint),
      field("Trail length (spaces)", T.length), field("Prizepot (× bet)", T.prizepot)),
    folded("board", "The board: special spaces and coin values",
      el("div", {className: "grid2"}, ...SPACES.map(([k, label]) => field(label, T.counts[k])),
        field("Spin Upgrade chance, %", T.upgrade), field("Coins Doubled chance, %", T.double)),
      el("div", {className: "grid2"}, field("Coin values (× bet, value:weight)", T.coins), field("Crate reach (spaces, value:weight)", T.crate))),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save the trail", onclick: () => save({trail: {
      name: T.name.value, launcher: T.launcher.value, hint: T.hint.value, length: +T.length.value, prizepot: +T.prizepot.value,
      upgrade_chance: +T.upgrade.value / 100, double_chance: +T.double.value / 100, coins: parseTable(T.coins.value),
      crate_radius: parseTable(T.crate.value), counts: Object.fromEntries(SPACES.map(([k]) => [k, +T.counts[k].value]))}}, "Trail saved.")})));
  return card;
}

// A bonus's pictures as a strip of tiles; the one picked opens below to be changed.
function pictures(keys) {
  const {el} = C, art = C.data.art;
  if (!keys.includes(picked)) picked = null;
  const tiles = keys.map(k => el("button", {type: "button", className: "wz-pic", ariaPressed: String(k === picked), title: art[k].label,
    onclick: () => { picked = picked === k ? null : k; update(C); }},
    el("img", {src: art[k].file ? C.img(art[k].file) : STAND_IN(k), alt: "", className: art[k].file ? "" : "standin"}),
    el("span", {textContent: (SHORT[k] || k).replace(/^Trail /, "")})));
  const own = keys.filter(k => art[k].file).length;
  return el("div", {className: "pane"},
    el("div", {className: "controls"}, el("b", {textContent: "Pictures"}),
      el("span", {className: "hint", textContent: own === keys.length ? "all its own" : `${keys.length - own} of ${keys.length} still Armadillo's (faded): pick one to change it`})),
    el("div", {className: "wz-pics"}, ...tiles),
    picked ? artSlot(C, picked) : null);
}

// ------------------------------------------------------------------ the free games
function freeCard(f) {
  const {el} = C, card = el("div", {className: "card" + (f.enabled ? "" : " wz-off")},
    bonusHead("free", f, "Free games", "spins with guaranteed features"), waysIn("free", f));
  if (!f.enabled) { card.append(offNote("them")); return card; }
  const name = txt(f.name, "Their name"), games = num(f.games, 1, 20, 1, "How many");
  card.append(
    el("p", {className: "hint", textContent: "Paid at the triggering bet, with at least one random feature on every game (their free-game chances are on the Features step). They play on the reels, so they need no pictures of their own."}),
    el("div", {className: "grid2"}, field("Their name", name), field("How many", games)),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save", onclick: () => save({free: {name: name.value, games: +games.value}}, "Free games saved.")})));
  return card;
}

// ------------------------------------------------------------------ Buy Bonus and the Jackpot Pick
function buyCard(by) {
  const {el} = C, r = C.data.bonuses.routes;
  const on = el("input", {type: "checkbox", checked: by.enabled, onchange: () => save({buy: {enabled: on.checked}}, `Buy Bonus ${on.checked ? "offered" : "off"}.`)});
  const cost = num(by.cost, 10, 500, 1, "Cost (× bet)");
  return el("div", {className: "card" + (by.enabled ? "" : " wz-off")},
    el("div", {className: "card-head"}, el("h3", {textContent: "Buy Bonus"}), el("label", {className: "confirm", style: "margin-left:auto"}, on, "Offer it")),
    el("p", {className: "hint", textContent: by.enabled ? (plays(r.buy) ? `Pay a multiple of the bet for ${plays(r.buy)}.` : "Nothing to buy yet: tick “Buy Bonus can give it” on a bonus.") : "Off: players get in by scatters only."}),
    by.enabled ? el("div", {className: "controls"}, field("Cost (× bet)", cost),
      el("button", {type: "button", className: "primary", textContent: "Save", onclick: () => save({buy: {cost: +cost.value}}, "Buy Bonus saved.")})) : null);
}

function pickCard() {
  const {el} = C;
  return el("div", {className: "card"}, el("div", {className: "card-head"}, el("h3", {textContent: "Jackpot Pick"}),
      el("span", {className: "tag", textContent: "always on"}),
      el("button", {type: "button", textContent: "▶ Try it", style: "margin-left:auto", onclick: () => C.play({rig: {jackpot: "mini"}})})),
    el("p", {className: "hint", textContent: "Shared by every slot on the floor: a random trigger on any spin (likelier on bigger bets) opens a board of coins; three alike win that meter (Mini, Minor, Major or Grand)."}));
}
