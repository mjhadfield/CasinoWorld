// A design (the wizard's overview data) as the mockup's config: the variant, its art, logo, background, frame, look
// and texts. The maths (slots_math.js, the signed-off source shared with the docs mockup) loads once as a script.
let loading = null;
export function loadMath() {
  return loading ??= new Promise((res, rej) => {
    if (window.SlotMath) return res(window.SlotMath);
    const s = Object.assign(document.createElement("script"), {src: "/slot-design-ui/slots_math.js"});
    s.onload = () => res(window.SlotMath);
    s.onerror = () => rej(new Error("couldn't load slots_math.js"));
    document.head.append(s);
  });
}

const HOUSE_UI = "BarlowCondensed-Bold.ttf";
// The design's two fonts (its scene's), served by the server and added to the page so the canvas can use them.
const fontsLoaded = new Map();
export function fontFamily(did, name) {
  const family = "sd-" + (did + "-" + name).replace(/[^a-z0-9]+/gi, "-");
  if (!fontsLoaded.has(family)) {
    const face = new FontFace(family, `url(/slot-design-font/${did}/${encodeURIComponent(name)})`);
    fontsLoaded.set(family, face.load().then(f => { document.fonts.add(f); return f; }).catch(() => null));
  }
  return family;
}

// Feature and bonus pictures the base game and bonuses draw. Until a design gives its own (Features and Bonus
// games steps), Armadillo's painted set stands in.
export const EXTRA_ART = ["barrel", "armadillo", "cylinder", "t_coin", "t_double", "t_forward", "t_heart", "t_lightning",
  "t_crate", "t_upgrade", "t_gold", "t_snake", "b_hero", "b_enemy", "b_boss", "v_ship", "v_treasure", "v_wreck", "v_skull", "v_port",
  "v_cove", "v_final", "v_chest", "v_relic", "v_key", "v_art1", "v_art2", "v_art3", "v_art4"];
const armadillo = id => `/slot-art/armadillo/flux2/${id}.png`;

// Armadillo's per-reel symbol counts stretched to another tier shape: a tier Armadillo has keeps its count; an
// extra one (a fifth royal, a third high pay) copies the last tier of its group.
function stretch(counts, tiers) {
  return counts.map(c => {
    const out = {};
    for (const t of tiers) {
      if (c[t] != null) { out[t] = c[t]; continue; }
      const group = Object.keys(c).filter(k => k[0] === t[0] && k.length > 1 && /\d$/.test(k)).sort();
      out[t] = c[group[group.length - 1]] ?? 0;
    }
    return out;
  });
}

// The settings a design's variant is built from (SlotMath.makeVariant), as plain data the Maths step's worker can be
// sent: reel counts from the Maths step (or Armadillo's stretched to the tier shape), frozen strips once it's frozen.
export function designParams(data) {
  const M = window.SlotMath, A = M.ARMADILLO, lad = data.ladder;
  const paying = lad.tiers.filter(t => !["BS", "FS"].includes(t));
  const sym = t => data.symbols.find(s => s.id === lad.slots[t]);
  const symbols = Object.fromEntries(lad.tiers.map(t => [t, sym(t)?.name || A.symbols[t] || t]));
  const maths = data.maths || {}, f = data.features, b = data.bonuses, tr = b.trail, bt = b.battle, vy = b.voyage;
  // every tier's count (a scatter that starts no bonus is on the Value ladder's tiers no more, and stays at 0)
  const all = [...lad.tiers, ...b.unused_scatters];
  const counts = (maths.counts || stretch(A.counts, all)).map(c => ({...c, ...Object.fromEntries(b.unused_scatters.map(s => [s, 0]))}));
  return {
    id: data.id, name: data.name, symbols, pays: lad.pays, upgrades: lad.upgrades,
    strips: maths.strips || null, freeStrips: maths.free_strips || null, bigStrip: maths.big_strip || null,
    counts,
    bigCounts: maths.big_counts || stretch([A.bigCounts], paying)[0],
    features: f.enabled, rates: f.rates, freeRates: f.free_rates,
    wildCounts: f.tables.wild_counts, wildReelCounts: f.tables.wild_reel_counts, colossalSizes: f.tables.colossal_sizes,
    multipliers: f.tables.multipliers, repeats: f.tables.repeats, instants: f.tables.instants,
    trail: {length: tr.length, prizepot: tr.prizepot, counts: tr.counts, upgradeChance: tr.upgrade_chance,
            doubleChance: tr.double_chance, coins: tr.coins, crateRadius: tr.crate_radius},
    battle: {waves: bt.waves, shields: bt.shields, returnFire: bt.return_fire, prizes: bt.prizes, spinsChance: bt.spins_chance,
             spins: bt.spins, clear: bt.clear, bossHits: bt.boss_hits, bossFire: bt.boss_fire, boss: bt.boss},
    voyage: {legs: vy.legs, kinds: vy.kinds, coves: vy.coves, treasure: vy.treasure, relics: vy.relics, itemChance: vy.item_chance,
             keyChance: vy.key_chance, skull: vy.skull, sink: vy.sink, cove: vy.cove, relicValue: vy.relic_value,
             artefactPrice: vy.artefact_price, keyPrice: vy.key_price, spinsPrice: vy.spins_price, spinsGames: vy.spins_games,
             chest: vy.chest, parts: vy.parts, legend: vy.legend},
    freeGames: b.free.games, buyCost: b.routes.buy.length ? b.buy.cost : 0, routes: b.routes,
  };
}

