// Step 6, Bonus games: one column, a row per bonus (the Trail bonus, the free games, the wave battle, the island
// voyage, the expedition, then Buy Bonus
// and the shared Jackpot Pick). A row shows its switch, how players get in and Try it; its settings open under it,
// on or off (an off bonus keeps them for when it's switched back on): its ways in, its pictures (each with an Adjust
// panel: size, position, rotation, mirror, colour) and how it plays. "Try it" plays the mockup straight into a bonus.
import {STAND_IN, SHORT, artSlot, parseTable, specs, tableText, typing} from "./artslot.js";

const SPACES = [["snake", "Hazards"], ["heart", "Hearts"], ["forward", "Forward"], ["back", "Back"], ["lightning", "Lightning rolls"], ["crate", "Coin crates"]];
const TRAIL_ART = ["armadillo", "cylinder", "t_coin", "t_gold", "t_snake", "t_heart", "t_forward", "t_lightning", "t_crate", "t_upgrade", "t_double"];
const BATTLE_ART = ["b_hero", "b_enemy", "b_boss"];
const VOYAGE_ART = ["v_ship", "v_treasure", "v_wreck", "v_skull", "v_port", "v_cove", "v_final", "v_chest", "v_relic", "v_key",
  "v_art1", "v_art2", "v_art3", "v_art4"];
const EXPEDITION_ART = ["x_ship", "x_planet", "x_credits", "x_mult", "x_scanner", "x_shuttle", "x_shields", "x_artefact", "x_wormhole",
  "x_spins", "x_hazard", "x_final"];
const PLANETS = [["credits", "Credits"], ["mult", "A multiplier"], ["tech", "Tech"], ["special", "A special"]];
const TECHS = [["scanner", "Scanner"], ["shuttle", "Shuttle"], ["shields", "Shields"]];
const SPECIALS = [["artefact", "Artefact"], ["wormhole", "Wormhole"], ["spins", "Free games"]];
const ISLANDS = [["treasure", "Treasure Island"], ["wreck", "Shipwreck"], ["skull", "Skull Island"], ["port", "Port Royal"]];
const SCATTERS = [["BS", "bonus scatter"], ["FS", "free-spins scatter"]];
let C, picked = null;          // the picture open for changing
const opened = new Set();      // rows and <details> left open, kept across redraws

export function render(ctx, body) {
  C = ctx;
  const {el} = C, b = C.data.bonuses;
  body.append(
    el("p", {className: "lead", textContent: "The bonus games: switch each on or off, and open one (▸) for how players get in, its pictures and how it plays. Its settings can be changed whether it's on or off. Bonuses that share a way in take turns at random; what they're worth is measured on the Maths step."}),
    el("div", {className: "wz-bonuses"},
      waysCard(), trailRow(b.trail), freeRow(b.free), battleRow(b.battle), voyageRow(b.voyage), expeditionRow(b.expedition), buyRow(b.buy), pickRow(),
      folded("ideas", "New bonus ideas", ideas())));
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
const TITLE = {trail: "The trail bonus", free: "The free games", battle: "The battle bonus", voyage: "The voyage bonus",
  expedition: "The expedition bonus"};
const field = (label, input) => C.el("label", {className: "field"}, C.el("span", {textContent: label}), input);
const num = (v, min, max, step = 1, label = "") => C.el("input", {type: "number", min, max, step, value: v, className: "wz-num", ariaLabel: label});
const txt = (v, label = "") => C.el("input", {value: v, ariaLabel: label});
const tag = (text, kind = "") => C.el("span", {className: "tag" + (kind ? " " + kind : ""), textContent: text});
const section = (title, ...kids) => C.el("div", {className: "wz-sec"}, C.el("h4", {textContent: title}), ...kids);
const saveRow = (text, onclick) => C.el("div", {className: "controls"}, C.el("button", {type: "button", className: "primary", textContent: text, onclick}));

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
  const b = C.data.bonuses, name = k => k === "free" ? `${b.free.games} ${b.free.name}` : b[k].name;
  return kinds.length ? kinds.map(name).join(" or ") + (kinds.length > 1 ? ", at random" : "") : null;
}

