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

// Feature and bonus pictures the base game and bonuses draw. Until a design gives its own (Features and Bonus
// games steps), Armadillo's painted set stands in.
export const EXTRA_ART = ["barrel", "armadillo", "cylinder", "t_coin", "t_double", "t_forward", "t_heart", "t_lightning",
  "t_crate", "t_upgrade", "t_gold", "t_snake"];
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

export function designConfig(data, img) {
  const M = window.SlotMath, A = M.ARMADILLO, lad = data.ladder;
  const pays = Object.fromEntries(Object.entries(lad.pays).map(([k, v]) => [k, v]));
  const paying = lad.tiers.filter(t => !["BS", "FS"].includes(t));
  const sym = t => data.symbols.find(s => s.id === lad.slots[t]);
  const symbols = Object.fromEntries(lad.tiers.map(t => [t, sym(t)?.name || A.symbols[t] || t]));
  const maths = data.maths || {}, f = data.features, b = data.bonuses, tr = b.trail;
  const V = M.makeVariant({
    ...A, strips: maths.strips || null, freeStrips: maths.free_strips || null, bigStrip: maths.big_strip || null,
    id: data.id, name: data.name, symbols, pays, upgrades: lad.upgrades,
    counts: maths.counts || stretch(A.counts, lad.tiers),
    bigCounts: maths.big_counts || stretch([A.bigCounts], paying)[0],
    features: f.enabled, rates: f.rates, freeRates: f.free_rates,
    wildCounts: f.tables.wild_counts, wildReelCounts: f.tables.wild_reel_counts, colossalSizes: f.tables.colossal_sizes,
    multipliers: f.tables.multipliers, repeats: f.tables.repeats, instants: f.tables.instants,
    trail: {length: tr.length, prizepot: tr.prizepot, counts: tr.counts, upgradeChance: tr.upgrade_chance,
            doubleChance: tr.double_chance, coins: tr.coins, crateRadius: tr.crate_radius},
    freeGames: b.free.games, buyCost: b.buy.enabled ? b.buy.cost : 0,
  });
  const art = {};
  for (const t of lad.tiers) {
    const s = sym(t);
    art[t] = s && s.file ? img(s.file) : (A.symbols[t] ? armadillo(t) : null);
  }
  for (const id of EXTRA_ART) art[id] = data.art[id] && data.art[id].file ? img(data.art[id].file) : armadillo(id);
  const sc = data.scene || {};
  const logoLines = sc.logo && sc.logo.lines && sc.logo.lines.length ? sc.logo.lines : [data.name];
  return {
    variant: V, art,
    logo: sc.logo && sc.logo.file ? img(sc.logo.file) : null,
    background: sc.background ? img(sc.background) : null,
    frame: sc.frame || {style: "metal", colour: "#c9a24a"},
    theme: (data.sprites && data.sprites.theme) || {},
    labels: false,
    texts: {title: logoLines.map(l => l.toUpperCase()), tagline: "GOOD LUCK",
            bonus: [`3+ ${symbols.BS.toUpperCase()}`, tr.name.toUpperCase()],
            free: [`3+ ${symbols.FS.toUpperCase()}`, `${V.freeGames} ${b.free.name.toUpperCase()}`],
            freeName: b.free.name.toUpperCase(), pistol: tr.launcher.toUpperCase(), trailHint: tr.hint},
  };
}
