// The Floor tab: the slot banks on the casino floor (slot_banks.py). The floor map shows the room, its tables and
// every bank; drag a bank to move it. The bank editor is the picked bank close up, on a grid of half a cabinet:
// click the grid to put down a cabinet of the picked slot, drag cabinets about, turn them, re-slot them. Save keeps
// the banks (the server checks them as this page does); Apply restarts the casino to put them on the floor.
let $, el, api, status;
let R = null;              // the rules: floor map and a cabinet's shapes (GET /api/slot-banks)
let slots = [];            // the slots a cabinet can be
let banks = [];            // the banks being edited
let saved = "";            // the banks as last saved (JSON), to know when there's something to save
let pending = 0, live = false, skipped = [];
let bi = -1;               // the picked bank
let sel = new Set();       // the picked bank's selected cabinets
let pick = null;           // the slot new cabinets are
let facing = "down";       // ...and the way they face
let root = null;

const GRID = [17, 13];     // half a cabinet across and down
const TURN = {down: "left", left: "up", up: "right", right: "down"};   // a quarter turn, clockwise
const ARMADILLO_LOOK = {body: "#4a2c18", trim: "#d9a54a"};
const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}, ...kids) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) e.setAttribute(k, v);
  e.append(...kids.filter(k => k !== null && k !== undefined));
  return e;
};

export function init(ctx) { ({$, el, api, status} = ctx); }

export async function load() {
  root = $("#floor-app");
  try { take(await api("GET", "/api/slot-banks")); }
  catch (e) { status("Couldn't load the slot banks: " + e.message, "warn"); return; }
  status(`${banks.length} slot bank${banks.length === 1 ? "" : "s"} on the floor` + (pending ? ` (${pending} saved changes not applied)` : "."), pending ? "warn" : "ok");
  addEventListener("beforeunload", e => { if (dirty()) e.preventDefault(); });
  document.addEventListener("keydown", onKey);
  draw();
}

function take(view) {
  R = view.rules; slots = view.slots; pending = view.pending; live = view.live; skipped = view.skipped;
  banks = structuredClone(view.banks); saved = JSON.stringify(banks);
  if (!slots.some(s => s.id === pick)) pick = slots[0] ? slots[0].id : null;
  if (bi >= banks.length) bi = banks.length - 1;
  if (bi < 0 && banks.length) bi = 0;
  sel = new Set();
}

const dirty = () => JSON.stringify(banks) !== saved;
const slot = id => slots.find(s => s.id === id) || {id, name: id, cabinet: {}};
const look = id => ({...ARMADILLO_LOOK, ...(slot(id).cabinet || {})});
const short = id => slot(id).name.split(/\s+/).map(w => w[0]).join("").slice(0, 3).toUpperCase();

// ---------------------------------------------------------------- the checks (slot_banks.check, the same rules)
const at = (r, x, y) => [r[0] + x, r[1] + y, r[2], r[3]];
const overlap = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
const inside = (p, r) => r[0] <= p[0] && p[0] <= r[0] + r[2] && r[1] <= p[1] && p[1] <= r[1] + r[3];
const grow = (r, by) => [r[0] - by, r[1] - by, r[2] + 2 * by, r[3] + 2 * by];

function shapes(b, c) {
  const x = b.x + c.dx, y = b.y + c.dy, f = c.facing;
  return {body: at(R.body[f], x, y), art: at(R.art[f], x, y), stool: at(R.stool[f], x, y), stand: [x + R.stand[f][0], y + R.stand[f][1]]};
}

