// The Modern lobby's furniture, drawn pixel by pixel in the LPC style of the floor plan's library: 1:1 game pixels,
// top-lit, dark outlines, a top and a front face in 3/4 view. Designed in the "Modern Lobby" mockup artifact
// (https://claude.ai/artifact/3Jvh1mDYRmzbknFaWE8fpA) and rendered to PNGs by tools/build_modern_pieces.py, which
// loads this file in headless Chromium and calls renderAll(look).
//
// A piece: def(id, {name, cat, size: [w, h], anchor: [x, y] (the middle of its base; a rug's middle),
// body: [x, y, w, h] about the anchor (the footprint that blocks walking; null for rugs and wall pieces),
// facings, mount: floor|flat|wall, uses (which look options colour it), screen (a live display the game draws on),
// interact ("atm": something you walk up to and use, bank.py), note, draw(p, o, facing)}. Left and right of the tub chair are mirror images.

/* ================================================================ colour */
const h2r = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const r2h = (r, g, b) => "#" + [r, g, b].map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
const lit = (h, a) => { const [r, g, b] = h2r(h); return r2h(r + (255 - r) * a, g + (255 - g) * a, b + (255 - b) * a); };   // Godot's lightened()
const drk = (h, a) => { const [r, g, b] = h2r(h); return r2h(r * (1 - a), g * (1 - a), b * (1 - a)); };                   // Godot's darkened()
const rgba = (h, a) => { const [r, g, b] = h2r(h); return `rgba(${r},${g},${b},${a})`; };
const ramp = h => ({ hi: lit(h, .26), mid: h, lo: drk(h, .24), dk: drk(h, .45), ln: drk(h, .7) });
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

/* ================================================================ a pixel canvas */
class P {
  constructor(w, h) { this.c = document.createElement("canvas"); this.c.width = w; this.c.height = h; this.g = this.c.getContext("2d"); this.w = w; this.h = h; }
  r(x, y, w, h, col) { if (!col || w <= 0 || h <= 0) return; this.g.fillStyle = col; this.g.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); }
  px(x, y, col) { this.r(x, y, 1, 1, col); }
  // a filled rect with a one-pixel outline round it
  ob(x, y, w, h, fill, line) { this.r(x - 1, y - 1, w + 2, h + 2, line); this.r(x, y, w, h, fill); }
  ell(cx, cy, rx, ry, col) {
    if (ry <= 0) { this.r(cx - rx, cy, rx * 2 + 1, 1, col); return; }
    for (let y = -ry; y <= ry; y++) { const hw = Math.round(rx * Math.sqrt(Math.max(0, 1 - (y * y) / (ry * ry)))); this.r(cx - hw, cy + y, hw * 2 + 1, 1, col); }
  }
  oell(cx, cy, rx, ry, fill, line) { this.ell(cx, cy, rx + 1, ry + 1, line); this.ell(cx, cy, rx, ry, fill); }
  ring(cx, cy, rx, ry, col, steps) { for (let i = 0; i < steps; i++) { const a = i / steps * Math.PI * 2; this.px(Math.round(cx + Math.cos(a) * rx), Math.round(cy + Math.sin(a) * ry), col); } }
  // a box in 3/4 view: footprint x..x+w, fy..fy+d on the floor, H tall. Returns the faces.
  box3(x, fy, w, d, H, top, front, line) {
    this.r(x - 1, fy - H - 1, w + 2, d + H + 2, line);
    this.r(x, fy - H, w, d, top);
    this.r(x, fy - H + d, w, H, front);
    this.r(x, fy - H + d, w, 1, line);
    return { topY: fy - H, frontY: fy - H + d, bottom: fy + d };
  }
  shadow(cx, cy, rx, ry, a = .3) { this.ell(cx, cy, rx, ry, `rgba(0,0,0,${a})`); }
  flipped() { const q = new P(this.w, this.h); q.g.translate(this.w, 0); q.g.scale(-1, 1); q.g.drawImage(this.c, 0, 0); return q; }
}

/* a 3×5 pixel font for the screens, plaques and labels */
const GLYPH = {
  "0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111", "4": "101101111001001",
  "5": "111100111001111", "6": "111100111101111", "7": "111001001010010", "8": "111101111101111", "9": "111101111001111",
  "£": "011010111010111", ",": "000000000010100", ".": "000000000000010", " ": "000000000000000",
  "A": "010101111101101", "C": "011100100100011", "E": "111100110100111", "H": "101101111101101", "I": "111010010010111",
  "J": "001001001101010", "K": "101101110101101", "N": "101111111101101", "O": "010101101101010", "P": "110101110100100",
  "R": "110101110101101", "S": "011100010001110", "T": "111010010010010", "L": "100100100100111", "G": "011100101101011",
  "W": "101101111111101", "M": "101111111101101", "B": "110101110101110", "D": "110101101101110", "F": "111100110100100",
  "U": "101101101101111", "V": "101101101101010", "Y": "101101010010010", "X": "101101010101101", "Z": "111001010100111", "Q": "010101101110011",
};
const textW = (s, k = 1) => s.length ? (s.length * 4 - 1) * k : 0;
function text(p, s, x, y, col, k = 1) {
  s = s.toUpperCase();
  for (let i = 0; i < s.length; i++) {
    const g = GLYPH[s[i]] || GLYPH[" "];
    for (let j = 0; j < 15; j++) if (g[j] === "1") p.r(x + (i * 4 + j % 3) * k, y + Math.floor(j / 3) * k, k, k, col);
  }
}


