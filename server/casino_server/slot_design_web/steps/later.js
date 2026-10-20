// Steps not built yet: what each will do, so the whole wizard is visible from the start.
const ABOUT = {
  ladder: "Order the chosen symbols from highest to lowest value into the pay tiers (Wild, the two scatters, then the high, mid and low pays), with each tier's pays shown, and set the upgrade chain.",
  scene: "Generate or upload the background, render the logo lettering, and style the reel frame. The base-game mockup opens from here on.",
  features: "Pick the random features from Armadillo's library (Random Wilds, Wild Reels, Colossal Reels, Multiplier, Symbol Upgrade, Repeat Win, Instant Win), set their rates and art, or spec a new one.",
  bonuses: "Set up the bonus games: the Trail bonus, Combo free games, Buy Bonus and the shared Jackpot Pick, with their art, or spec a new bonus.",
  sprites: "Symbol win animations, the UI pieces (colours, font, spin button, win banners) and the floor cabinet's look, previewed here.",
  sounds: "Give the slot its own sounds for each moment (reels, wins, features, bonuses), from the library or uploads.",
  maths: "Set the pays and reel strips, simulate millions of spins, and tune the return to the Concept's target.",
  mockup: "Play the whole machine in the browser with live tweaks, check the rules screen, and sign it off.",
  build: "Export the signed-off design to a real cabinet on the casino floor.",
};

export function render(ctx, body) {
  body.append(ctx.el("div", {className: "card"},
    ctx.el("p", {className: "lead", textContent: ABOUT[ctx.step] || ""}),
    ctx.el("p", {className: "hint", textContent: "This step isn't built yet."})));
}
