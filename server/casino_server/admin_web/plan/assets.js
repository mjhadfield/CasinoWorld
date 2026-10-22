// The Floor plan tab's Assets view (plan_assets.py): the furniture, decor, rugs and floor textures the room editor's
// palette offers. The built-ins (LPC packs, server/plan_assets/CREDITS.md) are read-only; uploads can be named,
// sorted into a category, stood on the floor / laid flat / hung on the wall, given their anchor (where they stand)
// and footprint (what blocks walking) by dragging on the picture, given pictures for other facings, and deleted
// unless a room uses them.
let el, api, status, cat, changed, app;
let pick = null, filter = "";

export function open(h) {
  ({ el, api, status, cat, changed, app } = h);
  draw();
}

async function refresh(select) {
  cat = await changed();
  if (select !== undefined) pick = select;
  draw();
}

function draw() {
  const groups = {};
  for (const [id, a] of Object.entries(cat.assets)) (groups[a.category] ||= []).push([id, a]);
  const order = [...cat.categories, ...Object.keys(groups).filter(c => !cat.categories.includes(c))];
  const q = filter.toLowerCase();
  const tile = (id, a, url, sub) => el("button", { className: "pl-asset" + (pick === id ? " on" : ""), title: a.name, onclick: () => { pick = id; draw(); } },
    el("img", { src: url, alt: "" }), el("span", { textContent: a.name }), sub ? el("small", { textContent: sub }) : null);
  const lists = order.filter(c => groups[c]).map(c => {
    const items = groups[c].filter(([, a]) => !q || a.name.toLowerCase().includes(q));
    return items.length ? el("section", {}, el("h3", { textContent: `${c} (${items.length})` }),
      el("div", { className: "pl-asset-grid" }, ...items.map(([id, a]) => tile(id, a, a.facings.down.url, a.uploaded ? "upload" : "")))) : null;
  });
  const floors = Object.entries(cat.floors).filter(([, f]) => f.url && (!q || f.name.toLowerCase().includes(q)));
  app.replaceChildren(
    el("div", { className: "pl-asset-main" },
      el("div", { className: "pl-asset-list panel" },
        el("div", { className: "pl-bar" },
          el("input", { type: "search", placeholder: "Search the library", value: filter, oninput: e => { filter = e.target.value; draw(); app.querySelector("input[type=search]").focus(); } }),
          uploadButton("Upload pictures", "asset"), uploadButton("Upload floor textures", "floor"),
          el("a", { href: "/plan-art-credits", target: "_blank", textContent: "Credits" })),
        el("p", { className: "hint", textContent: "Drop PNGs anywhere here to upload them. Pixel art is drawn at its own size (an LPC tile is 32px; the casino's people are 64px tall)." }),
        ...lists,
        floors.length ? el("section", {}, el("h3", { textContent: `Floors (${floors.length})` }),
          el("div", { className: "pl-asset-grid" }, ...floors.map(([id, f]) => tile(id, f, f.url, f.uploaded ? "upload" : "")))) : null),
      el("aside", { className: "pl-asset-detail panel" }, detail())));
  app.ondragover = e => e.preventDefault();
  app.ondrop = e => { e.preventDefault(); upload([...e.dataTransfer.files], "asset"); };
}

function uploadButton(text, kind) {
  const input = el("input", { type: "file", accept: "image/png,image/webp,image/gif,image/jpeg", multiple: true, hidden: true, onchange: () => upload([...input.files], kind) });
  return el("label", { className: "button" }, text, input);
}

async function upload(files, kind) {
  let last = null;
  for (const f of files) {
    try {
      last = (await api("PUT", `/api/plan-assets/${encodeURIComponent(f.name)}?kind=${kind}`, f, true)).id;
      status(`Uploaded ${f.name}.`, "ok");
    } catch (e) { status(`${f.name}: ${e.message}`, "warn"); }
  }
  if (last) refresh(last);
}