function check() {
  const walk = R.floor.walkable, every = [];
  for (const b of banks) for (const c of b.cabinets) every.push([b, c, shapes(b, c)]);
  const out = new Map();   // cabinet -> message
  for (const [b, c, s] of every) {
    let bad = null;
    const corners = r => [[r[0], r[1]], [r[0] + r[2], r[1] + r[3]]];
    if (![...corners(s.body), ...corners(s.stool), s.stand].every(p => inside(p, walk))) bad = "is off the floor";
    for (const t of bad ? [] : R.floor.tables)
      if (["body", "art", "stool"].some(k => overlap(s[k], t.rect)) || inside(s.stand, t.rect)) { bad = `is in ${t.name}'s way`; break; }
    for (const [name, p] of bad ? [] : Object.entries(R.floor.points))
      if (["body", "stool"].some(k => inside(p, grow(s[k], R.point_clear)))) { bad = "stands on " + (name === "entrance" ? "the entrance" : "an aisle NPCs walk to"); break; }
    for (const [b2, c2, s2] of bad ? [] : every) {
      if (c2 === c) continue;
      if (overlap(s.body, s2.body) || overlap(s.stool, s2.body) || overlap(s.stool, s2.stool)) { bad = "overlaps another cabinet" + (b2 === b ? "" : ` (${b2.name})`); break; }
      if (inside(s.stand, s2.body)) { bad = "can't be reached: another cabinet stands where its player would"; break; }
    }
    if (bad) out.set(c, `${b.name}: a cabinet at ${Math.round(b.x + c.dx)}, ${Math.round(b.y + c.dy)} ${bad}.`);
  }
  return out;
}

// ---------------------------------------------------------------- drawing
function draw() {
  const problems = check();
  const bank = banks[bi];
  root.replaceChildren(
    topBar(problems),
    el("div", {className: "fl-cols"},
      el("div", {className: "pane"}, el("h2", {}, el("span", {textContent: "The floor"}),
          el("span", {className: "hint", textContent: "Drag a bank to move it (Shift: by the pixel)"})),
        el("div", {className: "card fl-mapcard"}, floorMap(problems))),
      el("div", {className: "pane"}, el("h2", {}, el("span", {textContent: "Bank"}), bankPicker()),
        bank ? bankCard(bank, problems) : el("div", {className: "card"}, el("p", {className: "hint", textContent: "No banks yet: make one with New bank."})))),
    problems.size ? el("div", {className: "card fl-problems"}, el("h3", {textContent: "Not clear yet"}),
      el("ul", {}, ...[...new Set(problems.values())].map(m => el("li", {textContent: m})))) : null);
}

function topBar(problems) {
  const save = el("button", {type: "button", className: "primary", textContent: "Save", disabled: !dirty() || problems.size > 0, onclick: async () => {
    save.disabled = true;
    try { take(await api("PUT", "/api/slot-banks", {banks})); status("Saved. " + (pending ? "Apply puts it on the floor." : ""), "ok"); }
    catch (e) { status(e.message, "warn"); }
    draw();
  }});
  const revert = el("button", {type: "button", textContent: "Undo changes", disabled: !dirty(), onclick: () => { banks = JSON.parse(saved); sel = new Set(); bi = Math.min(bi, banks.length - 1); draw(); }});
  const apply = el("button", {type: "button", className: "primary", textContent: "Apply: restart the casino", disabled: dirty() || !pending, onclick: async () => {
    if (!confirm("Restart the casino now? Anyone playing is stood up for a few seconds while it comes back.")) return;
    try { const r = await api("POST", "/api/slot-banks/apply"); status(r.message, "ok"); }
    catch (e) { status(e.message, "warn"); }
  }});
  const words = dirty() ? (problems.size ? "Unsaved changes: move the red cabinets clear to save." : "Unsaved changes.")
    : pending ? `${pending} cabinet${pending === 1 ? "" : "s"} saved but not on the floor yet.` : "The floor has these banks.";
  return el("div", {className: "card fl-bar"},
    el("span", {className: "tag " + (dirty() || pending ? "warn" : "ok"), textContent: dirty() ? "Unsaved" : pending ? "Not applied" : "On the floor"}),
    el("span", {textContent: words}),
    skipped.length ? el("span", {className: "tag warn", textContent: `${skipped.length} cabinet${skipped.length === 1 ? "" : "s"} left off (their slot isn't loaded)`}) : null,
    el("span", {className: "fl-grow"}), revert, save,
    live ? apply : el("span", {className: "hint", textContent: "Dev or test instance: restart it (tools/dev.sh server) to apply."}));
}

