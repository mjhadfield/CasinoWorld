// Step 2, Art: every symbol as a tile on the left, a section per category (with how many the main game needs), and the
// picked symbol's card on the right. On the card: cycle the takes, pick a frame colour (a character's frame, a royal's
// colour) or a special's word, tick the final set, link references, Reiterate (1, 3 or 5 takes), Refine, Fit, bin what's
// not wanted, change a symbol's kind, move it to another section, and hide symbols not in use (Show › Hidden brings
// them back). The top bar has the Show filter, Prompts (a dialog: how many takes a new symbol's first Generate makes,
// the style prompts and the shared lettering), Hide unused, Cancel all and Generate.
// Polling redraws the card only when it changed, and never while you're typing in it or saving: it's left behind
// (behind(), which keeps the wizard polling) and catches up once you've left it.
const HUE = {gold: "#d39a26", red: "#d0562e", blue: "#3a7be0", purple: "#9550d8", silver: "#9aa4b2", green: "#3fae4c"};
const KINDS = [["object", "Object · cut out"], ["character", "Character · framed"], ["special", "Special · lettered"],
  ["royal", "Royal · drawn rank"]];
let C, filter = "all", lastDid = null;
const rows = new Map();     // the picked symbol's id -> {card, json, behind}
const picked = new Map();   // design id -> the symbol shown, or "new:<category>" for that section's New forms
const drafts = new Map();   // category id -> New forms not yet added (they stack)
const open = new Map();     // symbol id -> which tool panel is open (refine | fit | bin)
const timers = {};
const saving = new Map();   // symbol id -> PATCHes in flight
let els = {};

const sym = sid => `/api/slot-design/${C.did}/symbols/${encodeURIComponent(sid)}`;
const thumbOf = (s, w) => w.hues ? (w.hues[s.hue] || Object.values(w.hues)[0])
  : w.words ? (w.words[s.word] || Object.values(w.words)[0]) : w.src;

// Colour swatches: a character's frame, a royal's colour.
function swatches(current, pick, what) {
  return C.el("div", {className: "swatches", role: "group", ariaLabel: what}, ...Object.keys(HUE).map(h =>
    C.el("button", {type: "button", className: "sw", title: `${h} ${what.toLowerCase()}`, ariaLabel: `${h} ${what.toLowerCase()}`,
      ariaPressed: String(h === current), style: `background:${HUE[h]}`, onclick: () => pick(h)})));
}

// A special's word: the standard ones, or its own (Custom asks for it).
function wordPicker(current, pick) {
  const {el} = C, words = C.data.words, own = current && !words.includes(current);
  return el("span", {className: "seg dz-words", role: "group", ariaLabel: "Word"},
    ...words.map(w => el("button", {type: "button", textContent: w, ariaPressed: String(w === current), onclick: () => pick(w)})),
    el("button", {type: "button", textContent: own ? current : "Custom…", ariaPressed: String(!!own), title: "A word of your own",
      onclick: () => {
        const w = prompt("The word on this special (up to 16 letters):", own ? current : "");
        if (w && w.trim()) pick(w.trim().toUpperCase());
      }}));
}

