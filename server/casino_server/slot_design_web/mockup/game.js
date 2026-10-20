/* The Slot design wizard's mockup: the signed-off Armadillo mockup (docs/slots/mockup/game.js) made to play any
   design. The full-screen slot game: reels, feature choreography, wins, the deck, the shared meters, and the four
   bonus scenes (Trail, Combo Free Games, the wave battle, the island voyage, Jackpot Pick), drawn on one 1280x720 canvas laid out the way the Godot
   SlotScreen is. createGame(canvas, cfg) plays cfg.variant (a SlotMath variant) with cfg's art, logo, background,
   frame, theme and texts (design.js builds cfg from a design); setConfig swaps them live, destroy stops it. */
export function createGame(cv, cfg) {
  "use strict";
  const M = window.SlotMath;
  let V = cfg.variant;
  const ctx = cv.getContext("2d");
  const W = 1280, H = 720;
  const CELL_W = 150, CELL_H = 112, REEL_X = 265, REEL_Y = 128;
  const REEL_W = CELL_W * 5, REEL_H = CELL_H * 4;
  let DISPLAY = '"Rye", "Cinzel", Georgia, serif';
  let COND = '"Barlow Condensed", "Arial Narrow", system-ui, sans-serif';
  const C = {
    gold: "#f4c94f", goldHi: "#fff1b0", goldLo: "#9a6614", ink: "#2b1004", shade: "#1a0b03", cream: "#f6ead0",
    tiers: { mini: "#4fb3ff", minor: "#55d07a", major: "#c768ff", grand: "#ff5a48" },
    edge: "#d9a54a", muted: "#b89b74", win: "#ffe27a", spin: "#f0b43a", alert: "#7d130c",
  };
  const C0 = Object.assign({}, C);   // Armadillo's look: a design's theme (Sprites step) is laid over it
  let FRAME = { style: "wood", colour: C.edge }, TEXT = {}, LABELS = true;
  let SKIN = { base: "classic" };   // the Scene step's skin: its shapes, palette, decor and words
  const lc = () => SKIN.base === "lcars";
  const VOYAGE_TEXT = { name: "DEAD MAN'S MAP", hint: "choose your next island", start: "TORTUGA", final: "ISLA DE MUERTA",
    treasure: "TREASURE ISLAND", wreck: "SHIPWRECK", skull: "SKULL ISLAND", port: "PORT ROYAL", cove: "HIDDEN COVE", relic: "RELIC",
    chest: "LEGENDARY TREASURE", legend: "THE LEGEND", artefacts: ["COMPASS", "MEDALLION", "SPYGLASS", "CUTLASS"] };
  // The deck's look (Scene step): the bottom bar, the readout boxes and the buttons. Wood untinted is Armadillo's
  // browns; any other style or a tint derives the set from one base colour (slot_screen.gd's _deck_look matches).
  const DECK_BASE = { wood: "#6e4426", metal: "#5d6470", neon: "#2b2470", glass: "#5a6f96" };
  const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const dark = (h, t, a = 1) => `rgba(${hexRgb(h).map((v) => Math.round(v * (1 - t))).join(",")},${a})`;
  const light = (h, t) => `rgb(${hexRgb(h).map((v) => Math.round(v + (255 - v) * t)).join(",")})`;
  const hex = (c) => "#" + c.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
  const mix = (h, to, t) => { const q = hexRgb(to); return hex(hexRgb(h).map((v, i) => v + (q[i] - v) * t)); };
  const alpha = (h, a) => `rgba(${hexRgb(h).join(",")},${a})`;
  // Every tone the screen draws comes from the design's colours (Sprites step), so a design inherits none of
  // Armadillo's browns: shade backs the banners, pop-ups and dimming; goldLo is the dark end of gold and coins.
  const spinBtn = () => [C.goldHi, C.spin, dark(C.spin, 0.4)];
  const fireBtn = () => { const hot = hex(hexRgb(C.alert).map((v) => v * 1.8)); return [light(hot, 0.6), hot, C.alert]; };
  function deckLook(d, frameColour) {
    if (d.style === "wood" && !d.colour) return { band: "rgba(12,5,2,0.86)", box: "#1a0c05", boxEdge: "#7a5a36",
      inset: "rgba(20,9,4,0.65)", buy: "rgba(40,18,6,0.85)", buyHover: "rgba(90,40,10,0.95)",
      btn: ["#6e4426", "#4a2a14", "#2c1609"], ring: "#1a0b03" };
    const b = d.colour || DECK_BASE[d.style] || DECK_BASE.metal, glass = d.style === "glass";
    return { band: glass ? dark(b, 0.75, 0.62) : dark(b, 0.9, 0.88), box: dark(b, 0.82, glass ? 0.6 : 1),
      boxEdge: d.style === "neon" ? frameColour : light(b, 0.12), inset: dark(b, 0.8, 0.65),
      buy: dark(b, 0.7, 0.85), buyHover: dark(b, 0.45, 0.95), btn: [b, dark(b, 0.33), dark(b, 0.6)], ring: dark(b, 0.85) };
  }
  let DECK = deckLook({ style: "wood" }, C.edge);
  // Win animations by tier group (Sprites step): what a symbol does while its line win shows.
  const WIN0 = { wild: { preset: "glow", strength: 1, colour: C.win }, high: { preset: "none" }, mid: { preset: "none" },
                 low: { preset: "none" }, scatter: { preset: "none" } };
  let WIN = WIN0;
  const groupOf = (sym) => sym === "W" ? "wild" : sym === "BS" || sym === "FS" ? "scatter" : sym[0] === "H" ? "high" : sym[0] === "M" ? "mid" : "low";
  const LINE_COLOURS = ["#ffd54a", "#ff7a59", "#5fd4ff", "#9cff6b", "#ff6bd5", "#ffb347", "#6b9dff", "#d0ff4a", "#ff4a6e",
    "#4affc3", "#ffe0a3", "#b38bff", "#ff9e4a", "#4ad2ff", "#e3ff7a", "#ff7ab8", "#7affd9", "#ffcf4a", "#a6b8ff",
    "#ff6a4a", "#4aff8f", "#ffa6e1", "#c6ff4a", "#4a9eff", "#ffd1a6"];
  const rng = M.mulberry32((Date.now() & 0xffffff) ^ 0x5eed);
  const money = (p) => "\u00a3" + (p / 100).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const moneyShort = (p) => p >= 100000 ? "\u00a3" + Math.round(p / 100).toLocaleString("en-GB") : money(p);

  // ------------------------------------------------------------------ art and look (from cfg)
  let ART = {}, logoImg = null, bgImg = null;
  const load = (url) => { if (!url) return null; const im = new Image(); im.src = url; return im; };
  const ok = (im) => im && im.complete && im.naturalWidth > 0;
  const img = (n) => ART[n];
  const drawImg = (im, ...a) => { if (ok(im)) ctx.drawImage(im, ...a); };   // a design may not have every picture yet
  function setConfig(c) {
    cfg = c;
    if (c.variant && c.variant !== V) V = c.variant;
    const art = {};
    for (const [n, url] of Object.entries(c.art || {})) art[n] = ART[n] && ART[n].src.endsWith(url) ? ART[n] : load(url);
    ART = art;
    logoImg = c.logo ? (logoImg && logoImg.src.endsWith(c.logo) ? logoImg : load(c.logo)) : null;
    bgImg = c.background ? (bgImg && bgImg.src.endsWith(c.background) ? bgImg : load(c.background)) : null;
    const t = c.theme || {};
    if (t.display) DISPLAY = t.display;
    if (t.cond) COND = t.cond;
    Object.assign(C, C0, t.colours || {});
    WIN = Object.assign({}, WIN0, c.win || {});
    FRAME = Object.assign({ style: "wood", colour: C.edge }, c.frame || {});
    DECK = deckLook(c.deck || { style: FRAME.style }, FRAME.colour);
    TEXT = Object.assign({ tagline: "GOOD LUCK", title: [V.name.toUpperCase()], bonus: ["3+ BONUS", "TRAIL BONUS"],
                           free: ["3+ FREE SPINS", "3 COMBO FREE GAMES"], trailHint: "fire to move along the trail",
                           pistol: "THE PISTOL", freeName: "COMBO FREE GAMES", battle: "RED ALERT", battleHint: "tap a ship to fire",
                           enemy: "ENEMY SHIP", boss: "FLAGSHIP", voyage: VOYAGE_TEXT }, c.texts || {});
    LABELS = c.labels !== false;
    SKIN = c.skin || { base: "classic" };
    if (SKIN.texts && SKIN.texts.tagline) TEXT.tagline = SKIN.texts.tagline;
  }
  setConfig(cfg);

  // ------------------------------------------------------------------ state
  const S = {
    balance: 100000, betIdx: 3, busy: false, mode: "reels", turbo: false, speed: 1, auto: 0, autoMenu: false,
    grid: null, landed: false, wins: [], showLines: [], cycle: 0, cycleAt: 0, winShown: 0, winTarget: 0,
    message: "25 LINES \u00b7 " + TEXT.tagline, featureLit: {}, multiplier: 1, cellFx: {}, banner: null,
    overlay: null, particles: [], tweens: [], waits: [], hurry: false, hits: [], free: null, colossal: null,
    trail: null, battle: null, voyage: null, pick: null, rig: { features: [], trigger: null, jackpot: null }, shake: 0, flyers: [],
    meters: {}, metersShown: {}, now: 0, hover: null, roller: null,
  };
  for (const t of M.JACKPOT_TIERS) {
    const start = t.seed + Math.round(t.seed * (0.15 + 0.5 * rng()));
    S.meters[t.id] = start; S.metersShown[t.id] = start;
  }
  const bet = () => M.LADDER[S.betIdx];

  // Reels: each spins its own strip; a Colossal group spins the big strip as one wide reel.
  const reels = [0, 1, 2, 3, 4].map((r) => ({ r, pos: rng() * 50, spinning: false, v: 0, strip: V.strips[r], glow: 0 }));
  S.grid = M.gridFromStops(V.strips, reels.map((x) => Math.floor(x.pos)));
  reels.forEach((x, r) => { x.pos = Math.floor(x.pos); });

  // ------------------------------------------------------------------ time, tweens, waits
  const ease = {
    out: (t) => 1 - Math.pow(1 - t, 3), inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    back: (t) => { const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); }, lin: (t) => t,
  };
  const pace = () => S.speed * (S.turbo ? 1.8 : 1);
  function wait(sec) {
    return new Promise((res) => S.waits.push({ until: S.now + sec, res, hurryable: true }));
  }
  function tween(obj, props, dur, e = ease.out) {
    return new Promise((res) => {
      const from = {};
      for (const k in props) from[k] = obj[k];
      S.tweens.push({ obj, from, to: props, t: 0, dur: Math.max(0.001, dur), e, res });
    });
  }
  function update(dt) {
    S.now += dt;
    for (const w of S.waits.slice()) {
      if (S.now >= w.until || (S.hurry && w.hurryable)) { S.waits.splice(S.waits.indexOf(w), 1); w.res(); }
    }
    for (const tw of S.tweens.slice()) {
      tw.t += dt / tw.dur;
      const k = tw.e(Math.min(1, tw.t));
      for (const p in tw.to) tw.obj[p] = tw.from[p] + (tw.to[p] - tw.from[p]) * k;
      if (tw.t >= 1) { S.tweens.splice(S.tweens.indexOf(tw), 1); tw.res(); }
    }
    for (const x of reels) if (x.spinning) x.pos -= x.v * dt;
    for (const id in S.meters) S.metersShown[id] += (S.meters[id] - S.metersShown[id]) * Math.min(1, dt * 4);
    if (S.winShown < S.winTarget) S.winShown = Math.min(S.winTarget, S.winShown + Math.max(1, S.roller || 1) * dt);
    for (const p of S.particles) { p.vy += p.g * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.spin += p.vs * dt; p.life -= dt; }
    S.particles = S.particles.filter((p) => p.life > 0 && p.y < H + 60);
    S.shake = Math.max(0, S.shake - dt * 2.5);
    if (!S.busy && S.wins.length && S.now > S.cycleAt) { S.cycle = (S.cycle + 1) % (S.wins.length + 1); S.cycleAt = S.now + 1.4; }
  }

  // ------------------------------------------------------------------ the floor's other players feed the meters
  const feeder = setInterval(() => {
    for (let i = 0; i < 5; i++) if (rng() < 0.3) contribute(M.LADDER[1 + Math.floor(rng() * 4)]);
  }, 1000);
  function contribute(b) { for (const t of M.JACKPOT_TIERS) S.meters[t.id] += b * t.rate; }

  // ------------------------------------------------------------------ drawing helpers
  function rr(x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  // maxW: shrink to fit that width (so a theme's longer names never spill out of their boxes)
  function text(str, x, y, size, font = COND, colour = C.cream, align = "center", weight = "700", stroke = 0, maxW = 0) {
    ctx.font = `${weight} ${size}px ${font}`;
    if (maxW > 0) {
      const w = ctx.measureText(str).width;
      if (w > maxW) { size = Math.max(10, Math.floor(size * maxW / w)); ctx.font = `${weight} ${size}px ${font}`; }
    } ctx.textAlign = align; ctx.textBaseline = "middle";
    if (stroke) { ctx.lineWidth = stroke; ctx.strokeStyle = alpha(C.shade, 0.95); ctx.lineJoin = "round"; ctx.strokeText(str, x, y); }
    ctx.fillStyle = colour; ctx.fillText(str, x, y);
  }
  function goldText(str, x, y, size, font = DISPLAY) {
    ctx.font = `400 ${size}px ${font}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const g = ctx.createLinearGradient(0, y - size / 2, 0, y + size / 2);
    g.addColorStop(0, C.goldHi); g.addColorStop(0.45, C.gold); g.addColorStop(1, C.goldLo);
    ctx.lineJoin = "round"; ctx.lineWidth = size * 0.16; ctx.strokeStyle = C.ink; ctx.strokeText(str, x, y);
    ctx.fillStyle = g; ctx.fillText(str, x, y);
  }
  // Panels in the design's frame style (Scene step): wood (Armadillo's), metal, neon or glass, edged in its colour.
  function woodPanel(x, y, w, h, r = 14) {
    if (lc()) return lcarsPanel(x, y, w, h);
    if (FRAME.style !== "wood") return stylePanel(x, y, w, h, r);
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, "#8a5530"); g.addColorStop(0.5, "#5c341a"); g.addColorStop(1, "#3a1f0d");
    rr(x, y, w, h, r); ctx.fillStyle = g; ctx.fill();
    ctx.save(); ctx.clip(); ctx.globalAlpha = 0.12; ctx.strokeStyle = "#1e0d04"; ctx.lineWidth = 1.2;
    for (let i = 0; i < h; i += 7) { ctx.beginPath(); ctx.moveTo(x, y + i + Math.sin(i) * 2); ctx.bezierCurveTo(x + w * 0.3, y + i + 4, x + w * 0.7, y + i - 3, x + w, y + i + 1); ctx.stroke(); }
    ctx.restore();
    rr(x + 3, y + 3, w - 6, h - 6, r - 3); ctx.lineWidth = 3; ctx.strokeStyle = C.edge; ctx.stroke();
    rr(x, y, w, h, r); ctx.lineWidth = 2; ctx.strokeStyle = "#1a0b03"; ctx.stroke();
  }
  function stylePanel(x, y, w, h, r) {
    const col = FRAME.colour, st = FRAME.style;
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    if (st === "metal") { g.addColorStop(0, "#5d6470"); g.addColorStop(0.5, "#2c313a"); g.addColorStop(1, "#15181d"); }
    else if (st === "neon") { g.addColorStop(0, "rgba(10,8,30,0.92)"); g.addColorStop(1, "rgba(4,3,14,0.92)"); }
    else { g.addColorStop(0, "rgba(255,255,255,0.16)"); g.addColorStop(1, "rgba(10,14,30,0.55)"); }
    rr(x, y, w, h, r); ctx.fillStyle = g; ctx.fill();
    ctx.save();
    if (st === "neon") { ctx.shadowColor = col; ctx.shadowBlur = 18; }
    rr(x + 3, y + 3, w - 6, h - 6, Math.max(2, r - 3)); ctx.lineWidth = st === "neon" ? 3 : 3; ctx.strokeStyle = col; ctx.stroke();
    ctx.restore();
    rr(x, y, w, h, r); ctx.lineWidth = 2; ctx.strokeStyle = st === "glass" ? "rgba(255,255,255,0.35)" : "#0b0c10"; ctx.stroke();
  }
  function button(id, x, y, w, h, label, opts = {}) {
    const on = opts.on, disabled = opts.disabled, hover = S.hover === id && !disabled;
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    const base = opts.colour || (on ? [mix(C.gold, C.goldHi, 0.5), mix(C.gold, C.goldLo, 0.3), C.goldLo] : DECK.btn);
    g.addColorStop(0, base[0]); g.addColorStop(0.55, base[1]); g.addColorStop(1, base[2]);
    ctx.save(); if (disabled) ctx.globalAlpha = 0.4;
    if (lc()) {   // LCARS: a flat pill, its label on the right
      lcarsButton(x, y, w, h, opts.colour, hover, on);
      const tc = sc(part("button").text || "ink"), wide = w > 80 && label.length > 1;
      text(label, wide ? x + w - 12 : x + w / 2, y + h / 2 + 1, Math.min(opts.size || 22, h * 0.5), wide ? DISPLAY : COND, tc,
           wide ? "right" : "center", wide ? "400" : "700", 0, w - 20);
      ctx.restore();
      if (!disabled) S.hits.push({ id, x, y, w, h });
      return;
    }
    rr(x, y, w, h, h * 0.28); ctx.fillStyle = g; ctx.fill();
    ctx.lineWidth = hover ? 3 : 2; ctx.strokeStyle = hover ? C.goldHi : C.edge; ctx.stroke();
    text(label, x + w / 2, y + h / 2 + 1, opts.size || 22, COND, on || opts.colour ? C.ink : C.cream);
    ctx.restore();
    if (!disabled) S.hits.push({ id, x, y, w, h });
  }

  // ------------------------------------------------------------------ the skin's shapes (Scene step; slot_screen.gd's match)
  // A skin's colour: one of its names (palette, then the screen's colours) or a colour like #8fd3ff.
  const sc = (ref) => !ref ? C.edge : ref[0] === "#" ? ref : (SKIN.palette && SKIN.palette[ref]) || C[ref] || ref;
  const part = (p) => (SKIN.parts && SKIN.parts[p]) || {};
  const T = (key, fallback) => (SKIN.texts && SKIN.texts[key]) || fallback;
  // A bar with round ends (both, left, right or none): a half-circle each, or as round as a short bar allows.
  function pillPath(x, y, w, h, round = "both") {
    const L = round === "both" || round === "left", R = round === "both" || round === "right";
    const r = Math.min(h / 2, L && R ? w / 2 : w);
    ctx.beginPath();
    ctx.moveTo(x + (L ? r : 0), y);
    if (R) { ctx.arcTo(x + w, y, x + w, y + r, r); ctx.arcTo(x + w, y + h, x + w - r, y + h, r); } else { ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + h); }
    if (L) { ctx.lineTo(x + r, y + h); ctx.arcTo(x, y + h, x, y + h - r, r); ctx.arcTo(x, y, x + r, y, r); } else { ctx.lineTo(x, y + h); }
    ctx.closePath();
  }
  // An LCARS elbow: a vertical arm (arm wide) turning into a bar (bar high) through a rounded outer corner r, in
  // the box x,y,w,h, the turn at corner (tl, tr, bl, br).
  function elbowPath(x, y, w, h, corner, arm, bar, r) {
    r = Math.min(r, w, h);
    const ri = Math.max(2, Math.min(r * 0.45, w - arm, h - bar));
    const fx = corner[1] === "r", fy = corner[0] === "b";
    const P = (px, py) => [fx ? x + w - px : x + px, fy ? y + h - py : y + py];   // the tl shape, turned to its corner
    ctx.beginPath();
    ctx.moveTo(...P(w, 0)); ctx.lineTo(...P(r, 0)); ctx.arcTo(...P(0, 0), ...P(0, r), r); ctx.lineTo(...P(0, h)); ctx.lineTo(...P(arm, h));
    ctx.lineTo(...P(arm, bar + ri)); ctx.arcTo(...P(arm, bar), ...P(arm + ri, bar), ri); ctx.lineTo(...P(w, bar)); ctx.closePath();
  }
  // The background blurred, for glass to show (made once per background picture).
  let bgBlur = null, bgBlurOf = null;
  function blurred() {
    const src = ok(bgImg) ? bgImg.src : null, blur = (SKIN.glass && SKIN.glass.blur) || 0;
    if (!src || !blur) return null;
    if (bgBlurOf !== src + blur) {
      bgBlur = document.createElement("canvas"); bgBlur.width = W; bgBlur.height = H;
      const b = bgBlur.getContext("2d"); b.filter = `blur(${blur}px)`; b.drawImage(bgImg, -blur, -blur, W + blur * 2, H + blur * 2);
      bgBlurOf = src + blur;
    }
    return bgBlur;
  }
  // Frosted glass in the current path's shape: the blurred background, the tint, a sheen across the top, an edge.
  function glass(path, x, y, w, h, tint, edge, edgeW) {
    const G = SKIN.glass || {};
    ctx.save(); path(); ctx.clip();
    const bl = blurred();
    if (bl) ctx.drawImage(bl, 0, 0);
    ctx.globalAlpha = G.opacity != null ? G.opacity : 0.55; ctx.fillStyle = sc(tint || "glass"); ctx.fillRect(x, y, w, h);
    if (G.sheen) {
      const g = ctx.createLinearGradient(0, y, 0, y + Math.min(h, 80));
      g.addColorStop(0, `rgba(255,255,255,${G.sheen})`); g.addColorStop(1, "rgba(255,255,255,0)");
      ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.fillRect(x, y, w, Math.min(h, 80));
    }
    ctx.restore();
    const ew = edgeW != null ? edgeW : G.edge != null ? G.edge : 1.5;
    if (edge && ew > 0) { path(); ctx.lineWidth = ew; ctx.strokeStyle = sc(edge); ctx.stroke(); }
  }
  // An LCARS panel: elbows top and bottom on its spine side, the spine between in blocks, a glass body. The side
  // panels put the spine on the screen's edge; pop-ups on the left.
  function lcarsPanel(x, y, w, h) {
    const p = part("panel");
    if (p.shape === "glass") { glass(() => rr(x, y, w, h, 16), x, y, w, h, p.fill, p.edge); return; }
    // the side panels' spines run in the screen's margin, on its edge; a pop-up's on its left
    const right = x + w >= 1250, left = x <= 20, arm = left || right ? 16 : 14, bar = 14, gap = 4;
    const ox = left ? 4 : right ? x : x, ow = left ? x + w - 4 : right ? 1276 - x : w;   // the elbows' box
    const bx = left ? 4 + arm + gap : right ? x : x + arm + gap, bw = left ? x + w - 4 - bx : right ? 1276 - arm - gap - x - 4 : w - arm - gap;
    const eh = Math.min(110, h * 0.3);
    glass(() => rr(bx, y + bar + gap, bw, h - 2 * (bar + gap), 10), bx, y + bar + gap, bw, h - 2 * (bar + gap), p.fill, p.edge, 1);
    elbowPath(ox, y, ow, eh, right ? "tr" : "tl", arm, bar, 44); ctx.fillStyle = sc(p.top || "a"); ctx.fill();
    elbowPath(ox, y + h - eh, ow, eh, right ? "br" : "bl", arm, bar, 44); ctx.fillStyle = sc(p.bottom || "c"); ctx.fill();
    const spine = p.spine || ["b"], top = y + eh + gap, len = h - 2 * (eh + gap), seg = (len - gap * (spine.length - 1)) / spine.length;
    spine.forEach((c, i) => { ctx.fillStyle = sc(c); ctx.fillRect(right ? ox + ow - arm : ox, top + i * (seg + gap), arm, seg); });
  }
  function lcarsFrame() {
    const p = part("frame"), x = REEL_X - 22, y = REEL_Y - 18, w = REEL_W + 44, h = REEL_H + 36;
    ctx.fillStyle = sc(p.fill || "glass"); ctx.fillRect(REEL_X, REEL_Y, REEL_W, REEL_H);
    for (let r = 0; r < 5; r++) {
      const rx = REEL_X + r * CELL_W, g = ctx.createLinearGradient(rx, 0, rx + CELL_W, 0);
      g.addColorStop(0, "rgba(0,0,0,0.45)"); g.addColorStop(0.5, "rgba(255,255,255,0.03)"); g.addColorStop(1, "rgba(0,0,0,0.45)");
      ctx.fillStyle = g; ctx.fillRect(rx, REEL_Y, CELL_W, REEL_H);
    }
    if (p.shape === "glass") { ctx.save(); rr(x, y, w, h, 18); rr(REEL_X - 4, REEL_Y - 4, REEL_W + 8, REEL_H + 8, 6); ctx.clip("evenodd");
      glass(() => rr(x, y, w, h, 18), x, y, w, h, p.fill, null); ctx.restore(); rr(x, y, w, h, 18); ctx.lineWidth = 1.5; ctx.strokeStyle = sc(p.edge || "hl"); ctx.stroke(); return; }
    const arm = 10, bar = 10, gap = 4, top = sc(p.top || "a"), bottom = sc(p.bottom || "c"), edge = sc(p.edge || "hl");
    elbowPath(x, y, 260, 120, "tl", arm, bar, 28); ctx.fillStyle = top; ctx.fill();
    elbowPath(x + w - 260, y + h - 120, 260, 120, "br", arm, bar, 28); ctx.fillStyle = bottom; ctx.fill();
    // the bars running on from each elbow, in blocks
    const run = (bx, by, len, cols, round) => {
      const seg = [0.62, 0.24, 0.14];
      let cx = bx;
      cols.forEach((c, i) => { const sw = len * seg[i] - (i < cols.length - 1 ? gap : 0);
        pillPath(cx, by, sw, bar, i === cols.length - 1 ? round : "none"); ctx.fillStyle = c; ctx.fill(); cx += sw + gap; });
    };
    run(x + 260 + gap, y, w - 260 - gap, [top, edge, bottom], "right");
    ctx.save(); ctx.translate(x + w, y + h - bar); ctx.scale(-1, 1); run(260 + gap, 0, w - 260 - gap, [bottom, edge, top], "right"); ctx.restore();
    ctx.fillStyle = alpha(edge, 0.7);
    ctx.fillRect(x + 2, y + 120 + gap, 2, h - 120 - gap - bar - gap); ctx.fillRect(x + w - 4, y + bar + gap, 2, h - 120 - gap - bar - gap);
  }
  // The jackpot meters: a tier-coloured cap on the outer end and a glass body (tab); a coloured pill; or glass.
  function lcarsMeter(id, name, value, x, y, w, h, lit) {
    const p = part("meter"), tier = (SKIN.palette && SKIN.palette[id]) || C.tiers[id];
    const fill = p.fill === "tier" || !p.fill ? tier : sc(p.fill), txt = sc(p.text || "goldHi");
    const outer = x < 640 ? "left" : "right";
    if (p.shape === "pill") {
      pillPath(x, y, w, h); ctx.fillStyle = lit ? mix(fill, "#ffffff", 0.35) : fill; ctx.fill();
      text(name, x + w / 2, y + 18, 16, DISPLAY, sc("ink"), "center", "400", 0, w - 40);
      text(value, x + w / 2, y + 46, 32, COND, sc("ink"), "center", "700", 0, w - 40);
      return;
    }
    if (p.shape === "glass") {
      glass(() => rr(x, y, w, h, 18), x, y, w, h, "glass", fill, lit ? 4 : 2);
    } else {
      const cap = 44, gap = 5, cx = outer === "left" ? x : x + w - cap, bx = outer === "left" ? x + cap + gap : x;
      pillPath(cx, y, cap, h, outer); ctx.fillStyle = lit ? mix(fill, "#ffffff", 0.45) : fill; ctx.fill();
      glass(() => { ctx.beginPath(); ctx.rect(bx, y, w - cap - gap, h); }, bx, y, w - cap - gap, h, "glass", lit ? "hl" : fill, lit ? 3 : 1.5);
      x = bx; w = w - cap - gap;
    }
    text(name, x + w / 2, y + 17, 16, DISPLAY, fill, "center", "400", 0, w - 16);
    text(value, x + w / 2, y + 46, 32, COND, txt, "center", "700", 0, w - 16);
  }
  // A box (credit, bet, win; the feature list; the info boxes; Buy Bonus): a glass pill, or glass.
  function lcarsBox(x, y, w, h, opts = {}) {
    const p = part("box");
    const path = () => (p.shape === "glass" || h > 60 ? rr(x, y, w, h, Math.min(p.shape === "glass" ? 14 : 22, h / 2)) : pillPath(x, y, w, h));
    if (opts.lit) { path(); ctx.fillStyle = opts.lit; ctx.fill(); return; }
    glass(path, x, y, w, h, p.fill, opts.edge || p.edge || "b", opts.edgeW);
  }
  function lcarsButton(x, y, w, h, base, hover, on) {
    const p = part("button");
    pillPath(x, y, w, h, p.shape === "half" ? "right" : "both");
    const f = base ? base[1] : on ? sc(p.on || "warn") : sc(p.fill || "b");
    ctx.fillStyle = hover ? mix(f, "#ffffff", 0.3) : f; ctx.fill();
  }
  // The deck: dark glass under an LCARS rail, an elbow at its left end.
  function lcarsDeck(y) {
    const p = part("deck"), top = y - 26, fill = sc(p.fill || "d"), accent = sc(p.accent || "a"), edge = sc(p.edge || "hl");
    ctx.fillStyle = alpha(sc("shade"), 0.9); ctx.fillRect(0, top, W, H - top);
    const bar = 6, gap = 4;
    if (p.shape === "bar") {
      pillPath(4, top, 600, bar, "left"); ctx.fillStyle = accent; ctx.fill();
      ctx.fillStyle = edge; ctx.fillRect(608, top, 200, bar);
      pillPath(812, top, W - 816, bar, "right"); ctx.fillStyle = fill; ctx.fill();
      return;
    }
    elbowPath(4, top, 140, H - top - 4, "tl", 12, bar, 26); ctx.fillStyle = accent; ctx.fill();
    ctx.fillStyle = fill; ctx.fillRect(148, top, 460, bar);
    ctx.fillStyle = edge; ctx.fillRect(612, top, 180, bar);
    pillPath(796, top, W - 800, bar, "right"); ctx.fillStyle = fill; ctx.fill();
  }
  // The spin button: a pill across the gap between AUTO and CASH OUT, or a glass disc.
  const SPIN_PILL = { x: 1036, y: 628, w: 128, h: 72 };
  function lcarsSpin(label, spinning, hov) {
    const p = part("spin"), f = sc(p.fill || "hl"), cx = 1112, cy = 664;
    if (p.shape === "disc") {
      glass(() => { ctx.beginPath(); ctx.arc(cx, cy, 46, 0, 7); }, cx - 46, cy - 46, 92, 92, f, f, hov ? 5 : 3);
      ctx.beginPath(); ctx.arc(cx, cy, 34, 0, 7); ctx.fillStyle = spinning ? dark(f, 0.25) : f; ctx.fill();
      text(label, cx, cy + 2, 22, DISPLAY, sc(p.text || "ink"), "center", "400", 0, 62);
      return { x: cx - 46, y: cy - 46, w: 92, h: 92 };
    }
    const b = SPIN_PILL;
    pillPath(b.x, b.y, b.w, b.h); ctx.fillStyle = spinning ? dark(f, 0.25) : hov ? mix(f, "#ffffff", 0.3) : f; ctx.fill();
    text(label, b.x + b.w / 2, b.y + b.h / 2 + 2, 28, DISPLAY, sc(p.text || "ink"), "center", "400", 0, b.w - 28);
    return b;
  }
  // Decor: Claude's free shapes, under the parts or over them.
  const pad = (n, k) => String(n).padStart(k, "0");
  function stardate() {
    const d = new Date(), y0 = new Date(d.getFullYear(), 0, 1), y1 = new Date(d.getFullYear() + 1, 0, 1);
    return ((d.getFullYear() - 1976) * 1000 + ((d - y0) / (y1 - y0)) * 1000).toFixed(1);
  }
  function token(s) {
    const d = new Date();
    return s.replace("{name}", V.name.toUpperCase()).replace("{stardate}", stardate())
      .replace("{date}", d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" }).toUpperCase())
      .replace("{time}", `${pad(d.getHours(), 2)}:${pad(d.getMinutes(), 2)}`);
  }
  // A readout's number: the same for a cell until its tick comes round (slot_screen.gd's _readout_value matches).
  function readoutValue(seed, i, epoch, digits) {
    let h = (Math.imul(seed + 1, 73856093) ^ Math.imul(i + 1, 19349663) ^ Math.imul(epoch + 1, 83492791)) >>> 0;
    h = Math.imul(h ^ (h >>> 15), 2246822519) >>> 0; h = Math.imul(h ^ (h >>> 13), 3266489917) >>> 0; h = (h ^ (h >>> 16)) >>> 0;
    return pad(h % Math.pow(10, digits), digits);
  }
  function drawDecor(layer) {
    for (const d of SKIN.decor || []) {
      if (d.layer !== layer || d.show === false) continue;
      ctx.save(); ctx.globalAlpha = d.alpha != null ? d.alpha : 1;
      const col = sc(d.colour);
      if (d.kind === "elbow") { elbowPath(d.x, d.y, d.w, d.h, d.corner, d.arm, d.bar, d.r); ctx.fillStyle = col; ctx.fill(); }
      else if (d.kind === "bar" || d.kind === "pill") {
        pillPath(d.x, d.y, d.w, d.h, d.round); ctx.fillStyle = col; ctx.fill();
        if (d.kind === "pill" && d.text) {
          const tx = d.align === "left" ? d.x + d.h / 2 + 4 : d.align === "right" ? d.x + d.w - d.h / 2 - 4 : d.x + d.w / 2;
          text(token(d.text), tx, d.y + d.h / 2 + 1, d.size, d.font === "ui" ? COND : DISPLAY, sc(d.text_colour), d.align, "400", 0, d.w - d.h);
        }
      } else if (d.kind === "text") {
        const tx = d.align === "left" ? d.x : d.align === "right" ? d.x + d.w : d.x + d.w / 2;
        text(token(d.text), tx, d.y + d.h / 2, d.size, d.font === "ui" ? COND : DISPLAY, col, d.align, "400", 0, d.w);
      } else if (d.kind === "readout") {
        const total = d.cells.reduce((a, c) => a + c + 1.2, 0), gap = 3, unit = (d.w - gap * (d.cells.length - 1)) / total;
        let x = d.x;
        d.cells.forEach((n, i) => {
          const cw = unit * (n + 1.2), c = sc(d.colours[i % d.colours.length]);
          const epoch = d.tick > 0 ? Math.floor(S.now / d.tick + i * 0.37) : 0;   // the cells change one by one
          pillPath(x, d.y, cw, d.h, i === 0 ? "left" : i === d.cells.length - 1 ? "right" : "none"); ctx.fillStyle = c; ctx.fill();
          text(readoutValue(d.seed, i, epoch, n), x + cw - 4 - (i === d.cells.length - 1 ? d.h / 3 : 0), d.y + d.h / 2 + 1,
               d.h * 0.78, COND, sc(d.text_colour), "right", "700", 0, cw - 6);
          x += cw + gap;
        });
      }
      ctx.restore();
    }
  }

  // The vector background: dusk over the mesas (the painted set brings its own).
  const vecBg = document.createElement("canvas"); vecBg.width = W; vecBg.height = H;
  (function paintBg() {
    const b = vecBg.getContext("2d");
    const sky = b.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#1b1440"); sky.addColorStop(0.35, "#6a2c5c"); sky.addColorStop(0.62, "#e0663a"); sky.addColorStop(0.8, "#f7b25a"); sky.addColorStop(1, "#5a2a16");
    b.fillStyle = sky; b.fillRect(0, 0, W, H);
    const r2 = M.mulberry32(42);
    for (let i = 0; i < 90; i++) { b.fillStyle = `rgba(255,240,210,${0.2 + r2() * 0.6})`; b.fillRect(r2() * W, r2() * H * 0.35, 1.6, 1.6); }
    const sun = b.createRadialGradient(640, 470, 10, 640, 470, 220);
    sun.addColorStop(0, "rgba(255,230,150,0.95)"); sun.addColorStop(0.25, "rgba(255,170,80,0.55)"); sun.addColorStop(1, "rgba(255,120,60,0)");
    b.fillStyle = sun; b.fillRect(0, 200, W, 520);
    const mesa = (pts, col) => { b.beginPath(); b.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) b.lineTo(pts[i], pts[i + 1]); b.closePath(); b.fillStyle = col; b.fill(); };
    mesa([0, 520, 60, 520, 80, 430, 260, 420, 290, 520, 420, 540, 460, 470, 600, 466, 630, 540, 1280, 560, 1280, 720, 0, 720], "#6e2c22");
    mesa([700, 560, 760, 450, 900, 440, 930, 500, 1050, 498, 1080, 420, 1230, 410, 1280, 470, 1280, 720, 700, 720], "#57211c");
    mesa([0, 600, 300, 580, 640, 610, 980, 590, 1280, 610, 1280, 720, 0, 720], "#3a160f");
    const cactus = (x, y, s) => {
      b.fillStyle = "#24100b"; b.fillRect(x - 6 * s, y - 70 * s, 12 * s, 70 * s);
      b.fillRect(x - 24 * s, y - 50 * s, 8 * s, 26 * s); b.fillRect(x - 24 * s, y - 28 * s, 22 * s, 8 * s);
      b.fillRect(x + 16 * s, y - 60 * s, 8 * s, 30 * s); b.fillRect(x + 2 * s, y - 36 * s, 22 * s, 8 * s);
    };
    cactus(120, 640, 1.4); cactus(1170, 650, 1.6); cactus(1010, 610, 0.8); cactus(240, 610, 0.7);
  })();

  // ------------------------------------------------------------------ the frame, meters, panels, deck
  function drawBackground() {
    if (ok(bgImg)) ctx.drawImage(bgImg, 0, 0, W, H);
    else if (lc()) {   // no picture: deep space, not Armadillo's dusk
      const g = ctx.createRadialGradient(W / 2, H * 0.45, 60, W / 2, H / 2, 900);
      g.addColorStop(0, mix(sc("glass"), "#ffffff", 0.05)); g.addColorStop(1, "#000000");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    } else ctx.drawImage(vecBg, 0, 0);
    const v = ctx.createRadialGradient(W / 2, H / 2, 200, W / 2, H / 2, 820);
    v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, dark(C.shade, 0.6, 0.6));
    ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  }
  function drawTop() {
    const pills = [["grand", 18, 250], ["major", 278, 210], ["minor", 792, 210], ["mini", 1012, 250]];
    for (const [id, x, w] of pills) {
      const t = M.JACKPOT_TIERS.find((q) => q.id === id), y = 14, h = 70, col = C.tiers[id];
      if (lc()) { lcarsMeter(id, t.name, moneyShort(Math.floor(S.metersShown[id])), x, y, w, h, S.pick && S.pick.lit === id && Math.floor(S.now * 6) % 2); continue; }
      const g = ctx.createLinearGradient(0, y, 0, y + h);
      g.addColorStop(0, "rgba(255,255,255,0.18)"); g.addColorStop(0.5, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,0.3)");
      rr(x, y, w, h, 18); ctx.fillStyle = C.shade; ctx.fill();
      rr(x + 4, y + 4, w - 8, h - 8, 15); ctx.fillStyle = col; ctx.globalAlpha = 0.85; ctx.fill(); ctx.globalAlpha = 1;
      ctx.fillStyle = g; ctx.fill();
      rr(x, y, w, h, 18); ctx.lineWidth = 3; ctx.strokeStyle = C.gold; ctx.stroke();
      const lit = S.pick && S.pick.lit === id && Math.floor(S.now * 6) % 2;
      if (lit) { rr(x - 4, y - 4, w + 8, h + 8, 22); ctx.lineWidth = 5; ctx.strokeStyle = C.goldHi; ctx.stroke(); }
      text(t.name, x + w / 2, y + 18, 18, COND, "#fff", "center", "700", 4);
      text(moneyShort(Math.floor(S.metersShown[id])), x + w / 2, y + 46, 32, COND, "#fff", "center", "700", 6);
    }
    // The logo: lettering in both art sets (FLUX can't spell ARMADILLO).
    if (ok(logoImg)) { const k = Math.min(292 / logoImg.naturalWidth, 99 / logoImg.naturalHeight); const w = logoImg.naturalWidth * k, h = logoImg.naturalHeight * k; ctx.drawImage(logoImg, 640 - w / 2, 53.5 - h / 2, w, h); }
    else if (TEXT.title.length > 1) { goldText(TEXT.title[0], 640, 34, 44); goldText(TEXT.title[1], 640, 80, 34); }
    else goldText(TEXT.title[0], 640, 53, 40);
  }
  function drawFrame() {
    if (lc()) return lcarsFrame();
    woodPanel(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36, 18);
    const reelBg = FRAME.style === "wood" ? ["#1c0e07", "#2e190d"] : FRAME.style === "metal" ? ["#0d0f13", "#1d2128"] : ["#05040f", "#100c26"];
    for (let r = 0; r < 5; r++) {
      const x = REEL_X + r * CELL_W;
      const g = ctx.createLinearGradient(x, 0, x + CELL_W, 0);
      g.addColorStop(0, reelBg[0]); g.addColorStop(0.5, reelBg[1]); g.addColorStop(1, reelBg[0]);
      ctx.fillStyle = g; ctx.fillRect(x, REEL_Y, CELL_W, REEL_H);
    }
    // rivets
    ctx.fillStyle = FRAME.style === "wood" ? "#e3b45a" : FRAME.colour;
    for (const [x, y] of [[REEL_X - 10, REEL_Y - 6], [REEL_X + REEL_W + 10, REEL_Y - 6], [REEL_X - 10, REEL_Y + REEL_H + 6], [REEL_X + REEL_W + 10, REEL_Y + REEL_H + 6]]) {
      ctx.beginPath(); ctx.arc(x, y, 4.5, 0, 7); ctx.fill();
    }
  }
  function drawSides() {
    // Left: the random features, lit when they hit this spin.
    woodPanel(18, REEL_Y - 18, 224, REEL_H + 36, 16);
    text(T("features", "RANDOM FEATURES"), lc() ? 134 : 130, REEL_Y + 8, 19, lc() ? DISPLAY : COND, lc() ? sc(part("panel").title || "hl") : C.goldHi, "center", lc() ? "400" : "700", 0, 196);
    const names = [["wilds", "RANDOM WILDS"], ["wildReels", "WILD REELS"], ["colossal", "COLOSSAL REELS"], ["multiplier", "MULTIPLIER"],
      ["upgrade", "SYMBOL UPGRADE"], ["repeat", "REPEAT WIN"], ["instant", "INSTANT WIN"]].filter(([id]) => V.features.includes(id))
      .map(([id, n]) => [id, (cfg.featureNames && cfg.featureNames[id]) || n]);
    const step = Math.min(52, 364 / Math.max(1, names.length));
    names.forEach(([id, label], i) => {
      const y = REEL_Y + 32 + i * step, lit = S.featureLit[id];
      const litCol = alpha(mix(C.win, C.goldHi, 0.5 + 0.5 * Math.sin(S.now * 8)), 0.95);
      if (lc()) lcarsBox(36, y, 196, 42, { lit: lit ? sc("hl") : null, edgeW: 1 });
      else {
        rr(34, y, 192, 42, 10);
        ctx.fillStyle = lit ? litCol : DECK.inset; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = lit ? C.goldHi : DECK.boxEdge; ctx.stroke();
      }
      text(id === "multiplier" && S.multiplier > 1 ? `${label} \u00d7${S.multiplier}` : label, lc() ? 134 : 130, y + 22, 20, COND,
           lit ? C.ink : lc() ? sc(part("box").label || "c") : C.muted, "center", "700", 0, 180);
    });
    // Right: Buy Bonus and the two ways in.
    woodPanel(1038, REEL_Y - 18, 224, REEL_H + 36, 16);
    const busy = S.busy || S.mode !== "reels";
    const by = REEL_Y + 6;
    if (V.buyCost) {   // no Buy Bonus: the panel shows just the two ways in
    S.hits.push(...(busy ? [] : [{ id: "buy", x: 1052, y: by, w: 196, h: 178 }]));
    const hov = S.hover === "buy" && !busy;
    if (lc()) glass(() => rr(1048, by, 200, 178, 18), 1048, by, 200, 178, "glass", hov ? "hl" : "warn", hov ? 3 : 2);
    else {
      rr(1052, by, 196, 178, 14);
      ctx.fillStyle = hov ? DECK.buyHover : DECK.buy; ctx.fill();
      ctx.lineWidth = hov ? 4 : 3; ctx.strokeStyle = C.gold; ctx.stroke();
    }
    ctx.save(); if (busy) ctx.globalAlpha = 0.45;
    text(T("buy", "BUY BONUS"), 1150, by + 24, 26, lc() ? DISPLAY : COND, lc() ? sc("warn") : C.goldHi, "center", lc() ? "400" : "700", 0, 180);
    drawImg(img(buyIcon()), 1150 - 52, by + 38, 104, 104);
    text(money(bet() * V.buyCost), 1150, by + 156, 26, COND, "#fff");
    ctx.restore();
    }
    const info = M.SCATTERS.filter((s) => routes(s).length)
      .map((s) => [s, (s === "BS" ? TEXT.bonus : TEXT.free)[0], routes(s).length > 1 ? "A RANDOM BONUS" : plays(routes(s))]);
    info.forEach(([sym, a, b], i) => {
      const y = by + 196 + i * 116;
      if (lc()) lcarsBox(1048, y, 200, 104, { edgeW: 1 }); else { rr(1052, y, 196, 104, 12); ctx.fillStyle = DECK.inset; ctx.fill(); }
      // the symbol on the left, its two lines centred in the space to its right
      drawImg(img(sym), 1058, y + 14, 76, 76);
      const tx = 1138, tw = 1248 - 8 - tx, mid = tx + tw / 2;
      if (lc()) { text(a, mid, y + 40, 17, DISPLAY, sc("hl"), "center", "400", 0, tw); text(b, mid, y + 66, 14, COND, C.cream, "center", "700", 0, tw); }
      else { text(a, mid, y + 40, 22, COND, C.goldHi, "center", "700", 0, tw); text(b, mid, y + 66, 16, COND, C.cream, "center", "700", 0, tw); }
    });
  }
  function drawDeck() {
    const y = 618;
    if (lc()) lcarsDeck(y);
    else {
      ctx.fillStyle = DECK.band; ctx.fillRect(0, y - 26, W, H - y + 26);
      ctx.fillStyle = C.edge; ctx.fillRect(0, y - 26, W, 2);
    }
    // the message bar
    text(S.message, 640, y - 12, 19, COND, C.goldHi);
    const box = (x, w, label, value, col = "#fff") => {
      if (lc()) {
        lcarsBox(x, y + 10, w, 82);
        text(label, x + w / 2, y + 28, 16, DISPLAY, sc(part("box").label || "c"), "center", "400");
        text(value, x + w / 2, y + 64, 36, COND, col === "#fff" ? sc(part("box").value || "goldHi") : col, "center", "700", 0, w - 50);
        return;
      }
      rr(x, y + 10, w, 82, 12); ctx.fillStyle = DECK.box; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = DECK.boxEdge; ctx.stroke();
      text(label, x + w / 2, y + 28, 16, COND, C.muted); text(value, x + w / 2, y + 64, 36, COND, col);
    };
    const credit = S.balance - (S.pendingCredit || 0);
    box(20, 210, T("credit", "CREDIT"), money(credit));
    box(242, 230, T("bet", "BET"), money(bet()));
    const canBet = !S.busy && S.mode === "reels";
    button("bet-", 252, y + 46, 40, 38, "\u2212", { disabled: !canBet || S.betIdx === 0, size: 30 });
    button("bet+", 422, y + 46, 40, 38, "+", { disabled: !canBet || S.betIdx === M.LADDER.length - 1, size: 30 });
    box(484, 230, S.free ? "FREE GAMES WIN" : T("win", "WIN"), S.winShown > 0 ? money(Math.floor(S.winShown)) : "", C.win);
    const deckBusy = S.mode !== "reels" || S.overlay;
    button("info", 730, y + 22, 92, 56, T("info", "INFO"), { disabled: deckBusy || S.busy });
    button("turbo", 832, y + 22, 92, 56, T("turbo", "TURBO"), { on: S.turbo });
    button("auto", 934, y + 22, 92, 56, S.auto > 0 ? `STOP ${S.auto}` : T("auto", "AUTO"), { on: S.auto > 0 || S.autoMenu, disabled: S.mode !== "reels" && S.auto === 0 });
    // SPIN
    // Inside the 720px screen with room to spare: centre 664, ring 50 (614..714).
    const cx = 1112, cy = 664, r = 46, spinning = reels.some((x) => x.spinning);
    const hov = S.hover === "spin";
    const spinLabel = spinning ? T("stop", "STOP") : S.mode === "trail" || S.mode === "battle" ? T("fire", "FIRE") : S.mode === "voyage" ? T("sail", "SAIL") : T("spin", "SPIN");
    if (lc()) {
      S.hits.push(Object.assign({ id: "spin" }, lcarsSpin(spinLabel, spinning, hov)));
      button("cashout", 1172, y + 22, 96, 56, T("cashout", "CASH OUT"), { size: 18, disabled: S.busy || S.mode !== "reels" });
      if (S.autoMenu) [10, 25, 50, 100].forEach((n, i) => button("auto" + n, 930, y - 70 - i * 46, 100, 40, `${n} SPINS`, { colour: spinBtn() }));
      return;
    }
    const g = ctx.createRadialGradient(cx - 14, cy - 18, 6, cx, cy, r);
    g.addColorStop(0, C.goldHi); g.addColorStop(0.5, spinning ? dark(C.spin, 0.2) : C.spin); g.addColorStop(1, dark(C.spin, 0.5));
    ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, 7); ctx.fillStyle = DECK.ring; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.fillStyle = g; ctx.fill();
    ctx.lineWidth = hov ? 5 : 3; ctx.strokeStyle = C.goldHi; ctx.stroke();
    text(spinLabel, cx, cy + 2, 28, COND, C.ink, "center", "700", 0, 84);
    S.hits.push({ id: "spin", x: cx - r, y: cy - r, w: r * 2, h: r * 2 });
    button("cashout", 1172, y + 22, 96, 56, T("cashout", "CASH OUT"), { size: 18, disabled: S.busy || S.mode !== "reels" });
    if (S.autoMenu) {
      [10, 25, 50, 100].forEach((n, i) => button("auto" + n, 934 + i * 0 - 4, y - 70 - i * 46, 100, 40, `${n} SPINS`, { colour: spinBtn() }));
    }
  }

  // ------------------------------------------------------------------ the reels
  const cellRect = (c) => ({ x: REEL_X + Math.floor(c / 4) * CELL_W, y: REEL_Y + (c % 4) * CELL_H });
  function drawSymbol(sym, x, y, w, h, fx) {
    const im = img(sym);
    if (!ok(im)) return;
    const a = fx && fx.anim, k = a ? a.strength || 1 : 0, t = S.now;
    let s = 0.92 * (fx && fx.scale || 1), dy = 0;
    let flip = fx && fx.flip != null ? Math.abs(Math.cos(fx.flip * Math.PI)) : 1;
    if (a && a.preset === "pulse") s *= 1 + 0.08 * k * (0.5 + 0.5 * Math.sin(t * 7));
    if (a && a.preset === "bounce") dy = -10 * k * Math.abs(Math.sin(t * 6));
    if (a && a.preset === "spin") flip = Math.max(0.08, Math.abs(Math.cos(t * 3 * k)));
    const size = Math.min(w, h) * s;
    ctx.save(); ctx.translate(x + w / 2, y + h / 2 + dy); ctx.scale(flip, 1);
    if (fx && fx.glow) { ctx.shadowColor = fx.glowColour || C.win; ctx.shadowBlur = 26 * fx.glow; }
    if (a && a.preset === "glow") { ctx.shadowColor = a.colour || C.win; ctx.shadowBlur = 24 * k * (0.6 + 0.4 * Math.sin(t * 6)); }
    ctx.drawImage(im, -size / 2, -size / 2, size, size);
    if (a && a.preset === "shine") {   // a light band sweeping across the symbol
      const p = ((t * 0.9) % 1.4) - 0.2, band = ctx.createLinearGradient(-size / 2, -size / 2, size / 2, size / 2);
      const c01 = (x) => Math.min(1, Math.max(0, x));
      band.addColorStop(c01(p - 0.12), "rgba(255,255,255,0)"); band.addColorStop(c01(p), `rgba(255,255,255,${0.5 * Math.min(1, k)})`);
      band.addColorStop(c01(p + 0.12), "rgba(255,255,255,0)");
      ctx.globalCompositeOperation = "lighter"; ctx.fillStyle = band; ctx.fillRect(-size / 2, -size / 2, size, size);
    }
    ctx.restore();
    if (LABELS && (sym === "W" || sym === "BS" || sym === "FS")) {
      const label = sym === "W" ? "WILD" : sym === "BS" ? "BONUS" : "FREE SPINS";
      const size2 = sym === "FS" ? 17 : 21;
      ctx.save(); ctx.translate(x + w / 2, y + h - 18); ctx.scale(flip, 1);
      rr(-w * 0.36, -12, w * 0.72, 24, 6); ctx.fillStyle = sym === "W" ? C.alert : C.ink; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = C.gold; ctx.stroke();
      text(label, 0, 1, size2, DISPLAY, C.goldHi, "center", "400");
      ctx.restore();
    }
  }
  function drawReels() {
    ctx.save();
    ctx.beginPath(); ctx.rect(REEL_X, REEL_Y, REEL_W, REEL_H); ctx.clip();
    const col = S.colossal;
    for (const x of reels) {
      const inGroup = col && x.r >= col.start && x.r < col.start + col.k;
      if (inGroup && x.r !== col.start) continue;
      if (x.spinning || x.stopping || !S.landed) {
        if (inGroup) drawBigReel(x, col); else drawSpinningReel(x);
      }
    }
    if (S.landed) drawGrid();
    // anticipation glow
    for (const x of reels) if (x.glow > 0) {
      ctx.save(); ctx.globalAlpha = x.glow * (0.6 + 0.4 * Math.sin(S.now * 12));
      ctx.lineWidth = 8; ctx.strokeStyle = C.win; ctx.strokeRect(REEL_X + x.r * CELL_W + 4, REEL_Y + 4, CELL_W - 8, REEL_H - 8); ctx.restore();
    }
    ctx.restore();
    // reel dividers
    ctx.fillStyle = alpha(C.edge, 0.55);
    for (let r = 1; r < 5; r++) {
      if (S.colossal && r > S.colossal.start && r < S.colossal.start + S.colossal.k) continue;
      ctx.fillRect(REEL_X + r * CELL_W - 1, REEL_Y, 2, REEL_H);
    }
    // glass shine
    const g = ctx.createLinearGradient(0, REEL_Y, 0, REEL_Y + REEL_H);
    g.addColorStop(0, "rgba(255,255,255,0.10)"); g.addColorStop(0.18, "rgba(255,255,255,0)"); g.addColorStop(0.85, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,0.35)");
    ctx.fillStyle = g; ctx.fillRect(REEL_X, REEL_Y, REEL_W, REEL_H);
  }
  function drawSpinningReel(x) {
    const strip = x.strip, len = strip.length, base = Math.floor(x.pos), frac = x.pos - base;
    const blur = Math.min(1, Math.abs(x.v) / 18);
    for (let i = -1; i <= 4; i++) {
      const sym = strip[(((base + i) % len) + len) % len];
      const y = REEL_Y + (i - frac) * CELL_H;
      if (blur > 0.05) {
        ctx.save(); ctx.globalAlpha = 0.28 * blur;
        drawSymbol(sym, REEL_X + x.r * CELL_W, y - 22 * blur, CELL_W, CELL_H);
        drawSymbol(sym, REEL_X + x.r * CELL_W, y + 22 * blur, CELL_W, CELL_H);
        ctx.restore();
        ctx.save(); ctx.globalAlpha = 1 - 0.45 * blur; drawSymbol(sym, REEL_X + x.r * CELL_W, y, CELL_W, CELL_H); ctx.restore();
      } else drawSymbol(sym, REEL_X + x.r * CELL_W, y, CELL_W, CELL_H);
    }
  }
  function drawBigReel(x, col) {
    // The fused reels: big symbols k cells square, scrolling as one reel. pos is in big-symbol units.
    const big = V.bigStrip, len = big.length, k = col.k, size = CELL_H * k, wPx = CELL_W * k;
    const base = Math.floor(x.pos), frac = x.pos - base;
    ctx.save();
    ctx.fillStyle = alpha(mix(C.shade, C.edge, 0.15), 0.6); ctx.fillRect(REEL_X + col.start * CELL_W, REEL_Y, wPx, REEL_H);
    for (let i = -1; i <= Math.ceil(4 / k); i++) {
      const sym = big[(((base + i) % len) + len) % len];
      const y = REEL_Y + (i - frac) * size;
      drawSymbol(sym, REEL_X + col.start * CELL_W + (wPx - size * 1.05) / 2, y, size * 1.05, size);
    }
    ctx.restore();
  }
  function drawGrid() {
    const col = S.colossal;
    // a landed Colossal block is drawn big, then any cell that changed since is drawn over it
    if (col) {
      const k = col.k, size = CELL_H * k, wPx = CELL_W * k;
      ctx.fillStyle = alpha(mix(C.shade, C.edge, 0.15), 0.6); ctx.fillRect(REEL_X + col.start * CELL_W, REEL_Y, wPx, REEL_H);
      for (let b = 0; b <= Math.ceil(4 / k); b++) {
        const sym = V.bigStrip[(col.stop + b) % V.bigStrip.length];
        const y = REEL_Y + (b * k - col.offset) * CELL_H;
        const cells = [];
        for (let rr2 = 0; rr2 < 4; rr2++) if (Math.floor((rr2 + col.offset) / k) === b) for (let r = col.start; r < col.start + k; r++) cells.push(r * 4 + rr2);
        const now = cells.length ? S.grid[cells[0]] : sym;
        const same = cells.every((c) => S.grid[c] === now);
        const fx = cells.length ? S.cellFx[cells[0]] : null;
        if (same) drawSymbol(now, REEL_X + col.start * CELL_W + (wPx - size * 1.05) / 2, y, size * 1.05, size, fx && fx.big ? fx : null);
      }
    }
    const shown = S.landed && S.wins.length ? (S.busy || S.cycle === 0 ? S.wins : [S.wins[S.cycle - 1]]) : [];
    const winning = new Set(shown.flatMap((w) => w.cells));
    for (let c = 0; c < 20; c++) {
      const r = Math.floor(c / 4);
      if (col && r >= col.start && r < col.start + col.k) {
        const b = Math.floor(((c % 4) + col.offset) / col.k);
        const block = [];
        for (let rr2 = 0; rr2 < 4; rr2++) if (Math.floor((rr2 + col.offset) / col.k) === b) for (let q = col.start; q < col.start + col.k; q++) block.push(q * 4 + rr2);
        if (block.every((q) => S.grid[q] === S.grid[block[0]])) continue;
      }
      const { x, y } = cellRect(c);
      const anim = winning.has(c) ? WIN[groupOf(S.grid[c])] : null;
      drawSymbol(S.grid[c], x, y, CELL_W, CELL_H, anim && anim.preset !== "none" ? Object.assign({}, S.cellFx[c], { anim }) : S.cellFx[c]);
    }
  }
  function drawWins() {
    if (!S.landed || !S.wins.length) return;
    const lines = S.busy || S.cycle === 0 ? S.wins : [S.wins[S.cycle - 1]];
    for (const w of lines) {
      const colr = LINE_COLOURS[(w.line - 1) % 25];
      const pts = M.LINES[w.line - 1].map((row, reel) => [REEL_X + reel * CELL_W + CELL_W / 2, REEL_Y + row * CELL_H + CELL_H / 2]);
      ctx.save();
      ctx.lineJoin = "round"; ctx.lineCap = "round";
      ctx.shadowColor = colr; ctx.shadowBlur = 16;
      ctx.lineWidth = 9; ctx.strokeStyle = alpha(C.shade, 0.7);
      ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(REEL_X - 8, y))); ctx.lineTo(REEL_X + REEL_W + 8, pts[4][1]); ctx.stroke();
      ctx.lineWidth = 5; ctx.strokeStyle = colr; ctx.stroke();
      ctx.restore();
      for (const c of w.cells) {
        const { x, y } = cellRect(c);
        ctx.save(); ctx.lineWidth = 4; ctx.strokeStyle = colr; ctx.shadowColor = colr; ctx.shadowBlur = 14;
        rr(x + 6, y + 6, CELL_W - 12, CELL_H - 12, 10); ctx.stroke(); ctx.restore();
      }
      if (lines.length === 1) {
        const { x, y } = cellRect(w.cells[w.cells.length - 1]);
        rr(x + CELL_W - 92, y + 6, 86, 30, 8); ctx.fillStyle = alpha(C.shade, 0.85); ctx.fill();
        text(money(w.pence), x + CELL_W - 49, y + 21, 22, COND, colr);
      }
    }
    if (!S.busy && S.cycle > 0) {
      const w = S.wins[S.cycle - 1];
      S.message = `LINE ${w.line} \u00b7 ${w.count} \u00d7 ${V.symbols[w.sym].toUpperCase()} \u00b7 ${money(w.pence)}`;
    }
  }

  // ------------------------------------------------------------------ banners, particles, overlays
  function banner(textStr, sub, dur = 1.4) {
    S.banner = { text: textStr, sub, t0: S.now, dur };
    return wait(dur * 0.8);
  }
  function drawBanner() {
    const b = S.banner;
    if (!b) return;
    const t = (S.now - b.t0) / b.dur;
    if (t > 1) { S.banner = null; return; }
    const a = t < 0.15 ? t / 0.15 : t > 0.8 ? (1 - t) / 0.2 : 1;
    const s = t < 0.15 ? 0.6 + 0.4 * ease.back(t / 0.15) : 1;
    ctx.save(); ctx.globalAlpha = a; ctx.translate(640, REEL_Y + REEL_H / 2); ctx.scale(s, s);
    rr(-420, -66, 840, b.sub ? 132 : 100, 22); ctx.fillStyle = alpha(C.shade, 0.88); ctx.fill();
    ctx.lineWidth = 4; ctx.strokeStyle = C.gold; ctx.stroke();
    goldText(b.text, 0, b.sub ? -16 : -16, 58);
    if (b.sub) text(b.sub, 0, 40, 26, COND, C.cream);
    ctx.restore();
  }
  function coinBurst(x, y, n, spread = 1) {
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + (rng() - 0.5) * 2.2 * spread;
      const v = 300 + rng() * 520;
      S.particles.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, g: 1100, life: 2.4, spin: rng() * 6, vs: 6 + rng() * 10, r: 10 + rng() * 9 });
    }
  }
  function coinRain(n) {
    for (let i = 0; i < n; i++) S.particles.push({ x: rng() * W, y: -40 - rng() * 400, vx: (rng() - 0.5) * 80, vy: 100 + rng() * 200, g: 500, life: 4, spin: rng() * 6, vs: 5 + rng() * 9, r: 11 + rng() * 10 });
  }
  function drawParticles() {
    for (const p of S.particles) {
      const sx = Math.cos(p.spin);
      ctx.save(); ctx.translate(p.x, p.y); ctx.scale(Math.max(0.12, Math.abs(sx)), 1);
      const g = ctx.createRadialGradient(-p.r * 0.3, -p.r * 0.3, 1, 0, 0, p.r);
      g.addColorStop(0, C.goldHi); g.addColorStop(0.5, sx > 0 ? C.gold : mix(C.gold, C.goldLo, 0.3)); g.addColorStop(1, C.goldLo);
      ctx.beginPath(); ctx.arc(0, 0, p.r, 0, 7); ctx.fillStyle = g; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = dark(C.goldLo, 0.4); ctx.stroke();
      ctx.restore();
    }
  }
  function drawFlyers() {
    for (const f of S.flyers) {
      if (f.a <= 0) continue;
      ctx.save(); ctx.globalAlpha = f.a; ctx.translate(f.x, f.y); ctx.rotate(f.rot || 0); ctx.scale(f.s, f.s);
      if (f.img) drawImg(img(f.img), -f.size / 2, -f.size / 2, f.size, f.size);
      if (f.text) text(f.text, 0, 0, f.textSize || 40, f.font || COND, f.colour || C.goldHi, "center", "700", 6);
      if (f.flash) { ctx.globalCompositeOperation = "lighter"; const g = ctx.createRadialGradient(0, 0, 2, 0, 0, 60); g.addColorStop(0, alpha(C.goldHi, 1)); g.addColorStop(1, alpha(C.spin, 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, 60, 0, 7); ctx.fill(); }
      ctx.restore();
    }
    S.flyers = S.flyers.filter((f) => !f.dead);
  }
  function flyer(props) { const f = Object.assign({ x: 640, y: 360, s: 1, a: 1, size: 120 }, props); S.flyers.push(f); return f; }

  function drawOverlay() {
    const o = S.overlay;
    if (!o) return;
    ctx.fillStyle = dark(C.shade, 0.6, 0.72); ctx.fillRect(0, 0, W, H);
    S.hits = o.keepDeck ? S.hits : [];
    if (o.kind === "bigwin") {
      const t = Math.min(1, (S.now - o.t0) * 2.2);
      ctx.save(); ctx.translate(640, 300); const s = 0.5 + 0.5 * ease.back(t); ctx.scale(s, s);
      const pulse = 1 + 0.03 * Math.sin(S.now * 6);
      ctx.scale(pulse, pulse);
      goldText(o.title, 0, -40, 120);
      text(money(Math.floor(o.shown)), 0, 70, 84, COND, "#fff", "center", "700", 10);
      ctx.restore();
      text("Click to continue", 640, 520, 20, COND, C.muted);
      S.hits.push({ id: "overlay", x: 0, y: 0, w: W, h: H });
    } else if (o.kind === "summary") {
      woodPanel(340, 170, 600, 330, 22);
      goldText(o.title, 640, 240, 54);
      text(o.sub || "", 640, 300, 24, COND, C.cream);
      text(money(o.amount), 640, 372, 76, COND, C.win, "center", "700", 8);
      button("overlay", 560, 430, 160, 50, T("collect", "COLLECT"), { colour: spinBtn() });
      const left = 5 - (S.now - o.t0);
      text(`collects itself in ${Math.max(1, Math.ceil(left))}`, 640, 486 + 10, 16, COND, C.muted);
      if (left <= 0 && o.done) { const d = o.done; o.done = null; d(); }
    } else if (o.kind === "buy") {
      woodPanel(360, 170, 560, 340, 22);
      goldText("BUY BONUS", 640, 228, 50);
      drawImg(img(buyIcon()), 640 - 60, 256, 120, 120);
      text(`Go straight to ${routes("buy").length > 1 ? "" : "the "}${plays(routes("buy")).toLowerCase()} for ${money(bet() * V.buyCost)}`, 640, 400, 26, COND, C.cream, "center", "700", 0, 520);
      text(`${V.buyCost} \u00d7 your ${money(bet())} bet. Bonus wins pay at ${money(bet())}.`, 640, 430, 19, COND, C.muted);
      button("buy-yes", 470, 450, 160, 48, "BUY", { colour: spinBtn(), disabled: S.balance < bet() * V.buyCost });
      button("buy-no", 650, 450, 160, 48, "CANCEL");
    } else if (o.kind === "info") {
      drawInfo();
    } else if (o.kind === "notice") {
      woodPanel(390, 250, 500, 200, 20);
      text(o.text, 640, 320, 28, COND, C.cream);
      button("overlay", 560, 372, 160, 48, "OK");
    }
  }
  function drawInfo() {
    woodPanel(40, 40, 1200, 640, 22);
    goldText("PAYS AT " + money(bet()), 640, 82, 34);
    const lb = bet() / 25;
    // The pay table, rows of high pays (with the Wild), mids and lows; as many columns as the row needs.
    const tiers = Object.keys(V.pays);
    const rowsOf = [tiers.filter((t) => t === "W" || t[0] === "H"), tiers.filter((t) => t[0] === "M"), tiers.filter((t) => t[0] === "L")];
    rowsOf.forEach((row, ri) => row.forEach((sym, col) => {
      const n = row.length, cw = Math.min(280, 1120 / n), sz = Math.min(104, cw - 130), x0 = 640 - (n * cw) / 2 + col * cw, y = 118 + ri * 128;
      drawImg(img(sym), x0 + 10, y + 4 + (104 - sz) / 2, sz, sz);
      [5, 4, 3].forEach((k, j) => {
        text(`${k}`, x0 + sz + 32, y + 30 + j * 26, 20, COND, C.spin, "left");
        text(money(Math.floor(V.pays[sym][k - 3] * lb)), x0 + sz + 56, y + 30 + j * 26, 22, COND, C.cream, "left");
      });
    }));
    const nm = (t) => V.symbols[t] || t;
    const ups = {};
    for (const [f, t] of Object.entries(V.upgrades)) (ups[t] = ups[t] || []).push(nm(f));
    const ways = M.SCATTERS.filter((s) => routes(s).length);
    const tips = (cfg.rules || [
      `Wild stands in for everything except ${ways.map(nm).join(" and ")}. Pays left to right on 25 lines; the longest match on each line pays.`,
      "Random features can hit any spin, some before the reels stop and some after.",
      ways.map((s) => `3+ ${nm(s)}: ${plays(routes(s))}.`).join(" "),
      "Upgrades: " + Object.entries(ups).map(([t, fs]) => `${fs.join(", ")} \u2192 ${nm(t)}`).join(" \u00b7 ")]);
    tips.forEach((t, i) => text(t, 640, 528 + i * 28, 19, COND, i === tips.length - 1 ? C.goldHi : C.cream, "center", "700", 0, 1140));
    button("overlay", 1100, 56, 120, 44, "CLOSE");
  }

  // ------------------------------------------------------------------ the spin
  function clearWins() {
    S.wins = []; S.cycle = 0; S.winShown = 0; S.winTarget = 0; S.cellFx = {}; S.featureLit = {}; S.multiplier = 1;
  }
  async function spin(opts = {}) {
    if (S.busy || S.overlay || S.mode !== "reels") return;
    const b = bet();
    if (S.balance < b) { S.auto = 0; S.overlay = { kind: "notice", text: "Not enough credit for that bet. Top up below the screen." }; return; }
    S.busy = true; S.hurry = false;
    S.balance -= b; contribute(b);
    clearWins();
    const rig = S.rig; S.rig = { features: [], trigger: null, jackpot: null }; if (cfg.onRigUsed) cfg.onRigUsed();
    const o = M.spinOutcome(V, b, rng, { rig: { features: rig.features.length ? rig.features : null, trigger: rig.trigger } });
    const jackpot = rig.jackpot || M.jackpotTrigger(b, rng);
    S.message = "GOOD LUCK!";
    await playSpin(o);
    S.balance += o.total;
    if (o.total > 0) S.message = `YOU WON ${money(o.total)}`;
    else S.message = "25 LINES \u00b7 " + TEXT.tagline;
    if (jackpot) await jackpotPick(jackpot);
    if (o.trigger === "trail") await trailBonus(b, false);
    else if (o.trigger === "free") await freeGames(b);
    else if (o.trigger === "battle") await battleBonus(b, false);
    else if (o.trigger === "voyage") await voyageBonus(b, false);
    S.busy = false;
    const stopAuto = o.trigger || jackpot || o.total >= 25 * b;
    if (S.auto > 0) { S.auto = stopAuto ? 0 : S.auto - 1; if (S.auto > 0) setTimeout(() => spin(), 450 / pace()); }
  }

  async function playSpin(o) {
    S.landed = false; S.colossal = null;
    const strips = o.free ? V.freeStrips : V.strips;
    reels.forEach((x) => { x.strip = strips[x.r]; x.glow = 0; });
    // Pre-stop announcements: what's coming before the reels stop.
    const pre = [];
    if (o.colossal) { S.colossal = Object.assign({}, o.colossal); pre.push(["colossal", "COLOSSAL REELS", `${o.colossal.k}\u00d7${o.colossal.k} symbols`]); }
    if (o.multiplier > 1) { S.multiplier = o.multiplier; pre.push(["multiplier", `${o.multiplier}\u00d7 MULTIPLIER`, "on every line win this spin"]); }
    if (o.wildReels.length) pre.push(["wildReels", "WILD REELS", `${o.wildReels.length} reel${o.wildReels.length > 1 ? "s" : ""} going wild`]);
    if (o.wilds.length) pre.push(["wilds", "RANDOM WILDS", `${o.wilds.length} shot${o.wilds.length > 1 ? "s" : ""} fired`]);
    // Start the reels.
    reels.forEach((x, i) => {
      if (S.colossal && x.r >= S.colossal.start && x.r < S.colossal.start + S.colossal.k) {
        if (x.r === S.colossal.start) { x.pos = rng() * V.bigStrip.length; startReel(x, 10 / S.colossal.k, i); }
        return;
      }
      startReel(x, 20, i);
    });
    for (const [id, title, sub] of pre) { S.featureLit[id] = true; await banner(title, sub, 1.25); }
    await wait(pre.length ? 0.15 : 0.55);
    // Stop left to right, teasing when two of a scatter are already showing.
    const seen = { BS: 0, FS: 0 };
    for (let r = 0; r < 5; r++) {
      const x = reels[r];
      if (S.colossal && r > S.colossal.start && r < S.colossal.start + S.colossal.k) continue;
      const tease = !S.hurry && (seen.BS >= 2 || seen.FS >= 2);
      if (tease) { x.glow = 1; x.v = 34; S.message = "ONE MORE\u2026"; await wait(1.0); }
      if (S.colossal && r === S.colossal.start) {
        const col = S.colossal;
        await stopReel(x, col.stop + col.offset / col.k, V.bigStrip.length);
        r = col.start + col.k - 1;
      } else {
        await stopReel(x, o.stops[r], x.strip.length);
        for (let row = 0; row < 4; row++) { const s = o.landed[r * 4 + row]; if (seen[s] != null) seen[s]++; }
      }
      x.glow = 0;
      if (!S.hurry) await wait(0.12);
    }
    await wait(0.05);
    S.grid = o.afterColossal.slice(); S.landed = true;
    S.hurry = false;
    // Wild Reels: the armadillo rolls down each one.
    for (const r of o.wildReels) {
      const f = flyer({ img: "armadillo", x: REEL_X + r * CELL_W + CELL_W / 2, y: REEL_Y - 40, size: 130, rot: 0 });
      const drop = { y: f.y };
      const roll = tween(f, { y: REEL_Y + REEL_H + 40, rot: Math.PI * 6 }, 0.9, ease.inOut);
      for (let row = 0; row < 4; row++) {
        await wait(0.2);
        const c = r * 4 + row;
        if (!M.SCATTERS.includes(S.grid[c])) { S.grid[c] = "W"; S.cellFx[c] = { scale: 1.25, glow: 1 }; tween(S.cellFx[c], { scale: 1, glow: 0 }, 0.4); }
      }
      await roll; f.dead = true;
    }
    // Random Wilds: shots ring out and stars land.
    for (const c of o.wilds) {
      const { x, y } = cellRect(c);
      const f = flyer({ x: x + CELL_W / 2, y: y + CELL_H / 2, flash: true, s: 1.4, a: 1 });
      tween(f, { s: 0.2, a: 0 }, 0.3).then(() => (f.dead = true));
      S.shake = 0.35;
      S.grid[c] = "W"; S.cellFx[c] = { scale: 1.7, glow: 1 }; tween(S.cellFx[c], { scale: 1, glow: 0 }, 0.35, ease.back);
      await wait(0.32);
    }
    // Symbol Upgrade.
    if (o.upgrade) {
      S.featureLit.upgrade = true;
      const { from, to, cells } = o.upgrade;
      for (const c of cells) S.cellFx[c] = { glow: 1, glowColour: "#7affd9" };
      await banner("SYMBOL UPGRADE", `${V.symbols[from]} \u2192 ${V.symbols[to]}`, 1.2);
      for (const c of cells) { S.cellFx[c].flip = 0; tween(S.cellFx[c], { flip: 0.5 }, 0.22, ease.lin); }
      await wait(0.22);
      for (const c of cells) { S.grid[c] = to; tween(S.cellFx[c], { flip: 1 }, 0.22, ease.lin); }
      if (S.colossal) for (const c of cells) S.cellFx[c].big = true;
      await wait(0.3);
      for (const c of cells) S.cellFx[c] = { glow: 0 };
    }
    // The line wins.
    if (o.wins.length) {
      S.wins = o.wins; S.cycle = 0;
      for (const w of o.wins) for (const c of w.cells) { S.cellFx[c] = S.cellFx[c] || {}; S.cellFx[c].scale = 1.1; tween(S.cellFx[c], { scale: 1 }, 0.5, ease.back); }
      S.roller = Math.max(o.lineWin / 0.9, bet()); S.winTarget += o.lineWin;
      S.message = S.multiplier > 1 ? `LINE WINS ${money(o.lineWin)} (\u00d7${S.multiplier})` : `LINE WINS ${money(o.lineWin)}`;
      await wait(1.1);
      if (o.repeat) {
        S.featureLit.repeat = true;
        for (let i = 2; i <= o.repeat; i++) {
          await banner("REPEAT WIN", `pays again: ${i} of ${o.repeat}`, 1.0);
          S.winTarget += o.lineWin; S.cellFx = {}; for (const w of o.wins) for (const c of w.cells) { S.cellFx[c] = { scale: 1.15, glow: 1 }; tween(S.cellFx[c], { scale: 1, glow: 0 }, 0.6); }
          await wait(0.5);
        }
      }
    }
    if (o.instant) {
      S.featureLit.instant = true;
      const f = flyer({ img: "barrel", x: 640, y: REEL_Y + REEL_H / 2, size: 220, s: 0.2 });
      await tween(f, { s: 1 }, 0.45, ease.back);
      coinBurst(640, REEL_Y + REEL_H / 2 - 40, 40);
      f.text = null;
      const t = flyer({ text: `INSTANT WIN ${money(o.instant)}`, x: 640, y: REEL_Y + REEL_H / 2 + 120, textSize: 48, s: 0.4 });
      tween(t, { s: 1 }, 0.3, ease.back);
      S.roller = Math.max(o.instant, bet()); S.winTarget += o.instant;
      await wait(1.3);
      tween(f, { a: 0 }, 0.3); await tween(t, { a: 0 }, 0.3); f.dead = t.dead = true;
    }
    if (o.total >= 10 * o.bet && !o.free) await bigWin(o.total, o.bet);
    S.winShown = S.winTarget;
  }
  function startReel(x, v, i) {
    x.stopping = false;
    setTimeout(() => { x.spinning = true; x.v = 0; tween(x, { v }, 0.25, ease.lin); }, i * 40);
  }
  async function stopReel(x, stop, len) {
    // Land with the stop index on the top row: travel at least 3 more symbols, overshoot, settle back.
    x.spinning = false; x.stopping = true;
    let target = stop + Math.floor(x.pos / len) * len;
    while (target > x.pos - 3) target -= len;
    const dur = (S.hurry ? 0.12 : 0.34);
    x.v = 0;
    await tween(x, { pos: target - 0.18 }, dur, ease.out);
    await tween(x, { pos: target }, 0.14, ease.out);
    x.pos = ((target % len) + len) % len; x.stopping = false;
  }
  async function bigWin(total, b) {
    const x = total / b, title = x >= 50 ? "EPIC WIN" : x >= 25 ? "MEGA WIN" : "BIG WIN";
    S.overlay = { kind: "bigwin", title, shown: 0, t0: S.now };
    coinRain(70);
    const rain = setInterval(() => coinRain(18), 600);
    const done = new Promise((res) => (S.overlay.done = res));
    tween(S.overlay, { shown: total }, x >= 50 ? 5 : x >= 25 ? 4 : 3, ease.out).then(() => setTimeout(() => S.overlay && S.overlay.done && S.overlay.done(), 1500 / pace()));
    await done;
    clearInterval(rain);
    S.overlay = null;
  }
  function summary(title, sub, amount) {
    return new Promise((res) => { S.overlay = { kind: "summary", title, sub, amount, done: res, t0: S.now }; coinBurst(640, 380, 50, 1.4); })
      .then(() => { S.overlay = null; });
  }

  // ------------------------------------------------------------------ ways in
  // Which bonuses a way in plays ("BS", "FS" or "buy"); several means one of them at random.
  const routes = (way) => (V.routes || M.ROUTES)[way] || [];
  const plays = (kinds) => kinds.map((k) => k === "trail" ? TEXT.bonus[1] : k === "battle" ? TEXT.battle : k === "voyage" ? TEXT.voyage.name : TEXT.free[1]).join(" OR ");
  const buyIcon = () => M.SCATTERS.find((s) => routes("buy").some((k) => routes(s).includes(k))) || "BS";
  function playBonus(kind, b, bought) {
    return kind === "free" ? freeGames(b, bought) : kind === "battle" ? battleBonus(b, bought) : kind === "voyage" ? voyageBonus(b, bought) : trailBonus(b, bought);
  }

  // ------------------------------------------------------------------ Combo Free Games
  // `games`: how many (a battle's ships and a voyage's Port Royal give their own number, won in `from`; otherwise the slot's).
  async function freeGames(b, bought = false, games = 0, from = TEXT.battle) {
    const n = games || V.freeGames;
    S.free = { n: 0, of: n, total: 0 };
    await banner(TEXT.freeName, bought ? "bought for " + money(b * V.buyCost) : games ? `${n} won in ${from.toLowerCase()} \u00b7 a random feature every spin` : `${n} games \u00b7 a random feature every spin`, 2.2);
    for (let i = 1; i <= n; i++) {
      S.free.n = i; S.message = `FREE GAME ${i} OF ${n}`;
      clearWins(); S.winShown = S.winTarget = S.free.total;
      const o = M.spinOutcome(V, b, rng, { free: true });
      await playSpin(o);
      S.free.total += o.total;
      await wait(0.9);
    }
    const total = S.free.total;
    S.balance += total;
    await summary(TEXT.freeName, `${n} games at ${money(b)}`, total);
    if (total >= 10 * b) await bigWin(total, b);
    S.free = null; S.message = `FREE GAMES PAID ${money(total)}`;
    clearWins(); S.winShown = S.winTarget = total;
  }

  // ------------------------------------------------------------------ the Jackpot Pick
  async function jackpotPick(tier) {
    const { seq, rest } = M.pickSequence(tier, rng);
    S.mode = "pick";
    S.pick = { tier, seq, rest, step: 0, coins: Array.from({ length: 12 }, () => ({ tier: null, flip: 0, s: 1 })), tally: {}, lit: null, done: false };
    await banner("JACKPOT PICK", "pick coins until three match", 1.8);
    await new Promise((res) => (S.pick.finish = res));
    S.mode = "reels"; S.pick = null;
  }
  async function pickCoin(i) {
    const P = S.pick;
    if (!P || P.done || P.coins[i].tier || P.flipping) return;
    P.flipping = true;
    const coin = P.coins[i], id = P.seq[P.step++];
    await tween(coin, { flip: 0.5 }, 0.16, ease.lin); coin.tier = id; await tween(coin, { flip: 1 }, 0.16, ease.lin);
    P.tally[id] = (P.tally[id] || 0) + 1;
    P.flipping = false;
    if (P.step === P.seq.length) {
      P.done = true; P.lit = id;
      const t = M.JACKPOT_TIERS.find((q) => q.id === id);
      const amount = Math.floor(S.meters[id]);
      for (const c of P.coins) if (c.tier === id) tween(c, { s: 1.2 }, 0.4, ease.back);
      await wait(1.0);
      P.coins.forEach((c, j) => { if (!c.tier) { c.tier = P.rest.shift(); c.dim = true; c.flip = 1; } });
      await wait(0.8);
      S.meters[id] = t.seed; S.metersShown[id] = t.seed;
      S.balance += amount;
      coinRain(90);
      await summary(`${t.name} JACKPOT`, "shared by every slot on the floor", amount);
      P.lit = null; P.finish();
    }
  }
  function drawPick() {
    const P = S.pick;
    ctx.fillStyle = dark(C.shade, 0.6, 0.82); ctx.fillRect(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36);
    woodPanel(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36, 18);
    goldText("PICK A COIN", 640, REEL_Y + 22, 40);
    P.coins.forEach((c, i) => {
      const col = i % 4, row = Math.floor(i / 4);
      const cx = REEL_X + 105 + col * 180, cy = REEL_Y + 125 + row * 128, r = 52 * c.s;
      const hover = S.hover === "coin" + i && !c.tier && !P.done;
      if (!P.done && !c.tier) S.hits.push({ id: "coin" + i, x: cx - r, y: cy - r, w: r * 2, h: r * 2 });
      ctx.save(); ctx.translate(cx, cy); ctx.scale(Math.max(0.05, Math.abs(Math.cos(c.flip * Math.PI))), 1);
      if (c.dim) ctx.globalAlpha = 0.45;
      const face = c.tier && c.flip >= 0.5 ? C.tiers[c.tier] : null;
      const g = ctx.createRadialGradient(-r * 0.3, -r * 0.3, 4, 0, 0, r);
      if (face) { g.addColorStop(0, "#ffffff"); g.addColorStop(0.35, face); g.addColorStop(1, C.shade); }
      else { g.addColorStop(0, C.goldHi); g.addColorStop(0.5, hover ? mix(C.gold, C.goldHi, 0.4) : C.gold); g.addColorStop(1, C.goldLo); }
      ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.fillStyle = g; ctx.fill();
      ctx.lineWidth = 4; ctx.strokeStyle = P.done && c.tier === P.lit && !c.dim ? "#fff" : dark(C.goldLo, 0.4); ctx.stroke();
      if (face) text(M.JACKPOT_TIERS.find((q) => q.id === c.tier).name, 0, 2, 26, COND, "#fff", "center", "700", 5);
      else { drawImg(img("t_coin"), -r * 0.7, -r * 0.7, r * 1.4, r * 1.4); }
      ctx.restore();
    });
    // the tally under the meters' colours
    M.JACKPOT_TIERS.forEach((t, i) => {
      const x = REEL_X + 60 + i * 180, y = REEL_Y + REEL_H - 22;
      text(t.name, x, y, 20, COND, C.tiers[t.id], "left", "700", 4);
      for (let k = 0; k < 3; k++) {
        ctx.beginPath(); ctx.arc(x + 76 + k * 22, y, 8, 0, 7);
        ctx.fillStyle = (P.tally[t.id] || 0) > k ? C.tiers[t.id] : "rgba(255,255,255,0.15)"; ctx.fill();
      }
    });
  }

  // ------------------------------------------------------------------ the Trail Bonus
  const TILE = 86;
  const trailPos = (i) => ({ x: 120 + i * TILE, y: 400 + Math.sin(i * 0.55) * 64 + Math.sin(i * 0.17) * 30 });
  async function trailBonus(b, bought) {
    const st = M.trailStart(V, b, rng);
    S.mode = "trail";
    S.trail = { st, cam: 0, token: { i: 0, x: trailPos(0).x, y: trailPos(0).y, hop: 0, sq: 1 }, bullets: 0, cyl: 0, total: 0,
                hearts: 0, waiting: false, autoAt: 0, popups: [], snakeHit: null };
    S.trail.cam = S.trail.token.x - 330;
    await banner(TEXT.bonus[1], bought ? "bought for " + money(b * V.buyCost) : TEXT.trailHint, 2.2);
    while (!st.done) {
      S.trail.waiting = true; S.trail.autoAt = S.now + 6;
      S.message = "FIRE THE PISTOL \u00b7 SPACE OR CLICK FIRE";
      await new Promise((res) => (S.trail.fire = res));
      S.trail.waiting = false;
      const roll = M.trailRoll(V, st, rng);
      await animateRoll(roll);
    }
    await wait(0.8);
    const total = st.total;
    S.balance += total;
    await summary(st.pos >= st.board.length - 1 ? "PRIZEPOT!" : TEXT.bonus[1], `${st.rolls} shots at ${money(b)}`, total);
    if (total >= 10 * b) await bigWin(total, b);
    S.mode = "reels"; S.trail = null; clearWins(); S.winShown = S.winTarget = total;
    S.message = `${TEXT.bonus[1]} PAID ${money(total)}`;
  }
  async function animateRoll(roll) {
    const T = S.trail, st = T.st;
    // load and spin the cylinder
    T.bullets = 0;
    for (let i = 0; i < roll.bullets; i++) { T.bullets = i + 1; await wait(0.09); }
    await tween(T, { cyl: T.cyl + Math.PI * 2 * (2 + roll.bullets / 6) }, 0.6, ease.out);
    const f = flyer({ text: st.upgraded && !roll.events.some((e) => e.kind === "upgrade") ? `${roll.bullets} \u00d7 2 = ${roll.move}` : `${roll.bullets}`, x: 1130, y: 250, textSize: 64, s: 0.3 });
    tween(f, { s: 1 }, 0.25, ease.back).then(() => wait(0.5)).then(() => tween(f, { a: 0 }, 0.25)).then(() => (f.dead = true));
    const evs = roll.events.slice();
    const play = async (pos) => {
      while (evs.length && evs[0].pos === pos) await playEvent(evs.shift());
    };
    await play(roll.from);
    let at = roll.from;
    for (const p of roll.path) {
      await moveToken(p, Math.abs(p - at) > 1 ? "slide" : "hop");
      at = p;
      await play(p);
    }
    while (evs.length) await playEvent(evs.shift());
    T.bullets = 0;
  }
  async function moveToken(i, how) {
    const T = S.trail, tk = T.token, p = trailPos(i);
    if (how === "hop") {
      tk.hop = 0;
      await Promise.all([tween(tk, { x: p.x, y: p.y }, 0.2, ease.lin), tween(tk, { hop: 1 }, 0.2, ease.lin)]);
      tk.sq = 0.7; tween(tk, { sq: 1 }, 0.15, ease.back);
    } else {
      await tween(tk, { x: p.x, y: p.y }, 0.5, ease.inOut);
    }
    tk.i = i; tk.hop = 0;
  }
  async function playEvent(e) {
    const T = S.trail, st = T.st, p = trailPos(e.pos);
    const sx = p.x - T.cam, sy = p.y;
    const pop = (txt, colour) => {
      const f = flyer({ text: txt, x: sx, y: sy - 90, textSize: 40, colour, s: 0.4 });
      tween(f, { s: 1, y: sy - 130 }, 0.35, ease.back).then(() => wait(0.6)).then(() => tween(f, { a: 0 }, 0.3)).then(() => (f.dead = true));
    };
    switch (e.kind) {
      case "coin": case "prizepot":
        pop(money(e.pence), C.win); coinBurst(sx, sy - 30, e.kind === "prizepot" ? 80 : 12, 0.6);
        T.total += e.pence; S.winTarget = T.total; S.roller = Math.max(e.pence * 1.4, bet());
        await wait(e.kind === "prizepot" ? 1.6 : 0.55); break;
      case "heart": pop("+1 HEART", "#ff8a80"); T.hearts++; await wait(0.6); break;
      case "heart_used": pop("SAVED BY A HEART", "#ff8a80"); T.snakeHit = { pos: e.pos, t0: S.now }; S.shake = 0.6; T.hearts--; await wait(0.9); break;
      case "snake": pop("SNAKE BITE!", "#ff5a48"); T.snakeHit = { pos: e.pos, t0: S.now }; S.shake = 1; await wait(1.2); break;
      case "double": pop("DOUBLE! ALL COINS \u00d72", "#ffb347"); T.doubleAt = S.now; await wait(1.1); break;
      case "upgrade": pop("SPIN UPGRADE: MOVES \u00d72", "#7affd9"); await wait(1.0); break;
      case "lightning": pop("LIGHTNING ROLL NEXT", "#ffe14a"); await wait(0.9); break;
      case "lightning_roll": pop("LIGHTNING ROLL!", "#ffe14a"); T.lightningAt = S.now; await wait(0.6); break;
      case "crate": pop(`CRATE: COINS WITHIN ${e.r}`, "#ffb347"); T.crate = { pos: e.pos, r: e.r, t0: S.now };
        if (e.pence) { T.total += e.pence; S.winTarget = T.total; S.roller = Math.max(e.pence, bet()); coinBurst(sx, sy - 30, 24, 0.8); }
        await wait(1.0); break;
      case "forward": pop(`FORWARD ${e.n}`, "#9cff6b"); await wait(0.6); break;
      case "back": pop(`BACK ${e.n}`, "#ff9e4a"); await wait(0.6); break;
    }
  }
  function drawTrail() {
    const T = S.trail, st = T.st, b = st.board;
    const road = mix(C.edge, C.cream, 0.2);
    // camera follows the armadillo
    const want = T.token.x - 380;
    T.cam += (want - T.cam) * 0.08;
    const x0 = REEL_X - 22, y0 = REEL_Y - 18, w0 = REEL_W + 44 + 1262 - (REEL_X + REEL_W + 22) - 2 + 240, h0 = REEL_H + 36;
    ctx.save();
    rr(18, y0, 1010, h0, 18); ctx.clip();
    ctx.fillStyle = alpha(mix(C.shade, C.edge, 0.1), 0.35); ctx.fillRect(18, y0, 1010, h0);
    // the road, in the design's edge colour
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    for (const [w, c] of [[64, alpha(mix(C.shade, C.edge, 0.15), 0.55)], [50, dark(road, 0.08)], [44, road]]) {
      ctx.beginPath();
      for (let i = 0; i < b.length; i++) { const p = trailPos(i); const x = p.x - T.cam; if (i === 0) ctx.moveTo(x, p.y); else ctx.lineTo(x, p.y); }
      ctx.lineWidth = w; ctx.strokeStyle = c; ctx.stroke();
    }
    const lo = Math.max(0, Math.floor((T.cam - 100) / TILE)), hi = Math.min(b.length - 1, Math.ceil((T.cam + 1400) / TILE));
    const dbl = T.doubleAt && S.now - T.doubleAt < 0.8;
    for (let i = lo; i <= hi; i++) {
      const p = trailPos(i), x = p.x - T.cam, y = p.y, sp = b[i];
      const end = sp.type === "prizepot", sz = end ? 120 : 64;
      ctx.save();
      if (sp.taken) ctx.globalAlpha = 0.35;
      const crate = T.crate && S.now - T.crate.t0 < 1.0 && Math.abs(i - T.crate.pos) <= T.crate.r;
      const light = T.lightningAt && S.now - T.lightningAt < 1.2 && i > T.token.i - 7 && i <= T.token.i;
      rr(x - sz / 2, y - sz / 2, sz, sz, 12);
      ctx.fillStyle = sp.type === "snake" ? dark(C.alert, 0.25) : end ? dark(C.goldLo, 0.42) : mix(C.shade, C.edge, 0.2); ctx.fill();
      ctx.lineWidth = crate || light ? 4 : 2; ctx.strokeStyle = crate ? "#ffb347" : light ? "#ffe14a" : C.edge; ctx.stroke();
      const icon = { coin: "t_coin", snake: "t_snake", heart: "t_heart", forward: "t_forward", back: "t_forward", lightning: "t_lightning",
                     crate: "t_crate", upgrade: "t_upgrade", double: "t_double", prizepot: "t_gold" }[sp.type];
      if (icon) {
        ctx.save(); ctx.translate(x, y - (sp.type === "coin" || end ? 6 : 0));
        if (sp.type === "back") ctx.scale(-1, 1);
        const is = sz * 0.82; drawImg(img(icon), -is / 2, -is / 2, is, is); ctx.restore();
      }
      if (sp.type === "coin" || end) {
        const pulse = dbl ? 1.25 : 1;
        text(end ? `${sp.x}\u00d7` : `${sp.x}\u00d7`, x, y + sz / 2 - 10, (end ? 26 : 19) * pulse, COND, "#fff", "center", "700", 4);
      }
      if (sp.type === "double") text("\u00d72", x, y + 2, 26, COND, "#fff", "center", "700", 5);
      if (sp.type === "start") text("START", x, y, 20, COND, C.goldHi, "center", "700", 4);
      ctx.restore();
    }
    // the armadillo
    const tk = T.token, tx = tk.x - T.cam, ty = tk.y - 46 - Math.sin(tk.hop * Math.PI) * 46;
    ctx.save(); ctx.translate(tx, ty + 30); ctx.scale(1 / tk.sq ** 0.3, tk.sq); drawImg(img("armadillo"), -55, -82, 110, 110); ctx.restore();
    // the snake strikes
    if (T.snakeHit && S.now - T.snakeHit.t0 < 1.1) {
      const p = trailPos(T.snakeHit.pos), k = Math.min(1, (S.now - T.snakeHit.t0) * 4);
      drawImg(img("t_snake"), p.x - T.cam + 10, p.y - 60 - 50 * k, 110, 110);
    }
    ctx.restore();
    // the HUD: progress, hearts, chips, the cylinder and FIRE
    const prog = tk.i / (b.length - 1);
    rr(40, REEL_Y - 8, 900, 18, 9); ctx.fillStyle = alpha(C.shade, 0.8); ctx.fill();
    rr(40, REEL_Y - 8, 900 * prog, 18, 9); ctx.fillStyle = road; ctx.fill();
    drawImg(img("t_gold"), 930, REEL_Y - 28, 50, 50);
    drawImg(img("armadillo"), 40 + 900 * prog - 20, REEL_Y - 34, 44, 44);
    text(`TRAIL WIN ${money(T.total)}`, 640, REEL_Y + 34, 34, COND, C.win, "center", "700", 6);
    for (let h = 0; h < T.hearts; h++) drawImg(img("t_heart"), 40 + h * 46, REEL_Y + 18, 44, 44);
    let cx = 40 + Math.max(1, T.hearts) * 46 + 10;
    if (st.upgraded) { rr(cx, REEL_Y + 24, 150, 32, 8); ctx.fillStyle = "#1d6b62"; ctx.fill(); text("MOVES \u00d72", cx + 75, REEL_Y + 41, 20, COND, "#fff"); cx += 160; }
    if (st.doubled) { rr(cx, REEL_Y + 24, 150, 32, 8); ctx.fillStyle = C.alert; ctx.fill(); text("COINS DOUBLED", cx + 75, REEL_Y + 41, 20, COND, "#fff"); }
    woodPanel(1038, REEL_Y - 18, 224, REEL_H + 36, 16);
    text(TEXT.pistol, 1150, REEL_Y + 10, 22, COND, C.goldHi);
    text(st.upgraded ? "moves doubled" : "1 to 6 spaces a shot", 1150, REEL_Y + 34, 16, COND, C.cream);
    const cyx = 1150, cyy = REEL_Y + 150;
    ctx.save(); ctx.translate(cyx, cyy); ctx.rotate(T.cyl); drawImg(img("cylinder"), -78, -78, 156, 156);
    for (let k = 0; k < T.bullets; k++) {
      const a = -Math.PI / 2 + (k * Math.PI) / 3;
      ctx.beginPath(); ctx.arc(Math.cos(a) * 35, Math.sin(a) * 35, 13, 0, 7);
      const g = ctx.createRadialGradient(Math.cos(a) * 35 - 4, Math.sin(a) * 35 - 4, 2, Math.cos(a) * 35, Math.sin(a) * 35, 13);
      g.addColorStop(0, C.goldHi); g.addColorStop(1, mix(C.gold, C.goldLo, 0.5)); ctx.fillStyle = g; ctx.fill();
    }
    ctx.restore();
    if (T.waiting) {
      const left = Math.max(0, T.autoAt - S.now);
      button("fire", cyx - 80, cyy + 100, 160, 58, "FIRE", { colour: fireBtn(), size: 32 });
      text(`fires itself in ${Math.ceil(left)}`, cyx, cyy + 176, 16, COND, C.muted);
      if (left <= 0) fire();
    }
  }
  function fire() { if (S.trail && S.trail.waiting && S.trail.fire) { const f = S.trail.fire; S.trail.fire = null; f(); } }

  // ------------------------------------------------------------------ the wave battle (Red Alert)
  // Your ship on the left; each wave's ships in a loose formation on the right, drifting and cloaking now and then
  // (only for show: a cloaked ship can't be targeted, and the draw is the same whichever ship you shoot). The scene
  // fills the trail's area; the right-hand panel shows the wave, shields, what's banked and FIRE. Its timings match
  // bonuses.py _BATTLE_SECONDS (0.6s for the beam, then each event's own).
  const B_AREA = { x: 18, y: REEL_Y - 18, w: 1010, h: REEL_H + 36 };
  const HERO = { x: 200, y: 352 };
  const BOSS_AT = { x: 760, y: 385 };
  const STARS = Array.from({ length: 140 }, () => ({ x: rng() * 1010, y: rng() * (REEL_H + 36), r: 0.6 + rng() * 1.8, v: 6 + rng() * 40 }));
  function shipSpot(i, n) {
    const rows = n <= 2 ? n : n <= 6 ? 2 : 3, cols = Math.ceil(n / rows), r = i % rows, c = Math.floor(i / rows);
    const dx = cols > 1 ? 380 / (cols - 1) : 0, stagger = r % 2 ? Math.min(60, dx * 0.3) : 0;   // stays clear of the panel
    return { x: (cols > 1 ? 510 + c * dx : 730) + stagger, y: rows > 1 ? 240 + r * (275 / (rows - 1)) : 378 };
  }
  const shipSize = (n) => n <= 6 ? 124 : 104;
  function battleShips(n, t0) { return Array.from({ length: n }, (_, i) => ({ i, ...shipSpot(i, n), phase: (i * 0.618 + rng() * 0.2) % 1, born: t0, dead: 0, evade: 0 })); }
  function shipPos(sh) {
    return { x: sh.x + Math.cos(S.now * 0.9 + sh.i * 1.3) * 7 + Math.max(0, 1 - (S.now - sh.born) / 0.6) * 300, y: sh.y + Math.sin(S.now * 1.3 + sh.i * 1.7) * 9 };
  }
  // How cloaked a ship is (0 to 1): a 9-second cycle, cloaked for about a fifth of it, never while it's being shot,
  // never for the last two, and never all of them at once (drawBattle picks one to stay visible).
  function cloakOf(sh) {
    const B = S.battle;
    if (B.aim === sh.i || B.forced === sh.i) return 0;
    return rawCloak(sh);
  }
  function rawCloak(sh) {
    if (sh.evade && S.now - sh.evade < 1.2) return Math.sin(Math.min(1, (S.now - sh.evade) / 1.2) * Math.PI);   // it answered
    if (S.battle.alive < 3) return 0;   // the last two ships stay in sight
    const f = (S.now / 9 + sh.phase) % 1;
    return f < 0.72 ? 0 : f < 0.76 ? (f - 0.72) / 0.04 : f < 0.9 ? 1 : f < 0.94 ? 1 - (f - 0.9) / 0.04 : 0;
  }
  function targetable() {
    return S.battle.ships.filter((sh) => !sh.dead && S.now - sh.born > 0.6 && cloakOf(sh) < 0.5);
  }
  async function battleBonus(b, bought) {
    const st = M.battleStart(V, b);
    S.mode = "battle";
    S.battle = { st, ships: battleShips(st.ships.length, S.now), shields: st.shields, total: 0, spins: 0, wave: 0, boss: null,
                 beam: null, bolts: [], booms: [], shieldAt: -9, restoreAt: -9, heroDown: false, aim: null, waiting: false, autoAt: 0, alertAt: S.now };
    await banner(TEXT.battle, bought ? "bought for " + money(b * V.buyCost) : TEXT.battleHint, 2.6);
    while (!st.done) {
      const B = S.battle;
      B.waiting = true; B.autoAt = S.now + 8;
      S.message = st.bossHp !== null ? `FIRE ON THE ${TEXT.boss} · SPACE OR CLICK FIRE` : "TAP A SHIP TO FIRE · SPACE FIRES AT ONE";
      const target = await new Promise((res) => (B.fire = res));
      B.waiting = false;
      await animateShot(M.battleShot(V, st, rng, target));
    }
    await wait(0.8);
    const total = st.total;
    S.balance += total;
    const spins = st.spins ? ` · ${st.spins} free game${st.spins > 1 ? "s" : ""} to come` : "";
    await summary(st.won ? `${TEXT.boss} DESTROYED!` : TEXT.battle, `${st.cleared} of ${st.waves} waves cleared${spins}`, total);
    if (total >= 10 * b) await bigWin(total, b);
    S.mode = "reels"; S.battle = null; clearWins(); S.winShown = S.winTarget = total;
    S.message = `${TEXT.battle} PAID ${money(total)}`;
    if (st.spins) await freeGames(b, false, st.spins);
  }
  function fireBattle(target) {
    const B = S.battle;
    if (!B || !B.waiting || !B.fire) return;
    if (target == null && B.st.bossHp === null) { const open = targetable(); target = open.length ? open[Math.floor(rng() * open.length)].i : null; }
    const f = B.fire; B.fire = null; f(target);
  }
  function boom(x, y, size) { S.battle.booms.push({ x, y, size, t0: S.now, bits: Array.from({ length: 14 }, () => ({ a: rng() * 7, v: 0.4 + rng() })) }); }
  function battlePop(txt, colour, x, y, size = 40) {
    const f = flyer({ text: txt, x, y: y - 50, textSize: size, colour, s: 0.4 });
    tween(f, { s: 1, y: y - 95 }, 0.35, ease.back).then(() => wait(0.7)).then(() => tween(f, { a: 0 }, 0.3)).then(() => (f.dead = true));
  }
  async function animateShot(shot) {
    const B = S.battle, boss = shot.target === "boss";
    const sh = boss ? null : B.ships[shot.target];
    B.aim = boss ? null : shot.target;
    const at = () => boss ? BOSS_AT : shipPos(sh);
    B.beam = { to: at, t0: S.now };
    await wait(0.6);
    for (const e of shot.events) {
      const p = at();
      switch (e.kind) {
        case "return_fire":
          if (sh) sh.evade = S.now;
          B.bolts.push({ from: { ...p }, t0: S.now }, { from: { x: p.x, y: p.y + 14 }, t0: S.now + 0.12 });
          await wait(0.45);
          B.shields = e.shields; B.shieldAt = S.now; S.shake = 0.5;
          battlePop(e.shields > 0 ? `SHIELDS ${e.shields}/${B.st.maxShields}` : "SHIELDS FAILING", "#ff6a5a", HERO.x, HERO.y - 40, 34);
          await wait(0.55); break;
        case "shields_down":
          B.heroDown = true; boom(HERO.x + 20, HERO.y, 150); S.shake = 1;
          battlePop("SHIELDS DOWN", "#ff5a48", HERO.x + 60, HERO.y - 60, 46);
          await wait(1.6); break;
        case "destroyed":
          sh.dead = S.now; boom(p.x, p.y, 110); B.aim = null;
          if (e.spins) { B.spins += e.spins; battlePop(`+${e.spins} FREE GAME${e.spins > 1 ? "S" : ""}`, "#7fd0ff", p.x, p.y); }
          else { B.total += e.pence; S.winTarget = B.total; S.roller = Math.max(e.pence * 1.4, bet()); battlePop(money(e.pence), C.win, p.x, p.y); }
          await wait(0.9); break;
        case "wave_clear":
          B.total += e.pence; S.winTarget = B.total; S.roller = Math.max(e.pence, bet());
          battlePop(`WAVE ${e.wave + 1} CLEARED  +${money(e.pence)}`, C.goldHi, 523, 330, 48);
          coinBurst(523, 330, 30, 1);
          await wait(1.0);
          B.shields = B.st.maxShields; B.restoreAt = S.now;
          await wait(0.8); break;
        case "wave_start":
          B.wave = e.wave; B.ships = battleShips(e.ships, S.now + 0.3);
          battlePop(`WAVE ${e.wave + 1} OF ${B.st.waves}`, "#ff8a6a", 523, 300, 44);
          await wait(1.6); break;
        case "boss_start":
          B.ships = []; B.boss = { hp: e.hp, max: e.hp, t0: S.now, hitAt: -9, dead: 0 }; S.shake = 0.6; B.alertAt = S.now;
          battlePop(`${TEXT.boss} INCOMING`, "#ff5a48", 523, 220, 52);
          await wait(2.4); break;
        case "boss_hit":
          B.boss.hp = e.hp; B.boss.hitAt = S.now; boom(p.x + (rng() - 0.5) * 120, p.y + (rng() - 0.5) * 80, 70);
          await wait(0.7); break;
        case "boss_destroyed":
          B.boss.dead = S.now; boom(p.x, p.y, 320); S.shake = 1.2; coinRain(80);
          B.total += e.pence; S.winTarget = B.total; S.roller = Math.max(e.pence, bet());
          battlePop(`${TEXT.boss} DESTROYED  ${money(e.pence)}`, C.goldHi, 523, 300, 52);
          await wait(2.6); break;
      }
    }
    B.aim = null;
  }
  function drawBattle() {
    const B = S.battle, st = B.st, A = B_AREA;
    const alive = B.ships.filter((sh) => !sh.dead);
    const hidden = alive.length > 0 && alive.every((sh) => rawCloak(sh) >= 0.5);
    B.forced = hidden ? (alive.some((sh) => sh.i === B.forced) ? B.forced : alive[0].i) : null;
    B.alive = alive.length;
    ctx.save();
    rr(A.x, A.y, A.w, A.h, 18); ctx.clip();
    const sky = ctx.createLinearGradient(0, A.y, 0, A.y + A.h);
    sky.addColorStop(0, "#03040c"); sky.addColorStop(1, "#0b1030");
    ctx.fillStyle = sky; ctx.fillRect(A.x, A.y, A.w, A.h);
    if (bgImg && ok(bgImg)) { ctx.globalAlpha = 0.25; ctx.drawImage(bgImg, A.x, A.y, A.w, A.h); ctx.globalAlpha = 1; }
    for (const s of STARS) {
      const x = A.x + ((s.x - S.now * s.v) % A.w + A.w) % A.w;
      ctx.fillStyle = `rgba(220,230,255,${0.35 + s.r / 3})`; ctx.fillRect(x, A.y + s.y, s.r, s.r);
    }
    // red alert: the edges pulse red for a moment at the start and when the boss arrives
    const alert = Math.max(0, 1 - (S.now - B.alertAt) / 3);
    if (alert > 0) {
      const g = ctx.createRadialGradient(523, 352, 200, 523, 352, 640);
      g.addColorStop(0, "rgba(255,0,0,0)"); g.addColorStop(1, `rgba(255,30,20,${0.45 * alert * (0.6 + 0.4 * Math.sin(S.now * 10))})`);
      ctx.fillStyle = g; ctx.fillRect(A.x, A.y, A.w, A.h);
    }
    // your ship and its shields
    const hy = HERO.y + Math.sin(S.now * 1.1) * 6;
    const hit = Math.max(0, 1 - (S.now - B.shieldAt) / 0.6), up = Math.max(0, 1 - (S.now - B.restoreAt) / 0.9);
    const strength = B.shields / st.maxShields;
    if (strength > 0 || hit > 0) {
      ctx.beginPath(); ctx.ellipse(HERO.x, hy, 140, 100, 0, 0, 7);
      ctx.fillStyle = `rgba(90,170,255,${0.06 + 0.08 * strength + 0.3 * hit + 0.25 * up})`; ctx.fill();
      ctx.lineWidth = 2 + 4 * hit; ctx.strokeStyle = `rgba(140,210,255,${0.25 + 0.4 * strength + 0.6 * hit})`; ctx.stroke();
    }
    ctx.save(); if (B.heroDown) ctx.globalAlpha = 0.55;
    drawImg(img("b_hero"), HERO.x - 120, hy - 120, 240, 240); ctx.restore();
    // the enemy ships
    const n = B.ships.length, size = shipSize(n), open = B.waiting ? new Set(targetable().map((sh) => sh.i)) : new Set();
    for (const sh of B.ships) {
      const age = sh.dead ? S.now - sh.dead : 0;
      if (sh.dead && age > 0.4) continue;
      const p = shipPos(sh), cl = cloakOf(sh), z = sh.dead ? 1 - age / 0.4 : 1;
      if (S.now < sh.born) continue;
      ctx.save();
      ctx.globalAlpha = Math.min(1, (S.now - sh.born) / 0.6) * (1 - 0.88 * cl) * z;
      drawImg(img("b_enemy"), p.x - size / 2 * z, p.y - size / 2 * z, size * z, size * z);
      ctx.restore();
      if (cl > 0.05 && !sh.dead) {   // the cloak's shimmer
        ctx.beginPath(); ctx.ellipse(p.x, p.y, size * 0.5, size * 0.3, 0, 0, 7);
        ctx.strokeStyle = `rgba(160,220,255,${0.35 * Math.sin(cl * Math.PI)})`; ctx.lineWidth = 2; ctx.stroke();
      }
      if (open.has(sh.i)) {
        const hover = S.hover === "ship" + sh.i;
        S.hits.push({ id: "ship" + sh.i, x: p.x - size / 2, y: p.y - size / 2, w: size, h: size });
        if (hover) {   // the targeting reticle
          ctx.strokeStyle = "#ff5a48"; ctx.lineWidth = 3;
          ctx.beginPath(); ctx.arc(p.x, p.y, size * 0.55, 0, 7); ctx.stroke();
          for (let k = 0; k < 4; k++) { const a = k * Math.PI / 2 + S.now; ctx.beginPath(); ctx.moveTo(p.x + Math.cos(a) * size * 0.45, p.y + Math.sin(a) * size * 0.45); ctx.lineTo(p.x + Math.cos(a) * size * 0.7, p.y + Math.sin(a) * size * 0.7); ctx.stroke(); }
        }
      }
    }
    // the boss
    if (B.boss && !(B.boss.dead && S.now - B.boss.dead > 0.6)) {
      const bz = B.boss.dead ? 1 - (S.now - B.boss.dead) / 0.6 : 1, enter = Math.min(1, (S.now - B.boss.t0) / 1.2);
      const bx = BOSS_AT.x + (1 - enter) * 400, by = BOSS_AT.y + Math.sin(S.now * 0.8) * 8, bs = 320 * bz;
      ctx.save(); ctx.globalAlpha = enter * bz;
      if (S.now - B.boss.hitAt < 0.15) ctx.filter = "brightness(2)";
      drawImg(img("b_boss"), bx - bs / 2, by - bs / 2, bs, bs); ctx.restore();
      if (B.waiting) S.hits.push({ id: "boss", x: bx - 160, y: by - 120, w: 320, h: 240 });
      rr(bx - 150, by - 150, 300, 20, 10); ctx.fillStyle = "rgba(0,0,0,0.6)"; ctx.fill();
      rr(bx - 150, by - 150, 300 * B.boss.hp / B.boss.max, 20, 10); ctx.fillStyle = "#e2402f"; ctx.fill();
      text(TEXT.boss, bx, by - 168, 22, COND, "#ffb4a6", "center", "700", 4);
    }
    // the phaser beam, the return fire and the explosions
    if (B.beam && S.now - B.beam.t0 < 0.45) {
      const t = B.beam.to(), k = 1 - (S.now - B.beam.t0) / 0.45;
      ctx.save(); ctx.lineCap = "round"; ctx.shadowColor = "#ff7a30"; ctx.shadowBlur = 18;
      ctx.strokeStyle = `rgba(255,140,60,${k})`; ctx.lineWidth = 9; ctx.beginPath(); ctx.moveTo(HERO.x + 100, hy - 6); ctx.lineTo(t.x, t.y); ctx.stroke();
      ctx.strokeStyle = `rgba(255,240,200,${k})`; ctx.lineWidth = 3; ctx.stroke(); ctx.restore();
    }
    B.bolts = B.bolts.filter((bo) => S.now - bo.t0 < 0.45);
    for (const bo of B.bolts) {
      const k = (S.now - bo.t0) / 0.45;
      if (k < 0) continue;
      const x = bo.from.x + (HERO.x + 60 - bo.from.x) * k, y = bo.from.y + (hy - bo.from.y) * k;
      ctx.save(); ctx.shadowColor = "#6aff6a"; ctx.shadowBlur = 16; ctx.fillStyle = "#b8ffb0";
      ctx.beginPath(); ctx.ellipse(x, y, 16, 6, Math.atan2(hy - bo.from.y, HERO.x - bo.from.x), 0, 7); ctx.fill(); ctx.restore();
    }
    B.booms = B.booms.filter((bm) => S.now - bm.t0 < 0.9);
    for (const bm of B.booms) {
      const k = (S.now - bm.t0) / 0.9, r = bm.size * (0.3 + k * 0.7);
      const g = ctx.createRadialGradient(bm.x, bm.y, 0, bm.x, bm.y, r);
      g.addColorStop(0, `rgba(255,250,210,${1 - k})`); g.addColorStop(0.4, `rgba(255,150,40,${0.9 * (1 - k)})`); g.addColorStop(1, "rgba(120,20,0,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(bm.x, bm.y, r, 0, 7); ctx.fill();
      ctx.fillStyle = `rgba(255,200,120,${1 - k})`;
      for (const bit of bm.bits) ctx.fillRect(bm.x + Math.cos(bit.a) * r * bit.v * 1.3, bm.y + Math.sin(bit.a) * r * bit.v * 1.3, 4, 4);
    }
    ctx.restore();
    // the top: wave progress (a pip a wave, then the boss) and the battle's win
    const steps = st.waves + 1;
    for (let k = 0; k < steps; k++) {
      const x = 60 + k * (880 / (steps - 1)), done = k < st.cleared || (k === st.waves && st.won), now = k === st.cleared && !st.done;
      ctx.beginPath(); ctx.arc(x, REEL_Y + 2, k === st.waves ? 14 : 10, 0, 7);
      ctx.fillStyle = done ? C.gold : now ? "#e2402f" : "rgba(255,255,255,0.15)"; ctx.fill();
      if (k < steps - 1) { ctx.fillStyle = "rgba(255,255,255,0.15)"; ctx.fillRect(x + 12, REEL_Y + 1, 880 / (steps - 1) - 24, 2); }
    }
    text(`${TEXT.battle} WIN ${money(B.total)}`, 523, REEL_Y + 30, 34, COND, C.win, "center", "700", 6, 600);
    // the panel: wave, shields, ships left, what's banked, FIRE
    woodPanel(1038, REEL_Y - 18, 224, REEL_H + 36, 16);
    text(TEXT.battle, 1150, REEL_Y + 10, 26, COND, "#ff6a5a", "center", "700", 0, 200);
    text(st.bossHp !== null || B.boss ? TEXT.boss : `WAVE ${Math.min(st.wave, st.waves - 1) + 1} OF ${st.waves}`, 1150, REEL_Y + 40, 22, COND, C.goldHi, "center", "700", 0, 200);
    text("SHIELDS", 1150, REEL_Y + 76, 18, COND, C.cream);
    const pw = Math.min(40, 180 / st.maxShields);
    for (let k = 0; k < st.maxShields; k++) {
      rr(1150 - st.maxShields * pw / 2 + k * pw + 3, REEL_Y + 88, pw - 6, 18, 5);
      ctx.fillStyle = k < B.shields ? "#5ab4ff" : "rgba(255,255,255,0.12)"; ctx.fill();
    }
    const left = B.ships.filter((sh) => !sh.dead).length;
    text(B.boss ? `HITS LEFT ${B.boss.hp}` : `${TEXT.enemy}: ${left} LEFT`, 1150, REEL_Y + 136, 18, COND, C.cream, "center", "700", 0, 200);
    text(`FREE GAMES WON ${B.spins}`, 1150, REEL_Y + 166, 18, COND, "#7fd0ff", "center", "700", 0, 200);
    if (B.waiting) {
      const wait = Math.max(0, B.autoAt - S.now);
      button("fire", 1070, REEL_Y + 300, 160, 58, "FIRE", { colour: fireBtn(), size: 32 });
      text(TEXT.battleHint, 1150, REEL_Y + 380, 16, COND, C.cream, "center", "700", 0, 200);
      text(`fires itself in ${Math.ceil(wait)}`, 1150, REEL_Y + 402, 16, COND, C.muted);
      if (wait <= 0) fireBattle(null);
    }
  }

  // ------------------------------------------------------------------ the island voyage (Dead Man's Map)
  // A sea chart filling the trail's area: the start port on the left, a column of three islands a leg, the final
  // island on the right, dotted sea lanes between neighbours. Click one of the lit islands to sail there (a cove
  // needs a key); at Port Royal the panel's deals trade relics. The panel keeps the hold: relics, keys, artefacts,
  // free games. Its timings match bonuses.py _VOYAGE_SECONDS (0.3s, then each event's own).
  const VT = () => TEXT.voyage;
  const ISLE_ART = { treasure: "v_treasure", wreck: "v_wreck", skull: "v_skull", port: "v_port", cove: "v_cove" };
  const isleName = (kind) => VT()[kind];
  const ROW_Y = [228, 352, 476];
  const vStep = (legs) => 860 / (legs + 1);
  function islePos(leg, row, legs) {   // leg -1 is the start port, `legs` the final island
    const x = 90 + (leg + 1) * vStep(legs);
    return { x, y: leg < 0 || leg >= legs ? 352 : ROW_Y[row] };
  }
  async function voyageBonus(b, bought) {
    const st = M.voyageStart(V, b, rng), legs = st.map.length, p0 = islePos(-1, 1, legs);
    S.mode = "voyage";
    S.voyage = { st, legs, shown: voyageShown(st), ship: { x: p0.x, y: p0.y - 34, rot: 0, sink: 0, a: 1 }, waiting: false, autoAt: 0,
                 reveal: null };
    await banner(VT().name, bought ? "bought for " + money(b * V.buyCost) : VT().hint, 2.6);
    while (!st.done) {
      const Y = S.voyage;
      Y.shown = voyageShown(st);
      Y.waiting = true; Y.autoAt = S.now + 12;
      S.message = st.awaiting === "trade" ? `${VT().port}: TRADE YOUR ${VT().relic}S, OR SET SAIL`
        : st.leg === legs - 1 ? `SAIL TO ${VT().final}` : "CHOOSE YOUR NEXT ISLAND · CLICK ONE";
      const choice = await new Promise((res) => (Y.choose = res));
      Y.waiting = false;
      await animateVoyage(M.voyageStep(V, st, rng, choice));
    }
    await wait(0.8);
    const total = st.total;
    S.balance += total;
    const games = st.spins ? ` · ${st.spins} free game${st.spins > 1 ? "s" : ""} to come` : "";
    const sub = st.sunk ? `sunk on the way${games}` : `${st.artefacts.filter(Boolean).length} of 4 artefacts${games}`;
    await summary(st.sunk ? VT().name : `${VT().chest}!`, sub, total);
    if (total >= 10 * b) await bigWin(total, b);
    S.mode = "reels"; S.voyage = null; clearWins(); S.winShown = S.winTarget = total;
    S.message = `${VT().name} PAID ${money(total)}`;
    if (st.spins) await freeGames(b, false, st.spins, VT().name);
  }
  // What the screen shows of the voyage: it follows the events, so a find shows when it's animated, not before.
  const voyageShown = (st) => ({ relics: st.relics, keys: st.keys, artefacts: st.artefacts.slice(), spins: st.spins, total: st.total,
                                 leg: st.leg, row: st.row, route: st.route.slice(), awaiting: st.awaiting });
  function chooseVoyage(choice) {
    const Y = S.voyage;
    if (!Y || !Y.waiting || !Y.choose) return;
    const f = Y.choose; Y.choose = null; f(choice);   // anything not open (or null) is chosen for you
  }
  function voyagePop(txt, colour, x, y, size = 36) { battlePop(txt, colour, x, y, size); }
  // An artefact (or a relic or key) flying from where it was found into the hold.
  function toHold(art, x, y, to) {
    const f = flyer({ img: art, x, y, size: 90, s: 0.3 });
    tween(f, { s: 1.2, y: y - 50 }, 0.35, ease.back).then(() => tween(f, { x: to.x, y: to.y, s: 0.45 }, 0.55, ease.inOut)).then(() => (f.dead = true));
  }
  const ART_SLOT = (i) => ({ x: 1078 + i * 48, y: REEL_Y + 160 });   // the hold's artefacts, a row of four
  async function animateVoyage(step) {
    const Y = S.voyage, sh = Y.shown;
    await wait(0.3);
    for (const e of step.events) {
      const here = islePos(sh.leg, sh.row, Y.legs);
      switch (e.kind) {
        case "arrive": {
          const to = islePos(e.leg, e.row, Y.legs);
          Y.ship.rot = Math.atan2(to.y - Y.ship.y, to.x - Y.ship.x) * 0.3;
          await tween(Y.ship, { x: to.x, y: to.y - 34 }, 1.1, ease.inOut);
          Y.ship.rot = 0; sh.leg = e.leg; sh.row = e.row; sh.route.push(e.row);
          await wait(0.3); break;
        }
        case "treasure": case "skull": case "cove":
          sh.total += e.pence; S.winTarget = sh.total; S.roller = Math.max(e.pence * 1.4, bet());
          voyagePop(money(e.pence), C.win, here.x, here.y - 40, e.kind === "treasure" ? 36 : 46);
          coinBurst(here.x, here.y, e.kind === "treasure" ? 14 : 26, 0.8);
          await wait(e.kind === "treasure" ? 1.0 : 1.2); break;
        case "relics":
          sh.relics += e.n; toHold("v_relic", here.x, here.y, { x: 1072, y: REEL_Y + 92 });
          voyagePop(`+${e.n} ${VT().relic}${e.n > 1 ? "S" : ""}`, C.goldHi, here.x, here.y - 30, 30);
          await wait(0.8); break;
        case "key":
          sh.keys += 1; toHold("v_key", here.x, here.y, { x: 1162, y: REEL_Y + 92 });
          voyagePop("+1 KEY", C.goldHi, here.x, here.y - 30, 30);
          await wait(0.8); break;
        case "artefact":
          toHold(`v_art${e.i + 1}`, here.x, here.y, ART_SLOT(e.i));
          voyagePop(VT().artefacts[e.i], C.goldHi, here.x, here.y - 70, 34);
          await wait(0.9); sh.artefacts[e.i] = true; await wait(0.3); break;
        case "unlock":
          sh.keys -= 1; voyagePop("UNLOCKED", C.goldHi, here.x, here.y - 30, 32);
          await wait(0.8); break;
        case "sunk":
          sh.sunk = true; voyagePop("SUNK!", "#ff5a48", here.x, here.y - 60, 52); S.shake = 1;
          await tween(Y.ship, { rot: 0.5, sink: 1, a: 0 }, 2.0, ease.inOut);
          await wait(0.2); break;
        case "port":
          sh.awaiting = e.deals.length ? "trade" : "sail";
          await wait(0.6); break;
        case "bought":
          sh.relics -= e.cost; sh.awaiting = "sail";
          if (e.deal === "spins") { sh.spins += V.voyage.spinsGames; voyagePop(`+${V.voyage.spinsGames} FREE GAME${V.voyage.spinsGames > 1 ? "S" : ""}`, "#7fd0ff", here.x, here.y - 30, 30); }
          await wait(0.6); break;
        case "sold":
          sh.relics = 0; sh.awaiting = "sail"; sh.total += e.pence; S.winTarget = sh.total; S.roller = Math.max(e.pence, bet());
          voyagePop(`SOLD ${money(e.pence)}`, C.win, here.x, here.y - 30, 34);
          await wait(0.9); break;
        case "leave":
          sh.awaiting = "sail"; await wait(0.3); break;
        case "final": {
          const to = islePos(Y.legs, 1, Y.legs);
          await tween(Y.ship, { x: to.x - 70, y: to.y - 20 }, 0.9, ease.inOut);
          Y.reveal = { t0: S.now, shown: -1, e };
          const parts = [e.chest, ...e.parts, e.legend, e.relics];
          for (let k = 0; k < 7; k++) {   // the chest, four parts, the legend, the relics: 0.5s each
            Y.reveal.shown = k;
            if (parts[k]) { sh.total += parts[k]; S.winTarget = sh.total; S.roller = Math.max(parts[k], bet()); }
            if (k === 5 && e.legend) { coinRain(60); S.shake = 0.6; }
            await wait(k === 5 && e.legend ? 0.9 : 0.5);
          }
          coinBurst(523, 330, 40, 1.2);
          await wait(0.6); break;
        }
      }
    }
  }
  function dashed(x0, y0, x1, y1, colour, width, dash) {
    ctx.save(); ctx.setLineDash(dash); ctx.lineWidth = width; ctx.strokeStyle = colour;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); ctx.restore();
  }
  function drawVoyage() {
    const Y = S.voyage, st = Y.st, sh = Y.shown, A = B_AREA, legs = Y.legs, size = Math.min(104, vStep(legs) * 0.84);
    const open = Y.waiting && st.awaiting === "sail" ? M.voyageOptions(V, st) : [];
    ctx.save();
    rr(A.x, A.y, A.w, A.h, 18); ctx.clip();
    const sea = ctx.createLinearGradient(0, A.y, 0, A.y + A.h);
    sea.addColorStop(0, "#0e4a66"); sea.addColorStop(1, "#08263c");
    ctx.fillStyle = sea; ctx.fillRect(A.x, A.y, A.w, A.h);
    if (bgImg && ok(bgImg)) { ctx.globalAlpha = 0.18; ctx.drawImage(bgImg, A.x, A.y, A.w, A.h); ctx.globalAlpha = 1; }
    ctx.strokeStyle = "rgba(255,255,255,0.05)"; ctx.lineWidth = 1;   // the chart's grid, and the swell
    for (let x = A.x + 40; x < A.x + A.w; x += 80) { ctx.beginPath(); ctx.moveTo(x, A.y); ctx.lineTo(x, A.y + A.h); ctx.stroke(); }
    for (let y = A.y + 40; y < A.y + A.h; y += 80) { ctx.beginPath(); ctx.moveTo(A.x, y); ctx.lineTo(A.x + A.w, y); ctx.stroke(); }
    ctx.strokeStyle = "rgba(190,230,255,0.10)"; ctx.lineWidth = 2;
    for (let k = 0; k < 14; k++) {
      const wx = A.x + ((k * 173 + S.now * 14) % A.w), wy = A.y + 30 + ((k * 97) % (A.h - 60));
      ctx.beginPath(); ctx.arc(wx, wy, 16, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
    }
    // the sea lanes: faint between neighbours, red where you've sailed, gold to where you can go now
    const at = (leg, row) => islePos(leg, row, legs);
    for (let leg = -1; leg < legs; leg++) {
      for (const r of leg < 0 ? [1] : [0, 1, 2]) {
        const a = at(leg, r);
        const nexts = leg === legs - 1 ? [1] : leg < 0 ? [0, 1, 2] : [r - 1, r, r + 1].filter((x) => x >= 0 && x <= 2);
        for (const n of nexts) { const b2 = at(leg + 1, n); dashed(a.x, a.y, b2.x, b2.y, "rgba(255,240,200,0.16)", 2, [4, 8]); }
      }
    }
    let px = at(-1, 1);
    sh.route.forEach((r, leg) => { const q = at(leg, r); dashed(px.x, px.y, q.x, q.y, "#d8432f", 4, [10, 7]); px = q; });
    if (Y.reveal) { const q = at(legs, 1); dashed(px.x, px.y, q.x, q.y, "#d8432f", 4, [10, 7]); }
    const pulse = 0.55 + 0.45 * Math.sin(S.now * 5);
    for (const o of open) {
      const q = o === "final" ? at(legs, 1) : at(sh.leg + 1, o);
      dashed(px.x, px.y, q.x, q.y, alpha(C.goldHi, pulse), 3, [10, 7]);
    }
    // the islands
    const isle = (art, x, y, s, a, label, id, lit) => {
      ctx.save(); ctx.globalAlpha = a;
      const bob = lit ? Math.sin(S.now * 2.4 + x) * 3 : 0;
      if (lit) {
        const g = ctx.createRadialGradient(x, y + bob, 4, x, y + bob, s * 0.7);
        g.addColorStop(0, alpha(C.goldHi, 0.45 * pulse)); g.addColorStop(1, alpha(C.goldHi, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y + bob, s * 0.7, 0, 7); ctx.fill();
      }
      drawImg(img(art), x - s / 2, y - s / 2 + bob, s, s);
      if (id && S.hover === id) { ctx.lineWidth = 3; ctx.strokeStyle = C.goldHi; ctx.beginPath(); ctx.arc(x, y + bob, s * 0.56, 0, 7); ctx.stroke(); }
      text(label, x, y + s / 2 + 8, 13, COND, lit ? C.goldHi : C.cream, "center", "700", 4, vStep(legs) - 8);
      ctx.restore();
      if (id) S.hits.push({ id, x: x - s / 2, y: y - s / 2, w: s, h: s });
    };
    const s0 = at(-1, 1);
    isle("v_port", s0.x, s0.y, size * 0.9, sh.leg < 0 ? 1 : 0.55, VT().start, null, false);
    st.map.forEach((col, leg) => col.forEach((kind, r) => {
      const q = at(leg, r), lit = sh.leg === leg - 1 && open.includes(r);
      const passed = leg <= sh.leg && !(leg === sh.leg && r === sh.row);
      const locked = kind === "cove" && !(sh.leg === leg && sh.row === r) && !(leg > sh.leg && sh.keys > 0);
      isle(ISLE_ART[kind], q.x, q.y, size, passed ? 0.35 : locked ? 0.6 : 1, isleName(kind), lit ? "isle" + r : null, lit);
      if (locked && !passed) {   // a padlock over a cove you've no key for
        ctx.save(); ctx.lineWidth = 4; ctx.strokeStyle = "#c8c8cc";
        ctx.beginPath(); ctx.arc(q.x + size * 0.3, q.y - size * 0.32, 8, Math.PI, 0); ctx.stroke();
        rr(q.x + size * 0.3 - 12, q.y - size * 0.32, 24, 18, 4); ctx.fillStyle = C.gold; ctx.fill(); ctx.restore();
      }
    }));
    const fq = at(legs, 1), finalLit = open.includes("final");
    isle("v_final", fq.x, fq.y, Math.min(150, size * 1.4), 1, VT().final, finalLit ? "final" : null, finalLit);
    // the ship
    const sp = Y.ship, bob = Math.sin(S.now * 2) * 3;
    ctx.save(); ctx.globalAlpha = sp.a; ctx.translate(sp.x, sp.y + bob + sp.sink * 40); ctx.rotate(sp.rot);
    drawImg(img("v_ship"), -46, -46, 92, 92); ctx.restore();
    // the final island's treasure, revealed part by part
    if (Y.reveal) drawReveal(Y.reveal);
    ctx.restore();
    // the top: the voyage's win
    text(`${VT().name} WIN ${money(sh.total)}`, 523, REEL_Y + 14, 32, COND, C.win, "center", "700", 6, 600);
    drawVoyagePanel(Y, st, sh);
  }
  function drawReveal(R) {
    const e = R.e, k = R.shown, cx = 523;
    ctx.fillStyle = alpha(C.shade, Math.min(0.8, (S.now - R.t0) * 2)); ctx.fillRect(B_AREA.x, B_AREA.y, B_AREA.w, B_AREA.h);
    text(VT().chest, cx, REEL_Y + 64, 40, DISPLAY, C.goldHi, "center", "400", 6, 700);
    const s = 200 + 12 * Math.sin(S.now * 2);
    drawImg(img("v_chest"), cx - s / 2, 300 - s / 2, s, s);
    if (k >= 0) text(money(e.chest), cx, 410, 30, COND, C.win, "center", "700", 5);
    for (let i = 0; i < 4; i++) {
      const x = cx + (i - 1.5) * 150, y = 490, held = e.parts[i] > 0, on = k >= i + 1;
      ctx.save(); ctx.globalAlpha = on ? (held ? 1 : 0.3) : 0.12;
      drawImg(img(`v_art${i + 1}`), x - 34, y - 46, 68, 68);
      text(VT().artefacts[i], x, y + 30, 15, COND, C.cream, "center", "700", 4, 140);
      ctx.restore();
      if (on) text(held ? `+${money(e.parts[i])}` : "MISSING", x, y + 52, held ? 20 : 15, COND, held ? C.win : C.muted, "center", "700", 4);
    }
    if (k >= 5 && e.legend) text(`${VT().legend} +${money(e.legend)}`, cx, 180, 44, COND, C.goldHi, "center", "700", 7, 800);
    if (k >= 6 && e.relics) text(`${VT().relic}S SOLD +${money(e.relics)}`, cx, 440, 18, COND, C.cream, "center", "700", 4);
  }
  const DEALS = [["artefact", "artefactPrice"], ["key", "keyPrice"], ["spins", "spinsPrice"], ["sell", null], ["leave", null]];
  function drawVoyagePanel(Y, st, sh) {
    const P = V.voyage, x0 = 1038, cx = 1150;
    woodPanel(x0, REEL_Y - 18, 224, REEL_H + 36, 16);
    text(VT().name, cx, REEL_Y + 10, 24, COND, C.goldHi, "center", "700", 0, 200);
    const stage = Y.reveal ? VT().final : sh.sunk ? "SUNK" : sh.awaiting === "trade" ? VT().port
      : sh.leg >= Y.legs - 1 ? `ON TO ${VT().final}` : `LEG ${sh.leg + 2} OF ${Y.legs}`;
    text(stage, cx, REEL_Y + 40, 20, COND, C.cream, "center", "700", 0, 200);
    // the hold: relics and keys, the four artefacts (faint until found), free games
    drawImg(img("v_relic"), 1052, REEL_Y + 72, 40, 40);
    text(`× ${sh.relics}`, 1096, REEL_Y + 92, 20, COND, C.cream, "left", "700", 0, 50);
    drawImg(img("v_key"), 1142, REEL_Y + 72, 40, 40);
    text(`× ${sh.keys}`, 1186, REEL_Y + 92, 20, COND, C.cream, "left", "700", 0, 50);
    text(`ARTEFACTS ${sh.artefacts.filter(Boolean).length} OF 4`, cx, REEL_Y + 128, 16, COND, C.goldHi, "center", "700", 0, 200);
    for (let i = 0; i < 4; i++) {
      const p = ART_SLOT(i);
      ctx.save(); ctx.globalAlpha = sh.artefacts[i] ? 1 : 0.2;
      drawImg(img(`v_art${i + 1}`), p.x - 22, p.y - 22, 44, 44);
      ctx.restore();
    }
    text(`FREE GAMES ${sh.spins}`, cx, REEL_Y + 200, 16, COND, "#7fd0ff", "center", "700", 0, 200);
    if (!Y.waiting) return;
    const left = Math.max(0, Y.autoAt - S.now);
    if (st.awaiting === "trade") {
      const opts = M.voyageOptions(V, st);
      DEALS.forEach(([d, price], i) => {
        const label = d === "artefact" ? `ARTEFACT · ${P[price]} ${VT().relic}S` : d === "key" ? `KEY · ${P[price]} ${VT().relic}S`
          : d === "spins" ? `${P.spinsGames > 1 ? P.spinsGames + " FREE GAMES" : "FREE GAME"} · ${P[price]} ${VT().relic}S` : d === "sell" ? `SELL · ${money(M.betPence(st.relics * P.relicValue, st.bet))}` : "SET SAIL";
        button("deal-" + d, 1054, REEL_Y + 220 + i * 44, 192, 38, label, { size: 16, disabled: !opts.includes(d), colour: d === "leave" ? spinBtn() : undefined });
      });
      text(`chooses itself in ${Math.ceil(left)}`, cx, REEL_Y + 448, 16, COND, C.muted);
    } else {
      if (st.leg === Y.legs - 1) button("final", 1060, REEL_Y + 300, 180, 52, `SAIL TO ${VT().final}`, { colour: spinBtn(), size: 18 });
      else text(VT().hint, cx, REEL_Y + 320, 16, COND, C.cream, "center", "700", 0, 200);
      text(`chooses itself in ${Math.ceil(left)}`, cx, REEL_Y + 370, 16, COND, C.muted);
    }
    if (left <= 0) chooseVoyage(null);
  }

  // ------------------------------------------------------------------ the frame loop
  let last = performance.now(), running = true;
  // One frame. A design can be half-made (missing pictures, odd settings), so a drawing error is reported and the
  // next frame still comes: the mockup never freezes.
  function frame(t) {
    if (!running) return;
    try { paint(t); } catch (e) { if (ctx.reset) ctx.reset(); else ctx.setTransform(1, 0, 0, 1, 0, 0); console.error("mockup frame:", e); }
    requestAnimationFrame(frame);
  }
  function paint(t) {
    const dt = Math.min(0.05, (t - last) / 1000) * pace();
    last = t;
    update(dt);
    S.hits = [];
    ctx.save();
    if (S.shake > 0) ctx.translate((rng() - 0.5) * 14 * S.shake, (rng() - 0.5) * 10 * S.shake);
    drawBackground();
    drawDecor("under");
    drawTop();
    if (S.mode === "trail" && S.trail) drawTrail();
    else if (S.mode === "battle" && S.battle) drawBattle();
    else if (S.mode === "voyage" && S.voyage) drawVoyage();
    else {
      drawSides();
      drawFrame();
      drawReels();
      drawWins();
      if (S.mode === "pick" && S.pick) drawPick();
    }
    if (S.free) {
      rr(440, REEL_Y - 16, 400, 34, 10); ctx.fillStyle = C.alert; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = C.gold; ctx.stroke();
      text(`${TEXT.freeName} ${S.free.n} OF ${S.free.of}`, 640, REEL_Y + 1, 22, COND, C.goldHi, "center", "700", 0, 380);
    }
    drawDeck();
    drawDecor("over");
    drawFlyers();
    drawBanner();
    drawParticles();
    ctx.restore();
    drawOverlay();
  }

  // ------------------------------------------------------------------ input
  function at(ev) {
    const r = cv.getBoundingClientRect();
    return { x: ((ev.clientX - r.left) / r.width) * W, y: ((ev.clientY - r.top) / r.height) * H };
  }
  function hitAt(p) {
    for (let i = S.hits.length - 1; i >= 0; i--) { const h = S.hits[i]; if (p.x >= h.x && p.x <= h.x + h.w && p.y >= h.y && p.y <= h.y + h.h) return h.id; }
    return null;
  }
  const onMove = (ev) => { S.hover = hitAt(at(ev)); }, onLeave = () => (S.hover = null), onClick = (ev) => act(hitAt(at(ev)));
  cv.addEventListener("mousemove", onMove);
  cv.addEventListener("mouseleave", onLeave);
  cv.addEventListener("click", onClick);
  function act(id) {
    if (S.overlay) {
      if (id === "overlay" || (S.overlay.kind === "bigwin" && id)) {
        const o = S.overlay;
        if (o.kind === "bigwin") { if (o.shown < 1e12) o.shown = o.shown; o.done && o.done(); }
        else if (o.done) { const d = o.done; o.done = null; d(); } else S.overlay = null;
      } else if (id === "buy-yes") {
        S.overlay = null; const b = bet();
        S.balance -= b * V.buyCost; S.busy = true; clearWins();
        playBonus(M.pickBonus(rng, routes("buy")), b, true).then(() => { S.busy = false; });
      } else if (id === "buy-no") S.overlay = null;
      return;
    }
    if (id && id.startsWith("coin")) return pickCoin(+id.slice(4));
    if (S.mode === "battle") { if (id && id.startsWith("ship")) return fireBattle(+id.slice(4)); if (id === "boss" || id === "fire") return fireBattle(null); }
    if (S.mode === "voyage") {
      if (id && id.startsWith("isle")) return chooseVoyage(+id.slice(4));
      if (id && id.startsWith("deal-")) return chooseVoyage(id.slice(5));
      if (id === "final") return chooseVoyage("final");
    }
    if (id !== "auto" && !(id && id.startsWith("auto"))) S.autoMenu = false;
    switch (id) {
      case "spin": return spinOrStop();
      case "fire": return fire();
      case "bet-": if (!S.busy) S.betIdx = Math.max(0, S.betIdx - 1); clearIdle(); return;
      case "bet+": if (!S.busy) S.betIdx = Math.min(M.LADDER.length - 1, S.betIdx + 1); clearIdle(); return;
      case "turbo": S.turbo = !S.turbo; return;
      case "auto": if (S.auto > 0) S.auto = 0; else S.autoMenu = !S.autoMenu; return;
      case "info": S.overlay = { kind: "info" }; return;
      case "buy": if (!S.busy && S.mode === "reels") S.overlay = { kind: "buy" }; return;
      case "cashout": S.overlay = { kind: "notice", text: "In the game, Cash Out stands you up from the cabinet." }; return;
    }
    if (id && id.startsWith("auto")) { S.autoMenu = false; S.auto = +id.slice(4); spin(); }
    else if (!id && S.mode === "reels" && !S.busy) spinOrStop();
  }
  function clearIdle() { if (!S.busy) { S.wins = []; S.message = `BET ${money(bet())} \u00b7 25 LINES`; } }
  function spinOrStop() {
    if (S.mode === "trail") return fire();
    if (S.mode === "battle") return fireBattle(null);
    if (S.mode === "voyage") return chooseVoyage(null);
    if (S.busy) { if (reels.some((x) => x.spinning || x.stopping)) S.hurry = true; return; }
    spin();
  }
  const onKey = (ev) => {
    if (ev.code !== "Space" || ev.target.closest("button,input,select,textarea") || !cv.isConnected) return;
    const r = cv.getBoundingClientRect();
    if (r.bottom < 0 || r.top > innerHeight) return;
    ev.preventDefault();
    if (S.overlay) return act("overlay");
    spinOrStop();
  };
  window.addEventListener("keydown", onKey);

  // ------------------------------------------------------------------ the wizard's controls
  document.fonts.ready.then(() => requestAnimationFrame(frame));
  return {
    setConfig(c) {
      const swap = c.variant && c.variant !== V;
      setConfig(c);
      if (swap && !S.busy && S.mode === "reels") {
        reels.forEach((x) => { x.strip = V.strips[x.r]; x.pos = Math.floor(rng() * x.strip.length); });
        S.grid = M.gridFromStops(V.strips, reels.map((x) => Math.floor(x.pos))); S.landed = true; clearWins();
      }
    },
    setSpeed(x) { S.speed = x; },
    topUp() { S.balance = Math.max(S.balance, 100000); },
    rig(r) { S.rig = r; },
    // Play a bonus straight away, as if it had triggered (the Bonus games step's Try it, for one only Buy gives).
    bonus(kind) {
      if (S.busy || S.overlay || S.mode !== "reels") return;
      S.busy = true; clearWins();
      playBonus(kind, bet(), false).then(() => { S.busy = false; });
    },
    spin: () => act("spin"),
    // Show a five-of-a-kind of `tier` on the middle line, as if it had just landed (the Sprites step's preview).
    demoWin(tier) {
      if (S.busy || S.mode !== "reels") return;
      const g = S.grid.slice();
      for (let r = 0; r < 5; r++) g[r * 4 + 1] = tier;
      clearWins(); S.grid = g; S.landed = true; S.colossal = null;
      S.wins = M.evaluate(g, V.pays).map((w) => ({ ...w, pence: Math.floor(w.mult * bet() / 25) }));
      S.cycle = 0; S.cycleAt = S.now + 3;
      S.message = `5 \u00d7 ${(V.symbols[tier] || tier).toUpperCase()}`;
    },
    state: S,
    bet,
    destroy() {
      running = false; clearInterval(feeder);
      cv.removeEventListener("mousemove", onMove); cv.removeEventListener("mouseleave", onLeave); cv.removeEventListener("click", onClick);
      window.removeEventListener("keydown", onKey);
    },
  };
}