function cabinetShape(b, c, problems, big) {
  const x = b.x + c.dx, y = b.y + c.dy, lk = look(c.variant), f = c.facing;
  const body = at(R.body[f], x, y), stool = at(R.stool[f], x, y);
  const bad = problems.has(c), picked = big && sel.has(c);
  // the screen's side of the body, where its player sits
  const edge = {down: [body[0], body[1] + body[3] - 2, body[2], 2], up: [body[0], body[1], body[2], 2],
                left: [body[0], body[1], 2, body[3]], right: [body[0] + body[2] - 2, body[1], 2, body[3]]}[f];
  const g = svg("g", {"data-cab": b.cabinets.indexOf(c), "data-bank": banks.indexOf(b), class: "fl-cab" + (bad ? " bad" : "") + (picked ? " picked" : "")},
    big ? svg("rect", {x: R.art[f][0] + x, y: R.art[f][1] + y, width: R.art[f][2], height: R.art[f][3], class: "fl-art"}) : null,
    svg("ellipse", {cx: stool[0] + stool[2] / 2, cy: stool[1] + stool[3] / 2, rx: stool[2] / 2, ry: stool[3] / 2, class: "fl-stool"}),
    svg("rect", {x: body[0], y: body[1], width: body[2], height: body[3], rx: 1.5, fill: lk.body, stroke: lk.trim, "stroke-width": big ? 1.2 : 1.5}),
    svg("rect", {x: edge[0], y: edge[1], width: edge[2], height: edge[3], fill: lk.trim}),
    big ? svg("circle", {cx: x + R.stand[f][0], cy: y + R.stand[f][1], r: 1.6, class: "fl-stand"}) : null,
    big ? svg("text", {x: body[0] + body[2] / 2, y: body[1] + body[3] / 2 + 2, class: "fl-label", fill: lk.title || lk.trim}, short(c.variant)) : null,
    svg("title", {}, `${slot(c.variant).name}, facing ${f}` + (bad ? `: ${problems.get(c)}` : "")));
  return g;
}

function floorMap(problems) {
  const [W, H] = R.floor.room, wk = R.floor.walkable;
  const s = svg("svg", {viewBox: `0 0 ${W} ${H}`, class: "fl-map", role: "img", "aria-label": "The casino floor"},
    svg("rect", {x: 0, y: 0, width: W, height: H, class: "fl-room"}),
    svg("rect", {x: wk[0], y: wk[1], width: wk[2], height: wk[3], class: "fl-walk"}),
    ...R.floor.tables.map(t => svg("g", {},
      svg("rect", {x: t.rect[0], y: t.rect[1], width: t.rect[2], height: t.rect[3], rx: 18, class: "fl-table"}),
      svg("text", {x: t.x, y: t.y - 30, class: "fl-tname"}, t.name))),
    ...Object.entries(R.floor.points).map(([n, p]) => svg("g", {class: "fl-point"},
      svg("circle", {cx: p[0], cy: p[1], r: 9}), svg("text", {x: p[0], y: p[1] - 14}, n === "entrance" ? "Entrance" : n.replace("_", " ")))));
  banks.forEach((b, i) => {
    const g = svg("g", {class: "fl-bank" + (i === bi ? " on" : "")});
    const box = bounds(b);
    if (box) g.append(svg("rect", {x: box[0] - 8, y: box[1] - 8, width: box[2] + 16, height: box[3] + 16, rx: 6, class: "fl-bankbox", "data-bank": i}));
    for (const c of b.cabinets) g.append(cabinetShape(b, c, problems, false));
    g.append(svg("text", {x: b.x, y: (box ? box[1] : b.y) - 14, class: "fl-bname", "data-bank": i}, b.name));
    s.append(g);
  });
  dragging(s, (e, start) => {   // drag a bank by any of its cabinets or its frame
    const hit = e.target.closest("[data-bank]");
    if (!hit) return null;
    const i = +hit.dataset.bank;
    if (i !== bi) { bi = i; sel = new Set(); }
    const b = banks[i], from = [b.x, b.y];
    return (p, ev) => {
      const step = ev.shiftKey ? 1 : 10;
      b.x = Math.round((from[0] + p[0] - start[0]) / step) * step;
      b.y = Math.round((from[1] + p[1] - start[1]) / step) * step;
    };
  });
  return s;
}