function slabTile(base, grout, vein, seed) {
  const p = new P(64, 64), R = rng(seed);
  p.r(0, 0, 64, 64, grout);
  const slabs = [[0, 0], [-32, 32], [32, 32]];
  for (const [sx, sy] of slabs) {
    const tone = (R() - .5) * .06, col = tone > 0 ? lit(base, tone) : drk(base, -tone);
    p.r(sx + 1, sy + 1, 62, 30, col);
    let x = sx + 4 + R() * 50, y = sy + 3 + R() * 20;
    for (let i = 0; i < 26; i++) { if (x > sx && x < sx + 63 && y > sy && y < sy + 31) p.px(x, y, vein); x += 1 + (R() < .3 ? 1 : 0); y += R() < .5 ? 1 : (R() < .5 ? 0 : -1); }
  }
  return p.c;
}

/* ================================================================ the looks you can switch */
const FINISH = {
  quartz: { name: "White quartz, charcoal flutes", top: "#e9e7e1", vein: "#cdc9c0", front: "#2d2d34" },
  marble: { name: "Black marble, black flutes", top: "#2a2a31", vein: "#4c4c58", front: "#1b1b20" },
  walnut: { name: "Cream stone, walnut flutes", top: "#ede6d8", vein: "#d6ccb9", front: "#6a4128" },
};
const UPH = {
  emerald: { name: "Emerald velvet", c: "#1f6b55" }, navy: { name: "Navy velvet", c: "#2a447e" }, blush: { name: "Blush boucle", c: "#c28a84" },
  charcoal: { name: "Charcoal wool", c: "#46464f" }, mustard: { name: "Mustard velvet", c: "#c0912a" },
};
const RUG = {
  teal: { name: "Teal and gold", field: "#13423f", field2: "#0e3533", dk: "#061c1b" },
  plum: { name: "Plum and gold", field: "#40193d", field2: "#331431", dk: "#1a0a19" },
  charcoal: { name: "Charcoal and gold", field: "#2c2c32", field2: "#242429", dk: "#121215" },
  ivory: { name: "Ivory and gold", field: "#ddd3bf", field2: "#cfc3ab", dk: "#7d6d50" },
};
const METAL = {
  gold: { name: "Brushed gold", hi: "#f6dc94", mid: "#cfa64e", lo: "#8d6a28", ln: "#4a3612" },
  chrome: { name: "Chrome", hi: "#f4f6f9", mid: "#b7bec8", lo: "#7a838f", ln: "#383e47" },
  black: { name: "Matte black", hi: "#62626b", mid: "#34343a", lo: "#1f1f23", ln: "#0b0b0d" },
};
function opts(st) { return { finish: FINISH[st.finish], uph: ramp(UPH[st.uph].c), rug: RUG[st.rug], metal: METAL[st.metal] }; }


/* ================================================================ the new pieces */
const PIECES = {};
const def = (id, o) => { PIECES[id] = Object.assign({ id, facings: ["down"], mount: "floor", uses: [] }, o); };
const LEAF = { ln: "#16301a", lo: "#2c5a2c", mid: "#3f7f3a", hi: "#69a84f" };

def("reception_side", {
  name: "Reception counter, along a wall", cat: "Reception", size: [44, 198], anchor: [22, 196], body: [-14, -160, 28, 160], facings: ["left"],
  uses: ["finish", "metal"], note: "Runs north to south against a side wall; the staff stand on the wall side and guests on the open side. A raised guest ledge, fluted end panel, and a warm LED wash on the floor along the guest side. Monitors face the staff.",
  draw(p, o) {
    const F = o.finish, M = o.metal, T = ramp(F.top), Fr = ramp(F.front);
    for (let i = 0; i < 3; i++) p.r(2 - i, 14, 1, 182, `rgba(255,214,140,${.08 + .07 * (2 - i)})`);   // LED wash on the floor
    p.r(3, 196, 37, 2, "rgba(0,0,0,.35)");
    p.ob(4, 9, 4, 187, Fr.mid, Fr.ln);                                         // the fluted guest face, seen at a slant
    for (let y = 10; y < 196; y += 3) { p.r(4, y, 4, 1, Fr.hi); p.r(4, y + 1, 4, 1, Fr.lo); }
    p.r(7, 9, 1, 187, M.mid); p.r(4, 9, 1, 187, "#ffd98a");
    p.ob(8, 12, 28, 160, T.mid, T.ln);                                         // work surface
    const R = rng(3);
    for (let i = 0; i < 9; i++) { let x = 18 + R() * 14, y = 16 + R() * 150; for (let j = 0; j < 6; j++) p.px(x + j, y + j * 1.6, T.lo); }
    p.ob(8, 172, 28, 24, Fr.mid, Fr.ln);                                       // the fluted south end
    for (let x = 8; x < 36; x++) if ((x - 8) % 3 === 2) p.r(x, 174, 1, 18, Fr.hi); else if ((x - 8) % 3 === 0) p.r(x, 174, 1, 18, Fr.lo);
    p.r(8, 172, 28, 2, M.mid); p.r(8, 172, 28, 1, M.hi);
    p.r(8, 192, 28, 4, Fr.dk); p.r(8, 191, 28, 1, "#ffd98a");
    p.r(21, 180, 2, 6, M.hi); p.r(20, 182, 4, 2, M.hi);                         // a small gold mark
    p.ob(8, 8, 9, 160, T.hi, T.ln);                                            // the raised guest ledge
    p.r(8, 168, 9, 4, T.lo); p.r(8, 168, 9, 1, T.ln);
    p.r(17, 12, 1, 160, T.lo);
    for (const c of [84, 146]) {                                               // monitors, backs to the guests
      p.r(30, c - 4, 4, 10, "#c9cbd1"); p.r(30, c - 4, 4, 1, "#e9eaee");      // keyboard on the staff side
      p.ob(25, c - 9, 3, 15, "#1c1d22", "#0a0a0c"); p.r(25, c - 9, 1, 15, "#3b3d45");
      p.r(26, c + 6, 3, 2, "#55575f");
    }
    p.r(11, 117, 3, 2, M.mid); p.px(12, 116, M.hi); p.r(10, 119, 5, 1, M.lo);  // a desk bell
    p.ob(10, 57, 5, 7, "#f4f1ea", "#6d6a63"); p.r(11, 58, 3, 1, "#c1443d"); p.r(11, 60, 3, 1, "#2a6f9b"); p.r(11, 62, 3, 1, M.mid);   // brochures
    p.ob(10, 23, 5, 5, "#f3f0ea", "#8f8a80");                                  // an orchid
    p.r(12, 14, 1, 9, "#5b7a3a"); p.px(11, 22, LEAF.mid); p.px(14, 22, LEAF.mid); p.px(10, 23, LEAF.lo);
    for (const [x, y] of [[10, 14], [13, 12], [15, 15], [11, 17]]) { p.r(x, y, 2, 2, "#f6eef6"); p.px(x + 1, y + 1, "#c35a9a"); }
  },
});

