// The table designer's renderer: draws a table in a table style, from the game's real geometry
// (geometry.json, made by tools/table_geometry.gd). For the card tables it is the signed-off mockup's renderer
// (docs/table_styles/mockup/index.html); Roulette and Craps are ports of rou_felt.gd and crp_felt.gd. It draws
// with the game's own tiles and fonts, and the game's StyledFelt draws the same way, so what's designed here is
// what the floor shows. Positions never depend on the style.

let G = null;        // the geometry
const TEX = {};      // the tiles, by name

/** Loads the geometry, tiles and fonts from `base` (the folder this file is served from). */
export async function loadAssets(base) {
  G = await fetch(base + "geometry.json").then(r => { if (!r.ok) throw new Error("no geometry.json"); return r.json(); });
  const files = { mahogany: "wood_mahogany.jpg", walnut: "wood_walnut.jpg", wenge: "wood_wenge.jpg", rosewood: "wood_rosewood.jpg",
    ebony: "wood_ebony.jpg", leather: "leather_shade.png", grain: "felt_grain.png", weave: "weave_shade.png", velvet: "velvet_shade.png", carpet: "carpet.png", dealer: "dealer.png" };
  await Promise.all(Object.entries(files).map(([k, f]) => new Promise(res => { const i = new Image(); i.onload = () => { TEX[k] = i; res(); };
    i.onerror = () => { const c = document.createElement("canvas"); c.width = c.height = 4; TEX[k] = c; res(); }; i.src = base + "textures/" + f; })));
  await Promise.all(Object.entries(FONT_FILES).map(([family, [file, weight]]) =>
    new FontFace(family, `url(${base}fonts/${file})`, { weight }).load().then(f => document.fonts.add(f)).catch(() => {})));
}
export const geometry = () => G;

// ---------------------------------------------------------------- the options
export const FELTS = [["Crimson", "#93141f"], ["Burgundy", "#6a1424"], ["Emerald", "#0f5b3f"], ["Forest", "#1d4a2a"], ["Navy", "#14284a"],
  ["Teal", "#0f4a4f"], ["Royal blue", "#1a3f93"], ["Plum", "#4a1d47"], ["Charcoal", "#2b2f33"]];
export const LEATHERS = [["Black", "#1b1a1a"], ["Oxblood", "#4a1418"], ["Tan", "#7a4a26"], ["Navy", "#1a2234"], ["Bone", "#cfc3a8"]];
export const INKS = [["Cream", "#f1e4c4"], ["Champagne", "#e8d3a0"], ["Gold", "#d9b56a"], ["White", "#f4f4f2"], ["Silver", "#c9d0d6"]];
export const LEDS = [["Ice", "#8fd3ff"], ["Warm white", "#ffd28a"], ["Magenta", "#ff4fd8"], ["Red", "#ff3b3b"], ["Green", "#4dff9a"], ["Violet", "#9a7bff"]];
export const TINTS = [["Red smoke", "#6b0f19"], ["Black", "#141416"], ["Smoke grey", "#1e2328"], ["Amber", "#7a4a0c"], ["Sapphire", "#12305e"], ["Bottle green", "#0f4a2c"]];
export const HOUSINGS = [["Gunmetal", "#3a3e44"], ["Black", "#1c1e22"], ["Bronze", "#4a3a2a"], ["Navy", "#1f2a3d"], ["Burgundy", "#4a1a22"], ["Pearl", "#cfccc4"]];
// The spot glow's colours (table_styles HOUSE's glow is Champagne).
const GLOWS = [["Champagne", "#ffdf9e"], ["Warm white", "#fff2dc"], ["Gold", "#f0c75e"], ["Ice", "#8fd3ff"], ["Mint", "#7ef0c1"],
  ["Rose", "#ff9db8"], ["Violet", "#b9a3ff"], ["Red", "#ff5a5a"]];
export const ACCENTS = [["Brass", "#c9a24a"], ["Gold", "#e0b84e"], ["Copper", "#c8794a"], ["Chrome", "#b9c3cb"], ["Ice", "#8fd3ff"], ["Jade", "#7fc8a9"]];
export const WOODS = {
  mahogany: { label: "Mahogany", tex: "mahogany", tile: 58 },
  walnut: { label: "Walnut", tex: "walnut", tile: 52 },
  wenge: { label: "Wenge", tex: "wenge", tile: 46 },
  rosewood: { label: "Rosewood", tex: "rosewood", tile: 64 },
  ebony: { label: "Ebony lacquer", tex: "ebony", tile: 48, gloss: true },
};
export const WOOD_PICKS = [["match", "Match the rail"], ...Object.entries(WOODS).map(([k, v]) => [k, v.label])];
function woodTex(D, pick) { return WOODS[pick === "match" || !WOODS[pick] ? D.rail.wood : pick].tex; }
export const BEADS = { brass: ["#c9a24a", "#f3d78e"], gold: ["#d9b453", "#fff0b8"], chrome: ["#aeb7bf", "#ffffff"], none: null };
export const FONTS = { cinzel: ["TS Cinzel", 600, "Cinzel"], cormorant: ["TS Cormorant", 700, "Cormorant SC"], josefin: ["TS Josefin", 600, "Josefin Sans (Deco)"], montserrat: ["TS Montserrat", 600, "Montserrat"] };
// The game's own font files (client/assets/fonts), copied beside this by tools/build_table_tiles.py.
const FONT_FILES = { "TS Cinzel": ["Cinzel-SemiBold.ttf", "600"], "TS Cormorant": ["CormorantSC-Bold.ttf", "700"], "TS Josefin": ["JosefinSans-SemiBold.ttf", "600"],
  "TS Montserrat": ["Montserrat-SemiBold.ttf", "600"], "TS DejaVu": ["DejaVuSans-Bold.ttf", "700"] };
const SANS = '"TS DejaVu", "DejaVu Sans", sans-serif';   // the game's chip, card and display lettering
export const BACKS = { charcoal: "Framed", lattice: "Lattice", sunburst: "Sunburst", monogram: "Monogram", stripe: "Stripe" };
// Each back's colour before the colour was its own choice (table_styles.BACK_MAIN): a design without backColour takes it.
export const BACK_MAIN = { charcoal: "#34373c", lattice: "#8e1a22", sunburst: "#4d1616", monogram: "#5a1322", stripe: "#141414", emerald: "#145238" };
export const backColour = D => D.backColour || BACK_MAIN[D.back] || BACK_MAIN.charcoal;
const BACK_COLOURS = [["Charcoal", "#34373c"], ["Red", "#8e1a22"], ["Garnet", "#4d1616"], ["Burgundy", "#5a1322"], ["Black", "#141414"],
  ["Emerald", "#145238"], ["Navy", "#14284a"], ["Royal blue", "#1a3f93"], ["Plum", "#4a1d47"]];
const CARD_COLOURS = [["White", "#f4f2ec"], ["Ivory", "#efe4c8"], ["Silver", "#cfd3d6"], ["Gold", "#d9b453"], ["Black", "#1c1c1e"]];
export const FRONTS = { classic: "Classic (today)", jumbo: "Jumbo index", vintage: "Vintage", minimal: "Minimal" };
// The chairs' frame metals (Seating.METALS) and upholstery.
export const FRAMES = [["brass", "Brass (today)"], ["gold", "Gold"], ["chrome", "Chrome"], ["gunmetal", "Gunmetal"], ["copper", "Copper"], ["black", "Black"]];
const UPHOLSTERY = [["Espresso (today)", "#2a2320"], ["Black", "#1b1a1a"], ["Oxblood", "#4a1418"], ["Burgundy", "#6a1424"], ["Tan", "#7a4a26"],
  ["Navy", "#1a2234"], ["Forest", "#1d4a2a"], ["Bone", "#cfc3a8"]];

export const SLOTS = [
  { id: "felt", label: "Felt", keys: ["felt"], ctl: [
    { key: "felt.colour", type: "swatch", options: FELTS, custom: true, label: "Colour" },
    { key: "felt.texture", type: "seg", options: [["weave", "Woven"], ["velvet", "Velvet"], ["plain", "Plain"]], label: "Cloth" },
    { key: "felt.vignette", type: "range", label: "Darker towards the rail" }] },
  { id: "border", label: "Border line", keys: ["border", "led"], ctl: [
    { key: "border", type: "seg", options: [["none", "None"], ["pinstripe", "Pinstripe"], ["gilt", "Gilt"], ["double", "Double"], ["deco", "Deco"], ["led", "LED glow"]] },
    { key: "led", type: "swatch", options: LEDS, custom: true, label: "LED colour (glow, LED Jackpot ring, black shuffler)" }] },
  { id: "rail", label: "Rail", keys: ["rail"], ctl: [
    { key: "rail.wood", type: "seg", options: Object.entries(WOODS).map(([k, v]) => [k, v.label]), label: "Wood" },
    { key: "rail.armrest", type: "seg", options: [["none", "Bare wood"], ["player", "Leather armrest"], ["all", "Leather all round"]], label: "Padding" },
    { key: "rail.leather", type: "swatch", options: LEATHERS, label: "Leather" },
    { key: "rail.bead", type: "seg", options: [["brass", "Brass"], ["gold", "Gold"], ["chrome", "Chrome"], ["none", "None"]], label: "Bead where it meets the felt" }] },
  { id: "tray", label: "Chip tray", keys: ["tray"], ctl: [
    { key: "tray.mode", type: "seg", options: [["ledge", "Dealer's ledge"], ["sunk", "Sunk in"]], label: "Built in as" },
    { key: "tray.finish", type: "seg", options: [["wood", "Felt-lined well"], ["steel", "Brushed steel"], ["lid", "Smoked lid"]], label: "Finish" }] },
  { id: "print", label: "Printing", keys: ["print"], ctl: [
    { key: "print.font", type: "seg", options: Object.entries(FONTS).map(([k, v]) => [k, v[2]]), label: "Lettering" },
    { key: "print.ink", type: "swatch", options: INKS, custom: true, label: "Ink (titles, rules, follow-up bets like Play)" },
    { key: "print.primary", type: "swatch", options: [...INKS, ...ACCENTS], custom: true, label: "Primary bet (the Ante, Blackjack's bet, Banker)" },
    { key: "print.side", type: "swatch", options: [...ACCENTS, ...INKS], custom: true, label: "Side bets (Pair Plus, 21+3, Tie, Dragons...)" },
    { key: "print.accent", type: "swatch", options: ACCENTS, custom: true, label: "Trim (gilt, double and deco borders, House chips, Master crest)" }] },
  { id: "spots", label: "Betting spots", keys: ["spots"], hint: "same centres and sizes", ctl: [
    { key: "spots", type: "seg", options: [["printed", "Printed"], ["double", "Double ring"], ["foil", "Gold foil"], ["inlaid", "Inlaid"], ["deco", "Deco"]] },
    { key: "glow", type: "swatch", options: GLOWS, custom: true, label: "Glow round the spots waiting for your chips (the main bet, then the side bets): Spot glow above shows it" }] },
  { id: "jackpot", label: "Jackpot disc", keys: ["jackpot", "jackpotRim"], hint: "same size and place", ctl: [
    { key: "jackpot", type: "seg", options: [["clear", "Clear (today)"], ["gold", "Gold bezel"], ["led", "LED ring"]] },
    { key: "jackpotRim", type: "seg", options: [["thin", "Thin"], ["standard", "Standard"], ["heavy", "Heavy"]], label: "Rim thickness (grows inward)" }] },
  { id: "equip", label: "Shuffler, shoe, rack", keys: ["shuffler", "shufflerTint", "shufflerWood", "shoe", "shoeTint", "shoeWood", "rack", "rackTint", "rackWood"], ctl: [
    { key: "shuffler", type: "seg", options: [["gunmetal", "Brushed metal (today)"], ["black", "Gloss with LED"], ["brass", "Wood & brass"]], label: "Shuffler" },
    { key: "shufflerTint", type: "swatch", options: HOUSINGS, custom: true, label: "Shuffler housing colour (metal and gloss)" },
    { key: "shufflerWood", type: "seg", options: WOOD_PICKS, label: "Shuffler wood (wood & brass)" },
    { key: "shoe", type: "seg", options: [["acrylic", "Tinted acrylic (today: red)"], ["wood", "Wood"]], label: "Shoe (Blackjack)" },
    { key: "shoeTint", type: "swatch", options: TINTS, custom: true, label: "Shoe acrylic colour" },
    { key: "shoeWood", type: "seg", options: WOOD_PICKS, label: "Shoe wood" },
    { key: "rack", type: "seg", options: [["clear", "Clear (today)"], ["smoked", "Tinted"], ["wood", "Wood-backed"]], label: "Discard rack" },
    { key: "rackTint", type: "swatch", options: TINTS, custom: true, label: "Rack tint (tinted)" },
    { key: "rackWood", type: "seg", options: WOOD_PICKS, label: "Rack wood (wood-backed)" }] },
  { id: "back", label: "Card back", keys: ["back", "backColour", "cardColour"], ctl: [
    { key: "back", type: "seg", options: Object.entries(BACKS), label: "Design" },
    { key: "backColour", type: "swatch", options: BACK_COLOURS, custom: true, label: "Design colour" },
    { key: "cardColour", type: "swatch", options: CARD_COLOURS, custom: true, label: "Card colour (the border round the back)" }] },
  { id: "front", label: "Card front", keys: ["front", "suits"], ctl: [
    { key: "front", type: "seg", options: Object.entries(FRONTS), label: "Design" },
    { key: "suits", type: "seg", options: [["two", "Red and black"], ["four", "Four-colour (blue diamonds, green clubs)"]], label: "Suit colours" }] },
  { id: "chairs", label: "Chairs", keys: ["chairs"], hint: "shape and sitting from Settings, Seating", ctl: [
    { key: "chairs.frame", type: "seg", options: FRAMES, label: "Frame" },
    { key: "chairs.upholstery", type: "swatch", options: UPHOLSTERY, custom: true, label: "Upholstery" }] },
  { id: "chips", label: "Chips", keys: ["chips"], hint: "Roulette and Craps keep today's", ctl: [
    { key: "chips", type: "seg", options: [["classic", "Today's"], ["clay", "Clay inlay"], ["ceramic", "Ceramic"], ["stripes", "Striped edge"], ["metal", "Metal ring"], ["house", "House colours"], ["vintage", "Vintage suits"]] }] },
];

export const GAMES = [["tcp", "Three Card"], ["bj", "Blackjack"], ["pgf", "Pai Gow Fortune"], ["pgu", "Pai Gow Face Up"], ["ms", "Mississippi"],
  ["uth", "Hold'em"], ["lir", "Let It Ride"], ["hcf", "High Card Flush"], ["bac", "Baccarat"], ["mt", "Master Table"]];
export const VIEWS = { seated: ["Seated", [-166, -188, 332, 242]], table: ["Whole table", [-182, -192, 364, 254]],
  bay: ["Bay close-up", [-112, -160, 224, 70]], seat: ["One seat", [-16, -98, 82, 108]] };

// Roulette's and Craps' own parts (table_styles.KINDS: their House is how they looked before styles, "today").
const CLOTHS = [["grain", "Fine grain (today)"], ["weave", "Woven"], ["velvet", "Velvet"], ["plain", "Plain"]];
const PAD_LEATHERS = [["Brown (today)", "#2a140a"], ...LEATHERS];
const feltSlot = { id: "felt", label: "Felt", ctl: [
  { key: "felt.colour", type: "swatch", options: FELTS, custom: true, label: "Colour" },
  { key: "felt.texture", type: "seg", options: CLOTHS, label: "Cloth" },
  { key: "felt.vignette", type: "range", label: "Darker towards the rail" }] };
const railSlot = pads => ({ id: "rail", label: "Rail", ctl: [
  { key: "rail.wood", type: "seg", options: Object.entries(WOODS).map(([k, v]) => [k, v.label]), label: "Wood" },
  { key: "rail.armrest", type: "seg", options: pads, label: "Padding" },
  { key: "rail.leather", type: "swatch", options: PAD_LEATHERS, custom: true, label: "Leather" },
  { key: "rail.bead", type: "seg", options: [["brass", "Brass"], ["gold", "Gold"], ["chrome", "Chrome"], ["none", "None"]], label: "Bead where it meets the felt" }] });
