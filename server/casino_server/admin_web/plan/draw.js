// Drawing the floor plan on a canvas, in plan coordinates (the caller sets the transform): a room's floor and walls as
// the game draws them (plan_room.gd), its doorways, and everything in it -- tables in their table styles (the Tables
// tab's render.js), cabinets, pieces, standing figures and furniture -- plus the NPCs' points and zones.
import { render, loadAssets, planShadow, planChair, planSpot, planDealer } from "/admin-ui/tables/render.js";
import { CAT, shapes, kindOf, piece, gap, STOOLS, cabinetsOf } from "./geom.js";

const images = {};
let redraw = () => {};
export function onImage(fn) { redraw = fn; }

/** A picture by URL (null until it's loaded; the view redraws when it is). */
export function image(url) {
  if (!url) return null;
  if (!images[url]) {
    const img = new Image();
    img.onload = () => redraw();
    img.src = url;
    images[url] = img;
  }
  return images[url].complete && images[url].naturalWidth ? images[url] : null;
}

// ---------------------------------------------------------------- the tables, drawn once each in their style
let styles = null;   // {cards, roulette, craps}: the Tables tab's styles and which table has which
const thumbs = {};
const KIND = { roulette: "roulette", craps: "craps" };

export async function loadTables(api) {
  await loadAssets("/admin-ui/tables/");
  const kinds = ["cards", "roulette", "craps"];
  const got = await Promise.all(kinds.map(k => api("GET", "/api/table-styles?kind=" + k)));
  styles = Object.fromEntries(kinds.map((k, i) => [k, got[i]]));
}

// A table's style: its id and design.
function styleOf(game, tableId) {
  if (!styles) return {};
  const st = styles[KIND[game] || "cards"], sid = (st.tables || {})[tableId] || st.default;
  return { sid, design: (st.styles[sid] || st.styles[st.default] || {}).design };
}

function tableThumb(game, tableId) {
  const { sid, design } = styleOf(game, tableId);
  const key = `${game}|${sid}`;
  if (!design) return null;
  if (!thumbs[key]) {
    const rect = CAT.games[game].at["0"].rect, c = document.createElement("canvas");
    c.width = Math.ceil(rect[2] * 2);
    try { render(c, design, CAT.games[game].prefix, rect, { bare: true, plan: true }); } catch (e) { return null; }
    thumbs[key] = { canvas: c, rect };
  }
  return thumbs[key];
}

// ---------------------------------------------------------------- rooms
const SIGN = { back: "#120406", rim: "#f2c14e", text: "#ffd76a" };

function floorFill(ctx, texture, tint) {
  if (texture === "carpet") {
    const img = image("/admin-ui/tables/textures/carpet.png");
    if (img) return ctx.createPattern(img, "repeat");
  } else if (CAT.floors[texture] && CAT.floors[texture].url) {
    const img = image(CAT.floors[texture].url), k = CAT.floors[texture].scale || 1;
    if (img) {
      const pat = ctx.createPattern(img, "repeat");
      if (k !== 1) pat.setTransform(new DOMMatrix().scale(1 / k));   // (a finer tile, shown at its game size)
      return pat;
    }
  }
  return texture === "carpet" ? "#1f3a3e" : tint;
}

function paint(ctx, r, texture, tint) {
  ctx.save();
  ctx.fillStyle = floorFill(ctx, texture, tint);
  ctx.fillRect(r[0], r[1], r[2], r[3]);
  if (texture !== "plain" && tint && tint.toLowerCase() !== "#ffffff") {   // (tinted: multiplied, as the game's modulate)
    ctx.globalCompositeOperation = "multiply";
    ctx.fillStyle = tint;
    ctx.fillRect(r[0], r[1], r[2], r[3]);
  }
  ctx.restore();
}

// ---------------------------------------------------------------- floor patches (plan_room.gd draws them the same way)
/** A patch's outline as points, `inset` in from its edge; the same number of points at any inset. */
function outline(x, y, w, h, p, inset = 0) {
  x += inset; y += inset; w = Math.max(0, w - 2 * inset); h = Math.max(0, h - 2 * inset);
  if (p.shape === "oval") return Array.from({ length: 64 }, (_, i) => { const a = Math.PI * i / 32; return [x + w / 2 + w / 2 * Math.cos(a), y + h / 2 + h / 2 * Math.sin(a)]; });
  if (p.shape !== "rounded") return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
  const r = Math.max(0, Math.min((p.radius ?? 24) - inset, w / 2, h / 2)), out = [];
  for (const [cx, cy, a0] of [[x + w - r, y + r, -90], [x + w - r, y + h - r, 0], [x + r, y + h - r, 90], [x + r, y + r, 180]])
    for (let k = 0; k <= 6; k++) { const a = (a0 + 15 * k) * Math.PI / 180; out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
  return out;
}

const rect = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];