export function render(ctx, body) {
  C = ctx;
  const {el} = C;
  rows.clear();
  if (C.did !== lastDid) { drafts.clear(); open.clear(); lastDid = C.did; }
  els.gen = el("button", {type: "button", className: "primary", onclick: generate});
  els.stop = el("button", {type: "button", onclick: cancelAll});
  els.tidy = el("button", {type: "button", onclick: hideUnused,
    title: "Hide every symbol that isn't in the final set, on the ladder or followed by an art slot (and isn't marked or being made)"});
  els.prompts = promptsPanel();
  const seg = el("span", {className: "seg", role: "group", ariaLabel: "Show"},
    ...[["all", "All"], ["keep", "In set"], ["open", "Not in set"], ["marked", "Marked"], ["hidden", "Hidden"]].map(([f, t]) =>
      el("button", {type: "button", textContent: t, ariaPressed: String(f === filter), onclick: e => {
        filter = f;
        for (const b of seg.children) b.ariaPressed = String(b === e.currentTarget);
        drawBrowser();
      }})));
  C.tools.append(seg, el("button", {type: "button", textContent: "Prompts…", onclick: () => els.prompts.showModal()}), els.tidy, els.stop, els.gen,
    C.info("Pick each symbol's best take and tick it into the final set. First generate makes 1, 2 or 3 takes in the Prompts styles, from the reference or the description; Reiterate makes 1, 3 or 5 fresh takes from the chosen take; Refine changes one thing on a take and keeps the rest; Fit rescales or nudges a take (no image model); Split moves the take shown into a new symbol. ✕ moves a take to the Bin, where it can be restored. Generate sends everything marked to the image model; a card's Queue sends just that one.", true));
  els.list = el("div", {className: "wz-list"});
  els.detail = el("div", {className: "wz-detail"});
  body.classList.add("split");
  body.style.setProperty("--split", "560px");
  body.append(els.list, els.detail, els.prompts);
  draw(true);
}

// The Prompts fold: the first Generate's take count and every style prompt, saved as you type. Built once per render,
// so polling never touches a box you're typing in.
function promptsPanel() {
  const {el} = C, p = C.data.prompts, def = C.data.default_prompts;
  const save = async body => {
    try { await C.api("PATCH", `/api/slot-design/${C.did}/prompts`, body); await C.refresh(); }
    catch (e) { C.status(e.message, "warn"); }
  };
  const summaryText = () => `Prompts · a new symbol's first Generate makes ${C.data.prompts.first_takes}`
    + ` take${C.data.prompts.first_takes === 1 ? "" : "s"}`;
  const summary = el("b", {textContent: summaryText()});
  const first = el("span", {className: "seg", role: "group", ariaLabel: "Takes on a new symbol's first Generate"},
    ...[1, 2, 3].map(n => el("button", {type: "button", textContent: String(n), ariaPressed: String(n === p.first_takes),
      onclick: async e => {
        for (const b of first.children) b.ariaPressed = String(b === e.currentTarget);
        await save({first_takes: n});
        summary.textContent = summaryText();
      }})));
  // One box per prompt: saves 500 ms after typing stops; emptied, or Default, goes back to the built-in prompt.
  const box = (label, value, dflt, body, rows = 2) => {
    const ta = el("textarea", {rows, value, ariaLabel: label});
    const reset = el("button", {type: "button", textContent: "Default", title: "Put the built-in prompt back",
      disabled: value === dflt, onclick: () => { ta.value = dflt; send(); }});
    let timer = null;
    const send = () => {
      clearTimeout(timer); timer = null;
      if (!ta.value.trim()) ta.value = dflt;
      reset.disabled = ta.value.trim() === dflt;
      save(body(ta.value));
    };
    ta.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(send, 500); reset.disabled = false; });
    ta.addEventListener("change", () => { if (timer) send(); });
    return el("div", {className: "wz-sec"},
      el("div", {className: "controls"}, el("span", {className: "hint", textContent: label}), el("span", {className: "grow"}), reset), ta);
  };
  const take = (k, i, what) => box(`Take ${i + 1} · ${what}`, p[k][i], def[k][i], v => ({[k]: {[i]: v}}));
  const d = el("dialog", {className: "wz-prompts"},
    el("div", {className: "ph"}, summary, el("span", {className: "grow"}), el("button", {type: "button", textContent: "Done", onclick: () => d.close()})),
    el("div", {className: "pb padded dz-prompts"},
    el("div", {className: "controls"}, el("span", {textContent: "Takes on a new symbol's first Generate"}), first),
    el("p", {className: "hint", textContent: "Take 1 uses style 1, take 2 style 2, take 3 style 3; a Reiterate of 5 goes round again. The theme (Concept), the keep-text, the note and the flat background to key out are added around these. Reiterate's variations and Refine have their own fixed wording."}),
    el("div", {className: "wz-sec"}, el("h4", {textContent: "From a reference (a sheet cut or a linked picture)"}),
      ...[0, 1, 2].map(i => take("redraw", i, "redraw instruction"))),
    el("div", {className: "wz-sec"}, el("h4", {textContent: "From a description only (a New symbol without a reference)"}),
      ...[0, 1, 2].map(i => take("text", i, "style words, after the description"))),
    el("div", {className: "wz-sec"}, el("h4", {textContent: "Characters (every take)"}),
      box("Portrait style: the character is drawn as …", p.bust, def.bust, v => ({bust: v}), 4)),
    el("div", {className: "wz-sec"}, el("h4", {textContent: "Specials (every take)"}),
      box("Emblem style: drawn with no words, the code lays the word on in the lettering below", p.special, def.special, v => ({special: v}), 3)),
    el("div", {className: "wz-sec"}, el("h4", {textContent: "Royals (every take)"}),
      box("Repaint: the image model is given the rank drawn in the royal font and its colour, and told …", p.royal, def.royal, v => ({royal: v}), 3)),
    letteringPanel(save)));
  return d;
}