const fontCtl = { key: "print.font", type: "seg", options: Object.entries(FONTS).map(([k, v]) => [k, v[2]]), label: "Lettering" };
export const ROULETTE_SLOTS = [
  feltSlot,
  { id: "border", label: "Border line", ctl: [
    { key: "border", type: "seg", options: [["none", "None (today)"], ["pinstripe", "Pinstripe"], ["gilt", "Gilt"], ["double", "Double"], ["deco", "Deco"], ["led", "LED glow"]] },
    { key: "led", type: "swatch", options: LEDS, custom: true, label: "LED colour" }] },
  railSlot([["none", "Bare wood (today)"], ["all", "Leather all round"]]),
  { id: "print", label: "Printing", ctl: [fontCtl,
    { key: "print.ink", type: "swatch", options: INKS, custom: true, label: "Ink (lines, numbers, the wheel's numbers)" },
    { key: "print.accent", type: "swatch", options: ACCENTS, custom: true, label: "Accent (gilt, double and deco borders)" }] },
  { id: "numbers", label: "Number colours", hint: "the layout and the wheel's pockets", ctl: [
    { key: "numbers.red", type: "swatch", options: [["Today's red", "#e0453d"], ["Crimson", "#c8283a"], ["Deep red", "#b3263a"], ["Scarlet", "#ff4a3d"], ["Wine", "#8e1a2a"]], custom: true, label: "Red" },
    { key: "numbers.black", type: "swatch", options: [["Today's black", "#1a0d0b"], ["Ink", "#0e0f14"], ["Charcoal", "#2b2f33"], ["Navy", "#14203a"]], custom: true, label: "Black" },
    { key: "numbers.zero", type: "swatch", options: [["Today's green", "#1f8a52"], ["Emerald", "#0f6b45"], ["Jade", "#2fa37a"], ["Gold", "#b8902e"]], custom: true, label: "Zero" }] },
  { id: "float", label: "Float (chip tray)", ctl: [
    { key: "float", type: "seg", options: [["wood", "Wood frame (today)"], ["steel", "Brushed steel"], ["lid", "Wood, smoked lid"]] }] },
  { id: "chairs", label: "Chairs", hint: "shape and sitting from Settings, Seating", ctl: [
    { key: "chairs.frame", type: "seg", options: FRAMES, label: "Frame" },
    { key: "chairs.upholstery", type: "swatch", options: UPHOLSTERY, custom: true, label: "Upholstery" }] },
  { id: "wheel", label: "Wheel", ctl: [
    { key: "wheel.wood", type: "seg", options: WOOD_PICKS, label: "Bowl wood" },
    { key: "wheel.metal", type: "seg", options: [["brass", "Brass (today)"], ["gold", "Gold"], ["chrome", "Chrome"]], label: "Metal (frets, turret, rims, the chip hole)" }] },
];
export const CRAPS_SLOTS = [
  feltSlot,
  railSlot([["none", "Bare wood"], ["dealer", "Dealers' side (today)"], ["all", "Leather all round"]]),
  { id: "print", label: "Printing", ctl: [fontCtl,
    { key: "print.ink", type: "swatch", options: INKS, custom: true, label: "Ink (lines and most lettering)" },
    { key: "print.accent", type: "swatch", options: [["Today's gold", "#f2cf6a"], ...ACCENTS], custom: true, label: "Gold (6 and 8, Field, Horn)" },
    { key: "print.red", type: "swatch", options: [["Today's red", "#e0453d"], ["Deep red", "#b3263a"], ["Scarlet", "#ff4a3d"], ["Gold", "#f2cf6a"], ["Cream", "#f1e4c4"]], custom: true, label: "Red (Come, Big 6/8, Seven, Any Craps)" }] },
  { id: "rubber", label: "Rubber walls", ctl: [
    { key: "rubber", type: "swatch", options: [["Black (today)", "#1b1413"], ["Red", "#7a1418"], ["Navy", "#141a2a"], ["Green", "#123a24"], ["Grey", "#3a3e44"]], custom: true }] },
  { id: "rack", label: "Chip rack", ctl: [
    { key: "rack", type: "seg", options: [["wood", "Felt-lined well (today)"], ["steel", "Brushed steel"], ["lid", "Smoked lid"]] }] },
  { id: "dice", label: "Dice", ctl: [
    { key: "dice", type: "seg", options: [["red", "Red (today)"], ["green", "Green"], ["blue", "Blue"], ["smoke", "Smoke"], ["amber", "Amber"], ["violet", "Violet"]] }] },
];
// What each kind's designer shows: its parts, its games (the card tables' layouts) and its views.
export const KINDS = {
  cards: { slots: SLOTS, views: VIEWS },
  roulette: { slots: ROULETTE_SLOTS, game: "rou", views: { table: ["Whole table", [-190, -160, 380, 215]],
    layout: ["Layout close-up", [-75, -125, 250, 120]], wheel: ["Wheel and float", [-180, -125, 165, 130]] } },
  craps: { slots: CRAPS_SLOTS, game: "crp", views: { table: ["Whole table", [-212, -190, 424, 210]],
    end: ["One end", [30, -140, 180, 150]], middle: ["Middle", [-70, -140, 140, 150]] } },
};

// ---------------------------------------------------------------- small helpers
export function clone(o) { return JSON.parse(JSON.stringify(o)); }
export function getKey(o, k) { return k.split(".").reduce((a, p) => a && a[p], o); }
export function setKey(o, k, v) { const p = k.split("."); const last = p.pop(); p.reduce((a, q) => a[q], o)[last] = v; }

// ---------------------------------------------------------------- colour helpers
function hex(c) { const n = parseInt(c.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function rgba(c, a = 1) { const [r, g, b] = hex(c); return `rgba(${r},${g},${b},${a})`; }
function mix(c, d, t) { const a = hex(c), b = hex(d); return "#" + a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, "0")).join(""); }
function lighten(c, t) { return mix(c, "#ffffff", t); }
function darken(c, t) { return mix(c, "#000000", t); }
function lum(c) { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; const [r, g, b] = hex(c); return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); }
function lab(c) {   // CIE Lab, for how far apart two colours look
  const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }, [r, g, b] = hex(c).map(f);
  const X = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047, Y = r * 0.2126 + g * 0.7152 + b * 0.0722, Z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
  const t = v => v > 0.008856 ? Math.cbrt(v) : 7.787 * v + 16 / 116;
  return [116 * t(Y) - 16, 500 * (t(X) - t(Y)), 200 * (t(Y) - t(Z))];
}
export function distance(a, b) { const x = lab(a), y = lab(b); return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); }

// ---------------------------------------------------------------- geometry
const RAIL = 7;
const ARMREST_X = 141;   // "Leather armrest" runs along the players' straight front (StyledFelt.ARMREST_X)
const HW = 38, FIL = 9, CR = 4;   // the ledge: half width (the tray's), the fillets into the dealer's edge, its front corners
function ye(x) { return -140 - 2 * (1 - Math.min(1, (x / 65) ** 2)); }   // CasinoTable._edge_y
function arcPts(out, cx, cy, r, a0, a1, n = 10) { for (let i = 0; i <= n; i++) { const a = (a0 + (a1 - a0) * i / n) * Math.PI / 180; out.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } }
function trayFront() { const t = G.tables.tcp.tray; return t[1] + t[3]; }
// The ledge's edge against the felt, from the dealer's edge on the left round to it on the right, grown by d into the felt.
function tongue(d) {
  const hw = HW + d, fy = trayFront() + d, f = Math.max(1, FIL - d), r = CR + d, yl = ye(-(hw + f));
  const p = [];
  arcPts(p, -(hw + f), yl + f, f, -90, 0);
  arcPts(p, -hw + r, fy - r, r, 180, 90, 6);
  arcPts(p, hw - r, fy - r, r, 90, 0, 6);
  arcPts(p, hw + f, yl + f, f, 180, 270);
  return p;
}
function feltPoly(mode) {
  const o = G.outline;
  if (mode !== "ledge") return o;
  const lim = HW + FIL + 0.5;
  let first = -1, last = -1;
  o.forEach((p, i) => { if (p[1] < -110 && Math.abs(p[0]) < lim) { if (first < 0) first = i; last = i; } });
  return [...o.slice(0, first), ...tongue(0), ...o.slice(last + 1)];
}
// The shape a table's rail and felt are drawn round (StyledFelt's _grown, _rail_w, _middle, _reach, _pad_area):
// the card table's, or Roulette's or Craps' ("rou", "crp"). g(by) is the outline grown `by` out from the felt.
const CARD_SHAPE = {
  g: by => need(G.grown, Number.isInteger(by) ? by.toFixed(1) : String(by), "outline"), rail: RAIL, middle: [0, -70], reach: 400,
  box: [-200, -200, 400, 260], cards: true,
  pad: arm => arm === "player" ? [[-ARMREST_X, -20], [ARMREST_X, -20], [ARMREST_X, 66], [-ARMREST_X, 66]] : null,
};
function shapeOf(key) {
  const T = G[key];
  return { g: by => { const p = T.grown[by.toFixed(2)]; if (!p) throw new Error("geometry.json has no " + key + " outline at " + by); return p; },
    rail: T.rail, middle: key === "rou" ? [30, -60] : [0, -60], reach: key === "rou" ? 420 : 460, box: [-230, -160, 460, 200],
    pad: arm => arm === "dealer" ? T.pad : null };
}
const grown = k => need(G.grown, k, "outline");
// A line from geometry.json, or a clear error (a missing one once blanked everything drawn after it).
function need(set, key, what) { const p = set && set[key]; if (!p) throw new Error(`geometry.json has no ${what} at ${key}: add it to tools/table_geometry.gd`); return p; }
function shift(pts, dx, dy) { return pts.map(p => [p[0] + dx, p[1] + dy]); }

// ---------------------------------------------------------------- drawing primitives
function path(ctx, pts, close = true) { ctx.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]); if (close) ctx.closePath(); }
function fillPoly(ctx, pts, style) { ctx.beginPath(); path(ctx, pts); ctx.fillStyle = style; ctx.fill(); }
function strokePoly(ctx, pts, style, w, close = true) { ctx.beginPath(); path(ctx, pts, close); ctx.strokeStyle = style; ctx.lineWidth = w; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.stroke(); }
function rrect(ctx, x, y, w, h, r) { r = Math.min(r, w / 2, h / 2); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function pat(ctx, key, units, m) {
  const img = TEX[key]; const p = ctx.createPattern(img, "repeat");
  let M = new DOMMatrix();
  if (m) M = M.translate(m.x, m.y).rotate(m.deg).translate(-(m.s || 0), 0);
  p.setTransform(M.scale(units / img.width));
  return p;
}
function text(ctx, s, x, y, size, colour, D, opts = {}) {
  const f = FONTS[opts.font || D.print.font];
  ctx.save(); ctx.translate(x, y); if (opts.angle) ctx.rotate(opts.angle); ctx.translate(0, size * 0.35); ctx.scale(0.1, 0.1);
  ctx.font = `${f[1]} ${size * 10}px "${f[0]}", Georgia, serif`;
  ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  if (opts.foil) { const g = ctx.createLinearGradient(0, -size * 8, 0, size * 2); g.addColorStop(0, lighten(colour, 0.45)); g.addColorStop(0.55, colour); g.addColorStop(1, darken(colour, 0.35)); ctx.fillStyle = "rgba(0,0,0,.45)"; ctx.fillText(s, 2, 3); ctx.fillStyle = g; }
  else ctx.fillStyle = colour;
  ctx.fillText(s, 0, 0); ctx.restore();
}

// ---------------------------------------------------------------- the table
let bare = false;   // (opts.bare: no carpet behind the table -- the Floor plan tab draws tables on its own floors)
let forPlan = false;   // (opts.plan: just the table -- the Floor plan tab adds its shadow, chairs and dealers upright
                       // on screen however it's turned, as the game does: planShadow, planChair, planDealer)
function drawCarpet(ctx, r) {
  if (bare) return;
  ctx.fillStyle = "#1f3a3e"; ctx.fillRect(r[0], r[1], r[2], r[3]);
  ctx.fillStyle = pat(ctx, "carpet", 128); ctx.fillRect(r[0], r[1], r[2], r[3]);
}
function drawDealer(ctx, at = [0, -123], row = 6) {
  const img = TEX.dealer; if (!img || forPlan) return;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(img, 0, row * 64, 64, 64, at[0] - 32, at[1] - 28 - 32, 64, 64);   // the sheet's idle rows: 6 faces down
  ctx.imageSmoothingEnabled = true;
}
function railRegion(ctx, S, felt) { ctx.beginPath(); path(ctx, S.g(S.rail + 0.5)); path(ctx, felt); ctx.clip("evenodd"); }
const crown = S => S.rail * 4 / 7;
function fillBox(ctx, S, style) { const b = S.box; ctx.fillStyle = style; ctx.fillRect(b[0], b[1], b[2], b[3]); }

function drawWood(ctx, S, D) {
  const W = WOODS[D.rail.wood];
  fillBox(ctx, S, "#2a160b");
  fillBox(ctx, S, pat(ctx, W.tex, W.tile));
  // Strips round the curve, so the grain follows the rail (the card table's straight dealer's edge and ledge run left to right).
  const c = S.g(S.rail / 2); let s = 0;
  for (let i = 0; i < c.length; i++) {
    const p = c[i], q = c[(i + 1) % c.length];
    const dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy);
    if (len < 1e-6) continue;
    if (!(S.cards && Math.abs(p[0]) < 70 && p[1] < -118)) {
      const tx = dx / len, ty = dy / len, nx = -ty, ny = tx, e = 0.35, w = S.rail / 2 + 2;
      const quad = [[p[0] - tx * e + nx * w, p[1] - ty * e + ny * w], [q[0] + tx * e + nx * w, q[1] + ty * e + ny * w],
        [q[0] + tx * e - nx * w, q[1] + ty * e - ny * w], [p[0] - tx * e - nx * w, p[1] - ty * e - ny * w]];
      fillPoly(ctx, quad, pat(ctx, W.tex, W.tile, { x: p[0], y: p[1], deg: Math.atan2(dy, dx) * 180 / Math.PI, s }));
    }
    s += len;
  }
  if (W.gloss) { strokePoly(ctx, shift(S.g(crown(S)), 0, -1.4), "rgba(255,255,255,.10)", 1.6); }
}
function drawLeather(ctx, S, D, ledge) {
  const c = D.rail.leather;
  fillBox(ctx, S, c);
  fillBox(ctx, S, pat(ctx, "leather", 22));
  // Padded: lit along its crown, falling away to both edges.
  const hi = lum(c) > 0.3 ? "rgba(255,255,255,.18)" : "rgba(255,255,255,.09)";
  strokePoly(ctx, shift(S.g(crown(S)), 0, -0.6), hi, 3.2);
  strokePoly(ctx, shift(S.g(crown(S)), 0, -0.9), hi, 1.2);
  if (ledge) { const t = tongue(-3); ctx.beginPath(); path(ctx, t, false); ctx.strokeStyle = hi; ctx.lineWidth = 2.4; ctx.stroke(); }
  // stitching just inside both edges
  ctx.setLineDash([0.8, 0.6]);
  strokePoly(ctx, S.g(1.2), rgba(lighten(c, 0.35), 0.55), 0.18);
  strokePoly(ctx, S.g(S.rail - 1.1), rgba(lighten(c, 0.35), 0.55), 0.18);
  ctx.setLineDash([]);
}
function drawRail(ctx, S, D, felt, ledge) {
  ctx.save(); railRegion(ctx, S, felt);
  const arm = D.rail.armrest;
  if (arm !== "all") drawWood(ctx, S, D);
  if (arm !== "none") {
    ctx.save();
    const area = S.pad(arm);
    if (area) { ctx.beginPath(); path(ctx, area); ctx.clip(); }
    drawLeather(ctx, S, D, ledge && arm === "all");
    ctx.restore();
    if (S.cards && arm === "player" && BEADS[D.rail.bead]) {   // end caps where the padding stops
      for (const sx of [-1, 1]) { ctx.beginPath(); ctx.moveTo(sx * ARMREST_X, 0.5); ctx.lineTo(sx * ARMREST_X, 1 + RAIL + 0.5); ctx.strokeStyle = BEADS[D.rail.bead][0]; ctx.lineWidth = 0.7; ctx.stroke(); }
    }
  }
  // the rounded profile: dark outer edge, a lit crown, a shadow where it meets the felt
  strokePoly(ctx, S.g(S.rail + 0.5), "rgba(0,0,0,.6)", 1.3);
  strokePoly(ctx, shift(S.g(crown(S)), 0, -1.0), "rgba(255,226,190,.10)", 2.4);
  strokePoly(ctx, shift(S.g(crown(S)), 0, -1.2), "rgba(255,230,200,.20)", 0.6);
  strokePoly(ctx, felt, "rgba(0,0,0,.5)", 1.8);
  if (ledge) { ctx.beginPath(); path(ctx, tongue(-2.4), false); ctx.strokeStyle = "rgba(255,226,190,.12)"; ctx.lineWidth = 1.4; ctx.stroke(); }
  ctx.restore();
}
function drawFelt(ctx, S, D, felt) {
  ctx.save(); ctx.beginPath(); path(ctx, felt); ctx.clip();
  const c = D.felt.colour, [mx, my] = S.middle;
  fillBox(ctx, S, c);
  const g = ctx.createRadialGradient(mx, my, 0, mx, my, S.reach / 2);
  g.addColorStop(0, rgba(lighten(c, 0.07), 1)); g.addColorStop(0.35, c); g.addColorStop(1, darken(c, 0.25 + 0.45 * D.felt.vignette));
  fillBox(ctx, S, g);
  const cloth = { velvet: ["velvet", 240, 0.85], weave: ["weave", 16, 0.7], grain: ["grain", 40, 0.25] }[D.felt.texture];
  if (cloth) {
    ctx.globalAlpha = cloth[2];
    fillBox(ctx, S, pat(ctx, cloth[0], cloth[1]));
    ctx.globalAlpha = 1;
  }
  strokePoly(ctx, felt, "rgba(0,0,0,.22)", 6);
  strokePoly(ctx, felt, "rgba(0,0,0,.35)", 2.6);
  ctx.restore();
}
function drawBorder(ctx, S, D, felt, ledge) {
  const b = D.border; if (!b || b === "none") return;
  // The card table's line runs unbroken round the chip tray, on its ledge or sunk in (StyledFelt.border_edge).
  const grown = by => S.cards ? need(G.border[ledge ? "ledge" : "sunk"], (+by).toFixed(2), "border") : S.g(+by);
  const ink = D.print.ink, acc = D.print.accent;
  ctx.save(); ctx.beginPath(); path(ctx, felt); ctx.clip();
  if (b === "pinstripe") strokePoly(ctx, grown("-5.0"), rgba(ink, 0.7), 0.5);
  if (b === "gilt") { strokePoly(ctx, shift(grown("-5.0"), 0, 0.25), "rgba(0,0,0,.4)", 0.8); strokePoly(ctx, grown("-5.0"), lighten(acc, 0.15), 0.65); strokePoly(ctx, shift(grown("-5.0"), 0, -0.15), "rgba(255,245,210,.5)", 0.2); }
  if (b === "double") { strokePoly(ctx, grown("-4.0"), rgba(acc, 0.85), 0.55); strokePoly(ctx, grown("-6.0"), rgba(acc, 0.6), 0.3); }
  if (b === "deco") {
    strokePoly(ctx, grown("-3.5"), rgba(acc, 0.9), 0.6); strokePoly(ctx, grown("-6.0"), rgba(acc, 0.65), 0.3);
    const p = grown("-4.75"); let s = 0;
    for (let i = 0; i < p.length; i++) {
      const a = p[i], q = p[(i + 1) % p.length], len = Math.hypot(q[0] - a[0], q[1] - a[1]);
      if (Math.floor((s + len) / 34) > Math.floor(s / 34)) { const m = [(a[0] + q[0]) / 2, (a[1] + q[1]) / 2]; fillPoly(ctx, [[m[0], m[1] - 1.3], [m[0] + 1.0, m[1]], [m[0], m[1] + 1.3], [m[0] - 1.0, m[1]]], rgba(acc, 0.95)); }
      s += len;
    }
  }
  if (b === "led") { for (const [w, a] of [[5, 0.06], [3, 0.1], [1.6, 0.2], [0.6, 0.7]]) strokePoly(ctx, grown("-2.0"), rgba(ledOf(D), a), w); strokePoly(ctx, grown("-2.0"), "rgba(255,255,255,.55)", 0.2); }
  ctx.restore();
}
function drawBead(ctx, D, felt) {
  const b = BEADS[D.rail.bead]; if (!b) return;
  strokePoly(ctx, felt, b[0], 0.75);
  strokePoly(ctx, shift(felt, 0, -0.18), rgba(b[1], 0.55), 0.22);
}