function folded(id, title, ...content) {
  const d = C.el("details", {className: id === "ideas" ? "card" : "wz-fold", open: opened.has(id)}, C.el("summary", {}, C.el("b", {textContent: title})), ...content);
  d.addEventListener("toggle", () => { if (d.open) opened.add(id); else opened.delete(id); });
  return d;
}

// A row: its head (▸ and the title, tags saying how it stands, its switch and Try it) and, opened, its settings.
// `content` builds them when the row opens (null: nothing to open).
function row(id, {title, sub, tags = [], toggle = null, tryIt = null, off = false}, content) {
  const {el} = C;
  const card = el("section", {className: "card wz-bonus" + (off ? " wz-off" : "")});
  let body = null;
  const caret = el("button", {type: "button", className: "wz-bonus-toggle", disabled: !content, ariaExpanded: "false",
    title: content ? "Show or hide its settings" : "", onclick: () => { if (!opened.delete(id)) opened.add(id); show(); }},
    el("span", {className: "caret", textContent: "▸"}), el("span", {className: "t", textContent: title}), el("span", {className: "hint", textContent: sub}));
  const show = () => {
    const on = opened.has(id);
    caret.ariaExpanded = String(on);
    if (on && !body) card.append(body = el("div", {className: "wz-bonus-body"}, ...content().filter(Boolean)));
    if (!on && body) { body.remove(); body = null; }
  };
  card.append(el("div", {className: "wz-bonus-head"}, caret, el("span", {className: "wz-bonus-tags"}, ...tags.filter(Boolean)), toggle, tryIt));
  if (content) show();
  return card;
}

// ------------------------------------------------------------------ how players get in
function waysCard() {
  const {el} = C, b = C.data.bonuses, r = b.routes;
  const way = (icon, name, what, off) => el("div", {className: "wz-way" + (off ? " off" : "")},
    icon ? el("img", {src: icon, alt: ""}) : el("span", {className: "wz-way-icon", textContent: "£"}),
    el("b", {textContent: name}), el("span", {textContent: "→"}), el("span", {textContent: what}));
  return el("div", {className: "card"}, el("div", {className: "card-head"}, el("h3", {textContent: "How players get in"})),
    el("div", {className: "wz-ways"},
      ...SCATTERS.map(([t]) => way(scatterImg(t), `3+ ${scatterName(t)}`, plays(r[t]) || "nothing: it's off the reels and the Value ladder", !r[t].length)),
      way(null, `Buy Bonus (${b.buy.cost}× the bet)`, !b.buy.enabled ? "off" : plays(r.buy) || "nothing yet: tick “Buy Bonus can give it” on a bonus", !r.buy.length)));
}

// The bonuses sharing this one's scatter (one of them plays, at random).
const shares = (kind, x) => Object.keys(TITLE).filter(k => k !== kind && x.enabled && x.scatter && C.data.bonuses[k].enabled && C.data.bonuses[k].scatter === x.scatter);

// A bonus's row: its switch, Try it, and tags for its ways in and its pictures.
function bonusRow(kind, x, title, sub, art, content) {
  const {el} = C, b = C.data.bonuses;
  const on = el("input", {type: "checkbox", checked: x.enabled, ariaLabel: `${TITLE[kind]}: on`,
    onchange: () => save({[kind]: {enabled: on.checked}}, `${TITLE[kind]} ${on.checked ? "on" : "off"}.`)});
  const tryIt = el("button", {type: "button", textContent: "▶ Try it", disabled: !x.enabled,
    title: x.scatter ? "Play the mockup with its scatters landing" : "Play the mockup straight into it",
    onclick: () => C.play(x.scatter ? {rig: {trigger: kind}} : {bonus: kind})});
  const stand = art.filter(k => !C.data.art[k].file).length;
  const tags = !x.enabled ? [tag("off")] : [x.scatter ? tag(`3+ ${scatterName(x.scatter)}`) : null,
    x.buyable && b.buy.enabled ? tag("Buy Bonus") : null, shares(kind, x).length ? tag("shared: at random", "gold") : null,
    art.length ? tag(stand ? `${stand} of ${art.length} pictures stand-ins` : "pictures done", stand ? "" : "ok") : null];
  return row(kind, {title, sub, tags, off: !x.enabled, tryIt, toggle: el("label", {className: "confirm"}, on, "On")},
    () => [x.enabled ? null : offNote(kind === "free" ? "them" : "it"), ...content()]);
}

