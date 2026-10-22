// Step 3, Value ladder: put the final set in order of value. Each tier (Wild, the two scatters, then the high, mid
// and low pays) takes one symbol; its pays are shown (the Maths step tunes them), with the tier it upgrades to.
// Drag a symbol onto a tier, or click a symbol and then a tier. Every change saves at once.
let C, picked = null, showAll = false;

const ROYAL_ORDER = ["A", "K", "Q", "J", "10", "9", "8", "7"];
const SPECIAL = {W: "Wild: stands in for every pay symbol", BS: "Bonus scatter: 3+ start the bonus game",
                 FS: "Free-spins scatter: 3+ start the free games"};
const GROUPS = [["Specials", t => t in SPECIAL], ["High pays", t => t[0] === "H"], ["Mid pays", t => t[0] === "M"], ["Low pays", t => t[0] === "L"]];

export function render(ctx, body) { C = ctx; body.append(C.el("div", {className: "lad"})); draw(body.firstChild); }
export function update(ctx) { C = ctx; const root = document.querySelector(".lad"); if (root) draw(root); }

const symOf = id => C.data.symbols.find(s => s.id === id);

async function save(slots, upgrades) {
  try {
    await C.api("PUT", `/api/slot-design/${C.did}/ladder`, {slots, upgrades});
    if (C.data.steps.find(s => s.id === "ladder").status === "todo") await C.setStep("ladder", "doing");
    else await C.refresh();
  } catch (e) { C.status(e.message, "warn"); }
}

function place(tier, sid) {
  const slots = {...C.data.ladder.slots};
  const from = Object.keys(slots).find(t => slots[t] === sid);
  if (from) { if (slots[tier]) slots[from] = slots[tier]; else delete slots[from]; }  // a move swaps with what's there
  slots[tier] = sid;
  picked = null;
  save(slots, C.data.ladder.upgrades);
}

function autoFill() {
  const d = C.data, lad = d.ladder;
  const pool = d.symbols.filter(s => s.keep).length ? d.symbols.filter(s => s.keep) : d.symbols;
  const role = r => { const cat = d.categories.find(c => c.role === r); return cat ? pool.filter(s => s.category === cat.id) : []; };
  const slots = {};
  const sp = role("specials"), taken = new Set();
  const grab = re => { const s = sp.find(x => !taken.has(x.id) && re.test(`${x.name} ${x.keep_text || ""} ${x.id}`)); if (s) taken.add(s.id); return s; };
  for (const [t, re] of [["W", /wild/i], ["FS", /free/i], ["BS", /bonus|scatter/i]]) { const s = grab(re); if (s) slots[t] = s.id; }
  for (const t of ["W", "BS", "FS"]) if (!slots[t]) { const s = sp.find(x => !taken.has(x.id)); if (s) { slots[t] = s.id; taken.add(s.id); } }
  const fill = (prefix, list) => lad.tiers.filter(t => t[0] === prefix && t.length > 1 && !(t in SPECIAL)).forEach((t, i) => { if (list[i]) slots[t] = list[i].id; });
  fill("H", role("high"));
  fill("M", role("mid"));
  const rank = s => { const i = ROYAL_ORDER.indexOf(String(s.name).trim().toUpperCase()); return i < 0 ? 99 : i; };
  fill("L", [...role("low")].sort((a, b) => rank(a) - rank(b)));
  save(slots, lad.upgrades);
}

