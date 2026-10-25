// The floor plan's shapes, doorways and reach, as the server works them out (plan.py): the Floor plan tab draws
// and checks with these while you edit, and the server checks again when the draft is saved.

export let CAT = null;   // the catalogue (GET /api/plan/catalogue)
export function setCatalogue(c) { CAT = c; }

export const STOOLS = { down: [-10, 11, 20, 12], up: [-10, -21, 20, 12], left: [-35, -11, 20, 12], right: [15, -11, 20, 12] };
const AGENT = 9, CELL = 8;

export const at = (r, x, y) => [r[0] + x, r[1] + y, r[2], r[3]];
export const overlap = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
export const inside = (p, r) => r[0] <= p[0] && p[0] <= r[0] + r[2] && r[1] <= p[1] && p[1] <= r[1] + r[3];
export const grow = (r, by) => [r[0] - by, r[1] - by, r[2] + 2 * by, r[3] + 2 * by];
export const outline = room => [room.x, room.y, room.w, room.h];
/** How deep a room's back wall is: the full 3/4-view wall, or a thin border like the sides. */
export const wallTop = room => room.walls.back === "thin" ? CAT.walls.side : CAT.walls.top;
/** The least height a room can have: its walls and a floor deep enough for one figure. */
export const minHeight = room => wallTop(room) + CAT.walls.bottom + CAT.min_floor;
export function interior(room) {
  const W = CAT.walls, top = wallTop(room);
  return [room.x + W.side, room.y + top, room.w - 2 * W.side, room.h - top - W.bottom];
}

export function kindOf(asset) {
  if (asset.startsWith("table:")) return "table";
  if (asset === "slot") return "slot";
  if (asset.startsWith("bank:")) return "bank";
  if (CAT.pieces[asset]) return "piece";
  return "furniture";
}

export function piece(asset) {
  if (CAT.pieces[asset]) return { mount: "floor", ...CAT.pieces[asset] };
  if (asset.startsWith("a:")) return CAT.assets[asset.slice(2)] || null;
  return null;
}

/** A slot bank's cabinets as slot items placed in the room (plan.cabinets); anything else is just itself. */
export function cabinetsOf(item) {
  if (kindOf(item.asset) !== "bank") return [item];
  const bank = CAT.banks[item.asset.slice(5)];
  if (!bank) return [];
  const flip = item.facing === "up", turns = bank.facings.length === CAT.facings.length, slots = item.props.slots || [];
  return bank.cabinets.map(([dx, dy, f], n) => {
    if (flip) { dy = -dy; f = { down: "up", up: "down" }[f] || f; }
    if (turns) f = item.facing || "down";
    return { id: item.id ? `${item.id}_${n + 1}` : undefined, asset: "slot", x: item.x + dx, y: item.y + dy, facing: f,
             props: { variant: slots[n] }, bank: item.id };
  });
}

/** An item's shapes on the plan (see plan.shapes): rect, body, stands, mount, kind; null if its asset is unknown.
 *  A slot bank's: its cabinets' shapes (parts), with rect and body round them all. */
export function shapes(room, item) {
  const x = room.x + item.x, y = room.y + item.y, kind = kindOf(item.asset);
  if (kind === "bank") {
    const parts = cabinetsOf(item).map(c => shapes(room, c));
    if (!parts.length) return null;
    const round = rs => {
      const x0 = Math.min(...rs.map(r => r[0])), y0 = Math.min(...rs.map(r => r[1]));
      return [x0, y0, Math.max(...rs.map(r => r[0] + r[2])) - x0, Math.max(...rs.map(r => r[1] + r[3])) - y0];
    };
    return { kind, parts, rect: round(parts.map(p => p.rect)), body: round(parts.map(p => p.body)), mount: "floor",
             stands: parts.flatMap(p => p.stands) };
  }
  if (kind === "table") {
    const g = CAT.games[item.asset.slice(6)];
    if (!g) return null;
    const a = g.at[String(item.rot || 0)] || g.at["0"];
    const out = { kind, rect: at(a.rect, x, y), body: at(a.body, x, y), mount: "floor", stands: a.stands.map(p => [x + p[0], y + p[1]]) };
    if (a.sign) { const sg = a.sign[signSide(item)]; out.sign = { rect: at(sg.rect, x, y), body: at(sg.body, x, y), foot: [x + sg.foot[0], y + sg.foot[1]] }; }
    return out;
  }
  if (kind === "slot") {
    const f = item.facing || "down", a = CAT.cabinet[f];
    return { kind, rect: at(a.rect, x, y), body: at(a.body, x, y), stool: at(STOOLS[f], x, y), mount: "floor",
             stands: a.stands.map(p => [x + p[0], y + p[1]]) };
  }
  const p = piece(item.asset);
  if (!p) return null;
  const turned = (p.by_facing || {})[item.facing || "down"] || {};
  const rect = turned.rect || p.rect, body = turned.body || p.body || rect;
  return { kind, rect: at(rect, x, y), body: at(body, x, y), mount: p.mount || "floor", stands: [] };
}