function waysIn(kind, x) {
  const {el} = C;
  const sel = el("select", {ariaLabel: `${TITLE[kind]}: started by`},
    ...SCATTERS.map(([t, what]) => el("option", {value: t, textContent: `3+ ${scatterName(t)} (the ${what})`})),
    el("option", {value: "", textContent: "No scatter: Buy Bonus only"}));
  sel.value = x.scatter || "";
  sel.addEventListener("change", () => save({[kind]: {scatter: sel.value || null}}, `${TITLE[kind]}: way in saved.`));
  const buy = el("input", {type: "checkbox", checked: x.buyable,
    onchange: () => save({[kind]: {buyable: buy.checked}}, `${TITLE[kind]}: Buy Bonus ${buy.checked ? "can" : "can't"} give it now.`)});
  const others = shares(kind, x);
  return section("Ways in", el("div", {className: "wz-in"},
    el("label", {className: "field"}, el("span", {textContent: "Started by"}), sel),
    el("label", {className: "confirm"}, buy, "Buy Bonus can give it"),
    others.length ? tag(`shares ${scatterName(x.scatter)} with ${others.map(k => TITLE[k].toLowerCase()).join(" and ")}: one at random`, "gold") : null));
}

const offNote = what => C.el("p", {className: "wz-offnote", textContent: `Off: nothing plays ${what}, and its pictures aren't needed. Its settings and pictures can still be changed; they're kept for when it's switched on.`});

// A bonus's pictures as a strip of tiles; the one picked opens below with its Adjust panel.
function pictures(keys) {
  const {el} = C, art = C.data.art;
  const open = keys.includes(picked) ? picked : null;   // (each bonus has its own strip)
  const tiles = keys.map(k => el("button", {type: "button", className: "wz-pic" + (art[k].file && art[k].file !== art[k].src ? " adj" : ""),
    ariaPressed: String(k === picked), title: art[k].label,
    onclick: () => { picked = picked === k ? null : k; update(C); }},
    el("img", {src: art[k].file ? C.img(art[k].file) : STAND_IN(k), alt: "", className: art[k].file ? "" : "standin"}),
    el("span", {textContent: (SHORT[k] || k).replace(/^(Trail |Battle: |Voyage: )/, "")})));
  const own = keys.filter(k => art[k].file).length;
  return section("Pictures",
    el("p", {className: "hint", textContent: (own === keys.length ? "All its own. " : `${keys.length - own} of ${keys.length} still Armadillo's stand-ins (faded). `)
      + "Pick one to change it, or to size, move, rotate, mirror or recolour it."}),
    el("div", {className: "wz-pics"}, ...tiles),
    open ? artSlot(C, open, {open: true}) : null);
}

