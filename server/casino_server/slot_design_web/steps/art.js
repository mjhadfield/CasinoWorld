// Step 2, Art: a section per category (with how many the main game needs) and a card per symbol. Cycle the takes,
// pick a frame colour, tick the final set, link references, Reiterate, Refine, Fit, and bin what's not wanted.
// Polling only redraws cards that changed, and never one you're typing in or saving: that card is left behind
// (behind(), which keeps the wizard polling) and catches up once you've left it.
const HUE = {gold: "#d39a26", red: "#d0562e", blue: "#3a7be0", purple: "#9550d8", silver: "#9aa4b2", green: "#3fae4c"};
let C, filter = "all", lastDid = null;
const rows = new Map();     // symbol id -> {card, json, behind}
const cats = new Map();     // category id -> {list, box, count, need}
const drafts = new Map();   // category id -> New forms not yet added (they stack)
const open = new Map();     // symbol id -> which tool panel is open (refine | fit | bin)
const timers = {};
const saving = new Map();   // symbol id -> PATCHes in flight
let els = {};

const sym = sid => `/api/slot-design/${C.did}/symbols/${encodeURIComponent(sid)}`;
const thumbOf = (s, w) => w.hues ? (w.hues[s.hue] || Object.values(w.hues)[0]) : w.src;

export function render(ctx, body) {
  C = ctx;
  const {el} = C;
  rows.clear(); cats.clear();
  if (C.did !== lastDid) { drafts.clear(); open.clear(); lastDid = C.did; }
  els.sum = el("div", {className: "dz-sum"});
  els.gen = el("button", {type: "button", className: "primary", onclick: generate});
  els.board = el("div");
  const seg = el("span", {className: "seg", role: "group", ariaLabel: "Show"},
    ...[["all", "All"], ["keep", "In set"], ["open", "Not in set"], ["marked", "Marked"]].map(([f, t]) =>
      el("button", {type: "button", textContent: t, ariaPressed: String(f === filter), onclick: e => {
        filter = f;
        for (const b of seg.children) b.ariaPressed = String(b === e.currentTarget);
        for (const s of C.data.symbols) { const r = rows.get(s.id); if (r) r.card.hidden = !visible(s); }
      }})));
  body.append(
    el("p", {className: "lead", textContent: "Pick each symbol's best take and tick it into the final set. Reiterate makes three fresh takes; Refine changes one thing on a take and keeps the rest; Fit rescales or nudges a take (no FLUX). ✕ moves a take to the Bin, where it can be restored. Generate sends everything marked to FLUX."}),
    el("div", {className: "dz-bar"}, seg, el("span", {className: "grow"}), els.gen),
    els.sum, el("p", {className: "hint", textContent: C.data.note || ""}), els.board);
  draw(true);
}

export function update(ctx, force) { C = ctx; draw(false, force); }

// Is a card showing older data than the last load? The wizard keeps refreshing until it isn't.
export const behind = () => [...rows.values()].some(r => r.behind);

const countTag = c => C.el("span", {
  className: "tag " + (c.required == null ? "" : c.in_set === c.required ? "ok" : c.in_set > c.required ? "warn" : "gold"),
  textContent: c.required == null ? `${c.count} designed` : `${c.in_set} of ${c.required} in set · ${c.count} to choose from`});

function visible(s) {
  return filter === "all" || (filter === "keep" && s.keep) || (filter === "open" && !s.keep)
    || (filter === "marked" && (s.reiterate || s.pending_new || !!s.job));
}

