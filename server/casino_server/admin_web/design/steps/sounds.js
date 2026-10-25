// Step 8, Sounds: the slot preset the slot starts on (the Sounds tab's Default, or one made there), and the slot's own
// sound for any slot moment; anything left alone plays the preset's. The bonus games' sounds are set on the Sounds
// tab, not per slot. Picks are kept in the design; Build gives the slot its sound set, following that preset.
// The library is the Sounds tab's (the CC0 collection plus uploads).
let C, lib = null, openKey = null, query = "";

export async function render(ctx, body) {
  C = ctx;
  const {el} = C;
  body.append(el("p", {className: "lead", textContent: "Pick a preset to start from: each moment plays the preset's sound until you give it this slot's own. Several sounds on one moment play at random. The bonus games' sounds are on the Sounds tab. Changes here reach the game when the slot is built."}),
    el("label", {className: "controls snd-preset"}, el("span", {className: "hint", textContent: "Starts from preset"}), el("select", {id: "snd-preset", ariaLabel: "Sound preset"})),
    el("div", {className: "snd-list"}, el("p", {className: "hint", textContent: "Loading the sound library…"})));
  document.getElementById("snd-preset").addEventListener("change", async e => {
    try { await C.api("PUT", `/api/slot-design/${C.did}/sound-preset`, {preset: e.target.value}); await C.refresh(); }
    catch (err) { C.status(err.message, "warn"); }
  });
  if (!lib) lib = await C.api("GET", "/api/sounds");
  draw();
}

export function update(ctx) {
  C = ctx;
  const root = document.querySelector(".snd-list");
  if (root && !(root.contains(document.activeElement) && document.activeElement.type === "search")) draw();
}

const play = id => { const a = new Audio(`/sound-files/${id}`); a.play().catch(() => {}); };
const nameOf = id => id.split("/").pop().replace(/\.(ogg|mp3|wav)$/, "");

async function setFiles(key, files, gain) {
  try {
    if (files === null) await C.api("DELETE", `/api/slot-design/${C.did}/sounds/${key}`);
    else await C.api("PUT", `/api/slot-design/${C.did}/sounds/${key}`, {files, gain_db: gain});
    if (C.data.steps.find(s => s.id === "sounds").status === "todo") await C.setStep("sounds", "doing"); else await C.refresh();
  } catch (e) { C.status(e.message, "warn"); }
}

function draw() {
  const {el} = C, rows = C.data.sounds.moments;
  const root = document.querySelector(".snd-list");
  if (!root) return;
  const sel = document.getElementById("snd-preset");
  if (sel) { sel.replaceChildren(...C.data.sounds.presets.map(p => el("option", {value: p.key, textContent: p.name}))); sel.value = C.data.sounds.preset; }
  const sections = [...new Set(rows.map(r => r.section))];
  root.replaceChildren(...sections.map(sec => el("div", {className: "pane"}, el("h3", {className: "sec", textContent: sec}),
    el("div", {className: "mrows"}, ...rows.filter(r => r.section === sec).map(r => row(r))))));
}

function row(r) {
  const {el} = C, own = r.own, files = own ? own.files : r.inherited.files;
  const chip = (id, removable) => el("span", {className: "chip"},
    el("button", {type: "button", className: "icon", textContent: "▶", ariaLabel: `Play ${nameOf(id)}`, onclick: () => play(id)}),
    el("span", {textContent: nameOf(id)}),
    removable ? el("button", {type: "button", className: "icon", textContent: "✕", ariaLabel: `Remove ${nameOf(id)}`,
      onclick: () => setFiles(r.key, own.files.filter(f => f !== id), own.gain_db)}) : null);
  const box = el("div", {className: "mrow" + (own ? "" : " inherited") + (openKey === r.key ? " editing" : "")},
    el("div", {className: "mt"}, el("b", {textContent: r.title}), r.loop ? el("span", {className: "tag", textContent: "loops"}) : null,
      el("span", {className: "tag " + (own ? "gold" : ""), textContent: own ? "this slot's" : (r.inherited.from_name || "the preset") + "'s"})),
    el("p", {className: "when", textContent: r.when}),
    el("div", {className: "chosen"}, ...(files.length ? files.map(f => chip(f, !!own)) : [el("span", {className: "hint", textContent: "silent"})])),
    el("div", {className: "acts"}, el("div", {className: "btns"},
      el("button", {type: "button", textContent: openKey === r.key ? "Done" : "Change…", onclick: () => { openKey = openKey === r.key ? null : r.key; draw(); }}),
      own ? el("button", {type: "button", textContent: "Same as the preset", onclick: () => setFiles(r.key, null)}) : null,
      own ? el("button", {type: "button", textContent: "No sound", onclick: () => setFiles(r.key, [], own.gain_db)}) : null)));
  if (openKey === r.key) box.append(picker(r));
  return box;
}

function picker(r) {
  const {el} = C, own = r.own;
  const search = el("input", {type: "search", value: query, placeholder: "Search the library", ariaLabel: "Search the library"});
  const list = el("div", {className: "list"});
  const suited = new Set(Object.entries(lib.folders).filter(([, f]) => f.sections.includes(r.section)).map(([k]) => k));
  const fill = () => {
    query = search.value;
    const q = query.trim().toLowerCase();
    const items = lib.library.filter(x => !q || x.id.toLowerCase().includes(q))
      .sort((a, b) => (suited.has(b.group) - suited.has(a.group)) || a.id.localeCompare(b.id)).slice(0, 80);
    list.replaceChildren(...items.map(x => el("div", {className: "row"},
      el("button", {type: "button", className: "icon", textContent: "▶", ariaLabel: `Play ${x.name}`, onclick: () => play(x.id)}),
      el("span", {className: "name", textContent: x.name}, el("small", {textContent: x.group})),
      el("span", {className: "btns"},
        el("button", {type: "button", textContent: "Use", onclick: () => setFiles(r.key, [x.id], own ? own.gain_db : 0)}),
        el("button", {type: "button", textContent: "Add", onclick: () => setFiles(r.key, [...(own ? own.files : r.inherited.files), x.id].filter((v, i, a) => a.indexOf(v) === i), own ? own.gain_db : 0)})))));
  };
  search.addEventListener("input", fill);
  fill();
  const upload = el("input", {type: "file", accept: "audio/*", ariaLabel: "Upload a sound"});
  upload.addEventListener("change", async () => {
    const f = upload.files[0];
    if (!f) return;
    try {
      const up = await C.api("PUT", `/api/sound-uploads/${encodeURIComponent(f.name)}`, await f.arrayBuffer(), true);
      lib.library.push(up);
      await setFiles(r.key, [...(own ? own.files : []), up.id], own ? own.gain_db : 0);
    } catch (e) { C.status(e.message, "warn"); }
  });
  const gain = el("input", {type: "number", min: -30, max: 12, step: 1, value: own ? own.gain_db : 0, className: "wz-num", ariaLabel: "Volume trim, dB"});
  gain.addEventListener("change", () => own && setFiles(r.key, own.files, +gain.value));
  return el("div", {className: "pane snd-pick"}, el("div", {className: "lib-tools"}, search, upload),
    own ? el("label", {className: "controls"}, el("span", {className: "hint", textContent: "Volume trim (dB)"}), gain) : null, list);
}
