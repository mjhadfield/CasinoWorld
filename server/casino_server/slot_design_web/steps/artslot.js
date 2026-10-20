// An art slot: a picture the game draws outside the reels (the mascot, the Instant Win prize, the bonus launcher,
// the trail's spaces). Follow a symbol (its chosen take, whatever that becomes), pick any image on the board, or
// make a new one: it's added to the Bonus screens category and generated straight away.
export const STAND_IN = key => `/slot-art/armadillo/flux2/${key}.png`;
export const SHORT = {armadillo: "Mascot", barrel: "Instant Win prize", cylinder: "Bonus launcher", t_coin: "Trail coins",
  t_gold: "Trail prizepot", t_snake: "Trail hazard", t_heart: "Trail heart", t_forward: "Trail forward", t_lightning: "Trail lightning",
  t_crate: "Trail coin crate", t_upgrade: "Trail moves doubled", t_double: "Trail coins doubled",
  b_hero: "Battle: your ship", b_enemy: "Battle: enemy ship", b_boss: "Battle: boss",
  v_ship: "Voyage: your ship", v_treasure: "Voyage: Treasure Island", v_wreck: "Voyage: Shipwreck", v_skull: "Voyage: Skull Island",
  v_port: "Voyage: Port Royal", v_cove: "Voyage: Hidden Cove", v_final: "Voyage: final island", v_chest: "Voyage: the treasure",
  v_relic: "Voyage: relic", v_key: "Voyage: key", v_art1: "Voyage: artefact 1", v_art2: "Voyage: artefact 2", v_art3: "Voyage: artefact 3",
  v_art4: "Voyage: artefact 4"};

// Hand tweaks on top of the picture: the server bakes them in (adj/), so the mockup and the built game draw the
// tweaked picture. The preview here is the same transform in CSS, live while the sliders move.
export const ADJUST = {scale: 1, dx: 0, dy: 0, rot: 0, mirror: false, flip: false, bright: 1, sat: 1};
const pct = x => Math.round(x * 100) + "%", signed = x => (x > 0 ? "+" : "") + x;
const SLIDERS = [["scale", "Size", 0.3, 2, 0.01, pct], ["dx", "Left / right", -50, 50, 0.5, x => signed(x) + "%"],
  ["dy", "Up / down", -50, 50, 0.5, x => signed(x) + "%"], ["rot", "Rotate", -180, 180, 1, x => signed(x) + "°"],
  ["bright", "Brightness", 0.4, 1.6, 0.01, pct], ["sat", "Colour", 0, 2, 0.01, pct]];
const drafts = new Map();      // art slot -> adjustments being made, not saved yet (kept across redraws)
const adjusting = new Map();   // art slot -> Adjust panel opened (true) or closed (false) by hand
const same = (a, b) => Object.keys(ADJUST).every(k => a[k] === b[k]);
export const adjusted = a => !same({...ADJUST, ...a}, ADJUST);
function look(img, a) {
  const sx = a.mirror ? -a.scale : a.scale, sy = a.flip ? -a.scale : a.scale;
  img.style.transform = `translate(${a.dx}%, ${a.dy}%) rotate(${a.rot}deg) scale(${sx}, ${sy})`;
  img.style.filter = a.bright === 1 && a.sat === 1 ? "" : `brightness(${a.bright}) saturate(${a.sat})`;
}