function draw(full, force) {
  const {el} = C, d = C.data;
  els.sum.replaceChildren(...d.categories.map(c => el("button", {type: "button", title: "Go to " + c.title,
    onclick: () => document.getElementById("dz-cat-" + c.id).scrollIntoView({behavior: "smooth"})}, c.title + " ", countTag(c))));
  els.gen.textContent = d.pending ? `Generate (${d.pending})` : "Generate";
  els.gen.disabled = !d.pending;
  els.gen.title = d.pending ? "Make three takes of every symbol marked Reiterate or newly added" : "Mark a symbol Reiterate, or add a New one, first";
  if (full || !cats.size) {
    rows.clear(); cats.clear();
    els.board.replaceChildren(...d.categories.map(c => {
      const list = el("div", {className: "pane"}), box = el("div", {className: "pane"}, ...(drafts.get(c.id) || []));
      // Tier-shaped categories take their count from the Concept step's tier shape; the rest are set here.
      const shaped = !!c.role;
      const need = el("input", {type: "number", min: 0, max: 30, value: c.required ?? "", placeholder: "—", disabled: shaped,
        title: shaped ? "Set by the tier shape on the Concept step" : "", ariaLabel: `${c.title}: how many the main game needs`});
      need.addEventListener("change", async () => {
        try {
          await C.api("PATCH", `/api/slot-design/${C.did}/categories/${c.id}`, {required: need.value === "" ? null : +need.value});
          await C.refresh();
        } catch (e) { C.status(e.message, "warn"); }
      });
      const count = countTag(c);
      cats.set(c.id, {list, box, count, need});
      return el("div", {className: "dz-cat", id: "dz-cat-" + c.id},
        el("h2", {}, el("span", {textContent: c.title}), count, el("label", {}, "Needed", need)),
        list, box,
        el("div", {}, el("button", {type: "button", textContent: "＋ New", title: `Add a symbol to ${c.title}`, onclick: () => {
          const f = draftForm(c);
          drafts.set(c.id, [...(drafts.get(c.id) || []), f]);
          box.append(f);
          f.querySelector("input").focus();
        }})));
    }));
  }
  for (const c of d.categories) {
    const cat = cats.get(c.id);
    if (!cat) continue;
    const count = countTag(c);
    cat.count.replaceWith(count);
    cat.count = count;
    if (document.activeElement !== cat.need) cat.need.value = c.required ?? "";
    for (const s of d.symbols.filter(x => x.category === c.id)) {
      const json = JSON.stringify(s), row = rows.get(s.id);
      if (!row) {
        const card = symRow(s);
        cat.list.append(card);
        rows.set(s.id, {card, json});
      } else if (s.id === force || row.json !== json) {
        row.behind = s.id !== force && (row.card.contains(document.activeElement) || !!saving.get(s.id));
        if (!row.behind) {
          const card = symRow(s);
          row.card.replaceWith(card);
          rows.set(s.id, {card, json});
        }
      }
      rows.get(s.id).card.hidden = !visible(s);
    }
  }
  for (const [sid, row] of rows) {
    if (!d.symbols.some(s => s.id === sid)) { row.card.remove(); rows.delete(sid); }
  }
}

// Redraw one card from the data already loaded (opening or closing a tool panel needs no fetch).
function redraw(sid) {
  const s = C.data.symbols.find(x => x.id === sid), row = rows.get(sid);
  if (!s || !row) return;
  const card = symRow(s);
  row.card.replaceWith(card);
  rows.set(sid, {card, json: JSON.stringify(s)});
}

async function generate() {
  try {
    const r = await C.api("POST", `/api/slot-design/${C.did}/generate`);
    C.status(`Queued ${r.queued} job${r.queued === 1 ? "" : "s"}: three takes each. They appear here as FLUX finishes them.`, "ok");
    await C.refresh();
  } catch (e) { C.status(e.message, "warn"); }
}

async function patch(s, body, redraw = true) {
  saving.set(s.id, (saving.get(s.id) || 0) + 1);
  try { await C.api("PATCH", sym(s.id), body); }
  catch (e) { return C.status(e.message, "warn"); }
  finally { saving.set(s.id, saving.get(s.id) - 1); }
  if (redraw) await C.refresh(s.id).catch(e => C.status(e.message, "warn"));
}

