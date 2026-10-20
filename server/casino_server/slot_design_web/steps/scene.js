// Step 4, Scene: the slot screen's whole look, as a skin (slot_design_scene.py; docs/slots/scenes.md): its family
// (Classic's four frame styles, or LCARS), palette, glass, a shape per part, Claude's decor, fonts and the screen's
// words, plus the background and the logo. A design keeps several skins and plays the chosen one. This is the step
// Claude designs by hand: the Brief asks for a scene, and a Claude Code session answers with a new skin here. The
// mockup above is the real screen layout and plays (press Spin).
import {createGame} from "../mockup/game.js";
import {designConfig, loadMath} from "../mockup/design.js";

let C, game = null, parts = {}, bgBehind = false;
const binOpen = {backgrounds: false, logos: false, skins: false};   // is that Bin shown
const PALETTE = {hl: "Highlight", a: "Block A", b: "Block B", c: "Block C", d: "Deep", warn: "Warning", glass: "Glass",
  grand: "Grand", major: "Major", minor: "Minor", mini: "Mini"};
const COLOURS = {gold: "Accent", goldHi: "Highlight", goldLo: "Accent shadow", edge: "Panel edges", cream: "Text", muted: "Quiet text",
  ink: "Text on colour", shade: "Shade (banners, dimming)", win: "Win amounts", spin: "Spin button", alert: "Alerts"};
const PARTS = {meter: "Jackpot meters", panel: "Side panels and pop-ups", frame: "Reel frame", box: "Readouts and lists",
  button: "Buttons", spin: "Spin", deck: "Deck"};
const SHAPES = {tab: "Tab", pill: "Pill", glass: "Glass", elbow: "Elbows", half: "Half pill", disc: "Disc", bar: "Rail"};
const GLASS = [["opacity", "Tint", 0, 1, 0.01], ["sheen", "Sheen", 0, 0.5, 0.01], ["edge", "Edge", 0, 6, 0.5], ["blur", "Blur", 0, 40, 1]];

export function render(ctx, body) {
  C = ctx;
  const {el} = C;
  const canvas = el("canvas", {width: 1280, height: 720, className: "wz-canvas", ariaLabel: "The base-game mockup"});
  const pane = () => el("div", {className: "pane"});
  parts = {skins: el("div", {className: "wz-skins"}), brief: pane(), look: pane(), parts: pane(), decor: pane(), bg: pane(), logo: pane(),
    note: el("p", {className: "hint"}), partsTitle: el("h3", {textContent: "Parts"})};
  body.append(
    el("p", {className: "lead", textContent: "The machine's whole look: its scene. Pick one, tweak it, or ask Claude to design a new one from a brief. " +
      "The mockup is the real screen layout and plays (click Spin)."}),
    el("div", {className: "card"}, canvas, parts.note),
    parts.skins,
    el("div", {className: "wz-cards"},
      el("div", {className: "card"}, el("h3", {textContent: "Brief for Claude"}), parts.brief),
      el("div", {className: "card"}, el("h3", {textContent: "Look"}), parts.look),
      el("div", {className: "card"}, parts.partsTitle, parts.parts),
      el("div", {className: "card"}, el("h3", {textContent: "Decor"}), parts.decor),
      el("div", {className: "card"}, el("h3", {textContent: "Background"}), parts.bg),
      el("div", {className: "card"}, el("h3", {textContent: "Logo"}), parts.logo)));
  drawAll(true);
  loadMath().then(() => {
    if (game) game.destroy();
    game = createGame(canvas, designConfig(C.data, C.img));
  }).catch(e => C.status(e.message, "warn"));
}

export function leave() { if (game) { game.destroy(); game = null; } }

// Is the Background pane showing older data (left alone while you type or pick in it)? The wizard keeps refreshing.
export const behind = () => bgBehind;

export function update(ctx) {
  C = ctx;
  if (!document.body.contains(parts.bg)) { if (game) { game.destroy(); game = null; } return; }
  if (game) game.setConfig(designConfig(C.data, C.img));
  drawAll(false);
}