// ---------------------------------------------------------------- chips
const DENOMS = [[50000, "#d6389f", "#8f1f68"], [10000, "#1c1c1c", "#000000"], [2500, "#1f8a4c", "#125c32"], [500, "#d1362f", "#8f211d"], [100, "#1f6fd6", "#0d3c85"]];
const COL = Object.fromEntries(DENOMS.map(d => [d[0], [d[1], d[2]]]));
function breakdown(p) { const out = []; for (const [d] of DENOMS) while (p >= d && out.length < 8) { out.push(d); p -= d; } return out; }
function chipLabel(p) { const l = p / 100; return l >= 1000 ? (l / 1000) + "k" : String(l); }
function chipFace(ctx, D, x, y, r, denom, label) {
  const kind = D.chips, [c0, c1] = COL[denom];
  ctx.lineCap = "butt";   // (the rail leaves it round, which turns edge spots into blobs)
  const edge = denom === 10000 ? "#d8c9a0" : "#ffffff";
  if (kind === "classic") {
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c1; ctx.fill();
    for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3; ctx.beginPath(); ctx.arc(x, y, r * 0.86, a, a + 0.4); ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = r * 0.2; ctx.stroke(); }
    ctx.beginPath(); ctx.arc(x, y, r * 0.66, 0, 7); ctx.fillStyle = c0; ctx.fill();
    chipText(ctx, label, x, y, r, "#ffffff");
  } else if (kind === "clay") {
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c0; ctx.fill();
    for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2 + 0.3; ctx.beginPath(); ctx.arc(x, y, r * 0.84, a, a + 0.5); ctx.strokeStyle = edge; ctx.lineWidth = r * 0.28; ctx.stroke();
      ctx.beginPath(); ctx.arc(x, y, r * 0.84, a + 0.12, a + 0.38); ctx.strokeStyle = c1; ctx.lineWidth = r * 0.1; ctx.stroke(); }
    ctx.beginPath(); ctx.arc(x, y, r * 0.6, 0, 7); ctx.fillStyle = "#efe7d4"; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, r * 0.6, 0, 7); ctx.strokeStyle = c1; ctx.lineWidth = r * 0.07; ctx.stroke();
    chipText(ctx, label, x, y, r, c1 === "#000000" ? "#1c1c1c" : c1);
  } else if (kind === "stripes") {   // eight edge spots, each three thin stripes, on a darker centre
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c0; ctx.fill();
    for (let i = 0; i < 8; i++) for (let j = 0; j < 3; j++) { const a = i * Math.PI / 4 + j * 0.09 - 0.09;
      ctx.beginPath(); ctx.arc(x, y, r * 0.85, a - 0.03, a + 0.03); ctx.strokeStyle = j === 1 ? c1 : edge; ctx.lineWidth = r * 0.26; ctx.stroke(); }
    ctx.beginPath(); ctx.arc(x, y, r * 0.66, 0, 7); ctx.strokeStyle = "rgba(255,255,255,.8)"; ctx.lineWidth = r * 0.04; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r * 0.6, 0, 7); ctx.fillStyle = c1 === "#000000" ? "#2a2a2a" : c1; ctx.fill();
    chipText(ctx, label, x, y, r, "#ffffff");
  } else if (kind === "metal") {   // a metal ring set into the face, in the rail's bead metal
    const m = BEADS[D.rail.bead] || BEADS.brass;
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c0; ctx.fill();
    for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3 + 0.25; ctx.beginPath(); ctx.arc(x, y, r * 0.86, a, a + 0.3); ctx.strokeStyle = edge; ctx.lineWidth = r * 0.22; ctx.stroke(); }
    const g = ctx.createLinearGradient(x, y - r, x, y + r); g.addColorStop(0, m[1]); g.addColorStop(0.5, m[0]); g.addColorStop(1, darken(m[0], 0.45));
    ctx.beginPath(); ctx.arc(x, y, r * 0.62, 0, 7); ctx.strokeStyle = g; ctx.lineWidth = r * 0.14; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r * 0.54, 0, 7); ctx.fillStyle = darken(c0, 0.15); ctx.fill();
    chipText(ctx, label, x, y, r, "#ffffff");
  } else if (kind === "house") {   // the house's own chip: the felt in the centre, the accent on the edge
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c0; ctx.fill();
    for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3 + 0.25; ctx.beginPath(); ctx.arc(x, y, r * 0.85, a, a + 0.38); ctx.strokeStyle = D.print.accent; ctx.lineWidth = r * 0.24; ctx.stroke(); }
    ctx.beginPath(); ctx.arc(x, y, r * 0.62, 0, 7); ctx.fillStyle = D.felt.colour; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, r * 0.62, 0, 7); ctx.strokeStyle = D.print.accent; ctx.lineWidth = r * 0.06; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r * 0.5, 0, 7); ctx.strokeStyle = rgba(D.print.ink, 0.45); ctx.lineWidth = r * 0.02; ctx.stroke();
    chipText(ctx, label, x, y, r, D.print.ink);
  } else if (kind === "vintage") {   // cream suit inserts round the edge, a cream centre
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c0; ctx.fill();
    ["s", "h", "c", "d"].forEach((suit, i) => { const a = i * Math.PI / 2 - Math.PI / 2;
      suitShape(ctx, suit, x + Math.cos(a) * r * 0.8, y + Math.sin(a) * r * 0.8, r * 0.3, "#f1e4c4");
      const b = a + Math.PI / 4; ctx.beginPath(); ctx.arc(x, y, r * 0.82, b - 0.12, b + 0.12); ctx.strokeStyle = "#f1e4c4"; ctx.lineWidth = r * 0.1; ctx.stroke(); });
    ctx.beginPath(); ctx.arc(x, y, r * 0.56, 0, 7); ctx.fillStyle = "#efe4c8"; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, r * 0.5, 0, 7); ctx.strokeStyle = rgba(c1 === "#000000" ? "#1c1c1c" : c1, 0.6); ctx.lineWidth = r * 0.03; ctx.stroke();
    chipText(ctx, label, x, y, r, c1 === "#000000" ? "#1c1c1c" : c1);
  } else {   // ceramic: printed fine rings and ticks, a glossy face
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = c0; ctx.fill();
    for (let i = 0; i < 24; i++) { const a = i * Math.PI / 12; ctx.beginPath(); ctx.arc(x, y, r * 0.88, a, a + 0.11); ctx.strokeStyle = i % 2 ? "rgba(255,255,255,.9)" : rgba(c1, 0.9); ctx.lineWidth = r * 0.16; ctx.stroke(); }
    ctx.beginPath(); ctx.arc(x, y, r * 0.72, 0, 7); ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.lineWidth = r * 0.04; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r * 0.58, 0, 7); ctx.fillStyle = "#f6f4ee"; ctx.fill();
    chipText(ctx, label, x, y, r, c1 === "#000000" ? "#1c1c1c" : c0);
    const g = ctx.createLinearGradient(x - r, y - r, x + r, y + r); g.addColorStop(0, "rgba(255,255,255,.28)"); g.addColorStop(0.5, "rgba(255,255,255,0)");
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = g; ctx.fill();
  }
}
function chipText(ctx, label, x, y, r, colour) {
  const size = r * (label.length <= 3 ? 0.62 : 0.46);
  ctx.save(); ctx.translate(x, y + size * 0.36); ctx.scale(0.1, 0.1);
  ctx.font = `700 ${size * 10}px ${SANS}`; ctx.textAlign = "center"; ctx.fillStyle = colour;
  ctx.fillText(label, 0, 0); ctx.restore();
}
function stack(ctx, D, amount, x, y) {
  const chips = breakdown(amount), R = 6, L = 1.5;
  ctx.save(); ctx.translate(x + 0.5, y + 1.2); ctx.scale(1, 0.55); ctx.beginPath(); ctx.arc(0, 0, R + 0.5, 0, 7); ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.fill(); ctx.restore();
  for (let i = 0; i < chips.length - 1; i++) {
    const [c0, c1] = COL[chips[i]];
    ctx.beginPath(); ctx.arc(x, y - i * L, R, 0, 7); ctx.fillStyle = D.chips === "classic" ? c1 : c0; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y - i * L, R, 0.2, Math.PI - 0.2); ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = 0.35; ctx.stroke();
    for (let k = 0; k < 4; k++) { const a = 0.35 + k * 0.7; ctx.beginPath(); ctx.arc(x, y - i * L, R - 0.2, a, a + 0.22); ctx.strokeStyle = "rgba(255,255,255,.75)"; ctx.lineWidth = 0.6; ctx.stroke(); }
  }
  chipFace(ctx, D, x, y - (chips.length - 1) * L, R, chips[chips.length - 1], chipLabel(amount));
}
function edgeChip(ctx, D, x, y, w, h, denom, k) {   // one chip on its edge in a tray channel, seen from above
  const [c0, c1] = COL[denom];
  ctx.fillStyle = c0; ctx.fillRect(x, y, w, h);
  const stripe = 0.18 + 0.32 * (k % 2);
  ctx.fillStyle = D.chips === "clay" ? "rgba(240,230,210,.85)" : "rgba(255,255,255,.8)";
  for (const f of [stripe, stripe + 0.5]) ctx.fillRect(x + w * f, y, w * (D.chips === "ceramic" ? 0.07 : 0.12), h);
  ctx.fillStyle = rgba(c1, 0.8); ctx.fillRect(x, y + h - 0.12, w, 0.12);
}

// ---------------------------------------------------------------- the chip tray
const TRAY_DENOMS = [50000, 10000, 10000, 2500, 2500, 2500, 500, 500, 100, 100];
const TRAY_FILL = [0.45, 1.0, 0.6, 0.0, 0.85, 1.0, 0.7, 0.0, 0.9, 0.35];
function wellChannels(ctx, D, x, y, w, h, finish) {
  const lining = finish === "steel" ? "#3b4147" : "#130806";
  const ridge = finish === "steel" ? "#7d868f" : "#2a160b";
  ctx.beginPath(); rrect(ctx, x, y, w, h, 1.4); ctx.fillStyle = ridge; ctx.fill();
  const cw = w / 10;
  for (let i = 0; i < 10; i++) {
    const cx = x + i * cw + 0.3, ww = cw - 0.6;
    ctx.beginPath(); rrect(ctx, cx, y, ww, h, 1.0); ctx.fillStyle = lining; ctx.fill();
    const n = Math.round(TRAY_FILL[i] * Math.floor((h - 0.6) / 1.05));
    for (let k = 0; k < n; k++) edgeChip(ctx, D, cx + 0.35, y + h - 0.3 - (k + 1) * 1.05, ww - 0.7, 0.93, TRAY_DENOMS[i], k);
  }
  for (const band of [3, 2, 1]) { ctx.fillStyle = "rgba(0,0,0,.18)"; ctx.fillRect(x, y, w, band); }   // the back wall's shadow
  if (finish === "steel") { const g = ctx.createLinearGradient(x, 0, x + w, 0); g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(0.5, "rgba(255,255,255,.08)"); g.addColorStop(1, "rgba(255,255,255,0)"); ctx.fillStyle = g; ctx.fillRect(x, y, w, h); }
}
function lid(ctx, x, y, w, h) {
  ctx.beginPath(); rrect(ctx, x, y, w, h, 1.6); ctx.fillStyle = "rgba(25,18,16,.42)"; ctx.fill();
  ctx.save(); ctx.beginPath(); rrect(ctx, x, y, w, h, 1.6); ctx.clip();
  ctx.beginPath(); ctx.moveTo(x + 6, y); ctx.lineTo(x + 18, y); ctx.lineTo(x + 12, y + h); ctx.lineTo(x, y + h); ctx.closePath(); ctx.fillStyle = "rgba(255,255,255,.09)"; ctx.fill();
  ctx.beginPath(); ctx.moveTo(x + 22, y); ctx.lineTo(x + 25, y); ctx.lineTo(x + 19, y + h); ctx.lineTo(x + 16, y + h); ctx.closePath(); ctx.fillStyle = "rgba(255,255,255,.06)"; ctx.fill();
  ctx.restore();
  ctx.beginPath(); rrect(ctx, x, y, w, h, 1.6); ctx.strokeStyle = "rgba(255,255,255,.28)"; ctx.lineWidth = 0.3; ctx.stroke();
  ctx.fillStyle = "#c9a24a"; ctx.fillRect(-1.6, y + h - 1.2, 3.2, 0.9);   // the lock
}
function drawTray(ctx, D, ledge) {
  const t = G.tables.tcp.tray, fin = D.tray.finish;
  const bead = BEADS[D.rail.bead] || ["#6d757c", "#cfd6dc"];
  if (ledge) {
    const x = -35.5, y = -132.2, w = 71, h = 7.9;
    ctx.beginPath(); rrect(ctx, x - 0.6, y - 0.6, w + 1.2, h + 1.2, 2.0); ctx.fillStyle = "rgba(0,0,0,.55)"; ctx.fill();   // the cut
    wellChannels(ctx, D, x, y, w, h, fin);
    ctx.beginPath(); ctx.moveTo(x + 1.4, y + h + 0.35); ctx.lineTo(x + w - 1.4, y + h + 0.35); ctx.strokeStyle = "rgba(255,226,190,.28)"; ctx.lineWidth = 0.35; ctx.stroke();   // the front edge, lit
    if (fin === "steel") { ctx.beginPath(); rrect(ctx, x - 0.4, y - 0.4, w + 0.8, h + 0.8, 1.8); ctx.strokeStyle = "#c3cad1"; ctx.lineWidth = 0.45; ctx.stroke(); }
    if (fin === "lid") lid(ctx, x - 0.3, y - 0.3, w + 0.6, h + 0.6);
  } else {
    const [x, y, w, h] = t;
    ctx.beginPath(); rrect(ctx, x - 0.5, y - 0.5, w + 1, h + 1, 2.8); ctx.fillStyle = "rgba(0,0,0,.6)"; ctx.fill();   // the gap round it
    ctx.beginPath(); rrect(ctx, x, y, w, h, 2.4); ctx.fillStyle = bead[0]; ctx.fill();   // the lip
    const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, "rgba(255,255,255,.35)"); g.addColorStop(0.4, "rgba(255,255,255,0)"); g.addColorStop(1, "rgba(0,0,0,.35)");
    ctx.fillStyle = g; ctx.fill();
    wellChannels(ctx, D, x + 1.3, y + 1.3, w - 2.6, h - 2.6, fin === "steel" ? "steel" : "wood");
    if (fin === "lid") lid(ctx, x + 0.8, y + 0.8, w - 1.6, h - 1.6);
  }
}

