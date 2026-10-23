// NPCs: the casino's regulars and staff. The roster is a table on the left; the editor on the right keeps the look's
// preview (walking, standing, seated) pinned at its top, with the look and how they play side by side beneath it.
// Punters come and go on their own (each brings a budget they're willing to lose and takes a break after a visit);
// dealers work shifts. Bulk create swaps the roster for a batch to generate, review and create at once.
let H, $, el, money, signed;
let opts = null, list = [], selected = null, draft = null, pollTimer = null, previewTimer = null, tab = "design";
let previewUrl = null, animStart = performance.now(), sort = {key: "role", dir: 1};
const STAFF = ["cocktail_waiter", "pit_boss", "cashier", "bartender"];

export function init(h) {
  H = h; el = h.el; money = h.money; signed = h.signed; $ = s => h.view.querySelector(s) || h.top.querySelector(s);
  h.top.append(
    el("select", {id: "npc-role", ariaLabel: "Show"}, el("option", {value: "", textContent: "Everyone"}), el("option", {value: "punter", textContent: "Punters"}),
      el("option", {value: "dealer", textContent: "Dealers"}), el("option", {value: "staff", textContent: "Other staff"})),
    el("input", {type: "search", id: "npc-search", placeholder: "Search names or traits", style: "width: 220px"}),
    el("span", {className: "hint", id: "npc-count"}),
    el("span", {className: "grow"}),
    el("button", {type: "button", id: "npc-bulk", textContent: "Bulk create"}),
    el("button", {type: "button", className: "primary", id: "npc-new", textContent: "New NPC"}));
  h.view.innerHTML = `
  <div class="wb" style="grid-template-columns: minmax(0, 1fr) minmax(760px, 46%)">
    <div class="panel"><div class="pb" id="roster"></div><div class="pb" id="bulk" hidden></div></div>
    <div class="panel" id="editor"></div>
  </div>
  <style>
    #roster canvas, .npc-b canvas { width: 32px; height: 32px; image-rendering: pixelated; background: var(--stage); border-radius: 4px; display: block; }
    #roster td { height: 38px; }
    #roster td.av { width: 44px; padding-right: 0; }
    #roster .badges, .npc-b .badges { display: flex; gap: 4px; flex-wrap: wrap; }
    .npc-ed-top { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 16px; padding: var(--pad); border-bottom: 1px solid var(--line); flex: none; }
    .npc-stage { display: flex; gap: 6px; align-items: end; background: var(--stage); border-radius: 8px; padding: 8px 10px 4px; color: var(--fg-faint); font-size: var(--fs-xs); position: relative; }
    .npc-stage figure { margin: 0; display: grid; justify-items: center; gap: 0; }
    .npc-stage canvas { image-rendering: pixelated; }
    .npc-stage #pv-note { position: absolute; left: 8px; top: 6px; color: var(--fg-muted); }
    .npc-cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0; min-height: 100%; }
    .npc-cols > div { padding: var(--pad); display: grid; gap: var(--gap); align-content: start; min-width: 0; }
    .npc-cols > div + div { border-left: 1px solid var(--line); }
    .npc-cols h4 { margin: 0; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .1em; color: var(--fg-muted); }
    .slot { display: grid; grid-template-columns: 92px minmax(0, 1fr) minmax(0, 1fr); gap: 6px; align-items: center; font-size: var(--fs-s); color: var(--fg-muted); }
    .slot select { width: 100%; }
    .traits { display: grid; gap: 4px; }
    .trait { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: start; padding: 5px 8px; border: 1px solid var(--line); border-radius: var(--radius); cursor: pointer; font-size: var(--fs-s); }
    .trait input { margin: 2px 0 0; }
    .trait small { display: block; color: var(--fg-faint); }
    .trait:has(input:checked) { border-color: var(--accent-line); background: var(--accent-soft); }
    .npc-b { display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 5px var(--pad); border-bottom: 1px solid var(--line); }
    .npc-b.sel { background: var(--accent-soft); box-shadow: inset 2px 0 0 var(--accent); }
    .npc-b .who { display: grid; gap: 4px; min-width: 0; }
    .npc-b .who input { font-weight: 600; width: min(100%, 16em); }
    .npc-b select { height: 22px; font-size: var(--fs-xs); padding: 0 20px 0 6px; }
    .npc-b .row-acts { display: flex; gap: 4px; }
    .npc-b .row-acts button { height: 24px; padding: 0 8px; }
  </style>`;
  $("#npc-role").addEventListener("change", renderList);
  $("#npc-search").addEventListener("input", renderList);
  $("#npc-new").addEventListener("click", newNpc);
  $("#npc-bulk").addEventListener("click", () => bulkMode(!bulkOn));
}

export async function load() {
  try {
    opts = await H.api("GET", "/api/npc-options");
    await refresh();
    if (!selected && list.length) select(list.find(n => n.role === "punter") || list[0]);
    requestAnimationFrame(animate);
    H.status(list.length + " NPCs loaded.");
  } catch (e) { H.status("Couldn't load NPCs: " + e.message, "warn"); }
}
async function refresh() {
  const data = await H.api("GET", "/api/npcs");
  list = data.npcs;
  renderList();
  if (selected) {   // keep the editor's live status in step (not the draft)
    const fresh = list.find(n => n.id === selected.id);
    if (fresh) { selected = fresh; renderStatus(); }
  }
}
export function shown(on) {
  clearInterval(pollTimer);
  if (on && opts) pollTimer = setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 5000);
}