// The shared lettering: the specials' font and colours, the royals' font, with a live sample (saved on change).
function letteringPanel(save) {
  const {el} = C, l = {...C.data.lettering};
  const sample = el("img", {className: "dz-letters", alt: "Lettering sample: the specials' words, then the royals as the image model gets them"});
  let t = null, n = 0;
  const preview = () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const mine = ++n;
      try {
        const r = await fetch(`/api/slot-design/${C.did}/lettering-preview`, {method: "POST",
          headers: {"Content-Type": "application/json"}, body: JSON.stringify(l)});
        if (!r.ok) throw new Error(await r.text());
        const url = URL.createObjectURL(await r.blob());
        if (mine === n) { URL.revokeObjectURL(sample.src); sample.src = url; }
      } catch (e) { C.status("Lettering preview failed: " + e.message, "warn"); }
    }, 200);
  };
  const set = (k, v) => { l[k] = v; preview(); save({lettering: {[k]: v}}); };
  const font = k => {
    const s = el("select", {ariaLabel: k === "special_font" ? "Specials' font" : "Royals' font"},
      ...C.data.fonts.map(f => el("option", {value: f, textContent: f.replace(/\.[ot]tf$/, "")})));
    s.value = l[k];
    s.addEventListener("change", () => set(k, s.value));
    return s;
  };
  const colour = (k, label) => {
    const i = el("input", {type: "color", value: l[k], ariaLabel: label});
    i.addEventListener("change", () => set(k, i.value));
    return el("label", {className: "field"}, el("span", {textContent: label}), i);
  };
  preview();
  return el("div", {className: "wz-sec"}, el("h4", {textContent: "Lettering (specials' words, royals' ranks)"}),
    el("div", {className: "controls"},
      el("label", {className: "field"}, el("span", {textContent: "Specials' font"}), font("special_font")),
      colour("top", "Top"), colour("bottom", "Bottom"), colour("outline", "Outline"),
      el("label", {className: "field"}, el("span", {textContent: "Royals' font"}), font("royal_font"))),
    el("p", {className: "hint", textContent: "Unset, both fonts are the Sprites step's display font. A special's word is laid on by the code, so every special matches and changing this redoes them all at once (no image model). A royal's rank is drawn in its font and colour before the image model repaints it, so a change here shows on its next takes."}),
    sample);
}

export function update(ctx, force) { C = ctx; draw(false, force); }

// Is a card showing older data than the last load? The wizard keeps refreshing until it isn't.
export const behind = () => [...rows.values()].some(r => r.behind);

const countTag = c => C.el("span", {
  className: "tag " + (c.required == null ? "" : c.in_set === c.required ? "ok" : c.in_set > c.required ? "warn" : "gold"),
  textContent: (c.required == null ? `${c.count} designed` : `${c.in_set} of ${c.required} in set · ${c.count} to choose from`)
    + (c.hidden ? ` · ${c.hidden} hidden` : "")});

function visible(s) {
  if (filter === "hidden" || s.hide) return filter === "hidden" && s.hide;
  return filter === "all" || (filter === "keep" && s.keep) || (filter === "open" && !s.keep)
    || (filter === "marked" && (s.reiterate || s.pending_new || !!s.job));
}