// ---------------------------------------------------------------- spots
const SPOT_FILL = "rgba(0,0,0,.15)";
function ledOf(D) { return D.led || "#8fd3ff"; }
// The printing's colours by role: ink (titles, rules, follow-up bets), primary (the bet every hand must have), side
// (the bonus bets) and accent (the trim) -- StyledFelt.role_colour.
function colourOf(D, role) { return ["primary", "side", "accent"].includes(role) ? D.print[role] || D.print.ink : D.print.ink; }
function shapePath(ctx, s, k = 0) {
  ctx.beginPath();
  const [x, y] = s.at;
  if (s.shape === "circle") ctx.arc(x, y, Math.max(0.3, s.r - k), 0, Math.PI * 2);
  else if (s.shape === "diamond") { const a = s.hw - k * 1.2, b = s.hh - k * 1.2; ctx.moveTo(x, y - b); ctx.lineTo(x + a, y); ctx.lineTo(x, y + b); ctx.lineTo(x - a, y); ctx.closePath(); }
  else rrect(ctx, x - s.w / 2 + k, y - s.h / 2 + k, s.w - 2 * k, s.h - 2 * k, Math.max(0.2, (s.rad || 1.2) - k * 0.5));
}
function drawSpot(ctx, D, s) {
  const style = D.spots, c = rgba(colourOf(D, s.ring), s.alpha ?? 1), w = s.width ?? 0.8, base = colourOf(D, s.ring);
  if (style === "printed") {
    shapePath(ctx, s); ctx.fillStyle = SPOT_FILL; ctx.fill(); shapePath(ctx, s, 0.4); ctx.strokeStyle = c; ctx.lineWidth = w; ctx.stroke();
  } else if (style === "double") {
    shapePath(ctx, s); ctx.fillStyle = "rgba(0,0,0,.12)"; ctx.fill();
    shapePath(ctx, s, 0.3); ctx.strokeStyle = c; ctx.lineWidth = w * 0.55; ctx.stroke();
    shapePath(ctx, s, 1.5); ctx.strokeStyle = rgba(base, (s.alpha ?? 1) * 0.75); ctx.lineWidth = w * 0.35; ctx.stroke();
  } else if (style === "foil") {
    shapePath(ctx, s); ctx.fillStyle = "rgba(0,0,0,.12)"; ctx.fill();
    ctx.save(); ctx.translate(0, 0.25); shapePath(ctx, s, 0.45); ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.lineWidth = w + 0.25; ctx.stroke(); ctx.restore();
    const r = s.r || Math.max(s.hh || 0, (s.h || 0) / 2), g = ctx.createLinearGradient(s.at[0], s.at[1] - r, s.at[0], s.at[1] + r);
    g.addColorStop(0, rgba(lighten(base, 0.5), s.alpha ?? 1)); g.addColorStop(0.5, rgba(base, s.alpha ?? 1)); g.addColorStop(1, rgba(darken(base, 0.35), s.alpha ?? 1));
    shapePath(ctx, s, 0.45); ctx.strokeStyle = g; ctx.lineWidth = w * 1.05; ctx.stroke();
  } else if (style === "inlaid") {
    shapePath(ctx, s); ctx.fillStyle = "rgba(0,0,0,.26)"; ctx.fill();
    ctx.save(); shapePath(ctx, s); ctx.clip();
    ctx.translate(0, -0.5); shapePath(ctx, s, -0.2); ctx.strokeStyle = "rgba(0,0,0,.55)"; ctx.lineWidth = 1.8; ctx.stroke();
    ctx.translate(0, 0.9); shapePath(ctx, s, -0.2); ctx.strokeStyle = "rgba(255,255,255,.09)"; ctx.lineWidth = 0.9; ctx.stroke();
    ctx.restore();
    shapePath(ctx, s, 0.35); ctx.strokeStyle = c; ctx.lineWidth = w * 0.5; ctx.stroke();
  } else if (style === "deco") {
    shapePath(ctx, s); ctx.fillStyle = "rgba(0,0,0,.14)"; ctx.fill();
    shapePath(ctx, s, 0.3); ctx.strokeStyle = c; ctx.lineWidth = w * 0.55; ctx.stroke();
    shapePath(ctx, s, 1.6); ctx.strokeStyle = rgba(base, (s.alpha ?? 1) * 0.6); ctx.lineWidth = 0.25; ctx.stroke();
    const [x, y] = s.at;
    const tips = s.shape === "circle" ? [[0, -s.r], [s.r, 0], [0, s.r], [-s.r, 0]].map(p => [x + p[0], y + p[1]])
      : s.shape === "diamond" ? [] : [[x - s.w / 2, y - s.h / 2], [x + s.w / 2, y - s.h / 2], [x + s.w / 2, y + s.h / 2], [x - s.w / 2, y + s.h / 2]];
    for (const [tx, ty] of tips) { ctx.beginPath(); ctx.moveTo(tx, ty - 0.9); ctx.lineTo(tx + 0.7, ty); ctx.lineTo(tx, ty + 0.9); ctx.lineTo(tx - 0.7, ty); ctx.closePath(); ctx.fillStyle = rgba(base, s.alpha ?? 1); ctx.fill(); }
  }
  if (s.inner) {   // a second ring inside (the main bet circles)
    const inner = { ...s, r: s.inner.r }, ic = rgba(colourOf(D, s.inner.ring), s.inner.alpha ?? 0.8);
    shapePath(ctx, inner); ctx.strokeStyle = style === "foil" ? rgba(lighten(colourOf(D, s.inner.ring), 0.15), 0.85) : ic; ctx.lineWidth = s.inner.width ?? 0.4; ctx.stroke();
  }
  if (s.lines) {
    const tc = colourOf(D, s.textRing || s.ring), a = s.textAlpha ?? 1, size = s.size || 2, foil = style === "foil";
    if (s.lines.length === 1) text(ctx, s.lines[0], s.at[0] + (s.dx || 0), s.at[1] + (s.dy || 0), size, rgba(tc, a), D, { foil: foil && a === 1 ? tc : false, font: s.font });
    else s.lines.forEach((l, i) => text(ctx, l, s.at[0], s.at[1] + (i ? 1.3 : -1.3), size, rgba(tc, a), D, { foil: foil ? tc : false }));
  }
}
const RIM = { thin: 0.6, standard: 1, heavy: 1.8 };
function jackpotDisc(ctx, D, at, lit) {
  const [x, y] = at, r = 7.5, kind = D.jackpot, k = RIM[D.jackpotRim] || 1;   // the rim's width; it grows inward, the disc's edge stays put
  ctx.beginPath(); ctx.arc(x, y + 0.7, r + 0.5, 0, 7); ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.fill();
  ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fillStyle = "rgba(214,235,245,.28)"; ctx.fill();
  if (lit) {
    ctx.beginPath(); ctx.arc(x, y, r + 2.5, 0, 7); ctx.fillStyle = "rgba(255,26,26,.18)"; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, r - 0.6, 0, 7); ctx.fillStyle = "rgba(255,31,38,.75)"; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, 3.2, 0, 7); ctx.fillStyle = "rgba(255,140,140,.45)"; ctx.fill();
  }
  if (kind === "clear") {
    ctx.beginPath(); ctx.arc(x, y, r - 0.4 * k, 0, 7); ctx.strokeStyle = "rgba(255,255,255,.75)"; ctx.lineWidth = 0.8 * k; ctx.stroke();
  } else if (kind === "gold") {
    const g = ctx.createLinearGradient(x, y - r, x, y + r); g.addColorStop(0, "#fff0b8"); g.addColorStop(0.45, "#d9b453"); g.addColorStop(1, "#7a5a1c");
    ctx.beginPath(); ctx.arc(x, y, r - 0.6 * k, 0, 7); ctx.strokeStyle = g; ctx.lineWidth = 1.2 * k; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r - 1.2 * k - 0.1, 0, 7); ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = 0.25; ctx.stroke();
  } else {
    const g = ctx.createLinearGradient(x, y - r, x, y + r); g.addColorStop(0, "#ffffff"); g.addColorStop(0.5, "#9aa3ab"); g.addColorStop(1, "#4b535a");
    ctx.beginPath(); ctx.arc(x, y, r - 0.55 * k, 0, 7); ctx.strokeStyle = g; ctx.lineWidth = 1.1 * k; ctx.stroke();
    const dr = r - 1.1 * k - 0.8;
    for (let i = 0; i < 16; i++) { const a = i * Math.PI / 8; ctx.beginPath(); ctx.arc(x + Math.cos(a) * dr, y + Math.sin(a) * dr, 0.32, 0, 7);
      ctx.fillStyle = lit ? "#ff5a5a" : rgba(ledOf(D), 0.8); ctx.fill(); }
  }
  ctx.beginPath(); ctx.arc(x, y, r - 2.0, Math.PI * 1.05, Math.PI * 1.55); ctx.strokeStyle = "rgba(255,255,255,.6)"; ctx.lineWidth = 0.7; ctx.stroke();
  text(ctx, "JACKPOT", x, y, 2, lit ? "#ffffff" : "rgba(255,255,255,.85)", D);
}

// ---------------------------------------------------------------- each game's printing (ports of the *_felt.gd files)
function layout(game, T, D) {
  const DY = G.dealer_y, sp = [], tx = [], ink = 1, draw = [];
  const title = (s, size = 9) => tx.push([s, 0, T.title_y, size, "ink", 1]);
  const small = (s, x, dy) => tx.push([s, x, DY + dy, 3, "ink", 0.85]);
  const circle = (at, ring, lines) => sp.push({ shape: "circle", at, r: 7.5, ring, lines, size: 2 });
  const big = (at, r, lines, size, inner, ring = "primary") => sp.push({ shape: "circle", at, r, ring, lines, size, width: 0.8, inner: inner && { ring, ...inner } });
  const box = (at, w, h, alpha, width = 0.5, ring = "ink", rad = 1.5) => sp.push({ shape: "box", at, w, h, rad, ring, alpha, width });
  const jp = [];
  const S = T.spots;
  switch (game) {
    case "tcp":
      title("THREE CARD POKER");
      for (const [s, x, d] of [["DEALER QUALIFIES", -62, -1.5], ["WITH QUEEN HIGH", -62, 3.5], ["PLAY MUST", 62, -1.5], ["EQUAL ANTE", 62, 3.5]]) small(s, x, d);
      S.forEach(s => { jp.push(s.jackpot.at); circle(s.pair_plus.at, "side", ["PAIR", "PLUS"]); circle(s.prime.at, "side", ["PRIME"]);
        sp.push({ shape: "diamond", at: s.ante.at, hw: 9, hh: 7.5, ring: "primary", lines: ["ANTE"], size: 3 });
        sp.push({ shape: "box", at: s.play.at, w: 21, h: 12, rad: 1.2, ring: "ink", lines: ["PLAY"], size: 4 }); });
      break;
    case "bj":
      title("BLACKJACK PAYS 3 TO 2"); small("STANDS ON 17s", 69, -1.5); small("INSURANCE 2:1", 69, 3.5);
      S.forEach(s => { jp.push(s.jackpot.at);
        sp.push({ shape: "diamond", at: s.top_three.at, hw: 8.5, hh: 7.5, ring: "side", lines: ["TOP 3"], size: 2 });
        circle(s.super_pairs.at, "side", ["SUPER", "PAIRS"]); circle(s.twenty_one_plus_three.at, "side", ["21+3"]);
        big(s.bet.at, T.extra.bet_r, null, 0, { r: T.extra.bet_r - 2.2, alpha: 0.8, width: 0.4 });
        sp.push({ shape: "circle", at: s.insurance.at, r: 4.6, ring: "ink", alpha: 0.55, width: 0.4, lines: ["INS"], size: 2, textAlpha: 0.7 }); });
      break;
    case "pgf": case "pgu": {
      title(game === "pgu" ? "FACE UP PAI GOW" : "FORTUNE PAI GOW");
      const last = game === "pgu" ? "NO COMMISSION" : "5% COMMISSION";
      for (const [s, d] of [["DEALER SETS", -6.5], ["BY HOUSE WAY", -1.5], [last, 3.5]]) small(s, -62, d);
      S.forEach((s, i) => { jp.push(s.jackpot.at); circle(s.fortune.at, "side", ["FORTUNE"]);
        big(s.ante.at, T.extra.ante_r, ["ANTE"], 3, { r: T.extra.ante_r - 2.0, alpha: 0.8, width: 0.4 });
        const [lo, hi] = T.cards[i];
        sp.push({ shape: "box", at: lo, w: T.extra.low_box[0], h: T.extra.low_box[1], rad: 1.5, ring: "ink", alpha: 0.8, width: 0.6, lines: ["LOW"], size: 2, dy: T.extra.low_box[1] / 2 - 3, textAlpha: 0.8 });
        sp.push({ shape: "box", at: hi, w: T.extra.high_box[0], h: T.extra.high_box[1], rad: 1.5, ring: "ink", alpha: 0.8, width: 0.6, lines: ["HIGH"], size: 2, dy: T.extra.high_box[1] / 2 - 3, textAlpha: 0.8 }); });
      break; }
    case "ms":
      title("MISSISSIPPI STUD");
      for (const [s, x, d] of [["JACKS OR BETTER", -64, -1.5], ["PAYS EVERY BET", -64, 3.5], ["6s TO 10s", 64, -1.5], ["PUSH", 64, 3.5]]) small(s, x, d);
      T.dealer_cards.forEach(at => box(at, 16, 22, 0.55));
      S.forEach(s => { jp.push(s.jackpot.at); circle(s.bonus.at, "side", ["3 CARD", "BONUS"]);
        big(s.ante.at, 9, ["ANTE"], 3, { r: 7.0, alpha: 0.8, width: 0.4 });
        ["third", "fourth", "fifth"].forEach((k, j) => sp.push({ shape: "circle", at: s[k].at, r: T.extra.street_r, ring: "ink", alpha: 0.9, width: 0.6, lines: [["3RD", "4TH", "5TH"][j]], size: 2 })); });
      break;
    case "uth":
      title("ULTIMATE TEXAS HOLD'EM", 8); small("DEALER QUALIFIES", 64, -1.5); small("WITH A PAIR", 64, 3.5);
      T.dealer_cards.forEach((at, k) => box(at, 15, 21, k >= 2 ? 0.5 : 0.35));
      S.forEach(s => { jp.push(s.jackpot.at); circle(s.trips.at, "side", ["TRIPS"]);
        for (const k of ["ante", "blind"]) big(s[k].at, 8, [k.toUpperCase()], 3);
        tx.push(["=", (s.ante.at[0] + s.blind.at[0]) / 2, s.ante.at[1], 4, "ink", 0.8]);
        sp.push({ shape: "box", at: s.play.at, w: 21, h: 12, rad: 1.2, ring: "ink", lines: ["PLAY"], size: 4 }); });
      break;
    case "lir":
      title("LET IT RIDE");
      for (const [s, x, d] of [["PAIR OF 10s", -60, -1.5], ["OR BETTER PAYS", -60, 3.5], ["PULL BACK", 60, -1.5], ["1 AND 2", 60, 3.5]]) small(s, x, d);
      T.dealer_cards.forEach(at => box(at, 16, 22, 0.55));
      S.forEach(s => { jp.push(s.jackpot.at); circle(s.bonus.at, "side", ["BONUS"]); circle(s.three_card.at, "side", ["3 CARD", "BONUS"]);
        for (const [k, l] of [["bet1", "1"], ["bet2", "2"], ["ante", "£"]]) big(s[k].at, 7, [l], 6, { r: 5.2, alpha: 0.7, width: 0.4 }); });
      break;
    case "hcf": {
      title("HIGH CARD FLUSH");
      for (const [s, x, d] of [["DEALER NEEDS", -64, -1.5], ["3-CARD 9-HIGH", -64, 3.5], ["RAISE 2X ON 5", 64, -1.5], ["3X ON 6 OR 7", 64, 3.5]]) small(s, x, d);
      const L = T.dealer_cards[0], R = T.dealer_cards[6];
      box([(L[0] + R[0]) / 2, L[1]], R[0] - L[0] + 17, 22, 0.45);
      S.forEach(s => { jp.push(s.jackpot.at); circle(s.flush.at, "side", ["FLUSH"]); circle(s.straight_flush.at, "side", ["STRAIGHT", "FLUSH"]);
        big(s.ante.at, 8, ["ANTE"], 3); big(s.raise.at, 8, ["RAISE"], 3, null, "ink"); });
      break; }
    case "mt": {   // the Master Table before a game's chosen (master_felt.gd): its crest
      for (const [s, x, d] of [["ANY CARD GAME", -62, -1.5], ["ON ONE TABLE", -62, 3.5], ["CHANGE GAME", 62, -1.5], ["BETWEEN HANDS", 62, 3.5]]) small(s, x, d);
      draw.push(c => masterCrest(c, D));
      break; }
    case "bac": {
      title("BACCARAT");
      for (const [side, j] of [["player", 0], ["banker", 3]]) {
        const L = T.dealer_cards[j], R = T.dealer_cards[j + 2], ring = side === "banker" ? "primary" : "ink";
        sp.push({ shape: "box", at: [(L[0] + R[0]) / 2, L[1]], w: R[0] - L[0] + 17, h: 22, rad: 1.5, ring, alpha: 0.8, width: 0.6 });
        tx.push([side.toUpperCase(), (L[0] + R[0]) / 2, L[1] + 14, 3, ring, 0.9]);
      }
      S.forEach((s, i) => { circle(s.player_dragon.at, "side", ["P", "DRAGON"]); circle(s.tie.at, "side", ["TIE"]); circle(s.banker_dragon.at, "side", ["B", "DRAGON"]);
        for (const k of ["banker", "player"]) {
          const at = [T.chairs[i][0], k === "banker" ? T.extra.banker_y : T.extra.player_y], ring = k === "player" ? "ink" : "primary";
          sp.push({ shape: "box", at, w: T.extra.box[0], h: T.extra.box[1], rad: 2, ring, lines: [k.toUpperCase()], size: 3, dx: 9 });
        } });
      break; }
  }
  return { sp, tx, jp, draw };
}