// ------------------------------------------------------------ Sheets: a look's 64x64 frames
// rows walk (0-3), idle (4-7), sit (8-11), in up/left/down/right order
const images = {}, waiting = {};
function sheet(url) {
  if (!url) return null;
  if (!images[url]) {
    const img = new Image();
    waiting[url] = [];
    img.onload = () => { const w = waiting[url]; waiting[url] = []; w.forEach(f => f()); };
    img.src = url; images[url] = img;
  }
  return images[url].complete && images[url].naturalWidth ? images[url] : null;
}
function frame(canvas, url, col, row, scale = 1) {
  const g = canvas.getContext("2d");
  g.imageSmoothingEnabled = false;
  g.clearRect(0, 0, canvas.width, canvas.height);
  const img = sheet(url);
  if (!img) { if (url) waiting[url].push(() => frame(canvas, url, col, row, scale)); return; }
  const s = 64 * scale;
  g.drawImage(img, col * 64, row * 64, 64, 64, (canvas.width - s) / 2, canvas.height - s, s, s);
}
// the roster's thumbnails: the head and shoulders of the standing frame
function thumb(url) {
  const cv = el("canvas", {width: 32, height: 32});
  const draw = () => {
    const img = sheet(url), g = cv.getContext("2d");
    if (!img) { if (url) waiting[url].push(draw); return; }
    g.imageSmoothingEnabled = false; g.clearRect(0, 0, 32, 32);
    g.drawImage(img, 16, 6 * 64 + 8, 32, 32, 0, 0, 32, 32);
  };
  draw();
  return cv;
}

// ------------------------------------------------------------ the roster
function statusOf(n) {
  if (!n.enabled) return ["Off", "warn"];
  if (n.dealing) return ["Dealing · " + (opts.tables[n.dealing] || n.dealing), "ok"];
  if (n.on_floor) {
    const f = n.on_floor, where = f.table ? opts.tables[f.table] || f.table : null;
    const doing = f.state === "leaving" ? "Leaving" : where ? (f.state === "seated" ? "At " : "Heading to ") + where : "On the floor";
    return [doing + " · " + money(f.bankroll), "ok"];
  }
  if (n.cooldown_until && n.cooldown_until * 1000 > Date.now()) return ["Away till " + new Date(n.cooldown_until * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}), ""];
  if (n.role === "punter") return ["Free to visit", ""];
  if (STAFF.includes(n.role)) return ["Not on the floor yet", ""];
  return ["Off duty", ""];
}
const COLS = [["", ""], ["name", "Name"], ["role", "Role"], ["style", "Style"], ["", "Traits"], ["status", "Now"], ["net", "Net", "num"], ["visits", "Visits", "num"]];
const sortVal = {name: n => n.name, role: n => (opts.roles[n.role] || n.role) + " " + n.name, style: n => n.archetype || "~",
  status: n => (n.on_floor || n.dealing ? "0" : "1") + statusOf(n)[0], net: n => n.role === "punter" ? n.net : -Infinity, visits: n => n.visits};
function renderList() {
  if (!opts) return;
  const role = $("#npc-role").value, q = $("#npc-search").value.trim().toLowerCase();
  const shown = list.filter(n => (!role || n.role === role || (role === "staff" && STAFF.includes(n.role)))
    && (!q || (n.name + " " + n.traits.join(" ") + " " + n.archetype).toLowerCase().includes(q)));
  const f = sortVal[sort.key];
  shown.sort((a, b) => { const x = f(a), y = f(b); return (typeof x === "string" ? x.localeCompare(y) : x - y) * sort.dir; });
  $("#npc-count").textContent = shown.length + " of " + list.length;
  const head = el("tr", {}, ...COLS.map(([k, label, c]) => {
    const th = el("th", {className: (k ? "sort " : "") + (c || ""), textContent: label});
    if (k) {
      if (sort.key === k) th.setAttribute("aria-sort", sort.dir > 0 ? "ascending" : "descending");
      th.addEventListener("click", () => { sort = sort.key === k ? {key: k, dir: -sort.dir} : {key: k, dir: k === "net" || k === "visits" ? -1 : 1}; renderList(); });
    }
    return th;
  }));
  const rows = shown.map(n => {
    const [st, kind] = statusOf(n);
    const tr = el("tr", {className: "click" + (selected && n.id === selected.id ? " sel" : "") + (n.enabled ? "" : " off"), tabIndex: 0},
      el("td", {className: "av"}, thumb(n.look_url)),
      el("td", {}, el("b", {textContent: n.name})),
      el("td", {className: "muted", textContent: opts.roles[n.role] || n.role}),
      el("td", {}, n.archetype && n.role === "punter" ? el("span", {className: "tag gold", textContent: opts.archetypes[n.archetype].label}) : null),
      el("td", {}, el("div", {className: "badges"}, ...n.traits.map(t => el("span", {className: "tag", textContent: opts.modifiers[t].label})))),
      el("td", {className: kind === "ok" ? "pos" : kind === "warn" ? "neg" : "muted", textContent: st}),
      el("td", {className: "num " + (n.net > 0 ? "pos" : n.net < 0 ? "neg" : ""), textContent: n.role === "punter" ? signed(n.net) : ""}),
      el("td", {className: "num", textContent: n.role === "punter" ? n.visits : ""}));
    tr.addEventListener("click", () => select(n));
    tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(n); } });
    return tr;
  });
  $("#roster").replaceChildren(el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows)));
  if (!shown.length) $("#roster").append(el("p", {className: "empty", textContent: "Nobody matches."}));
}

