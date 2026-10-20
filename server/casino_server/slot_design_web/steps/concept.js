// Step 1, Concept: the slot's name, the theme brief that leads every FLUX prompt, the tier shape (which sets how
// many symbols the Art step needs), the target return and volatility, and the sheet cutter: upload a reference
// sheet, drag a box round each symbol, name it, and cut them all into new symbols waiting for Generate.
let C, cutter = null, sheetCard = null;

export function render(ctx, body) {
  C = ctx;
  const {el} = C, d = C.data, c = d.concept;
  const name = el("input", {value: d.name, ariaLabel: "Name"});
  const brief = el("textarea", {rows: 3, value: c.brief, ariaLabel: "Theme brief",
    placeholder: "e.g. Star Trek: The Original Series and The Next Generation, bold and glossy"});
  const style = el("textarea", {rows: 2, value: c.style, ariaLabel: "Style notes",
    placeholder: "Optional: how the art should look, e.g. 'premium mobile slot art, rich colours, gold trim'"});
  const tier = (k, label) => {
    const i = el("input", {type: "number", min: 1, max: 8, value: c.tiers[k]});
    i.dataset.tier = k;
    return el("label", {className: "field"}, el("span", {textContent: label}), i);
  };
  const rtp = el("input", {type: "number", min: 85, max: 98, step: 0.1, value: c.target_rtp, ariaLabel: "Target return"});
  const vol = el("select", {ariaLabel: "Volatility"}, ...["low", "medium", "high"].map(v => el("option", {value: v, textContent: v[0].toUpperCase() + v.slice(1)})));
  vol.value = c.volatility;
  const tiers = el("div", {className: "grid2"}, tier("high", "High pays (Symbol set 1)"), tier("mid", "Mid pays (Symbol set 2)"),
    tier("low", "Low pays (Royals)"), el("div", {className: "field"}, el("span", {textContent: "Specials"}),
      el("span", {className: "hint", textContent: "3: the Wild, the bonus scatter and the free-spins scatter"})));

  const save = async () => {
    const t = {};
    for (const i of tiers.querySelectorAll("input[data-tier]")) t[i.dataset.tier] = +i.value;
    try {
      await C.api("PATCH", `/api/slot-design/${C.did}/concept`,
        {name: name.value, brief: brief.value, style: style.value, tiers: t, target_rtp: +rtp.value, volatility: vol.value});
      if (C.data.steps.find(s => s.id === "concept").status === "todo") await C.setStep("concept", "doing");
      else await C.refresh();
      C.status("Concept saved.", "ok");
    } catch (e) { C.status(e.message, "warn"); }
  };

  body.append(
    el("p", {className: "lead", textContent: "What the slot is. The theme brief and style lead every picture FLUX makes for it, so the whole set belongs together. The tier shape sets how many symbols the Art step needs."}),
    el("div", {className: "two"},
      el("div", {className: "pane"},
        el("div", {className: "card"},
          el("label", {className: "field"}, el("span", {textContent: "Name"}), name),
          el("label", {className: "field"}, el("span", {textContent: "Theme brief"}), brief),
          el("label", {className: "field"}, el("span", {textContent: "Style notes"}), style)),
        el("div", {className: "card"}, el("h3", {textContent: "Tier shape"}), tiers,
          el("p", {className: "hint", textContent: "The house standard (Armadillo Goes West) is 2 high, 4 mid and 4 low. The Value ladder step orders the chosen symbols into these tiers."})),
        el("div", {className: "card"}, el("h3", {textContent: "Return"}),
          el("div", {className: "grid2"},
            el("label", {className: "field"}, el("span", {textContent: "Target return, %"}), rtp),
            el("label", {className: "field"}, el("span", {textContent: "Volatility"}), vol)),
          el("p", {className: "hint", textContent: "Armadillo returns about 91.5%, plus 3.75% from the shared jackpots. The Maths step tunes the reels to the target."})),
        el("div", {className: "controls"}, el("button", {type: "button", className: "primary", textContent: "Save the concept", onclick: save}))),
      el("div", {className: "pane"},
        el("div", {className: "card"}, el("h3", {textContent: "House standard"}),
          el("p", {className: "hint", textContent: "5 reels × 4 rows, 25 fixed lines paying left to right; Wild stands in for everything but the scatters; total bets 25p, 50p, 75p, £1, £1.50, £2.50, £5, £10 and £25; the shared Jackpot Pick (Mini, Minor, Major, Grand)."})),
        sheetCard = sheets())));
}

// Polling while jobs run mustn't wipe the form: only the sheets card redraws, and only when asked ("sheets").
export function update(ctx, what) {
  C = ctx;
  if (what === "sheets" && sheetCard) { const fresh = sheets(); sheetCard.replaceWith(fresh); sheetCard = fresh; }
}

// ------------------------------------------------------------------ the sheet cutter
function sheets() {
  const {el} = C, d = C.data;
  const file = el("input", {type: "file", accept: "image/png,image/jpeg,image/webp", ariaLabel: "Upload a reference sheet"});
  file.addEventListener("change", async () => {
    const f = file.files[0];
    if (!f) return;
    try {
      const {path} = await C.api("PUT", `/api/slot-design/${C.did}/sources/${encodeURIComponent(f.name)}`, await f.arrayBuffer(), true);
      cutter = {sheet: path, boxes: []};
      await C.refresh("sheets");
    } catch (e) { C.status(e.message, "warn"); }
  });
  const work = el("div");
  if (cutter && d.sources.includes(cutter.sheet)) work.append(cutterView());
  return el("div", {className: "card"}, el("h3", {textContent: "Reference sheets"}),
    el("p", {className: "hint", textContent: "Upload a sheet of symbol ideas, then drag a box round each one. Every box becomes a new symbol with that crop as its reference, waiting for Generate on the Art step."}),
    el("div", {className: "dz-strip"}, ...d.sources.map(p => el("button", {type: "button", title: p.split("/")[1],
      ariaPressed: String(cutter?.sheet === p), onclick: () => { cutter = {sheet: p, boxes: []}; C.refresh("sheets"); }},
      el("img", {src: C.img(p), alt: p, loading: "lazy", className: "wide"})))),
    el("div", {className: "controls"}, file), work);
}