// A bank's extent (its cabinets' bodies and art), or null when it has none.
function bounds(b) {
  if (!b.cabinets.length) return null;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const c of b.cabinets) for (const r of [shapes(b, c).body, shapes(b, c).art, shapes(b, c).stool]) {
    x0 = Math.min(x0, r[0]); y0 = Math.min(y0, r[1]); x1 = Math.max(x1, r[0] + r[2]); y1 = Math.max(y1, r[1] + r[3]);
  }
  return [x0, y0, x1 - x0, y1 - y0];
}

// Pointer dragging on an svg: begin(event, point) returns a move(point, event), or null for a plain click; the svg
// redraws as the pointer moves and the whole tab once it's let go.
function dragging(s, begin) {
  const point = e => { const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(s.getScreenCTM().inverse()); return [p.x, p.y]; };
  s.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    const start = point(e), move = begin(e, start);
    if (!move) { draw(); return; }
    e.preventDefault();
    const redraw = s.classList.contains("fl-map") ? floorMap : editor;
    const onMove = ev => {
      move(point(ev), ev);
      const fresh = redraw(check());
      s.replaceWith(fresh); s = fresh;   // keep following the pointer on the redrawn svg
    };
    const onUp = () => { removeEventListener("pointermove", onMove); removeEventListener("pointerup", onUp); draw(); };
    addEventListener("pointermove", onMove); addEventListener("pointerup", onUp);
  });
}

function bankPicker() {
  const list = el("select", {ariaLabel: "Bank", onchange: () => { bi = +list.value; sel = new Set(); draw(); }},
    ...banks.map((b, i) => el("option", {value: i, textContent: `${b.name} (${b.cabinets.length})`, selected: i === bi})));
  const shape = el("select", {ariaLabel: "New bank's shape"},
    el("option", {value: "empty", textContent: "Empty"}), el("option", {value: "row", textContent: "Row of 4"}),
    el("option", {value: "full", textContent: "Armadillo's 10"}));
  return el("span", {className: "controls"}, banks.length ? list : null, shape,
    el("button", {type: "button", textContent: "New bank", onclick: () => newBank(shape.value)}));
}

const TEMPLATES = {
  empty: [],
  row: [[-51, 0, "down"], [-17, 0, "down"], [17, 0, "down"], [51, 0, "down"]],
  full: [[-51, -13, "up"], [-17, -13, "up"], [17, -13, "up"], [51, -13, "up"], [-51, 13, "down"], [-17, 13, "down"],
         [17, 13, "down"], [51, 13, "down"], [-92, 2, "left"], [92, 2, "right"]],
};

function newBank(kind) {
  const n = banks.length + 1;
  const b = {name: `Bank ${n}`, x: 0, y: 0, cabinets: TEMPLATES[kind].map(([dx, dy, f]) => ({dx, dy, facing: f, variant: pick}))};
  banks.push(b);
  // the first clear place on the floor, scanning from the top left
  const [W, H] = R.floor.room;
  outer: for (let y = 120; y < H - 60; y += 20) for (let x = 120; x < W - 120; x += 20) {
    b.x = x; b.y = y;
    if (![...check().keys()].some(c => b.cabinets.includes(c)) && (b.cabinets.length || clearSpot(x, y))) break outer;
  }
  bi = banks.length - 1; sel = new Set();
  draw();
}

const clearSpot = (x, y) => !R.floor.tables.some(t => inside([x, y], grow(t.rect, 60)));