// ------------------------------------------------------------ the editor
function select(n) {
  selected = n;
  draft = n ? JSON.parse(JSON.stringify({name: n.name, role: n.role, look: n.look, archetype: n.archetype || "casual",
                                          traits: n.traits, settings: n.settings, enabled: n.enabled})) : null;
  previewUrl = n ? n.look_url : null;
  renderList(); renderEditor();
}
function newNpc() {
  if (bulkOn) bulkMode(false);
  selected = null; tab = "design";
  draft = {name: "", role: "punter", archetype: "casual", traits: [], settings: {}, enabled: true,
           look: {body: "female", skin: "light", hair: ["bob", "chestnut"], top: ["tshirt", "teal"], bottom: ["pants", "navy"], shoes: ["shoes", "black"]}};
  previewUrl = null;
  renderList(); renderEditor(); updatePreview();
  $("#npc-name").focus();
}
function renderEditor() {
  const box = $("#editor");
  const scrollWas = box.querySelector(".pb")?.scrollTop || 0;
  box.replaceChildren();
  if (!draft) {
    box.append(el("div", {className: "ph", textContent: bulkOn ? "Batch" : "Editor"}),
      el("p", {className: "empty", textContent: bulkOn ? "Generate a batch, then Tweak anyone to change their look or how they play." : "Pick someone on the left, or make a new NPC."}));
    return;
  }
  const d = draft;
  // the head: who, the Design / Now tabs, the actions
  const head = el("div", {className: "ph"}, el("b", {textContent: selected ? selected.name : bulkOn ? "Reviewing " + (d.name || "(no name)") : "New NPC"}));
  if (selected) {
    const tabs = el("div", {className: "seg"}, ...[["design", "Design"], ["now", "Now and lifetime"]].map(([k, t]) => {
      const b = el("button", {type: "button", textContent: t, ariaPressed: String(tab === k)});
      b.addEventListener("click", () => { tab = k; renderEditor(); });
      return b;
    }));
    head.append(tabs);
  }
  head.append(el("span", {className: "grow"}));
  if (bulkOn) {   // a draft in the batch: changes stay in the batch until it's created
    const drop = el("button", {type: "button", className: "ghost", textContent: "Remove from batch"});
    drop.addEventListener("click", () => removeDraft(d));
    const done = el("button", {type: "button", className: "primary", textContent: "Done"});
    done.addEventListener("click", () => { draft = null; renderEditor(); renderBulkList(); });
    head.append(drop, done);
  } else {
    if (selected) {
      if (selected.role === "punter") {
        head.append(el("button", {type: "button", id: "npc-bring", textContent: "Bring in now", onclick: () => act("bring-in", "Here they come.")}),
                    el("button", {type: "button", id: "npc-home", textContent: "Send home", onclick: () => act("send-home", "Off they go.")}));
      }
      const reset = el("button", {type: "button", className: "ghost", textContent: "Reset stats"});
      reset.addEventListener("click", () => confirmIn(reset, "Clear their lifetime figures?", () => act("reset-stats", "Stats cleared.")));
      const del = el("button", {type: "button", className: "ghost danger", textContent: "Delete"});
      del.addEventListener("click", () => confirmIn(del, "Delete " + selected.name + " for good?", deleteNpc));
      head.append(reset, del);
    }
    head.append(el("button", {type: "button", className: "primary", textContent: selected ? "Save" : "Create", onclick: saveDraft}));
  }
  box.append(head);

  if (selected && tab === "now") {
    box.append(el("div", {className: "pb padded", id: "npc-status"}));
    renderStatus();
    return;
  }
  // pinned: the preview, name, role, in service
  const name = el("input", {id: "npc-name", value: d.name, maxLength: 24, placeholder: "Name"});
  name.addEventListener("input", () => { d.name = name.value; });
  if (bulkOn) name.addEventListener("change", renderBulkList);
  const role = el("select", {id: "npc-role-sel"}, ...Object.entries(opts.roles).map(([k, v]) => el("option", {value: k, textContent: v + (opts.on_the_floor.includes(k) ? "" : " (not on the floor yet)"), selected: k === d.role})));
  role.addEventListener("change", () => { d.role = role.value; renderEditor(); });
  const enabled = el("input", {type: "checkbox", id: "npc-enabled", checked: d.enabled});
  enabled.addEventListener("change", () => { d.enabled = enabled.checked; });
  const walk = el("canvas", {width: 128, height: 128, id: "pv-walk"}), idle = el("canvas", {width: 128, height: 128, id: "pv-idle"}), sit = el("canvas", {width: 128, height: 128, id: "pv-sit"});
  box.append(el("div", {className: "npc-ed-top"},
    el("div", {className: "npc-stage"}, el("figure", {}, walk, el("figcaption", {textContent: "Walking"})),
      el("figure", {}, idle, el("figcaption", {textContent: "Standing"})), el("figure", {}, sit, el("figcaption", {textContent: "Seated, from behind"})),
      el("span", {id: "pv-note", textContent: ""})),
    el("div", {style: "display: grid; gap: var(--gap); align-content: start"},
      el("div", {className: "grid2", style: "grid-template-columns: 1fr 1fr"}, el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
        el("label", {className: "field"}, el("span", {textContent: "Role"}), role)),
      el("label", {className: "controls hint"}, enabled, "In service (", d.role === "punter" ? "visits the casino" : "works shifts", ")"),
      bodyRow(d.look))));
  // scrolling: the look's pieces, and how they play
  const body = el("div", {className: "pb"}, el("div", {className: "npc-cols", style: d.role === "punter" ? "" : "grid-template-columns: minmax(0, 1fr)"},
    el("div", {}, el("h4", {textContent: "Look"}), lookDesigner(d)),
    d.role === "punter" ? el("div", {}, el("h4", {textContent: "How they play"}), traitsEditor(d)) : null));
  box.append(body);
  body.scrollTop = scrollWas;
  if (bulkOn) renderBulkList();
}
function confirmIn(btn, question, yes) {
  const y = el("button", {type: "button", className: "primary", textContent: "Yes"}), n = el("button", {type: "button", textContent: "No"});
  const span = el("span", {className: "confirm", style: "text-transform: none; letter-spacing: 0; color: var(--fg)"}, question, y, n);
  btn.replaceWith(span);
  y.addEventListener("click", yes); n.addEventListener("click", renderEditor);
}

