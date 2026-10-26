// Sounds: every table and slot machine plays from its own sound set, which plays the set above's sounds for any
// moment it doesn't have its own (Whole casino, then each game; for a slot machine, Default, then the preset it
// follows, then the machine's own tweaks). The bonus games have sets of their own, which every machine plays.
// Three columns: the sets, the chosen set's moments one to a line, and the library for the moment being changed.
// Changes save at once and every open game picks them up within a second.
let H, $, el, data = null, setKey = "casino", editing = null, group = "@suggested";
const saveTimers = {};

export function init(h) {
  H = h; el = h.el; $ = s => h.view.querySelector(s) || h.top.querySelector(s);
  h.top.append(
    el("input", {type: "search", id: "moment-search", placeholder: "Find a moment, e.g. reel, win", style: "width: 260px"}),
    el("label", {className: "controls hint"}, el("input", {type: "checkbox", id: "only-own"}), "Only its own sounds"),
    el("span", {className: "grow"}), el("span", {id: "set-reset"}));
  h.view.innerHTML = `
  <div class="wb" style="grid-template-columns: 230px minmax(0, 1fr) 460px">
    <div class="panel"><div class="ph">Sound sets</div><div class="pb snd-sets" id="sets"></div></div>
    <div class="panel flat">
      <div class="ph"><b id="set-title"></b><span class="hint" id="set-sub" style="text-transform:none;letter-spacing:0"></span>
        <span class="grow"></span><span class="controls set-tools" id="set-tools"></span></div>
      <div class="pb" id="moments"></div>
    </div>
    <div class="panel">
      <div class="ph"><b id="picker-h">Library</b><span class="grow"></span><button type="button" class="ghost" id="picker-close" hidden>Done</button></div>
      <div class="pb padded snd-picker" style="grid-template-rows: auto auto auto minmax(0, 1fr) auto; height: 100%; overflow: hidden">
        <p class="hint" id="picker-sub">Press Change on a moment to pick its sounds here.</p>
        <div class="chosen" id="picker-chosen"></div>
        <div class="controls"><input type="search" id="search" placeholder="Search, e.g. coin, banjo, click" style="flex: 1"><select id="group" aria-label="Folder" style="max-width: 200px"></select></div>
        <div class="list" id="list"></div>
        <label class="drop" id="drop">Drop sound files here, or <u>choose files</u> (.ogg .mp3 .wav .flac .m4a)
          <input type="file" id="file" accept=".ogg,.mp3,.wav,.flac,.m4a,.opus,audio/*" multiple hidden></label>
      </div>
    </div>
  </div>
  <style>
    .snd-sets { padding: 6px; display: grid; gap: 1px; align-content: start; }
    .snd-sets h3 { margin: 10px 8px 2px; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .1em; color: var(--fg-faint); }
    .snd-sets h3:first-child { margin-top: 2px; }
    .set-item { justify-content: flex-start; width: 100%; height: 28px; border: 0; background: none; padding: 0 8px; font-size: var(--fs-s); color: var(--fg-muted); }
    .set-item:hover { background: var(--bg-2); color: var(--fg); }
    .set-item.child { padding-left: 22px; }
    .set-item .n { margin-left: auto; font: var(--fs-xs) var(--mono); color: var(--fg-faint); }
    .set-item .dot { background: var(--accent); }
    .set-item[aria-current="true"] { background: var(--accent-soft); color: var(--fg); box-shadow: inset 2px 0 0 var(--accent); font-weight: 600; }
    .snd-sets .reset-all { margin: 10px 8px 4px; justify-self: start; }
    .snd-sets .new-preset { margin: 2px 8px 4px 22px; justify-self: start; height: 24px; padding: 0 8px; }
    .snd-sets .ask, .set-tools .ask { display: flex; gap: 4px; margin: 2px 8px 4px 22px; }
    .set-tools .ask { margin: 0; }
    .snd-sets .ask input { min-width: 0; flex: 1; }
    .set-tools { gap: 6px; text-transform: none; letter-spacing: 0; }
    .set-tools button { height: 24px; padding: 0 8px; }
    .set-tools select { height: 24px; }
    #moments .sec { position: sticky; top: 0; z-index: 1; margin: 0; padding: 0 12px; height: 28px; display: flex; align-items: center; background: var(--bg-0); border-bottom: 1px solid var(--line);
      font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: .1em; color: var(--fg-faint); }
    .mrow { display: grid; grid-template-columns: 260px minmax(0, 1fr) 210px auto; align-items: center; gap: 12px; min-height: 38px; padding: 4px 12px; border-bottom: 1px solid var(--line); }
    .mrow:hover { background: color-mix(in srgb, var(--bg-1) 70%, transparent); }
    .mrow.inherited .chip { border-style: dashed; color: var(--fg-muted); background: none; }
    .mrow.editing { background: var(--accent-soft); box-shadow: inset 2px 0 0 var(--accent); }
    .mrow .mt { display: flex; align-items: center; gap: 6px; min-width: 0; overflow: hidden; }
    .mrow .mt b { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .mrow .gain { display: flex; align-items: center; gap: 6px; font-size: var(--fs-xs); color: var(--fg-faint); }
    .mrow .gain input { flex: 1; min-width: 0; }
    .mrow .gain output { font: var(--fs-xs) var(--mono); color: var(--fg); min-width: 52px; text-align: right; }
    .mrow .btns { display: flex; gap: 4px; justify-content: end; }
    .mrow .btns button { height: 24px; padding: 0 8px; }
    .snd-picker .list .row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 3px 8px; border-bottom: 1px solid var(--line); }
    .snd-picker .list .row:last-child { border-bottom: 0; }
    .snd-picker .list .name { font: var(--fs-s) var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .snd-picker .list .name small { display: block; color: var(--fg-faint); font: var(--fs-xs) var(--font); }
    .snd-picker .list .row.used .name { color: var(--ok); }
    .snd-picker .list .btns { display: flex; gap: 4px; }
    .snd-picker .list .btns button { height: 24px; padding: 0 8px; }
  </style>`;
  wire();
}