// ------------------------------------------------------------------ the Trail bonus
function trailRow(t) {
  return bonusRow("trail", t, "Trail bonus", "the mascot walks a trail of prizes", TRAIL_ART, () => {
    const {el} = C;
    const T = {name: txt(t.name, "Its name"), launcher: txt(t.launcher, "The launcher's name"), hint: txt(t.hint, "Hint on its banner"),
      length: num(t.length, 40, 200, 1, "Trail length"), prizepot: num(t.prizepot, 100, 10000, 50, "Prizepot"),
      upgrade: num(+(t.upgrade_chance * 100).toFixed(1), 0, 100, 0.5, "Spin Upgrade chance"), double: num(+(t.double_chance * 100).toFixed(1), 0, 100, 0.5, "Coins Doubled chance"),
      coins: txt(tableText(t.coins), "Coin values"), crate: txt(tableText(t.crate_radius), "Crate reach"),
      counts: Object.fromEntries(SPACES.map(([k, label]) => [k, num(t.counts[k] ?? 0, 0, 40, 1, label)]))};
    return [
      el("p", {className: "hint", textContent: "Each shot moves the mascot 1 to 6 spaces along a trail of coin prizes to the prizepot. Hazards cost a heart or end it."}),
      waysIn("trail", t),
      pictures(TRAIL_ART),
      section("How it plays",
        el("div", {className: "grid2"}, field("Its name", T.name), field("The launcher's name", T.launcher), field("Hint on its banner", T.hint),
          field("Trail length (spaces)", T.length), field("Prizepot (× bet)", T.prizepot)),
        folded("board", "The board: special spaces and coin values",
          el("div", {className: "grid2"}, ...SPACES.map(([k, label]) => field(label, T.counts[k])),
            field("Spin Upgrade chance, %", T.upgrade), field("Coins Doubled chance, %", T.double)),
          el("div", {className: "grid2"}, field("Coin values (× bet, value:weight)", T.coins), field("Crate reach (spaces, value:weight)", T.crate))),
        saveRow("Save the trail", () => save({trail: {
          name: T.name.value, launcher: T.launcher.value, hint: T.hint.value, length: +T.length.value, prizepot: +T.prizepot.value,
          upgrade_chance: +T.upgrade.value / 100, double_chance: +T.double.value / 100, coins: parseTable(T.coins.value),
          crate_radius: parseTable(T.crate.value), counts: Object.fromEntries(SPACES.map(([k]) => [k, +T.counts[k].value]))}}, "Trail saved.")))];
  });
}

// ------------------------------------------------------------------ the free games
function freeRow(f) {
  return bonusRow("free", f, "Free games", "spins with guaranteed features", [], () => {
    const {el} = C, name = txt(f.name, "Their name"), games = num(f.games, 1, 20, 1, "How many");
    return [
      el("p", {className: "hint", textContent: "Paid at the triggering bet, with at least one random feature on every game (their free-game chances are on the Features step). They play on the reels, so they need no pictures of their own."}),
      waysIn("free", f),
      section("How it plays", el("div", {className: "grid2"}, field("Their name", name), field("How many", games)),
        saveRow("Save the free games", () => save({free: {name: name.value, games: +games.value}}, "Free games saved.")))];
  });
}

// ------------------------------------------------------------------ the wave battle (Red Alert)
const list = v => v.join(", ");
const parseList = text => text.split(/[,;\s]+/).filter(Boolean).map(Number);
const pcts = v => v.map(x => +(x * 100).toFixed(1)).join(", ");

