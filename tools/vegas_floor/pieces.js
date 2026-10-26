// The Vegas floor's furniture: painted on canvas at twice the game's resolution (scale 2), with soft light,
// gradients and real material textures (ambientCG, CC0: textures/), so it reads a touch more real than the 1:1 pixel
// art while still sitting in the game's 3/4 top-down view. Its palette follows Mike's "Dark Modern" master table:
// charcoal and black marble, warm amber LED (#ffd28a), chrome, mahogany and a little gold.
//
// tools/build_vegas_floor.py loads this in headless Chromium and calls renderAll(textures, fonts).
//
// A piece: def(id, {name, cat, size: [w, h] (game pixels), anchor: [x, y] (the middle of its base; a flat piece's
// placing point), body: [x, y, w, h] about the anchor (what blocks walking; null for flat and wall pieces), facings,
// mirrors: {facing: drawn as this facing turned over}, mount: floor|flat|wall, screen, interact, draw(g, facing)}.
// draw() paints in game pixels: the canvas is already scaled by S.

const S = 2;
const TEX = {};   // name -> HTMLImageElement (marble_black, marble_white, mahogany, walnut, leather, carpet_fibre)
const LED = "#ffd28a", LED_HOT = "#fff1d2", AMBER = "#f2b25c", COPPER = "#c8794a", GOLD = "#d9b56a", RED = "#c45454";
const FONT = { sans: "Montserrat", deco: "Josefin Sans", serif: "Cinzel" };

/* ================================================================ helpers */
function rgba(h, a) { const n = parseInt(h.slice(1), 16); return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; }
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function lin(g, x0, y0, x1, y1, stops) { const l = g.createLinearGradient(x0, y0, x1, y1); for (const [o, c] of stops) l.addColorStop(o, c); return l; }
function rr(g, x, y, w, h, r) { g.beginPath(); g.roundRect(x, y, w, h, r); }
function ell(g, cx, cy, rx, ry) { g.beginPath(); g.ellipse(cx, cy, Math.max(.01, rx), Math.max(.01, ry), 0, 0, Math.PI * 2); }
function fillRR(g, x, y, w, h, r, style) { rr(g, x, y, w, h, r); g.fillStyle = style; g.fill(); }
function fillEll(g, cx, cy, rx, ry, style) { ell(g, cx, cy, rx, ry); g.fillStyle = style; g.fill(); }
// a soft pool of light (or dark): an ellipse fading out from its middle
function pool(g, cx, cy, rx, ry, col, a, mid = 0) {
  g.save(); g.translate(cx, cy); g.scale(1, ry / rx);
  const r = g.createRadialGradient(0, 0, 0, 0, 0, rx);
  r.addColorStop(0, rgba(col, a)); if (mid) r.addColorStop(mid, rgba(col, a * .6)); r.addColorStop(1, rgba(col, 0));
  g.fillStyle = r; g.beginPath(); g.arc(0, 0, rx, 0, Math.PI * 2); g.fill(); g.restore();
}
function shade(g, cx, cy, rx, ry, a = .5) { pool(g, cx, cy, rx, ry, "#000000", a, .45); }
// a texture as a fill: k is how many game pixels one texture pixel covers (the textures are 512 square)
function tex(g, name, k = .25, rot = 0, ox = 0, oy = 0) {
  const p = g.createPattern(TEX[name], "repeat");
  p.setTransform(new DOMMatrix().translate(ox, oy).rotate(rot).scale(k));
  return p;
}
// polished metal: bands of light across a bar (vertical bar: bands run down it)
const CHROME = [[0, "#5d6670"], [.18, "#f4f7fa"], [.36, "#aab3bd"], [.55, "#e9edf1"], [.78, "#6f7882"], [1, "#2e343a"]];
const BRASS = [[0, "#6b4f1f"], [.2, "#f3d999"], [.42, "#c9a24a"], [.6, "#f0d58f"], [.82, "#8d6a28"], [1, "#4a3612"]];
function metalV(g, x, y, w, h, stops = CHROME) { g.fillStyle = lin(g, x, 0, x + w, 0, stops); g.fillRect(x, y, w, h); }
function metalH(g, x, y, w, h, stops = CHROME) { g.fillStyle = lin(g, 0, y, 0, y + h, stops); g.fillRect(x, y, w, h); }
// a line of LED light: a bright core with a bloom round it
function ledLine(g, x0, y0, x1, y1, w = 1, col = LED, bloom = 6) {
  g.save(); g.lineCap = "round";
  g.shadowColor = col; g.shadowBlur = bloom * S;
  g.strokeStyle = col; g.lineWidth = w; g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke();
  g.shadowBlur = 0; g.strokeStyle = LED_HOT; g.lineWidth = w * .45; g.stroke();
  g.restore();
}
function label(g, s, x, y, size, col, { font = FONT.sans, weight = 600, align = "center", spacing = 0, glow = 0 } = {}) {
  g.save(); g.font = `${weight} ${size}px "${font}"`; g.textAlign = align; g.textBaseline = "middle";
  if ("letterSpacing" in g) g.letterSpacing = `${spacing}px`;
  if (glow) { g.shadowColor = col; g.shadowBlur = glow * S; }
  g.fillStyle = col; g.fillText(s, x, y);
  if (glow) { g.shadowBlur = 0; g.fillStyle = LED_HOT; g.globalAlpha = .55; g.fillText(s, x, y); }
  g.restore();
}
// a glossy sheen over whatever was just drawn in a path's area (call with the path set)
function sheen(g, x, y, w, h, a = .16) {
  g.save(); g.clip();
  g.fillStyle = lin(g, x, y, x + w * .7, y + h, [[0, `rgba(255,255,255,${a})`], [.35, "rgba(255,255,255,0)"], [.6, "rgba(255,255,255,0)"], [.72, `rgba(255,255,255,${a * .5})`], [.8, "rgba(255,255,255,0)"]]);
  g.fillRect(x, y, w, h); g.restore();
}
// fine noise, for surfaces that shouldn't look flat
function grain(g, x, y, w, h, seed, a = .05, step = .5) {
  const R = rng(seed);
  for (let yy = y; yy < y + h; yy += step) for (let xx = x; xx < x + w; xx += step) {
    const v = R(); if (v < .5) continue;
    g.fillStyle = v > .75 ? `rgba(255,255,255,${a})` : `rgba(0,0,0,${a})`; g.fillRect(xx, yy, step, step);
  }
}

/* ================================================================ the pieces */
const PIECES = {};
const def = (id, o) => { PIECES[id] = Object.assign({ id, facings: ["down"], mount: "floor", mirrors: {}, cat: "Decor" }, o); };

