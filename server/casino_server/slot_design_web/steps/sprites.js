// Step 7, Sprites: how symbols move on a win (a preset per tier group), the screen's colours and fonts, and the
// cabinet on the casino floor. The mockup shows it live; "Show a win" lays a five-of-a-kind on the middle line.
import {createGame} from "../mockup/game.js";
import {designConfig, loadMath} from "../mockup/design.js";

const GROUPS = [["wild", "Wild"], ["high", "High pays"], ["mid", "Mid pays"], ["low", "Low pays (royals)"], ["scatter", "Scatters"]];
const COLOURS = [["gold", "Accent (titles, borders)"], ["goldHi", "Highlight"], ["edge", "Panel edges"], ["cream", "Text"], ["muted", "Quiet text"],
  ["ink", "Text on gold"], ["win", "Win amounts"], ["spin", "Spin button"], ["alert", "Alerts (free games, fire)"]];
let C, game = null, parts = {};

export function render(ctx, body) {
  C = ctx;
  const {el} = C;
  const canvas = el("canvas", {width: 1280, height: 720, className: "wz-canvas", ariaLabel: "The mockup"});
  const tier = el("select", {ariaLabel: "Which tier wins"}, ...C.data.ladder.tiers.filter(t => !["BS", "FS"].includes(t))
    .map(t => el("option", {value: t, textContent: `${t}: ${(C.data.symbols.find(s => s.id === C.data.ladder.slots[t]) || {}).name || "—"}`})));
  parts = {win: el("div", {className: "pane"}), theme: el("div", {className: "pane"}), cab: el("div", {className: "pane"})};
  body.append(
    el("p", {className: "lead", textContent: "How the machine moves and feels: what each symbol does on a win, the screen's colours and fonts, and the cabinet players walk up to on the floor."}),
    el("div", {className: "card"}, canvas, el("div", {className: "controls"}, el("span", {className: "hint", textContent: "Show a win:"}), tier,
      el("button", {type: "button", textContent: "▶ Show it", onclick: () => game && game.demoWin(tier.value)}),
      el("span", {className: "hint", textContent: "or click Spin on the screen."}))),
    el("div", {className: "wz-cards"},
      el("div", {className: "card"}, el("h3", {textContent: "Win animations"}), parts.win),
      el("div", {className: "card"}, el("h3", {textContent: "Colours and fonts"}), parts.theme),
      el("div", {className: "card"}, el("h3", {textContent: "Floor cabinet"}), parts.cab)));
  draw();
  loadMath().then(() => {
    if (game) game.destroy();
    game = createGame(canvas, designConfig(C.data, C.img));
    setTimeout(() => game && game.demoWin(tier.value), 600);
  }).catch(e => C.status(e.message, "warn"));
}

export function leave() { if (game) { game.destroy(); game = null; } }

export function update(ctx) {
  C = ctx;
  if (game) game.setConfig(designConfig(C.data, C.img));
  draw();
}

async function patch(body) {
  try {
    await C.api("PATCH", `/api/slot-design/${C.did}/sprites`, body);
    if (C.data.steps.find(s => s.id === "sprites").status === "todo") await C.setStep("sprites", "doing"); else await C.refresh();
  } catch (e) { C.status(e.message, "warn"); }
}

function draw() {
  const {el} = C, sp = C.data.sprites;
  if (!parts.win.contains(document.activeElement)) parts.win.replaceChildren(...GROUPS.map(([g, label]) => {
    const w = sp.win[g];
    const preset = el("select", {ariaLabel: `${label}: animation`}, ...sp.presets.map(p => el("option", {value: p, textContent: p})));
    preset.value = w.preset;
    const strength = el("input", {type: "range", min: 0.25, max: 2, step: 0.05, value: w.strength, ariaLabel: `${label}: strength`});
    const colour = el("input", {type: "color", value: w.colour, ariaLabel: `${label}: glow colour`, title: "Glow colour"});
    const send = () => patch({win: {[g]: {preset: preset.value, strength: +strength.value, colour: colour.value}}});
    preset.addEventListener("change", send); strength.addEventListener("change", send); colour.addEventListener("change", send);
    return el("div", {className: "wz-row"}, el("b", {textContent: label}), preset, strength, colour);
  }));
  if (!parts.theme.contains(document.activeElement)) {
    const fontSel = (key, label) => {
      const s = el("select", {ariaLabel: label}, ...sp.font_list.map(f => el("option", {value: f, textContent: f.replace(/\.(ttf|otf)$/i, "")})));
      s.value = sp.fonts[key];
      s.addEventListener("change", () => patch({fonts: {[key]: s.value}}));
      return el("label", {className: "field"}, el("span", {textContent: label}), s);
    };
    parts.theme.replaceChildren(
      el("div", {className: "wz-swatches"}, ...COLOURS.map(([k, label]) => {
        const i = el("input", {type: "color", value: sp.colours[k], ariaLabel: label});
        i.addEventListener("change", () => patch({colours: {[k]: i.value}}));
        return el("label", {className: "wz-swatch"}, i, el("span", {textContent: label}));
      })),
      el("div", {className: "grid2"}, fontSel("display", "Display font (banners, titles)"), fontSel("ui", "Interface font (numbers, buttons)")),
      el("p", {className: "hint", textContent: "Fonts come from the game's set or any added on the Scene step."}),
      el("button", {type: "button", textContent: "Back to Armadillo's colours", onclick: () => patch({colours: {gold: "#f4c94f", goldHi: "#fff1b0", edge: "#d9a54a",
        cream: "#f6ead0", muted: "#b89b74", ink: "#2b1004", win: "#ffe27a", spin: "#f0b43a", alert: "#7d130c"}})}));
  }
  if (!parts.cab.contains(document.activeElement) || document.activeElement.type === "color") drawCabinet();
}