function bankCard(b, problems) {
  const name = el("input", {value: b.name, ariaLabel: "Bank name", maxLength: 40, oninput: () => { b.name = name.value; refreshBar(); }, onchange: draw});
  const palette = el("div", {className: "fl-palette", role: "group", ariaLabel: "Slot for new cabinets"},
    ...slots.map(s => el("button", {type: "button", ariaPressed: String(s.id === pick), title: s.loaded ? s.name : s.name + " (loads when the casino restarts)",
      onclick: () => { pick = s.id; draw(); }},
      s.logo ? el("img", {src: s.logo, alt: "", loading: "lazy"}) : el("span", {className: "fl-swatch", style: `background:${look(s.id).body};border-color:${look(s.id).trim}`}),
      el("span", {textContent: s.name + (s.loaded ? "" : " ·new")}))));
  const sideways = el("span", {className: "seg", role: "group", ariaLabel: "New cabinets face"},
    ...["down", "left", "up", "right"].map(f => el("button", {type: "button", textContent: {down: "↓", left: "←", up: "↑", right: "→"}[f],
      title: `Screen facing ${f}`, ariaPressed: String(f === facing), onclick: () => { facing = f; draw(); }})));
  const chosen = [...sel];
  const reslot = el("select", {ariaLabel: "Make the selected cabinets"}, ...slots.map(s => el("option", {value: s.id, textContent: s.name, selected: s.id === pick})));
  return el("div", {className: "card"},
    el("div", {className: "controls"}, el("label", {className: "field"}, el("span", {textContent: "Name "}), name),
      el("button", {type: "button", textContent: "Turn the bank 90°", onclick: () => turnBank(b)}),
      el("button", {type: "button", textContent: "Duplicate", onclick: () => duplicate(b)}),
      el("button", {type: "button", textContent: "Delete bank", onclick: () => {
        if (b.cabinets.length && !confirm(`Delete ${b.name} and its ${b.cabinets.length} cabinets?`)) return;
        banks.splice(bi, 1); bi = Math.min(bi, banks.length - 1); sel = new Set(); draw();
      }})),
    el("div", {className: "field"}, el("span", {className: "hint", textContent: "Click the grid to put down a"}), palette),
    el("div", {className: "controls"}, el("span", {className: "hint", textContent: "facing"}), sideways,
      el("span", {className: "hint", textContent: "Click a cabinet to select it (Shift: several), drag to move, R turns, Delete removes, arrows nudge."})),
    el("div", {className: "fl-editor"}, editor(problems)),
    el("div", {className: "controls"},
      el("span", {className: "hint", textContent: chosen.length ? `${chosen.length} selected:` : "Nothing selected."}),
      el("button", {type: "button", textContent: "Turn", disabled: !chosen.length, onclick: () => turn()}),
      el("button", {type: "button", textContent: "Remove", disabled: !chosen.length, onclick: () => remove()}),
      reslot, el("button", {type: "button", textContent: "Make these that slot", disabled: !chosen.length, onclick: () => { for (const c of chosen) c.variant = reslot.value; draw(); }}),
      el("span", {className: "fl-grow"}),
      el("span", {className: "hint", textContent: Object.entries(count(b)).map(([v, n]) => `${n} × ${slot(v).name}`).join(", ") || "No cabinets"})));
}

function refreshBar() { const bar = root.querySelector(".fl-bar"); if (bar) bar.replaceWith(topBar(check())); }

const count = b => b.cabinets.reduce((o, c) => (o[c.variant] = (o[c.variant] || 0) + 1, o), {});