// `open`: show the Adjust panel from the start (the Bonus games step's picture editor).
export function artSlot(C, key, {open = false} = {}) {
  const {el} = C, a = C.data.art[key];
  const sel = el("select", {ariaLabel: a.label},
    el("option", {value: "", textContent: "Armadillo's (stand-in)"}),
    el("optgroup", {label: "Follow a symbol's chosen take"}, ...C.data.symbols.map(s => el("option", {value: "sym:" + s.id, textContent: s.name}))),
    el("optgroup", {label: "An image on the board"},
      ...C.data.symbols.flatMap(s => s.refs.map((r, k) => el("option", {value: r, textContent: `${s.name}: reference ${k + 1}`}))),
      ...C.data.sources.map(p => el("option", {value: p, textContent: `Sheet: ${p.split("/")[1]}`}))));
  sel.value = a.value || "";
  sel.addEventListener("change", () => set(C, key, {value: sel.value || null}));
  const desc = el("input", {placeholder: "Describe it, e.g. 'a glowing photon torpedo'", ariaLabel: `Describe ${a.label}`});
  const make = el("div", {className: "controls", hidden: true}, desc, el("button", {type: "button", className: "primary", textContent: "Make it", onclick: async () => {
    if (!desc.value.trim()) return C.status("Describe it first.", "warn");
    const cat = C.data.categories.find(c => c.role == null) || C.data.categories[C.data.categories.length - 1];
    try {
      const {id} = await C.api("POST", `/api/slot-design/${C.did}/symbols`, {name: SHORT[key] || key, category: cat.id, kind: "object", prompt: desc.value});
      await C.api("PUT", `/api/slot-design/${C.did}/art-slots/${key}`, {value: "sym:" + id});
      await C.api("POST", `/api/slot-design/${C.did}/generate`);
      C.status(`Making three takes on the Art board (${cat.title}); this slot follows the chosen one.`, "ok");
      await C.refresh();
    } catch (e) { C.status(e.message, "warn"); }
  }}));
  // the preview: the picture as chosen, with the adjustments drawn over it (a stand-in can't be adjusted)
  const img = el("img", {src: a.src ? C.img(a.src) : STAND_IN(key), alt: "", className: a.src ? "" : "standin"});
  const frame = el("div", {className: "wz-adj-frame", title: "The picture's box: anything moved past its edge is cut off"}, img);
  img.addEventListener("load", () => { frame.style.aspectRatio = `${img.naturalWidth} / ${img.naturalHeight}`; });
  const isOpen = () => !!a.src && (adjusting.get(key) ?? open);
  const toggle = el("button", {type: "button", textContent: "Adjust", ariaPressed: String(isOpen()), disabled: !a.src,
    title: a.src ? "Size, position, rotation, mirror and colour" : "Choose a picture first: Armadillo's stand-ins can't be adjusted",
    onclick: () => { adjusting.set(key, !isOpen()); swap(); }});
  const side = el("div", {className: "pane"},
    el("div", {className: "controls"}, el("b", {textContent: a.label}), adjusted(a.adjust) ? el("span", {className: "tag gold", textContent: "adjusted"}) : null),
    sel, el("div", {className: "controls"}, el("button", {type: "button", textContent: "＋ Make one", onclick: () => { make.hidden = !make.hidden; }}), toggle), make);
  const box = el("div", {className: "wz-slot edit"}, frame, side);
  let panel = null;
  const swap = () => {
    const on = isOpen();
    toggle.ariaPressed = String(on);
    if (panel) panel.remove();
    panel = on ? adjustPanel(C, key, img) : null;
    if (panel) side.append(panel);
    else look(img, a.src ? a.adjust : ADJUST);
  };
  swap();
  return box;
}

function adjustPanel(C, key, img) {
  const {el} = C, saved = {...ADJUST, ...C.data.art[key].adjust};
  const f = {...saved, ...drafts.get(key)};
  const outs = {}, ranges = {}, flags = {};
  const changed = () => {
    if (same(f, saved)) drafts.delete(key); else drafts.set(key, {...f});
    look(img, f);
    for (const [k, , , , , show] of SLIDERS) { ranges[k].value = f[k]; outs[k].textContent = show(f[k]); }
    for (const k of ["mirror", "flip"]) flags[k].ariaPressed = String(f[k]);
    saveBtn.disabled = undo.disabled = same(f, saved);
    reset.disabled = same(f, ADJUST);
  };
  const sliders = SLIDERS.map(([k, label, min, max, step, show]) => {
    outs[k] = el("output", {textContent: show(f[k])});
    ranges[k] = el("input", {type: "range", min, max, step, value: f[k], ariaLabel: label, title: "Double-click to put it back"});
    ranges[k].addEventListener("input", () => { f[k] = +ranges[k].value; changed(); });
    ranges[k].addEventListener("dblclick", () => { f[k] = ADJUST[k]; changed(); });
    return el("label", {className: "dz-slider"}, el("span", {textContent: label}), ranges[k], outs[k]);
  });
  const flag = (k, text, title) => (flags[k] = el("button", {type: "button", textContent: text, title, ariaPressed: String(f[k]),
    onclick: () => { f[k] = !f[k]; changed(); }}));
  const turn = by => () => { const r = f.rot + by; f.rot = r > 180 ? r - 360 : r < -180 ? r + 360 : r; changed(); };
  const saveBtn = el("button", {type: "button", className: "primary", textContent: "Save", onclick: () => {
    drafts.delete(key);
    set(C, key, {adjust: same(f, ADJUST) ? null : f}, "Adjustments saved: the mockup and the built game use them.");
  }});
  const undo = el("button", {type: "button", textContent: "Undo changes", title: "Back to what's saved",
    onclick: () => { Object.assign(f, saved); changed(); }});
  const reset = el("button", {type: "button", textContent: "Reset", title: "The picture as it comes, no adjustments (Save to keep it)",
    onclick: () => { Object.assign(f, ADJUST); changed(); }});
  const panel = el("div", {className: "wz-adj"}, ...sliders,
    el("div", {className: "controls"}, flag("mirror", "⇆ Mirror", "Flip left to right (face the other way)"),
      flag("flip", "⇅ Flip", "Turn upside down"),
      el("button", {type: "button", textContent: "↺ 90°", onclick: turn(-90)}), el("button", {type: "button", textContent: "↻ 90°", onclick: turn(90)})),
    el("div", {className: "controls"}, saveBtn, undo, reset));
  changed();
  return panel;
}