// A text box that saves half a second after you stop typing, and at once when you leave it.
function typed(s, field, box) {
  const key = field + ":" + s.id;
  const save = () => { clearTimeout(timers[key]); timers[key] = null; patch(s, {[field]: box.value}, false); };
  box.addEventListener("input", () => { clearTimeout(timers[key]); timers[key] = setTimeout(save, 500); });
  box.addEventListener("change", () => { if (timers[key]) save(); });
}

async function act(s, action, body, msg) {
  try {
    const r = await C.api("POST", `${sym(s.id)}/${action}`, body);
    if (msg) C.status(msg, "ok");
    await C.refresh(s.id);
    return r;
  } catch (e) { C.status(e.message, "warn"); }
}

// Everything that can be linked as a reference: each symbol's chosen art, every linked reference, and the sheets.
const boardImages = () => [
  ...C.data.symbols.filter(s => s.file).map(s => [`${s.name}: chosen art`, s.file]),
  ...C.data.symbols.flatMap(s => s.refs.map((r, k) => [`${s.name}: reference ${k + 1}`, r])),
  ...C.data.sources.map(p => [`Sheet: ${p.split("/")[1]}`, p])];

// Upload a file, fetch a web address, or pick art already on the board; onPath gets the board path.
export function linker(ctx, onPath) {
  const {el, api, status} = ctx;
  const file = el("input", {type: "file", accept: "image/png,image/jpeg,image/webp", ariaLabel: "Upload a reference image"});
  const url = el("input", {type: "url", placeholder: "https://… an image's address", ariaLabel: "Image address"});
  const pick = el("select", {ariaLabel: "Art already on the board"}, el("option", {value: "", textContent: "Art already on the board…"}),
    ...(C ? boardImages() : []).map(([label, path]) => el("option", {value: path, textContent: label})));
  const take = async fn => { try { await onPath((await fn()).path); } catch (e) { status(e.message, "warn"); } };
  file.addEventListener("change", () => {
    const f = file.files[0];
    if (f) take(async () => api("PUT", `/api/slot-design/${ctx.did}/links/${encodeURIComponent(f.name)}`, await f.arrayBuffer(), true)).then(() => { file.value = ""; });
  });
  return el("div", {className: "dz-link"},
    el("div", {className: "controls"}, file),
    el("div", {className: "controls"}, url, el("button", {type: "button", textContent: "Fetch",
      onclick: () => url.value && take(() => api("POST", `/api/slot-design/${ctx.did}/links`, {url: url.value}))})),
    el("div", {className: "controls"}, pick, el("button", {type: "button", textContent: "Link",
      onclick: () => pick.value && onPath(pick.value)})));
}

function jobBits(s) {
  const {el} = C, j = s.job;
  if (!j) return [];
  const text = {queued: "Queued", waiting: "Waiting for FLUX", running: `Making ${j.done + 1} of ${j.count}`, failed: "Failed"}[j.status];
  const go = (method, tail) => async () => {
    try { await C.api(method, `/api/slot-design/${C.did}/jobs/${j.id}${tail}`); await C.refresh(s.id); }
    catch (e) { C.status(e.message, "warn"); }
  };
  return [el("span", {className: "tag " + (j.status === "failed" ? "warn" : "gold"), textContent: (j.action === "refine" ? "Refine: " : "") + text, title: j.error || ""}),
    j.status === "failed" ? el("button", {type: "button", textContent: "Retry", onclick: go("POST", "/retry")}) : null,
    j.status !== "running" ? el("button", {type: "button", textContent: "Cancel", onclick: go("DELETE", "")}) : null];
}