const remember = {get: k => H.remember.get("sounds." + k), set: (k, v) => H.remember.set("sounds." + k, v)};
const nameOf = id => id.split("/").pop().replace(/\.(ogg|mp3|wav)$/, "");
const fmtDb = v => (v > 0 ? "+" : "") + (+v).toFixed(1) + " dB";
const setOf = k => data.sets.find(s => s.key === k);
const setName = k => (setOf(k) || {name: k}).name;
const rowOf = k => setOf(setKey).moments.find(r => r.key === k);
const path = k => "/api/sounds/" + encodeURIComponent(setKey) + "/" + k;

// ---------------------------------------------------------------- listening
let ctx = null, playing = null;
const buffers = {};
function stopPlaying() {
  if (playing) { try { playing.src.stop(); } catch (e) {} playing.btn && playing.btn.classList.remove("on"); playing = null; }
}
// Loops (the reels spinning, the win meter) play round until pressed again, so the join can be heard.
async function play(id, gainDb, btn, loop) {
  const again = playing && playing.btn === btn && btn;
  stopPlaying();
  if (again) return;
  ctx = ctx || new AudioContext();
  if (ctx.state === "suspended") await ctx.resume();
  btn && btn.classList.add("on");
  try {
    buffers[id] = buffers[id] || fetch("/sound-files/" + id).then(r => r.arrayBuffer()).then(b => ctx.decodeAudioData(b));
    const buffer = await buffers[id];
    const src = ctx.createBufferSource(), gain = ctx.createGain();
    src.buffer = buffer; src.loop = !!loop; gain.gain.value = Math.pow(10, (gainDb || 0) / 20);
    src.connect(gain).connect(ctx.destination);
    const me = {src, btn}; playing = me;
    src.onended = () => { if (playing === me) stopPlaying(); };
    src.start();
  } catch (e) {
    delete buffers[id]; btn && btn.classList.remove("on");
    H.status("Couldn't play " + nameOf(id) + ": " + e.message, "warn");
  }
}
const playButton = (id, gain, loop, label = "Play") => {
  const b = el("button", {className: "icon", type: "button", textContent: "▶", title: label + (loop ? " (loops until pressed again)" : "")});
  b.setAttribute("aria-label", label + " " + nameOf(id));
  b.addEventListener("click", () => play(id, typeof gain === "function" ? gain() : gain, b, loop));
  return b;
};