const SKIN = {light: "#f3cfb3", amber: "#e3a978", olive: "#c99a6b", taupe: "#b08668", bronze: "#9a6646", brown: "#7a4c32", black: "#4a2e22"};
function bodyRow(L) {
  const body = el("div", {className: "seg"}, ...opts.bodies.map(b => {
    const btn = el("button", {type: "button", textContent: b === "male" ? "Male" : "Female", ariaPressed: String(L.body === b)});
    btn.addEventListener("click", () => { L.body = b; fixFits(L); renderEditor(); updatePreview(); });
    return btn;
  }));
  const skins = el("div", {className: "swatches"}, ...opts.skins.map(s => {
    const b = el("button", {type: "button", className: "sw", title: s, style: "background:" + (SKIN[s] || "#ccc"), ariaPressed: String(L.skin === s), ariaLabel: "Skin " + s});
    b.addEventListener("click", () => { L.skin = s; renderEditor(); updatePreview(); });
    return b;
  }));
  const rnd = el("button", {type: "button", textContent: "Randomise"});
  rnd.addEventListener("click", () => { randomise(L); renderEditor(); updatePreview(); });
  const uni = el("select", {ariaLabel: "Uniform"}, el("option", {value: "", textContent: "Put on a uniform…"}),
    ...Object.keys(opts.uniforms).map(k => el("option", {value: k, textContent: opts.roles[k] || k})));
  uni.addEventListener("change", () => {
    if (!uni.value) return;
    for (const slot of opts.slots) if (!["hair", "beard", "glasses"].includes(slot.slot)) L[slot.slot] = null;
    Object.assign(L, JSON.parse(JSON.stringify(opts.uniforms[uni.value][L.body])));
    renderEditor(); updatePreview();
  });
  return el("div", {className: "controls"}, body, skins, el("span", {className: "grow", style: "flex: 1"}), rnd, uni);
}
function lookDesigner(d) {
  const L = d.look;
  const wrap = el("div", {style: "display: grid; gap: 5px"});
  for (const slot of opts.slots) {   // each piece: option, colour
    const choice = L[slot.slot];
    const fits = slot.options.filter(o => o.bodies.includes(L.body));
    const optSel = el("select", {id: "slot-" + slot.slot},
      ...(slot.required ? [] : [el("option", {value: "", textContent: "None"})]),
      ...fits.map(o => el("option", {value: o.id, textContent: o.label, selected: choice && choice[0] === o.id})));
    if (!choice) optSel.value = "";
    const current = choice && slot.options.find(o => o.id === choice[0]);
    const colSel = el("select", {id: "colour-" + slot.slot, disabled: !current},
      ...(current ? current.colours.map(c => el("option", {value: c, textContent: c.replace(/_/g, " "), selected: choice[1] === c})) : [el("option", {textContent: "—"})]));
    optSel.addEventListener("change", () => {
      if (!optSel.value) { L[slot.slot] = null; }
      else {
        const o = slot.options.find(x => x.id === optSel.value);
        const keep = choice && o.colours.includes(choice[1]) ? choice[1] : o.colours[0];
        L[slot.slot] = [o.id, keep];
      }
      renderEditor(); updatePreview();
    });
    colSel.addEventListener("change", () => { L[slot.slot] = [L[slot.slot][0], colSel.value]; updatePreview(); });
    wrap.append(el("label", {className: "slot"}, el("span", {textContent: slot.label}), optSel, colSel));
  }
  return wrap;
}
function fixFits(L) {   // after a body change: anything that doesn't come in that fit comes off (or the first that does)
  for (const slot of opts.slots) {
    const c = L[slot.slot];
    if (!c) continue;
    const o = slot.options.find(x => x.id === c[0]);
    if (o && o.bodies.includes(L.body)) continue;
    if (slot.required) {
      const alt = slot.options.find(x => x.bodies.includes(L.body));
      L[slot.slot] = [alt.id, alt.colours.includes(c[1]) ? c[1] : alt.colours[0]];
    } else L[slot.slot] = null;
  }
}
const pick = a => a[Math.floor(Math.random() * a.length)];
function randomise(L) {
  L.body = pick(opts.bodies); L.skin = pick(opts.skins);
  for (const slot of opts.slots) {
    const fits = slot.options.filter(o => o.bodies.includes(L.body));
    const odds = {hair: 1, beard: L.body === "male" ? 0.3 : 0, top: 1, over: 0.15, bottom: 1, shoes: 1, neck: 0.1, glasses: 0.2, hat: 0.05}[slot.slot];
    if (Math.random() < odds && fits.length) { const o = pick(fits); L[slot.slot] = [o.id, pick(o.colours)]; }
    else L[slot.slot] = slot.required ? (() => { const o = pick(fits); return [o.id, pick(o.colours)]; })() : null;
  }
}
function updatePreview() {
  clearTimeout(previewTimer);
  const note = () => H.view.querySelector("#pv-note");
  note() && (note().textContent = "Building…");
  previewTimer = setTimeout(async () => {
    try {
      const d = draft, r = await H.api("POST", "/api/looks/preview", {look: d.look});
      previewUrl = r.url;
      if (bulkOn) { d.look_url = r.url; renderBulkList(); }   // the batch's thumbnail follows
      note() && (note().textContent = "");
    } catch (e) { note() && (note().textContent = e.message); }
  }, 250);
}
function animate(now) {   // the preview: walking round in a circle, standing, seated
  const walk = H.view.querySelector("#pv-walk");
  if (walk && previewUrl && !H.view.hidden) {
    const t = (now - animStart) / 1000;
    const dir = [2, 3, 0, 1][Math.floor(t / 1.6) % 4];   // down, right, up, left
    frame(walk, previewUrl, 1 + Math.floor(t * 10) % 8, dir, 2);
    frame(H.view.querySelector("#pv-idle"), previewUrl, Math.floor(t * 1.5) % 2, 6, 2);
    frame(H.view.querySelector("#pv-sit"), previewUrl, 0, 8, 2);
  }
  requestAnimationFrame(animate);
}

