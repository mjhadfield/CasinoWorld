// Step 4, Scene: the background, the logo lettering and the reel frame, seen live in the base-game mockup (it plays:
// press Spin). The mockup uses the Value ladder's symbols and Armadillo's maths until the Maths step tunes this slot.
import {createGame} from "../mockup/game.js";
import {designConfig, loadMath} from "../mockup/design.js";

let C, game = null, parts = {}, bgBehind = false;

export function render(ctx, body) {
  C = ctx;
  const {el} = C;
  const canvas = el("canvas", {width: 1280, height: 720, className: "wz-canvas", ariaLabel: "The base-game mockup"});
  parts = {bg: el("div", {className: "pane"}), logo: el("div", {className: "pane"}), frame: el("div", {className: "pane"}), note: el("p", {className: "hint"})};
  body.append(
    el("p", {className: "lead", textContent: "The machine's look: background, logo and reel frame. The mockup below is the real screen layout and plays (click Spin), using the Value ladder's symbols."}),
    el("div", {className: "card"}, canvas, parts.note),
    el("div", {className: "wz-cards"},
      el("div", {className: "card"}, el("h3", {textContent: "Background"}), parts.bg),
      el("div", {className: "card"}, el("h3", {textContent: "Logo"}), parts.logo),
      el("div", {className: "card"}, el("h3", {textContent: "Reel frame"}), parts.frame)));
  drawBg(); drawLogo(); drawFrame();
  loadMath().then(() => {
    if (game) game.destroy();
    game = createGame(canvas, designConfig(C.data, C.img));
  }).catch(e => C.status(e.message, "warn"));
  note();
}

export function leave() { if (game) { game.destroy(); game = null; } }

// Is the Background pane showing older data (left alone while you type or pick in it)? The wizard keeps refreshing.
export const behind = () => bgBehind;

export function update(ctx) {
  C = ctx;
  if (!document.body.contains(parts.bg)) { if (game) { game.destroy(); game = null; } return; }
  if (game) game.setConfig(designConfig(C.data, C.img));
  drawBg(); drawFrame(); refreshLogoStrip(); note();
}

function note() {
  const lad = C.data.ladder, missing = lad.tiers.length - Object.keys(lad.slots).length;
  parts.note.textContent = missing ? `${missing} tier${missing === 1 ? "" : "s"} of the Value ladder still empty: Armadillo's pictures stand in.` : "";
}

async function patch(body, msg) {
  try {
    await C.api("PATCH", `/api/slot-design/${C.did}/scene`, body);
    if (C.data.steps.find(s => s.id === "scene").status === "todo") await C.setStep("scene", "doing");
    else await C.refresh();
    if (msg) C.status(msg, "ok");
  } catch (e) { C.status(e.message, "warn"); }
}

const boardImages = () => [
  ...C.data.symbols.filter(s => s.file).map(s => [`${s.name}: chosen art`, s.file]),
  ...C.data.symbols.flatMap(s => s.refs.map((r, k) => [`${s.name}: reference ${k + 1}`, r])),
  ...C.data.sources.map(p => [`Sheet: ${p.split("/")[1]}`, p])];

// ------------------------------------------------------------------ background
function drawBg() {
  const {el} = C, sc = C.data.scene;
  // Don't redraw under a description being typed or a picker being used (a pressed button is fine to redraw).
  const a = document.activeElement;
  bgBehind = parts.bg.contains(a) && a.matches("textarea, select");
  if (bgBehind) return;
  const jobs = C.data.scene_jobs || [];
  const desc = el("textarea", {rows: 2, ariaLabel: "Describe the background", placeholder: "e.g. a starship bridge looking out on a nebula, dim and moody"});
  const file = el("input", {type: "file", accept: "image/png,image/jpeg,image/webp", ariaLabel: "Upload a background"});
  file.addEventListener("change", async () => {
    const f = file.files[0];
    if (!f) return;
    try { await C.api("PUT", `/api/slot-design/${C.did}/scene/backgrounds/${encodeURIComponent(f.name)}`, await f.arrayBuffer(), true); await C.refresh(); }
    catch (e) { C.status(e.message, "warn"); }
  });
  const pick = el("select", {ariaLabel: "Art on the board"}, el("option", {value: "", textContent: "An image already on the board…"}),
    ...boardImages().map(([l, p]) => el("option", {value: p, textContent: l})));
  parts.bg.replaceChildren(
    el("div", {className: "dz-strip"},
      el("button", {type: "button", ariaPressed: String(!sc.background), title: "No picture: the drawn dusk", onclick: () => patch({background: null})},
        el("span", {className: "wz-none", textContent: "None"})),
      ...sc.backgrounds.map(p => el("button", {type: "button", ariaPressed: String(sc.background === p), title: p.split("/")[1],
        onclick: () => patch({background: p}, "Background chosen.")}, el("img", {src: C.img(p), alt: p, className: "wide", loading: "lazy"})))),
    ...jobs.map(j => el("p", {className: "hint", textContent: `Background: ${{queued: "queued", waiting: "waiting for FLUX", running: `making ${j.done + 1} of ${j.count}`, failed: "failed: " + j.error}[j.status]}`})),
    el("label", {className: "field"}, el("span", {textContent: "Generate (three takes, about two minutes each)"}), desc),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Generate", onclick: async () => {
      try { await C.api("POST", `/api/slot-design/${C.did}/scene/backgrounds`, {description: desc.value}); desc.value = ""; C.status("Background queued: the takes appear here as FLUX finishes them.", "ok"); await C.refresh(); }
      catch (e) { C.status(e.message, "warn"); }
    }})),
    el("div", {className: "controls"}, file),
    el("div", {className: "controls"}, pick, el("button", {type: "button", textContent: "Use", onclick: async () => {
      if (!pick.value) return;
      try { await C.api("POST", `/api/slot-design/${C.did}/scene/backgrounds`, {path: pick.value}); await C.refresh(); }
      catch (e) { C.status(e.message, "warn"); }
    }})));
}