// A pane's new contents (what isn't shown is null or false).
const fill = (pane, ...kids) => pane.replaceChildren(...kids.filter(k => k != null && k !== false));

// A pane with a field in use (not a button just pressed) is left alone until you're done with it.
const held = root => root.contains(document.activeElement) && document.activeElement.tagName !== "BUTTON";

function drawAll(first) {
  for (const [k, draw] of [["skins", drawSkins], ["brief", drawBrief], ["look", drawLook], ["parts", drawParts], ["decor", drawDecor]])
    if (first || !held(parts[k])) draw();
  drawBg();
  if (first) drawLogo(); else refreshLogoStrip();
  const lad = C.data.ladder, missing = lad.tiers.length - Object.keys(lad.slots).length;
  parts.note.textContent = missing ? `${missing} tier${missing === 1 ? "" : "s"} of the Value ladder still empty: Armadillo's pictures stand in.` : "";
}

const sc = () => C.data.scene;
const skin = () => sc().edit;            // the chosen skin as saved (its fonts unresolved)
const lcars = () => skin().base === "lcars";

async function doing() {
  if (C.data.steps.find(s => s.id === "scene").status === "todo") await C.setStep("scene", "doing"); else await C.refresh();
}
async function patch(body, msg) {
  try { await C.api("PATCH", `/api/slot-design/${C.did}/scene`, body); await doing(); if (msg) C.status(msg, "ok"); }
  catch (e) { C.status(e.message, "warn"); }
}
async function skinPatch(body, msg) {
  try { await C.api("PATCH", `/api/slot-design/${C.did}/scene/skins/${sc().skin}`, body); await doing(); if (msg) C.status(msg, "ok"); }
  catch (e) { C.status(e.message, "warn"); await C.refresh(); }
}
async function skinDo(slug, action, body, msg) {
  try { await C.api("POST", `/api/slot-design/${C.did}/scene/skins/${slug}/${action}`, body); await doing(); if (msg) C.status(msg, "ok"); }
  catch (e) { C.status(e.message, "warn"); }
}

// ------------------------------------------------------------------ the scenes: pick, new, duplicate, rename, bin
const BY = {claude: "Claude's", mike: "Yours", house: "House"};
function drawSkins() {
  const {el} = C, s = sc();
  const cards = s.skins.map(k => el("button", {type: "button", className: "wz-skin", ariaPressed: String(k.slug === s.skin),
    title: k.slug === s.skin ? "Playing on the mockup (and built into the game)" : "Use this scene",
    onclick: () => k.slug !== s.skin && skinDo(k.slug, "choose", undefined, `${k.name} chosen.`)},
    el("b", {textContent: k.name}),
    el("span", {className: "hint", textContent: `${k.base === "lcars" ? "LCARS" : "Classic"} · ${BY[k.by] || k.by}`})));
  const cur = s.skins.find(k => k.slug === s.skin) || {};
  const binned = s.bin.skins || [];
  fill(parts.skins, 
    el("div", {className: "wz-skin-row"}, el("span", {className: "hint", textContent: "Scenes"}), ...cards),
    el("div", {className: "controls"},
      el("button", {type: "button", textContent: "Rename", onclick: () => {
        const name = prompt("Name this scene:", cur.name);
        if (name && name.trim()) skinDo(s.skin, "rename", {name}, "Renamed.");
      }}),
      el("button", {type: "button", textContent: "Duplicate", title: "A copy to change, leaving this one as it is",
        onclick: () => skinDo(s.skin, "duplicate", {name: `${cur.name} copy`}, "Copied: you're changing the copy.")}),
      cur.has_original ? el("button", {type: "button", textContent: "Reset to Claude's version", title: "Undo every tweak made to it since",
        onclick: () => confirm(`Put ${cur.name} back the way Claude made it?`) && skinDo(s.skin, "reset", undefined, "Back to Claude's version.")}) : null,
      el("button", {type: "button", textContent: "Bin", disabled: s.skins.length < 2, title: s.skins.length < 2 ? "It's the only scene" : "Into the Bin (restorable)",
        onclick: () => skinDo(s.skin, "bin", undefined, `${cur.name} is in the Bin.`)}),
      el("span", {className: "grow"}),
      el("span", {className: "hint", textContent: "New:"}),
      el("button", {type: "button", textContent: "Classic", onclick: () => skinDo(s.skin, "new", {base: "classic"}, "A new Classic scene.")}),
      el("button", {type: "button", textContent: "LCARS", onclick: () => skinDo(s.skin, "new", {base: "lcars"}, "A new LCARS scene.")}),
      binned.length ? el("button", {type: "button", textContent: `Bin (${binned.length})`, ariaPressed: String(binOpen.skins),
        onclick: () => { binOpen.skins = !binOpen.skins; drawSkins(); }}) : null),
    binOpen.skins && binned.length ? el("div", {className: "dz-panel"}, el("p", {className: "hint", textContent: "Binned scenes. Nothing is deleted."}),
      el("div", {className: "controls"}, ...binned.map(b => el("button", {type: "button", textContent: `Restore ${b.name}`,
        onclick: () => skinDo(b.slug, "restore", undefined, `${b.name} restored.`)})))) : "");
}