// ---------------------------------------------------------------- the picked asset
function detail() {
  if (!pick) return el("p", { className: "hint", textContent: "Pick an asset to see it, or upload your own." });
  const a = cat.assets[pick], f = cat.floors[pick];
  if (f) {
    return el("div", {}, el("h3", { textContent: f.name }),
      el("div", { className: "pl-floor-preview", style: `background-image:url(${f.url})` }),
      f.uploaded ? field("Name", input(f.name, v => save({ name: v }))) : null,
      f.uploaded ? field("Credit", input(f.credit, v => save({ credit: v }))) : el("p", { className: "hint", textContent: "Built in: " + credit(f.credit) }),
      f.uploaded ? del() : null);
  }
  if (!a) return null;
  const facings = ["down", "left", "up", "right"];
  return el("div", { className: "pl-asset-edit" },
    el("h3", { textContent: a.name }),
    stage(a),
    el("p", { className: "hint", textContent: a.uploaded ? "Drag the dot to where it stands (the middle of its base). Drag the box (or its corner) to the footprint that blocks walking." : "Built in (" + credit(a.credit) + "). The gold dot is where it stands; the box is what blocks walking." }),
    a.uploaded ? field("Name", input(a.name, v => save({ name: v }))) : null,
    a.uploaded ? field("Category", select(a.category, cat.categories.map(c => [c, c]), v => save({ category: v }))) : null,
    a.uploaded ? field("Stands", select(a.mount, [["floor", "On the floor"], ["flat", "Flat (a rug)"], ["wall", "On the back wall"]], v => save({ mount: v }))) : null,
    a.uploaded ? field("Credit", input(a.credit || "", v => save({ credit: v }))) : null,
    el("h4", { textContent: "Facings" }),
    el("div", { className: "pl-facings" }, ...facings.map(fc => {
      const p = a.facings[fc];
      return el("div", { className: "pl-facing" },
        el("span", { textContent: fc }),
        p ? el("img", { src: p.url, alt: fc, style: p.mirror ? "transform:scaleX(-1)" : "" }) : el("span", { className: "hint", textContent: fc === "down" ? "" : "the down picture" }),
        a.uploaded && fc !== "down" ? facingUpload(fc) : null,
        a.uploaded && (fc === "left" || fc === "right") && !(p && !p.mirror) && a.facings[fc === "left" ? "right" : "left"] && !a.facings[fc === "left" ? "right" : "left"].mirror
          ? el("button", { textContent: "Mirror", onclick: () => save({ mirror: { [fc]: fc === "left" ? "right" : "left" } }) }) : null);
    })),
    a.uploaded ? del() : null);
}

function credit(key) {
  return { wood: "LPC Wooden Furniture", upholstery: "LPC Upholstery", tavern: "LPC Tavern", floors: "LPC Floors", medieval: "LPC Medieval Village Decorations",
           plant: "Potted plant by AntumDeluge", fountain: "LPC water fountain by Sharm" }[key] || key || "no credit given";
}

function facingUpload(fc) {
  const input = el("input", { type: "file", accept: "image/*", hidden: true, onchange: async () => {
    try { await api("PUT", `/api/plan-assets/${pick}/facings/${fc}`, input.files[0], true); status(`The ${fc} picture is in.`, "ok"); refresh(); }
    catch (e) { status(e.message, "warn"); }
  } });
  return el("label", { className: "button small" }, "Picture…", input);
}

function del() {
  return el("button", { className: "danger", textContent: "Delete", onclick: async () => {
    if (!confirm("Delete this upload?")) return;
    try { await api("DELETE", "/api/plan-assets/" + pick); status("Deleted.", "ok"); pick = null; refresh(); }
    catch (e) { status(e.message, "warn"); }
  } });
}

async function save(changes) {
  try { await api("PATCH", "/api/plan-assets/" + pick, changes); refresh(); }
  catch (e) { status(e.message, "warn"); }
}