// ---------------------------------------------------------------- the sets
function renderSets() {
  const nav = $("#sets");
  nav.replaceChildren();
  let heading = null;
  const endPresets = () => { if (heading === "Slot presets") nav.append(newPresetButton()); };
  for (const s of data.sets) {
    if (s.group !== heading) { endPresets(); heading = s.group; if (heading) nav.append(el("h3", {textContent: heading})); }
    const own = s.moments.filter(r => r.own).length, changed = s.moments.some(r => r.changed);
    const b = el("button", {type: "button", className: "set-item" + (s.parent && s.parent !== "casino" ? " child" : "")},
      el("span", {textContent: s.name}), changed ? el("span", {className: "dot", title: "Changed here"}) : null,
      el("span", {className: "n", textContent: own + "/" + s.moments.length, title: own + " of the " + s.moments.length + " moments it uses have their own sounds here"}));
    b.setAttribute("aria-current", String(s.key === setKey));
    if (s.preset && s.preset !== "slots") b.title = "Follows " + setName(s.preset);
    b.addEventListener("click", () => choose(s.key));
    nav.append(b);
  }
  endPresets();
  if (data.sets.some(s => s.moments.some(r => r.changed))) {
    const all = el("button", {type: "button", className: "reset-all ghost", textContent: "Reset every set…"});
    all.addEventListener("click", () => confirmIn(all, "Reset every set", async () => {
      await mutate(H.api("POST", "/api/sounds-reset", {}), "Every set is back to how it came.");
    }));
    nav.append(all);
  }
}
function choose(key) {
  setKey = key; remember.set("set", key);
  closePicker(true);
  renderSets(); renderMoments();
  $("#moments").scrollTop = 0;
}
function newPresetButton() {
  const b = el("button", {type: "button", className: "ghost new-preset", textContent: "+ New preset", title: "A preset plays Default's sounds until you give it its own"});
  b.addEventListener("click", () => askName(b, "Create", "", name => makePreset(name)));
  return b;
}
async function makePreset(name, from) {
  try {
    const r = await H.api("POST", "/api/sound-presets", from ? {name, from} : {name});
    await refresh(); choose(r.key);
    H.status(from && from.startsWith("slots.") ? setName(from) + " now follows " + name + ", which has its sounds. Games updated."
             : "Made " + name + (from ? ", a copy of " + setName(from) : ": it plays Default's sounds until you give it its own") + ".", "ok");
  } catch (e) { H.status(e.message, "warn"); }
}
// Swap a button for "[name] [ok] [cancel]".
function askName(btn, label, value, action) {
  const input = el("input", {type: "text", value, placeholder: "Preset name", maxLength: 40});
  input.setAttribute("aria-label", "Preset name");
  const ok = el("button", {type: "button", className: "primary", textContent: label});
  const no = el("button", {type: "button", textContent: "Cancel"});
  const box = el("span", {className: "ask"}, input, ok, no);
  const go = () => input.value.trim() && action(input.value.trim());
  ok.addEventListener("click", go);
  input.addEventListener("keydown", e => { if (e.key === "Enter") go(); if (e.key === "Escape") { e.stopPropagation(); box.replaceWith(btn); } });
  no.addEventListener("click", () => box.replaceWith(btn));
  btn.replaceWith(box);
  input.focus(); input.select();
}
// Swap a button for "[yes] [keep]".
function confirmIn(btn, label, action) {
  const yes = el("button", {type: "button", className: "primary", textContent: label});
  const no = el("button", {type: "button", textContent: "Keep"});
  const box = el("span", {className: "confirm"}, yes, no);
  yes.addEventListener("click", action);
  no.addEventListener("click", () => box.replaceWith(btn));
  btn.replaceWith(box);
}