function symRow(s) {
  const {el} = C;
  const vs = s.variants, i = Math.max(0, vs.findIndex(v => v.id === s.choice)), v = vs[i];
  const choose = d => vs[i + d] && patch(s, {choice: vs[i + d].id});
  const tool = open.get(s.id);
  const toggle = name => () => { open.set(s.id, tool === name ? null : name); redraw(s.id); };

  const view = el("div", {className: "dz-view"},
    el("div", {className: "dz-big"}, v ? el("img", {src: C.img(s.file), alt: `${s.name}: ${v.label}`})
        : el("span", {className: "hint", textContent: s.pending_new ? "New: press Generate" : "No art yet"}),
      v ? el("span", {className: "lbl" + (v.fav ? " fav" : ""), textContent: (v.fav ? "★ " : "") + v.label}) : null),
    el("div", {className: "dz-nav"},
      el("button", {type: "button", className: "icon", textContent: "◀", disabled: i <= 0, ariaLabel: "Previous take", onclick: () => choose(-1)}),
      el("span", {textContent: `${vs.length ? i + 1 : 0} / ${vs.length}`}),
      el("button", {type: "button", className: "icon", textContent: "▶", disabled: i >= vs.length - 1, ariaLabel: "Next take", onclick: () => choose(1)})),
    v && v.hues ? el("div", {className: "swatches", role: "group", ariaLabel: "Frame colour"}, ...Object.keys(v.hues).map(h =>
      el("button", {type: "button", className: "sw", title: h + " frame", ariaLabel: h + " frame", ariaPressed: String(h === s.hue),
        style: `background:${HUE[h] || "#888"}`, onclick: () => patch(s, {hue: h})}))) : null,
    v ? el("div", {className: "dz-tools"},
      el("button", {type: "button", textContent: "Refine", ariaPressed: String(tool === "refine"), onclick: toggle("refine")}),
      el("button", {type: "button", textContent: "Fit", ariaPressed: String(tool === "fit"), onclick: toggle("fit")})) : null);

  const head = el("div", {className: "card-head"}, el("h3", {textContent: s.name}),
    el("span", {className: "tag", textContent: s.kind === "character" ? "character · framed" : "object"}),
    s.pending_new ? el("span", {className: "tag gold", textContent: "new · waiting for Generate"}) : null, ...jobBits(s),
    el("label", {className: "confirm", style: "margin-left:auto"},
      el("input", {type: "checkbox", checked: s.keep, onchange: e => patch(s, {keep: e.target.checked})}), "In final set"),
    s.binned.length ? el("button", {type: "button", textContent: `Bin (${s.binned.length})`, ariaPressed: String(tool === "bin"), onclick: toggle("bin")}) : null,
    s.added ? el("button", {type: "button", textContent: "Remove", onclick: async () => {
      if (!confirm(`Remove ${s.name} from the board? Its images stay in the design folder.`)) return;
      try { await C.api("DELETE", sym(s.id)); await C.refresh(); } catch (e) { C.status(e.message, "warn"); }
    }}) : null);

  const strip = el("div", {className: "dz-strip"}, ...vs.map((w, j) => el("span", {className: "dz-take"},
    el("button", {type: "button", title: w.label, ariaPressed: String(j === i), onclick: () => patch(s, {choice: w.id})},
      el("img", {src: C.img(thumbOf(s, w)), alt: w.label, loading: "lazy"})),
    el("button", {type: "button", className: "x", textContent: "✕", title: "Move to the Bin", ariaLabel: `Bin ${w.label}`,
      onclick: () => act(s, "bin", {variant: w.id}, `${w.label} is in ${s.name}'s Bin.`)}))));

  const panel = tool === "refine" && v ? refinePanel(s, v) : tool === "fit" && v ? fitPanel(s, v)
    : tool === "bin" ? binPanel(s) : null;

  const linkBox = linker(C, path => patch(s, {add_ref: path}));
  linkBox.hidden = true;
  const refs = el("div", {className: "dz-refs"}, "References",
    ...s.refs.map((r, k) => el("span", {className: "dz-ref"},
      el("a", {href: C.img(r), target: "_blank", title: "Open full size"}, el("img", {src: C.img(r), alt: `Reference ${k + 1}`, loading: "lazy"})),
      k > 0 || s.added ? el("button", {type: "button", textContent: "✕", title: "Unlink", ariaLabel: `Unlink reference ${k + 1}`,
        onclick: () => patch(s, {remove_ref: r})}) : null)),
    el("button", {type: "button", textContent: "＋ Link image", onclick: () => { linkBox.hidden = !linkBox.hidden; }}));

  const note = el("textarea", {rows: 2, value: s.note || "", disabled: !s.reiterate, ariaLabel: `What to change on ${s.name}`,
    placeholder: "What to change (optional), e.g. 'more gold trim, less glow'"});
  typed(s, "note", note);
  const base = el("select", {disabled: !s.reiterate, ariaLabel: "Start the new takes from"},
    el("option", {value: "", textContent: "From the chosen take"}),
    ...s.refs.map((r, k) => el("option", {value: r, textContent: `From reference ${k + 1}`})));
  base.value = s.base || "";
  base.addEventListener("change", () => patch(s, {base: base.value || null}));
  const re = el("div", {className: "dz-re"}, el("div", {className: "controls"},
    el("label", {className: "confirm"}, el("input", {type: "checkbox", checked: s.reiterate,
      onchange: e => patch(s, {reiterate: e.target.checked})}), "Reiterate: make 3 more takes"), base), note);

  let prompt = null;
  if (s.added || s.prompt) {
    prompt = el("textarea", {rows: 2, value: s.prompt || "", ariaLabel: `Description of ${s.name}`, placeholder: "Describe it for FLUX"});
    typed(s, "prompt", prompt);
  }
  const failed = s.job && s.job.status === "failed" ? el("p", {className: "hint", textContent: "FLUX said: " + s.job.error}) : null;
  const card = el("div", {className: "card dz-sym" + (s.keep ? " keep" : "")}, view,
    el("div", {className: "dz-main"}, head, failed, strip, panel, prompt, refs, linkBox, re));
  card.dataset.sid = s.id;
  return card;
}