// ------------------------------------------------------------------ the Brief for Claude
function drawBrief() {
  const {el} = C, br = sc().brief;
  const text = el("textarea", {rows: 4, value: br.text, ariaLabel: "What you'd like",
    placeholder: "e.g. an LCARS interface like the phone mockup: glassy, light-blue highlights, elbows round the reels, readouts in the corners"});
  const file = el("input", {type: "file", accept: "image/png,image/jpeg,image/webp", ariaLabel: "Add a reference picture"});
  file.addEventListener("change", async () => {
    const f = file.files[0];
    if (!f) return;
    try { await C.api("PUT", `/api/slot-design/${C.did}/scene/brief/${encodeURIComponent(f.name)}`, await f.arrayBuffer(), true); await C.refresh(); }
    catch (e) { C.status(e.message, "warn"); }
  });
  const send = async (extra, msg) => {
    try { await C.api("PATCH", `/api/slot-design/${C.did}/scene/brief`, {text: text.value, ...extra}); await C.refresh(); if (msg) C.status(msg, "ok"); }
    catch (e) { C.status(e.message, "warn"); }
  };
  const answer = br.status === "answered" && sc().skins.find(k => k.slug === br.answer);
  fill(parts.brief, 
    el("p", {className: "hint", textContent: "Describe the scene you'd like and add pictures of the feel. Claude reads this, the concept, the art and the " +
      "lettering font, and designs a scene to pick and tweak here."}),
    text,
    el("div", {className: "dz-refs"}, ...br.refs.map(p => el("span", {className: "dz-ref"},
      el("a", {href: C.img(p), target: "_blank"}, el("img", {src: C.img(p), alt: "A reference"})),
      el("button", {type: "button", textContent: "✕", title: "Take it off the brief", onclick: () => send({refs: br.refs.filter(x => x !== p)})}))),
      el("label", {className: "field"}, el("span", {textContent: "Add a picture"}), file)),
    el("div", {className: "controls"},
      el("button", {type: "button", textContent: "Save", onclick: () => send({}, "Brief saved.")}),
      br.status === "waiting"
        ? el("button", {type: "button", textContent: "Withdraw", onclick: () => send({withdraw: true}, "Withdrawn.")})
        : el("button", {type: "button", className: "primary", textContent: "Ask Claude", onclick: () => send({ask: true}, "Asked: see below for how.")})),
    br.status === "waiting" ? el("p", {className: "wz-offnote", textContent: `Waiting for Claude since ${String(br.asked || "").replace("T", " ")}. ` +
      `In a Claude Code session in ~/Projects/CasinoWorld, say "design the ${C.data.name} scene". The new scene appears above when it's done.`}) : null,
    answer ? el("p", {className: "hint"}, `Claude answered with `, el("b", {textContent: answer.name}),
      answer.slug === sc().skin ? " (playing now)." : el("button", {type: "button", textContent: "Use it", onclick: () => skinDo(answer.slug, "choose")})) : null);
}