def("reception_front", {
  name: "Reception counter, facing the room", cat: "Reception", size: [146, 72], anchor: [73, 68], body: [-70, -28, 140, 28],
  uses: ["finish", "metal"], note: "The same counter turned to face the door: staff stand behind it and show from the waist up. A backlit RECEPTION plaque on the fluted front.",
  draw(p, o) {
    const F = o.finish, M = o.metal, T = ramp(F.top), Fr = ramp(F.front);
    for (let i = 0; i < 4; i++) p.r(3 - i, 69 + i * 0, 140 + 2 * i, 1, `rgba(255,214,140,${.18 - .04 * i})`);
    p.r(3, 69, 140, 1, "rgba(255,214,140,.22)"); p.r(5, 70, 136, 1, "rgba(255,214,140,.12)"); p.r(9, 71, 128, 1, "rgba(255,214,140,.06)");
    p.ob(3, 14, 140, 24, T.mid, T.ln);                                        // work surface
    const R = rng(5);
    for (let i = 0; i < 10; i++) { let x = 8 + R() * 128, y = 15 + R() * 10; for (let j = 0; j < 7; j++) p.px(x + j * 1.7, y + j * .6, T.lo); }
    p.ob(3, 42, 140, 26, Fr.mid, Fr.ln);                                      // the fluted front
    for (let x = 3; x < 143; x++) if ((x - 3) % 3 === 2) p.r(x, 44, 1, 19, Fr.hi); else if ((x - 3) % 3 === 0) p.r(x, 44, 1, 19, Fr.lo);
    p.r(3, 42, 140, 2, M.mid); p.r(3, 42, 140, 1, M.hi);
    p.r(3, 64, 140, 4, Fr.dk); p.r(3, 63, 140, 1, "#ffd98a");
    p.ob(48, 48, 50, 11, "#141416", M.mid);                                   // the plaque
    p.r(48, 48, 50, 11, "#141416"); p.r(48, 47, 50, 1, M.hi); p.r(48, 59, 50, 1, M.lo);
    text(p, "RECEPTION", 73 - textW("RECEPTION") / 2, 51, "#ffe2a0");
    p.ob(3, 30, 140, 8, T.hi, T.ln);                                          // the raised guest ledge
    p.r(3, 38, 140, 4, T.lo); p.r(3, 38, 140, 1, T.ln); p.r(3, 29, 140, 1, T.lo);
    for (const c of [40, 102]) {                                              // monitors, screens to the staff
      p.ob(c - 8, 15, 16, 8, "#1c1d22", "#0a0a0c"); p.r(c - 8, 15, 16, 1, "#3b3d45");
      p.r(c - 2, 23, 4, 3, "#55575f");
    }
    p.r(72, 31, 3, 2, M.mid); p.px(73, 30, M.hi); p.r(71, 33, 5, 1, M.lo);    // bell
    p.ob(126, 30, 7, 5, "#f4f1ea", "#6d6a63"); p.r(127, 31, 5, 1, "#c1443d"); p.r(127, 33, 5, 1, "#2a6f9b");
    p.ob(9, 29, 5, 5, "#f3f0ea", "#8f8a80");
    p.r(11, 19, 1, 10, "#5b7a3a"); p.px(10, 28, LEAF.mid); p.px(13, 28, LEAF.mid);
    for (const [x, y] of [[9, 19], [12, 17], [14, 20], [10, 22]]) { p.r(x, y, 2, 2, "#f6eef6"); p.px(x + 1, y + 1, "#c35a9a"); }
  },
});