/** The pattern's shapes over a w×h patch, from its corner (they run past the edge; the outline clips them). */
function patternShapes(w, h, pat) {
  const s = pat.size, out = [], nx = Math.ceil(w / s), ny = Math.ceil(h / s);
  if (pat.kind === "stripes") for (let i = 0; i < nx; i++) out.push(rect(i * s, 0, s / 2, h));
  if (pat.kind === "diagonal") for (let k = -h; k < w; k += s) out.push([[k, 0], [k + s / 2, 0], [k + s / 2 + h, h], [k + h, h]]);
  if (pat.kind === "checks") for (let i = 0; i < nx; i++) for (let j = i % 2; j < ny; j += 2) out.push(rect(i * s, j * s, s, s));
  if (pat.kind === "diamonds") for (let i = 0; i <= nx; i++) for (let j = 0; j <= ny; j++) out.push([[i * s, j * s - s / 2], [i * s + s / 2, j * s], [i * s, j * s + s / 2], [i * s - s / 2, j * s]]);
  if (pat.kind === "dots") for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++)
    out.push(Array.from({ length: 16 }, (_, k) => [i * s + s / 2 + s / 4 * Math.cos(Math.PI * k / 8), j * s + s / 2 + s / 4 * Math.sin(Math.PI * k / 8)]));
  if (pat.kind === "grid") {   // (the uprights stop at the rails, so nothing's drawn twice)
    const lw = Math.max(1, Math.round(s / 16));
    for (let j = 0; j <= ny; j++) out.push(rect(0, j * s - lw / 2, w, lw));
    for (let i = 0; i <= nx; i++) for (let j = 0; j < ny; j++) out.push(rect(i * s - lw / 2, j * s + lw / 2, lw, s - lw));
  }
  return out;
}

/** A patch's border as rings between two insets, each [from, to, darker]. */
function borderRings(b) {
  const W = b.width;
  if (b.style === "line") return [[0, W]];
  if (b.style === "double") { const t = Math.max(1, W / 4); return [[0, t], [W - t, W]]; }
  if (b.style === "inlay") return W >= 3 ? [[0, W], [0, 1, true], [W - 1, W, true]] : [[0, W]];
  return [];
}

const darker = hex => "#" + [1, 3, 5].map(i => Math.round(parseInt(hex.slice(i, i + 2), 16) / 2).toString(16).padStart(2, "0")).join("");

function trace(ctx, pts) { ctx.moveTo(...pts[0]); for (const q of pts.slice(1)) ctx.lineTo(...q); ctx.closePath(); }

function drawPatch(ctx, x, y, p) {
  const shape = outline(x, y, p.w, p.h, p), pat = p.pattern || {}, bor = p.border || {};
  ctx.save();
  ctx.beginPath(); trace(ctx, shape); ctx.clip();
  paint(ctx, [x, y, p.w, p.h], p.texture, p.tint);
  if (pat.kind && pat.kind !== "none") {
    ctx.globalAlpha = pat.opacity / 100; ctx.fillStyle = pat.colour;
    ctx.beginPath();
    for (const poly of patternShapes(p.w, p.h, pat)) trace(ctx, poly.map(([a, b]) => [x + a, y + b]));
    ctx.fill();
    ctx.globalAlpha = 1;
  }
  for (const [a, b, dark] of borderRings(bor)) {
    ctx.fillStyle = dark ? darker(bor.colour) : bor.colour;
    ctx.beginPath(); trace(ctx, outline(x, y, p.w, p.h, p, a)); trace(ctx, outline(x, y, p.w, p.h, p, b)); ctx.fill("evenodd");
  }
  ctx.restore();
}

