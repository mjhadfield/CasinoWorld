// Step 6, Bonus games: the Trail bonus (its names, length, prizepot, the mix of special spaces, the coin values and
// its pictures), the free games, Buy Bonus, and the shared Jackpot Pick. "Try it" plays the mockup straight into it.
import {artSlot, parseTable, specs, tableText, typing} from "./artslot.js";

const SPACES = [["snake", "Hazards"], ["heart", "Hearts"], ["forward", "Forward"], ["back", "Back"], ["lightning", "Lightning rolls"], ["crate", "Coin crates"]];
let C;

export function render(ctx, body) {
  C = ctx;
  const {el} = C, b = C.data.bonuses, t = b.trail;
  const field = (label, input) => el("label", {className: "field"}, el("span", {textContent: label}), input);
  const num = (v, min, max, step = 1) => el("input", {type: "number", min, max, step, value: v, className: "wz-num"});
  const txt = v => el("input", {value: v});
  const save = async (body, msg) => {
    try {
      await C.api("PATCH", `/api/slot-design/${C.did}/bonuses`, body);
      if (C.data.steps.find(s => s.id === "bonuses").status === "todo") await C.setStep("bonuses", "doing"); else await C.refresh();
      C.status(msg, "ok");
    } catch (e) { C.status(e.message, "warn"); }
  };

  const T = {name: txt(t.name), launcher: txt(t.launcher), hint: txt(t.hint), length: num(t.length, 40, 200), prizepot: num(t.prizepot, 100, 10000, 50),
    upgrade: num(+(t.upgrade_chance * 100).toFixed(1), 0, 100, 0.5), double: num(+(t.double_chance * 100).toFixed(1), 0, 100, 0.5),
    coins: txt(tableText(t.coins)), crate: txt(tableText(t.crate_radius)),
    counts: Object.fromEntries(SPACES.map(([k]) => [k, num(t.counts[k] ?? 0, 0, 40)]))};
  const trail = el("div", {className: "card"}, el("div", {className: "card-head"}, el("h3", {textContent: "Trail bonus"}),
      el("span", {className: "hint", textContent: "3+ bonus scatters, or Buy Bonus"}),
      el("button", {type: "button", textContent: "▶ Try it", onclick: () => C.play({rig: {trigger: "trail"}})})),
    el("p", {className: "hint", textContent: "Each shot moves the mascot 1 to 6 spaces along a trail of coin prizes to the prizepot. Hazards cost a heart or end it."}),
    el("div", {className: "grid2"}, field("Its name", T.name), field("The launcher's name", T.launcher), field("Hint on its banner", T.hint),
      field("Trail length (spaces)", T.length), field("Prizepot (× bet)", T.prizepot),
      field("Spin Upgrade chance, %", T.upgrade), field("Coins Doubled chance, %", T.double)),
    el("h3", {textContent: "Special spaces on each trail"}),
    el("div", {className: "grid2"}, ...SPACES.map(([k, label]) => field(label, T.counts[k]))),
    el("div", {className: "grid2"}, field("Coin values (× bet, value:weight)", T.coins), field("Crate reach (spaces, value:weight)", T.crate)),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save the trail", onclick: () => save({trail: {
      name: T.name.value, launcher: T.launcher.value, hint: T.hint.value, length: +T.length.value, prizepot: +T.prizepot.value,
      upgrade_chance: +T.upgrade.value / 100, double_chance: +T.double.value / 100, coins: parseTable(T.coins.value),
      crate_radius: parseTable(T.crate.value), counts: Object.fromEntries(SPACES.map(([k]) => [k, +T.counts[k].value]))}}, "Trail saved.")})));

  const fname = txt(b.free.name), games = num(b.free.games, 1, 20);
  const free = el("div", {className: "card"}, el("div", {className: "card-head"}, el("h3", {textContent: "Free games"}),
      el("span", {className: "hint", textContent: "3+ free-spins scatters"}),
      el("button", {type: "button", textContent: "▶ Try it", onclick: () => C.play({rig: {trigger: "free"}})})),
    el("p", {className: "hint", textContent: "Paid at the triggering bet, with at least one random feature on every game (their free-game chances are on the Features step)."}),
    el("div", {className: "grid2"}, field("Their name", fname), field("How many", games)),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save", onclick: () => save({free: {name: fname.value, games: +games.value}}, "Free games saved.")})));

  const buyOn = el("input", {type: "checkbox", checked: b.buy.enabled}), cost = num(b.buy.cost, 10, 500);
  const buy = el("div", {className: "card"}, el("h3", {textContent: "Buy Bonus"}),
    el("p", {className: "hint", textContent: "Pay a multiple of the bet to go straight into the trail bonus."}),
    el("label", {className: "confirm"}, buyOn, "Offer Buy Bonus"), field("Cost (× bet)", cost),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save", onclick: () => save({buy: {enabled: buyOn.checked, cost: +cost.value}}, "Buy Bonus saved.")})));

  const pick = el("div", {className: "card"}, el("div", {className: "card-head"}, el("h3", {textContent: "Jackpot Pick"}),
      el("button", {type: "button", textContent: "▶ Try it", onclick: () => C.play({rig: {jackpot: "mini"}})})),
    el("p", {className: "hint", textContent: "Shared by every slot on the floor: a random trigger on any spin (likelier on bigger bets) opens a board of coins; three alike win that meter (Mini, Minor, Major or Grand). Always on."}));

  body.append(
    el("p", {className: "lead", textContent: "The bonus games and how they look. The trail's settings change what it's worth, which the Maths step measures."}),
    el("div", {className: "wz-cards"}, trail, el("div", {className: "pane"}, free, buy, pick)),
    el("div", {className: "card"}, el("h3", {textContent: "Bonus pictures"}),
      el("div", {className: "wz-slots"}, ...Object.keys(C.data.art).filter(k => C.data.art[k].step === "bonuses" || k === "armadillo").map(k => artSlot(C, k)))),
    specs(C, "bonus"));
}

export function update(ctx) {
  C = ctx;
  const body = document.querySelector(".wz-body");
  if (body && !typing(body)) { body.replaceChildren(); render(ctx, body); }
}