/* ---------------------------------------------------------------- the stage */
// The master table's raised platform: a black marble deck with a brass inlay and an LED nosing, a lacquered riser with
// a cove of light spilling onto the carpet, and three lit steps in the middle of the front. Flat: it lies under
// everything; the glass balustrade (rail_* pieces) stands on its edges and gives it its height.
const ST = { w: 480, d: 320, rise: 12, x0: 10, y0: 8, stepW: 96 };
def("stage", {
  name: "Raised stage, 480×320", cat: "Stage", mount: "flat", size: [500, 376], anchor: [250, 328], body: null,
  draw(g) {
    const { w, d, rise, x0, y0, stepW } = ST, x1 = x0 + w, y1 = y0 + d, sx0 = 250 - stepW / 2, sx1 = 250 + stepW / 2;
    // the light the riser throws on the carpet, and its shadow down the right
    pool(g, 250, y1 + rise + 2, 260, 22, LED, .32, .3);
    g.fillStyle = lin(g, x1, 0, x1 + 8, 0, [[0, "rgba(0,0,0,.55)"], [1, "rgba(0,0,0,0)"]]); g.fillRect(x1, y0 + 6, 8, d + rise);
    // the riser
    g.fillStyle = lin(g, 0, y1, 0, y1 + rise, [[0, "#1b1a1d"], [.5, "#0f0e10"], [1, "#070607"]]); g.fillRect(x0, y1, w, rise);
    g.fillStyle = tex(g, "walnut", .2, 90); g.globalAlpha = .18; g.fillRect(x0, y1, w, rise); g.globalAlpha = 1;
    metalH(g, x0, y1, w, 1.2);
    ledLine(g, x0 + 2, y1 + rise - .6, x1 - 2, y1 + rise - .6, .8, LED, 5);
    // the deck: black marble, polished
    g.save();
    g.beginPath(); g.rect(x0, y0, w, d); g.fillStyle = tex(g, "marble_black", .5, 8); g.fill();
    g.fillStyle = "rgba(10,10,14,.25)"; g.fill();
    pool(g, 250, y0 + d * .52, w * .48, d * .5, LED, .16, .35);           // the downlight over the table
    g.beginPath(); g.rect(x0, y0, w, d); sheen(g, x0, y0, w, d, .10);
    g.restore();
    // brass inlay, a frame in from the edge, and a rule round the step landing
    g.strokeStyle = lin(g, x0, y0, x1, y1, BRASS); g.lineWidth = 1.4;
    g.strokeRect(x0 + 10.5, y0 + 10.5, w - 21, d - 21);
    g.lineWidth = .6; g.strokeRect(x0 + 13.5, y0 + 13.5, w - 27, d - 27);
    // edges: a soft dark lip round the deck, the LED nosing along the front
    g.strokeStyle = "rgba(0,0,0,.6)"; g.lineWidth = 1; g.strokeRect(x0 + .5, y0 + .5, w - 1, d - 1);
    ledLine(g, x0 + 1, y1 - .8, sx0, y1 - .8, 1, LED, 6); ledLine(g, sx1, y1 - .8, x1 - 1, y1 - .8, 1, LED, 6);
    ledLine(g, x0 + .8, y0 + 4, x0 + .8, y1 - 2, .6, LED, 3); ledLine(g, x1 - .8, y0 + 4, x1 - .8, y1 - 2, .6, LED, 3);
    // the steps: cut into the riser, each a marble tread with a lit nose and a dark riser
    const treads = [[y1, y1 + 4, y1 + 12], [y1 + 12, y1 + 16, y1 + 24], [y1 + 24, y1 + 28, y1 + 36]];   // [riser top, tread top, tread bottom]
    g.fillStyle = "#070607"; g.fillRect(sx0, y1, stepW, 36);
    treads.forEach(([rt, tt, tb], i) => {
      g.fillStyle = lin(g, 0, rt, 0, tt, [[0, "#1c1b1e"], [1, "#0b0a0c"]]); g.fillRect(sx0 - i * 2, rt, stepW + i * 4, tt - rt);
      g.save(); g.beginPath(); g.rect(sx0 - i * 2, tt, stepW + i * 4, tb - tt);
      g.fillStyle = tex(g, "marble_black", .5, 8, i * 40, 0); g.fill(); g.fillStyle = `rgba(255,214,150,${.05 + i * .02})`; g.fill(); g.restore();
      ledLine(g, sx0 - i * 2 + 1, tt + .5, sx0 + stepW + i * 2 - 1, tt + .5, .7, LED, 4);
    });
    g.fillStyle = "rgba(0,0,0,.45)"; g.fillRect(sx0 - 6, y1 + 36, stepW + 12, 1.5);
  },
});

/* ---------------------------------------------------------------- glass balustrade */
// Frameless glass on chrome posts with a brushed handrail: 18 game px high (waist height on a figure).
const RAIL_H = 18;
def("rail_glass_ew", {
  name: "Glass balustrade, east–west (64)", cat: "Stage", size: [68, 26], anchor: [34, 24], body: [-32, -3, 64, 4],
  draw(g) {
    const y = 24, top = y - RAIL_H, x0 = 2, x1 = 66;
    shade(g, 34, y + .5, 34, 2.2, .35);
    // the glass: faint blue-green, its edge brighter, reflections running across it
    g.fillStyle = lin(g, 0, top, 0, y, [[0, "rgba(190,225,235,.28)"], [1, "rgba(150,190,205,.16)"]]); g.fillRect(x0, top + 1, x1 - x0, RAIL_H - 2);
    g.save(); g.beginPath(); g.rect(x0, top + 1, x1 - x0, RAIL_H - 2); g.clip();
    g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 2.2;
    for (const sx of [12, 20, 44]) { g.beginPath(); g.moveTo(sx, y); g.lineTo(sx + 9, top); g.stroke(); }
    g.lineWidth = .6; g.beginPath(); g.moveTo(52, y); g.lineTo(61, top); g.stroke();
    g.restore();
    g.fillStyle = "rgba(220,245,250,.5)"; g.fillRect(x0, top + 1, x1 - x0, .6);
    // the base shoe, the posts and the handrail
    metalH(g, x0 - 1, y - 2.2, x1 - x0 + 2, 2.2);
    for (const px of [x0 - 1, x1 - 2]) { metalV(g, px, top - .5, 3, RAIL_H + .5); }
    metalH(g, x0 - 2, top - 1.6, x1 - x0 + 4, 2.4);
    g.fillStyle = "rgba(255,255,255,.7)"; g.fillRect(x0 - 2, top - 1.4, x1 - x0 + 4, .4);
  },
});
def("rail_glass_ns", {
  name: "Glass balustrade, north–south (32)", cat: "Stage", size: [12, 52], anchor: [6, 50], body: [-2, -32, 4, 32],
  draw(g) {
    const x = 6, base0 = 18, base1 = 50, top0 = base0 - RAIL_H, top1 = base1 - RAIL_H;   // the run, and its top line RAIL_H up
    g.fillStyle = "rgba(0,0,0,.28)"; g.fillRect(x + 1.5, base0, 3, base1 - base0);
    // seen end-on from the front: the glass is a narrow band between the base line and the handrail line
    g.fillStyle = lin(g, x - 2, 0, x + 2, 0, [[0, "rgba(170,210,222,.35)"], [.5, "rgba(225,245,250,.45)"], [1, "rgba(140,180,195,.3)"]]);
    g.fillRect(x - 1.6, top0, 3.2, base1 - top0);
    metalV(g, x - 1.2, base0, 2.4, base1 - base0);                                    // base shoe
    metalV(g, x - 1.5, top0 - 1, 3, top1 - top0 + 2);                                  // handrail
    g.fillStyle = "rgba(255,255,255,.75)"; g.fillRect(x - .6, top0 - .5, .5, top1 - top0 + 1);
    for (const [t, b] of [[top0, base0], [top1, base1]]) metalV(g, x - 1.6, t - 1, 3.2, b - t + 1);   // posts at the ends
  },
});