// ------------------------------------------------------------------ the floor cabinet (slot_cabinet.gd's front, ×6)
function drawCabinet() {
  const {el} = C, cab = C.data.sprites.cabinet;
  const cv = el("canvas", {width: 240, height: 420, className: "wz-cab", ariaLabel: "The cabinet on the floor"});
  const colour = (k, label) => { const i = el("input", {type: "color", value: cab[k], ariaLabel: label}); i.addEventListener("change", () => patch({cabinet: {[k]: i.value}})); return el("label", {className: "wz-swatch"}, i, el("span", {textContent: label})); };
  const lines = [0, 1].map(i => el("input", {value: cab.lines[i] || "", maxLength: 12, placeholder: i ? "optional" : "TOPPER", ariaLabel: `Topper line ${i + 1}`}));
  const save = el("button", {type: "button", textContent: "Save the topper", onclick: () => patch({cabinet: {lines: lines.map(i => i.value).filter(Boolean)}})});
  parts.cab.replaceChildren(el("div", {className: "wz-cabrow"}, cv, el("div", {className: "pane"},
    colour("body", "Body"), colour("trim", "Trim"), colour("title", "Topper lettering"), ...lines, save,
    el("p", {className: "hint", textContent: "Its little screen shows each spin on the floor."}))));
  paintCabinet(cv, cab);
}

// A colour lightened (k > 1) or darkened (k < 1), as #rrggbb.
function shade(hex, k) {
  const n = parseInt(hex.slice(1), 16), f = c => Math.max(0, Math.min(255, Math.round(c * k))).toString(16).padStart(2, "0");
  return "#" + f(n >> 16) + f((n >> 8) & 255) + f(n & 255);
}

function paintCabinet(cv, cab) {
  const g = cv.getContext("2d"), S = 6, ox = 120, oy = 400;
  const box = (x, y, w, h, base) => {
    const gr = g.createLinearGradient(0, oy + y * S, 0, oy + (y + h) * S);
    gr.addColorStop(0, shade(base, 1.25)); gr.addColorStop(0.5, shade(base, 0.8)); gr.addColorStop(1, shade(base, 0.45));
    g.fillStyle = gr; g.fillRect(ox + x * S, oy + y * S, w * S, h * S);
  };
  g.clearRect(0, 0, cv.width, cv.height);
  g.fillStyle = "rgba(0,0,0,.35)"; g.beginPath(); g.ellipse(ox, oy, 17 * S, 4.6 * S, 0, 0, 7); g.fill();
  box(-14, -8, 28, 8, shade(cab.body, 0.8));
  box(-15, -22, 30, 14, cab.body);
  g.fillStyle = shade(cab.body, 1.6); g.fillRect(ox - 6 * S, oy - 18 * S, 12 * S, 7 * S);
  g.strokeStyle = cab.trim; g.lineWidth = 3; g.strokeRect(ox - 6 * S, oy - 18 * S, 12 * S, 7 * S);
  box(-16, -26, 32, 5, shade(cab.body, 2));
  ["#4fb3ff", "#55d07a", "#c768ff", "#ff5a48", "#ffb347"].forEach((c, i) => { g.fillStyle = c; g.fillRect(ox + (-12 + i * 5.2) * S, oy - 25 * S, 3.4 * S, 1.6 * S); });
  box(-15, -44, 30, 18, "#2a1a10");
  // the mini screen: the ladder's symbols
  g.fillStyle = "#0b0604"; g.fillRect(ox - 13 * S, oy - 42.5 * S, 26 * S, 15 * S);
  const tiers = C.data.ladder.tiers.filter(t => C.data.ladder.slots[t]);
  const cw = 26 * S / 5, ch = 15 * S / 4;
  for (let r = 0; r < 5; r++) for (let row = 0; row < 4; row++) {
    const t = tiers[(r * 7 + row * 3) % Math.max(1, tiers.length)], s = C.data.symbols.find(x => x.id === C.data.ladder.slots[t]);
    if (!s || !s.file) continue;
    const im = new Image();
    im.onload = () => g.drawImage(im, ox - 13 * S + r * cw, oy - 42.5 * S + row * ch, cw, ch);
    im.src = C.img(s.file);
  }
  box(-14, -54, 28, 10, cab.body);
  g.fillStyle = cab.title; g.textAlign = "center"; g.textBaseline = "middle"; g.font = `700 ${cab.lines.length > 1 ? 20 : 26}px "Arial Narrow", sans-serif`;
  cab.lines.forEach((l, i) => g.fillText(l, ox, oy + (cab.lines.length > 1 ? -51 + i * 3.8 : -49) * S, 27 * S));
  g.fillStyle = cab.trim;
  g.fillRect(ox - 15.8 * S, oy - 54 * S, 1.2 * S, 46 * S); g.fillRect(ox + 14.6 * S, oy - 54 * S, 1.2 * S, 46 * S);
  g.fillRect(ox - 15.8 * S, oy - 55.2 * S, 31.6 * S, 1 * S);
  box(-15.8, -63, 31.6, 8, shade(cab.body, 1.3));
  g.fillStyle = "#c97a2a"; g.fillRect(ox - 1.8 * S, oy - 65 * S, 3.6 * S, 4.5 * S);
}