function traitsEditor(d) {
  const s = d.settings;
  const box = el("div", {className: "traits"});
  box.append(el("span", {className: "hint", textContent: "Style (pick one)"}));
  for (const [k, a] of Object.entries(opts.archetypes)) {
    const input = el("input", {type: "radio", name: "arch", value: k, checked: d.archetype === k});
    input.addEventListener("change", () => { d.archetype = k; renderEditor(); });
    box.append(el("label", {className: "trait"}, input, el("span", {}, el("b", {textContent: a.label}), el("small", {textContent: a.about}))));
  }
  box.append(el("span", {className: "hint", style: "margin-top: 6px", textContent: "Traits (any)"}));
  for (const [k, m] of Object.entries(opts.modifiers)) {
    const input = el("input", {type: "checkbox", value: k, checked: d.traits.includes(k)});
    input.addEventListener("change", () => { d.traits = input.checked ? [...d.traits, k] : d.traits.filter(t => t !== k); renderEditor(); });
    box.append(el("label", {className: "trait"}, input, el("span", {}, el("b", {textContent: m.label}), el("small", {textContent: m.about}))));
  }
  const pounds = (key, label, placeholder) => {
    const i = el("input", {type: "number", min: 5, step: 5, value: s[key] ? s[key] / 100 : "", placeholder});
    i.addEventListener("input", () => { s[key] = i.value ? Math.round(+i.value * 100) : undefined; });
    return el("label", {className: "field"}, el("span", {textContent: label}), i);
  };
  box.append(el("span", {className: "hint", style: "margin-top: 6px", textContent: "Budget for a visit (what they're willing to lose; blank for their style's usual)"}),
    el("div", {className: "grid2", style: "grid-template-columns: 1fr 1fr"}, pounds("budget_min", "Least (£)", "usual"), pounds("budget_max", "Most (£)", "usual")));
  if (d.traits.includes("hit_and_run")) {
    const i = el("input", {type: "number", min: 5, max: 500, step: 5, value: s.hit_and_run_pct || 50});
    i.addEventListener("input", () => { s.hit_and_run_pct = +i.value; });
    box.append(el("label", {className: "field"}, el("span", {textContent: "Hit-and-run: leave once up (% of budget)"}), i));
  }
  if (d.traits.includes("superstitious")) {
    const i = el("input", {value: (s.lucky_numbers || []).join(", "), placeholder: "e.g. 7, 17, 23"});
    i.addEventListener("input", () => { s.lucky_numbers = i.value.split(/[ ,]+/).filter(Boolean).map(Number).filter(n => Number.isInteger(n)); });
    box.append(el("label", {className: "field"}, el("span", {textContent: "Lucky numbers (Roulette, 0-36)"}), i));
  }
  const games = el("div", {className: "seg wrap"}, ...Object.entries(opts.games).map(([k, v]) => {
    const on = (s.favourite_games || []).includes(k);
    const b = el("button", {type: "button", textContent: v, ariaPressed: String(on)});
    b.addEventListener("click", () => { const g = new Set(s.favourite_games || []); on ? g.delete(k) : g.add(k); s.favourite_games = [...g]; renderEditor(); });
    return b;
  }));
  box.append(el("span", {className: "hint", style: "margin-top: 6px", textContent: "Favourite games (they head for these first)"}), games);
  return box;
}