/* ---------------------------------------------------------------- architecture and light */
def("led_column", {
  name: "Marble column with LED", cat: "Lighting", size: [44, 140], anchor: [22, 134], body: [-12, -10, 24, 10],
  draw(g) {
    const x0 = 10, x1 = 34, base = 134, top = 8;
    pool(g, 22, base, 28, 9, LED, .30, .2); shade(g, 22, base + .5, 15, 3.5, .55);
    // plinth
    g.fillStyle = lin(g, x0 - 2, 0, x1 + 2, 0, CHROME); g.fillRect(x0 - 2, base - 7, x1 - x0 + 4, 7);
    g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(x0 - 2, base - 1.5, x1 - x0 + 4, 1.5);
    // the shaft: black marble, lit down its corners
    g.save(); g.beginPath(); g.rect(x0, top + 6, x1 - x0, base - 7 - top - 6);
    g.fillStyle = tex(g, "marble_black", .35, 82, 7, 0); g.fill();
    g.fillStyle = lin(g, x0, 0, x1, 0, [[0, "rgba(255,210,140,.20)"], [.3, "rgba(0,0,0,.05)"], [.7, "rgba(0,0,0,.35)"], [1, "rgba(255,210,140,.12)"]]); g.fill();
    g.restore();
    ledLine(g, x0 + 2.5, top + 10, x0 + 2.5, base - 10, .9, LED, 7);
    ledLine(g, x1 - 2.5, top + 10, x1 - 2.5, base - 10, .9, LED, 7);
    for (let yy = top + 26; yy < base - 14; yy += 22) { g.fillStyle = "rgba(0,0,0,.4)"; g.fillRect(x0 + 4, yy, x1 - x0 - 8, .7); g.fillStyle = "rgba(255,230,190,.12)"; g.fillRect(x0 + 4, yy + .7, x1 - x0 - 8, .5); }
    // capital
    g.fillStyle = lin(g, 0, top, 0, top + 6, [[0, "#3a3a40"], [1, "#121214"]]); g.fillRect(x0 - 3, top, x1 - x0 + 6, 6);
    metalH(g, x0 - 3, top + 5, x1 - x0 + 6, 1.4, BRASS);
    pool(g, 22, top, 22, 6, LED, .35);
  },
});

def("glow_warm", {
  name: "Pool of warm light, large", cat: "Lighting", mount: "flat", size: [240, 140], anchor: [120, 70], body: null,
  draw(g) { pool(g, 120, 70, 120, 70, LED, .20, .35); },
});
def("glow_spot", {
  name: "Pool of warm light, small", cat: "Lighting", mount: "flat", size: [120, 72], anchor: [60, 36], body: null,
  draw(g) { pool(g, 60, 36, 60, 36, LED, .24, .3); },
});

def("video_wall", {
  name: "LED video wall with jackpot", cat: "Wall decor", mount: "wall", size: [340, 58], anchor: [170, 58], body: null,
  screen: { show: "jackpot", rect: [96, 30, 148, 20], colour: "#ffd28a" },
  draw(g) {
    const w = 340, h = 58;
    pool(g, w / 2, h / 2, w * .55, h * .9, LED, .18);
    fillRR(g, 2, 2, w - 4, h - 4, 3, "#050506");
    g.strokeStyle = lin(g, 0, 0, w, 0, CHROME); g.lineWidth = 1.4; rr(g, 2.7, 2.7, w - 5.4, h - 5.4, 3); g.stroke();
    // the picture on it: an amber haze and light trails over black, the jackpot banner in the middle
    g.save(); rr(g, 5, 5, w - 10, h - 10, 2); g.clip();
    g.fillStyle = lin(g, 0, 5, 0, h - 5, [[0, "#1a0f08"], [.6, "#0b0706"], [1, "#030303"]]); g.fillRect(5, 5, w - 10, h - 10);
    for (const [cx, col, a] of [[60, AMBER, .35], [280, COPPER, .35], [170, LED, .22]]) pool(g, cx, 34, 90, 30, col, a);
    g.strokeStyle = "rgba(255,210,140,.35)"; g.lineWidth = .8;
    for (let i = 0; i < 7; i++) { g.beginPath(); g.moveTo(5, 14 + i * 5); g.bezierCurveTo(90, 4 + i * 7, 240, 50 - i * 6, w - 5, 18 + i * 4); g.stroke(); }
    label(g, "MEGA PROGRESSIVE", w / 2, 17, 8.5, LED, { spacing: 1.6, glow: 4 });
    fillRR(g, 94, 28, 152, 24, 2, "rgba(0,0,0,.72)");
    g.strokeStyle = rgba(LED, .6); g.lineWidth = .6; rr(g, 94.5, 28.5, 151, 23, 2); g.stroke();
    g.fillStyle = "rgba(0,0,0,.25)"; for (let y = 5; y < h - 5; y += 1) g.fillRect(5, y, w - 10, .35);   // scan lines
    g.restore();
  },
});

def("wall_sconce", {
  name: "Wall sconce, amber", cat: "Wall decor", mount: "wall", size: [24, 40], anchor: [12, 40], body: null,
  draw(g) {
    pool(g, 12, 14, 12, 18, LED, .45); pool(g, 12, 34, 10, 6, LED, .3);
    g.fillStyle = lin(g, 8, 0, 16, 0, BRASS); g.fillRect(9.5, 6, 5, 26);
    fillRR(g, 8, 8, 8, 18, 2, lin(g, 8, 0, 16, 0, [[0, "#ffcf8a"], [.5, "#fff3dc"], [1, "#e8a85a"]]));
    g.save(); g.shadowColor = LED; g.shadowBlur = 8 * S; fillRR(g, 9, 9, 6, 16, 2, "rgba(255,240,210,.9)"); g.restore();
    metalH(g, 7.5, 7, 9, 1.4, BRASS); metalH(g, 7.5, 25, 9, 1.4, BRASS);
  },
});