function battleRow(x) {
  return bonusRow("battle", x, "Battle bonus", "your ship against waves of enemy ships, then a boss", BATTLE_ART, () => {
    const {el} = C;
    const T = {name: txt(x.name, "Its name"), hint: txt(x.hint, "Hint on its banner"), enemy: txt(x.enemy, "What the enemy ships are called"),
      boss_name: txt(x.boss_name, "What the boss is called"),
      waves: txt(list(x.waves), "Ships in each wave"), shields: num(x.shields, 1, 9, 1, "Shields"),
      fire: txt(pcts(x.return_fire), "Return fire chance by wave"), clear: txt(list(x.clear), "Wave rewards"),
      prizes: txt(tableText(x.prizes), "Ship prizes"), spinsChance: num(+(x.spins_chance * 100).toFixed(2), 0, 100, 0.1, "Free spins chance"),
      spins: txt(tableText(x.spins), "Free spins"), bossHits: num(x.boss_hits, 1, 20, 1, "Boss hits"),
      bossFire: num(+(x.boss_fire * 100).toFixed(1), 0, 90, 0.5, "Boss return fire"), boss: txt(tableText(x.boss), "Boss prizes")};
    return [
      el("p", {className: "hint", textContent: `Tap an enemy ship to fire. A hit destroys it for a prize (or free spins, played as ${C.data.bonuses.free.name.toLowerCase()} after the battle); a miss lets it cloak and fire back, costing a shield. Lose every shield and the battle ends; clear a wave for its reward and fresh shields. After ${x.waves.length} waves the boss arrives.`}),
      waysIn("battle", x),
      pictures(BATTLE_ART),
      section("How it plays",
        el("div", {className: "grid2"}, field("Its name", T.name), field("Hint on its banner", T.hint),
          field("The enemy ships are called", T.enemy), field("The boss is called", T.boss_name)),
        folded("waves", "The waves: ships, shields, return fire and rewards",
          el("div", {className: "grid2"}, field("Ships in each wave", T.waves), field("Shields (hits a wave)", T.shields),
            field("Return fire by wave, %", T.fire), field("Wave rewards (× bet)", T.clear),
            field("Ship prizes (× bet, value:weight)", T.prizes), field("Free spins chance a ship, %", T.spinsChance),
            field("Free spins (games, value:weight)", T.spins))),
        folded("boss", "The boss",
          el("div", {className: "grid2"}, field("Hits to destroy it", T.bossHits), field("Its return fire, %", T.bossFire),
            field("Its prize (× bet, value:weight)", T.boss))),
        saveRow("Save the battle", () => save({battle: {
          name: T.name.value, hint: T.hint.value, enemy: T.enemy.value, boss_name: T.boss_name.value,
          waves: parseList(T.waves.value), shields: +T.shields.value, return_fire: parseList(T.fire.value).map(v => v / 100),
          clear: parseList(T.clear.value), prizes: parseTable(T.prizes.value), spins_chance: +T.spinsChance.value / 100,
          spins: parseTable(T.spins.value), boss_hits: +T.bossHits.value, boss_fire: +T.bossFire.value / 100, boss: parseTable(T.boss.value)}}, "Battle saved.")))];
  });
}