// ---------------------------------------------------------------- the Master Table's crest (master_felt.gd)
const CREST = [0, -64];
function arcText(c, s, cx, cy, r, mid, size, colour, D, bottom = false) {
  const f = FONTS[D.print.font] || FONTS.cinzel;
  c.save(); c.font = `${f[1]} ${size * 10}px "${f[0]}", Georgia, serif`;
  const chars = [...s], ws = chars.map(ch => c.measureText(ch).width / 10), gap = size * 0.16;
  const total = ws.reduce((a, b) => a + b, 0) + gap * (chars.length - 1), dir = bottom ? -1 : 1;
  let along = 0; const a0 = mid - dir * total / (2 * r);
  chars.forEach((ch, i) => {
    const a = a0 + dir * (along + ws[i] / 2) / r;
    c.save(); c.translate(cx + r * Math.cos(a), cy + r * Math.sin(a)); c.rotate(a + dir * Math.PI / 2); c.scale(0.1, 0.1);
    c.textAlign = "center"; c.textBaseline = "middle"; c.fillStyle = colour; c.fillText(ch, 0, 0); c.restore();
    along += ws[i] + gap;
  });
  c.restore();
}
function masterCrest(c, D) {
  const [cx, cy] = CREST, ink = D.print.ink, acc = D.print.accent, R = 24, band = 18.9;
  const grad = (y0, y1) => { const g = c.createLinearGradient(cx, y0, cx, y1); g.addColorStop(0, lighten(acc, 0.45)); g.addColorStop(0.5, acc); g.addColorStop(1, darken(acc, 0.35)); return g; };
  const ring = (r, style, w) => { c.beginPath(); c.arc(cx, cy, r, 0, 7); c.strokeStyle = style; c.lineWidth = w; c.stroke(); };
  const diamond = (x, y, hw, hh, col) => { c.beginPath(); c.moveTo(x, y - hh); c.lineTo(x + hw, y); c.lineTo(x, y + hh); c.lineTo(x - hw, y); c.closePath(); c.fillStyle = col; c.fill(); };
  c.beginPath(); c.arc(cx, cy, R + 0.6, 0, 7); c.fillStyle = "rgba(0,0,0,.15)"; c.fill();
  ring(R, grad(cy - R, cy + R), 1.0); ring(R - 1.5, rgba(ink, 0.55), 0.22); ring(15.2, rgba(ink, 0.75), 0.32); ring(14.2, rgba(ink, 0.35), 0.18);
  arcText(c, "MASTER TABLE", cx, cy, band, -Math.PI / 2, 4, ink, D);
  arcText(c, "NINE GAMES · ONE TABLE", cx, cy, band, Math.PI / 2, 2, rgba(ink, 0.85), D, true);
  for (const s of [-1, 1]) diamond(cx + s * band, cy, 0.9, 1.4, acc);
  for (const [deg, suit] of [[-90, "s"], [0, "h"], [90, "c"], [180, "d"]]) {
    const a = deg * Math.PI / 180;
    suitShape(c, suit, cx + Math.cos(a) * 8, cy + Math.sin(a) * 8 + 0.3, 5.6, "hd".includes(suit) ? acc : ink);
  }
  c.beginPath();
  for (let i = 0; i < 8; i++) { const a = -Math.PI / 2 + i * Math.PI / 4, r = i % 2 ? 1.0 : 2.2; c.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); }
  c.closePath(); c.fillStyle = acc; c.fill();
  c.beginPath(); c.ellipse(cx, cy - R, 7.6, 2.4, 0, 0, 7); c.fillStyle = D.felt.colour; c.fill();
  const w = 11, h = w * 0.7, bx = cx, by = cy - R + 0.8;
  c.beginPath(); c.moveTo(bx - w / 2, by); c.lineTo(bx - w / 2, by - h * 0.25); c.lineTo(bx - w * 0.56, by - h * 0.92); c.lineTo(bx - w * 0.25, by - h * 0.48);
  c.lineTo(bx, by - h); c.lineTo(bx + w * 0.25, by - h * 0.48); c.lineTo(bx + w * 0.56, by - h * 0.92); c.lineTo(bx + w / 2, by - h * 0.25); c.lineTo(bx + w / 2, by); c.closePath();
  c.fillStyle = grad(by - h, by); c.fill(); c.strokeStyle = darken(acc, 0.5); c.lineWidth = 0.25; c.stroke();
  for (const [px, py] of [[-w * 0.56, -h * 0.92], [0, -h], [w * 0.56, -h * 0.92]]) { c.beginPath(); c.arc(bx + px, by + py, w * 0.07, 0, 7); c.fillStyle = lighten(acc, 0.35); c.fill(); }
  for (const [x, y] of [[cx + R, cy], [cx, cy + R], [cx - R, cy]]) diamond(x, y, 1.2, 1.6, lighten(acc, 0.2));
  const ty = cy + 31;
  text(c, "ASK THE DEALER FOR ANY GAME", 0, ty, 3, rgba(ink, 0.92), D);
  for (const s of [-1, 1]) {
    c.beginPath(); c.moveTo(s * 33, ty); c.lineTo(s * 48, ty); c.strokeStyle = rgba(acc, 0.8); c.lineWidth = 0.3; c.stroke();
    diamond(s * 31, ty, 0.8, 0.9, acc);
  }
}

// ---------------------------------------------------------------- cards
const SUITS = { s: "♠", h: "♥", d: "♦", c: "♣" };
function cardShape(ctx, x, y, w = 14, h = 20) { ctx.beginPath(); rrect(ctx, x - w / 2, y - h / 2, w, h, 0.9); }
// A card's back (Card2D.draw_back): its design over its colour, inside a border in the card's colour.
function cardBack(ctx, D, x, y, w = 14, h = 20) {
  const k = D.back === "emerald" ? "lattice" : D.back, main = backColour(D);
  cardShape(ctx, x, y, w, h); ctx.fillStyle = D.cardColour || "#f4f2ec"; ctx.fill(); ctx.strokeStyle = "rgba(0,0,0,.35)"; ctx.lineWidth = 0.3; ctx.stroke();
  const ix = x - w / 2 + 1.3, iy = y - h / 2 + 1.3, iw = w - 2.6, ih = h - 2.6;
  ctx.fillStyle = main; ctx.fillRect(ix, iy, iw, ih);
  ctx.save(); ctx.beginPath(); ctx.rect(ix, iy, iw, ih); ctx.clip();
  const gold = "#c9a24a";
  if (k === "lattice") {
    for (let t = -ih; t < iw + ih; t += 1.6) { ctx.beginPath(); ctx.moveTo(ix + t, iy); ctx.lineTo(ix + t - ih, iy + ih); ctx.moveTo(ix + t - ih, iy); ctx.lineTo(ix + t, iy + ih); ctx.strokeStyle = "rgba(255,235,217,.52)"; ctx.lineWidth = 0.18; ctx.stroke(); }
    ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 0.4; ctx.strokeRect(ix + 1.3, iy + 1.3, iw - 2.6, ih - 2.6);
  } else if (k === "sunburst") {
    for (let i = 0; i < 24; i++) { const a = i * Math.PI / 12; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(a) * 20, y + Math.sin(a) * 20); ctx.strokeStyle = rgba("#e0b84e", 0.45); ctx.lineWidth = 0.2; ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x + 3, y); ctx.lineTo(x, y + 4); ctx.lineTo(x - 3, y); ctx.closePath(); ctx.fillStyle = "#e0b84e"; ctx.fill();
    ctx.strokeStyle = "#e0b84e"; ctx.lineWidth = 0.35; ctx.strokeRect(ix + 0.9, iy + 0.9, iw - 1.8, ih - 1.8); ctx.lineWidth = 0.18; ctx.strokeRect(ix + 1.7, iy + 1.7, iw - 3.4, ih - 3.4);
  } else if (k === "monogram") {
    ctx.strokeStyle = "#d9b453"; ctx.lineWidth = 0.35; ctx.strokeRect(ix + 1, iy + 1, iw - 2, ih - 2); ctx.lineWidth = 0.18; ctx.strokeRect(ix + 1.8, iy + 1.8, iw - 3.6, ih - 3.6);
    ctx.beginPath(); ctx.arc(x, y, 3.3, 0, 7); ctx.strokeStyle = "#d9b453"; ctx.lineWidth = 0.3; ctx.stroke();
    text(ctx, "CW", x, y, 3, "#e8cf86", D, { font: "cormorant" });
  } else if (k === "stripe") {
    const [r, g, b] = hex(main), band = r - Math.max(g, b) < 64 ? "#c8202b" : "#f1e4c4";   // (cream on a red back)
    ctx.fillStyle = band; ctx.beginPath(); ctx.moveTo(ix, iy + ih * 0.62); ctx.lineTo(ix + iw, iy + ih * 0.22); ctx.lineTo(ix + iw, iy + ih * 0.38); ctx.lineTo(ix, iy + ih * 0.78); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = "#c9d0d6"; ctx.lineWidth = 0.3; ctx.strokeRect(ix + 0.9, iy + 0.9, iw - 1.8, ih - 1.8);
  } else {   // framed: a faint lattice in a brass frame
    for (let t = -ih; t < iw + ih; t += 3.4) { ctx.beginPath(); ctx.moveTo(ix + t, iy); ctx.lineTo(ix + t - ih, iy + ih); ctx.moveTo(ix + t - ih, iy); ctx.lineTo(ix + t, iy + ih); ctx.strokeStyle = "rgba(255,255,255,.1)"; ctx.lineWidth = 0.3; ctx.stroke(); }
    ctx.strokeStyle = rgba(gold, 0.85); ctx.lineWidth = 0.4; ctx.strokeRect(ix + 1.3, iy + 1.3, iw - 2.6, ih - 2.6);
  }
  ctx.restore();
}
function suitShape(ctx, suit, cx, cy, h, colour) {   // each part filled on its own, so overlaps never cancel out
  ctx.fillStyle = colour;
  const dot = (x, y, r) => { ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill(); };
  const poly = pts => { ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); ctx.fill(); };
  const stem = top => poly([[cx - h * 0.05, cy + top], [cx + h * 0.05, cy + top], [cx + h * 0.18, cy + h * 0.5], [cx - h * 0.18, cy + h * 0.5]]);
  if (suit === "d") poly([[cx, cy - h / 2], [cx + h * 0.38, cy], [cx, cy + h / 2], [cx - h * 0.38, cy]]);
  else if (suit === "h") { const r = h * 0.27; dot(cx - r * 0.92, cy - h * 0.2, r); dot(cx + r * 0.92, cy - h * 0.2, r); poly([[cx - h * 0.5, cy - h * 0.12], [cx + h * 0.5, cy - h * 0.12], [cx, cy + h * 0.48]]); }
  else if (suit === "s") { const r = h * 0.26; dot(cx - r * 0.92, cy + h * 0.1, r); dot(cx + r * 0.92, cy + h * 0.1, r); poly([[cx - h * 0.48, cy + h * 0.04], [cx + h * 0.48, cy + h * 0.04], [cx, cy - h * 0.5]]); stem(h * 0.12); }
  else { const r = h * 0.22; dot(cx, cy - h * 0.25, r); dot(cx - h * 0.25, cy + h * 0.04, r); dot(cx + h * 0.25, cy + h * 0.04, r); stem(-h * 0.05); }
}
// A suit's colour: red and black, or a four-colour deck's (Card2D.suit_colour).
function suitColour(D, suit) {
  if (D.suits === "four") return { h: "#c62828", d: "#1f5fbf", c: "#1e7d3a" }[suit] || "#1b1b1b";
  return "hd".includes(suit) ? "#c62828" : "#1b1b1b";
}
// A rank centred on x, its baseline at y, `size` units tall, in `family` (the game's sans unless the front's Vintage).
function rankText(ctx, rank, x, y, size, col, family = SANS, weight = 700) {
  ctx.save(); ctx.translate(x, y); ctx.scale(0.1, 0.1); ctx.font = `${weight} ${size * 10}px ${family}`; ctx.textAlign = "center"; ctx.fillStyle = col; ctx.fillText(rank, 0, 0); ctx.restore();
}
// A card face up or down, in the style's front and back (Card2D.paint).
function card(ctx, D, code, x, y, rot = 0) {
  ctx.save(); ctx.translate(x, y); if (rot) ctx.rotate(rot);
  cardShape(ctx, 0.6, 0.8); ctx.fillStyle = "rgba(0,0,0,.25)"; ctx.fill();
  if (code === "??") { cardBack(ctx, D, 0, 0); ctx.restore(); return; }
  const front = D.front || "classic", vintage = front === "vintage";
  cardShape(ctx, 0, 0); ctx.fillStyle = vintage ? "#f3ead2" : "#fbfaf5"; ctx.fill(); ctx.strokeStyle = vintage ? "#b9a77f" : "#b9b4a5"; ctx.lineWidth = 0.3; ctx.stroke();
  const rank = code.slice(0, -1), suit = code.slice(-1), col = suitColour(D, suit), one = rank.length < 2;
  const corners = draw => { for (const flip of [0, 1]) { ctx.save(); if (flip) ctx.rotate(Math.PI); draw(); ctx.restore(); } };
  if (front === "jumbo") corners(() => { rankText(ctx, rank, -3.4, -3.6, one ? 7 : 5, col); suitShape(ctx, suit, -3.4, -0.7, 3.6, col); });
  else if (front === "vintage") {
    ctx.strokeStyle = rgba(col, 0.6); ctx.lineWidth = 0.3; ctx.strokeRect(-2.8, -7.8, 5.6, 15.6);
    ctx.strokeStyle = rgba(col, 0.35); ctx.lineWidth = 0.15; ctx.strokeRect(-2.2, -7.2, 4.4, 14.4);
    const f = FONTS[D.print.font] || FONTS.cinzel;
    corners(() => { rankText(ctx, rank, -4.8, -6, one ? 4 : 3, col, `"${f[0]}", Georgia, serif`, f[1]); suitShape(ctx, suit, -4.8, -3.9, 2.2, col); });
    suitShape(ctx, suit, 0, 0.4, 5, col);
  } else if (front === "minimal") {
    rankText(ctx, rank, 0, 2, one ? 9 : 7, col); suitShape(ctx, suit, 0, 5.4, 3, col);
    rankText(ctx, rank, -5.1, -7, 2, col);   // (for cascaded cards)
  } else {
    corners(() => { rankText(ctx, rank, -4.6, -6, one ? 4 : 3, col); suitShape(ctx, suit, -4.6, -3.9, 2.5, col); });
    suitShape(ctx, suit, 0, 0.6, 7, col);
  }
  ctx.restore();
}