/* ---------------------------------------------------------------- signs */
// Digital totems standing at the pits: black glass, a chrome edge, the game's name lit in amber over its emblem.
function pylon(g, name, emblem) {
  const w = 36, base = 82, top = 4;
  pool(g, w / 2, base, 22, 6, LED, .35); shade(g, w / 2, base + .5, 13, 2.6, .5);
  fillRR(g, 6, base - 5, w - 12, 5, 1, lin(g, 6, 0, w - 6, 0, CHROME));
  fillRR(g, 4, top, w - 8, base - top - 4, 2.5, lin(g, 4, 0, w - 4, 0, [[0, "#1b1c20"], [.5, "#0c0c0e"], [1, "#050506"]]));
  g.strokeStyle = lin(g, 4, top, w - 4, base, CHROME); g.lineWidth = .9; rr(g, 4.4, top + .4, w - 8.8, base - top - 4.8, 2.5); g.stroke();
  g.save(); rr(g, 6, top + 2, w - 12, base - top - 8, 1.5); g.clip();
  pool(g, w / 2, top + 30, 20, 26, AMBER, .22);
  emblem(g, w / 2, top + 36);
  g.restore();
  label(g, name, w / 2, top + 10, name.length > 6 ? 3.6 : 5, LED, { spacing: name.length > 6 ? 0 : .5, glow: 3 });
  ledLine(g, 9, top + 16, w - 9, top + 16, .4, LED, 2);
  label(g, name === "SLOTS" ? "JACKPOTS" : "TABLE GAMES", w / 2, base - 13, 2.1, rgba(LED, .75), { spacing: .15 });
  g.beginPath(); rr(g, 4, top, w - 8, base - top - 4, 2.5); sheen(g, 4, top, w - 8, base - top, .12);
}
def("pylon_roulette", {
  name: "Sign totem: Roulette", cat: "Signs", size: [36, 86], anchor: [18, 82], body: [-9, -6, 18, 6],
  draw(g) {
    pylon(g, "ROULETTE", (g, cx, cy) => {
      fillEll(g, cx, cy, 11, 11, lin(g, cx - 11, cy - 11, cx + 11, cy + 11, BRASS));
      for (let i = 0; i < 18; i++) { g.beginPath(); g.moveTo(cx, cy); g.arc(cx, cy, 9.5, i / 18 * Math.PI * 2, (i + 1) / 18 * Math.PI * 2); g.closePath(); g.fillStyle = i === 0 ? "#1f8a52" : i % 2 ? "#b8322b" : "#141414"; g.fill(); }
      fillEll(g, cx, cy, 5.5, 5.5, tex(g, "mahogany", .1)); fillEll(g, cx, cy, 2, 2, lin(g, cx - 2, 0, cx + 2, 0, BRASS));
      fillEll(g, cx + 6.5, cy - 4.5, 1.2, 1.2, "#ffffff");
    });
  },
});
def("pylon_craps", {
  name: "Sign totem: Craps", cat: "Signs", size: [36, 86], anchor: [18, 82], body: [-9, -6, 18, 6],
  draw(g) {
    pylon(g, "CRAPS", (g, cx, cy) => {
      for (const [dx, dy, rot, pips] of [[-5, 1, -.25, [[0, 0], [-2.6, -2.6], [2.6, 2.6], [-2.6, 2.6], [2.6, -2.6]]], [5.5, -2, .3, [[-2.6, -2.6], [2.6, 2.6]]]]) {
        g.save(); g.translate(cx + dx, cy + dy); g.rotate(rot);
        fillRR(g, -6, -6, 12, 12, 2.2, lin(g, -6, -6, 6, 6, [[0, "#e85a5a"], [1, "#8e1f22"]]));
        g.beginPath(); rr(g, -6, -6, 12, 12, 2.2); sheen(g, -6, -6, 12, 12, .3);
        for (const [px, py] of pips) fillEll(g, px, py, 1.1, 1.1, "#fff6ea");
        g.restore();
      }
    });
  },
});
def("pylon_slots", {
  name: "Sign totem: Slots", cat: "Signs", size: [36, 86], anchor: [18, 82], body: [-9, -6, 18, 6],
  draw(g) {
    pylon(g, "SLOTS", (g, cx, cy) => {
      fillRR(g, cx - 13, cy - 8, 26, 16, 2, "#f3eee4");
      for (let i = 0; i < 3; i++) { label(g, "7", cx - 8 + i * 8, cy + .5, 11, i === 1 ? "#c8322b" : "#b8322b", { font: FONT.serif }); }
      g.strokeStyle = lin(g, cx - 13, 0, cx + 13, 0, BRASS); g.lineWidth = 1.2; rr(g, cx - 13, cy - 8, 26, 16, 2); g.stroke();
      g.fillStyle = "rgba(0,0,0,.18)"; g.fillRect(cx - 13, cy - 8, 26, 3); g.fillRect(cx - 13, cy + 5, 26, 3);
    });
  },
});