// ------------------------------------------------------------------ Look: family, palette, glass, fonts, colours, words
function swatch(label, value, onchange, tag) {
  const {el} = C, i = el("input", {type: "color", value, ariaLabel: label});
  i.addEventListener("change", () => onchange(i.value));
  return el("label", {className: "wz-swatch"}, i, el("span", {textContent: label}, ...(tag ? [el("em", {className: "wz-inherited", textContent: tag})] : [])));
}
function drawLook() {
  const {el} = C, sk = skin(), schema = sc().schema, lettering = sc().lettering_font.replace(/\.(ttf|otf)$/i, "");
  const fontSel = (role, label) => {
    const s = el("select", {ariaLabel: label}, el("option", {value: "@lettering", textContent: `The lettering font (${lettering})`}),
      ...sc().fonts.map(f => el("option", {value: f, textContent: f.replace(/\.(ttf|otf)$/i, "")})));
    s.value = sk.fonts[role];
    s.addEventListener("change", () => skinPatch({fonts: {[role]: s.value}}));
    return el("label", {className: "field"}, el("span", {textContent: label}), s);
  };
  const fontFile = el("input", {type: "file", accept: ".ttf,.otf", ariaLabel: "Add a font"});
  fontFile.addEventListener("change", async () => {
    const f = fontFile.files[0];
    if (!f) return;
    try { const {font} = await C.api("PUT", `/api/slot-design/${C.did}/fonts/${encodeURIComponent(f.name)}`, await f.arrayBuffer(), true); await C.refresh(); C.status(`Font ${font} added.`, "ok"); }
    catch (e) { C.status(e.message, "warn"); }
  });
  const words = Object.entries(schema.texts).map(([k, d]) => {
    const i = el("input", {value: sk.texts[k] || "", placeholder: d, ariaLabel: `Instead of ${d}`, maxLength: 24});
    i.addEventListener("change", () => skinPatch({texts: {[k]: i.value.trim()}}));
    return el("label", {className: "field"}, el("span", {textContent: d}), i);
  });
  fill(parts.look, 
    el("span", {className: "seg", role: "group", ariaLabel: "Family"}, ...[["classic", "Classic"], ["lcars", "LCARS"]].map(([b, l]) =>
      el("button", {type: "button", textContent: l, ariaPressed: String(sk.base === b),
        onclick: () => sk.base !== b && skinPatch({base: b}, `This scene is ${l} now.`)}))),
    el("p", {className: "hint", textContent: lcars() ? "LCARS: elbows, pills and readouts on frosted glass. Shapes per part are under Parts." :
      "Classic: the frame styles (metal, wood, neon, glass) under Parts."}),
    lcars() ? el("div", {className: "wz-sec"}, el("h4", {textContent: "Palette"}),
      el("div", {className: "wz-swatches"}, ...schema.palette.map(k => swatch(PALETTE[k] || k, sk.palette[k] || "#000000",
        v => skinPatch({palette: {[k]: v}}))))) : null,
    lcars() ? el("div", {className: "wz-sec"}, el("h4", {textContent: "Glass"}), ...GLASS.map(([k, label, lo, hi, step]) => {
      const out = el("output", {textContent: String(sk.glass[k] ?? 0)});
      const r = el("input", {type: "range", min: lo, max: hi, step, value: sk.glass[k] ?? 0, ariaLabel: `Glass ${label}`});
      r.addEventListener("input", () => { out.textContent = r.value; });
      r.addEventListener("change", () => skinPatch({glass: {[k]: +r.value}}));
      return el("label", {className: "dz-slider"}, el("span", {textContent: label}), r, out);
    }), el("p", {className: "hint", textContent: "Blur is how much of the background shows through the panels (it needs a background)."})) : null,
    el("div", {className: "grid2"}, fontSel("display", "Display font (titles, labels)"), fontSel("ui", "Interface font (numbers)")),
    el("label", {className: "field"}, el("span", {textContent: "Add a font (.ttf or .otf)"}), fontFile),
    el("details", {className: "wz-fold"}, el("summary", {textContent: "Screen colours (text, wins, banners, spin, alerts)"}),
      el("div", {className: "wz-swatches"}, ...Object.entries(COLOURS).map(([k, label]) => swatch(label, sk.colours[k], v => skinPatch({colours: {[k]: v}}))))),
    el("details", {className: "wz-fold"}, el("summary", {textContent: "Screen words (relabel SPIN, CREDIT, ...)"}),
      el("div", {className: "grid2"}, ...words)));
}