function field(label, inputEl) { return el("label", { className: "pl-field" }, el("span", { textContent: label }), inputEl); }
function input(value, set) { return el("input", { value, onchange: e => set(e.target.value) }); }
function select(value, options, set) {
  return el("select", { onchange: e => set(e.target.value) }, ...options.map(([v, t]) => el("option", { value: v, textContent: t, selected: v === value })));
}

// ---------------------------------------------------------------- the picture, its anchor and footprint
function stage(a) {
  const pic = a.facings.down, w = a.rect[2], h = a.rect[3], k = Math.max(2, Math.min(6, Math.floor(260 / Math.max(w, h))));
  const pad = 24, c = el("canvas", { className: "pl-stage-pic", width: w * k + 2 * pad, height: h * k + 2 * pad });
  const g = c.getContext("2d"), img = new Image();
  let anchor = [-a.rect[0], -a.rect[1]], body = a.body ? a.body.slice() : null, drag = null;
  const toPx = (x, y) => [pad + (x + anchor[0]) * k, pad + (y + anchor[1]) * k];   // about the anchor -> canvas
  function paint() {
    g.fillStyle = "#23403e"; g.fillRect(0, 0, c.width, c.height);
    g.imageSmoothingEnabled = false;
    if (img.complete) g.drawImage(img, pad, pad, w * k, h * k);
    if (body) {
      const [x, y] = toPx(body[0], body[1]);
      g.fillStyle = "rgba(255,90,72,.3)"; g.fillRect(x, y, body[2] * k, body[3] * k);
      g.strokeStyle = "#ff5a48"; g.lineWidth = 2; g.strokeRect(x, y, body[2] * k, body[3] * k);
      g.fillStyle = "#ff5a48"; g.fillRect(x + body[2] * k - 5, y + body[3] * k - 5, 10, 10);
    }
    const [ax, ay] = toPx(0, 0);
    g.fillStyle = "#ffd36b"; g.beginPath(); g.arc(ax, ay, 6, 0, 7); g.fill();
    g.strokeStyle = "#000"; g.lineWidth = 1.5; g.stroke();
  }
  img.onload = paint;
  img.src = pic.url;
  if (a.uploaded) {
    const at = e => { const r = c.getBoundingClientRect(); return [(e.clientX - r.left) * c.width / r.width, (e.clientY - r.top) * c.height / r.height]; };
    c.onpointerdown = e => {
      const [px, py] = at(e), [ax, ay] = toPx(0, 0);
      c.setPointerCapture(e.pointerId);
      if (Math.hypot(px - ax, py - ay) < 10) drag = { what: "anchor" };
      else if (body) {
        const [bx, by] = toPx(body[0], body[1]), bx2 = bx + body[2] * k, by2 = by + body[3] * k;
        if (Math.abs(px - bx2) < 10 && Math.abs(py - by2) < 10) drag = { what: "corner" };
        else if (px > bx && px < bx2 && py > by && py < by2) drag = { what: "body", from: [px, py], was: body.slice() };
      }
    };
    c.onpointermove = e => {
      if (!drag) return;
      const [px, py] = at(e);
      const sx = Math.round((px - pad) / k), sy = Math.round((py - pad) / k);   // picture pixels
      if (drag.what === "anchor") {
        const nx = Math.max(0, Math.min(w, sx)), ny = Math.max(0, Math.min(h, sy));
        if (body) { body[0] -= nx - anchor[0]; body[1] -= ny - anchor[1]; }   // (the footprint stays where it is on the picture)
        anchor = [nx, ny];
      } else if (drag.what === "corner") {
        body[2] = Math.max(2, sx - anchor[0] - body[0]); body[3] = Math.max(2, sy - anchor[1] - body[1]);
      } else {
        body[0] = drag.was[0] + Math.round((px - drag.from[0]) / k); body[1] = drag.was[1] + Math.round((py - drag.from[1]) / k);
      }
      paint();
    };
    c.onpointerup = () => { if (drag) { drag = null; save({ anchor, ...(body ? { body } : {}) }); } };
  }
  return c;
}