// ---------------------------------------------------------------- equipment
function shuffler(ctx, D, at) {
  const [x, y] = at, kind = D.shuffler, bw = 24, bh = 18;
  ctx.save(); ctx.translate(x, y);
  ctx.beginPath(); rrect(ctx, -bw / 2 - 1.4, -bh / 2 - 1.4, bw + 2.8, bh + 2.8, 3.2); ctx.fillStyle = "rgba(0,0,0,.55)"; ctx.fill();
  const tint = D.shufflerTint || (kind === "black" ? "#1c1e22" : "#3a3e44");
  const body = kind === "black" ? [darken(tint, 0.6), tint] : kind === "brass" ? ["#24130a", "#3d2414"] : [darken(tint, 0.45), tint];
  ctx.beginPath(); rrect(ctx, -bw / 2, -bh / 2, bw, bh, 2.6); ctx.fillStyle = body[0]; ctx.fill();
  ctx.beginPath(); rrect(ctx, -bw / 2 + 0.7, -bh / 2 + 0.7, bw - 1.4, bh - 1.4, 2.1); ctx.fillStyle = body[1]; ctx.fill();
  if (kind === "brass") { ctx.save(); ctx.clip(); ctx.fillStyle = pat(ctx, woodTex(D, D.shufflerWood), 30); ctx.globalAlpha = 0.9; ctx.fillRect(-bw / 2, -bh / 2, bw, bh); ctx.restore();
    ctx.beginPath(); rrect(ctx, -bw / 2 + 0.5, -bh / 2 + 0.5, bw - 1, bh - 1, 2.2); ctx.strokeStyle = "#c9a24a"; ctx.lineWidth = 0.6; ctx.stroke(); }
  else if (kind === "gunmetal") for (let i = 0; i < 7; i++) { ctx.fillStyle = `rgba(255,255,255,${0.035 + 0.02 * (i % 2)})`; ctx.fillRect(-bw / 2 + 1.2, -bh / 2 + 1.5 + i * 2.4, bw - 2.4, 0.5); }
  else { const g = ctx.createLinearGradient(-bw / 2, -bh / 2, bw / 2, bh / 2); g.addColorStop(0, "rgba(255,255,255,.16)"); g.addColorStop(0.35, "rgba(255,255,255,0)"); ctx.fillStyle = g; ctx.beginPath(); rrect(ctx, -bw / 2, -bh / 2, bw, bh, 2.6); ctx.fill(); }
  ctx.fillStyle = "#050607"; ctx.fillRect(-8.5, -bh / 2 + 1.6, 17, 1.6);   // intake
  ctx.beginPath(); rrect(ctx, -9.5, -bh / 2 + 4.2, 19, 7.6, 1.2); ctx.fillStyle = "#12161b"; ctx.fill();   // smoked lid
  ctx.fillStyle = "#23262c"; ctx.fillRect(-5.5, -bh / 2 + 5.6, 11, 4.8);
  ctx.strokeStyle = "rgba(255,255,255,.16)"; ctx.lineWidth = 0.3; ctx.beginPath(); rrect(ctx, -9.5, -bh / 2 + 4.2, 19, 7.6, 1.2); ctx.stroke();
  const ly = -bh / 2 + 12.8;
  if (kind === "black") {
    ctx.fillStyle = "#06080a"; ctx.fillRect(-9.8, ly, 13, 3.2);
    ctx.save(); ctx.translate(-3.3, ly + 2.25); ctx.scale(0.1, 0.1); ctx.font = `700 20px ${SANS}`; ctx.textAlign = "center"; ctx.fillStyle = "#e9f6ff"; ctx.fillText("READY", 0, 0); ctx.restore();
    for (const [w, a] of [[2.2, 0.15], [0.9, 0.9]]) { ctx.beginPath(); ctx.moveTo(-8, bh / 2 - 0.7); ctx.lineTo(8, bh / 2 - 0.7); ctx.strokeStyle = rgba(ledOf(D), a); ctx.lineWidth = w; ctx.stroke(); }
    ctx.beginPath(); ctx.arc(8, ly + 1.6, 1.1, 0, 7); ctx.fillStyle = ledOf(D); ctx.fill();
  } else {
    ctx.fillStyle = kind === "brass" ? "#1b1206" : "#0b1a10"; ctx.fillRect(-9.8, ly, 12.5, 3.2);
    ctx.save(); ctx.translate(-3.55, ly + 2.2); ctx.scale(0.1, 0.1); ctx.font = `700 20px ${SANS}`; ctx.textAlign = "center"; ctx.fillStyle = kind === "brass" ? "#ffcf6e" : "#7dff9a"; ctx.fillText("READY", 0, 0); ctx.restore();
    ctx.beginPath(); ctx.arc(8, ly + 1.6, 2.0, 0, 7); ctx.fillStyle = "rgba(56,224,106,.25)"; ctx.fill();
    ctx.beginPath(); ctx.arc(8, ly + 1.6, 1.1, 0, 7); ctx.fillStyle = "#38e06a"; ctx.fill();
    if (kind === "brass") { ctx.beginPath(); ctx.arc(8, ly + 1.6, 1.5, 0, 7); ctx.strokeStyle = "#c9a24a"; ctx.lineWidth = 0.4; ctx.stroke(); }
  }
  ctx.fillStyle = "#050607"; ctx.fillRect(-8, bh / 2 - 1.9, 16, 1.2);   // delivery slot
  ctx.beginPath(); ctx.moveTo(-8.5, bh / 2 - 0.3); ctx.lineTo(8.5, bh / 2 - 0.3); ctx.strokeStyle = kind === "brass" ? "#c9a24a" : "#9aa1aa"; ctx.lineWidth = 0.6; ctx.stroke();
  ctx.restore();
}
function shoe(ctx, D, at) {
  const [x, y] = at, kind = D.shoe, bw = 28, bh = 16;
  ctx.save(); ctx.translate(x, y);
  ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fillRect(-bw / 2 + 0.8, -bh / 2 + 1.2, bw, bh);
  const tint = D.shoeTint || "#6b0f19", dark = lum(tint) < 0.01;
  const edge = kind === "wood" ? "#1e0e06" : darken(tint, 0.6);
  ctx.fillStyle = edge; ctx.fillRect(-bw / 2, -bh / 2, bw, bh);
  if (kind === "wood") { ctx.fillStyle = pat(ctx, woodTex(D, D.shoeWood), 34); ctx.fillRect(-bw / 2 + 0.8, -bh / 2 + 0.8, bw - 1.6, bh - 1.6); }
  else { ctx.fillStyle = rgba(tint, 0.92); ctx.fillRect(-bw / 2 + 0.8, -bh / 2 + 0.8, bw - 1.6, bh - 1.6); }
  const ix = -bw / 2 + 3.5, iy = -bh / 2 + 2.2, iw = bw - 5.5, ih = bh - 4.4, fill = 0.72;
  ctx.fillStyle = "#ece8de"; ctx.fillRect(ix, iy, iw * fill, ih);
  for (let i = 0; i < iw * fill / 0.7; i++) { ctx.fillStyle = "rgba(0,0,0,.1)"; ctx.fillRect(ix + i * 0.7, iy, 0.2, ih); }
  ctx.fillStyle = backColour(D); ctx.fillRect(ix + iw * fill - 1.4, iy, 1.4, ih);
  ctx.fillStyle = "#ffd23c"; ctx.fillRect(ix + iw * 0.3 - 0.4, iy - 1.2, 0.8, ih + 2.4);   // the cut card
  ctx.fillStyle = kind === "wood" ? "rgba(30,15,5,.25)" : rgba(darken(tint, 0.15), 0.3); ctx.fillRect(ix, iy, iw, ih);
  ctx.fillStyle = kind === "wood" ? "#c9a24a" : darken(tint, 0.75); ctx.beginPath(); ctx.moveTo(-bw / 2, -bh / 2 + 2); ctx.lineTo(-bw / 2 + 3.5, -bh / 2 + 2.2); ctx.lineTo(-bw / 2 + 3.5, bh / 2 - 2.2); ctx.lineTo(-bw / 2, bh / 2 - 2); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = kind !== "wood" && dark ? "rgba(200,210,220,.5)" : "rgba(255,255,255,.12)"; ctx.lineWidth = 0.4; ctx.strokeRect(-bw / 2, -bh / 2, bw, bh);
  ctx.restore();
}
function rack(ctx, D, at, n = 3) {
  const [x, y] = at, kind = D.rack, w = 24, h = 18;
  ctx.save(); ctx.translate(x, y);
  ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.fillRect(-w / 2 + 0.6, -h / 2 + 1, w, h);
  const tint = D.rackTint || "#1e2328";
  if (kind === "wood") { ctx.fillStyle = pat(ctx, woodTex(D, D.rackWood), 30); ctx.fillRect(-w / 2, -h / 2, w, h); ctx.fillStyle = darken(D.felt.colour, 0.35); ctx.fillRect(-w / 2 + 1.4, -h / 2 + 1.4, w - 2.8, h - 1.4); }
  else { ctx.fillStyle = kind === "smoked" ? rgba(tint, 0.45) : "rgba(204,230,242,.16)"; ctx.fillRect(-w / 2, -h / 2, w, h); }
  ctx.fillStyle = "#e8e4da"; ctx.fillRect(-10, -7 + 0.6 - 1.2, 20, 15.2);
  for (let k = 0; k < n; k++) { ctx.save(); ctx.translate(Math.sin(k * 1.7) * 0.8, 0.6 - 1.2 + Math.cos(k * 2.3) * 0.6); ctx.rotate(Math.sin(k * 3.1) * 0.07); cardBack(ctx, D, 0, 0, 20, 14); ctx.restore(); }
  const wall = kind === "wood" ? "#2a160b" : kind === "smoked" ? rgba(lighten(tint, 0.12), 0.85) : "rgba(230,245,255,.55)";
  ctx.strokeStyle = wall; ctx.lineWidth = kind === "wood" ? 1.6 : 1.2;
  ctx.beginPath(); ctx.moveTo(-w / 2, h / 2); ctx.lineTo(-w / 2, -h / 2); ctx.lineTo(w / 2, -h / 2); ctx.lineTo(w / 2, h / 2); ctx.stroke();
  if (kind === "wood") { ctx.strokeStyle = "#c9a24a"; ctx.lineWidth = 0.3; ctx.beginPath(); ctx.moveTo(-w / 2 + 0.8, h / 2); ctx.lineTo(-w / 2 + 0.8, -h / 2 + 0.8); ctx.lineTo(w / 2 - 0.8, -h / 2 + 0.8); ctx.lineTo(w / 2 - 0.8, h / 2); ctx.stroke(); }
  ctx.strokeStyle = "rgba(255,255,255,.25)"; ctx.lineWidth = 0.4; ctx.beginPath(); ctx.moveTo(-w / 2, h / 2); ctx.lineTo(w / 2, h / 2); ctx.stroke();
  ctx.restore();
}
// ---------------------------------------------------------------- chairs (scripts/seating.gd, the seating mockup)
// The frame metals: hi, mid, lo, piping (Seating.METALS).
const METALS = { brass: ["#fbe7a1", "#c99a3c", "#6e4f1c", "#e2bb5c"], chrome: ["#ffffff", "#aeb6c0", "#4b525c", "#d5dbe2"],
  gunmetal: ["#9aa0a8", "#4a4e55", "#1d1f23", "#7e858f"], gold: ["#fff3b8", "#d9b453", "#7a5a1c", "#f0cf6e"],
  copper: ["#ffd3b4", "#c8794a", "#6b3418", "#e39d70"], black: ["#6a6e75", "#26282c", "#0c0d0f", "#4a4e55"] };
const CHAIR_COLOURS = { frame: "brass", upholstery: "#2a2320" };
let seatShape = { chair: "stool", back: 1.4, size: 1 };   // the Default seating style's shape (render's opts.seating)

function chairGeom() {
  const s = +seatShape.size || 1, back = +seatShape.back || 1.4;
  if (seatShape.chair === "lounge") return { rx: 11.5 * s, ry: 5.2 * s, seatY: -11 * s, thick: 3.6 * s, h: 13 * s * back, hs: 1.22, t: 2.4 * s, inset: 1, baseRx: 9.5 * s, ring: false, col: 3.2 * s, lounge: true };
  return { rx: 10 * s, ry: 4.6 * s, seatY: -13.5 * s, thick: 2.8 * s, h: 7.5 * s * back, hs: 1, t: 1.7 * s, inset: 0.6, baseRx: 7 * s, ring: true, col: 2.4 * s, lounge: false };
}
function chairPalette(colours) {
  const c = { ...CHAIR_COLOURS, ...(colours || {}) }, u = c.upholstery;
  return { main: u, top: lighten(u, 0.16), edge: darken(u, 0.28), side: darken(u, 0.5), rear: darken(u, 0.32), cap: lighten(u, 0.26), m: METALS[c.frame] || METALS.brass };
}
function ellPath(ctx, x, y, rx, ry, a0 = 0, a1 = Math.PI * 2) { ctx.beginPath(); ctx.ellipse(x, y, Math.max(rx, 0.01), Math.max(ry, 0.01), 0, a0, a1); }
function quadFill(ctx, q, c) { ctx.beginPath(); ctx.moveTo(...q[0]); for (let i = 1; i < q.length; i++) ctx.lineTo(...q[i]); ctx.closePath(); ctx.fillStyle = c; ctx.fill(); ctx.strokeStyle = c; ctx.lineWidth = 0.15; ctx.stroke(); }
function shade(c, k) { return k > 0 ? lighten(c, k) : darken(c, -k); }

/** A chair at `at` (where its sitter's feet go), its back pointing `theta` on screen (PI / 2: towards us), in a table
 *  style's chair colours: the base, the seat, the back (Seating.draw_chair, with no one in it). */
function seatChair(ctx, at, theta, colours) {
  const g = chairGeom(), p = chairPalette(colours), m = p.m;
  ctx.save(); ctx.translate(at[0], at[1]); ctx.lineCap = "butt";
  // the base
  ctx.fillStyle = "rgba(0,0,0,.38)"; ellPath(ctx, 0, 1.2, g.rx + 1.5, 3.8); ctx.fill();
  ctx.fillStyle = m[2]; ellPath(ctx, 0, 0.7, g.baseRx, g.baseRx * 0.36); ctx.fill();
  let gr = ctx.createLinearGradient(-g.baseRx * 0.9, 0, g.baseRx * 0.9, 0); gr.addColorStop(0, m[1]); gr.addColorStop(0.35, m[0]); gr.addColorStop(1, m[2]);
  ctx.fillStyle = gr; ellPath(ctx, 0, -0.1, g.baseRx * 0.9, g.baseRx * 0.3); ctx.fill();
  const ringY = -4.2 * g.rx / 10, rr = 0.76 * g.rx, top = g.seatY + g.thick, w = g.col;
  if (g.ring) { ctx.strokeStyle = m[2]; ctx.lineWidth = 1.1; ellPath(ctx, 0, ringY, rr, rr * 0.32, Math.PI, Math.PI * 2); ctx.stroke(); }
  gr = ctx.createLinearGradient(-w / 2, 0, w / 2, 0); gr.addColorStop(0, m[2]); gr.addColorStop(0.35, m[0]); gr.addColorStop(0.6, m[1]); gr.addColorStop(1, m[2]);
  ctx.fillStyle = gr; ctx.fillRect(-w / 2, top, w, -top);
  if (g.ring) {
    ctx.strokeStyle = m[1]; ctx.lineWidth = 1.2; ellPath(ctx, 0, ringY, rr, rr * 0.32, 0, Math.PI); ctx.stroke();
    ctx.strokeStyle = rgba(m[0], 0.8); ctx.lineWidth = 0.4; ellPath(ctx, 0, ringY - 0.3, rr, rr * 0.32, 0.3, 1.6); ctx.stroke();
  } else { ctx.fillStyle = m[2]; ellPath(ctx, 0, top + 0.6, g.rx * 0.42, g.ry * 0.42); ctx.fill(); }
  // the seat
  const y = g.seatY, th = g.thick;
  ctx.fillStyle = p.side; ellPath(ctx, 0, y + th, g.rx, g.ry); ctx.fill(); ctx.fillRect(-g.rx, y, 2 * g.rx, th);
  ctx.fillStyle = rgba(m[3], 0.55); ctx.fillRect(-g.rx, y + th * 0.55, 2 * g.rx, 0.35);
  ctx.fillStyle = p.edge; ellPath(ctx, 0, y, g.rx, g.ry); ctx.fill();
  ctx.fillStyle = p.main; ellPath(ctx, -g.rx * 0.06, y - g.ry * 0.1, g.rx * 0.88, g.ry * 0.8); ctx.fill();
  ctx.fillStyle = rgba(p.top, 0.75); ellPath(ctx, -g.rx * 0.3, y - g.ry * 0.35, g.rx * 0.45, g.ry * 0.4); ctx.fill();
  if (g.lounge) { ctx.strokeStyle = rgba(darken(p.main, 0.5), 0.45); ctx.lineWidth = 0.4; ellPath(ctx, 0, y + 0.2, g.rx * 0.62, g.ry * 0.58); ctx.stroke(); }
  ctx.strokeStyle = m[3]; ctx.lineWidth = 0.6; ellPath(ctx, 0, y, g.rx - 0.3, g.ry - 0.15); ctx.stroke();
  // the back: a curved band standing on the seat's edge round theta
  const n = 14, hs = g.hs;
  const pt = (a, inner, up) => { const rb = g.rx - g.inset - (inner ? g.t : 0), rby = (g.ry - g.inset * 0.45) * rb / (g.rx - g.inset);
    return [rb * Math.cos(a), g.seatY + rby * Math.sin(a) - (up ? g.h : 0)]; };
  const segs = [];
  for (let i = 0; i < n; i++) { const a1 = theta - hs + 2 * hs * i / n, a2 = theta - hs + 2 * hs * (i + 1) / n; segs.push([a1, a2, (a1 + a2) / 2]); }
  segs.sort((a, b) => Math.sin(a[2]) - Math.sin(b[2]));
  for (const [a1, a2, mid] of segs) {
    const outer = Math.sin(mid) > 0, k = -Math.cos(mid) * 0.13 * (outer ? 1 : -1);
    quadFill(ctx, [pt(a1, outer, false), pt(a2, outer, false), pt(a2, outer, true), pt(a1, outer, true)], shade(outer ? p.rear : p.main, k));
  }
  for (const f of g.lounge ? [0.2, 0.4, 0.6, 0.8] : [0.5]) {
    const a = theta - hs + 2 * hs * f, outer = Math.sin(a) > 0;
    if (!outer && !g.lounge) continue;
    const b = pt(a, outer, false), t = pt(a, outer, true);
    ctx.beginPath(); ctx.moveTo(b[0], b[1] - 0.6); ctx.lineTo(t[0], t[1] + 1.2);
    ctx.strokeStyle = g.lounge ? rgba(darken(p.main, 0.55), 0.55) : m[1]; ctx.lineWidth = g.lounge ? 0.45 : 0.9; ctx.stroke();
  }
  for (const a of [theta - hs, theta + hs]) quadFill(ctx, [pt(a, false, false), pt(a, true, false), pt(a, true, true), pt(a, false, true)], p.side);
  for (const [a1, a2] of segs) quadFill(ctx, [pt(a1, false, true), pt(a2, false, true), pt(a2, true, true), pt(a1, true, true)], g.lounge ? p.cap : m[1]);
  ctx.beginPath();
  for (let i = 0; i <= n; i++) { const q = pt(theta - hs + 2 * hs * i / n, false, true); i ? ctx.lineTo(...q) : ctx.moveTo(...q); }
  ctx.strokeStyle = g.lounge ? m[3] : m[0]; ctx.lineWidth = g.lounge ? 0.6 : 0.55; ctx.lineJoin = "round"; ctx.stroke();
  ctx.restore();
}
// A table's chair at rest: every sitter faces up the table (FloorGame.sit_facing), so its back is towards us.
function chair(ctx, at, D) {
  if (forPlan) return;
  seatChair(ctx, at, Math.PI / 2, D.chairs);
}