// ------------------------------------------------------------------ the island voyage (Dead Man's Map)
function voyageRow(x) {
  return bonusRow("voyage", x, "Voyage bonus", "sail a map of islands to a legendary treasure", VOYAGE_ART, () => {
    const {el} = C, words = ["name", "hint", "start", "final", "treasure_name", "wreck_name", "skull_name", "port_name", "cove_name",
      "relic", "chest_name", "legend_name"];
    const W = Object.fromEntries(words.map(k => [k, txt(x[k], k)]));
    const A = x.artefacts.map((a, i) => txt(a, `Artefact ${i + 1}`));
    const T = {legs: num(x.legs, 2, 8, 1, "Legs"), coves: num(x.coves, 0, 7, 1, "Hidden Coves"),
      kinds: ISLANDS.map(([k, label]) => num(x.kinds.find(r => r[0] === k)?.[1] ?? 0, 0, 1000, 1, label)),
      treasure: txt(tableText(x.treasure), "Treasure Island prizes"), relics: txt(tableText(x.relics), "Shipwreck relics"),
      item: num(+(x.item_chance * 100).toFixed(1), 0, 100, 1, "Item chance"), key: num(+(x.key_chance * 100).toFixed(1), 0, 100, 1, "Key chance"),
      skull: txt(tableText(x.skull), "Skull Island prizes"), sink: num(+(x.sink * 100).toFixed(1), 0, 90, 1, "Sinking chance"),
      cove: txt(tableText(x.cove), "Hidden Cove prizes"), relicValue: num(x.relic_value, 0, 10000, 0.5, "Relic value"),
      artefactPrice: num(x.artefact_price, 1, 20, 1, "Artefact price"), keyPrice: num(x.key_price, 1, 20, 1, "Key price"),
      spinsPrice: num(x.spins_price, 1, 20, 1, "Free games price"), spinsGames: num(x.spins_games, 1, 20, 1, "Free games bought"),
      chest: num(x.chest, 0, 10000, 1, "Chest"), parts: txt(list(x.parts), "Parts"), legend: num(x.legend, 0, 10000, 1, "Legend")};
    const free = C.data.bonuses.free.name.toLowerCase();
    return [
      el("p", {className: "hint", textContent: `A map of ${x.legs} legs of three islands, all in view, from ${x.start} to ${x.final}. Players choose each next island (level or either side). Treasure Island pays; a Shipwreck gives relics and maybe a key or an artefact; Skull Island pays big or sinks the ship (the voyage ends short of the final island); Port Royal trades relics for an artefact, a key, ${free} (played after) or cash; a Hidden Cove needs a key. The final island pays the chest, a part for each artefact held, and the legend for all four. It's tuned so careful, bold and collecting routes pay about the same on average.`}),
      waysIn("voyage", x),
      pictures(VOYAGE_ART),
      section("How it plays",
        el("div", {className: "grid2"}, field("Its name", W.name), field("Hint on its banner", W.hint),
          field("The start port", W.start), field("The final island", W.final)),
        folded("v_words", "Names: the islands, the relics, the treasure and the artefacts",
          el("div", {className: "grid2"}, ...ISLANDS.map(([k, label]) => field(label, W[`${k}_name`])), field("Hidden Cove", W.cove_name),
            field("A relic", W.relic), field("The treasure", W.chest_name), field("All four artefacts", W.legend_name),
            ...A.map((input, i) => field(`Artefact ${i + 1}`, input)))),
        folded("v_map", "The map and its islands",
          el("div", {className: "grid2"}, field("Legs", T.legs), field("Hidden Coves (one a leg)", T.coves),
            ...ISLANDS.map(([, label], i) => field(`${label}: how often (weight)`, T.kinds[i])),
            field("Treasure Island (× bet, value:weight)", T.treasure), field("Skull Island (× bet, value:weight)", T.skull),
            field("Skull Island sinks the ship, %", T.sink), field("Hidden Cove (× bet, value:weight)", T.cove),
            field("Shipwreck relics (value:weight)", T.relics), field("A Shipwreck holds an item, %", T.item),
            field("...of those, a key (else an artefact), %", T.key))),
        folded("v_port", "Port Royal and the treasure",
          el("div", {className: "grid2"}, field("A relic sells for (× bet)", T.relicValue), field("An artefact costs (relics)", T.artefactPrice),
            field("A key costs (relics)", T.keyPrice), field(`${C.data.bonuses.free.name} cost (relics)`, T.spinsPrice),
            field("...and that buys (games)", T.spinsGames), field("The chest (× bet, always)", T.chest),
            field("Each artefact's part (× bet, four)", T.parts), field("All four: the legend (× bet)", T.legend))),
        saveRow("Save the voyage", () => save({voyage: {
          ...Object.fromEntries(words.map(k => [k, W[k].value])), artefacts: A.map(a => a.value),
          legs: +T.legs.value, coves: +T.coves.value, kinds: ISLANDS.map(([k], i) => [k, +T.kinds[i].value]),
          treasure: parseTable(T.treasure.value), relics: parseTable(T.relics.value), item_chance: +T.item.value / 100,
          key_chance: +T.key.value / 100, skull: parseTable(T.skull.value), sink: +T.sink.value / 100, cove: parseTable(T.cove.value),
          relic_value: +T.relicValue.value, artefact_price: +T.artefactPrice.value, key_price: +T.keyPrice.value,
          spins_price: +T.spinsPrice.value, spins_games: +T.spinsGames.value, chest: +T.chest.value, parts: parseList(T.parts.value),
          legend: +T.legend.value}}, "Voyage saved.")))];
  });
}