/** Which end of a table its results sign stands past, as its players see it (plan.sign_side). */
export function signSide(item) {
  const side = (item.props || {}).sign;
  if (side === "left" || side === "right") return side;
  const a = (CAT.games[item.asset.slice(6)] || { at: {} }).at[String(item.rot || 0)] || {};
  return a.sign_default || "right";
}
export const covers = s => s.sign ? [s.rect, s.sign.rect] : [s.rect];   // all it covers, its sign's too
export const bodies = s => s.sign ? [s.body, s.sign.body] : [s.body];   // what it stands on, its sign's base too

const SLACK = 2;
function clash(a, b) {
  const hit = (r1, r2) => overlap(grow(r1, -SLACK), r2);
  if (a.kind === "slot" && b.kind === "slot")
    return hit(a.body, b.body) || hit(a.stool, b.body) || hit(a.body, b.stool) || hit(a.stool, b.stool);
  const seats = [a, b].filter(s => s.kind === "table" || s.kind === "slot");
  if (seats.length === 2) return covers(a).some(r1 => covers(b).some(r2 => hit(r1, r2)));
  if (seats.length === 1) { const o = (seats[0] === a ? b : a).body; return hit(seats[0].rect, o) || bodies(seats[0]).slice(1).some(r => hit(r, o)); }
  return hit(a.body, b.body);
}

// ---------------------------------------------------------------- doorways
function edge(room, side) {
  const { x, y, w, h } = room;
  return { top: ["h", y, x, x + w], bottom: ["h", y + h, x, x + w], left: ["v", x, y, y + h], right: ["v", x + w, y, y + h] }[side];
}
export const OPPOSITE = { top: "bottom", bottom: "top", left: "right", right: "left" };
function span(room, door) {
  const [axis, fixed, start] = edge(room, door.side);
  return [axis, fixed, start + door.at - door.width / 2, start + door.at + door.width / 2];
}

/** Every placed room's doorways (its own and its neighbours' through its walls), and the problems: as plan.openings. */
export function openings(rooms) {
  const out = {}, problems = [];
  rooms.forEach(r => { out[r.id] = []; });
  for (const room of rooms) for (const door of room.doors) {
    const [axis, fixed, a, b] = span(room, door);
    let mine = { side: door.side, at: door.at, width: door.width, kind: door.kind, to: null, door: door.id, owner: room.id };
    for (const other of rooms) {
      if (other === room) continue;
      const [oaxis, ofixed, ostart, oend] = edge(other, OPPOSITE[door.side]);
      if (oaxis !== axis || ofixed !== fixed || b <= ostart || a >= oend) continue;
      if (a < ostart || b > oend) { problems.push({ room: room.id, item: door.id, message: `${room.name}: a door half opens onto ${other.name}.` }); continue; }
      const theirs = other.doors.find(d => d.side === OPPOSITE[door.side] && overlap([span(other, d)[2], 0, d.width, 1], [a, 0, b - a, 1]));
      if (theirs) {
        if (theirs.kind !== door.kind || theirs.width !== door.width || Math.abs(span(other, theirs)[2] - a) > 0.5)
          problems.push({ room: room.id, item: door.id, message: `${room.name} and ${other.name} have different doors in the same place.` });
        else if (room.id > other.id) { mine = null; break; }
      }
      mine.to = other.id;
      out[other.id].push({ ...mine, side: OPPOSITE[door.side], at: (a + b) / 2 - ostart, to: room.id });
      break;
    }
    if (mine) out[room.id].push(mine);
  }
  return { ops: out, problems };
}

/** A doorway's gap through a room's wall, on the plan. */
export function gap(room, o) {
  const W = CAT.walls, [, fixed, start] = edge(room, o.side), lo = start + o.at - o.width / 2;
  if (o.side === "top") return [lo, fixed, o.width, wallTop(room)];
  if (o.side === "bottom") return [lo, fixed - W.bottom, o.width, W.bottom];
  if (o.side === "left") return [fixed, lo, W.side, o.width];
  return [fixed - W.side, lo, W.side, o.width];
}

// ---------------------------------------------------------------- problems in one room (the live check while editing)
export function label(item) {
  const kind = kindOf(item.asset);
  if (kind === "table") return `${item.props.label || item.asset.slice(6)}${item.id ? ` (${item.id})` : ""}`;
  if (kind === "slot") return `the slot cabinet${item.id ? " " + item.id : ""}`;
  if (kind === "bank") return `the ${((CAT.banks[item.asset.slice(5)] || {}).name || "slot bank").toLowerCase()}${item.id ? " " + item.id : ""}`;
  if (item.asset === "npc" && item.props.name) return item.props.name;
  const p = piece(item.asset);
  return `the ${(p ? p.name : item.asset).toLowerCase()}`;
}

/** What's wrong in a room (things off the floor, in each other's way, points in the wall): [{item index, message}].
 *  A slot bank is checked cabinet by cabinet, its problems under the bank's index. */