// ---------------------------------------------------------------- a hand in play
const SAMPLE = {
  tcp: { main: "ante", side: "pair_plus", up: [["Qh", "Qs", "7d"]] },
  bj: { main: "bet", side: "twenty_one_plus_three", up: [["Ac", "Kd"]] },
  pgf: { main: "ante", side: "fortune" }, pgu: { main: "ante", side: "fortune" },
  ms: { main: "ante", side: "bonus", up: [["9s", "9c"]] },
  uth: { main: "ante", also: "blind", side: "trips", up: [["As", "Js"]] },
  lir: { main: "bet1", also: "bet2", also2: "ante", side: "bonus", up: [["Th", "Td", "4c"]] },
  hcf: { main: "ante", side: "flush", up: [["Ah", "Jh", "8h", "6h", "3h", "Kc", "2s"]] },
  bac: { main: "player", side: "tie" },
};
let glowing = false;   // (opts.glow: seat 2 is betting, its spots glowing, so drawPlay leaves it empty)
function drawPlay(ctx, D, game, T) {
  const s = SAMPLE[game], seats = T.seats === 5 ? [0, 2, 3] : [0, 2, 3, 5], amounts = [1000, 2500, 500, 1500];
  // dealer's cards
  if (game === "bac") { ["8d", "Ks", "??"].forEach((c, k) => k < 2 && card(ctx, D, c, ...T.dealer_cards[k])); ["4h", "3c"].forEach((c, k) => card(ctx, D, c, ...T.dealer_cards[3 + k])); }
  else if (game === "uth") T.dealer_cards.forEach((p, k) => card(ctx, D, k < 2 ? "??" : ["Kh", "7s", "2d", "??", "??"][k - 2], ...p));
  else if (game === "bj") { card(ctx, D, "9c", ...T.dealer_cards[0]); card(ctx, D, "??", ...T.dealer_cards[1]); }
  else T.dealer_cards.forEach(p => card(ctx, D, "??", ...p));
  seats.forEach((seat, j) => {
    const S = T.spots[seat], you = seat === 2;
    if (you && glowing) return;   // (you're still betting: the spot glow's showing)
    if (game === "pgf" || game === "pgu") {
      const [lo, hi] = T.cards[seat];
      if (you) { card(ctx, D, "Kd", lo[0], lo[1] - 1.5); card(ctx, D, "Ks", lo[0], lo[1] + 1.5);
        ["Ah", "Qc", "Jd", "Ts", "9h"].forEach((c, k) => card(ctx, D, c, hi[0] - 4 + k * 2, hi[1], Math.PI / 2)); }
      else for (let k = 0; k < 7; k++) card(ctx, D, "??", lo[0] + Math.sin(k * 2.1) * 0.6, lo[1] - k * 0.25);
    } else if (T.cards[seat] && T.cards[seat].length) {
      T.cards[seat].forEach((p, k) => card(ctx, D, you && s.up ? s.up[0][k] : "??", p[0], p[1]));
    }
    stack(ctx, D, amounts[j], ...S[s.main].at);
    if (s.also) stack(ctx, D, amounts[j], ...S[s.also].at);
    if (s.also2) stack(ctx, D, amounts[j], ...S[s.also2].at);
    if (you || seat === 5) stack(ctx, D, 500, ...S[s.side].at);
    if (S.jackpot && seat === 0) stack(ctx, D, 100, ...S.jackpot.at);
  });
}

// ---------------------------------------------------------------- the fixed-layout overlay
function drawFixed(ctx, T) {
  ctx.save(); ctx.setLineDash([1.2, 0.8]); ctx.strokeStyle = "#46e0ff"; ctx.lineWidth = 0.35;
  for (const S of T.spots) for (const k in S) { const [x, y] = S[k].at; ctx.beginPath(); ctx.arc(x, y, S[k].r, 0, 7); ctx.stroke(); ctx.beginPath(); ctx.moveTo(x - 1.2, y); ctx.lineTo(x + 1.2, y); ctx.moveTo(x, y - 1.2); ctx.lineTo(x, y + 1.2); ctx.stroke(); }
  const r14 = p => ctx.strokeRect(p[0] - 7, p[1] - 10, 14, 20);
  T.cards.forEach(cs => cs.forEach(r14)); T.dealer_cards.forEach(r14);
  for (const k of ["shuffler", "discard"]) if (T[k]) ctx.strokeRect(T[k][0] - 12, T[k][1] - 9, 24, 18);
  if (T.shoe) ctx.strokeRect(T.shoe[0] - 14, T.shoe[1] - 8, 28, 16);
  ctx.strokeRect(...T.tray);
  ctx.setLineDash([]); ctx.restore();
}

// ---------------------------------------------------------------- Roulette and Craps (ports of rou_felt.gd, crp_felt.gd)
const WOOD_DARK = "#4a2412", RECESS = "#1a0b05", SHEEN = "255,226,190";
// The wheel's bowl in each wood (TableStyle.WHEEL_WOODS); its track, floor and cone are shades of it.
const WHEEL_WOODS = { mahogany: "#4e2814", walnut: "#4a3222", wenge: "#302520", rosewood: "#4c1f17", ebony: "#1c1917" };
const DICE = { red: ["#f04a4f", "#a5101a"], green: ["#3fcf7a", "#0d6b34"], blue: ["#4a8ff0", "#0f3c9a"], smoke: ["#8a8f96", "#2c3036"],
  amber: ["#f2b04a", "#9a5a0c"], violet: ["#a77bf0", "#4a1f9a"] };
const SEAT_COLOURS = ["#5ab0e8", "#f2c14e", "#ef7aa0", "#5fd3a0", "#a98ef2", "#e8935a"];
const centre = r => [r[0] + r[2] / 2, r[1] + r[3] / 2];
const add = (p, dx, dy) => [p[0] + dx, p[1] + dy];
function scaled(c, k) { return "#" + hex(c).map((v, i) => Math.min(255, Math.round(v * k[i])).toString(16).padStart(2, "0")).join(""); }
function metalOf(key) { const m = BEADS[key] || BEADS.brass; return [m[0], mix(m[0], m[1], 0.6)]; }

// The table's base: shadows, rail, felt, (border), bead.
function drawBase(ctx, S, D, felt) {
  if (!forPlan) {
    fillPoly(ctx, shift(S.g(S.rail + 4), 0, 3), "rgba(0,0,0,.16)");
    fillPoly(ctx, shift(S.g(S.rail + 1.5), 0, 2), "rgba(0,0,0,.3)");
  }
  drawRail(ctx, S, D, felt, false);
  drawFelt(ctx, S, D, felt);
  drawBorder(ctx, S, D, felt, false);
  drawBead(ctx, D, felt);
}
// Roulette's float and Craps' rack (StyledFelt.float_tray): a frame in the rail's wood, or just the well cut in.
function floatTray(ctx, D, r, felt, fin, frame) {
  const [x, y, w, h] = r, bead = BEADS[D.rail.bead];
  const C = { ...D, chips: "classic" };
  if (fin === "steel") {
    const m = bead ? bead[0] : "#6d757c";
    ctx.beginPath(); rrect(ctx, x - 0.5, y - 0.5, w + 1, h + 1, 2.8); ctx.fillStyle = "rgba(0,0,0,.6)"; ctx.fill();
    ctx.beginPath(); rrect(ctx, x, y, w, h, 2.4); ctx.fillStyle = m; ctx.fill();
    const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, "rgba(255,255,255,.35)"); g.addColorStop(0.4, "rgba(255,255,255,0)"); g.addColorStop(1, "rgba(0,0,0,.35)");
    ctx.fillStyle = g; ctx.fill();
    wellChannels(ctx, C, x + 1.3, y + 1.3, w - 2.6, h - 2.6, "steel");
    return;
  }
  let well = r;
  if (frame) {
    const W = WOODS[D.rail.wood];
    ctx.beginPath(); rrect(ctx, x, y, w, h, 2.5); ctx.fillStyle = "#2a160b"; ctx.fill(); ctx.fillStyle = pat(ctx, W.tex, W.tile); ctx.fill();
    if (bead) { ctx.save(); ctx.beginPath(); path(ctx, felt); ctx.clip(); ctx.beginPath(); rrect(ctx, x, y, w, h, 2.5); ctx.strokeStyle = bead[0]; ctx.lineWidth = 0.6; ctx.stroke(); ctx.restore(); }
    well = [x + 1.6, y + 1.6, w - 3.2, h - 3.2];
  }
  const [wx, wy, ww, wh] = well;
  wellChannels(ctx, C, wx, wy, ww, wh, "wood");
  ctx.beginPath(); ctx.moveTo(wx + 1.4, wy + wh - 0.25); ctx.lineTo(wx + ww - 1.4, wy + wh - 0.25); ctx.strokeStyle = `rgba(${SHEEN},.28)`; ctx.lineWidth = 0.35; ctx.stroke();
  if (!frame && bead) { ctx.beginPath(); rrect(ctx, x - 0.5, y - 0.5, w + 1, h + 1, 2.1); ctx.strokeStyle = bead[0]; ctx.lineWidth = 0.5; ctx.stroke(); }
  if (fin === "lid") lid(ctx, wx - 0.3, wy - 0.3, ww + 0.6, wh + 0.6);
}

function ringSeg(ctx, r0, r1, a0, a1, style) {
  ctx.beginPath(); ctx.arc(0, 0, r1, a0, a1); ctx.arc(0, 0, r0, a1, a0, true); ctx.closePath(); ctx.fillStyle = style; ctx.fill();
}
function circle(ctx, x, y, r, style) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fillStyle = style; ctx.fill(); }
function ring(ctx, x, y, r, style, w) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.strokeStyle = style; ctx.lineWidth = w; ctx.stroke(); }

// The wheel at rest (RouletteWheel: the bowl, the deflectors, the rotor's pockets and numbers, the cone, the turret).
function wheel(ctx, D, at, order) {
  const [brass, hi] = metalOf(D.wheel.metal), ink = D.print.ink;
  const bowl = WHEEL_WOODS[D.wheel.wood === "match" || !WHEEL_WOODS[D.wheel.wood] ? D.rail.wood : D.wheel.wood] || WHEEL_WOODS.mahogany;
  const red = new Set(G.rou.red), STEP = Math.PI * 2 / 37;
  ctx.save(); ctx.translate(at[0], at[1]);
  circle(ctx, 0.8, 1.6, 46.8, "rgba(0,0,0,.3)");
  circle(ctx, 0, 0, 46, bowl);
  circle(ctx, -6, -7, 38, "rgba(153,82,43,.25)");
  ring(ctx, 0, 0, 46, brass, 1.0);
  circle(ctx, 0, 0, 40, scaled(bowl, [0.95, 1.05, 1.15]));
  ring(ctx, 0, 0, 40, "rgba(255,219,178,.25)", 0.5);
  circle(ctx, 0, 0, 34, scaled(bowl, [0.46, 0.45, 0.5]));
  for (let i = 0; i < 8; i++) {
    const a = i * Math.PI / 4 + Math.PI / 8, c = [Math.cos(a) * 35.8, Math.sin(a) * 35.8], b = a + (i % 2 ? Math.PI / 2 : 0);
    const al = [Math.cos(b), Math.sin(b)], ac = [al[1], -al[0]];
    fillPoly(ctx, [[c[0] - al[0] * 2.2, c[1] - al[1] * 2.2], [c[0] - ac[0] * 0.9, c[1] - ac[1] * 0.9], [c[0] + al[0] * 2.2, c[1] + al[1] * 2.2], [c[0] + ac[0] * 0.9, c[1] + ac[1] * 0.9]], hi);
  }
  order.forEach((n, k) => {
    const a = k * STEP - Math.PI / 2;
    ringSeg(ctx, 27, 33, a - STEP / 2, a + STEP / 2, n === 0 ? D.numbers.zero : red.has(n) ? D.numbers.red : D.numbers.black);
    ringSeg(ctx, 22, 27, a - STEP / 2, a + STEP / 2, "rgba(0,0,0,.45)");
    const a0 = a - STEP / 2;
    ctx.beginPath(); ctx.moveTo(Math.cos(a0) * 22, Math.sin(a0) * 22); ctx.lineTo(Math.cos(a0) * 33, Math.sin(a0) * 33); ctx.strokeStyle = brass; ctx.lineWidth = 0.35; ctx.stroke();
    ctx.save(); ctx.translate(Math.cos(a) * 30, Math.sin(a) * 30); ctx.rotate(a + Math.PI / 2); ctx.scale(0.11, 0.11);
    ctx.font = `700 30px ${SANS}`; ctx.textAlign = "center"; ctx.fillStyle = ink; ctx.fillText(String(n), 0, 10.5); ctx.restore();
  });
  ring(ctx, 0, 0, 27, brass, 0.5);
  circle(ctx, 0, 0, 22, scaled(bowl, [1.36, 1.33, 1.25]));
  circle(ctx, -4, -5, 14, "rgba(191,115,56,.35)");
  ring(ctx, 0, 0, 22, brass, 0.6);
  for (let i = 0; i < 4; i++) {
    const a = i * Math.PI / 2, tip = [Math.cos(a) * 11, Math.sin(a) * 11];
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(tip[0], tip[1]); ctx.strokeStyle = hi; ctx.lineWidth = 1.4; ctx.lineCap = "round"; ctx.stroke();
    circle(ctx, tip[0], tip[1], 1.5, hi);
  }
  circle(ctx, 0, 0, 3.2, hi);
  ctx.restore();
}

// A seat's roulette chip (they're in the seat's colour).
function rouChip(ctx, x, y, colour, n) {
  for (let i = 0; i < n; i++) {
    const yy = y - i * 1.2;
    circle(ctx, x + 0.4, yy + 0.8, 4.8, "rgba(0,0,0,.3)");
    circle(ctx, x, yy, 4.6, colour);
    for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3; ctx.beginPath(); ctx.arc(x, yy, 3.9, a, a + 0.4); ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 0.9; ctx.lineCap = "butt"; ctx.stroke(); }
    ring(ctx, x, yy, 2.8, "rgba(255,255,255,.5)", 0.3);
  }
}

function drawRoulette(ctx, D, rect, opts) {
  const R = G.rou, S = shapeOf("rou"), felt = R.felt, g = R.grid, ink = D.print.ink, line = rgba(ink, 0.9);
  drawCarpet(ctx, rect);
  if (R.dealer) drawDealer(ctx, R.dealer);
  drawBase(ctx, S, D, felt);
  floatTray(ctx, D, R.tray, felt, D.float, true);
  // The hole the losing chips go down, rimmed in the wheel's metal.
  const [hx, hy] = R.hole, hr = R.hole_r;
  circle(ctx, hx, hy + 0.6, hr + 0.8, "rgba(0,0,0,.3)"); circle(ctx, hx, hy, hr, "#3a1a0c"); circle(ctx, hx, hy, hr - 1.2, "#120604"); circle(ctx, hx, hy + 0.6, hr - 2.4, "#000");
  ring(ctx, hx, hy, hr, metalOf(D.wheel.metal)[1], 1.1);
  ctx.beginPath(); ctx.arc(hx, hy, hr - 1, Math.PI * 1.1, Math.PI * 1.9); ctx.strokeStyle = "rgba(0,0,0,.5)"; ctx.lineWidth = 0.6; ctx.stroke();
  text(ctx, "ROULETTE", R.title[0], R.title[1], 8, ink, D);
  text(ctx, "SINGLE ZERO · LA PARTAGE · £1 – £100 STRAIGHT UP", R.title[0], R.title[1] + 7.5, 3.1, rgba(ink, 0.8), D);
  // The layout: fills, the diamonds, the grid as one set of lines, the lettering.
  const right = g.gx + 12 * g.bw, bottom = g.ey + g.eh, col = n => Math.floor((n - 1) / 3), row = n => 2 - (n - 1) % 3, red = new Set(R.red);
  fillPoly(ctx, [[g.gx, g.gy], [g.zx + 5, g.gy], [g.zx, g.gy + 1.5 * g.bh], [g.zx + 5, g.gy + 3 * g.bh], [g.gx, g.gy + 3 * g.bh]], D.numbers.zero);
  for (let n = 1; n <= 36; n++) { ctx.fillStyle = red.has(n) ? D.numbers.red : D.numbers.black; ctx.fillRect(g.gx + col(n) * g.bw, g.gy + row(n) * g.bh, g.bw, g.bh); }
  for (const i of [2, 3]) {
    const c = [g.gx + i * 2 * g.bw + g.bw, g.ey + g.eh / 2], dm = [[c[0], c[1] - 4.5], [c[0] + 9, c[1]], [c[0], c[1] + 4.5], [c[0] - 9, c[1]]];
    fillPoly(ctx, dm, i === 2 ? D.numbers.red : D.numbers.black); strokePoly(ctx, dm, rgba(ink, 0.7), 0.5);
  }
  strokePoly(ctx, [[g.zx + 5, g.gy], [right + g.bw, g.gy], [right + g.bw, g.gy + 3 * g.bh], [right, g.gy + 3 * g.bh], [right, bottom], [g.gx, bottom],
    [g.gx, g.gy + 3 * g.bh], [g.zx + 5, g.gy + 3 * g.bh], [g.zx, g.gy + 1.5 * g.bh]], line, 0.7);
  const seg = (x0, y0, x1, y1) => { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.strokeStyle = line; ctx.lineWidth = 0.7; ctx.stroke(); };
  for (const r of [1, 2]) seg(g.gx, g.gy + r * g.bh, right + g.bw, g.gy + r * g.bh);
  for (const y of [g.gy + 3 * g.bh, g.dy + g.dh]) seg(g.gx, y, right, y);
  for (let c = 0; c <= 12; c++) seg(g.gx + c * g.bw, g.gy, g.gx + c * g.bw, g.gy + 3 * g.bh);
  for (const k of [4, 8]) seg(g.gx + k * g.bw, g.gy + 3 * g.bh, g.gx + k * g.bw, bottom);
  for (const k of [2, 6, 10]) seg(g.gx + k * g.bw, g.ey, g.gx + k * g.bw, bottom);
  text(ctx, "0", (g.zx + g.gx) / 2 + 1, g.gy + 1.5 * g.bh, 8, ink, D);
  for (let n = 1; n <= 36; n++) text(ctx, String(n), g.gx + col(n) * g.bw + g.bw / 2, g.gy + row(n) * g.bh + g.bh / 2 + 0.3, 6.4, ink, D);
  for (let r = 0; r < 3; r++) text(ctx, "2 to 1", right + g.bw / 2, g.gy + r * g.bh + g.bh / 2, 3.3, ink, D);
  ["1st 12", "2nd 12", "3rd 12"].forEach((s, k) => text(ctx, s, g.gx + k * 4 * g.bw + 2 * g.bw, g.dy + g.dh / 2, 5, ink, D));
  for (const [i, s] of [[0, "1 – 18"], [1, "EVEN"], [4, "ODD"], [5, "19 – 36"]]) text(ctx, s, g.gx + i * 2 * g.bw + g.bw, g.ey + g.eh / 2, 4.6, ink, D);
  wheel(ctx, D, R.wheel, R.wheel_order);
  if (opts.play) Object.values(R.chips).forEach((at, i) => rouChip(ctx, at[0] + (i % 2) * 1.5, at[1], SEAT_COLOURS[i % SEAT_COLOURS.length], 1 + (i % 3)));
  R.chairs.forEach(c => chair(ctx, c, D));
}