function cutterView() {
  const {el} = C, d = C.data;
  const img = el("img", {src: C.img(cutter.sheet), alt: "Reference sheet", draggable: false});
  const layer = el("div", {className: "cut-layer"});
  const stage = el("div", {className: "cut-stage"}, img, layer);
  const list = el("div", {className: "pane"});
  const catOpts = () => d.categories.map(c => el("option", {value: c.id, textContent: c.title}));
  const scale = () => img.naturalWidth / img.clientWidth;

  const drawBoxes = () => {
    const k = 1 / scale();
    layer.replaceChildren(...cutter.boxes.map((b, i) => el("div", {className: "cut-box",
      style: `left:${b.x * k}px;top:${b.y * k}px;width:${b.w * k}px;height:${b.h * k}px`}, el("span", {textContent: b.name || i + 1}))));
    list.replaceChildren(...cutter.boxes.map((b, i) => {
      const name = el("input", {value: b.name, placeholder: `Symbol ${i + 1}`, ariaLabel: `Box ${i + 1} name`});
      name.addEventListener("input", () => { b.name = name.value; layer.children[i].firstChild.textContent = b.name || i + 1; });
      const cat = el("select", {ariaLabel: `Box ${i + 1} category`}, ...catOpts());
      cat.value = b.category;
      const kind = el("select", {ariaLabel: `Box ${i + 1} kind`}, el("option", {value: "object", textContent: "Object"}),
        el("option", {value: "character", textContent: "Character"}));
      kind.value = b.kind;
      cat.addEventListener("change", () => { b.category = cat.value; b.kind = kind.value = d.categories.find(c => c.id === cat.value).kind || "object"; });
      kind.addEventListener("change", () => { b.kind = kind.value; });
      const key = el("select", {ariaLabel: `Box ${i + 1} background`}, el("option", {value: "magenta", textContent: "Magenta"}),
        el("option", {value: "green", textContent: "Green (purple art)"}));
      key.value = b.key;
      key.addEventListener("change", () => { b.key = key.value; });
      return el("div", {className: "cut-row"}, el("b", {textContent: i + 1}), name, cat, kind, key,
        el("button", {type: "button", textContent: "✕", ariaLabel: `Remove box ${i + 1}`, onclick: () => { cutter.boxes.splice(i, 1); drawBoxes(); }}));
    }));
    go.disabled = !cutter.boxes.length;
    go.textContent = cutter.boxes.length ? `Cut ${cutter.boxes.length} into symbols` : "Draw boxes on the sheet";
  };

  // Drag to draw a box (mouse, pen or touch). Coordinates are kept in the sheet's own pixels.
  let start = null, ghost = null;
  const at = e => { const r = img.getBoundingClientRect(); return [(e.clientX - r.left) * scale(), (e.clientY - r.top) * scale()]; };
  stage.addEventListener("pointerdown", e => {
    if (e.target.closest(".cut-box")) return;
    start = at(e); stage.setPointerCapture(e.pointerId);
    ghost = el("div", {className: "cut-box ghost"}); layer.append(ghost);
  });
  stage.addEventListener("pointermove", e => {
    if (!start) return;
    const [x, y] = at(e), k = 1 / scale();
    Object.assign(ghost.style, {left: Math.min(x, start[0]) * k + "px", top: Math.min(y, start[1]) * k + "px",
      width: Math.abs(x - start[0]) * k + "px", height: Math.abs(y - start[1]) * k + "px"});
  });
  stage.addEventListener("pointerup", e => {
    if (!start) return;
    const [x, y] = at(e);
    const b = {x: Math.min(x, start[0]), y: Math.min(y, start[1]), w: Math.abs(x - start[0]), h: Math.abs(y - start[1])};
    start = null; ghost.remove();
    if (b.w >= 16 && b.h >= 16) {
      const cat = d.categories.find(c => c.role === "mid") || d.categories[0];
      cutter.boxes.push({...b, name: "", category: cat.id, kind: cat.kind || "object", key: "magenta"});
    }
    drawBoxes();
  });
  img.addEventListener("load", drawBoxes);
  window.addEventListener("resize", () => img.isConnected && drawBoxes());

  const go = el("button", {type: "button", className: "primary", onclick: async () => {
    try {
      const {made} = await C.api("POST", `/api/slot-design/${C.did}/cuts`, {sheet: cutter.sheet, boxes: cutter.boxes});
      C.status(`Cut ${made.length} new symbol${made.length === 1 ? "" : "s"}: press Generate on the Art step to draw them.`, "ok");
      cutter.boxes = [];
      await C.refresh("sheets");
    } catch (e) { C.status(e.message, "warn"); }
  }});
  const wrap = el("div", {className: "pane"}, el("p", {className: "hint", textContent: `Cutting ${cutter.sheet.split("/")[1]}: drag on the sheet to box a symbol.`}),
    stage, list, el("div", {className: "controls"}, go,
      el("button", {type: "button", textContent: "Close", onclick: () => { cutter = null; C.refresh("sheets"); }})));
  if (img.complete) queueMicrotask(drawBoxes);
  return wrap;
}