export function roomProblems(room) {
  const out = [], inner = interior(room), floorThings = [];
  room.items.flatMap((item, i) => cabinetsOf(item).map(c => [c, i])).forEach(([item, i]) => {
    const s = shapes(room, item), name = label(item);
    if (!s) { out.push({ i, message: `${name} isn't in the library any more.` }); return; }
    if (s.mount === "wall") return;
    const within = (outer, r) => outer[0] <= r[0] && outer[1] <= r[1] && r[0] + r[2] <= outer[0] + outer[2] && r[1] + r[3] <= outer[1] + outer[3];
    if (!bodies(s).every(b => within(inner, b)) || !covers(s).every(r => within(outline(room), r))) { out.push({ i, message: `${name} is off the floor.` }); return; }
    if (s.stands.some(p => !inside(p, inner))) { out.push({ i, message: `${name}'s players would stand in the wall.` }); return; }
    if (s.mount === "floor") floorThings.push([i, item, s]);
  });
  floorThings.forEach(([i, item, s], n) => {
    const other = floorThings.slice(n + 1).find(([, , s2]) => clash(s, s2));
    if (other) { out.push({ i, message: `${label(item)} overlaps ${label(other[1])}.` }); return; }
    const blocker = floorThings.find(([j, , s2]) => j !== i && s.stands.some(p => bodies(s2).some(b => inside(p, b))));
    if (blocker) out.push({ i, message: `${label(blocker[1])} stands where ${label(item)}'s players would.` });
  });
  return out;
}

// ---------------------------------------------------------------- reach
/** Where NPCs can walk, from where they come in (plan._reach_problems' fill, NPC side): {x0, y0, cols, rows,
 *  open, seen} -- `seen[c]` set for a cell they reach. Null with nowhere to come in. */
export function npcReach(rooms) {
  if (!rooms.length) return null;
  const x0 = Math.min(...rooms.map(r => r.x)), y0 = Math.min(...rooms.map(r => r.y));
  const x1 = Math.max(...rooms.map(r => r.x + r.w)), y1 = Math.max(...rooms.map(r => r.y + r.h));
  const cols = Math.floor((x1 - x0) / CELL) + 1, rows = Math.floor((y1 - y0) / CELL) + 1;
  if (cols * rows > 4e6) return null;
  const open = new Uint8Array(cols * rows);
  const mark = (r, v, shrink = 0) => {
    r = grow(r, -shrink);
    const cx0 = Math.max(0, Math.floor((r[0] - x0) / CELL)), cy0 = Math.max(0, Math.floor((r[1] - y0) / CELL));
    const cx1 = Math.min(cols - 1, Math.floor((r[0] + r[2] - x0) / CELL)), cy1 = Math.min(rows - 1, Math.floor((r[1] + r[3] - y0) / CELL));
    for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) {
      const c = [x0 + cx * CELL + CELL / 2, y0 + cy * CELL + CELL / 2];
      if (inside(c, r)) open[cy * cols + cx] = v;
    }
  };
  rooms.forEach(r => mark(interior(r), 1, AGENT - 4));
  const { ops } = openings(rooms), byId = Object.fromEntries(rooms.map(r => [r.id, r]));
  for (const [rid, list] of Object.entries(ops)) for (const o of list) {
    if (o.to == null) continue;
    const g = gap(byId[rid], o);
    mark(o.side === "top" || o.side === "bottom" ? [g[0] + 4, g[1] - 12, g[2] - 8, g[3] + 24] : [g[0] - 12, g[1] + 4, g[2] + 24, g[3] - 8], 1);
  }
  for (const r of rooms) {
    for (const item of r.items.flatMap(cabinetsOf)) { const s = shapes(r, item); if (s && s.mount === "floor") bodies(s).forEach(b => mark(b, 0, -(AGENT - 4))); }
    for (const z of r.paths.zones) mark([r.x + z.x, r.y + z.y, z.w, z.h], 0, -(AGENT - 4));
  }
  const starts = rooms.flatMap(r => r.paths.points.filter(p => p.kind === "arrival").map(p => [r.x + p.x, r.y + p.y]));
  if (!starts.length) return null;
  const seen = new Uint8Array(cols * rows), stack = [];
  const cellOf = p => [Math.floor((p[0] - x0) / CELL), Math.floor((p[1] - y0) / CELL)];
  const nearest = ([cx, cy]) => {
    for (let r = 0; r < 3; r++) for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) {
      const x = cx + dx, y = cy + dy;
      if (x >= 0 && x < cols && y >= 0 && y < rows && open[y * cols + x]) return y * cols + x;
    }
    return -1;
  };
  for (const p of starts) { const c = nearest(cellOf(p)); if (c >= 0 && !seen[c]) { seen[c] = 1; stack.push(c); } }
  while (stack.length) {
    const c = stack.pop(), cx = c % cols, cy = (c - cx) / cols;
    for (const [nx, ny] of [[cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]]) {
      if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
      const n = ny * cols + nx;
      if (open[n] && !seen[n]) { seen[n] = 1; stack.push(n); }
    }
  }
  return { x0, y0, cols, rows, open, seen, cell: CELL, reached: p => { const c = nearest(cellOf(p)); return c >= 0 && !!seen[c]; } };
}