// ------------------------------------------------------------------ Parts: a shape and colours each (LCARS); frame and deck (Classic)
function colourSel(value, label, onchange, extra = []) {
  const {el} = C, sk = skin();
  const s = el("select", {ariaLabel: label},
    ...extra.map(([v, t]) => el("option", {value: v, textContent: t})),
    el("optgroup", {label: "Palette"}, ...Object.keys(sk.palette).map(k => el("option", {value: k, textContent: PALETTE[k] || k}))),
    el("optgroup", {label: "Screen colours"}, ...Object.keys(COLOURS).map(k => el("option", {value: k, textContent: COLOURS[k]}))));
  if (value && value[0] === "#") s.append(el("option", {value, textContent: value}));
  s.value = value;
  s.addEventListener("change", () => onchange(s.value));
  const chip = el("span", {className: "wz-chip"});
  chip.style.background = value === "tier" ? "linear-gradient(90deg,#f5a623,#b98fd6,#7fc4c9,#6f9fd8)" : value && value[0] === "#" ? value : sk.palette[value] || sk.colours[value] || "transparent";
  return el("span", {className: "wz-colour"}, chip, s);
}
function drawParts() {
  const {el} = C, sk = skin(), schema = sc().schema.parts;
  parts.partsTitle.textContent = lcars() ? "Parts" : "Reel frame and deck";
  if (!lcars()) return drawClassicParts();
  fill(parts.parts, ...Object.entries(PARTS).map(([p, label]) => {
    const v = sk.parts[p] || {}, def = schema[p];
    const shapes = el("span", {className: "seg", role: "group", ariaLabel: `${label}: shape`}, ...def.shapes.map(s =>
      el("button", {type: "button", textContent: SHAPES[s] || s, ariaPressed: String(v.shape === s), onclick: () => skinPatch({parts: {[p]: {shape: s}}})})));
    const cols = def.colours.filter(k => k !== "spine").map(k => el("label", {className: "wz-pcol"}, el("span", {className: "hint", textContent: k}),
      colourSel(v[k] || "", `${label}: ${k}`, val => skinPatch({parts: {[p]: {[k]: val}}}), p === "meter" && k === "fill" ? [["tier", "Each tier's own"]] : [["", "—"]])));
    const spine = def.colours.includes("spine") ? el("label", {className: "wz-pcol"}, el("span", {className: "hint", textContent: "spine"}),
      ...[0, 1, 2, 3].map(i => colourSel((v.spine || [])[i] || "", `${label}: spine block ${i + 1}`, val => {
        const list = [...(v.spine || [])];
        if (val) list[i] = val; else list.splice(i, 1);
        skinPatch({parts: {[p]: {spine: list.filter(Boolean).length ? list.filter(Boolean) : ["b"]}}});
      }, [["", "—"]]))) : null;
    return el("div", {className: "wz-part"}, el("b", {textContent: label}), shapes, el("div", {className: "wz-pcols"}, ...cols, spine));
  }));
}
function drawClassicParts() {
  const {el} = C, s = sc(), fr = s.frame, dk = s.deck;
  if (parts.parts.contains(document.activeElement) && document.activeElement.type === "color") return;
  const fcol = el("input", {type: "color", value: fr.colour, ariaLabel: "Frame colour"});
  fcol.addEventListener("change", () => patch({frame: {style: fr.style, colour: fcol.value}}));
  const shown = dk.style === "frame" ? fr.style : dk.style;
  const dcol = el("input", {type: "color", value: dk.colour || {wood: "#6e4426", metal: "#5d6470", neon: "#2b2470", glass: "#5a6f96"}[shown], ariaLabel: "Deck colour"});
  dcol.addEventListener("change", () => patch({deck: {style: dk.style, colour: dcol.value}}));
  fill(parts.parts, 
    el("div", {className: "wz-sec"}, el("h4", {textContent: "Reel frame"}),
      el("span", {className: "seg", role: "group", ariaLabel: "Frame style"}, ...s.frame_styles.map(st =>
        el("button", {type: "button", textContent: st[0].toUpperCase() + st.slice(1), ariaPressed: String(fr.style === st),
          onclick: () => patch({frame: {style: st, colour: fr.colour}})}))),
      el("label", {className: "controls"}, el("span", {className: "hint", textContent: "Edge colour"}), fcol),
      el("p", {className: "hint", textContent: "Wood is Armadillo's. The frame's style also dresses the side panels and the pop-ups."})),
    el("div", {className: "wz-sec"}, el("h4", {textContent: "Deck"}),
      el("span", {className: "seg", role: "group", ariaLabel: "Deck style"}, ...s.deck_styles.map(st =>
        el("button", {type: "button", textContent: st === "frame" ? "Match frame" : st[0].toUpperCase() + st.slice(1),
          ariaPressed: String(dk.style === st), onclick: () => patch({deck: {style: st, colour: dk.colour}})}))),
      el("div", {className: "controls"}, el("span", {className: "hint", textContent: "Colour"}), dcol,
        el("button", {type: "button", textContent: "Style's own", disabled: !dk.colour, title: "Drop the tint: the style's own colours",
          onclick: () => patch({deck: {style: dk.style, colour: null}})})),
      el("p", {className: "hint", textContent: "The bottom bar, its readouts and every button, plus the boxes inside the side panels."})));
}