/* ---------------------------------------------------------------- the bar */
// The bar runs east–west facing the room; the bartenders stand behind it and show from the waist up. A black marble
// top, a padded leather armrest, mahogany panels with a chrome foot rail and a cove of light under it.
def("bar_counter", {
  name: "Bar counter, facing the room (280)", cat: "Bar & counters", size: [292, 70], anchor: [146, 64], body: [-140, -26, 280, 26],
  draw(g) {
    const x0 = 6, x1 = 286, w = x1 - x0, topY = 16, ledge = 36, front = 42, foot = 62;
    pool(g, 146, foot + 1, 160, 9, LED, .35, .3);
    // the top: back edge (the bartenders' side) a little darker
    g.save(); g.beginPath(); g.rect(x0, topY, w, ledge - topY); g.fillStyle = tex(g, "marble_black", .45, 14); g.fill();
    g.fillStyle = lin(g, 0, topY, 0, ledge, [[0, "rgba(0,0,0,.35)"], [1, "rgba(255,220,170,.06)"]]); g.fill();
    g.beginPath(); g.rect(x0, topY, w, ledge - topY); sheen(g, x0, topY, w, ledge - topY, .14); g.restore();
    g.strokeStyle = "rgba(0,0,0,.7)"; g.lineWidth = .8; g.strokeRect(x0 + .4, topY + .4, w - .8, ledge - topY);
    // the armrest: a rolled leather bolster along the guests' edge
    g.fillStyle = tex(g, "leather", .18); g.fillRect(x0 - 1, ledge, w + 2, front - ledge);
    g.fillStyle = lin(g, 0, ledge, 0, front, [[0, "rgba(255,225,190,.28)"], [.45, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,.55)"]]); g.fillRect(x0 - 1, ledge, w + 2, front - ledge);
    // the front: mahogany panels between fluted chrome-capped pilasters
    g.fillStyle = tex(g, "mahogany", .22, 90); g.fillRect(x0, front, w, foot - front);
    g.fillStyle = lin(g, 0, front, 0, foot, [[0, "rgba(0,0,0,.45)"], [.25, "rgba(0,0,0,.05)"], [1, "rgba(0,0,0,.55)"]]); g.fillRect(x0, front, w, foot - front);
    for (let i = 0; i <= 7; i++) {
      const px = x0 + i * (w / 7);
      g.fillStyle = "#120c0a"; g.fillRect(px - 1.6, front, 3.2, foot - front);
      metalV(g, px - 1, front + 1, 2, foot - front - 2, BRASS);
      if (i < 7) { g.strokeStyle = "rgba(255,200,150,.12)"; g.lineWidth = .6; g.strokeRect(px + 5, front + 4, w / 7 - 10, foot - front - 9); }
    }
    // foot rail and the cove of light under it
    g.fillStyle = "#050404"; g.fillRect(x0, foot - 3, w, 3);
    ledLine(g, x0 + 2, foot - .8, x1 - 2, foot - .8, .8, LED, 5);
    metalH(g, x0 + 3, foot - 7, w - 6, 2.2);
    for (let i = 0; i < 8; i++) metalV(g, x0 + 8 + i * (w - 16) / 7, foot - 6, 1.2, 4);
    // on the bar: taps, glasses, a bottle and a lamp
    metalH(g, 132, topY - 3, 28, 4); for (let i = 0; i < 5; i++) { metalV(g, 134 + i * 5.5, topY - 13, 2, 11); fillRR(g, 133.4 + i * 5.5, topY - 16, 3.2, 4, 1, i % 2 ? "#1b1b1f" : COPPER); }
    const glass = (x, y, tall, drink) => {
      g.fillStyle = "rgba(0,0,0,.35)"; fillEll(g, x, y + .5, 2.6, .9, "rgba(0,0,0,.35)");
      g.fillStyle = drink; g.fillRect(x - 1.6, y - tall * .55, 3.2, tall * .55);
      g.strokeStyle = "rgba(230,245,250,.8)"; g.lineWidth = .4; g.strokeRect(x - 1.8, y - tall, 3.6, tall);
      g.fillStyle = "rgba(255,255,255,.55)"; g.fillRect(x - 1.4, y - tall + .5, .5, tall - 1);
    };
    glass(40, ledge + 1, 6, "rgba(232,150,60,.85)"); glass(48, ledge + 1, 5, "rgba(200,40,60,.8)"); glass(96, ledge + 1, 7, "rgba(240,200,90,.8)");
    glass(204, ledge + 1, 6, "rgba(232,150,60,.85)"); glass(246, ledge + 1, 5, "rgba(120,200,190,.75)");
    // cocktail glasses (coupes)
    for (const x of [70, 226]) { g.strokeStyle = "rgba(230,245,250,.85)"; g.lineWidth = .4; g.beginPath(); g.moveTo(x, ledge + .5); g.lineTo(x, ledge - 4); g.stroke(); fillEll(g, x, ledge - 5, 2.8, 1.2, "rgba(225,80,90,.85)"); }
    // a bottle at each end
    for (const x of [20, 270]) { fillRR(g, x - 2, topY + 2 - 12, 4, 12, 1, "rgba(40,70,40,.95)"); g.fillStyle = "#e9dcc0"; g.fillRect(x - 2, topY - 6, 4, 3.5); g.fillStyle = "rgba(255,255,255,.45)"; g.fillRect(x - 1.2, topY - 9, .6, 9); }
    // a small brass lamp
    metalV(g, 178.4, topY - 6, 1.2, 8, BRASS); pool(g, 179, topY - 8, 9, 6, LED, .45);
    fillRR(g, 175, topY - 11, 8, 5, 2, lin(g, 175, 0, 183, 0, [[0, "#e8b670"], [.5, "#fff0d0"], [1, "#c88b44"]]));
  },
});

// Behind the bartenders, on the back wall: backlit amber onyx, glass shelves of lit bottles, the bar's name in neon.
def("back_bar", {
  name: "Back bar with lit shelves", cat: "Bar & counters", mount: "wall", size: [300, 66], anchor: [150, 66], body: null,
  draw(g) {
    const w = 300, h = 66;
    fillRR(g, 2, 4, w - 4, h - 4, 2, tex(g, "walnut", .25, 90));
    g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(2, 4, w - 4, h - 4);
    // the onyx panel, lit from behind
    g.save(); g.beginPath(); g.rect(10, 16, w - 20, h - 22); g.clip();
    g.fillStyle = lin(g, 0, 16, 0, h - 6, [[0, "#f6b25a"], [.5, "#e08a2e"], [1, "#a8551e"]]); g.fillRect(10, 16, w - 20, h - 22);
    g.globalCompositeOperation = "multiply"; g.globalAlpha = .55; g.fillStyle = tex(g, "marble_white", .45, 30); g.fillRect(10, 16, w - 20, h - 22);
    g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;
    pool(g, w / 2, 40, w * .45, 30, "#fff2d8", .35);
    // shelves and bottles
    const R = rng(4), cols = ["#3a6b3a", "#6b2a1a", "#c9a24a", "#e8e1d0", "#2a3f6b", "#7a1f2b", "#b8743a", "#1d1d22"];
    for (const sy of [36, 54]) {
      for (let x = 14; x < w - 14; x += 4.4 + R() * 2.2) {
        if (Math.abs(x - w / 2) < 34 && sy === 36) continue;
        const bh = 9 + R() * 6, c = cols[Math.floor(R() * cols.length)];
        g.globalAlpha = .92; fillRR(g, x, sy - bh, 3.4, bh, 1, c); fillRR(g, x + 1, sy - bh - 3, 1.4, 3.5, .5, c);
        g.globalAlpha = .5; g.fillStyle = "#fff6e0"; g.fillRect(x + .6, sy - bh + 1, .5, bh - 2); g.globalAlpha = 1;
      }
      g.fillStyle = "rgba(230,245,250,.7)"; g.fillRect(10, sy, w - 20, .8); g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(10, sy + .8, w - 20, 1.2);
    }
    g.restore();
    g.strokeStyle = lin(g, 0, 0, w, 0, BRASS); g.lineWidth = 1.2; g.strokeRect(10, 16, w - 20, h - 22);
    // the name, in amber neon on a black fascia
    fillRR(g, w / 2 - 44, 4, 88, 22, 2, "#0a0909");
    g.strokeStyle = lin(g, w / 2 - 44, 0, w / 2 + 44, 0, BRASS); g.lineWidth = .8; rr(g, w / 2 - 43.6, 4.4, 87.2, 21.2, 2); g.stroke();
    label(g, "AMBER", w / 2, 13, 9.5, LED, { font: FONT.deco, spacing: 2.2, glow: 5 });
    label(g, "B A R", w / 2, 21.5, 4.2, rgba(LED, .85), { spacing: 1.2, glow: 2 });
    metalH(g, 2, h - 3, w - 4, 2, BRASS);
  },
});

def("bar_stool", {
  name: "Bar stool, leather and chrome", cat: "Seating", size: [20, 34], anchor: [10, 32], body: [-5, -4, 10, 4],
  draw(g) {
    shade(g, 10, 32, 8, 2.4, .5);
    fillEll(g, 10, 30.5, 6, 1.8, lin(g, 4, 0, 16, 0, CHROME));
    metalV(g, 9, 14, 2, 17);
    g.strokeStyle = lin(g, 3, 0, 17, 0, CHROME); g.lineWidth = .9; ell(g, 10, 22, 5.5, 1.6); g.stroke();   // foot ring
    // the seat: a leather cushion on a chrome ring
    fillEll(g, 10, 13.5, 7, 3, lin(g, 3, 0, 17, 0, CHROME));
    fillEll(g, 10, 11.5, 7, 3.4, tex(g, "leather", .12));
    fillEll(g, 10, 11.5, 7, 3.4, lin(g, 0, 8, 0, 15, [[0, "rgba(255,225,190,.35)"], [.5, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,.45)"]]));
    fillEll(g, 8.5, 10.6, 3, 1, "rgba(255,240,220,.25)");
  },
});

def("high_top", {
  name: "Cocktail high-top table", cat: "Tables & desks", size: [32, 48], anchor: [16, 46], body: [-7, -5, 14, 5],
  draw(g) {
    shade(g, 16, 46, 12, 3, .5);
    fillEll(g, 16, 44.5, 8, 2.4, lin(g, 8, 0, 24, 0, CHROME));
    metalV(g, 14.8, 20, 2.4, 25);
    // the top: black marble with a chrome edge, a tea light and two drinks
    fillEll(g, 16, 19.5, 14, 6, lin(g, 2, 0, 30, 0, CHROME));
    ell(g, 16, 18, 14, 6); g.fillStyle = tex(g, "marble_black", .3, 20); g.fill();
    ell(g, 16, 18, 14, 6); sheen(g, 2, 12, 28, 12, .2);
    pool(g, 16, 17, 10, 5, LED, .45);
    fillRR(g, 14.6, 13.5, 2.8, 3.6, .8, "rgba(255,220,160,.9)"); fillEll(g, 16, 13.6, .7, 1.2, LED_HOT);
    for (const [x, c] of [[10, "rgba(232,150,60,.85)"], [22, "rgba(200,40,60,.8)"]]) {
      g.fillStyle = c; g.fillRect(x - 1.4, 15.6, 2.8, 2.4);
      g.strokeStyle = "rgba(230,245,250,.8)"; g.lineWidth = .35; g.strokeRect(x - 1.5, 13, 3, 5);
    }
  },
});

/* ---------------------------------------------------------------- the cage */
// The cashier: a walnut and marble counter with three windows of glass in chrome frames, lit from above, the sign in
// the header. The cashiers stand behind it and show through the glass.
def("cashier_cage", {
  name: "Cashier cage, three windows (260)", cat: "Bar & counters", size: [272, 96], anchor: [136, 92], body: [-130, -24, 260, 24],
  draw(g) {
    const x0 = 6, x1 = 266, w = x1 - x0, header = 4, glassTop = 22, ledge = 56, front = 64, foot = 90;
    pool(g, 136, foot + 1, 150, 8, LED, .32, .3);
    // the counter top and the guests' marble ledge
    g.save(); g.beginPath(); g.rect(x0, ledge - 6, w, front - ledge + 6); g.fillStyle = tex(g, "marble_white", .4, 6); g.fill();
    g.fillStyle = lin(g, 0, ledge - 6, 0, front, [[0, "rgba(0,0,0,.25)"], [1, "rgba(255,240,215,.08)"]]); g.fill(); g.restore();
    g.fillStyle = "rgba(0,0,0,.5)"; g.fillRect(x0, front - 1, w, 1);
    // the front: walnut, three panels each with a brass number
    g.fillStyle = tex(g, "walnut", .22, 90); g.fillRect(x0, front, w, foot - front);
    g.fillStyle = lin(g, 0, front, 0, foot, [[0, "rgba(0,0,0,.4)"], [.3, "rgba(0,0,0,.05)"], [1, "rgba(0,0,0,.5)"]]); g.fillRect(x0, front, w, foot - front);
    for (let i = 0; i < 3; i++) {
      const cx = x0 + w * (i + .5) / 3;
      g.strokeStyle = "rgba(255,210,160,.14)"; g.lineWidth = .6; g.strokeRect(cx - w / 6 + 6, front + 4, w / 3 - 12, foot - front - 9);
      fillEll(g, cx, front + 12, 4.6, 4.6, lin(g, cx - 4, 0, cx + 4, 0, BRASS)); label(g, String(i + 1), cx, front + 12.4, 5.5, "#1b140c", { font: FONT.sans });
    }
    g.fillStyle = "#050404"; g.fillRect(x0, foot - 2.5, w, 2.5); ledLine(g, x0 + 2, foot - .7, x1 - 2, foot - .7, .7, LED, 4);
    // the glass: three windows with a pass-through slot at the bottom of each
    for (let i = 0; i < 3; i++) {
      const gx = x0 + 4 + i * (w - 8) / 3, gw = (w - 8) / 3 - 4;
      g.fillStyle = lin(g, 0, glassTop, 0, ledge - 6, [[0, "rgba(200,230,240,.20)"], [1, "rgba(160,200,215,.12)"]]); g.fillRect(gx + 2, glassTop, gw - 4, ledge - 6 - glassTop);
      g.save(); g.beginPath(); g.rect(gx + 2, glassTop, gw - 4, ledge - 6 - glassTop); g.clip();
      g.strokeStyle = "rgba(255,255,255,.28)"; g.lineWidth = 3; g.beginPath(); g.moveTo(gx + 10, ledge - 6); g.lineTo(gx + 26, glassTop); g.stroke();
      g.lineWidth = 1; g.beginPath(); g.moveTo(gx + 32, ledge - 6); g.lineTo(gx + 48, glassTop); g.stroke(); g.restore();
      fillRR(g, gx + gw / 2 - 12, ledge - 10, 24, 4, 1, "rgba(10,10,12,.85)");
      label(g, "CASH · CHIPS", gx + gw / 2, glassTop + 4, 2.6, rgba(LED, .85), { spacing: .3 });
    }
    for (let i = 0; i <= 3; i++) metalV(g, x0 + 2 + i * (w - 8) / 3, glassTop - 1, 3, ledge - 5 - glassTop);
    metalH(g, x0, ledge - 7.5, w, 2);
    // the header with the sign
    g.fillStyle = lin(g, 0, header, 0, glassTop, [[0, "#1a1a1e"], [1, "#0a0a0c"]]); g.fillRect(x0 - 2, header, w + 4, glassTop - header);
    metalH(g, x0 - 2, glassTop - 1.6, w + 4, 1.6, BRASS); metalH(g, x0 - 2, header, w + 4, 1.2, BRASS);
    label(g, "CASHIER", 136, header + 9.5, 10, LED, { spacing: 3.2, glow: 5 });
    for (const x of [40, 232]) { fillEll(g, x, header + 9, 2, 2, LED_HOT); pool(g, x, header + 9, 8, 6, LED, .5); }
  },
});

def("atm", {
  name: "Cash machine (charcoal)", cat: "Services", size: [32, 62], anchor: [16, 58], body: [-13, -12, 26, 12], interact: "atm",
  draw(g) {
    shade(g, 16, 58, 15, 3, .55); pool(g, 16, 52, 18, 8, LED, .2);
    // body: a charcoal box in 3/4 view, the top lit, the front with a hood over the screen
    fillRR(g, 3, 4, 26, 12, 2, lin(g, 0, 4, 0, 16, [[0, "#4a4c55"], [1, "#2c2e35"]]));
    fillRR(g, 3, 14, 26, 44, 1.5, lin(g, 3, 0, 29, 0, [[0, "#2a2c33"], [.5, "#1d1e23"], [1, "#121316"]]));
    g.strokeStyle = "rgba(255,255,255,.08)"; g.lineWidth = .5; rr(g, 3.3, 14.3, 25.4, 43.4, 1.5); g.stroke();
    fillRR(g, 5, 16, 22, 6, 1, "#08080a"); label(g, "CASH", 16, 19.2, 4.2, LED, { spacing: .8, glow: 2 });
    fillRR(g, 6, 24, 20, 14, 1, "#0b0c0f");
    fillRR(g, 7.5, 25.5, 17, 11, .8, lin(g, 0, 25, 0, 37, [[0, "#3b2a12"], [1, "#1a1208"]]));
    g.fillStyle = rgba(LED, .9); g.fillRect(9, 28, 9, .9); g.fillStyle = rgba(LED, .6); g.fillRect(9, 31, 13, .7); g.fillRect(9, 33, 11, .7);
    pool(g, 16, 31, 10, 7, LED, .25);
    for (let j = 0; j < 3; j++) for (let i = 0; i < 3; i++) fillRR(g, 7 + i * 3.4, 40.5 + j * 3, 2.6, 2.2, .5, lin(g, 0, 40, 0, 50, CHROME));
    fillRR(g, 19, 41, 7, 1.6, .5, "#050505"); fillEll(g, 24.5, 44.5, .8, .8, "#5fe07a");
    fillRR(g, 7, 51, 18, 2.2, .6, "#050505"); metalH(g, 7, 50.2, 18, .8);
    metalH(g, 3, 56.5, 26, 1.5);
  },
});

/* ---------------------------------------------------------------- lounge */
const LEATHER_TINT = "rgba(150,70,30,.22)";   // a cognac warmth over the brown leather
function cushion(g, x, y, w, h, r, light = .3) {
  fillRR(g, x, y, w, h, r, tex(g, "leather", .14));
  fillRR(g, x, y, w, h, r, LEATHER_TINT);
  fillRR(g, x, y, w, h, r, lin(g, 0, y, 0, y + h, [[0, `rgba(255,226,190,${light})`], [.4, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,.5)"]]));
  g.strokeStyle = "rgba(20,8,4,.7)"; g.lineWidth = .5; rr(g, x + .25, y + .25, w - .5, h - .5, r); g.stroke();
}
def("armchair", {
  name: "Leather lounge chair", cat: "Seating", size: [38, 42], anchor: [19, 40], facings: ["down", "left", "up"], mirrors: { right: "left" },
  body: [-14, -12, 28, 11],
  draw(g, f) {
    shade(g, 19, 39, 16, 3.2, .5);
    for (const lx of [7, 31]) metalV(g, lx - .7, 34, 1.4, 5);
    if (f === "down") {
      cushion(g, 6, 6, 26, 18, 6, .35);                        // the back
      cushion(g, 9, 21, 20, 11, 3, .4);                        // the seat
      cushion(g, 3, 14, 7, 21, 3); cushion(g, 28, 14, 7, 21, 3);   // the arms
      metalH(g, 4, 34, 30, 1.2);
    } else if (f === "up") {
      cushion(g, 6, 8, 26, 26, 6, .3);
      cushion(g, 3, 16, 7, 19, 3); cushion(g, 28, 16, 7, 19, 3);
      metalH(g, 4, 34, 30, 1.2);
    } else {   // facing left: its back stands on the right
      cushion(g, 6, 20, 24, 13, 3, .4);                        // seat, from the side
      cushion(g, 26, 6, 8, 28, 4, .35);                        // back
      cushion(g, 5, 16, 24, 7, 3, .45);                        // near arm
      metalH(g, 5, 34, 28, 1.2);
    }
  },
});
def("sofa", {
  name: "Leather lounge sofa", cat: "Seating", size: [84, 46], anchor: [42, 44], facings: ["down", "up"], body: [-38, -16, 76, 15],
  draw(g, f) {
    shade(g, 42, 43, 40, 3.6, .5);
    for (const lx of [6, 42, 78]) metalV(g, lx - .7, 38, 1.4, 5);
    if (f === "up") {
      cushion(g, 5, 10, 74, 28, 6, .3); cushion(g, 2, 18, 9, 20, 3); cushion(g, 73, 18, 9, 20, 3);
    } else {
      cushion(g, 5, 6, 74, 20, 6, .35);
      for (let i = 0; i < 3; i++) cushion(g, 11 + i * 21, 23, 20.5, 12, 3, .42);
      cushion(g, 2, 14, 9, 24, 3); cushion(g, 73, 14, 9, 24, 3);
    }
    metalH(g, 3, 38, 78, 1.2);
  },
});
def("side_table", {
  name: "Chrome and marble side table", cat: "Tables & desks", size: [24, 30], anchor: [12, 28], body: [-7, -5, 14, 5],
  draw(g) {
    shade(g, 12, 28, 9, 2.5, .5);
    fillEll(g, 12, 27, 6, 1.6, lin(g, 6, 0, 18, 0, CHROME)); metalV(g, 11.2, 13, 1.6, 14);
    fillEll(g, 12, 13.5, 9, 4, lin(g, 3, 0, 21, 0, CHROME));
    ell(g, 12, 12.4, 9, 4); g.fillStyle = tex(g, "marble_white", .25, 12); g.fill();
    ell(g, 12, 12.4, 9, 4); sheen(g, 3, 8, 18, 9, .25);
    // a low brass bowl with an orchid
    fillEll(g, 12, 12, 3.4, 1.4, lin(g, 9, 0, 15, 0, BRASS));
    g.strokeStyle = "#5b7a3a"; g.lineWidth = .5; g.beginPath(); g.moveTo(12, 11.5); g.quadraticCurveTo(13, 6, 16, 4); g.stroke();
    for (const [x, y] of [[13.4, 6.4], [15, 4.6], [16.6, 3.6]]) { fillEll(g, x, y, 1.3, 1.1, "#f6eef6"); fillEll(g, x, y + .2, .4, .4, "#c35a9a"); }
  },
});

/* ---------------------------------------------------------------- planting and features */
function planter(g, cx, base, rw, h) {
  shade(g, cx, base, rw + 4, 3, .55);
  fillRR(g, cx - rw, base - h, rw * 2, h, 1.5, lin(g, cx - rw, 0, cx + rw, 0, [[0, "#2c2c31"], [.3, "#16161a"], [.75, "#0c0c0e"], [1, "#1c1c20"]]));
  g.beginPath(); rr(g, cx - rw, base - h, rw * 2, h, 1.5); sheen(g, cx - rw, base - h, rw * 2, h, .14);
  metalH(g, cx - rw - .5, base - h - .5, rw * 2 + 1, 1.6, BRASS);
  fillEll(g, cx, base - h + .6, rw - 1, 1.6, "#2a1d14");
}
def("planter_palm", {
  name: "Kentia palm, black planter", cat: "Plants", size: [64, 112], anchor: [32, 108], body: [-10, -8, 20, 8],
  draw(g) {
    const cx = 32, base = 108, R = rng(17);
    planter(g, cx, base, 10, 22);
    // fronds: arching stems with leaflets hanging off both sides, back ones darker
    const fronds = [];
    for (let i = 0; i < 13; i++) { const a = -Math.PI / 2 + (i / 12 - .5) * 2.9 + (R() - .5) * .2; fronds.push({ a, len: 34 + R() * 18, back: i % 2 === 0 }); }
    fronds.sort((p, q) => (p.back === q.back ? 0 : p.back ? -1 : 1));
    for (const fr of fronds) {
      const sx = cx + (R() - .5) * 3, sy = base - 24, ex = sx + Math.cos(fr.a) * fr.len, ey = sy + Math.sin(fr.a) * fr.len * .9 + 6;
      const mx = sx + Math.cos(fr.a) * fr.len * .5, my = sy + Math.sin(fr.a) * fr.len * .6 - 10;
      const dark = fr.back ? .55 : 1;
      g.strokeStyle = `rgba(${70 * dark},${100 * dark},${45 * dark},1)`; g.lineWidth = .7;
      g.beginPath(); g.moveTo(sx, sy); g.quadraticCurveTo(mx, my, ex, ey); g.stroke();
      for (let t = .18; t < 1; t += .06) {
        const u = 1 - t, px = u * u * sx + 2 * u * t * mx + t * t * ex, py = u * u * sy + 2 * u * t * my + t * t * ey;
        const tx = 2 * u * (mx - sx) + 2 * t * (ex - mx), ty = 2 * u * (my - sy) + 2 * t * (ey - my), n = Math.hypot(tx, ty) || 1;
        const leaf = 6.5 * (1 - t * .55);
        for (const side of [-1, 1]) {
          const nx = -ty / n * side, ny = tx / n * side, lx = px + nx * leaf * .55, ly = py + ny * leaf * .55 + leaf * .5;
          const shadeL = (side > 0 ? .85 : 1) * dark;
          g.strokeStyle = `rgb(${Math.round((60 + R() * 30) * shadeL)},${Math.round((120 + R() * 40) * shadeL)},${Math.round((50 + R() * 20) * shadeL)})`;
          g.lineWidth = 1; g.beginPath(); g.moveTo(px, py); g.quadraticCurveTo(px + nx * leaf * .4, py + ny * leaf * .4, lx, ly); g.stroke();
        }
      }
    }
  },
});
def("planter_trough", {
  name: "Long planter with grasses (96)", cat: "Plants", size: [104, 46], anchor: [52, 42], body: [-48, -10, 96, 10],
  draw(g) {
    const R = rng(23);
    shade(g, 52, 42, 52, 3, .5);
    // the trough: black marble box with a brass cap and LED under it
    pool(g, 52, 43, 56, 5, LED, .3);
    g.fillStyle = tex(g, "marble_black", .3, 4); g.fillRect(4, 28, 96, 14);
    g.fillStyle = lin(g, 0, 28, 0, 42, [[0, "rgba(255,220,170,.10)"], [1, "rgba(0,0,0,.45)"]]); g.fillRect(4, 28, 96, 14);
    g.fillStyle = "#2a2a30"; g.fillRect(4, 22, 96, 6);
    metalH(g, 3.5, 21.5, 97, 1.4, BRASS);
    // ornamental grass: fine arcs, pale tips
    for (let i = 0; i < 150; i++) {
      const x = 7 + R() * 90, h = 10 + R() * 18, lean = (R() - .5) * 14, gcol = R();
      g.strokeStyle = gcol < .5 ? `rgba(${90 + R() * 40},${130 + R() * 30},${60 + R() * 20},.95)` : `rgba(${150 + R() * 40},${150 + R() * 30},${90 + R() * 20},.9)`;
      g.lineWidth = .45; g.beginPath(); g.moveTo(x, 24); g.quadraticCurveTo(x + lean * .3, 24 - h * .7, x + lean, 24 - h); g.stroke();
    }
    g.fillStyle = "#1f160f"; g.fillRect(5, 22.5, 94, 1.5);
  },
});
def("chip_sculpture", {
  name: "Chip tower sculpture", cat: "Statues & fountains", size: [56, 96], anchor: [28, 92], body: [-16, -14, 32, 14],
  draw(g) {
    const cx = 28, base = 92;
    pool(g, cx, base - 2, 34, 10, LED, .35); shade(g, cx, base, 20, 4, .55);
    // a round black marble plinth with a lit ring
    fillEll(g, cx, base - 3, 18, 6, "#060607");
    g.fillStyle = tex(g, "marble_black", .3, 20); g.fillRect(cx - 18, base - 17, 36, 14);
    fillEll(g, cx, base - 3, 18, 6, tex(g, "marble_black", .3, 20));
    g.fillStyle = lin(g, cx - 18, 0, cx + 18, 0, [[0, "rgba(255,220,170,.18)"], [.5, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,.45)"]]); g.fillRect(cx - 18, base - 17, 36, 14);
    fillEll(g, cx, base - 17, 18, 6, tex(g, "marble_black", .3, 40));
    g.save(); g.strokeStyle = LED; g.shadowColor = LED; g.shadowBlur = 5 * S; g.lineWidth = .7; ell(g, cx, base - 17, 17.4, 5.6); g.stroke(); g.restore();
    // the chips, tilted and stacked, each with edge spots
    const chips = [["#1b1b1f", "#e8e3d8"], [AMBER, "#fff3dc"], ["#8e1f22", "#f3e9d6"], ["#e8e3d8", "#1b1b1f"], [GOLD, "#1b1b1f"], ["#1b1b1f", LED], ["#8e1f22", "#f3e9d6"], [AMBER, "#1b1b1f"]];
    let y = base - 20;
    chips.forEach(([c, spot], i) => {
      const dx = Math.sin(i * 1.3) * 2.2, th = 4.4, rx = 12 - i * .35, ry = 4;
      g.fillStyle = c; g.fillRect(cx + dx - rx, y - th, rx * 2, th); fillEll(g, cx + dx, y, rx, ry, c);
      for (let k = 0; k < 6; k++) { const a = (k / 6) * Math.PI + .3; const px = cx + dx - Math.cos(a) * rx * .96; g.fillStyle = spot; g.fillRect(px - 1, y - th + .8, 2, th - 1.2); }
      g.fillStyle = lin(g, cx + dx - rx, 0, cx + dx + rx, 0, [[0, "rgba(255,255,255,.25)"], [.4, "rgba(255,255,255,0)"], [1, "rgba(0,0,0,.45)"]]); g.fillRect(cx + dx - rx, y - th, rx * 2, th);
      fillEll(g, cx + dx, y - th, rx, ry, c);
      g.strokeStyle = spot; g.lineWidth = .6; ell(g, cx + dx, y - th, rx * .62, ry * .62); g.stroke();
      g.globalAlpha = .25; fillEll(g, cx + dx - 3, y - th - 1, rx * .5, ry * .4, "#ffffff"); g.globalAlpha = 1;
      y -= th;
    });
    label(g, "★", cx + Math.sin(7 * 1.3) * 2.2, y - 4.4 + .3, 4.5, "#1b1b1f", { font: FONT.sans });
  },
});

def("stanchion_chrome", {
  name: "Chrome posts, red rope (64)", cat: "Decor", size: [72, 30], anchor: [36, 28], body: [-33, -4, 66, 4],
  draw(g) {
    g.save(); g.lineCap = "round";
    g.strokeStyle = "#3a0c12"; g.lineWidth = 2.6; g.beginPath(); g.moveTo(4, 9); g.quadraticCurveTo(36, 22, 68, 9); g.stroke();
    g.strokeStyle = "#8e1f2b"; g.lineWidth = 1.8; g.stroke();
    g.strokeStyle = "rgba(255,190,190,.35)"; g.lineWidth = .5; g.beginPath(); g.moveTo(4, 8.6); g.quadraticCurveTo(36, 21.4, 68, 8.6); g.stroke();
    g.restore();
    for (const x of [4, 68]) {
      shade(g, x, 28, 5, 1.6, .45);
      fillEll(g, x, 27, 4, 1.3, lin(g, x - 4, 0, x + 4, 0, CHROME));
      metalV(g, x - 1, 7, 2, 20);
      fillEll(g, x, 6.5, 2, 2, lin(g, x - 2, 0, x + 2, 0, CHROME));
    }
  },
});


/* ================================================================ rendering, for the build tool */
async function loadImage(url) { const im = new Image(); im.src = url; await im.decode(); return im; }

// textures: {name: data URL}; fonts: {family: data URL}. Returns every piece's pictures (data URLs, one per drawn
// facing) and its shapes in game pixels.
async function renderAll(textures, fonts) {
  for (const [name, url] of Object.entries(textures)) TEX[name] = await loadImage(url);
  for (const [family, url] of Object.entries(fonts)) { const f = new FontFace(family, `url(${url})`, { weight: "600" }); await f.load(); document.fonts.add(f); }
  const out = {};
  for (const d of Object.values(PIECES)) {
    const pictures = {};
    for (const f of d.facings) {
      const c = document.createElement("canvas");
      c.width = d.size[0] * S; c.height = d.size[1] * S;
      const g = c.getContext("2d"); g.scale(S, S);
      d.draw(g, f);
      pictures[f] = c.toDataURL("image/png");
    }
    out[d.id] = { name: d.name, cat: d.cat, size: d.size, anchor: d.anchor, body: d.body, mount: d.mount, mirrors: d.mirrors,
                  screen: d.screen || null, interact: d.interact || null, pictures };
  }
  return out;
}
