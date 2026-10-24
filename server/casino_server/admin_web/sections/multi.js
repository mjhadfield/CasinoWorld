// Ticking rows to act on several at once (the NPC roster and archive, Players). Each row has a box: click it to tick
// or untick that row, Shift-click to do the same to every row between it and the last one clicked (they all follow
// the last one's state), and Ctrl/Cmd-click a row to tick it without opening it. The header's box ticks every row
// shown, or clears them.
export class Picker {
  constructor(el, onChange) {
    this.el = el; this.onChange = onChange;
    this.ids = new Set(); this.anchor = null; this.order = [];
  }
  get size() { return this.ids.size; }
  has(id) { return this.ids.has(id); }
  shown(ids) { this.order = ids; }                 // the rows in the order they're shown, every render
  keep(all) {                                      // drop anyone who's gone
    const live = new Set(all);
    for (const id of this.ids) if (!live.has(id)) this.ids.delete(id);
  }
  clear() { this.ids.clear(); this.anchor = null; this.onChange(); }
  click(id, e) {
    const a = this.order.indexOf(this.anchor), b = this.order.indexOf(id);
    if (e.shiftKey && a >= 0 && b >= 0) {
      const on = this.ids.has(this.anchor);
      for (const x of this.order.slice(Math.min(a, b), Math.max(a, b) + 1)) on ? this.ids.add(x) : this.ids.delete(x);
    } else if (this.ids.has(id)) this.ids.delete(id);
    else this.ids.add(id);
    this.anchor = id;
    this.onChange();
  }
  // A row's box (a td), and the header's.
  box(id, label) {
    const input = this.el("input", {type: "checkbox", checked: this.ids.has(id), ariaLabel: "Tick " + label});
    input.addEventListener("click", e => { e.stopPropagation(); this.click(id, e); });
    return this.el("td", {className: "pick", onclick: e => e.stopPropagation()}, input);
  }
  head() {
    const n = this.order.filter(id => this.ids.has(id)).length;
    const input = this.el("input", {type: "checkbox", checked: n > 0 && n === this.order.length, indeterminate: n > 0 && n < this.order.length,
                                    ariaLabel: "Tick everyone shown", title: "Tick everyone shown, or clear"});
    input.addEventListener("click", () => {
      if (n === this.order.length) for (const id of this.order) this.ids.delete(id);
      else for (const id of this.order) this.ids.add(id);
      this.onChange();
    });
    return this.el("th", {className: "pick"}, input);
  }
  // Shift- or Ctrl/Cmd-clicking a row ticks it instead of opening it (Shift without selecting the text between).
  row(tr, id, open) {
    tr.addEventListener("mousedown", e => { if (e.shiftKey) e.preventDefault(); });
    tr.addEventListener("click", e => { if (e.shiftKey || e.ctrlKey || e.metaKey) this.click(id, e); else open(); });
  }
}

// Runs `call` for each picked id one after another; resolves to {done: [names], skipped: [[name, why]]}.
export async function each(items, call) {
  const done = [], skipped = [];
  for (const it of items) {
    try { await call(it); done.push(it.name); } catch (e) { skipped.push([it.name, e.message]); }
  }
  return {done, skipped};
}

// "Banned 3. Skipped 1: Mike (protected)." from each()'s result.
export function report(verb, {done, skipped}) {
  const why = m => /protected/i.test(m) ? "protected" : m.replace(/\.$/, "");
  const parts = [done.length ? `${verb} ${done.length}.` : `Nobody ${verb.toLowerCase()}.`];
  if (skipped.length) parts.push(`Skipped ${skipped.length}: ${skipped.map(([n, m]) => `${n} (${why(m)})`).join(", ")}.`);
  return parts.join(" ");
}
