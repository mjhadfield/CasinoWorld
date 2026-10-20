// An art slot: a picture the game draws outside the reels (the mascot, the Instant Win prize, the bonus launcher,
// the trail's spaces). Follow a symbol (its chosen take, whatever that becomes), pick any image on the board, or
// make a new one: it's added to the Bonus screens category and generated straight away.
export const STAND_IN = key => `/slot-art/armadillo/flux2/${key}.png`;
export const SHORT = {armadillo: "Mascot", barrel: "Instant Win prize", cylinder: "Bonus launcher", t_coin: "Trail coins",
  t_gold: "Trail prizepot", t_snake: "Trail hazard", t_heart: "Trail heart", t_forward: "Trail forward", t_lightning: "Trail lightning",
  t_crate: "Trail coin crate", t_upgrade: "Trail moves doubled", t_double: "Trail coins doubled"};

export function artSlot(C, key) {
  const {el} = C, a = C.data.art[key];
  const sel = el("select", {ariaLabel: a.label},
    el("option", {value: "", textContent: "Armadillo's (stand-in)"}),
    el("optgroup", {label: "Follow a symbol's chosen take"}, ...C.data.symbols.map(s => el("option", {value: "sym:" + s.id, textContent: s.name}))),
    el("optgroup", {label: "An image on the board"},
      ...C.data.symbols.flatMap(s => s.refs.map((r, k) => el("option", {value: r, textContent: `${s.name}: reference ${k + 1}`}))),
      ...C.data.sources.map(p => el("option", {value: p, textContent: `Sheet: ${p.split("/")[1]}`}))));
  sel.value = a.value || "";
  sel.addEventListener("change", () => set(C, key, sel.value || null));
  const desc = el("input", {placeholder: "Describe it, e.g. 'a glowing photon torpedo'", ariaLabel: `Describe ${a.label}`});
  const make = el("div", {className: "controls", hidden: true}, desc, el("button", {type: "button", className: "primary", textContent: "Make it", onclick: async () => {
    if (!desc.value.trim()) return C.status("Describe it first.", "warn");
    const cat = C.data.categories.find(c => c.role == null) || C.data.categories[C.data.categories.length - 1];
    try {
      const {id} = await C.api("POST", `/api/slot-design/${C.did}/symbols`, {name: SHORT[key] || key, category: cat.id, kind: "object", prompt: desc.value});
      await C.api("PUT", `/api/slot-design/${C.did}/art-slots/${key}`, {value: "sym:" + id});
      await C.api("POST", `/api/slot-design/${C.did}/generate`);
      C.status(`Making three takes on the Art board (${cat.title}); this slot follows the chosen one.`, "ok");
      await C.refresh();
    } catch (e) { C.status(e.message, "warn"); }
  }}));
  return el("div", {className: "wz-slot"},
    el("img", {src: a.file ? C.img(a.file) : STAND_IN(key), alt: "", className: a.file ? "" : "standin"}),
    el("div", {className: "pane"}, el("b", {textContent: a.label}), sel,
      el("button", {type: "button", textContent: "＋ Make one", onclick: () => { make.hidden = !make.hidden; }}), make));
}

async function set(C, key, value) {
  try { await C.api("PUT", `/api/slot-design/${C.did}/art-slots/${key}`, {value}); await C.refresh(); }
  catch (e) { C.status(e.message, "warn"); }
}

// Is someone typing in this part of the page? (Polling and saves redraw a step, but never under the caret.)
export function typing(root) {
  const a = document.activeElement;
  return !!a && root.contains(a) && (a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && !["checkbox", "radio", "button", "color", "file", "range"].includes(a.type)));
}

// A value table as text ("1:40, 2:30") and back.
export const tableText = t => t.map(([v, w]) => `${v}:${w}`).join(", ");
export function parseTable(text) {
  return text.split(/[,;\n]+/).map(x => x.trim()).filter(Boolean).map(x => x.split(/[:×x*]/).map(n => +n.trim()));
}

// New feature or bonus ideas: described here, built later (Build turns them into code tasks).
export function specs(C, kind) {
  const {el} = C, list = (kind === "feature" ? C.data.features : C.data.bonuses).specs;
  const name = el("input", {placeholder: kind === "feature" ? "e.g. Red Alert" : "e.g. Away Team pick", ariaLabel: "Name"});
  const desc = el("textarea", {rows: 3, ariaLabel: "How it plays", placeholder: "How it plays: what triggers it, what happens, what it can pay"});
  const timing = el("select", {ariaLabel: "When"}, ...(kind === "feature"
    ? ["before the reels stop", "after the reels stop"] : ["from scatters", "from a random trigger", "bought"]).map(t => el("option", {value: t, textContent: t})));
  const art = el("input", {placeholder: "Pictures it needs (optional)", ariaLabel: "Pictures it needs"});
  return el("div", {className: "card"}, el("h3", {textContent: kind === "feature" ? "New feature ideas" : "New bonus ideas"}),
    el("p", {className: "hint", textContent: "Anything not in the library needs building (engine, mockup and game). Describe it here; the Build step turns it into a task, and once built it joins the library for every slot."}),
    ...list.map(x => el("div", {className: "wz-spec"}, el("b", {textContent: x.name}), el("span", {className: "tag gold", textContent: "spec · to build"}),
      el("span", {className: "hint", textContent: x.timing}), el("p", {textContent: x.description}),
      el("button", {type: "button", textContent: "Remove", onclick: async () => {
        try { await C.api("DELETE", `/api/slot-design/${C.did}/specs/${x.id}`); await C.refresh(); } catch (e) { C.status(e.message, "warn"); }
      }}))),
    el("div", {className: "grid2"}, el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
      el("label", {className: "field"}, el("span", {textContent: "When"}), timing),
      el("label", {className: "field", style: "grid-column: 1 / -1"}, el("span", {textContent: "How it plays"}), desc),
      el("label", {className: "field", style: "grid-column: 1 / -1"}, el("span", {textContent: "Pictures"}), art)),
    el("div", {className: "controls"}, el("button", {type: "button", textContent: "Add the idea", onclick: async () => {
      try {
        await C.api("POST", `/api/slot-design/${C.did}/specs`, {kind, name: name.value, description: desc.value, timing: timing.value, art: art.value});
        C.status("Idea saved for building.", "ok");
        await C.refresh();
      } catch (e) { C.status(e.message, "warn"); }
    }})));
}