function draw(full, force) {
  const d = C.data;
  els.gen.textContent = d.pending ? `Generate (${d.pending})` : "Generate";
  els.gen.disabled = !d.pending;
  els.gen.title = d.pending ? `Make the takes asked for on every symbol marked Reiterate (${d.prompts.first_takes} for a newly added one)` : "Mark a symbol Reiterate, or add a New one, first";
  els.stop.textContent = `Cancel all (${d.art_jobs})`;
  els.stop.hidden = !d.art_jobs;
  els.stop.title = "Cancel every Art job that's queued, waiting, being made or failed. The picture being drawn now is thrown away.";
  const unused = d.symbols.filter(s => !s.hide && !s.in_use && !s.reiterate && !s.pending_new && !s.job).length;
  els.tidy.textContent = `Hide unused (${unused})`;
  els.tidy.disabled = !unused;
  drawBrowser();
  drawDetail(full, force);
}

// Show a symbol (or a section's New forms, "new:<category>") on the right.
function pick(id) {
  picked.set(C.did, id);
  drawBrowser();
  drawDetail(true);
  els.detail.scrollTop = 0;
}

// The left: each section's tiles, with how many it needs and New.
function drawBrowser() {
  const {el} = C, d = C.data;
  if (els.list.contains(document.activeElement) && document.activeElement.tagName === "INPUT") return;   // typing a Needed count
  const y = els.list.scrollTop, cur = picked.get(C.did);
  els.list.replaceChildren(d.note ? el("p", {className: "hint", style: "padding: 8px var(--pad) 0", textContent: d.note}) : "",
    ...d.categories.flatMap(c => {
      // Tier-shaped categories take their count from the Concept step's tier shape; the rest are set here.
      const shaped = !!c.role;
      const need = el("input", {type: "number", min: 0, max: 30, value: c.required ?? "", placeholder: "—", disabled: shaped,
        title: shaped ? "Set by the tier shape on the Concept step" : "", ariaLabel: `${c.title}: how many the main game needs`});
      need.addEventListener("change", async () => {
        try {
          await C.api("PATCH", `/api/slot-design/${C.did}/categories/${c.id}`, {required: need.value === "" ? null : +need.value});
          need.blur();
          await C.refresh();
        } catch (e) { C.status(e.message, "warn"); }
      });
      const tiles = d.symbols.filter(s => s.category === c.id && visible(s)).map(s => {
        const j = s.job, badge = j ? (j.status === "failed" ? ["fail", "!"] : ["", j.status === "running" ? "…" : "⏳"])
          : s.pending_new || s.reiterate ? ["", "new"] : null;
        const t = el("button", {type: "button", className: "dz-tile" + (s.keep ? " keep" : "") + (s.hide ? " off" : ""), ariaPressed: String(s.id === cur),
          title: s.name + (s.keep ? " · in the final set" : "") + (j ? " · " + j.status : ""), onclick: () => pick(s.id)},
          s.file ? el("img", {src: C.img(s.file), alt: "", loading: "lazy"}) : el("span", {className: "noart", textContent: "no art yet"}),
          el("span", {className: "n", textContent: s.name}),
          badge ? el("span", {className: "b " + badge[0], textContent: badge[1]}) : null);
        return t;
      });
      const newBtn = el("button", {type: "button", className: "ghost", textContent: "+ New", title: `Add a symbol to ${c.title}`,
        ariaPressed: String(cur === "new:" + c.id), onclick: () => {
          if (!(drafts.get(c.id) || []).length) drafts.set(c.id, [draftForm(c)]);
          pick("new:" + c.id);
        }});
      return [el("div", {className: "dz-browse-sec"}, el("span", {textContent: c.title}), countTag(c), el("span", {className: "grow"}),
          el("label", {}, "Needed", need), newBtn),
        tiles.length ? el("div", {className: "dz-tiles"}, ...tiles) : el("p", {className: "hint", style: "padding: 8px var(--pad)", textContent: "Nothing to show here."})];
    }));
  els.list.scrollTop = y;
}