// ------------------------------------------------------------------ Decor: Claude's free shapes
const KIND = {elbow: "Elbow", bar: "Bar", pill: "Pill", text: "Text", readout: "Readout"};
function drawDecor() {
  const {el} = C, sk = skin(), list = sk.decor || [];
  const save = (i, ch) => skinPatch({decor: list.map((d, k) => k === i ? {...d, ...ch} : d)});
  const json = el("textarea", {rows: 8, value: JSON.stringify(list, null, 1), ariaLabel: "The decor as JSON", spellcheck: false, className: "wz-json"});
  fill(parts.decor, 
    el("p", {className: "hint", textContent: list.length ? "Shapes laid round the screen's parts (never over the reels or controls). Hide any, change a colour or the words." :
      lcars() ? "None yet: Claude adds these when designing a scene (elbows, bars, readouts, lettering)." : "Decor is drawn on LCARS scenes."}),
    ...list.map((d, i) => {
      const show = el("input", {type: "checkbox", checked: d.show !== false, ariaLabel: `Show ${d.id}`});
      show.addEventListener("change", () => save(i, {show: show.checked}));
      const words = "text" in d ? el("input", {value: d.text, ariaLabel: `${d.id}: words`, title: "{stardate}, {date}, {time} and {name} fill themselves in"}) : null;
      if (words) words.addEventListener("change", () => save(i, {text: words.value}));
      return el("div", {className: "wz-decor"}, show, el("span", {textContent: `${KIND[d.kind] || d.kind} · ${d.id}`, className: d.show === false ? "hint" : ""}),
        colourSel(d.colour, `${d.id}: colour`, v => save(i, {colour: v})), words || el("span"));
    }),
    lcars() ? el("details", {className: "wz-fold"}, el("summary", {textContent: "Edit as JSON (every setting: docs/slots/scenes.md)"}), json,
      el("div", {className: "controls"}, el("button", {type: "button", textContent: "Save the decor", onclick: () => {
        let v;
        try { v = JSON.parse(json.value); } catch (e) { return C.status("That isn't JSON: " + e.message, "warn"); }
        skinPatch({decor: v}, "Decor saved.");
      }}))) : null);
}