/** A room: floor, patches, walls, doorways. `ops` is its doorways (geom.openings). */
export function drawRoom(ctx, room, ops, opts = {}) {
  const W = CAT.walls, st = W.styles[room.walls.style] || W.styles.crimson, { x, y, w, h } = room;
  ctx.save();
  if (opts.dim) ctx.globalAlpha = 0.45;
  paint(ctx, [x, y, w, h], room.floor.texture, room.floor.tint);
  for (const p of room.patches) if (!p._hidden) drawPatch(ctx, x + p.x, y + p.y, p);   // (_hidden: hidden on the plan for now)
  const bare = room.walls.style === "none";   // no walls drawn: just the floor, and its doors
  const thin = room.walls.back === "thin";   // the back wall just a border, like the sides
  if (!bare) {
    // the back wall
    if (!thin) {
      ctx.fillStyle = st.paper; ctx.fillRect(x, y, w, W.top);
      ctx.fillStyle = st.stripe;
      for (let sx = 0; sx < w; sx += 24) ctx.fillRect(x + sx, y, Math.min(10, w - sx), W.top * 0.6);
      ctx.fillStyle = st.wainscot; ctx.fillRect(x, y + W.top * 0.6, w, W.top * 0.31);
      ctx.fillStyle = st.trim; ctx.fillRect(x, y + W.top - 8, w, 4);
    }
    ctx.fillStyle = st.edge; ctx.fillRect(x, y + (thin ? 0 : W.top - 4), w, thin ? W.side : 4);
    ctx.fillRect(x, y, W.side, h); ctx.fillRect(x + w - W.side, y, W.side, h); ctx.fillRect(x, y + h - W.bottom, w, W.bottom);
    const sign = thin ? "" : room.walls.sign;
    if (sign) {
      const sw = Math.min(420, Math.max(120, sign.length * 12 + 40)), sx = x + room.walls.sign_at - sw / 2;
      ctx.fillStyle = SIGN.back; ctx.fillRect(sx, y + 6, sw, 30);
      ctx.strokeStyle = SIGN.rim; ctx.lineWidth = 2; ctx.strokeRect(sx, y + 6, sw, 30);
      ctx.fillStyle = SIGN.text; ctx.font = "bold 18px 'DejaVu Sans', sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(sign, sx + sw / 2, y + 22);
    }
  }
  for (const o of ops || []) {
    const g = gap(room, o);
    if (!bare) {
      paint(ctx, g, room.floor.texture, room.floor.tint);
      ctx.fillStyle = st.trim;
      if (o.side === "top") { ctx.fillRect(g[0] - 5, g[1], 5, g[3]); ctx.fillRect(g[0] + g[2], g[1], 5, g[3]); }
      else if (o.side === "bottom") { ctx.fillRect(g[0] - 4, g[1] - 2, 4, g[3] + 2); ctx.fillRect(g[0] + g[2], g[1] - 2, 4, g[3] + 2); }
      else { ctx.fillRect(g[0] - 2, g[1] - 3, g[2] + 4, 6); ctx.fillRect(g[0] - 2, g[1] + g[3] - 3, g[2] + 4, 6); }
    }
    if (o.kind === "door" || o.to == null) {   // shut: leaves across the gap (a door to nowhere stays shut)
      ctx.fillStyle = o.side === "bottom" ? "rgba(153,204,230,.6)" : "#4a2a1c";
      if (o.side === "top" && !thin) ctx.fillRect(g[0], g[1] + 8, g[2], g[3] - 12);
      else ctx.fillRect(g[0], g[1], g[2], g[3]);
      if (o.to == null) { ctx.strokeStyle = "#ff9a8a"; ctx.lineWidth = 2; ctx.setLineDash([4, 3]); ctx.strokeRect(...g); ctx.setLineDash([]); }
    }
  }
  ctx.restore();
}

// ---------------------------------------------------------------- what's in a room
function cabinetLook(variant) {
  const v = (CAT.slot_looks || {})[variant] || {};
  return { body: v.body || "#4a2a16", trim: v.trim || "#ffb347" };
}

/** One slot cabinet, its base point at x, y. */
function drawCabinet(ctx, x, y, f, variant) {
  const look = cabinetLook(variant);
  const art = { down: [-16, -64, 32, 64], up: [-16, -64, 32, 64], left: [-12, -64, 24, 64], right: [-12, -64, 24, 64] }[f];
  ctx.fillStyle = look.body; ctx.fillRect(x + art[0], y + art[1], art[2], art[3]);
  ctx.strokeStyle = look.trim; ctx.lineWidth = 1.5; ctx.strokeRect(x + art[0], y + art[1], art[2], art[3]);
  if (f === "down") { ctx.fillStyle = "#111"; ctx.fillRect(x - 12, y - 52, 24, 22); ctx.fillStyle = look.trim; ctx.fillRect(x - 12, y - 60, 24, 5); }
  else if (f !== "up") { ctx.fillStyle = "#111"; ctx.fillRect(x + (f === "left" ? -12 : 6), y - 52, 6, 22); }
  const st = STOOLS[f];
  ctx.fillStyle = "#2a2320"; ctx.beginPath(); ctx.ellipse(x + st[0] + st[2] / 2, y + st[1] + st[3] / 2, 9, 6, 0, 0, 7); ctx.fill();
  ctx.strokeStyle = "#c9a24a"; ctx.lineWidth = 1; ctx.stroke();
}