def("back_credenza", {
  name: "Back credenza with lamp", cat: "Reception", size: [68, 52], anchor: [34, 50], body: [-32, -14, 64, 14],
  uses: ["finish", "metal"], note: "A low fluted cabinet for the wall behind the desk, with a drum lamp and a small plant.",
  draw(p, o) {
    const F = o.finish, M = o.metal, T = ramp(F.top), Fr = ramp(F.front);
    p.shadow(34, 50, 33, 2);
    const b = p.box3(2, 36, 64, 14, 22, T.mid, Fr.mid, Fr.ln);
    for (let x = 2; x < 66; x++) if ((x - 2) % 3 === 2) p.r(x, b.frontY + 3, 1, 15, Fr.hi); else if ((x - 2) % 3 === 0) p.r(x, b.frontY + 3, 1, 15, Fr.lo);
    p.r(2, b.frontY + 1, 64, 2, M.mid); p.r(2, b.bottom - 3, 64, 3, Fr.dk);
    p.r(33, b.frontY + 4, 1, 13, Fr.ln);
    p.r(29, b.frontY + 9, 2, 4, M.hi); p.r(36, b.frontY + 9, 2, 4, M.hi);
    p.r(2, b.topY, 64, 1, T.hi);
    p.ell(16, 6, 9, 9, "rgba(255,225,160,.10)");
    p.ob(15, 10, 2, 8, M.mid, M.ln); p.r(12, 18, 8, 2, M.lo);                  // drum lamp
    p.ob(10, 3, 12, 8, "#f6ecd6", "#9b8c6c"); p.r(10, 9, 12, 2, "#e4d4b0"); p.r(11, 4, 10, 1, "#fffaf0");
    p.ob(50, 16, 8, 6, "#efece6", "#8f8a80");                                  // small plant
    for (const [x, y] of [[49, 12], [52, 10], [55, 11], [57, 13], [51, 14], [54, 14]]) { p.r(x, y, 3, 3, LEAF.ln); p.r(x, y, 2, 2, LEAF.mid); }
  },
});

def("sofa", {
  name: "Low lounge sofa", cat: "Seating", size: [80, 44], anchor: [40, 42], facings: ["down", "up"], uses: ["uph", "metal"],
  body: [-36, -18, 72, 16], note: "A low three-seat sofa with a rolled back and slim gold legs. Two facings so a pair can face each other across a rug.",
  draw(p, o, f) {
    const U = o.uph, M = o.metal;
    p.shadow(40, 41, 38, 3);
    if (f === "up") {
      p.ob(4, 11, 72, 24, U.mid, U.ln);                                       // the back panel
      for (let y = 0; y < 24; y++) if (y > 14) p.r(4, 11 + y, 72, 1, drk(U.mid, (y - 14) * .025));
      p.r(4, 11, 72, 4, U.hi); p.r(4, 15, 72, 1, U.lo);
      for (let x = 12; x < 72; x += 10) p.px(x, 22, U.lo);
      p.ob(2, 14, 9, 22, U.lo, U.ln); p.r(2, 14, 9, 3, U.mid);
      p.ob(69, 14, 9, 22, U.lo, U.ln); p.r(69, 14, 9, 3, U.mid);
      p.r(6, 36, 2, 4, M.mid); p.r(72, 36, 2, 4, M.mid);
      return;
    }
    p.ob(5, 8, 70, 17, U.mid, U.ln);                                          // the back
    p.r(5, 8, 70, 5, U.hi); p.r(5, 13, 70, 1, lit(U.mid, .1));
    for (let x = 12; x < 72; x += 9) p.px(x, 18, U.lo);
    p.ob(12, 23, 56, 9, lit(U.mid, .14), U.ln);                               // seat cushions
    p.r(12, 23, 56, 1, U.lo); p.r(30, 24, 1, 8, U.lo); p.r(49, 24, 1, 8, U.lo);
    p.ob(12, 32, 56, 5, U.lo, U.ln);
    p.ob(2, 15, 10, 22, U.lo, U.ln); p.r(2, 15, 10, 5, U.hi); p.r(2, 20, 10, 1, U.mid);
    p.ob(68, 15, 10, 22, U.lo, U.ln); p.r(68, 15, 10, 5, U.hi); p.r(68, 20, 10, 1, U.mid);
    p.r(5, 38, 2, 3, M.mid); p.r(73, 38, 2, 3, M.mid); p.r(38, 38, 2, 2, M.lo);
  },
});

def("lounge_chair", {
  name: "Tub lounge chair", cat: "Seating", size: [34, 38], anchor: [17, 36], facings: ["down", "left", "right"], uses: ["uph", "metal"],
  body: [-13, -12, 26, 11], note: "A round-backed tub chair. Left and right are mirror images, as the library already does for armchairs.",
  draw(p, o, f) {
    const U = o.uph, M = o.metal;
    p.shadow(17, 35, 14, 2);
    if (f === "down") {
      p.ob(5, 20, 24, 11, U.lo, U.ln);                                        // front of the tub
      p.r(5, 20, 24, 2, U.mid);
      p.oell(17, 16, 12, 8, U.mid, U.ln);                                      // the back
      p.ell(17, 11, 9, 2, U.hi);
      p.oell(17, 20, 8, 4, lit(U.mid, .16), U.lo);                             // seat cushion
      p.r(7, 31, 2, 4, M.mid); p.r(25, 31, 2, 4, M.mid);
      return;
    }
    // facing left: the back stands on the right; mirrored for right
    p.ob(5, 20, 22, 10, U.lo, U.ln);
    p.ob(6, 15, 18, 6, lit(U.mid, .16), U.ln);                                // seat cushion, from the side
    p.r(6, 15, 18, 1, lit(U.mid, .3));
    p.ob(22, 5, 7, 25, U.mid, U.ln); p.r(22, 5, 7, 3, U.hi); p.r(22, 8, 7, 1, U.lo);
    p.ob(5, 21, 18, 4, U.mid, U.ln); p.r(5, 21, 18, 1, U.hi);                 // the near arm
    p.r(7, 30, 2, 4, M.mid); p.r(25, 30, 2, 4, M.mid);
  },
});