// The right: the picked symbol's card (redrawn when it changes, unless you're working in it), or a section's New forms.
function drawDetail(full, force) {
  const {el} = C, d = C.data;
  let cur = picked.get(C.did);
  if (cur && cur.startsWith("new:")) {
    const c = d.categories.find(x => "new:" + x.id === cur), forms = c ? drafts.get(c.id) || [] : [];
    if (forms.length) {
      rows.clear();
      if (full || !els.detail.contains(forms[0])) els.detail.replaceChildren(...forms,
        el("div", {}, el("button", {type: "button", textContent: "+ Another", onclick: () => { const f = draftForm(c); drafts.set(c.id, [...forms, f]); els.detail.append(f); }})));
      return;
    }
    cur = null;
  }
  let s = d.symbols.find(x => x.id === cur);
  if (!s) {
    s = d.symbols.find(visible) || d.symbols[0];
    if (!s) { els.detail.replaceChildren(el("p", {className: "empty", textContent: "No symbols yet: press + New on a section."})); return; }
    picked.set(C.did, s.id);
    drawBrowser();
  }
  const json = JSON.stringify(s), row = rows.get(s.id);
  if (full || !row) {
    rows.clear();
    const card = symRow(s);
    els.detail.replaceChildren(card);
    rows.set(s.id, {card, json});
  } else if (s.id === force || row.json !== json) {
    row.behind = s.id !== force && (row.card.contains(document.activeElement) || !!saving.get(s.id));
    if (!row.behind) {
      const card = symRow(s);
      row.card.replaceWith(card);
      rows.set(s.id, {card, json});
    }
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
    C.status(`Queued ${r.queued} job${r.queued === 1 ? "" : "s"}. The takes appear here as the image model finishes them.`, "ok");
    await C.refresh();
  } catch (e) { C.status(e.message, "warn"); }
}

async function cancelAll() {
  const n = C.data.art_jobs;
  if (!confirm(`Cancel all ${n} Art job${n === 1 ? "" : "s"}? The picture being drawn now is thrown away; takes already made stay.`)) return;
  try {
    const r = await C.api("DELETE", `/api/slot-design/${C.did}/jobs`);
    C.status(`Cancelled ${r.cancelled} job${r.cancelled === 1 ? "" : "s"}.`, "ok");
    await C.refresh();
  } catch (e) { C.status(e.message, "warn"); }
}