function refinePanel(s, v) {
  const {el} = C;
  const text = el("textarea", {rows: 2, ariaLabel: "What to change", placeholder: "One change, e.g. 'make his eyes brown' or 'remove the stray star top left'"});
  return el("div", {className: "dz-panel"},
    el("p", {className: "hint", textContent: `Refine ${v.label}: FLUX keeps everything and changes only what you say. One new take.`}),
    text,
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Refine", onclick: async () => {
      if (!text.value.trim()) return C.status("Say what to change.", "warn");
      open.set(s.id, null);
      await act(s, "refine", {variant: v.id, instruction: text.value}, `Refining ${s.name}: the new take appears when FLUX is done.`);
    }})));
}

function fitPanel(s, v) {
  const {el} = C;
  const f0 = Object.assign({scale: 1, dx: 0, dy: 0, rot: 0}, (s.fits[v.id] || {}).fit);
  const f = {...f0};
  const prev = el("img", {alt: "Fit preview", className: "dz-fitprev"});
  const slider = (key, label, min, max, step, show) => {
    const out = el("output", {textContent: show(f[key])});
    const r = el("input", {type: "range", min, max, step, value: f[key], ariaLabel: label});
    r.addEventListener("input", () => { f[key] = +r.value; out.textContent = show(f[key]); preview(); });
    return el("label", {className: "dz-slider"}, el("span", {textContent: label}), r, out);
  };
  let t = null, n = 0;
  const preview = () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const mine = ++n;
      try {
        const r = await fetch(`${sym(s.id)}/fit-preview`, {method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({variant: v.id, fit: f, hue: s.hue})});
        if (!r.ok) throw new Error(await r.text());
        const url = URL.createObjectURL(await r.blob());
        if (mine === n) { URL.revokeObjectURL(prev.src); prev.src = url; }
      } catch (e) { C.status("Preview failed: " + e.message, "warn"); }
    }, 220);
  };
  preview();
  return el("div", {className: "dz-panel dz-fit"},
    el("div", {className: "dz-big"}, prev),
    el("div", {className: "pane"},
      el("p", {className: "hint", textContent: `Fit ${v.label}: rescale and nudge it in its tile. Saving makes a new take; the original stays.`}),
      slider("scale", "Size", 0.5, 1.6, 0.01, x => Math.round(x * 100) + "%"),
      slider("dx", "Left / right", -160, 160, 1, x => (x > 0 ? "+" : "") + x),
      slider("dy", "Up / down", -160, 160, 1, x => (x > 0 ? "+" : "") + x),
      v.hues ? null : slider("rot", "Rotate", -45, 45, 0.5, x => x + "°"),
      el("div", {className: "controls"},
        el("button", {type: "button", className: "primary", textContent: "Save as a new take", onclick: async () => {
          open.set(s.id, null);
          await act(s, "fit", {variant: v.id, fit: f}, `Saved a fitted take of ${s.name}.`);
        }}),
        el("button", {type: "button", textContent: "Cancel", onclick: () => { open.set(s.id, null); redraw(s.id); }}))));
}