// ---------------------------------------------------------------- the moments
function renderMoments() {
  const s = setOf(setKey);
  $("#set-title").textContent = s.name;
  $("#set-sub").textContent = s.group === "Bonus games" ? "· every slot machine with this bonus plays these"
    : s.parent ? "· dashed sounds are " + setName(s.parent) + "'s" : "· every game plays these unless its own set says otherwise";
  renderSetTools(s);
  const rbox = $("#set-reset"); rbox.replaceChildren();
  if (s.moments.some(r => r.changed)) {
    const b = el("button", {type: "button", textContent: "Reset " + s.name + "…"});
    b.addEventListener("click", () => confirmIn(b, "Reset " + s.name, () => mutate(H.api("POST", "/api/sounds-reset", {set: setKey}), s.name + " is back to how it came.")));
    rbox.append(b);
  }
  const q = $("#moment-search").value.trim().toLowerCase(), onlyOwn = $("#only-own").checked;
  const box = $("#moments"); box.replaceChildren();
  for (const sec of data.sections) {
    const rows = s.moments.filter(r => {
      const m = data.moments[r.key];
      return m.section === sec && (!onlyOwn || r.own) && (!q || (m.title + " " + m.when + " " + r.key).toLowerCase().includes(q));
    });
    if (!rows.length) continue;
    box.append(el("h3", {className: "sec", textContent: sec}), ...rows.map(momentRow));
  }
  if (!box.children.length) box.append(el("p", {className: "empty", textContent: "No moments match."}));
}
// A machine: the preset it follows, and making one from it. A preset: who's on it, renaming, copying, deleting.
function renderSetTools(s) {
  const box = $("#set-tools"); box.replaceChildren();
  const machines = keys => keys.map(setName).join(", ");
  if (s.preset) {
    const sel = el("select", {}, ...data.sets.filter(x => x.group === "Slot presets").map(x => el("option", {value: x.key, textContent: x.name})));
    sel.setAttribute("aria-label", "Preset " + s.name + " follows");
    sel.value = s.preset;
    sel.addEventListener("change", () => mutate(H.api("PUT", "/api/sound-machines/" + encodeURIComponent(s.key), {preset: sel.value}),
      s.name + " now follows " + setName(sel.value) + (s.moments.some(r => r.own) ? ", with its own tweaks on top." : ".")));
    const save = el("button", {type: "button", textContent: "Save as preset…", title: "Make a preset from how " + s.name + " sounds, which it then follows"});
    save.addEventListener("click", () => askName(save, "Save", s.name, name => makePreset(name, s.key)));
    box.append(el("span", {className: "hint", textContent: "Preset"}), sel, save);
    if (s.moments.some(r => r.own)) {
      const drop = el("button", {type: "button", className: "ghost", textContent: "Drop tweaks…", title: "Play " + setName(s.preset) + "'s sounds for everything"});
      drop.addEventListener("click", () => confirmIn(drop, "Drop every tweak", () =>
        mutate(H.api("POST", "/api/sounds/" + encodeURIComponent(s.key) + "/inherit-all"), s.name + " plays " + setName(s.preset) + " as it is.")));
      box.append(drop);
    }
  } else if (s.used_by) {
    box.append(el("span", {className: "hint", textContent: s.used_by.length ? "Used by " + machines(s.used_by) : "No machine follows it yet"}));
    if (s.key !== "slots") {
      const rename = el("button", {type: "button", textContent: "Rename…"});
      rename.addEventListener("click", () => askName(rename, "Rename", s.name, name =>
        mutate(H.api("PATCH", "/api/sound-presets/" + encodeURIComponent(s.key), {name}), "Renamed it " + name + ".")));
      const copy = el("button", {type: "button", textContent: "Copy…", title: "A new preset starting with this one's sounds"});
      copy.addEventListener("click", () => askName(copy, "Copy", s.name + " copy", name => makePreset(name, s.key)));
      const del = el("button", {type: "button", className: "ghost danger", textContent: "Delete…"});
      del.addEventListener("click", () => confirmIn(del, "Delete " + s.name, async () => {
        try {
          const r = await H.api("DELETE", "/api/sound-presets/" + encodeURIComponent(s.key));
          await refresh(); choose("slots");
          H.status("Deleted " + s.name + "." + (r.moved.length ? " " + r.moved.join(", ") + (r.moved.length > 1 ? " follow" : " follows") + " Default now." : "") + " Games updated.", "ok");
        } catch (e) { H.status(e.message, "warn"); }
      }));
      box.append(rename, copy, del);
    }
  }
}
function momentRow(r) {
  const m = data.moments[r.key], s = setOf(setKey);
  const row = el("div", {className: "mrow" + (r.own ? "" : " inherited") + (editing === r.key ? " editing" : ""), id: "m-" + r.key});
  const title = el("div", {className: "mt"}, el("b", {textContent: m.title, title: m.when}), H.info(m.when));
  if (r.as) title.append(el("span", {className: "tag", textContent: "as " + data.moments[r.as].title}));
  if (!r.own) title.append(el("span", {className: "tag", textContent: "from " + setName(r.from)}));
  if (m.loop) title.append(el("span", {className: "tag", textContent: "loops"}));
  if (r.changed) title.append(el("span", {className: "tag gold", textContent: "changed"}));
  if (!r.files.length) title.append(el("span", {className: "tag warn", textContent: "silent"}));
  const chosen = el("div", {className: "chosen"},
    ...r.files.map(f => el("span", {className: "chip", title: f}, playButton(f, () => r.gain_db, m.loop), el("span", {textContent: nameOf(f)}))));
  if (!r.files.length) chosen.append(el("span", {className: "hint", textContent: "No sound" + (r.own ? " here." : ": " + setName(r.from) + " is silent for this.")}));
  // the volume trim (moving it on a borrowed moment gives this set its own copy)
  const out = el("output", {textContent: fmtDb(r.gain_db)});
  const slider = el("input", {type: "range", min: -30, max: 12, step: 0.5, value: r.gain_db, id: "gain-" + r.key});
  slider.setAttribute("aria-label", m.title + " volume trim");
  slider.addEventListener("input", () => {
    r.gain_db = +slider.value; out.textContent = fmtDb(r.gain_db);
    clearTimeout(saveTimers[r.key]);
    saveTimers[r.key] = setTimeout(() => save(r.key, r.files, r.gain_db, r.own), 450);
  });
  const tryBtn = el("button", {type: "button", textContent: "▶ Try", disabled: !r.files.length});
  tryBtn.addEventListener("click", () => r.files.length && play(r.files[Math.floor(Math.random() * r.files.length)], r.gain_db, tryBtn, m.loop));
  const edit = el("button", {type: "button", className: editing === r.key ? "primary" : "", textContent: r.own ? "Change" : "Own…", title: r.own ? "Pick its sounds" : "Give " + s.name + " its own sounds for this"});
  edit.addEventListener("click", () => editing === r.key ? closePicker() : openPicker(r.key));
  const btns = el("div", {className: "btns"}, tryBtn, edit);
  if (r.files.length) btns.append(silenceButton(r.key, r.gain_db));
  if (r.own && r.can_inherit) {
    const up = el("button", {type: "button", textContent: "Inherit", title: "Play " + setName(s.parent) + "'s sounds for this"});
    up.addEventListener("click", () => mutate(H.api("POST", path(r.key) + "/inherit"), m.title + " now plays " + setName(s.parent) + "'s."));
    btns.append(up);
  }
  if (r.changed) {
    const reset = el("button", {type: "button", className: "ghost", textContent: "Reset", title: "Back to how it came"});
    reset.addEventListener("click", () => mutate(H.api("DELETE", path(r.key)), m.title + " is back to how it came."));
    btns.append(reset);
  }
  row.append(title, chosen, el("label", {className: "gain", htmlFor: "gain-" + r.key}, slider, out), btns);
  return row;
}