// ------------------------------------------------------------------ the expedition (Delta Quadrant)
function expeditionRow(x) {
  return bonusRow("expedition", x, "Expedition bonus", "chart a route and explore a planet in each sector", EXPEDITION_ART, () => {
    const {el} = C, words = ["name", "hint", "planet_hint", "start", "final", "sector", "credits_name", "mult_name", "scanner_name",
      "shuttle_name", "shields_name", "artefact_name", "wormhole_name", "spins_name"];
    const W = Object.fromEntries(words.map(k => [k, txt(x[k], k)]));
    const L = x.level_names.map((n, i) => txt(n, `Hazard level ${i + 1}`));
    const weights = (rows, names) => names.map(([k, label]) => num(rows.find(r => r[0] === k)?.[1] ?? 0, 0, 1000, 1, label));
    const T = {hazards: txt(x.hazards.join(", "), "Hazards"), lengths: txt(tableText(x.lengths), "Route lengths"),
      levels: x.levels.map((lv, i) => ({weight: num(lv.weight, 0, 1000, 1, `Level ${i + 1} weight`), hazard: num(lv.hazard, 0, 200, 0.5, `Level ${i + 1} hazards`),
        scale: num(lv.scale, 0.1, 20, 0.1, `Level ${i + 1} prize scale`), final: num(lv.final, 0, 10000, 1, `Level ${i + 1} final prize`)})),
      ramp: num(x.ramp, 0, 50, 0.5, "Hazard ramp"), kinds: weights(x.kinds, PLANETS), techs: weights(x.techs, TECHS),
      specials: weights(x.specials, SPECIALS), credits: txt(tableText(x.credits), "Credits"), mults: txt(tableText(x.mults), "Multipliers"),
      artefact: txt(tableText(x.artefact), "The artefact"), spins: txt(tableText(x.spins), "Free games"),
      wormhole: num(x.wormhole, 1, 20, 0.5, "Wormhole boost")};
    const free = C.data.bonuses.free.name.toLowerCase();
    return [
      el("p", {className: "hint", textContent: `Three routes from ${x.start} to ${x.final}, each a length and a hazard level drawn fresh and shown up front with its final prize. Players choose one, then one of three hidden planets in each sector: credits, a multiplier (on every later prize and the final one), tech (a Scanner shows the next sector, a Shuttle explores a second planet there, Shields absorb a hazard), a special (an artefact's big prize, a Wormhole straight to a boosted final prize, or ${free}, played after), or a hazard, which ends it short of the final prize. Riskier routes have richer planets; it's tuned so every route pays about the same on average.`}),
      waysIn("expedition", x),
      pictures(EXPEDITION_ART),
      section("How it plays",
        el("div", {className: "grid2"}, field("Its name", W.name), field("Hint at the chart", W.hint),
          field("Hint in a sector", W.planet_hint), field("Your ship", W.start), field("The final destination", W.final),
          field("A sector is called", W.sector)),
        folded("x_words", "Names: what a planet holds, the hazard levels and the hazards",
          el("div", {className: "grid2"}, field("Credits", W.credits_name), field("A multiplier", W.mult_name),
            field("The Scanner", W.scanner_name), field("The Shuttle", W.shuttle_name), field("Shields", W.shields_name),
            field("The artefact", W.artefact_name), field("The Wormhole", W.wormhole_name), field(C.data.bonuses.free.name, W.spins_name),
            ...L.map((input, i) => field(`Hazard level ${i + 1}`, input)), field("Hazards (any, comma separated)", T.hazards))),
        folded("x_routes", "The routes: lengths and hazard levels",
          el("div", {className: "grid2"}, field("Sectors on a route (value:weight)", T.lengths),
            field("Hazards grow each sector by (weight)", T.ramp),
            ...T.levels.flatMap((lv, i) => [field(`${x.level_names[i]}: how often (weight)`, lv.weight), field(`${x.level_names[i]}: hazards (weight)`, lv.hazard),
              field(`${x.level_names[i]}: prize scale (×)`, lv.scale), field(`${x.level_names[i]}: final prize (× bet)`, lv.final)]))),
        folded("x_planets", "The planets and their prizes",
          el("div", {className: "grid2"}, ...PLANETS.map(([, label], i) => field(`${label}: how often (weight)`, T.kinds[i])),
            ...TECHS.map(([, label], i) => field(`Tech: ${label} (weight)`, T.techs[i])),
            ...SPECIALS.map(([, label], i) => field(`Special: ${label} (weight)`, T.specials[i])),
            field("Credits (× bet, value:weight)", T.credits), field("Multipliers added (value:weight)", T.mults),
            field("The artefact (× bet, value:weight)", T.artefact), field("Free games (value:weight)", T.spins),
            field("The Wormhole boosts the final prize (×)", T.wormhole))),
        saveRow("Save the expedition", () => save({expedition: {
          ...Object.fromEntries(words.map(k => [k, W[k].value])), level_names: L.map(a => a.value),
          hazards: T.hazards.value.split(",").map(h => h.trim()).filter(Boolean), lengths: parseTable(T.lengths.value),
          levels: T.levels.map(lv => ({weight: +lv.weight.value, hazard: +lv.hazard.value, scale: +lv.scale.value, final: +lv.final.value})),
          ramp: +T.ramp.value, kinds: PLANETS.map(([k], i) => [k, +T.kinds[i].value]), techs: TECHS.map(([k], i) => [k, +T.techs[i].value]),
          specials: SPECIALS.map(([k], i) => [k, +T.specials[i].value]), credits: parseTable(T.credits.value), mults: parseTable(T.mults.value),
          artefact: parseTable(T.artefact.value), spins: parseTable(T.spins.value), wormhole: +T.wormhole.value}}, "Expedition saved.")))];
  });
}