function editor(problems) {
  const b = banks[bi];
  const box = bounds(b) ? [bounds(b)[0] - b.x, bounds(b)[1] - b.y, bounds(b)[2], bounds(b)[3]] : [0, 0, 0, 0];
  // the view: at least 15 by 13 grid squares round the bank's centre, and the whole bank with room round it
  const x0 = Math.min(-GRID[0] * 8, box[0] - 50), x1 = Math.max(GRID[0] * 8, box[0] + box[2] + 50);
  const y0 = Math.min(-GRID[1] * 7, box[1] - 30), y1 = Math.max(GRID[1] * 7, box[1] + box[3] + 50);
  const s = svg("svg", {viewBox: `${b.x + x0} ${b.y + y0} ${x1 - x0} ${y1 - y0}`, class: "fl-ed", role: "img", "aria-label": `${b.name}, close up`});
  const grid = svg("g", {class: "fl-grid"});
  for (let gx = Math.ceil(x0 / GRID[0]) * GRID[0]; gx <= x1; gx += GRID[0])
    grid.append(svg("line", {x1: b.x + gx, y1: b.y + y0, x2: b.x + gx, y2: b.y + y1, class: gx === 0 ? "axis" : (gx / GRID[0]) % 2 ? "half" : ""}));
  for (let gy = Math.ceil(y0 / GRID[1]) * GRID[1]; gy <= y1; gy += GRID[1])
    grid.append(svg("line", {x1: b.x + x0, y1: b.y + gy, x2: b.x + x1, y2: b.y + gy, class: gy === 0 ? "axis" : (gy / GRID[1]) % 2 ? "half" : ""}));
  s.append(svg("rect", {x: b.x + x0, y: b.y + y0, width: x1 - x0, height: y1 - y0, class: "fl-room", "data-empty": 1}), grid);
  for (const t of R.floor.tables) s.append(svg("rect", {x: t.rect[0], y: t.rect[1], width: t.rect[2], height: t.rect[3], rx: 18, class: "fl-table"}));
  for (const b2 of banks) if (b2 !== b) for (const c of b2.cabinets) s.append(cabinetShape(b2, c, problems, true));
  // cabinets sort by their base, as the game draws them
  for (const c of [...b.cabinets].sort((p, q) => p.dy - q.dy)) s.append(cabinetShape(b, c, problems, true));
  dragging(s, (e, start) => {
    const hit = e.target.closest("[data-cab]");
    if (hit && +hit.dataset.bank !== bi) return null;   // another bank's cabinet: pick that bank on the map
    if (!hit) {   // the grid: put down a cabinet of the picked slot
      if (!pick) return null;
      const snap = (v, g) => Math.round(v / g) * g;
      const c = {dx: snap(start[0] - b.x, GRID[0]), dy: snap(start[1] - b.y, GRID[1]), facing, variant: pick};
      b.cabinets.push(c); sel = new Set([c]);
      return null;   // (draw() follows the click)
    }
    const c = b.cabinets[+hit.dataset.cab];
    if (e.shiftKey) { sel.has(c) ? sel.delete(c) : sel.add(c); return () => {}; }
    if (!sel.has(c)) sel = new Set([c]);
    const from = new Map([...sel].map(k => [k, [k.dx, k.dy]]));
    return (p, ev) => {
      const ddx = p[0] - start[0], ddy = p[1] - start[1];
      const sx = ev.shiftKey ? 1 : GRID[0], sy = ev.shiftKey ? 1 : GRID[1];
      for (const [k, [dx, dy]] of from) { k.dx = Math.round((dx + ddx) / sx) * sx; k.dy = Math.round((dy + ddy) / sy) * sy; }
    };
  });
  return s;
}

function turn() { for (const c of sel) c.facing = TURN[c.facing]; draw(); }
function remove() { const b = banks[bi]; b.cabinets = b.cabinets.filter(c => !sel.has(c)); sel = new Set(); draw(); }

function turnBank(b) {   // a quarter turn clockwise about the bank's centre
  for (const c of b.cabinets) { [c.dx, c.dy] = [-c.dy, c.dx]; c.facing = TURN[c.facing]; }
  draw();
}

function duplicate(b) {
  const copy = {name: b.name + " copy", x: b.x, y: b.y + 120, cabinets: b.cabinets.map(({dx, dy, facing, variant}) => ({dx, dy, facing, variant}))};
  banks.push(copy); bi = banks.length - 1; sel = new Set(); draw();
}

function onKey(e) {
  if (!root || !root.closest("section").classList.contains("on") || !sel.size) return;
  if (e.target.closest("input, select, textarea")) return;
  const nudge = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]}[e.key];
  if (nudge) {
    for (const c of sel) { c.dx += nudge[0] * (e.shiftKey ? 1 : GRID[0]); c.dy += nudge[1] * (e.shiftKey ? 1 : GRID[1]); }
  } else if (e.key === "r" || e.key === "R") {
    for (const c of sel) c.facing = TURN[c.facing];
  } else if (e.key === "Delete" || e.key === "Backspace") {
    const b = banks[bi]; b.cabinets = b.cabinets.filter(c => !sel.has(c)); sel = new Set();
  } else if (e.key === "Escape") {
    sel = new Set();
  } else return;
  e.preventDefault();
  draw();
}