// Nothing plays for this moment in this set (the set above doesn't fill in).
function silenceButton(key, gain) {
  const b = el("button", {type: "button", className: "ghost", textContent: "Mute", title: "Play nothing for this in " + setName(setKey)});
  b.addEventListener("click", () => mutate(H.api("PUT", path(key), {files: [], gain_db: gain}), data.moments[key].title + " is silent in " + setName(setKey) + "."));
  return b;
}

// ---------------------------------------------------------------- changing
async function refresh() {
  data = await H.api("GET", "/api/sounds");
  if (!setOf(setKey)) setKey = "casino";
}
async function mutate(request, message) {
  try {
    await request; await refresh();
    renderSets(); renderMoments(); if (editing) renderPicker();
    H.status(message + " Games updated.", "ok");
  } catch (e) { H.status(e.message, "warn"); }
}
// `quiet` (the volume of a moment that already has its own sounds): nothing on screen needs redrawing.
async function save(key, files, gain, quiet) {
  const title = data.moments[key].title;
  if (!quiet) return mutate(H.api("PUT", path(key), {files, gain_db: gain}), "Saved " + title + ".");
  try {
    await H.api("PUT", path(key), {files, gain_db: gain});
    await refresh(); renderSets();
    H.status("Saved " + title + ". Games updated.", "ok");
  } catch (e) { H.status(e.message, "warn"); }
}