function renderStatus() {
  const box = H.view.querySelector("#npc-status");
  if (!box || !selected) return;
  const n = selected;
  const [st] = statusOf(n);
  box.replaceChildren(el("div", {className: "controls"}, el("span", {className: "tag", textContent: st})));
  if (n.role !== "punter") { box.append(el("p", {className: "hint", textContent: n.dealing ? "Dealing at " + (opts.tables[n.dealing] || n.dealing) + "." : "Not on a table right now."})); return; }
  const stat = (label, value, cls = "") => el("div", {className: "stat"}, el("small", {textContent: label}), el("b", {className: cls, textContent: value}));
  if (n.on_floor) box.append(el("div", {className: "stats"}, stat("This visit", money(n.on_floor.bankroll) + " of " + money(n.on_floor.budget)),
    stat("Rounds so far", n.on_floor.rounds)));
  box.append(el("div", {className: "stats"},
    stat("Visits", n.visits), stat("Rounds", n.rounds), stat("Staked", money(n.wagered)), stat("Returned", money(n.returned)),
    stat("Net", signed(n.net), n.net > 0 ? "pos" : n.net < 0 ? "neg" : ""), stat("Best visit", money(n.biggest_win)), stat("Busts", n.busts),
    stat("Last seen", n.last_seen ? new Date(n.last_seen * 1000).toLocaleString([], {dateStyle: "short", timeStyle: "short"}) : "—")));
  const visitsBox = el("div", {}, el("p", {className: "hint", textContent: "Loading visits…"}));
  box.append(visitsBox);
  H.api("GET", "/api/npcs/" + n.id).then(full => {
    if (!full.visits.length) { visitsBox.replaceChildren(el("p", {className: "hint", textContent: "No visits yet."})); return; }
    const REASONS = {bust: "went bust", done: "done for the day", hit_and_run: "left while ahead", riches: "doubled up", admin: "sent home", shutdown: "closing time", npcs_off: "NPCs switched off"};
    visitsBox.replaceChildren(el("table", {}, el("thead", {}, el("tr", {}, ...["When", "Stayed", "Budget", "Left with", "Net", "Rounds", "Why"].map((h, i) => el("th", {className: i >= 2 && i <= 5 ? "num" : "", textContent: h})))),
      el("tbody", {}, ...full.visits.map(v => el("tr", {},
        el("td", {textContent: new Date(v.arrived * 1000).toLocaleString([], {dateStyle: "short", timeStyle: "short"})}),
        el("td", {textContent: Math.max(1, Math.round((v.left_at - v.arrived) / 60)) + " min"}),
        el("td", {className: "num", textContent: money(v.budget)}), el("td", {className: "num", textContent: money(v.end_bankroll)}),
        el("td", {className: "num " + (v.net > 0 ? "pos" : v.net < 0 ? "neg" : ""), textContent: signed(v.net)}),
        el("td", {className: "num", textContent: v.rounds}), el("td", {textContent: REASONS[v.reason] || v.reason}))))));
  }).catch(() => {});
}