def("bench_modern", {
  name: "Upholstered bench", cat: "Seating", size: [66, 26], anchor: [33, 24], body: [-30, -12, 60, 11], uses: ["uph", "metal"],
  note: "A backless waiting bench with a buttoned top, for the wall by the entrance.",
  draw(p, o) {
    const U = o.uph, M = o.metal;
    p.shadow(33, 24, 32, 2);
    const b = p.box3(2, 12, 62, 10, 10, lit(U.mid, .14), U.lo, U.ln);
    p.r(2, b.topY, 62, 1, U.hi);
    for (let x = 8; x < 62; x += 8) { p.px(x, b.topY + 4, U.lo); p.px(x + 4, b.topY + 7, U.lo); }
    p.r(2, b.frontY, 62, 2, U.mid);
    p.r(5, 22, 2, 2, M.mid); p.r(59, 22, 2, 2, M.mid);
  },
});

def("coffee_table_round", {
  name: "Round marble coffee table", cat: "Tables", size: [48, 34], anchor: [24, 31], body: [-17, -9, 34, 9], uses: ["finish", "metal"],
  note: "A round stone top on a gold pedestal, dressed with a tray and a stack of books.",
  draw(p, o) {
    const T = ramp(o.finish.top), M = o.metal;
    p.shadow(24, 30, 19, 3);
    p.ob(21, 18, 6, 10, M.mid, M.ln); p.r(21, 18, 2, 10, M.hi); p.r(25, 18, 2, 10, M.lo);
    p.oell(24, 29, 7, 1, M.lo, M.ln);
    p.oell(24, 15, 21, 8, T.lo, T.ln);
    p.ell(24, 13, 21, 8, T.mid);
    p.ell(22, 11, 15, 4, T.hi);
    p.px(15, 15, T.lo); p.px(16, 16, T.lo); p.px(32, 9, T.lo); p.px(33, 10, T.lo); p.px(34, 10, T.lo);
    p.oell(17, 12, 5, 2, M.mid, M.ln); p.ell(17, 12, 3, 1, M.lo);              // brass tray
    p.ob(27, 10, 8, 2, "#2a447e", "#121828"); p.ob(28, 8, 7, 2, "#e3dccd", "#5d564a"); p.ob(27, 6, 8, 2, "#8a2433", "#2a0a10");
  },
});

def("side_table", {
  name: "Drum side table", cat: "Tables", size: [20, 28], anchor: [10, 26], body: [-7, -6, 14, 6], uses: ["finish", "metal"],
  note: "A gold drum with a stone top and a bud vase, for the ends of a sofa.",
  draw(p, o) {
    const T = ramp(o.finish.top), M = o.metal;
    p.shadow(10, 26, 8, 2);
    p.ob(3, 14, 14, 11, M.mid, M.ln); p.r(3, 14, 4, 11, M.hi); p.r(13, 14, 4, 11, M.lo);
    for (let y = 16; y < 25; y += 3) p.r(3, y, 14, 1, M.lo);
    p.oell(10, 13, 7, 3, T.mid, T.ln); p.ell(9, 12, 5, 1, T.hi);
    p.ob(9, 6, 3, 6, "#e9edf1", "#7f8a94"); p.r(10, 1, 1, 5, "#5b7a3a"); p.r(9, 0, 3, 2, "#e8a3a0"); p.px(10, 0, "#f6d0cd");
  },
});

def("arc_lamp", {
  name: "Arc floor lamp", cat: "Lighting", size: [50, 86], anchor: [8, 84], body: [-5, -4, 10, 4], uses: ["metal"],
  note: "A tall gold arc over the seating with a glowing globe and a soft pool of light on the floor.",
  draw(p, o) {
    const M = o.metal;
    p.ell(40, 80, 15, 4, "rgba(255,220,150,.10)"); p.ell(40, 80, 9, 2, "rgba(255,220,150,.10)");
    p.shadow(8, 84, 7, 2);
    p.oell(8, 82, 6, 2, "#e7e3dc", "#6e6a63"); p.ell(7, 81, 4, 1, "#f6f3ee");
    const pts = [];
    for (let y = 81; y >= 22; y--) pts.push([7, y]);
    for (let t = 0; t <= 1; t += .01) { const u = 1 - t; pts.push([u * u * u * 7 + 3 * u * u * t * 7 + 3 * u * t * t * 40 + t * t * t * 40, u * u * u * 22 + 3 * u * u * t * 0 + 3 * u * t * t * 0 + t * t * t * 18]); }
    for (const [x, y] of pts) p.r(x - 1, y, 3, 1, M.ln);
    for (const [x, y] of pts) p.r(x, y, 1, 1, M.mid);
    for (const [x, y] of pts.slice(0, 60)) p.px(x - 1, y, M.hi);
    p.r(40, 18, 1, 4, M.lo);
    p.ell(40, 26, 10, 10, "rgba(255,225,160,.12)");
    p.oell(40, 26, 5, 5, "#fff1cf", "#8a7650"); p.ell(39, 25, 3, 3, "#fffaf0"); p.px(38, 24, "#ffffff");
  },
});

def("planter_fig", {
  name: "Fiddle-leaf fig, tall planter", cat: "Plants", size: [34, 66], anchor: [17, 64], body: [-9, -8, 18, 8], uses: ["metal"],
  note: "Big glossy leaves in a matte black cylinder with a gold rim. For corners.",
  draw(p, o) {
    const M = o.metal;
    p.shadow(17, 64, 12, 2);
    p.ob(9, 44, 16, 20, "#24242a", "#0b0b0d"); p.r(9, 44, 4, 20, "#3a3a43"); p.r(21, 44, 4, 20, "#1a1a1e");
    p.r(9, 44, 16, 2, M.mid); p.r(9, 44, 16, 1, M.hi);
    p.ell(17, 45, 6, 1, "#3b2a1e");
    p.r(16, 26, 2, 19, "#5a3e28"); p.px(16, 30, "#7a5638");
    const R = rng(21), leaves = [];
    for (let i = 0; i < 24; i++) { const a = R() * Math.PI * 2, d = Math.sqrt(R()); leaves.push([17 + Math.cos(a) * d * 12, 21 + Math.sin(a) * d * 15]); }
    leaves.sort((a, b) => a[1] - b[1]);
    for (const [x, y] of leaves) { p.oell(Math.round(x), Math.round(y), 4, 3, LEAF.mid, LEAF.ln); p.r(Math.round(x) - 2, Math.round(y) - 1, 2, 1, LEAF.hi); p.px(Math.round(x), Math.round(y) + 1, LEAF.lo); }
  },
});