async function set(C, key, body, msg) {
  try {
    await C.api("PUT", `/api/slot-design/${C.did}/art-slots/${key}`, body);
    await C.refresh();
    if (msg) C.status(msg, "ok");
  } catch (e) { C.status(e.message, "warn"); }
}

// Is someone typing in this part of the page? (Polling and saves redraw a step, but never under the caret.)
export function typing(root) {
  const a = document.activeElement;
  return !!a && root.contains(a) && (a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && !["checkbox", "radio", "button", "color", "file", "range"].includes(a.type)));
}

// A value table as text ("1:40, 2:30") and back.
export const tableText = t => t.map(([v, w]) => `${v}:${w}`).join(", ");
export function parseTable(text) {
  return text.split(/[,;\n]+/).map(x => x.trim()).filter(Boolean).map(x => x.split(/[:×x*]/).map(n => +n.trim()));
}

// New feature or bonus ideas: described here, built later (Build turns them into code tasks).
export function specs(C, kind) {
  const {el} = C, list = (kind === "feature" ? C.data.features : C.data.bonuses).specs;
  const name = el("input", {placeholder: kind === "feature" ? "e.g. Red Alert" : "e.g. Away Team pick", ariaLabel: "Name"});
  const desc = el("textarea", {rows: 3, ariaLabel: "How it plays", placeholder: "How it plays: what triggers it, what happens, what it can pay"});
  const timing = el("select", {ariaLabel: "When"}, ...(kind === "feature"
    ? ["before the reels stop", "after the reels stop"] : ["from scatters", "from a random trigger", "bought"]).map(t => el("option", {value: t, textContent: t})));
  const art = el("input", {placeholder: "Pictures it needs (optional)", ariaLabel: "Pictures it needs"});
  return el("div", {className: "card"}, el("h3", {textContent: kind === "feature" ? "New feature ideas" : "New bonus ideas"}),
    el("p", {className: "hint", textContent: "Anything not in the library needs building (engine, mockup and game). Describe it here; the Build step turns it into a task, and once built it joins the library for every slot."}),
    ...list.map(x => el("div", {className: "wz-spec"}, el("b", {textContent: x.name}), el("span", {className: "tag gold", textContent: "spec · to build"}),
      el("span", {className: "hint", textContent: x.timing}), el("p", {textContent: x.description}),
      el("button", {type: "button", textContent: "Remove", onclick: async () => {
        try { await C.api("DELETE", `/api/slot-design/${C.did}/specs/${x.id}`); await C.refresh(); } catch (e) { C.status(e.message, "warn"); }
      }}))),
    el("div", {className: "grid2"}, el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
      el("label", {className: "field"}, el("span", {textContent: "When"}), timing),
      el("label", {className: "field", style: "grid-column: 1 / -1"}, el("span", {textContent: "How it plays"}), desc),
      el("label", {className: "field", style: "grid-column: 1 / -1"}, el("span", {textContent: "Pictures"}), art)),
    el("div", {className: "controls"}, el("button", {type: "button", textContent: "Add the idea", onclick: async () => {
      try {
        await C.api("POST", `/api/slot-design/${C.did}/specs`, {kind, name: name.value, description: desc.value, timing: timing.value, art: art.value});
        C.status("Idea saved for building.", "ok");
        await C.refresh();
      } catch (e) { C.status(e.message, "warn"); }
    }})));
}