// ------------------------------------------------------------------ logo
function refreshLogoStrip() {
  const strip = parts.logo.querySelector(".wz-logos");
  if (strip) strip.replaceWith(logoStrip());
}
function logoStrip() {
  const {el} = C, sc = C.data.scene;
  return el("div", {className: "dz-strip wz-logos"}, ...sc.logos.map(p => el("button", {type: "button", ariaPressed: String(sc.logo.file === p),
    title: p.split("/")[1], onclick: () => patch({logo_file: p})}, el("img", {src: C.img(p), alt: p, className: "wide contain", loading: "lazy"}))));
}
function drawLogo() {
  const {el} = C, sc = C.data.scene, lg = sc.logo || {};
  const lines = [0, 1, 2].map(i => el("input", {value: (lg.lines || [C.data.name.toUpperCase()])[i] || "", placeholder: i ? "optional" : "e.g. STAR TREK", ariaLabel: `Line ${i + 1}`}));
  const font = el("select", {ariaLabel: "Font"}, ...sc.fonts.map(f => el("option", {value: f, textContent: f.replace(/\.(ttf|otf)$/i, "")})));
  font.value = lg.font || "Cinzel-SemiBold.ttf";
  const colour = (label, v) => el("input", {type: "color", value: v, ariaLabel: label, title: label});
  const top = colour("Top colour", lg.top || "#fff1b0"), bottom = colour("Bottom colour", lg.bottom || "#d39a26"), outline = colour("Outline", lg.outline || "#2b1004");
  const emblem = el("select", {ariaLabel: "Emblem"}, el("option", {value: "", textContent: "No emblem"}), ...boardImages().map(([l, p]) => el("option", {value: p, textContent: l})));
  emblem.value = lg.emblem || "";
  const fontFile = el("input", {type: "file", accept: ".ttf,.otf", ariaLabel: "Add a font"});
  fontFile.addEventListener("change", async () => {
    const f = fontFile.files[0];
    if (!f) return;
    try {
      const {font: name} = await C.api("PUT", `/api/slot-design/${C.did}/fonts/${encodeURIComponent(f.name)}`, await f.arrayBuffer(), true);
      await C.refresh();
      font.append(el("option", {value: name, textContent: name}));
      font.value = name;
      C.status(`Font ${name} added.`, "ok");
    } catch (e) { C.status(e.message, "warn"); }
  });
  parts.logo.replaceChildren(
    el("p", {className: "hint", textContent: "Lettering is rendered, not drawn by FLUX (it can't spell). The first line is the biggest."}),
    ...lines,
    el("div", {className: "grid2"}, el("label", {className: "field"}, el("span", {textContent: "Font"}), font),
      el("label", {className: "field"}, el("span", {textContent: "Emblem"}), emblem)),
    el("div", {className: "controls"}, el("span", {className: "hint", textContent: "Colours"}), top, bottom, outline),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Render the logo", onclick: async () => {
      try {
        await C.api("POST", `/api/slot-design/${C.did}/scene/logo`, {lines: lines.map(i => i.value), font: font.value,
          top: top.value, bottom: bottom.value, outline: outline.value, emblem: emblem.value || null});
        if (C.data.steps.find(s => s.id === "scene").status === "todo") await C.setStep("scene", "doing"); else await C.refresh();
        C.status("Logo rendered.", "ok");
      } catch (e) { C.status(e.message, "warn"); }
    }})),
    el("label", {className: "field"}, el("span", {textContent: "Add a font (.ttf or .otf)"}), fontFile),
    logoStrip());
}

// ------------------------------------------------------------------ frame
function drawFrame() {
  const {el} = C, sc = C.data.scene, fr = sc.frame;
  if (parts.frame.contains(document.activeElement) && document.activeElement.type === "color") return;
  const colour = el("input", {type: "color", value: fr.colour, ariaLabel: "Frame colour"});
  colour.addEventListener("change", () => patch({frame: {style: fr.style, colour: colour.value}}));
  parts.frame.replaceChildren(
    el("span", {className: "seg", role: "group", ariaLabel: "Frame style"}, ...sc.frame_styles.map(st =>
      el("button", {type: "button", textContent: st[0].toUpperCase() + st.slice(1), ariaPressed: String(fr.style === st),
        onclick: () => patch({frame: {style: st, colour: fr.colour}})}))),
    el("label", {className: "controls"}, el("span", {className: "hint", textContent: "Edge colour"}), colour),
    el("p", {className: "hint", textContent: "Wood is Armadillo's. The frame's style also dresses the side panels and the pop-ups."}));
}