function binPanel(s) {
  const {el} = C;
  return el("div", {className: "dz-panel"},
    el("p", {className: "hint", textContent: "Binned takes. Nothing is deleted: restore any of them."}),
    el("div", {className: "dz-strip"}, ...s.binned.map(w => el("span", {className: "dz-take"},
      el("img", {src: C.img(thumbOf(s, w)), alt: w.label, title: w.label, loading: "lazy"}),
      el("button", {type: "button", textContent: "Restore", onclick: () => act(s, "restore", {variant: w.id}, `${w.label} restored.`)})))));
}

function draftForm(c) {
  const {el} = C;
  let ref = null;
  const name = el("input", {placeholder: "e.g. Shuttlecraft", ariaLabel: "Name"});
  const kind = el("select", {ariaLabel: "Kind"}, el("option", {value: "object", textContent: "Object (cut out)"}),
    el("option", {value: "character", textContent: "Character (in the shared frame)"}));
  kind.value = c.kind || "object";
  const key = el("select", {ariaLabel: "Background to key off"}, el("option", {value: "magenta", textContent: "Magenta (most art)"}),
    el("option", {value: "green", textContent: "Green (purple or pink art)"}));
  const desc = el("textarea", {rows: 2, ariaLabel: "Description", placeholder: "Describe it for FLUX, e.g. 'a Starfleet shuttlecraft, three-quarter view'"});
  const chosen = el("div", {className: "dz-refs"});
  const card = el("div", {className: "card dz-new"},
    el("div", {className: "card-head"}, el("h3", {textContent: "New symbol"}), el("span", {className: "tag", textContent: c.title})),
    el("div", {className: "grid2"},
      el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
      el("label", {className: "field"}, el("span", {textContent: "Kind"}), kind),
      el("label", {className: "field"}, el("span", {textContent: "Background to key off"}), key),
      el("label", {className: "field", style: "grid-column: 1 / -1"}, el("span", {textContent: "Description"}), desc)),
    el("div", {className: "field"}, el("span", {textContent: "Reference image (optional: with one, FLUX redraws it; without, it draws from the description)"}),
      linker(C, path => {
        ref = path;
        chosen.replaceChildren("Reference", el("span", {className: "dz-ref"}, el("img", {src: C.img(path), alt: "Reference"}),
          el("button", {type: "button", textContent: "✕", ariaLabel: "Drop the reference", onclick: () => { ref = null; chosen.replaceChildren(); }})));
      }), chosen),
    el("div", {className: "controls"},
      el("button", {type: "button", className: "primary", textContent: "Add to " + c.title, onclick: async () => {
        try {
          await C.api("POST", `/api/slot-design/${C.did}/symbols`, {name: name.value, category: c.id, kind: kind.value, key: key.value, prompt: desc.value, ref});
          C.status(`${name.value} added: Generate makes three takes.`, "ok");
          discard();
          await C.refresh();
        } catch (e) { C.status(e.message, "warn"); }
      }}),
      el("button", {type: "button", textContent: "Discard", onclick: () => discard()})));
  function discard() { card.remove(); drafts.set(c.id, (drafts.get(c.id) || []).filter(f => f !== card)); }
  return card;
}
