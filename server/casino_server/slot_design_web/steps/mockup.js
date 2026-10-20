// Step 10, Mockup & sign-off: the whole machine, playable, built from every earlier step; force features, bonuses
// and jackpots onto the next spin to check them; the checklist of what Build needs; the rules screen's words; and
// the sign-off, which locks how the slot pays (Value ladder, Features, Bonus games, Maths) until it's reopened.
import {createGame} from "../mockup/game.js";
import {designConfig, loadMath} from "../mockup/design.js";
import {typing} from "./artslot.js";

const NAMES = {wilds: "Random Wilds", wildReels: "Wild Reels", colossal: "Colossal Reels", multiplier: "Multiplier",
  upgrade: "Symbol Upgrade", repeat: "Repeat Win", instant: "Instant Win"};
let C, game = null, side = null;

export function render(ctx, body) {
  C = ctx;
  const {el} = C, d = C.data;
  const canvas = el("canvas", {width: 1280, height: 720, className: "wz-canvas", ariaLabel: "The mockup"});
  const boxes = d.features.enabled.map(f => el("label", {className: "confirm"}, el("input", {type: "checkbox", value: f}), NAMES[f] || f));
  const trigger = el("select", {ariaLabel: "Bonus on the next spin"}, ...[["", "no bonus"], ["trail", d.bonuses.trail.name], ["free", d.bonuses.free.name], ...(d.bonuses.battle.enabled ? [["battle", d.bonuses.battle.name]] : []), ...(d.bonuses.voyage.enabled ? [["voyage", d.bonuses.voyage.name]] : []), ...(d.bonuses.expedition.enabled ? [["expedition", d.bonuses.expedition.name]] : [])].map(([v, t]) => el("option", {value: v, textContent: t})));
  const jackpot = el("select", {ariaLabel: "Jackpot Pick on the next spin"}, ...["", "mini", "minor", "major", "grand"].map(v => el("option", {value: v, textContent: v ? v[0].toUpperCase() + v.slice(1) + " jackpot" : "no jackpot"})));
  const speed = el("select", {ariaLabel: "Speed"}, ...[[0.5, "half speed"], [1, "normal speed"], [2, "double speed"]].map(([v, t]) => el("option", {value: v, textContent: t})));
  speed.value = 1;
  speed.addEventListener("change", () => game && game.setSpeed(+speed.value));
  side = el("div", {className: "pane"});
  body.append(
    el("p", {className: "lead", textContent: "The whole machine, built from every step so far: play it, force anything onto the next spin, then sign it off for Build."}),
    el("div", {className: "card"}, canvas,
      el("div", {className: "controls"}, el("b", {textContent: "Next spin:"}), ...boxes, trigger, jackpot,
        el("button", {type: "button", className: "primary", textContent: "Spin it", onclick: () => {
          if (!game) return;
          game.rig({features: boxes.map(b => b.firstChild).filter(i => i.checked).map(i => i.value), trigger: trigger.value || null, jackpot: jackpot.value || null});
          game.spin();
          for (const b of boxes) b.firstChild.checked = false;
          trigger.value = jackpot.value = "";
        }})),
      el("div", {className: "controls"}, speed, el("button", {type: "button", textContent: "Top up the credit", onclick: () => game && game.topUp()}),
        el("span", {className: "hint", textContent: "INFO on the screen shows the rules below. Space spins."}))),
    side);
  drawSide();
  loadMath().then(() => { if (game) game.destroy(); game = createGame(canvas, designConfig(C.data, C.img)); })
    .catch(e => C.status(e.message, "warn"));
}

export function leave() { if (game) { game.destroy(); game = null; } }

export function update(ctx) {
  C = ctx;
  if (game) game.setConfig(designConfig(C.data, C.img));
  if (side && !typing(side)) drawSide();
}

function drawSide() {
  const {el} = C, so = C.data.signoff;
  const lines = so.rules.map((l, i) => el("textarea", {rows: 2, value: l, ariaLabel: `Rules line ${i + 1}`}));
  const mark = c => c.ok ? "✓" : c.required ? "✗" : "•";
  side.replaceChildren(el("div", {className: "wz-cards"},
    el("div", {className: "card"}, el("h3", {textContent: "Checklist"}),
      el("ul", {className: "wz-check"}, ...so.checklist.map(c => el("li", {className: c.ok ? "ok" : c.required ? "bad" : "warn"},
        el("span", {className: "m", textContent: mark(c)}), el("a", {href: `#design/${C.did}/${c.step}`, textContent: c.label}),
        c.required ? null : el("span", {className: "hint", textContent: " (worth a look)"})))),
      el("p", {className: "hint", textContent: "✗ must be done before sign-off; • are stand-ins or unfinished, fine for a first build."})),
    el("div", {className: "card"}, el("h3", {textContent: "Rules screen"}),
      el("p", {className: "hint", textContent: so.rules_custom ? "Your words." : "Written from the design; edit them if you like."}),
      ...lines,
      el("div", {className: "controls"},
        el("button", {type: "button", className: "primary", textContent: "Save the rules", onclick: () => put(lines.map(t => t.value))}),
        so.rules_custom ? el("button", {type: "button", textContent: "Write them again from the design", onclick: () => put(null)}) : null)),
    el("div", {className: "card"}, el("h3", {textContent: "Sign-off"}),
      so.signed_off
        ? el("div", {className: "pane"}, el("span", {className: "tag ok", textContent: `Signed off ${so.signed_off.at.replace("T", " ")}`}),
            el("p", {className: "hint", textContent: "How it pays is locked. Build makes it a cabinet."}),
            el("div", {className: "controls"}, el("button", {type: "button", textContent: "Reopen", onclick: () => post("reopen", "Reopened: it can change again.")}),
              el("a", {href: `#design/${C.did}/build`, textContent: "On to Build ▶"})))
        : el("div", {className: "pane"},
            el("p", {className: "hint", textContent: so.ready ? "Everything Build needs is in place." : "Finish the ✗ items first."}),
            el("button", {type: "button", className: "primary", textContent: "Sign it off", disabled: !so.ready, onclick: () => post("sign-off", "Signed off.")})))));
}

async function put(lines) {
  try { await C.api("PUT", `/api/slot-design/${C.did}/rules`, {lines}); await C.refresh(); C.status("Rules saved.", "ok"); }
  catch (e) { C.status(e.message, "warn"); }
}
async function post(what, msg) {
  try { await C.api("POST", `/api/slot-design/${C.did}/${what}`); await C.refresh(); C.status(msg, "ok"); }
  catch (e) { C.status(e.message, "warn"); }
}