// A background or logo with its ✕ (into the Bin), and the pane's Bin: binned pictures, each restorable. Nothing is deleted.
function take(p, chosen, pick, cls) {
  const {el} = C, name = p.split("/")[1];
  return el("span", {className: "dz-take"},
    el("button", {type: "button", ariaPressed: String(chosen), title: name, onclick: pick}, el("img", {src: C.img(p), alt: p, className: cls, loading: "lazy"})),
    el("button", {type: "button", className: "x", textContent: "✕", title: "Move to the Bin", ariaLabel: `Bin ${name}`,
      onclick: () => scenePost("bin", p, `${name} is in the Bin.`)}));
}
function bin(kind, cls) {
  const {el} = C, paths = C.data.scene.bin[kind];
  if (!paths.length) return [];
  const toggle = el("button", {type: "button", textContent: `Bin (${paths.length})`, ariaPressed: String(binOpen[kind]),
    onclick: () => { binOpen[kind] = !binOpen[kind]; kind === "logos" ? refreshLogoStrip() : drawBg(); }});
  return [el("div", {className: "controls"}, toggle), binOpen[kind] ? el("div", {className: "dz-panel"},
    el("p", {className: "hint", textContent: "Binned. Nothing is deleted: restore any of them."}),
    el("div", {className: "dz-strip"}, ...paths.map(p => el("span", {className: "dz-take"},
      el("img", {src: C.img(p), alt: p, title: p.split("/")[1], className: cls, loading: "lazy"}),
      el("button", {type: "button", textContent: "Restore", onclick: () => scenePost("restore", p, `${p.split("/")[1]} restored.`)}))))) : null];
}
async function scenePost(action, path, msg) {
  try { await C.api("POST", `/api/slot-design/${C.did}/scene/${action}`, {path}); await C.refresh(); C.status(msg, "ok"); }
  catch (e) { C.status(e.message, "warn"); }
}

const boardImages = () => [
  ...C.data.symbols.filter(s => s.file).map(s => [`${s.name}: chosen art`, s.file]),
  ...C.data.symbols.flatMap(s => s.refs.map((r, k) => [`${s.name}: reference ${k + 1}`, r])),
  ...C.data.sources.map(p => [`Sheet: ${p.split("/")[1]}`, p])];