def("planter_snake", {
  name: "Snake plant, ribbed planter", cat: "Plants", size: [24, 50], anchor: [12, 48], body: [-7, -6, 14, 6], uses: [],
  note: "Upright banded leaves in a white ribbed pot. Narrow enough for beside a door.",
  draw(p) {
    p.shadow(12, 48, 9, 2);
    p.ob(5, 33, 14, 15, "#ece9e3", "#7f7a70");
    for (let x = 6; x < 19; x += 2) p.r(x, 34, 1, 13, "#d3cfc6");
    p.r(5, 33, 14, 1, "#fbfaf7");
    const R = rng(9);
    const leaves = [[7, 24, -2], [10, 30, -.6], [12, 33, .3], [15, 27, 1.4], [17, 20, 2.2], [9, 18, -3], [13, 22, .9]];
    for (const [bx, hgt, lean] of leaves) {
      for (let t = 0; t < hgt; t++) {
        const y = 33 - t, x = Math.round(bx + lean * t / 10), w = t < hgt * .6 ? 3 : t < hgt * .85 ? 2 : 1;
        const band = Math.floor((t + bx) / 4) % 2 ? "#2e5a2e" : "#3f7a3a";
        p.r(x - 1, y, w + 1, 1, "#16301a"); p.r(x, y, w, 1, band);
        if (w === 3) { p.px(x, y, "#c7c46a"); p.px(x + 2, y, "#c7c46a"); }
      }
    }
    p.r(6, 33, 12, 1, "#3b2a1e");
  },
});

def("rug_round", {
  name: "Round deco rug", cat: "Rugs", size: [180, 124], anchor: [90, 62], body: null, mount: "flat", uses: ["rug", "metal"],
  note: "A large oval rug with art-deco rays and a medallion, to anchor the lounge.",
  draw(p, o) {
    const C = o.rug, G = o.metal.mid, Gl = o.metal.lo, cx = 90, cy = 62;
    p.ell(cx, cy, 89, 61, C.dk);
    p.ell(cx, cy, 87, 59, G);
    p.ell(cx, cy, 86, 58, C.field2);
    p.ell(cx, cy, 80, 53, Gl); p.ell(cx, cy, 79, 52, C.field);
    for (let i = 0; i < 32; i++) {
      const a = i / 32 * Math.PI * 2, c = Math.cos(a), s = Math.sin(a) * .68;
      for (let r = 26; r < 74; r += (i % 2 ? 4 : 2)) p.px(cx + c * r, cy + s * r, i % 2 ? Gl : G);
    }
    for (let i = 0; i < 24; i++) { const a = i / 24 * Math.PI * 2, x = cx + Math.cos(a) * 83, y = cy + Math.sin(a) * 55.5; p.px(x, y - 1, G); p.r(x - 1, y, 3, 1, G); p.px(x, y + 1, G); }
    p.ell(cx, cy, 25, 17, G); p.ell(cx, cy, 24, 16, C.field2);
    p.ell(cx, cy, 15, 10, Gl); p.ell(cx, cy, 14, 9, C.dk);
    p.ell(cx, cy, 5, 3, G);
    p.ring(cx, cy, 20, 13.5, G, 40);
  },
});

def("runner", {
  name: "Entrance runner", cat: "Rugs", size: [56, 320], anchor: [28, 160], body: null, mount: "flat", uses: ["rug", "metal"],
  note: "A long runner from the street door to the casino door, so the way through reads at a glance. 56 wide, full room depth.",
  draw(p, o) {
    const C = o.rug, G = o.metal.mid, Gl = o.metal.lo;
    p.r(0, 0, 56, 320, C.dk); p.r(1, 0, 54, 320, C.field2);
    p.r(4, 0, 1, 320, G); p.r(51, 0, 1, 320, G); p.r(7, 0, 1, 320, Gl); p.r(48, 0, 1, 320, Gl);
    p.r(8, 0, 40, 320, C.field);
    for (let y = 16; y < 320; y += 32) {
      for (let i = 0; i <= 7; i++) { p.px(28 - i, y - 7 + i, G); p.px(28 + i, y - 7 + i, G); p.px(28 - i, y + 7 - i, G); p.px(28 + i, y + 7 - i, G); }
      p.r(27, y - 1, 3, 3, G);
      p.px(28, y + 16, Gl); p.px(16, y + 16, Gl); p.px(40, y + 16, Gl);
    }
  },
});