/** One thing in a room, at its place. `opts`: ghost (being placed), picked, bad. */
export function drawItem(ctx, room, item, opts = {}) {
  const s = shapes(room, item);
  const x = room.x + item.x, y = room.y + item.y, kind = kindOf(item.asset);
  ctx.save();
  if (opts.ghost) ctx.globalAlpha = 0.6;
  if (!s) {
    ctx.fillStyle = "rgba(255,90,72,.4)"; ctx.fillRect(x - 16, y - 16, 32, 32);
  } else if (kind === "table") {
    drawTable(ctx, item, x, y, s);
  } else if (kind === "slot") {
    drawCabinet(ctx, x, y, item.facing || "down", item.props.variant);
  } else if (kind === "bank") {   // (the back row first, so the front row stands over it)
    for (const c of cabinetsOf(item).sort((a, b) => a.y - b.y)) drawCabinet(ctx, room.x + c.x, room.y + c.y, c.facing, c.props.variant);
  } else if (item.asset === "podium") {
    ctx.fillStyle = "#3b1d0e"; ctx.fillRect(x - 15, y - 18, 30, 18);
    ctx.fillStyle = "#c9a24a"; ctx.fillRect(x - 17, y - 24, 34, 7);
    ctx.fillStyle = "#120406"; ctx.fillRect(x - 8, y - 31, 16, 8); ctx.fillStyle = "#2f6f8f"; ctx.fillRect(x - 7, y - 30, 14, 6);
  } else if (item.asset === "npc") {
    drawFigure(ctx, x, y, item.props.look, item.facing || "down");
    if (item.props.name) {
      ctx.fillStyle = "#fff"; ctx.font = "bold 11px sans-serif"; ctx.textAlign = "center"; ctx.fillText(item.props.name, x, y - 54);
    }
  } else {
    drawFurniture(ctx, item, x, y, s);
  }
  ctx.restore();
  if (s && (opts.picked || opts.bad)) {
    ctx.save();
    ctx.lineWidth = 2;
    ctx.strokeStyle = opts.bad ? "#ff5a48" : "#ffd36b";
    ctx.setLineDash(opts.bad ? [] : [6, 3]);
    ctx.strokeRect(...s.rect);
    if (s.sign) ctx.strokeRect(...s.sign.rect);
    ctx.restore();
  }
}

/** A table as the game shows it: the table turned, its shadow still falling down the screen, and its chairs, dealers
 *  and results sign upright where the catalogue says they stand at that turn (a dealer behind an upright table
 *  first, the felt hiding their feet). */
function drawTable(ctx, item, x, y, s) {
  const game = item.asset.slice(6), g = CAT.games[game], t = tableThumb(game, item.id), rot = (item.rot || 0) * Math.PI / 180;
  const at = g.at[String(item.rot || 0)] || g.at["0"], behind = c => !item.rot && c.at[1] < 0;
  at.crew.filter(behind).forEach(c => planDealer(ctx, [x + c.at[0], y + c.at[1]], c.facing));
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  if (t) {
    planShadow(ctx, g.prefix, [Math.sin(rot), Math.cos(rot)]);
    ctx.drawImage(t.canvas, t.rect[0], t.rect[1], t.rect[2], t.rect[3]);
  } else {
    const b = g.at["0"].body;
    ctx.fillStyle = "#1f5a3c"; ctx.fillRect(...b);
    ctx.fillStyle = "#f3e6c4"; ctx.font = "600 18px sans-serif"; ctx.textAlign = "center";
    ctx.fillText(item.props.label || game, b[0] + b[2] / 2, b[1] + b[3] / 2);
  }
  ctx.restore();
  if (s.sign) drawSign(ctx, s.sign);
  const upright = [...at.chairs.map(p => [p, null]), ...at.crew.filter(c => !behind(c)).map(c => [c.at, c.facing])].sort((a, b) => a[0][1] - b[0][1]);
  for (const [p, facing] of upright) {
    const q = [x + p[0], y + p[1]];
    if (facing) planDealer(ctx, q, facing);
    else if (game === "craps") planSpot(ctx, q);
    else planChair(ctx, q, Math.PI / 2 + rot, (styleOf(game, item.id).design || {}).chairs);
  }
}