// ------------------------------------------------------------ bulk create
// Generate a batch of random drafts (names, looks; a style and traits if seeded), review and tweak them, then create
// them all at once. The batch survives a trip back to the roster.
let bulkOn = false, batch = [], bulkKey = 0;
const setup = {count: 10, role: "punter", archetype: "mix", body: "", traits: [], enabled: true};
function bulkMode(on) {
  bulkOn = on; selected = null; draft = null;
  $("#roster").hidden = on; $("#bulk").hidden = !on;
  for (const id of ["#npc-role", "#npc-search", "#npc-new", "#npc-count"]) $(id).hidden = on;
  $("#npc-bulk").textContent = on ? "Back to the roster" : "Bulk create";
  if (on) renderBulk();
  else if (list.length) { select(list.find(n => n.role === "punter") || list[0]); return; }
  renderEditor();
}
const roleLabel = (role, n) => { const l = (opts.roles[role] || role).toLowerCase(); return n === 1 ? l : l.endsWith("s") ? l + "es" : l + "s"; };
function genLabel() {
  const s = setup, who = (s.role === "punter" && s.archetype !== "mix" ? opts.archetypes[s.archetype].label.toLowerCase() + " " : "") + roleLabel(s.role, s.count);
  return (batch.length ? "Add " : "Generate ") + s.count + " " + who;
}
function toggles(entries, isOn, flip) {   // a row of pressable buttons
  return el("div", {className: "seg wrap"}, ...entries.map(([k, label, about]) => {
    const b = el("button", {type: "button", textContent: label, title: about || "", ariaPressed: String(isOn(k))});
    b.addEventListener("click", () => flip(k));
    return b;
  }));
}
function renderBulk() {
  const box = $("#bulk"), s = setup, punter = s.role === "punter";
  const field = (label, input) => el("label", {className: "field"}, el("span", {textContent: label}), input);
  const gen = el("button", {type: "button", className: "primary", id: "bulk-generate", textContent: genLabel()});
  gen.addEventListener("click", () => generate(gen));
  const count = el("input", {type: "number", id: "bulk-count", min: 1, max: 30, step: 1, value: s.count});
  count.addEventListener("input", () => { s.count = Math.max(1, Math.min(30, Math.round(+count.value || 1))); gen.textContent = genLabel(); });
  const role = el("select", {id: "bulk-role"}, ...Object.entries(opts.roles).map(([k, v]) => el("option", {value: k, textContent: v + (opts.on_the_floor.includes(k) ? "" : " (not on the floor yet)"), selected: k === s.role})));
  role.addEventListener("change", () => { s.role = role.value; renderBulk(); });
  const style = el("select", {id: "bulk-style"}, el("option", {value: "mix", textContent: "A mix"}),
    ...Object.entries(opts.archetypes).map(([k, a]) => el("option", {value: k, textContent: a.label, selected: k === s.archetype})));
  style.addEventListener("change", () => { s.archetype = style.value; gen.textContent = genLabel(); });
  const enabled = el("input", {type: "checkbox", id: "bulk-enabled", checked: s.enabled});
  enabled.addEventListener("change", () => { s.enabled = enabled.checked; });
  const card = el("div", {style: "padding: var(--pad); display: grid; gap: var(--gap); border-bottom: 1px solid var(--line)"},
    el("div", {className: "grid2", style: "grid-template-columns: 120px repeat(2, minmax(0, 1fr))"}, field("How many (1-30)", count), field("Role", role), punter ? field("Style", style) : el("span")),
    el("div", {className: "field"}, el("span", {textContent: "Body"}),
       toggles([["", "Mixed"], ["female", "Female"], ["male", "Male"]], k => s.body === k, k => { s.body = k; renderBulk(); })),
    punter ? el("div", {className: "field"}, el("span", {textContent: "Traits for everyone (add them per person below too)"}),
       toggles(Object.entries(opts.modifiers).map(([k, m]) => [k, m.label, m.about]), k => s.traits.includes(k),
               k => { s.traits = s.traits.includes(k) ? s.traits.filter(t => t !== k) : [...s.traits, k]; renderBulk(); })) : null,
    el("div", {className: "controls"}, gen, el("label", {className: "controls hint"}, enabled, "In service (", punter ? "visits the casino" : "works shifts", ")")));
  box.replaceChildren(el("div", {className: "ph", textContent: "Bulk create"}), card, el("div", {id: "bulk-review"}));
  renderBulkList();
}
async function generate(btn) {
  btn.disabled = true; H.status("Generating…");
  try {
    const r = await H.api("POST", "/api/npcs/generate", {...setup, taken: batch.map(d => d.name)});
    for (const d of r.drafts) batch.push({...d, archetype: d.archetype || "casual", key: ++bulkKey});
    H.status(`Added ${r.drafts.length} to the batch. Nothing's saved till you create them.`, "ok");
  } catch (e) { H.status(e.message, "warn"); }
  btn.disabled = false; renderBulk();
}
const luckyNumbers = () => { const s = new Set(); const n = 2 + Math.floor(Math.random() * 3); while (s.size < n) s.add(Math.floor(Math.random() * 37)); return [...s].sort((a, b) => a - b); };
function addTrait(d, t) {
  if (d.role !== "punter" || d.traits.includes(t)) return;
  d.traits = [...d.traits, t];
  if (t === "superstitious" && !(d.settings.lucky_numbers || []).length) d.settings.lucky_numbers = luckyNumbers();
}
function changed(d) { if (draft === d) renderEditor(); else renderBulkList(); }   // renderEditor redraws the list too
async function reroll(d, what) {
  try {
    const r = await H.api("POST", "/api/npcs/generate", {count: 1, role: d.role, body: d.look.body, taken: batch.map(x => x.name)});
    const fresh = r.drafts[0];
    if (what === "name") d.name = fresh.name;
    else { d.look = fresh.look; d.look_url = fresh.look_url; if (draft === d) previewUrl = d.look_url; }
    changed(d);
  } catch (e) { H.status(e.message, "warn"); }
}
function removeDraft(d) {
  batch = batch.filter(x => x !== d);
  if (draft === d) { draft = null; renderEditor(); }
  renderBulk();
}
function tweak(d) { draft = d; previewUrl = d.look_url; renderEditor(); }
function bulkRow(d) {
  const name = el("input", {value: d.name, maxLength: 24, placeholder: "Name", ariaLabel: "Name"});
  name.addEventListener("input", () => { d.name = name.value; });
  name.addEventListener("change", () => { if (draft === d) renderEditor(); });
  const tags = [el("span", {className: "tag", textContent: opts.roles[d.role] || d.role})];
  if (d.role === "punter") {
    const style = el("select", {ariaLabel: "Style for " + d.name}, ...Object.entries(opts.archetypes).map(([k, a]) => el("option", {value: k, textContent: a.label, selected: k === d.archetype})));
    style.addEventListener("change", () => { d.archetype = style.value; changed(d); });
    tags.push(style);
    for (const t of d.traits) {
      const x = el("button", {type: "button", textContent: "✕", title: "Drop " + opts.modifiers[t].label, ariaLabel: "Drop " + opts.modifiers[t].label + " from " + d.name});
      x.addEventListener("click", () => { d.traits = d.traits.filter(y => y !== t); changed(d); });
      tags.push(el("span", {className: "tag gold"}, opts.modifiers[t].label, x));
    }
    const add = el("select", {ariaLabel: "Add a trait to " + d.name}, el("option", {value: "", textContent: "+ trait"}),
      ...Object.entries(opts.modifiers).filter(([k]) => !d.traits.includes(k)).map(([k, m]) => el("option", {value: k, textContent: m.label})));
    add.addEventListener("change", () => { if (add.value) { addTrait(d, add.value); changed(d); } });
    tags.push(add);
  }
  const btn = (label, title, fn) => el("button", {type: "button", textContent: label, title, onclick: fn});
  return el("div", {className: "npc-b" + (draft === d ? " sel" : "") + (d.enabled ? "" : " off")},
    thumb(d.look_url),
    el("div", {className: "who"}, name, el("div", {className: "badges"}, ...tags)),
    el("div", {className: "row-acts"},
      btn("↻ Name", "A different random name", () => reroll(d, "name")),
      btn("↻ Look", "A different random look", () => reroll(d, "look")),
      btn("Tweak", "Open in the editor", () => tweak(d)),
      btn("✕", "Remove from the batch", () => removeDraft(d))));
}
function renderBulkList() {
  const box = H.view.querySelector("#bulk-review");
  if (!box) return;
  if (!batch.length) { box.replaceChildren(el("p", {className: "empty", textContent: "The batch is empty: generate some above (you can add several batches, e.g. 10 casual punters, then 5 dealers)."})); return; }
  const punters = batch.filter(d => d.role === "punter");
  const bar = el("div", {className: "ph"}, el("b", {textContent: "Review · " + batch.length}), el("span", {className: "grow"}));
  if (punters.length) {
    const trait = el("select", {id: "bulk-all-trait", ariaLabel: "Trait"}, ...Object.entries(opts.modifiers).map(([k, m]) => el("option", {value: k, textContent: m.label})));
    const addAll = el("button", {type: "button", textContent: "Add to every punter"});
    addAll.addEventListener("click", () => { punters.forEach(d => addTrait(d, trait.value)); draft ? renderEditor() : renderBulkList(); });
    const dropAll = el("button", {type: "button", textContent: "Drop from all"});
    dropAll.addEventListener("click", () => { punters.forEach(d => { d.traits = d.traits.filter(t => t !== trait.value); }); draft ? renderEditor() : renderBulkList(); });
    const style = el("select", {ariaLabel: "Style for every punter"}, el("option", {value: "", textContent: "Every punter's style…"}),
      ...Object.entries(opts.archetypes).map(([k, a]) => el("option", {value: k, textContent: a.label})));
    style.addEventListener("change", () => { if (style.value) { punters.forEach(d => { d.archetype = style.value; }); draft ? renderEditor() : renderBulkList(); } });
    bar.append(trait, addAll, dropAll, style);
  }
  const create = el("button", {type: "button", className: "primary", id: "bulk-create", textContent: `Create ${batch.length === 1 ? "1 NPC" : batch.length + " NPCs"}`});
  create.addEventListener("click", () => createAll(create));
  const discard = el("button", {type: "button", className: "ghost", textContent: "Discard batch"});
  discard.addEventListener("click", () => {
    const y = el("button", {type: "button", className: "primary", textContent: "Yes"}), n = el("button", {type: "button", textContent: "No"});
    discard.replaceWith(el("span", {className: "confirm"}, "Throw away all " + batch.length + "?", y, n));
    y.addEventListener("click", () => { batch = []; draft = null; renderEditor(); renderBulk(); });
    n.addEventListener("click", renderBulkList);
  });
  box.replaceChildren(bar, ...batch.map(bulkRow), el("div", {className: "controls", style: "padding: var(--pad)"}, create, discard));
}
async function createAll(btn) {
  btn.disabled = true;
  try {
    const npcs = batch.map(({key, look_url, ...d}) => ({...d, settings: Object.fromEntries(Object.entries(d.settings || {}).filter(([, v]) => v !== undefined && v !== ""))}));
    const r = await H.api("POST", "/api/npcs/bulk", {npcs});
    batch = [];
    await refresh();
    bulkMode(false);
    H.status(`Created ${r.npcs.length === 1 ? "1 NPC" : r.npcs.length + " NPCs"}: ${r.npcs.map(n => n.name).join(", ")}.`, "ok");
  } catch (e) { btn.disabled = false; H.status(e.message, "warn"); }
}

async function saveDraft() {
  try {
    const body = {...draft, settings: Object.fromEntries(Object.entries(draft.settings).filter(([, v]) => v !== undefined && v !== ""))};
    const saved = selected ? await H.api("PUT", "/api/npcs/" + selected.id, body) : await H.api("POST", "/api/npcs", body);
    H.status((selected ? "Saved " : "Created ") + saved.name + ".", "ok");
    await refresh();
    select(list.find(n => n.id === saved.id));
  } catch (e) { H.status(e.message, "warn"); }
}
async function act(what, message) {
  try { await H.api("POST", `/api/npcs/${selected.id}/${what}`); H.status(message, "ok"); await refresh(); renderEditor(); }
  catch (e) { H.status(e.message, "warn"); }
}
async function deleteNpc() {
  try { await H.api("DELETE", "/api/npcs/" + selected.id); H.status("Deleted " + selected.name + ".", "ok"); selected = null; draft = null; await refresh(); renderEditor(); }
  catch (e) { H.status(e.message, "warn"); }
}