// ---------------------------------------------------------------- the library
function openPicker(key) {
  const sameSection = editing && data.moments[editing].section === data.moments[key].section;
  editing = key;
  if (!sameSection) { group = "@suggested"; $("#search").value = ""; }
  renderPicker(); renderMoments();
  $("#search").focus();
}
function closePicker(quiet) {
  if (!editing) return;
  editing = null; stopPlaying();
  $("#picker-close").hidden = true;
  $("#picker-h").textContent = "Library";
  $("#picker-sub").textContent = "Press Change on a moment to pick its sounds here.";
  $("#picker-chosen").replaceChildren();
  renderLibrary();
  if (!quiet) renderMoments();
}
function renderPicker() {
  const r = rowOf(editing), m = data.moments[editing];
  if (!r) return closePicker();
  $("#picker-close").hidden = false;
  $("#picker-h").textContent = m.title + " · " + setName(setKey);
  $("#picker-sub").textContent = r.own
    ? m.when + " One is picked at random each time it plays."
    : m.when + " It plays " + setName(r.from) + "'s sounds now: adding, using or removing one gives " + setName(setKey) + " its own.";
  const chosen = $("#picker-chosen"); chosen.replaceChildren();
  if (!r.files.length) chosen.append(el("span", {className: "hint", textContent: "No sound. Use or Add one below to give it a sound."}));
  for (const f of r.files) {
    const rm = el("button", {className: "icon", type: "button", textContent: "✕", title: "Remove", disabled: r.files.length === 1});
    rm.setAttribute("aria-label", "Remove " + nameOf(f));
    rm.addEventListener("click", () => save(editing, r.files.filter(x => x !== f), r.gain_db));
    chosen.append(el("span", {className: "chip", title: f}, playButton(f, r.gain_db, m.loop), el("span", {textContent: nameOf(f)}), rm));
  }
  renderFolders(m);
  renderLibrary();
}
function renderFolders(m) {   // the ones suited to this moment's section first
  const sel = $("#group"), folders = [...new Set(data.library.map(s => s.group))];
  const label = f => (data.folders[f] || {label: ""}).label;
  sel.replaceChildren(...(m ? [el("option", {value: "@suggested", textContent: "Suited to " + m.section})] : []),
                      el("option", {value: "", textContent: "Every folder"}),
                      ...folders.map(f => el("option", {value: f, textContent: f + (label(f) ? " · " + label(f) : "")})));
  sel.value = folders.includes(group) || group === "" ? group : m ? "@suggested" : "";
}
function renderLibrary() {
  const r = editing && rowOf(editing), m = editing && data.moments[editing];
  if (!m) renderFolders(null);
  const q = $("#search").value.trim().toLowerCase(), g = $("#group").value;
  group = g;
  const suits = f => m && ((data.folders[f] || {}).sections || []).includes(m.section);
  const order = Object.keys(data.folders);   // the slot and western folders first, then the rest
  const rank = s => { const i = order.indexOf(s.group); return i < 0 ? order.length : i; };
  const items = data.library.filter(s => (g === "@suggested" ? suits(s.group) : !g || s.group === g) && (!q || s.id.toLowerCase().includes(q)))
                            .sort((a, b) => rank(a) - rank(b));
  const list = $("#list"); list.replaceChildren();
  for (const s of items.slice(0, 500)) {
    const here = r && r.files.includes(s.id);
    const btns = el("span", {className: "btns"});
    if (r) {
      const use = el("button", {type: "button", textContent: "Use", title: "Use only this one"});
      use.addEventListener("click", () => save(editing, [s.id], r.gain_db));
      const add = el("button", {type: "button", textContent: here ? "Added" : "Add", disabled: here, title: "Add it as another variant"});
      add.addEventListener("click", () => save(editing, [...r.files, s.id], r.gain_db));
      btns.append(use, add);
    }
    if (s.group === "uploads") {
      const del = el("button", {type: "button", className: "ghost danger", textContent: "Delete", title: "Delete this upload"});
      del.addEventListener("click", () => confirmIn(del, "Delete", () => mutate(H.api("DELETE", "/api/sound-uploads/" + encodeURIComponent(s.id.slice(8))), "Deleted " + s.name + ".")));
      btns.prepend(del);
    }
    list.append(el("div", {className: "row" + (here ? " used" : "")},
      playButton(s.id, r ? r.gain_db : 0, m && m.loop),
      el("div", {className: "name", title: s.id}, s.name, el("small", {textContent: s.group + " · " + Math.max(1, Math.round(s.bytes / 1024)) + " KB" + (here ? " · chosen" : "")})),
      btns));
  }
  if (!items.length) list.append(el("p", {className: "empty", textContent: "Nothing matches. Try another word or folder, or upload a file below."}));
  if (items.length > 500) list.append(el("p", {className: "empty", textContent: "And " + (items.length - 500) + " more: search to narrow it down."}));
}
async function upload(files) {
  for (const f of files) {
    H.status("Uploading " + f.name + "…");
    try {
      const s = await H.api("PUT", "/api/sound-uploads/" + encodeURIComponent(f.name), f, true);
      await refresh();
      group = "uploads"; editing ? renderPicker() : renderLibrary();
      H.status("Uploaded " + s.name + ". It's in the uploads folder" + (editing ? ": press Use or Add." : "."), "ok");
    } catch (e) { H.status("Couldn't upload " + f.name + ": " + e.message, "warn"); }
  }
}

export async function load() {
  try {
    await refresh();
    const kept = remember.get("set");
    if (kept && setOf(kept)) setKey = kept;
    renderSets(); renderMoments(); renderLibrary();
    H.status("Ready. " + data.sets.length + " sound sets, " + data.library.length + " sounds in the library.");
  } catch (e) { H.status("Couldn't reach the server: " + e.message, "warn"); }
}

export function shown(on) { if (!on) stopPlaying(); }

function wire() {
  $("#moment-search").addEventListener("input", renderMoments);
  $("#only-own").addEventListener("change", renderMoments);
  $("#search").addEventListener("input", renderLibrary);
  $("#group").addEventListener("change", renderLibrary);
  $("#picker-close").addEventListener("click", () => closePicker());
  $("#file").addEventListener("change", e => { upload([...e.target.files]); e.target.value = ""; });
  const drop = $("#drop");
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); upload([...e.dataTransfer.files]); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !H.view.hidden) { stopPlaying(); closePicker(); } });
}
