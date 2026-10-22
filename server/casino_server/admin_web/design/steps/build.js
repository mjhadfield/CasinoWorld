// Step 11, Build: the signed-off slot becomes a game the casino plays. Build writes its build folder
// (server/slot_builds/<id>/), and Install restarts the casino to load it: its art, fonts and sounds reach every game.
// Its cabinets go on the floor from the Floor plan tab, anywhere, mixed with other slots. New feature or bonus ideas
// are listed for building.
let C;

export function render(ctx, body) { C = ctx; draw(body); }
export function update(ctx) { C = ctx; const body = document.querySelector(".wz-body"); if (body && !body.querySelector("select:focus, input:focus")) draw(body); }

function draw(body) {
  const {el} = C, b = C.data.build, d = C.data;
  const go = el("button", {type: "button", className: "primary", textContent: b.built ? "Build it again" : "Build it", disabled: !b.signed_off, onclick: async () => {
    go.disabled = true;
    try {
      await C.api("POST", `/api/slot-design/${C.did}/build`);
      await C.refresh();
      C.status(b.live ? "Built. Install restarts the casino to bring it in; then put it on the floor from the Floor plan tab." : "Built into this instance's folder.", "ok");
    } catch (e) { C.status(e.message, "warn"); go.disabled = false; }
  }});
  const install = el("button", {type: "button", className: "primary", textContent: "Install: restart the casino", disabled: !b.built || !b.live, onclick: async () => {
    if (!confirm("Restart the casino now? Anyone playing is stood up for a few seconds while it comes back.")) return;
    try { const r = await C.api("POST", `/api/slot-design/${C.did}/install`); C.status(r.message, "ok"); }
    catch (e) { C.status(e.message, "warn"); }
  }});
  body.replaceChildren(
    el("p", {className: "lead"}, "The signed-off slot becomes a game the casino plays. Its cabinets go on the floor from the ",
      el("a", {href: "#plan", textContent: "Floor plan tab"}), ": any number, anywhere, beside other slots."),
    b.signed_off ? null : el("div", {className: "card"}, el("span", {className: "tag warn", textContent: "Not signed off"}),
      el("p", {className: "hint"}, "Sign it off on ", el("a", {href: `#design/${C.did}/mockup`, textContent: "Mockup & sign-off"}), " first.")),
    el("div", {className: "wz-cards"},
      el("div", {className: "card"}, el("h3", {textContent: "Build"}),
        el("p", {className: "hint", textContent: "Writes the slot's maths, pictures, fonts and sounds into its build folder."}),
        el("div", {className: "controls"}, go),
        el("p", {className: "hint"}, b.on_floor ? `On the floor: ${b.on_floor} cabinet${b.on_floor === 1 ? "" : "s"}. ` : "No cabinets on the floor yet. ",
          el("a", {href: "#plan", textContent: "Place them on the Floor plan tab"}), ".")),
      el("div", {className: "card"}, el("h3", {textContent: "Install"}),
        b.built ? el("p", {className: "hint", textContent: `Built ${String(b.built.at || "").replace("T", " ")}. ${b.built.loaded ? "The casino has loaded it." : "Not loaded yet."}`})
          : el("p", {className: "hint", textContent: "Build it first."}),
        b.live ? install : el("p", {className: "hint", textContent: "This is a dev or test instance: restart it (tools/dev.sh server) to load the build."}),
        el("p", {className: "hint", textContent: "Each build after the first needs only this restart: the game picks up new slots, their art, fonts and sounds by itself."})),
      el("div", {className: "card"}, el("h3", {textContent: "Ideas to build in code"}),
        b.ideas.length ? el("ul", {}, ...b.ideas.map(x => el("li", {}, el("b", {textContent: x.name}), ` (${x.kind}): ${x.description}`)))
          : el("p", {className: "hint", textContent: "None: everything in this slot is in the library."}),
        b.ideas.length ? el("p", {className: "hint", textContent: `They're written to the build folder's IDEAS.md for building; until then the slot plays without them.`}) : null)));
}
