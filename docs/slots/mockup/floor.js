/* The slot bank on the casino floor at in-game scale (world units x ZOOM): the cabinet drawn in
   code in four orientations, players seated on stools, and each cabinet's little screen playing
   real spins. This is the drawing the Godot SlotCabinet will port. */
(function () {
  "use strict";
  const M = SlotMath, V = M.ARMADILLO;
  const cv = document.getElementById("floor"), ctx = cv.getContext("2d");
  const ZOOM = 3, WW = cv.width / ZOOM, WH = cv.height / ZOOM;
  const rng = M.mulberry32(77);
  const load = (src) => { const i = new Image(); i.src = src; return i; };
  const carpet = load("art/floor/carpet.png");
  const looks = ["npc_1", "npc_2", "npc_3", "npc_4", "npc_5", "npc_6", "player_default"].map((n) => load(`art/floor/${n}.png`));
  const icons = {};
  for (const s of ["W", "H1", "H2", "M1", "M2", "M3", "M4", "L1", "L2", "L3", "L4", "BS", "FS"]) icons[s] = load(`art/svg/${s}.svg`);
  const ok = (im) => im.complete && im.naturalWidth > 0;
  const SIT_ROW = { up: 8, left: 9, down: 10, right: 11 };
  const TRIM = "#ffb347", TRIM_HI = "#ffe0a3";

  // The bank: two back-to-back rows of four, and an end cap each side. x,y = the cabinet's base centre.
  const CX = WW / 2, CY = 108;
  const cabinets = [];
  for (let i = 0; i < 4; i++) cabinets.push({ x: CX - 51 + i * 34, y: CY - 13, facing: "up" });
  for (let i = 0; i < 4; i++) cabinets.push({ x: CX - 51 + i * 34, y: CY + 13, facing: "down" });
  cabinets.push({ x: CX - 92, y: CY + 2, facing: "left" });
  cabinets.push({ x: CX + 92, y: CY + 2, facing: "right" });
  const FACE_OFFSET = { down: [0, 17], up: [0, -15], left: [-19, 4], right: [19, 4] };
  const AVATAR_DIR = { down: "up", up: "down", left: "right", right: "left" };
  for (const c of cabinets) {
    const [dx, dy] = FACE_OFFSET[c.facing];
    c.stool = { x: c.x + dx, y: c.y + dy };
    c.grid = M.gridFromStops(V.strips, V.strips.map((s) => Math.floor(rng() * s.length)));
    c.player = rng() < 0.7 ? looks[Math.floor(rng() * looks.length)] : null;
    c.next = 1 + rng() * 5; c.spinUntil = 0; c.flash = 0; c.bonus = 0;
  }

  function spinCabinet(c, now) {
    const o = M.spinOutcome(V, 100, rng);
    c.spinUntil = now + 1.4; c.pending = o;
    c.next = now + 1.4 + 2 + rng() * 4;
  }

  // ------------------------------------------------------------------ the cabinet
  function box(x, y, w, h, top, mid, low) {
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, top); g.addColorStop(0.5, mid); g.addColorStop(1, low);
    ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
  }
  function rrect(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
  function miniScreen(c, x, y, w, h, now) {
    ctx.fillStyle = "#0b0604"; ctx.fillRect(x, y, w, h);
    const cw = w / 5, ch = h / 4;
    const spinning = now < c.spinUntil;
    for (let r = 0; r < 5; r++) {
      const stopAt = c.spinUntil - 1.0 + r * 0.2;
      for (let row = 0; row < 4; row++) {
        const cx = x + r * cw, cy = y + row * ch;
        if (spinning && now < stopAt) {
          ctx.fillStyle = `hsl(${(r * 60 + row * 40 + now * 900) % 360},55%,${40 + 10 * Math.sin(now * 40 + row)}%)`;
          ctx.globalAlpha = 0.5; ctx.fillRect(cx + 0.3, cy, cw - 0.6, ch); ctx.globalAlpha = 1;
        } else {
          const im = icons[c.grid[r * 4 + row]];
          if (ok(im)) ctx.drawImage(im, cx + 0.2, cy + 0.1, cw - 0.4, ch - 0.2);
        }
      }
    }
    if (c.bonus > now) { ctx.fillStyle = `rgba(255,200,80,${0.35 + 0.25 * Math.sin(now * 10)})`; ctx.fillRect(x, y, w, h); }
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, "rgba(255,255,255,0.18)"); g.addColorStop(0.3, "rgba(255,255,255,0)");
    ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
  }
  function candle(x, y, now, c) {
    const lit = c.flash > now;
    ctx.fillStyle = "#2a1408"; ctx.fillRect(x - 2.2, y - 1.5, 4.4, 1.5);
    ctx.fillStyle = lit ? (Math.floor(now * 8) % 2 ? "#fff1b0" : "#ff5a48") : "#c97a2a";
    rrect(x - 1.8, y - 6, 3.6, 4.5, 1.2); ctx.fill();
    if (lit) { ctx.globalAlpha = 0.5; ctx.fillStyle = "#ffe27a"; ctx.beginPath(); ctx.arc(x, y - 4, 5, 0, 7); ctx.fill(); ctx.globalAlpha = 1; }
  }
  function lid(x, b, w) {
    const g = ctx.createLinearGradient(0, b - 63, 0, b - 54);
    g.addColorStop(0, "#6b4223"); g.addColorStop(1, "#4a2c18");
    ctx.fillStyle = g; ctx.fillRect(x, b - 63, w, 9);
    ctx.fillStyle = "rgba(255,200,140,0.18)"; ctx.fillRect(x, b - 63, w, 1.2);
    ctx.fillStyle = "#1a0d05"; ctx.fillRect(x, b - 54.6, w, 0.8);
  }
  function cabinetFront(c, now) {   // screen facing the camera (facing down)
    const x = c.x - 15, b = c.y, lit = c.flash > now;
    ctx.fillStyle = "rgba(0,0,0,0.35)"; ctx.beginPath(); ctx.ellipse(c.x, b, 17, 4.5, 0, 0, 7); ctx.fill();
    box(x + 1, b - 8, 28, 8, "#3a2416", "#24140b", "#140a05");                     // plinth
    box(x, b - 22, 30, 14, "#4a2c18", "#2e1a0d", "#1c0f07");                         // lower cabinet
    ctx.fillStyle = "#7a4a26"; ctx.fillRect(x + 9, b - 18, 12, 7);                  // belly door
    ctx.strokeStyle = "#d9a54a"; ctx.lineWidth = 0.5; ctx.strokeRect(x + 9, b - 18, 12, 7);
    box(x - 1, b - 26, 32, 5, "#9a6a3e", "#6b4223", "#3c200d");                      // button deck
    for (let i = 0; i < 5; i++) { ctx.fillStyle = i === 4 ? "#ffb347" : ["#4fb3ff", "#55d07a", "#c768ff", "#ff5a48"][i]; ctx.fillRect(x + 3 + i * 5.2, b - 25, 3.4, 1.6); }
    box(x, b - 44, 30, 18, "#2a1a10", "#1b0f08", "#120904");                         // screen bezel
    miniScreen(c, x + 2, b - 42.5, 26, 15, now);
    box(x + 1, b - 54, 28, 10, "#3a2416", "#2a170b", "#1a0d05");                     // topper
    ctx.fillStyle = lit && Math.floor(now * 8) % 2 ? "#fff1b0" : "#e8a33a";
    ctx.font = "700 3.6px 'Barlow Condensed', sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("ARMADILLO", c.x, b - 50.6); ctx.fillText("GOES WEST", c.x, b - 47);
    // LED trim
    ctx.fillStyle = lit ? TRIM_HI : TRIM;
    ctx.fillRect(x - 0.8, b - 54, 1.2, 46); ctx.fillRect(x + 29.6, b - 54, 1.2, 46);
    lid(x - 0.8, b, 31.6);
    ctx.fillStyle = lit ? TRIM_HI : TRIM; ctx.fillRect(x - 0.8, b - 55.2, 31.6, 1);
    candle(c.x, b - 59, now, c);
  }
  function cabinetBack(c, now) {    // screen facing away (facing up): we see the back
    const x = c.x - 15, b = c.y, lit = c.flash > now;
    ctx.fillStyle = "rgba(0,0,0,0.35)"; ctx.beginPath(); ctx.ellipse(c.x, b, 17, 4.5, 0, 0, 7); ctx.fill();
    box(x + 1, b - 8, 28, 8, "#2a1a10", "#1c1008", "#100804");
    box(x, b - 54, 30, 46, "#3a2416", "#22130a", "#140a05");
    ctx.fillStyle = "#0e0704";
    for (let i = 0; i < 6; i++) ctx.fillRect(x + 6, b - 46 + i * 3.2, 18, 1.2);       // vents
    ctx.fillStyle = "#2c1a0e"; ctx.fillRect(x + 4, b - 24, 22, 12);
    ctx.strokeStyle = "#5a3d27"; ctx.lineWidth = 0.6; ctx.strokeRect(x + 4, b - 24, 22, 12);
    ctx.fillStyle = lit ? TRIM_HI : TRIM;
    ctx.fillRect(x - 0.8, b - 54, 1.2, 46); ctx.fillRect(x + 29.6, b - 54, 1.2, 46);
    lid(x - 0.8, b, 31.6);
    // the glow of the screen spilling over the far edge of the lid
    ctx.fillStyle = `rgba(255,200,120,${0.35 + (lit ? 0.3 : 0)})`; ctx.fillRect(x, b - 64, 30, 1.6);
    candle(c.x, b - 59, now, c);
  }
  function cabinetSide(c, now, dir) {   // profile: the screen faces `dir` (left or right)
    const s = dir === "left" ? -1 : 1, b = c.y, lit = c.flash > now;
    ctx.save(); ctx.translate(c.x, 0); ctx.scale(s, 1);
    ctx.fillStyle = "rgba(0,0,0,0.35)"; ctx.beginPath(); ctx.ellipse(0, b, 13, 5, 0, 0, 7); ctx.fill();
    // body silhouette: back edge on the left, front (screen side) on the right
    ctx.beginPath();
    ctx.moveTo(-11, b); ctx.lineTo(-11, b - 54); ctx.lineTo(4, b - 54); ctx.lineTo(6, b - 44);
    ctx.lineTo(10, b - 27); ctx.lineTo(13, b - 24); ctx.lineTo(9, b - 21); ctx.lineTo(9, b); ctx.closePath();
    const g = ctx.createLinearGradient(-11, 0, 13, 0);
    g.addColorStop(0, "#1c0f07"); g.addColorStop(0.6, "#3a2416"); g.addColorStop(1, "#4a2c18");
    ctx.fillStyle = g; ctx.fill();
    // the screen's edge and glow
    ctx.strokeStyle = lit ? "#fff1b0" : "#ffcf8a"; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.moveTo(6, b - 44); ctx.lineTo(10, b - 27); ctx.stroke();
    ctx.fillStyle = "#9a6a3e"; ctx.beginPath(); ctx.moveTo(10, b - 27); ctx.lineTo(13, b - 24); ctx.lineTo(9, b - 21); ctx.lineTo(8, b - 25); ctx.fill();
    // trim along the front and top
    ctx.fillStyle = lit ? TRIM_HI : TRIM;
    ctx.fillRect(-11, b - 55, 15, 1.2);
    ctx.beginPath(); ctx.moveTo(4, b - 54); ctx.lineTo(5.2, b - 54); ctx.lineTo(7.2, b - 44); ctx.lineTo(6, b - 44); ctx.fill();
    ctx.fillStyle = "#2a1a10"; ctx.fillRect(-11, b - 8, 20, 8);
    ctx.fillStyle = "#5a361c"; ctx.fillRect(-11, b - 63, 15, 9);
    ctx.fillStyle = "rgba(255,200,140,0.18)"; ctx.fillRect(-11, b - 63, 15, 1.2);
    ctx.restore();
    candle(c.x - s * 3, b - 59, now, c);
  }
  function stool(c, glow, now) {
    const { x, y } = c.stool;
    if (glow) {
      ctx.save(); ctx.globalAlpha = 0.55 + 0.45 * Math.sin(now * 5);
      ctx.strokeStyle = "#ffd970"; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.ellipse(x, y, 9, 5.4, 0, 0, 7); ctx.stroke(); ctx.restore();
    }
    ctx.fillStyle = "#3a1d0e"; ctx.fillRect(x - 0.8, y - 5, 1.6, 5);
    ctx.fillStyle = "#7d130c"; ctx.beginPath(); ctx.ellipse(x, y - 5, 6, 3.6, 0, 0, 7); ctx.fill();
    ctx.strokeStyle = "#c9a24a"; ctx.lineWidth = 0.6; ctx.stroke();
    if (glow) { ctx.fillStyle = "#ffe27a"; ctx.font = "700 4px 'Barlow Condensed', sans-serif"; ctx.textAlign = "center"; ctx.fillText("SIT", x, y + 6); }
  }
  function avatar(c) {
    const im = c.player;
    if (!im || !ok(im)) return;
    const dir = AVATAR_DIR[c.facing];
    const { x, y } = c.stool;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(im, 0, SIT_ROW[dir] * 64, 64, 64, x - 32, y - 60, 64, 64);
    ctx.imageSmoothingEnabled = true;
  }

  // ------------------------------------------------------------------ the frame loop
  let start = performance.now();
  function frame(t) {
    const now = (t - start) / 1000;
    for (const c of cabinets) {
      if (c.player && now > c.next) spinCabinet(c, now);
      if (c.pending && now >= c.spinUntil) {
        const o = c.pending; c.pending = null; c.grid = o.grid;
        if (o.total >= 10 * o.bet) c.flash = now + 3;
        if (o.trigger) { c.bonus = now + 4; c.flash = now + 4; c.next = now + 8; }
      }
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    if (ok(carpet)) {
      const pat = ctx.createPattern(carpet, "repeat");
      pat.setTransform(new DOMMatrix().scale(ZOOM / 2));
      ctx.fillStyle = pat; ctx.fillRect(0, 0, cv.width, cv.height);
    } else { ctx.fillStyle = "#1f3a3e"; ctx.fillRect(0, 0, cv.width, cv.height); }
    ctx.setTransform(ZOOM, 0, 0, ZOOM, 0, 0);
    // Draw back to front: anything with a smaller y first, as the game's y-sort does.
    const items = [];
    for (const c of cabinets) {
      items.push({ y: c.y, draw: () => {
        // Someone sitting behind a cabinet would be hidden by it, so it fades to show them.
        const behind = c.player && c.facing === "up";
        if (behind) ctx.globalAlpha = 0.62;
        if (c.facing === "down") cabinetFront(c, now); else if (c.facing === "up") cabinetBack(c, now); else cabinetSide(c, now, c.facing);
        ctx.globalAlpha = 1;
      } });
      items.push({ y: c.stool.y - 0.5, draw: () => stool(c, !c.player, now) });
      items.push({ y: c.stool.y, draw: () => avatar(c) });
    }
    items.sort((a, b) => a.y - b.y);
    for (const it of items) it.draw();
    // legend
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.font = "600 15px 'IBM Plex Sans', sans-serif"; ctx.textAlign = "left"; ctx.fillStyle = "#f1e4c4";
    const lg = [["Top row: screens face up (you see their backs; they fade while someone sits behind)", 30], ["Bottom row: screens face down, towards you", 52], ["End caps: screens face left and right", 74]];
    ctx.fillStyle = "rgba(10,5,3,0.7)"; ctx.fillRect(16, 14, 600, 72);
    ctx.fillStyle = "#f1e4c4"; for (const [s, y] of lg) ctx.fillText(s, 28, y + 4);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