// ------------------------------------------------------------------ Buy Bonus and the Jackpot Pick
function buyRow(by) {
  const {el} = C, r = C.data.bonuses.routes;
  const on = el("input", {type: "checkbox", checked: by.enabled, ariaLabel: "Offer Buy Bonus",
    onchange: () => save({buy: {enabled: on.checked}}, `Buy Bonus ${on.checked ? "offered" : "off"}.`)});
  const tags = by.enabled ? [tag(`${by.cost}× the bet`), plays(r.buy) ? tag(plays(r.buy)) : tag("nothing to buy yet", "warn")] : [tag("off")];
  return row("buy", {title: "Buy Bonus", sub: "pay to go straight into a bonus", tags, off: !by.enabled,
    toggle: el("label", {className: "confirm"}, on, "Offer it")}, () => {
    const cost = num(by.cost, 10, 500, 1, "Cost (× bet)");
    return [
      by.enabled ? null : offNote("it"),
      el("p", {className: "hint", textContent: plays(r.buy) ? `Pay a multiple of the bet for ${plays(r.buy)}.` : "Which bonuses it gives is ticked on each bonus (“Buy Bonus can give it”)."}),
      section("Price", el("div", {className: "controls"}, field("Cost (× bet)", cost),
        el("button", {type: "button", className: "primary", textContent: "Save", onclick: () => save({buy: {cost: +cost.value}}, "Buy Bonus saved.")})))];
  });
}

function pickRow() {
  const {el} = C;
  return row("pick", {title: "Jackpot Pick", sub: "shared by every slot on the floor", tags: [tag("always on")],
    tryIt: el("button", {type: "button", textContent: "▶ Try it", onclick: () => C.play({rig: {jackpot: "mini"}})})}, () => [
    el("p", {className: "hint", textContent: "A random trigger on any spin (likelier on bigger bets) opens a board of coins; three alike win that meter (Mini, Minor, Major or Grand). Its odds and meters are the floor's, so there's nothing to set here."})]);
}