function draw(root) {
  const {el} = C, d = C.data, lad = d.ladder;
  const placed = new Set(Object.values(lad.slots));
  const pool = d.symbols.filter(s => showAll || s.keep);
  const card = (s, small) => el("span", {className: "lad-sym" + (small ? " small" : "")},
    s.file ? el("img", {src: C.img(s.file), alt: ""}) : el("span", {className: "noart", textContent: "?"}), el("span", {textContent: s.name}));

  const palette = el("div", {className: "lad-pal"}, ...pool.map(s => {
    const b = el("button", {type: "button", draggable: true, ariaPressed: String(picked === s.id),
      className: placed.has(s.id) ? "placed" : "", title: placed.has(s.id) ? "Already in a tier: drop it on another to swap" : "Pick, then click a tier",
      onclick: () => { picked = picked === s.id ? null : s.id; draw(root); }}, card(s));
    b.addEventListener("dragstart", e => { e.dataTransfer.setData("text/plain", s.id); });
    return b;
  }));
  if (!pool.length) palette.append(el("p", {className: "hint", textContent: "Nothing is in the final set yet: tick symbols on the Art step, or show every symbol."}));

  const upSel = t => {
    if (t in SPECIAL || t === "H1") return el("span", {className: "hint", textContent: t === "H1" ? "top tier" : ""});
    const higher = lad.tiers.slice(3, lad.tiers.indexOf(t));
    const sel = el("select", {ariaLabel: `${t} upgrades to`}, ...higher.map(h => el("option", {value: h, textContent: `→ ${h}`})));
    sel.value = lad.upgrades[t] || higher[higher.length - 1];
    sel.addEventListener("change", () => save(lad.slots, {...lad.upgrades, [t]: sel.value}));
    return el("label", {className: "lad-up", title: "Symbol Upgrade turns this into"}, "upgrades", sel);
  };
  const move = (t, dir, tiers) => {
    const j = tiers.indexOf(t) + dir, other = tiers[j];
    if (!other) return;
    const slots = {...lad.slots};
    [slots[t], slots[other]] = [slots[other], slots[t]];
    for (const k of [t, other]) if (!slots[k]) delete slots[k];
    save(slots, lad.upgrades);
  };

  const groups = GROUPS.map(([title, test]) => {
    const tiers = lad.tiers.filter(test);
    return el("div", {className: "lad-group"}, el("h3", {textContent: title}), ...tiers.map((t, i) => {
      const s = symOf(lad.slots[t]), pays = lad.pays[t];
      const slot = el("div", {className: "lad-slot" + (s ? "" : " empty") + (picked ? " target" : ""), tabIndex: 0,
        onclick: () => picked && place(t, picked), onkeydown: e => { if (e.key === "Enter" && picked) place(t, picked); }},
        s ? card(s, true) : el("span", {className: "hint", textContent: picked ? "Click to put it here" : "Drop a symbol here"}));
      slot.addEventListener("dragover", e => { e.preventDefault(); slot.classList.add("over"); });
      slot.addEventListener("dragleave", () => slot.classList.remove("over"));
      slot.addEventListener("drop", e => { e.preventDefault(); place(t, e.dataTransfer.getData("text/plain")); });
      return el("div", {className: "lad-row"},
        el("span", {className: "tag gold lad-tier", textContent: t, title: SPECIAL[t] || ""}), slot,
        el("span", {className: "lad-pays", textContent: pays ? `3 ${pays[0]} · 4 ${pays[1]} · 5 ${pays[2]}` : SPECIAL[t] || "", title: pays ? "Pays for 3, 4 and 5 on a line, in line bets" : ""}),
        upSel(t),
        el("span", {className: "lad-move"},
          s && !(t in SPECIAL) ? el("button", {type: "button", className: "icon", textContent: "▲", ariaLabel: `Move ${s.name} up`, disabled: i === 0, onclick: () => move(t, -1, tiers)}) : null,
          s && !(t in SPECIAL) ? el("button", {type: "button", className: "icon", textContent: "▼", ariaLabel: `Move ${s.name} down`, disabled: i === tiers.length - 1, onclick: () => move(t, 1, tiers)}) : null,
          s ? el("button", {type: "button", className: "icon", textContent: "✕", ariaLabel: `Take ${s.name} out`, onclick: () => {
            const slots = {...lad.slots}; delete slots[t]; save(slots, lad.upgrades); }}) : null));
    }));
  });

  const filled = Object.keys(lad.slots).length;
  root.replaceChildren(
    el("p", {className: "lead", textContent: "Order the final set by value, highest first. Each tier holds one symbol; the pays shown are the house standard until the Maths step tunes them, and Symbol Upgrade turns a symbol into the tier chosen beside it."}),
    el("div", {className: "dz-bar"},
      el("span", {className: "tag " + (lad.complete ? "ok" : "gold"), textContent: `${filled} of ${lad.tiers.length} tiers filled`}),
      el("label", {className: "confirm"}, el("input", {type: "checkbox", checked: showAll, onchange: e => { showAll = e.target.checked; draw(root); }}), "Show every symbol, not just the final set"),
      el("span", {className: "grow"}),
      el("button", {type: "button", textContent: "Auto-fill from the Art step", title: "Specials by name, then each category in order (royals A, K, Q, J, 10…)", onclick: autoFill}),
      el("button", {type: "button", textContent: "Default upgrade chain", onclick: () => save(lad.slots, lad.default_upgrades)}),
      el("button", {type: "button", textContent: "Clear", onclick: () => confirm("Empty every tier?") && save({}, lad.upgrades)})),
    el("div", {className: "lad-cols"}, el("div", {className: "pane"}, el("h3", {textContent: picked ? `Placing ${symOf(picked).name}: click a tier` : "Symbols"}), palette),
      el("div", {className: "pane"}, ...groups)));
}