// A printed die on the craps layout, and a real one.
function miniDie(ctx, at, n, s, face, pip) {
  ctx.beginPath(); rrect(ctx, at[0] - s / 2, at[1] - s / 2, s, s, s * 0.18); ctx.fillStyle = face; ctx.fill();
  for (const p of G.crp.pips[n]) circle(ctx, at[0] + p[0] * s * 0.27, at[1] + p[1] * s * 0.27, s * 0.09, pip);
}
function die(ctx, at, n, tone, turn = 0) {
  const s = 6.2;
  ctx.save(); ctx.translate(at[0] + 0.6, at[1] + 0.9); ctx.scale(1, 0.78); circle(ctx, 0, 0, 3.6, "rgba(0,0,0,.42)"); ctx.restore();
  ctx.save(); ctx.translate(at[0], at[1]); ctx.rotate(turn);
  const g = ctx.createLinearGradient(-s / 2, -s / 2, s / 2, s / 2); g.addColorStop(0, tone[0]); g.addColorStop(1, tone[1]);
  ctx.beginPath(); rrect(ctx, -s / 2, -s / 2, s, s, s * 0.18); ctx.fillStyle = g; ctx.fill(); ctx.strokeStyle = "rgba(255,255,255,.35)"; ctx.lineWidth = 0.3; ctx.stroke();
  for (const p of G.crp.pips[n]) circle(ctx, p[0] * s * 0.27, p[1] * s * 0.27, s * 0.085, "#fff");
  ctx.restore();
}
// Points every `step` along a path, with the path's direction there (crp_felt.gd _along).
function along(pts, step) {
  const out = []; let into = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const dx = pts[i + 1][0] - pts[i][0], dy = pts[i + 1][1] - pts[i][1], seg = Math.hypot(dx, dy);
    if (seg <= 0) continue;
    const dir = [dx / seg, dy / seg];
    while (into <= seg) { out.push([[pts[i][0] + dir[0] * into, pts[i][1] + dir[1] * into], dir]); into += step; }
    into -= seg;
  }
  return out;
}

function drawCraps(ctx, D, rect, opts) {
  const C = G.crp, S = shapeOf("crp"), felt = C.felt, ink = D.print.ink, line = rgba(ink, 0.9), gold = D.print.accent, red = D.print.red;
  const face = rgba(ink, 0.92), pip = darken(D.felt.colour, 0.37);
  const t = (s, at, size, colour, angle) => text(ctx, s, at[0], at[1], size, colour, D, { angle });
  drawCarpet(ctx, rect);
  if (C.boxman) drawDealer(ctx, C.boxman);
  drawBase(ctx, S, D, felt);
  // The rubber pyramids lining both end walls, seen as two zigzags.
  const rw = C.rubber_w, ridge = lum(D.rubber) < 0.05 ? "rgba(255,255,255,.18)" : "rgba(255,255,255,.3)";
  for (const h of ["1", "-1"]) {
    const R = C.rubber[h];
    fillPoly(ctx, [...R.edge, ...[...R.inner].reverse()], D.rubber);
    const zig = [[], []];
    along(R.mid, rw * 0.75).forEach(([p, d], k) => { const ac = [d[1] * rw / 2, -d[0] * rw / 2], sg = k % 2 === 0 ? 1 : -1;
      zig[0].push([p[0] + ac[0] * sg, p[1] + ac[1] * sg]); zig[1].push([p[0] - ac[0] * sg, p[1] - ac[1] * sg]); });
    for (const z of zig) { ctx.beginPath(); path(ctx, z, false); ctx.strokeStyle = ridge; ctx.lineWidth = 0.35; ctx.lineJoin = "miter"; ctx.stroke(); }
  }
  // The players' chip rail: a groove sunk into the rail.
  const hw = C.groove_w / 2;
  for (const h of ["1", "-1"]) {
    const Gr = C.groove[h];
    strokePoly(ctx, Gr.mid, rgba(WOOD_DARK, 0.9), 2 * (hw + 0.4), false);
    strokePoly(ctx, Gr.mid, RECESS, 2 * hw, false);
    strokePoly(ctx, Gr.in, "rgba(0,0,0,.6)", 0.6, false);
    strokePoly(ctx, Gr.out, "rgba(255,214,171,.25)", 0.4, false);
  }
  floatTray(ctx, D, C.tray, felt, D.rack, false);
  // The printed lines, then the lettering.
  for (const h of ["1", "-1"]) for (const p of Object.values(C.polys[h])) strokePoly(ctx, p, line, 0.7);
  for (const r of Object.values(C.props)) { ctx.strokeStyle = line; ctx.lineWidth = 0.7; ctx.strokeRect(r[0], r[1], r[2], r[3]); }
  { const r = C.prop_box; ctx.lineWidth = 0.9; ctx.strokeRect(r[0], r[1], r[2], r[3]); }
  strokePoly(ctx, C.pass, line, 0.7);
  for (const hs of ["1", "-1"]) {
    const h = +hs, z = C.zones[hs], dc = centre(z.dont_come);
    t("DON'T", add(dc, 0, -6.5), 3.3, ink); t("COME", add(dc, 0, -2.5), 3.3, ink); t("BAR", add(dc, 0, 3), 2.6, ink);
    miniDie(ctx, add(dc, -3.2, 7.5), 6, 5, face, pip); miniDie(ctx, add(dc, 3.2, 7.5), 6, 5, face, pip);
    for (const n of C.nums) {
      const label = { 6: "SIX", 9: "NINE" }[n] || String(n);
      t(label, add(centre(z["place_" + n]), 0, 0.5), label.length > 2 ? 5.2 : 8.2, n === 6 || n === 8 ? gold : ink);
      t("LAY", add(centre(z["lay_" + n]), 0, 0.3), 2.6, ink); t("BUY", add(centre(z["buy_" + n]), 0, 0.3), 2.6, ink);
    }
    t("COME", add(centre(z.come), 0, 0.5), 13, red);
    const fi = z.field, fy = centre(fi)[1], step = (fi[2] - 12) / 6;
    t("FIELD", [centre(fi)[0], fy + 5.5], 6.5, gold);
    ["2", "3", "4", "9", "10", "11", "12"].forEach((s, i) => { const at = [fi[0] + 6 + i * step, fy - 4]; if (s === "2" || s === "12") ring(ctx, at[0], at[1], 3.6, gold, 0.5); t(s, add(at, 0, 0.2), 4.4, ink); });
    t("PAYS DOUBLE", [fi[0] + 13, fi[1] + fi[3] - 2.6], 1.8, gold); t("PAYS TRIPLE", [fi[0] + fi[2] - 13, fi[1] + fi[3] - 2.6], 1.8, gold);
    const dp = centre(z.dont_pass);
    t("DON'T PASS BAR", add(dp, -6, 0.3), 3.8, ink); miniDie(ctx, add(dp, 24, 0), 6, 5, face, pip); miniDie(ctx, add(dp, 30.5, 0), 6, 5, face, pip);
    t("6", add(centre(z.big6), -3 * h, -1), 8, red); t("8", add(centre(z.big8), 3 * h, 1), 8, red);
    t("PASS LINE", [C.mx[hs][0], -19.7], 4.6, ink); t("PASS LINE", [C.mx[hs][1], -61], 4.6, ink, h * Math.PI / 2);
  }
  t("PASS LINE", [0, -19.7], 4.6, ink);
  const pc = id => centre(C.props[id]);
  t("SEVEN  ·  4 TO 1", add(pc("any7"), 0, 0.3), 3.6, red);
  for (const [id, a, b, odds] of [["hard6", 3, 3, "9 TO 1"], ["hard10", 5, 5, "7 TO 1"], ["hard8", 4, 4, "9 TO 1"], ["hard4", 2, 2, "7 TO 1"],
      ["two", 1, 1, "30 TO 1"], ["twelve", 6, 6, "30 TO 1"], ["three", 1, 2, "15 TO 1"], ["eleven", 5, 6, "15 TO 1"]]) {
    const box = C.props[id], c = centre(box), s = Math.min(7, box[3] * 0.5);
    miniDie(ctx, add(c, -s * 0.6, -box[3] * 0.16), a, s, face, pip); miniDie(ctx, add(c, s * 0.6, -box[3] * 0.16), b, s, face, pip);
    t(odds, add(c, 0, box[3] * 0.33), Math.min(2.5, box[3] * 0.2), ink);
  }
  t("HORN", add(pc("horn"), 0, 0.3), 4, gold);
  const ce = pc("ce");
  for (const sd of [-1, 1]) ring(ctx, ce[0] + 5 * sd, ce[1], 3.6, ink, 0.5);
  t("C", add(ce, -5, 0.3), 3.8, ink); t("E", add(ce, 5, 0.3), 3.8, ink);
  t("ANY CRAPS  ·  7 TO 1", add(pc("any_craps"), 0, 0.3), 3.6, red);
  const tone = DICE[D.dice] || DICE.red;
  if (opts.play) {
    const z = C.zones["1"], C2 = { chips: "classic" };
    stack(ctx, C2, 2500, 96, -9); stack(ctx, C2, 1000, ...add(centre(z.place_6), 0, 2)); stack(ctx, C2, 500, ...centre(z.field));
    die(ctx, [118, -96], 5, tone, 0.3); die(ctx, [128, -90], 2, tone, -0.5);
  } else {
    for (const [i, at] of C.dice.entries()) die(ctx, at, [6, 1][i], tone);
  }
}

// ---------------------------------------------------------------- one picture
export function render(canvas, D, game, rect, opts = {}) {
  const T = G.tables[game] || {}, cssW = canvas.clientWidth || canvas.width || 600;
  const dpr = Math.min(2.5, window.devicePixelRatio || 1), k = cssW / rect[2];
  canvas.width = Math.round(cssW * dpr); canvas.height = Math.round(rect[3] * k * dpr);
  if (!canvas.clientWidth) canvas.style.width = cssW + "px";
  const ctx = canvas.getContext("2d");
  ctx.setTransform(k * dpr, 0, 0, k * dpr, -rect[0] * k * dpr, -rect[1] * k * dpr);
  bare = !!opts.bare;
  glowing = !!opts.glow;
  forPlan = !!opts.plan;
  if (opts.seating) seatShape = opts.seating;
  if (game === "rou" || game === "crp") { (game === "rou" ? drawRoulette : drawCraps)(ctx, D, rect, opts); return; }
  const S = CARD_SHAPE, ledge = D.tray.mode === "ledge", felt = feltPoly(D.tray.mode);
  drawCarpet(ctx, rect);
  drawDealer(ctx);
  if (!forPlan) {
    fillPoly(ctx, shift(grown("11.0"), 0, 3), "rgba(0,0,0,.16)");
    fillPoly(ctx, shift(grown("7.5"), 0, 2), "rgba(0,0,0,.3)");
  }
  drawRail(ctx, S, D, felt, ledge);
  drawFelt(ctx, S, D, felt);
  drawBorder(ctx, S, D, felt, ledge);
  drawBead(ctx, D, felt);
  drawTray(ctx, D, ledge);
  const L = layout(game, T, D);
  for (const [s, x, y, size, role, a] of L.tx) text(ctx, s, x, y, size, rgba(colourOf(D, role), a), D, { foil: D.spots === "foil" && size >= 8 ? colourOf(D, role) : false });
  L.sp.forEach(s => drawSpot(ctx, D, s));
  L.jp.forEach((at, i) => jackpotDisc(ctx, D, at, opts.lit && i === 3));
  L.draw.forEach(f => f(ctx));
  if (T.discard) rack(ctx, D, T.discard);
  if (opts.play && SAMPLE[game]) drawPlay(ctx, D, game, T);
  if (T.shoe) shoe(ctx, D, T.shoe);
  if (T.shuffler) shuffler(ctx, D, T.shuffler);
  T.chairs.forEach(c => chair(ctx, c, D));
  if (opts.fixed) drawFixed(ctx, T);
}

// ---------------------------------------------------------------- the spot glow (SpotGlow.gd)
// The light round the spots waiting for your chips, on seat 2 ("you"), drawn over a render() of the table: its
// primary bets (stage 0), or once one has chips on it, its side bets (stage 1, the chips drawn). `t` is seconds,
// `since` when the stage began (it fades in). The same halo, lit edge and wash as the game.
const GLOW = { breath: 2.4, fade: 0.4, bands: 4, step: 0.85 };
export function drawGlow(canvas, D, game, rect, t, stage, since) {
  const T = G.tables[game];
  if (!T || !T.spots || !T.spots[2]) return;
  const ctx = canvas.getContext("2d"), k = canvas.width / rect[2], S = T.spots[2], primary = T.primary || [];
  ctx.setTransform(k, 0, 0, k, -rect[0] * k, -rect[1] * k);
  if (stage) for (const p of game === "bac" ? ["banker"] : primary) stack(ctx, D, 1000, ...S[p].at);
  const names = Object.keys(S).filter(n => S[n].shape && primary.includes(n) !== !!stage);
  let fade = Math.min(1, Math.max(0, (t - since) / GLOW.fade));
  fade = fade * fade * (3 - 2 * fade);
  const breath = 0.5 + 0.5 * Math.sin(t * 2 * Math.PI / GLOW.breath), a = fade * (0.72 + 0.28 * breath);
  const colour = D.glow || "#ffdf9e", bright = mix(colour, "#ffffff", 0.45);
  for (const n of names) {
    const s = S[n].shape, pts = outlinePts(s);
    // The halo: Godot steps out from the edge in separate lines; here each band is a wide stroke outside the spot,
    // the outer ones under the inner, so the alpha falls the same way.
    ctx.save();
    ctx.beginPath(); ctx.rect(s.at[0] - 60, s.at[1] - 60, 120, 120); path(ctx, pts); ctx.clip("evenodd");
    const alpha = i => i >= GLOW.bands ? 0 : 0.34 * a * Math.pow(1 - i / GLOW.bands, 1.6) * (0.85 + 0.3 * breath);
    for (let i = GLOW.bands - 1; i >= 0; i--) strokePoly(ctx, pts, rgba(colour, alpha(i) - alpha(i + 1)), 2 * (0.55 + i * GLOW.step + 0.55));
    ctx.restore();
    fillPoly(ctx, pts, rgba(colour, 0.08 * a));
    strokePoly(ctx, pts, rgba(bright, 0.7 * a), 0.5);
  }
}
// A spot's outline as points (StyledFelt.shape, TableFelt._rounded).
function outlinePts(s) {
  const [x, y] = s.at;
  let pts = [];
  if (s.shape === "circle") for (let i = 0; i < 40; i++) { const a = 2 * Math.PI * i / 40; pts.push([x + Math.cos(a) * s.r, y + Math.sin(a) * s.r]); }
  else if (s.shape === "diamond") pts = [[x, y - s.hh], [x + s.hw, y], [x, y + s.hh], [x - s.hw, y]];
  else {
    const r = Math.min(s.rad || 1.2, s.w / 2, s.h / 2), x0 = x - s.w / 2, y0 = y - s.h / 2, x1 = x + s.w / 2, y1 = y + s.h / 2;
    for (const [cx, cy, a0] of [[x1 - r, y1 - r, 0], [x0 + r, y1 - r, Math.PI / 2], [x0 + r, y0 + r, Math.PI], [x1 - r, y0 + r, Math.PI * 1.5]])
      for (let i = 0; i < 5; i++) { const a = a0 + Math.PI / 2 * i / 4; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); }
  }
  return pts;
}

// ---------------------------------------------------------------- the Floor plan tab's pieces (render's opts.plan)
/** A table's shadow on the floor, in its own coordinates: `down` is down the screen in them, so it falls the same
 *  way however the table's turned (TableFelt._lit). */
export function planShadow(ctx, game, down) {
  const S = game === "rou" || game === "crp" ? shapeOf(game) : null;
  const big = S ? S.g(S.rail + 4) : grown("11.0"), small = S ? S.g(S.rail + 1.5) : grown("7.5");
  fillPoly(ctx, shift(big, down[0] * 3, down[1] * 3), "rgba(0,0,0,.16)");
  fillPoly(ctx, shift(small, down[0] * 2, down[1] * 2), "rgba(0,0,0,.3)");
}

/** A chair at `at` (where its sitter's feet go), upright on screen, its back pointing `back` (radians on screen:
 *  PI / 2 is towards us), in `colours` ({frame, upholstery}: its table style's `chairs`). */
export function planChair(ctx, at, back, colours) {
  seatChair(ctx, at, back, colours);
}

/** A craps player's standing spot at `at`: a brass-rimmed plate on the floor. */
export function planSpot(ctx, at) {
  ctx.save(); ctx.translate(at[0], at[1] + 4);
  ctx.beginPath(); ctx.ellipse(0, 0, 11, 5.5, 0, 0, 7); ctx.fillStyle = "rgba(13,8,4,.82)"; ctx.fill();
  ctx.strokeStyle = "#c99a3c"; ctx.lineWidth = 1; ctx.stroke();
  ctx.restore();
}

/** A dealer standing at `at`, facing `facing` on screen. */
export function planDealer(ctx, at, facing = "down") {
  const was = forPlan; forPlan = false; drawDealer(ctx, at, { up: 4, left: 5, down: 6, right: 7 }[facing] ?? 6); forPlan = was;
}