def("stanchion_ns", {
  name: "Queue posts, running north–south", cat: "Reception", size: [14, 94], anchor: [7, 92], body: [-3, -64, 6, 64], uses: ["uph", "metal"],
  note: "Two posts 64 px apart with a velvet rope in the upholstery colour, to make a queue lane at the desk.",
  draw(p, o) {
    const M = o.metal, U = o.uph;
    p.r(5, 8, 4, 64, U.ln); p.r(6, 8, 2, 64, U.mid); p.r(6, 8, 1, 64, U.hi);
    for (const b of [28, 92]) post(p, 7, b, M);
  },
});
def("stanchion_ew", {
  name: "Queue posts, running east–west", cat: "Reception", size: [72, 30], anchor: [36, 28], body: [-33, -4, 66, 4], uses: ["uph", "metal"],
  note: "The same posts across the room, the rope dipping between them.",
  draw(p, o) {
    const M = o.metal, U = o.uph;
    for (let x = 4; x <= 68; x++) { const t = (x - 4) / 64, y = 7 + Math.round(4 * t * (1 - t) * 6); p.r(x, y - 1, 1, 4, U.ln); p.r(x, y, 1, 2, U.mid); p.px(x, y, U.hi); }
    post(p, 4, 28, M); post(p, 68, 28, M);
  },
});
function post(p, x, b, M) {
  p.shadow(x, b, 5, 1.5);
  p.oell(x, b - 1, 4, 1, M.mid, M.ln); p.ell(x - 1, b - 2, 2, 0, M.hi);
  p.ob(x - 1, b - 21, 2, 20, M.mid, M.ln); p.r(x - 1, b - 21, 1, 20, M.hi);
  p.oell(x, b - 22, 2, 2, M.mid, M.ln); p.px(x - 1, b - 23, M.hi);
}

def("atm", {
  name: "Cash machine", cat: "Services", size: [32, 56], anchor: [16, 54], body: [-13, -12, 26, 12], uses: ["metal"],
  interact: "atm",
  note: "A slim modern ATM with a glowing screen and a gold CASH header. Faces the room from the back wall.",
  draw(p, o) {
    const M = o.metal;
    p.shadow(16, 54, 15, 2);
    const b = p.box3(3, 42, 26, 12, 38, "#3a3c45", "#2a2c33", "#0b0b0e");
    p.r(3, b.topY, 26, 1, "#55586a");
    p.r(3, b.frontY + 1, 26, 6, "#16171b"); p.r(3, b.frontY + 1, 26, 1, M.mid); p.r(3, b.frontY + 7, 26, 1, M.lo);
    text(p, "CASH", 16 - textW("CASH") / 2, b.frontY + 2, M.hi);
    p.ob(8, b.frontY + 10, 16, 10, "#1f8f8a", "#0b0b0e"); p.r(8, b.frontY + 10, 16, 2, "#4fd6c8"); p.r(9, b.frontY + 14, 8, 1, "#bff3ec"); p.r(9, b.frontY + 16, 11, 1, "#7fe0d4");
    for (let j = 0; j < 3; j++) for (let i = 0; i < 3; i++) p.r(8 + i * 3, b.frontY + 23 + j * 3, 2, 2, "#8b8f9b");
    p.r(19, b.frontY + 24, 5, 1, "#0b0b0e"); p.px(23, b.frontY + 26, "#5fe07a");
    p.r(8, b.frontY + 33, 16, 2, "#0b0b0e");
    p.r(3, b.frontY, 1, 38, "#3c3f4a");
  },
});

def("info_kiosk", {
  name: "Information kiosk", cat: "Services", size: [24, 60], anchor: [12, 58], body: [-7, -6, 14, 6], uses: ["metal"],
  note: "A slim touch-screen totem with a floor map of the casino.",
  draw(p, o) {
    const M = o.metal;
    p.shadow(12, 58, 10, 2);
    p.ob(5, 52, 14, 6, "#2a2c33", "#0b0b0e"); p.r(5, 52, 14, 1, M.mid);
    const b = p.box3(7, 46, 10, 6, 42, "#3a3c45", "#25272d", "#0b0b0e");
    p.ob(8, b.frontY + 2, 8, 20, "#0f2633", "#05080b");
    p.r(8, b.frontY + 2, 8, 2, "#1e5f80");
    p.r(9, b.frontY + 6, 3, 3, "#c9a24a"); p.r(13, b.frontY + 6, 2, 5, "#4b8fbf"); p.r(9, b.frontY + 10, 3, 4, "#8a2433"); p.r(13, b.frontY + 12, 2, 3, "#2f8f6a");
    p.r(9, b.frontY + 16, 6, 1, "#6fb7e0"); p.px(10, b.frontY + 18, "#ffffff");
    p.r(10, b.frontY + 25, 4, 4, M.mid); p.px(12, b.frontY + 26, "#111"); p.r(12, b.frontY + 27, 1, 2, "#111");
  },
});

def("dice_sculpture", {
  name: "Gold dice on a plinth", cat: "Feature", size: [40, 66], anchor: [20, 64], body: [-13, -14, 26, 14], uses: ["finish", "metal"],
  note: "A feature piece: two oversized gold dice on a stone plinth with a gold band. Something to walk past on the way in.",
  draw(p, o) {
    const M = o.metal, T = ramp(o.finish.top);
    p.shadow(20, 64, 17, 2);
    const b = p.box3(7, 50, 26, 14, 24, T.hi, T.mid, T.ln);
    p.r(7, b.frontY + 2, 26, 2, M.mid); p.r(7, b.frontY + 2, 26, 1, M.hi); p.r(7, b.bottom - 3, 26, 3, T.lo);
    die(p, 9, 10, 13, M, [[3, 3], [9, 3], [6, 6], [3, 9], [9, 9]], [[3, 2], [9, 5]]);
    die(p, 20, 17, 11, M, [[3, 3], [7, 7]], [[2, 2], [5, 3], [8, 4]]);
  },
});
function die(p, x, y, s, M, frontPips, topPips) {
  const th = Math.round(s * .55);
  p.r(x - 1, y - 1, s + 2, th + s + 2, M.ln);
  p.r(x, y, s, th, M.hi); p.r(x, y + th, s, s, M.mid); p.r(x, y + th, s, 1, M.lo); p.r(x + s - 2, y + th, 2, s, M.lo);
  for (const [a, b] of frontPips) p.r(x + a * s / 13, y + th + b * s / 13, 2, 2, "#1a1410");
  for (const [a, b] of topPips) p.px(x + a * s / 13 + 1, y + b * th / 7, "#1a1410");
}