// ------------------------------------------------------------------ background
function drawBg() {
  const {el} = C, s = sc();
  // Don't redraw under a description being typed or a picker being used (a pressed button is fine to redraw).
  const a = document.activeElement;
  bgBehind = parts.bg.contains(a) && a.matches("textarea, select");
  if (bgBehind) return;
  const jobs = (C.data.scene_jobs || []).filter(j => j.out === "background");
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
  fill(parts.bg, 
    el("div", {className: "dz-strip"},
      el("button", {type: "button", ariaPressed: String(!s.background), title: lcars() ? "No picture: deep space" : "No picture: the drawn dusk", onclick: () => patch({background: null})},
        el("span", {className: "wz-none", textContent: "None"})),
      ...s.backgrounds.map(p => take(p, s.background === p, () => patch({background: p}, "Background chosen."), "wide"))),
    ...bin("backgrounds", "wide"),
    ...jobs.map(j => el("p", {className: "hint", textContent: `Background: ${{queued: "queued", waiting: "waiting for the image model", running: `making ${j.done + 1} of ${j.count}`, failed: "failed: " + j.error}[j.status]}`})),
    el("label", {className: "field"}, el("span", {textContent: "Generate (three takes, about two minutes each)"}), desc),
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Generate", onclick: async () => {
      try { await C.api("POST", `/api/slot-design/${C.did}/scene/backgrounds`, {description: desc.value}); desc.value = ""; C.status("Background queued: the takes appear here as the image model finishes them.", "ok"); await C.refresh(); }
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
  const {el} = C, s = sc();
  const jobs = (C.data.scene_jobs || []).filter(j => j.out === "logo");
  return el("div", {className: "wz-logos"},
    el("div", {className: "dz-strip"}, ...s.logos.map(p => take(p, s.logo.file === p, () => patch({logo_file: p}), "wide contain"))),
    ...jobs.map(j => el("p", {className: "hint", textContent: `Logo: ${{queued: "queued", waiting: "waiting for the image model", running: `making ${j.done + 1} of ${j.count}`, failed: "failed: " + j.error}[j.status]}`})),
    ...bin("logos", "wide contain"));
}
function drawLogo() {
  const {el} = C, s = sc(), lg = s.logo || {};
  const lines = [0, 1, 2].map(i => el("input", {value: (lg.lines || [C.data.name.toUpperCase()])[i] || "", placeholder: i ? "optional" : "e.g. STAR TREK", ariaLabel: `Line ${i + 1}`}));
  const font = el("select", {ariaLabel: "Font"}, ...s.fonts.map(f => el("option", {value: f, textContent: f.replace(/\.(ttf|otf)$/i, "")})));
  font.value = lg.font || s.lettering_font;
  const colour = (label, v) => el("input", {type: "color", value: v, ariaLabel: label, title: label});
  const top = colour("Top colour", lg.top || "#fff1b0"), bottom = colour("Bottom colour", lg.bottom || "#d39a26"), outline = colour("Outline", lg.outline || "#2b1004");
  const emblem = el("select", {ariaLabel: "Emblem"}, el("option", {value: "", textContent: "No emblem"}), ...boardImages().map(([l, p]) => el("option", {value: p, textContent: l})));
  emblem.value = lg.emblem || "";
  const style = el("textarea", {rows: 2, ariaLabel: "How the image model should style it", value: lg.style || "",
    placeholder: lcars() ? "e.g. glowing light-blue LCARS lettering on frosted glass, a thin starship outline behind" : "e.g. carved gold western lettering with a rope border"});
  const queue = async (how) => {
    try {
      await C.api("POST", `/api/slot-design/${C.did}/scene/logo/generate`, {how, lines: lines.map(i => i.value), font: font.value, style: style.value});
      await doing();
      C.status("Logo queued: three takes, in the strip below as the image model finishes them.", "ok");
    } catch (e) { C.status(e.message, "warn"); }
  };
  fill(parts.logo, 
    el("p", {className: "hint", textContent: "The words, then how to make them: rendered in the font, the image model styling the rendered lettering " +
      "(the letters keep the font's shapes), or the image model drawing it all (it can spell now; the font is only a hint)."}),
    ...lines,
    el("div", {className: "grid2"}, el("label", {className: "field"}, el("span", {textContent: "Font"}), font),
      el("label", {className: "field"}, el("span", {textContent: "Emblem (rendered logos)"}), emblem)),
    el("div", {className: "controls"}, el("span", {className: "hint", textContent: "Colours"}), top, bottom, outline,
      el("button", {type: "button", className: "primary", textContent: "Render", onclick: async () => {
        try {
          await C.api("POST", `/api/slot-design/${C.did}/scene/logo`, {lines: lines.map(i => i.value), font: font.value,
            top: top.value, bottom: bottom.value, outline: outline.value, emblem: emblem.value || null});
          await doing();
          C.status("Logo rendered.", "ok");
        } catch (e) { C.status(e.message, "warn"); }
      }})),
    el("label", {className: "field"}, el("span", {textContent: "Style for the image model"}), style),
    el("div", {className: "controls"},
      el("button", {type: "button", textContent: "Style the lettering", title: "The words rendered in the font, then restyled by the image model: three takes",
        onclick: () => queue("stylise")}),
      el("button", {type: "button", textContent: "Generate", title: "The image model draws the whole logo, words and all: three takes",
        onclick: () => queue("generate")})),
    logoStrip());
}