// The deck's look with "frame" (match the reel frame) resolved; slot_design_build does the same for a built slot.
// sc is the chosen skin (scene.look.skin), which has the frame and deck.
const deckOf = sc => {
  const d = sc.deck || {style: "frame", colour: null};
  return {style: d.style === "frame" ? (sc.frame || {}).style || "metal" : d.style, colour: d.colour || null};
};

export function designConfig(data, img) {
  const M = window.SlotMath, A = M.ARMADILLO, lad = data.ladder, b = data.bonuses, tr = b.trail;
  const sym = t => data.symbols.find(s => s.id === lad.slots[t]);
  const V = M.makeVariant(designParams(data));
  const symbols = V.symbols;
  const art = {};
  for (const t of lad.tiers) {
    const s = sym(t);
    art[t] = s && s.file ? img(s.file) : (A.symbols[t] ? armadillo(t) : null);
  }
  for (const id of EXTRA_ART) art[id] = data.art[id] && data.art[id].file ? img(data.art[id].file) : armadillo(id);
  const sc = data.scene || {}, lk = sc.look;
  const logoLines = sc.logo && sc.logo.lines && sc.logo.lines.length ? sc.logo.lines : [data.name];
  return {
    variant: V, art,
    logo: sc.logo && sc.logo.file ? img(sc.logo.file) : null,
    background: sc.background ? img(sc.background) : null,
    frame: lk.skin.frame,
    deck: deckOf(lk.skin),
    skin: lk.skin,
    // a font without a glyph (StarTrek Film has no £) falls back to the house's interface font
    theme: {colours: lk.colours,
            display: `"${fontFamily(data.id, lk.fonts.display)}", "${fontFamily(data.id, HOUSE_UI)}", Georgia, serif`,
            cond: `"${fontFamily(data.id, lk.fonts.ui)}", "${fontFamily(data.id, HOUSE_UI)}", "Arial Narrow", system-ui, sans-serif`},
    win: data.sprites.win,
    featureNames: data.features.names,
    rules: data.signoff ? data.signoff.rules : null,
    labels: false,
    texts: {title: logoLines.map(l => l.toUpperCase()), tagline: "GOOD LUCK",
            bonus: [`3+ ${(symbols.BS || "BS").toUpperCase()}`, tr.name.toUpperCase()],
            free: [`3+ ${(symbols.FS || "FS").toUpperCase()}`, `${V.freeGames} ${b.free.name.toUpperCase()}`],
            freeName: b.free.name.toUpperCase(), pistol: tr.launcher.toUpperCase(), trailHint: tr.hint,
            battle: b.battle.name.toUpperCase(), battleHint: b.battle.hint, enemy: b.battle.enemy.toUpperCase(),
            boss: b.battle.boss_name.toUpperCase(), voyage: voyageTexts(b.voyage)},
  };
}

// The voyage's words as the mockup's screen uses them (the built game's are theme.texts voyage_*).
export function voyageTexts(v) {
  const up = s => String(s).toUpperCase();
  return {name: up(v.name), hint: v.hint, start: up(v.start), final: up(v.final), treasure: up(v.treasure_name), wreck: up(v.wreck_name),
          skull: up(v.skull_name), port: up(v.port_name), cove: up(v.cove_name), relic: up(v.relic), chest: up(v.chest_name),
          legend: up(v.legend_name), artefacts: v.artefacts.map(up)};
}