def("console_flowers", {
  name: "Console with flowers", cat: "Feature", size: [60, 64], anchor: [30, 62], body: [-25, -8, 50, 8], uses: ["finish", "metal"],
  note: "A slim gold console against the back wall with a tall arrangement of white and blush flowers.",
  draw(p, o) {
    const M = o.metal, T = ramp(o.finish.top);
    p.shadow(30, 62, 27, 2);
    p.ob(6, 40, 2, 21, M.mid, M.ln); p.ob(52, 40, 2, 21, M.mid, M.ln); p.ob(8, 56, 44, 2, M.lo, M.ln);
    p.ob(4, 30, 52, 8, T.mid, T.ln); p.r(4, 30, 52, 2, T.hi); p.ob(4, 38, 52, 3, T.lo, T.ln);
    p.ob(26, 20, 8, 12, "#eef0f2", "#7d8790"); p.r(26, 20, 2, 12, "#ffffff"); p.r(32, 20, 2, 12, "#c9d0d6");
    const R = rng(33);
    for (let i = 0; i < 14; i++) { const x = 30 + (R() - .5) * 26, y = 13 + (R() - .5) * 12; p.r(x, y, 3, 2, LEAF.lo); p.px(x + 1, y, LEAF.mid); }
    const bloom = [["#f7f2ea", "#b7a99a"], ["#e6aaa3", "#8e5550"], ["#f7f2ea", "#b7a99a"], ["#e2c26a", "#8d6a28"]];
    for (let i = 0; i < 16; i++) { const [c, l] = bloom[i % 4], x = Math.round(30 + (R() - .5) * 22), y = Math.round(10 + (R() - .5) * 16); p.oell(x, y, 2, 2, c, l); p.px(x, y, l); }
  },
});

def("jackpot_screen", {
  name: "Jackpot display", cat: "Wall", size: [108, 34], anchor: [54, 34], body: null, mount: "wall", uses: ["metal"], screen: { show: "jackpot", rect: [4, 13, 100, 15] },
  note: "A wall-mounted LED board; the game draws the live progressive jackpot on it.",
  draw(p, o) {
    const M = o.metal;
    p.r(0, 0, 108, 34, "#060608"); p.r(1, 1, 106, 32, M.lo); p.r(2, 2, 104, 30, "#0d0d10");
    p.r(4, 4, 100, 26, "#040405");
    const t = "JACKPOT"; text(p, t, 54 - textW(t) / 2, 6, M.hi);   // (the game draws the live amount in `screen`)
    for (let y = 4; y < 30; y += 2) p.r(4, y, 100, 1, "rgba(0,0,0,.28)");
    p.r(2, 2, 104, 1, "rgba(255,255,255,.08)");
  },
});

def("art_canvas", {
  name: "Abstract canvas", cat: "Wall", size: [44, 36], anchor: [22, 36], body: null, mount: "wall", uses: ["metal", "rug"],
  note: "A framed modern canvas in the rug colours, for the back wall.",
  draw(p, o) {
    const M = o.metal, C = o.rug;
    p.r(0, 0, 44, 36, M.ln); p.r(1, 1, 42, 34, M.mid); p.r(1, 1, 42, 1, M.hi);
    p.r(3, 3, 38, 30, "#eee6d8");
    p.ell(16, 17, 9, 9, C.field); p.ell(15, 16, 8, 8, lit(C.field, .12));
    for (let y = 0; y < 9; y++) { const hw = Math.round(Math.sqrt(81 - y * y)); p.r(29 - hw, 25 - y, hw, 1, "#d79f97"); }
    p.ring(28, 13, 7, 7, M.lo, 30);
    p.r(6, 28, 30, 1, "#1c1c20");
  },
});


/* ================================================================ rendering, for the build tool */
// Mike's picks on the mockup (2026-10-22): white quartz desk with charcoal flutes, emerald velvet, charcoal-and-gold
// rugs, brushed gold.
const LOOK = { finish: "quartz", uph: "emerald", rug: "charcoal", metal: "gold" };
const FLOOR_TILES = {
  porcelain: { name: "Pale porcelain slabs", gen: () => slabTile("#d8d4cb", "#bdb7ab", "#c8c3b8", 7) },
  basalt: { name: "Polished basalt slabs", gen: () => slabTile("#2a2a2f", "#18181b", "#36363d", 11) },
};

function renderPiece(d, o, f) {
  const p = new P(d.size[0], d.size[1]);
  d.draw(p, o, f);
  return p.c.toDataURL("image/png");
}

// Every piece's pictures (one per drawn facing; the tub chair's right is its left mirrored) and the floor tiles.
function renderAll(look) {
  const o = opts(Object.assign({}, LOOK, look || {}));
  const out = { pieces: {}, floors: {} };
  for (const d of Object.values(PIECES)) {
    const pictures = {};
    for (const f of d.facings) if (!(d.id === "lounge_chair" && f === "right")) pictures[f] = renderPiece(d, o, f);
    out.pieces[d.id] = { name: d.name, cat: d.cat, size: d.size, anchor: d.anchor, body: d.body, facings: d.facings,
                         mount: d.mount, screen: d.screen || null, interact: d.interact || null, pictures };
  }
  for (const [k, t] of Object.entries(FLOOR_TILES)) out.floors[k] = { name: t.name, png: t.gen().toDataURL("image/png") };
  return out;
}
