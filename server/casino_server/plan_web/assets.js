// The asset library (the Floor plan tab's Assets view): built in Phase 4.
export function open({ app, el, done }) {
  app.replaceChildren(el("h3", { textContent: "Assets" }), el("p", { className: "hint", textContent: "Coming next: the furniture library." }),
    el("button", { textContent: "Back to the plan", onclick: done }));
}
