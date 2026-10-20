/* The Slot design wizard's mockup: the signed-off Armadillo mockup (docs/slots/mockup/game.js) made to play any
   design. The full-screen slot game: reels, feature choreography, wins, the deck, the shared meters, and the three
   bonus scenes (Trail, Combo Free Games, Jackpot Pick), drawn on one 1280x720 canvas laid out the way the Godot
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
    gold: "#f4c94f", goldHi: "#fff1b0", goldLo: "#9a6614", ink: "#2b1608", wood: "#6b3d1d", woodHi: "#a8703f",
    woodLo: "#3c200d", cream: "#f6ead0", red: "#d8362a", teal: "#35c1b4", panel: "rgba(24,12,6,0.78)",
    tiers: { mini: "#4fb3ff", minor: "#55d07a", major: "#c768ff", grand: "#ff5a48" },
  };
  let FRAME = { style: "wood", colour: "#d9a54a" }, TEXT = {}, LABELS = true;
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
    Object.assign(C, t.colours || {});
    FRAME = Object.assign({ style: "wood", colour: "#d9a54a" }, c.frame || {});
    TEXT = Object.assign({ tagline: "GOOD LUCK", title: [V.name.toUpperCase()], bonus: ["3+ BONUS", "TRAIL BONUS"],
                           free: ["3+ FREE SPINS", "3 COMBO FREE GAMES"], trailHint: "fire to move along the trail",
                           pistol: "THE PISTOL" }, c.texts || {});
    LABELS = c.labels !== false;
  }
  setConfig(cfg);

  // ------------------------------------------------------------------ state
  const S = {
    balance: 100000, betIdx: 3, busy: false, mode: "reels", turbo: false, speed: 1, auto: 0, autoMenu: false,
    grid: null, landed: false, wins: [], showLines: [], cycle: 0, cycleAt: 0, winShown: 0, winTarget: 0,
    message: "25 LINES \u00b7 " + TEXT.tagline, featureLit: {}, multiplier: 1, cellFx: {}, banner: null,
    overlay: null, particles: [], tweens: [], waits: [], hurry: false, hits: [], free: null, colossal: null,
    trail: null, pick: null, rig: { features: [], trigger: null, jackpot: null }, shake: 0, flyers: [],
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
    if (stroke) { ctx.lineWidth = stroke; ctx.strokeStyle = "rgba(30,12,4,0.95)"; ctx.lineJoin = "round"; ctx.strokeText(str, x, y); }
    ctx.fillStyle = colour; ctx.fillText(str, x, y);
  }
  function goldText(str, x, y, size, font = DISPLAY) {
    ctx.font = `400 ${size}px ${font}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const g = ctx.createLinearGradient(0, y - size / 2, 0, y + size / 2);
    g.addColorStop(0, "#fff6c2"); g.addColorStop(0.45, "#f4c94f"); g.addColorStop(1, "#a8651a");
    ctx.lineJoin = "round"; ctx.lineWidth = size * 0.16; ctx.strokeStyle = "#2b1004"; ctx.strokeText(str, x, y);
    ctx.fillStyle = g; ctx.fillText(str, x, y);
  }
  // Panels in the design's frame style (Scene step): wood (Armadillo's), metal, neon or glass, edged in its colour.
  function woodPanel(x, y, w, h, r = 14) {
    if (FRAME.style !== "wood") return stylePanel(x, y, w, h, r);
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, "#8a5530"); g.addColorStop(0.5, "#5c341a"); g.addColorStop(1, "#3a1f0d");
    rr(x, y, w, h, r); ctx.fillStyle = g; ctx.fill();
    ctx.save(); ctx.clip(); ctx.globalAlpha = 0.12; ctx.strokeStyle = "#1e0d04"; ctx.lineWidth = 1.2;
    for (let i = 0; i < h; i += 7) { ctx.beginPath(); ctx.moveTo(x, y + i + Math.sin(i) * 2); ctx.bezierCurveTo(x + w * 0.3, y + i + 4, x + w * 0.7, y + i - 3, x + w, y + i + 1); ctx.stroke(); }
    ctx.restore();
    rr(x + 3, y + 3, w - 6, h - 6, r - 3); ctx.lineWidth = 3; ctx.strokeStyle = "#d9a54a"; ctx.stroke();
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
    const base = opts.colour || (on ? ["#ffe08a", "#d99a28", "#8a5410"] : ["#6e4426", "#4a2a14", "#2c1609"]);
    g.addColorStop(0, base[0]); g.addColorStop(0.55, base[1]); g.addColorStop(1, base[2]);
    ctx.save(); if (disabled) ctx.globalAlpha = 0.4;
    rr(x, y, w, h, h * 0.28); ctx.fillStyle = g; ctx.fill();
    ctx.lineWidth = hover ? 3 : 2; ctx.strokeStyle = hover ? "#fff1b0" : "#d9a54a"; ctx.stroke();
    text(label, x + w / 2, y + h / 2 + 1, opts.size || 22, COND, on || opts.colour ? "#2b1004" : C.cream);
    ctx.restore();
    if (!disabled) S.hits.push({ id, x, y, w, h });
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
    if (ok(bgImg)) ctx.drawImage(bgImg, 0, 0, W, H); else ctx.drawImage(vecBg, 0, 0);
    const v = ctx.createRadialGradient(W / 2, H / 2, 200, W / 2, H / 2, 820);
    v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(10,4,2,0.6)");
    ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
  }
  function drawTop() {
    const pills = [["grand", 18, 250], ["major", 278, 210], ["minor", 792, 210], ["mini", 1012, 250]];
    for (const [id, x, w] of pills) {
      const t = M.JACKPOT_TIERS.find((q) => q.id === id), y = 14, h = 70, col = C.tiers[id];
      const g = ctx.createLinearGradient(0, y, 0, y + h);
      g.addColorStop(0, "rgba(255,255,255,0.18)"); g.addColorStop(0.5, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,0.3)");
      rr(x, y, w, h, 18); ctx.fillStyle = "#1a0d06"; ctx.fill();
      rr(x + 4, y + 4, w - 8, h - 8, 15); ctx.fillStyle = col; ctx.globalAlpha = 0.85; ctx.fill(); ctx.globalAlpha = 1;
      ctx.fillStyle = g; ctx.fill();
      rr(x, y, w, h, 18); ctx.lineWidth = 3; ctx.strokeStyle = "#f4c94f"; ctx.stroke();
      const lit = S.pick && S.pick.lit === id && Math.floor(S.now * 6) % 2;
      if (lit) { rr(x - 4, y - 4, w + 8, h + 8, 22); ctx.lineWidth = 5; ctx.strokeStyle = "#fff6c2"; ctx.stroke(); }
      text(t.name, x + w / 2, y + 18, 18, COND, "#fff", "center", "700", 4);
      text(moneyShort(Math.floor(S.metersShown[id])), x + w / 2, y + 46, 32, COND, "#fff", "center", "700", 6);
    }
    // The logo: lettering in both art sets (FLUX can't spell ARMADILLO).
    if (ok(logoImg)) { const k = Math.min(292 / logoImg.naturalWidth, 99 / logoImg.naturalHeight); const w = logoImg.naturalWidth * k, h = logoImg.naturalHeight * k; ctx.drawImage(logoImg, 640 - w / 2, 53.5 - h / 2, w, h); }
    else if (TEXT.title.length > 1) { goldText(TEXT.title[0], 640, 34, 44); goldText(TEXT.title[1], 640, 80, 34); }
    else goldText(TEXT.title[0], 640, 53, 40);
  }
  function drawFrame() {
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
    text("RANDOM FEATURES", 130, REEL_Y + 8, 19, COND, C.goldHi);
    const names = [["wilds", "RANDOM WILDS"], ["wildReels", "WILD REELS"], ["colossal", "COLOSSAL REELS"], ["multiplier", "MULTIPLIER"],
      ["upgrade", "SYMBOL UPGRADE"], ["repeat", "REPEAT WIN"], ["instant", "INSTANT WIN"]].filter(([id]) => V.features.includes(id));
    const step = Math.min(52, 364 / Math.max(1, names.length));
    names.forEach(([id, label], i) => {
      const y = REEL_Y + 32 + i * step, lit = S.featureLit[id];
      rr(34, y, 192, 42, 10);
      ctx.fillStyle = lit ? `rgba(255,${200 + Math.sin(S.now * 8) * 30},90,0.95)` : "rgba(20,9,4,0.65)"; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = lit ? "#fff6c2" : "#7a5a36"; ctx.stroke();
      text(id === "multiplier" && S.multiplier > 1 ? `MULTIPLIER \u00d7${S.multiplier}` : label, 130, y + 22, 20, COND, lit ? "#2b1004" : "#b89b74");
    });
    // Right: Buy Bonus and the two ways in.
    woodPanel(1038, REEL_Y - 18, 224, REEL_H + 36, 16);
    const busy = S.busy || S.mode !== "reels";
    const by = REEL_Y + 6;
    S.hits.push(...(busy ? [] : [{ id: "buy", x: 1052, y: by, w: 196, h: 178 }]));
    rr(1052, by, 196, 178, 14);
    const hov = S.hover === "buy" && !busy;
    ctx.fillStyle = hov ? "rgba(90,40,10,0.95)" : "rgba(40,18,6,0.85)"; ctx.fill();
    ctx.lineWidth = hov ? 4 : 3; ctx.strokeStyle = "#f4c94f"; ctx.stroke();
    ctx.save(); if (busy) ctx.globalAlpha = 0.45;
    text("BUY BONUS", 1150, by + 24, 26, COND, C.goldHi);
    drawImg(img("BS"), 1150 - 52, by + 38, 104, 104);
    text(money(bet() * V.buyCost), 1150, by + 156, 26, COND, "#fff");
    ctx.restore();
    const info = [["BS", ...TEXT.bonus], ["FS", ...TEXT.free]];
    info.forEach(([sym, a, b], i) => {
      const y = by + 196 + i * 116;
      rr(1052, y, 196, 104, 12); ctx.fillStyle = "rgba(20,9,4,0.65)"; ctx.fill();
      // the symbol on the left, its two lines centred in the space to its right
      drawImg(img(sym), 1058, y + 14, 76, 76);
      const tx = 1138, tw = 1248 - 8 - tx, mid = tx + tw / 2;
      text(a, mid, y + 40, 22, COND, C.goldHi, "center", "700", 0, tw); text(b, mid, y + 66, 16, COND, C.cream, "center", "700", 0, tw);
    });
  }
  function drawDeck() {
    const y = 618;
    ctx.fillStyle = "rgba(12,5,2,0.86)"; ctx.fillRect(0, y - 26, W, H - y + 26);
    ctx.fillStyle = "#d9a54a"; ctx.fillRect(0, y - 26, W, 2);
    // the message bar
    text(S.message, 640, y - 12, 19, COND, C.goldHi);
    const box = (x, w, label, value, col = "#fff") => {
      rr(x, y + 10, w, 82, 12); ctx.fillStyle = "#1a0c05"; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = "#7a5a36"; ctx.stroke();
      text(label, x + w / 2, y + 28, 16, COND, "#b89b74"); text(value, x + w / 2, y + 64, 36, COND, col);
    };
    const credit = S.balance - (S.pendingCredit || 0);
    box(20, 210, "CREDIT", money(credit));
    box(242, 230, "BET", money(bet()));
    const canBet = !S.busy && S.mode === "reels";
    button("bet-", 252, y + 46, 40, 38, "\u2212", { disabled: !canBet || S.betIdx === 0, size: 30 });
    button("bet+", 422, y + 46, 40, 38, "+", { disabled: !canBet || S.betIdx === M.LADDER.length - 1, size: 30 });
    box(484, 230, S.free ? "FREE GAMES WIN" : "WIN", S.winShown > 0 ? money(Math.floor(S.winShown)) : "", "#ffe27a");
    const deckBusy = S.mode !== "reels" || S.overlay;
    button("info", 730, y + 22, 92, 56, "INFO", { disabled: deckBusy || S.busy });
    button("turbo", 832, y + 22, 92, 56, "TURBO", { on: S.turbo });
    button("auto", 934, y + 22, 92, 56, S.auto > 0 ? `STOP ${S.auto}` : "AUTO", { on: S.auto > 0 || S.autoMenu, disabled: S.mode !== "reels" && S.auto === 0 });
    // SPIN
    // Inside the 720px screen with room to spare: centre 664, ring 50 (614..714).
    const cx = 1112, cy = 664, r = 46, spinning = reels.some((x) => x.spinning);
    const hov = S.hover === "spin";
    const g = ctx.createRadialGradient(cx - 14, cy - 18, 6, cx, cy, r);
    g.addColorStop(0, "#fff1b0"); g.addColorStop(0.5, spinning ? "#c9871c" : "#f0b43a"); g.addColorStop(1, "#7a420c");
    ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, 7); ctx.fillStyle = "#1a0b03"; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.fillStyle = g; ctx.fill();
    ctx.lineWidth = hov ? 5 : 3; ctx.strokeStyle = "#fff6c2"; ctx.stroke();
    text(spinning ? "STOP" : S.mode === "trail" ? "FIRE" : "SPIN", cx, cy + 2, 28, COND, "#2b1004");
    S.hits.push({ id: "spin", x: cx - r, y: cy - r, w: r * 2, h: r * 2 });
    button("cashout", 1172, y + 22, 96, 56, "CASH OUT", { size: 18, disabled: S.busy || S.mode !== "reels" });
    if (S.autoMenu) {
      [10, 25, 50, 100].forEach((n, i) => button("auto" + n, 934 + i * 0 - 4, y - 70 - i * 46, 100, 40, `${n} SPINS`, { colour: ["#fff1b0", "#f0b43a", "#9a5a10"] }));
    }
  }

  // ------------------------------------------------------------------ the reels
  const cellRect = (c) => ({ x: REEL_X + Math.floor(c / 4) * CELL_W, y: REEL_Y + (c % 4) * CELL_H });
  function drawSymbol(sym, x, y, w, h, fx) {
    const im = img(sym);
    if (!ok(im)) return;
    let s = 0.92 * (fx && fx.scale || 1);
    const flip = fx && fx.flip != null ? Math.abs(Math.cos(fx.flip * Math.PI)) : 1;
    const size = Math.min(w, h) * s;
    ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.scale(flip, 1);
    if (fx && fx.glow) { ctx.shadowColor = fx.glowColour || "#ffe27a"; ctx.shadowBlur = 26 * fx.glow; }
    ctx.drawImage(im, -size / 2, -size / 2, size, size);
    ctx.restore();
    if (LABELS && (sym === "W" || sym === "BS" || sym === "FS")) {
      const label = sym === "W" ? "WILD" : sym === "BS" ? "BONUS" : "FREE SPINS";
      const size2 = sym === "FS" ? 17 : 21;
      ctx.save(); ctx.translate(x + w / 2, y + h - 18); ctx.scale(flip, 1);
      rr(-w * 0.36, -12, w * 0.72, 24, 6); ctx.fillStyle = sym === "W" ? "#7d130c" : "#2b1004"; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = "#f4c94f"; ctx.stroke();
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
      ctx.lineWidth = 8; ctx.strokeStyle = "#ffe27a"; ctx.strokeRect(REEL_X + x.r * CELL_W + 4, REEL_Y + 4, CELL_W - 8, REEL_H - 8); ctx.restore();
    }
    ctx.restore();
    // reel dividers
    ctx.fillStyle = "rgba(217,165,74,0.55)";
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
    ctx.fillStyle = "rgba(60,28,10,0.6)"; ctx.fillRect(REEL_X + col.start * CELL_W, REEL_Y, wPx, REEL_H);
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
      ctx.fillStyle = "rgba(60,28,10,0.6)"; ctx.fillRect(REEL_X + col.start * CELL_W, REEL_Y, wPx, REEL_H);
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
    for (let c = 0; c < 20; c++) {
      const r = Math.floor(c / 4);
      if (col && r >= col.start && r < col.start + col.k) {
        const b = Math.floor(((c % 4) + col.offset) / col.k);
        const block = [];
        for (let rr2 = 0; rr2 < 4; rr2++) if (Math.floor((rr2 + col.offset) / col.k) === b) for (let q = col.start; q < col.start + col.k; q++) block.push(q * 4 + rr2);
        if (block.every((q) => S.grid[q] === S.grid[block[0]])) continue;
      }
      const { x, y } = cellRect(c);
      drawSymbol(S.grid[c], x, y, CELL_W, CELL_H, S.cellFx[c]);
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
      ctx.lineWidth = 9; ctx.strokeStyle = "rgba(20,8,2,0.7)";
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
        rr(x + CELL_W - 92, y + 6, 86, 30, 8); ctx.fillStyle = "rgba(20,8,2,0.85)"; ctx.fill();
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
    rr(-420, -66, 840, b.sub ? 132 : 100, 22); ctx.fillStyle = "rgba(24,10,3,0.88)"; ctx.fill();
    ctx.lineWidth = 4; ctx.strokeStyle = "#f4c94f"; ctx.stroke();
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
      g.addColorStop(0, "#fff6c2"); g.addColorStop(0.5, sx > 0 ? "#f4c94f" : "#d9a030"); g.addColorStop(1, "#8a5410");
      ctx.beginPath(); ctx.arc(0, 0, p.r, 0, 7); ctx.fillStyle = g; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = "#5a3505"; ctx.stroke();
      ctx.restore();
    }
  }
  function drawFlyers() {
    for (const f of S.flyers) {
      if (f.a <= 0) continue;
      ctx.save(); ctx.globalAlpha = f.a; ctx.translate(f.x, f.y); ctx.rotate(f.rot || 0); ctx.scale(f.s, f.s);
      if (f.img) drawImg(img(f.img), -f.size / 2, -f.size / 2, f.size, f.size);
      if (f.text) text(f.text, 0, 0, f.textSize || 40, f.font || COND, f.colour || C.goldHi, "center", "700", 6);
      if (f.flash) { ctx.globalCompositeOperation = "lighter"; const g = ctx.createRadialGradient(0, 0, 2, 0, 0, 60); g.addColorStop(0, "rgba(255,240,180,1)"); g.addColorStop(1, "rgba(255,160,40,0)"); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, 60, 0, 7); ctx.fill(); }
      ctx.restore();
    }
    S.flyers = S.flyers.filter((f) => !f.dead);
  }
  function flyer(props) { const f = Object.assign({ x: 640, y: 360, s: 1, a: 1, size: 120 }, props); S.flyers.push(f); return f; }

  function drawOverlay() {
    const o = S.overlay;
    if (!o) return;
    ctx.fillStyle = "rgba(8,3,1,0.72)"; ctx.fillRect(0, 0, W, H);
    S.hits = o.keepDeck ? S.hits : [];
    if (o.kind === "bigwin") {
      const t = Math.min(1, (S.now - o.t0) * 2.2);
      ctx.save(); ctx.translate(640, 300); const s = 0.5 + 0.5 * ease.back(t); ctx.scale(s, s);
      const pulse = 1 + 0.03 * Math.sin(S.now * 6);
      ctx.scale(pulse, pulse);
      goldText(o.title, 0, -40, 120);
      text(money(Math.floor(o.shown)), 0, 70, 84, COND, "#fff", "center", "700", 10);
      ctx.restore();
      text("Click to continue", 640, 520, 20, COND, "#b89b74");
      S.hits.push({ id: "overlay", x: 0, y: 0, w: W, h: H });
    } else if (o.kind === "summary") {
      woodPanel(340, 170, 600, 330, 22);
      goldText(o.title, 640, 240, 54);
      text(o.sub || "", 640, 300, 24, COND, C.cream);
      text(money(o.amount), 640, 372, 76, COND, "#ffe27a", "center", "700", 8);
      button("overlay", 560, 430, 160, 50, "COLLECT", { colour: ["#fff1b0", "#f0b43a", "#9a5a10"] });
      const left = 5 - (S.now - o.t0);
      text(`collects itself in ${Math.max(1, Math.ceil(left))}`, 640, 486 + 10, 16, COND, "#b89b74");
      if (left <= 0 && o.done) { const d = o.done; o.done = null; d(); }
    } else if (o.kind === "buy") {
      woodPanel(360, 170, 560, 340, 22);
      goldText("BUY BONUS", 640, 228, 50);
      drawImg(img("BS"), 640 - 60, 256, 120, 120);
      text(`Go straight to the ${TEXT.bonus[1].toLowerCase()} for ${money(bet() * V.buyCost)}`, 640, 400, 26, COND, C.cream);
      text(`${V.buyCost} \u00d7 your ${money(bet())} bet. Bonus wins pay at ${money(bet())}.`, 640, 430, 19, COND, "#b89b74");
      button("buy-yes", 470, 450, 160, 48, "BUY", { colour: ["#fff1b0", "#f0b43a", "#9a5a10"], disabled: S.balance < bet() * V.buyCost });
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
        text(`${k}`, x0 + sz + 32, y + 30 + j * 26, 20, COND, "#ffb347", "left");
        text(money(Math.floor(V.pays[sym][k - 3] * lb)), x0 + sz + 56, y + 30 + j * 26, 22, COND, C.cream, "left");
      });
    }));
    const nm = (t) => V.symbols[t] || t;
    const ups = {};
    for (const [f, t] of Object.entries(V.upgrades)) (ups[t] = ups[t] || []).push(nm(f));
    const tips = (cfg.rules || [
      `Wild stands in for everything except ${nm("BS")} and ${nm("FS")}. Pays left to right on 25 lines; the longest match on each line pays.`,
      "Random features can hit any spin, some before the reels stop and some after.",
      `3+ ${nm("BS")}: ${TEXT.bonus[1]}. 3+ ${nm("FS")}: ${TEXT.free[1]}.`,
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

  // ------------------------------------------------------------------ Combo Free Games
  async function freeGames(b) {
    S.free = { n: 0, of: V.freeGames, total: 0 };
    await banner("COMBO FREE GAMES", `${V.freeGames} games \u00b7 a random feature every spin`, 2.2);
    for (let i = 1; i <= V.freeGames; i++) {
      S.free.n = i; S.message = `FREE GAME ${i} OF ${V.freeGames}`;
      clearWins(); S.winShown = S.winTarget = S.free.total;
      const o = M.spinOutcome(V, b, rng, { free: true });
      await playSpin(o);
      S.free.total += o.total;
      await wait(0.9);
    }
    const total = S.free.total;
    S.balance += total;
    await summary("FREE GAMES", `${V.freeGames} combo free games at ${money(b)}`, total);
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
    ctx.fillStyle = "rgba(10,4,2,0.82)"; ctx.fillRect(REEL_X - 22, REEL_Y - 18, REEL_W + 44, REEL_H + 36);
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
      if (face) { g.addColorStop(0, "#ffffff"); g.addColorStop(0.35, face); g.addColorStop(1, "#1a0b03"); }
      else { g.addColorStop(0, "#fff6c2"); g.addColorStop(0.5, hover ? "#ffd970" : "#f4c94f"); g.addColorStop(1, "#8a5410"); }
      ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.fillStyle = g; ctx.fill();
      ctx.lineWidth = 4; ctx.strokeStyle = P.done && c.tier === P.lit && !c.dim ? "#fff" : "#5a3505"; ctx.stroke();
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
        pop(money(e.pence), "#ffe27a"); coinBurst(sx, sy - 30, e.kind === "prizepot" ? 80 : 12, 0.6);
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
    // camera follows the armadillo
    const want = T.token.x - 380;
    T.cam += (want - T.cam) * 0.08;
    const x0 = REEL_X - 22, y0 = REEL_Y - 18, w0 = REEL_W + 44 + 1262 - (REEL_X + REEL_W + 22) - 2 + 240, h0 = REEL_H + 36;
    ctx.save();
    rr(18, y0, 1010, h0, 18); ctx.clip();
    ctx.fillStyle = "rgba(40,16,6,0.35)"; ctx.fillRect(18, y0, 1010, h0);
    // the dusty road
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    for (const [w, c] of [[64, "rgba(60,28,10,0.55)"], [50, "#c89a62"], [44, "#d8ae74"]]) {
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
      ctx.fillStyle = sp.type === "snake" ? "#5e1d12" : end ? "#5a3a08" : "#4a2a14"; ctx.fill();
      ctx.lineWidth = crate || light ? 4 : 2; ctx.strokeStyle = crate ? "#ffb347" : light ? "#ffe14a" : "#d9a54a"; ctx.stroke();
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
    rr(40, REEL_Y - 8, 900, 18, 9); ctx.fillStyle = "rgba(20,8,2,0.8)"; ctx.fill();
    rr(40, REEL_Y - 8, 900 * prog, 18, 9); ctx.fillStyle = "#d8ae74"; ctx.fill();
    drawImg(img("t_gold"), 930, REEL_Y - 28, 50, 50);
    drawImg(img("armadillo"), 40 + 900 * prog - 20, REEL_Y - 34, 44, 44);
    text(`TRAIL WIN ${money(T.total)}`, 640, REEL_Y + 34, 34, COND, "#ffe27a", "center", "700", 6);
    for (let h = 0; h < T.hearts; h++) drawImg(img("t_heart"), 40 + h * 46, REEL_Y + 18, 44, 44);
    let cx = 40 + Math.max(1, T.hearts) * 46 + 10;
    if (st.upgraded) { rr(cx, REEL_Y + 24, 150, 32, 8); ctx.fillStyle = "#1d6b62"; ctx.fill(); text("MOVES \u00d72", cx + 75, REEL_Y + 41, 20, COND, "#fff"); cx += 160; }
    if (st.doubled) { rr(cx, REEL_Y + 24, 150, 32, 8); ctx.fillStyle = "#8a2a12"; ctx.fill(); text("COINS DOUBLED", cx + 75, REEL_Y + 41, 20, COND, "#fff"); }
    woodPanel(1038, REEL_Y - 18, 224, REEL_H + 36, 16);
    text(TEXT.pistol, 1150, REEL_Y + 10, 22, COND, C.goldHi);
    text(st.upgraded ? "moves 2 spaces per bullet" : "1 to 6 bullets a shot", 1150, REEL_Y + 34, 16, COND, C.cream);
    const cyx = 1150, cyy = REEL_Y + 150;
    ctx.save(); ctx.translate(cyx, cyy); ctx.rotate(T.cyl); drawImg(img("cylinder"), -78, -78, 156, 156);
    for (let k = 0; k < T.bullets; k++) {
      const a = -Math.PI / 2 + (k * Math.PI) / 3;
      ctx.beginPath(); ctx.arc(Math.cos(a) * 35, Math.sin(a) * 35, 13, 0, 7);
      const g = ctx.createRadialGradient(Math.cos(a) * 35 - 4, Math.sin(a) * 35 - 4, 2, Math.cos(a) * 35, Math.sin(a) * 35, 13);
      g.addColorStop(0, "#fff1b0"); g.addColorStop(1, "#b07a1c"); ctx.fillStyle = g; ctx.fill();
    }
    ctx.restore();
    if (T.waiting) {
      const left = Math.max(0, T.autoAt - S.now);
      button("fire", cyx - 80, cyy + 100, 160, 58, "FIRE", { colour: ["#ffb4a6", "#e2402f", "#7d130c"], size: 32 });
      text(`fires itself in ${Math.ceil(left)}`, cyx, cyy + 176, 16, COND, "#b89b74");
      if (left <= 0) fire();
    }
  }
  function fire() { if (S.trail && S.trail.waiting && S.trail.fire) { const f = S.trail.fire; S.trail.fire = null; f(); } }

  // ------------------------------------------------------------------ the frame loop
  let last = performance.now(), running = true;
  function frame(t) {
    if (!running) return;
    const dt = Math.min(0.05, (t - last) / 1000) * pace();
    last = t;
    update(dt);
    S.hits = [];
    ctx.save();
    if (S.shake > 0) ctx.translate((rng() - 0.5) * 14 * S.shake, (rng() - 0.5) * 10 * S.shake);
    drawBackground();
    drawTop();
    if (S.mode === "trail" && S.trail) drawTrail();
    else {
      drawSides();
      drawFrame();
      drawReels();
      drawWins();
      if (S.mode === "pick" && S.pick) drawPick();
    }
    if (S.free) {
      rr(440, REEL_Y - 16, 400, 34, 10); ctx.fillStyle = "#7d130c"; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = "#f4c94f"; ctx.stroke();
      text(`COMBO FREE GAME ${S.free.n} OF ${S.free.of}`, 640, REEL_Y + 1, 22, COND, C.goldHi);
    }
    drawDeck();
    drawFlyers();
    drawBanner();
    drawParticles();
    ctx.restore();
    drawOverlay();
    requestAnimationFrame(frame);
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
        trailBonus(b, true).then(() => { S.busy = false; });
      } else if (id === "buy-no") S.overlay = null;
      return;
    }
    if (id && id.startsWith("coin")) return pickCoin(+id.slice(4));
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
    spin: () => act("spin"),
    state: S,
    bet,
    destroy() {
      running = false; clearInterval(feeder);
      cv.removeEventListener("mousemove", onMove); cv.removeEventListener("mouseleave", onLeave); cv.removeEventListener("click", onClick);
      window.removeEventListener("keydown", onKey);
    },
  };
}