async function hideUnused() {
  try {
    const r = await C.api("POST", `/api/slot-design/${C.did}/hide-unused`);
    C.status(`Hid ${r.hidden} symbol${r.hidden === 1 ? "" : "s"} not in use. Show › Hidden brings them back.`, "ok");
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
  const text = {queued: "Queued", waiting: "Waiting for the image model", running: `Making ${j.done + 1} of ${j.count}`, failed: "Failed"}[j.status];
  const go = (method, tail) => async () => {
    try { await C.api(method, `/api/slot-design/${C.did}/jobs/${j.id}${tail}`); await C.refresh(s.id); }
    catch (e) { C.status(e.message, "warn"); }
  };
  return [el("span", {className: "tag " + (j.status === "failed" ? "warn" : "gold"), textContent: (j.action === "refine" ? "Refine: " : "") + text, title: j.error || ""}),
    j.status === "failed" ? el("button", {type: "button", textContent: "Retry", onclick: go("POST", "/retry")}) : null,
    el("button", {type: "button", textContent: "Cancel", title: j.status === "running" ? "Stop: the picture being drawn now is thrown away" : "",
      onclick: go("DELETE", "")})];
}

function symRow(s) {
  const {el} = C;
  const vs = s.variants, i = Math.max(0, vs.findIndex(v => v.id === s.choice)), v = vs[i];
  const choose = d => vs[i + d] && patch(s, {choice: vs[i + d].id});
  const tool = open.get(s.id);
  const toggle = name => () => { open.set(s.id, tool === name ? null : name); redraw(s.id); };

  const view = el("div", {className: "dz-view"},
    el("div", {className: "dz-big"}, v ? el("img", {src: C.img(s.file), alt: `${s.name}: ${v.label}`})
        : el("span", {className: "hint", textContent: s.pending_new ? "New: press Generate" : "No art yet: pick First generate"}),
      v ? el("span", {className: "lbl" + (v.fav ? " fav" : ""), textContent: (v.fav ? "★ " : "") + v.label}) : null),
    el("div", {className: "dz-nav"},
      el("button", {type: "button", className: "icon", textContent: "◀", disabled: i <= 0, ariaLabel: "Previous take", onclick: () => choose(-1)}),
      el("span", {textContent: `${vs.length ? i + 1 : 0} / ${vs.length}`}),
      el("button", {type: "button", className: "icon", textContent: "▶", disabled: i >= vs.length - 1, ariaLabel: "Next take", onclick: () => choose(1)})),
    v && v.hues ? swatches(s.hue, h => patch(s, {hue: h}), "Frame") : null,
    s.kind === "special" ? wordPicker(s.word, w => patch(s, {word: w})) : null,
    s.kind === "royal" ? royalBits(s) : null,
    v ? el("div", {className: "dz-tools"},
      el("button", {type: "button", textContent: "Refine", ariaPressed: String(tool === "refine"), onclick: toggle("refine")}),
      el("button", {type: "button", textContent: "Fit", ariaPressed: String(tool === "fit"), onclick: toggle("fit")}),
      el("button", {type: "button", textContent: "Split", title: `Move ${v.label} out into a new symbol of its own in this section (the original goes to ${s.name}'s Bin)`,
        onclick: async () => {
          const name = prompt(`Name the new symbol made from ${s.name}'s ${v.label}:`, `${s.name} 2`);
          if (name === null) return;
          if (!name.trim()) return C.status("The new symbol needs a name.", "warn");
          const r = await act(s, "split", {variant: v.id, name});
          if (r) { C.status(`${name.trim()} is now its own symbol in this section; ${s.name}'s copy of the take is in its Bin.`, "ok"); await C.refresh(); }
        }})) : null);

  const section = el("select", {className: "dz-section", ariaLabel: `Section for ${s.name}`, title: "Section: choose another to move it there"},
    ...C.data.categories.map(c => el("option", {value: c.id, textContent: c.title})));
  section.value = s.category;
  section.addEventListener("change", () => patch(s, {category: section.value}));
  const head = el("div", {className: "card-head"}, el("h3", {textContent: s.name}),
    kindSelect(s),
    s.hide ? el("span", {className: "tag", textContent: "hidden"}) : null,
    s.pending_new ? el("span", {className: "tag gold", textContent: `${vs.length ? "first generate" : "new"} · ${s.first_takes} take${s.first_takes === 1 ? "" : "s"} waiting for Generate`}) : null, ...jobBits(s),
    el("label", {className: "confirm", style: "margin-left:auto"},
      el("input", {type: "checkbox", checked: s.keep, onchange: e => patch(s, {keep: e.target.checked})}), "In final set"),
    section,
    s.binned.length ? el("button", {type: "button", textContent: `Bin (${s.binned.length})`, ariaPressed: String(tool === "bin"), onclick: toggle("bin")}) : null,
    s.hide ? el("button", {type: "button", textContent: "Unhide", onclick: () => patch(s, {hide: false})})
      : s.in_use ? null : el("button", {type: "button", textContent: "Hide", title: "Not in use: take it off the board (Show › Hidden brings it back)",
        onclick: () => patch(s, {hide: true})}),
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
  const takes = el("span", {className: "seg", role: "group", ariaLabel: `Reiterate ${s.name}`},
    ...[0, 1, 3, 5].map(n => el("button", {type: "button", textContent: n ? `${n} take${n === 1 ? "" : "s"}` : "No",
      ariaPressed: String(s.reiterate ? n === s.takes : !n),
      onclick: () => patch(s, n ? {reiterate: true, takes: n} : {reiterate: false})})));
  // A first generate: the style prompts (Prompts, at the top) from the reference or the description, like a new symbol.
  const firstFrom = s.kind === "royal" ? "the drawn rank"
    : s.refs.length ? (s.refs.includes(s.base) ? `reference ${s.refs.indexOf(s.base) + 1}` : "reference 1") : "the description";
  const firstHow = {character: "the portrait prompt", special: "the specials prompt", royal: "the royals prompt"}[s.kind] || "style prompts";
  const first = el("span", {className: "seg", role: "group", ariaLabel: `First generate ${s.name}`},
    ...[0, 1, 2, 3].map(n => el("button", {type: "button", textContent: n ? `${n} take${n === 1 ? "" : "s"}` : "No",
      ariaPressed: String(s.pending_new ? n === s.first_takes : !n),
      title: n ? `Take 1${n > 1 ? ` to ${n}` : ""} in the Prompts styles, from ${firstFrom}` : "",
      onclick: () => patch(s, {first: n})})));
  const queue = s.reiterate || s.pending_new ? el("button", {type: "button", className: "primary", textContent: "Queue",
    title: `Send ${s.name} to the image model now, on its own (Generate sends everything marked)`, onclick: async () => {
      while (saving.get(s.id)) await new Promise(r => setTimeout(r, 50));   // the note just typed lands first
      await act(s, "queue", {}, `Queued ${s.name}. The takes appear here as the image model finishes them.`);
    }}) : null;
  const re = el("div", {className: "dz-re"},
    el("div", {className: "controls"}, el("span", {textContent: "First generate"}), first,
      el("span", {className: "hint", textContent: `${firstHow}, from ${firstFrom}`})),
    el("div", {className: "controls"}, el("span", {textContent: "Reiterate"}), takes, base, queue), note);

  let prompt = null;
  if (s.added || s.prompt) {
    prompt = el("textarea", {rows: 2, value: s.prompt || "", ariaLabel: `Description of ${s.name}`,
      placeholder: s.kind === "royal" ? "The emblem tucked into it (optional), e.g. 'a small Starfleet delta'" : "Describe it for the image model"});
    typed(s, "prompt", prompt);
  }
  const failed = s.job && s.job.status === "failed" ? el("p", {className: "hint", textContent: "Failed: " + s.job.error}) : null;
  const card = el("div", {className: "card dz-sym" + (s.keep ? " keep" : "")}, view,
    el("div", {className: "dz-main"}, head, failed, strip, panel, prompt, refs, linkBox, re));
  card.dataset.sid = s.id;
  return card;
}

function kindSelect(s) {
  const k = C.el("select", {className: "dz-section", ariaLabel: `Kind of ${s.name}`,
    title: "Kind: how its next takes are made (the takes it has stay as they are)"},
    ...KINDS.map(([v, t]) => C.el("option", {value: v, textContent: t})));
  k.value = s.kind;
  k.addEventListener("change", () => patch(s, {kind: k.value}));
  return k;
}

// A royal's rank and colour: drawn by the code, so they show on the next take.
function royalBits(s) {
  const {el} = C;
  const rank = el("input", {value: s.rank || "", size: 3, maxLength: 3, ariaLabel: `Rank of ${s.name}`, className: "dz-rank"});
  typed(s, "rank", rank);
  return el("div", {className: "dz-royal"}, swatches(s.hue, h => patch(s, {hue: h}), "Colour"),
    el("label", {className: "hint"}, "Rank ", rank, " · next take"));
}

function refinePanel(s, v) {
  const {el} = C;
  const text = el("textarea", {rows: 2, ariaLabel: "What to change", placeholder: "One change, e.g. 'make his eyes brown' or 'remove the stray star top left'"});
  return el("div", {className: "dz-panel"},
    el("p", {className: "hint", textContent: `Refine ${v.label}: the image model keeps everything and changes only what you say. One new take.`}),
    text,
    el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Refine", onclick: async () => {
      if (!text.value.trim()) return C.status("Say what to change.", "warn");
      open.set(s.id, null);
      await act(s, "refine", {variant: v.id, instruction: text.value}, `Refining ${s.name}: the new take appears when the image model is done.`);
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
    el("option", {value: "character", textContent: "Character (in the shared frame)"}),
    el("option", {value: "special", textContent: "Special (emblem + the shared lettering)"}),
    el("option", {value: "royal", textContent: "Royal (a drawn rank, repainted)"}));
  kind.value = c.kind || "object";
  // A special's word, or a royal's rank and colour, chosen before the first take
  const extra = {word: "WILD", rank: "", hue: null};   // no colour picked: the rank's own (A red, K blue, ...)
  const kindBox = el("div", {className: "field", style: "grid-column: 1 / -1"});
  const showKind = () => {
    if (kind.value === "special") {
      const pick = w => { extra.word = w; showKind(); };
      kindBox.replaceChildren(el("span", {textContent: "Word (laid on by the code; change it any time)"}), wordPicker(extra.word, pick));
    } else if (kind.value === "royal") {
      const rank = el("input", {value: extra.rank, size: 3, maxLength: 3, placeholder: "A", ariaLabel: "Rank"});
      rank.addEventListener("input", () => { extra.rank = rank.value; });
      kindBox.replaceChildren(el("span", {textContent: "Rank and colour (blank: from the name, and the rank's usual colour)"}),
        el("div", {className: "controls"}, rank, swatches(extra.hue, h => { extra.hue = h; showKind(); }, "Colour")));
    } else kindBox.replaceChildren();
  };
  kind.addEventListener("change", showKind);
  showKind();
  const key = el("select", {ariaLabel: "Background to key off"}, el("option", {value: "magenta", textContent: "Magenta (most art)"}),
    el("option", {value: "green", textContent: "Green (purple or pink art)"}));
  const desc = el("textarea", {rows: 2, ariaLabel: "Description", placeholder: "Describe it for the image model, e.g. 'a Starfleet shuttlecraft, three-quarter view'"});
  const chosen = el("div", {className: "dz-refs"});
  const card = el("div", {className: "card dz-new"},
    el("div", {className: "card-head"}, el("h3", {textContent: "New symbol"}), el("span", {className: "tag", textContent: c.title})),
    el("div", {className: "grid2"},
      el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
      el("label", {className: "field"}, el("span", {textContent: "Kind"}), kind),
      el("label", {className: "field"}, el("span", {textContent: "Background to key off"}), key),
      kindBox,
      el("label", {className: "field", style: "grid-column: 1 / -1"}, el("span", {textContent: "Description (a royal's: the emblem tucked into it, optional)"}), desc)),
    el("div", {className: "field"}, el("span", {textContent: "Reference image (optional: with one, the image model redraws it; without, it draws from the description)"}),
      linker(C, path => {
        ref = path;
        chosen.replaceChildren("Reference", el("span", {className: "dz-ref"}, el("img", {src: C.img(path), alt: "Reference"}),
          el("button", {type: "button", textContent: "✕", ariaLabel: "Drop the reference", onclick: () => { ref = null; chosen.replaceChildren(); }})));
      }), chosen),
    el("div", {className: "controls"},
      el("button", {type: "button", className: "primary", textContent: "Add to " + c.title, onclick: async () => {
        try {
          const r = await C.api("POST", `/api/slot-design/${C.did}/symbols`, {name: name.value, category: c.id, kind: kind.value, key: key.value, prompt: desc.value, ref,
            ...(kind.value === "special" ? {word: extra.word} : kind.value === "royal" ? {rank: extra.rank, ...(extra.hue ? {hue: extra.hue} : {})} : {})});
          const n = C.data.prompts.first_takes;
          C.status(`${name.value} added: Generate makes ${n} take${n === 1 ? "" : "s"}.`, "ok");
          discard(r.id);
          await C.refresh();
        } catch (e) { C.status(e.message, "warn"); }
      }}),
      el("button", {type: "button", textContent: "Discard", onclick: () => discard()})));
  function discard(next) {
    card.remove();
    drafts.set(c.id, (drafts.get(c.id) || []).filter(f => f !== card));
    if (next || !drafts.get(c.id).length) { picked.set(C.did, next || null); drawBrowser(); drawDetail(true); }
  }
  return card;
}