/** A results sign, upright from its foot: a dark board on a brass post. */
function drawSign(ctx, sign) {
  const [rx, ry, rw, rh] = sign.rect, [fx, fy] = sign.foot, top = ry + 2, board = rh * 0.62;
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(fx, fy, 10, 4, 0, 0, 7); ctx.fill();
  ctx.fillStyle = "#8a6a28"; ctx.fillRect(fx - 1.5, top + board, 3, fy - top - board);
  ctx.fillStyle = "#3b2a12"; ctx.fillRect(fx - 7, fy - 3, 14, 4);
  ctx.fillStyle = "#120406"; ctx.fillRect(rx + 1, top, rw - 2, board);
  ctx.strokeStyle = "#c9a24a"; ctx.lineWidth = 1.2; ctx.strokeRect(rx + 1, top, rw - 2, board);
  ctx.fillStyle = "#ffd76a";
  for (let k = 0; k < 8; k++) ctx.fillRect(rx + 6, top + 8 + k * (board - 14) / 8, k % 3 ? rw - 18 : rw - 12, 2);
  ctx.restore();
}

const ROWS = { up: 4, left: 5, down: 6, right: 7 };   // a look's sheet: idle rows, up/left/down/right
function drawFigure(ctx, x, y, look, facing) {
  const img = look && look.startsWith("x_") ? image(`/looks/${look}.png`) : null;
  if (img) {
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, 0, ROWS[facing] * 64, 64, 64, x - 32, y - 60, 64, 64);
    return;
  }
  ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(x, y, 10, 4, 0, 0, 7); ctx.fill();
  ctx.fillStyle = look === "dealer" ? "#1d1d22" : "#3d5aa8"; ctx.fillRect(x - 8, y - 34, 16, 30);
  ctx.fillStyle = "#e0b48c"; ctx.beginPath(); ctx.arc(x, y - 42, 8, 0, 7); ctx.fill();
}

function drawFurniture(ctx, item, x, y, s) {
  const a = piece(item.asset) || {}, f = (a.facings || {})[item.facing || "down"] || (a.facings || {}).down;
  const img = f ? image(f.url) : null;
  if (img) {
    const k = f.scale || 1;   // (a finer picture: its anchor is in game pixels, its pixels k to one)
    ctx.save();
    ctx.imageSmoothingEnabled = k > 1;
    ctx.translate(x, y);
    if (f.mirror) ctx.scale(-1, 1);
    ctx.drawImage(img, -f.anchor[0], -f.anchor[1], img.naturalWidth / k, img.naturalHeight / k);
    ctx.restore();
  } else {
    ctx.fillStyle = "rgba(201,162,74,.35)"; ctx.fillRect(...s.rect);
    ctx.strokeStyle = "#c9a24a"; ctx.strokeRect(...s.rect);
  }
}

// ---------------------------------------------------------------- paths: points and zones
const POINT_COLOURS = { spawn: "#5ad1ff", arrival: "#8cff8c", wander: "#ffd36b" };

export function drawPaths(ctx, room, picked = {}) {
  ctx.save();
  room.paths.zones.forEach((z, i) => {
    if (z._hidden) return;
    const r = [room.x + z.x, room.y + z.y, z.w, z.h];
    ctx.fillStyle = z.kind === "block" ? "rgba(255,90,72,.28)" : "rgba(255,160,60,.25)";
    ctx.fillRect(...r);
    ctx.strokeStyle = picked.zone === i ? "#fff" : z.kind === "block" ? "#ff5a48" : "#ffa03c";
    ctx.lineWidth = picked.zone === i ? 2 : 1; ctx.setLineDash([5, 3]); ctx.strokeRect(...r); ctx.setLineDash([]);
  });
  room.paths.points.forEach((p, i) => {
    if (p._hidden) return;
    const px = room.x + p.x, py = room.y + p.y, c = POINT_COLOURS[p.kind] || "#fff";
    ctx.fillStyle = c; ctx.globalAlpha = 0.25; ctx.beginPath(); ctx.arc(px, py, 12, 0, 7); ctx.fill();
    ctx.globalAlpha = 1; ctx.strokeStyle = picked.point === i ? "#fff" : c; ctx.lineWidth = picked.point === i ? 3 : 2;
    ctx.beginPath(); ctx.arc(px, py, 12, 0, 7); ctx.stroke();
    ctx.fillStyle = c; ctx.font = "bold 12px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.fillText(p.name, px, py + 15);
  });
  ctx.restore();
}

/** Where NPCs can walk (geom.npcReach), tinted. */
export function drawReach(ctx, reach) {
  if (!reach) return;
  ctx.save();
  ctx.fillStyle = "rgba(120,255,160,.16)";
  for (let cy = 0; cy < reach.rows; cy++) for (let cx = 0; cx < reach.cols; cx++)
    if (reach.seen[cy * reach.cols + cx]) ctx.fillRect(reach.x0 + cx * reach.cell, reach.y0 + cy * reach.cell, reach.cell, reach.cell);
  ctx.restore();
}
