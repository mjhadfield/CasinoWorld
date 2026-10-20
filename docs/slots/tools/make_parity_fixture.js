/* Writes the fixture tests/test_slots_parity.py checks the Python engine against: seeded
   outcomes from the signed-off mockup maths. node make_parity_fixture.js > ../../../server/tests/fixtures/slots_parity.json */
const M = require("../mockup/slots_math.js"), V = M.ARMADILLO;
const out = { rng: [], spins: [], free: [], rigged: [], trails: [], battles: [], picks: [], triggers: [], sim: null, buy: null, battleSim: null, exact: M.exactLineRtp(V.strips) };
const r0 = M.mulberry32(12345); for (let i = 0; i < 20; i++) out.rng.push(r0());
const pick = (o) => ({ stops: o.stops, grid: o.grid, landed: o.landed, after_colossal: o.afterColossal, trigger: o.trigger, colossal: o.colossal,
  wild_reels: o.wildReels, wilds: o.wilds, multiplier: o.multiplier, upgrade: o.upgrade, repeat: o.repeat, instant: o.instant,
  line_win: o.lineWin, total: o.total, features: o.features, wins: o.wins.map((w) => [w.line, w.sym, w.count, w.pence]) });
for (let s = 1; s <= 400; s++) out.spins.push({ seed: s, bet: M.LADDER[s % 9], o: pick(M.spinOutcome(V, M.LADDER[s % 9], M.mulberry32(s))) });
for (let s = 1; s <= 100; s++) out.free.push({ seed: s, o: pick(M.spinOutcome(V, 100, M.mulberry32(s), { free: true })) });
const rigs = [["wilds"], ["wildReels"], ["colossal"], ["multiplier"], ["upgrade"], ["repeat"], ["instant"], ["colossal", "wildReels", "wilds", "upgrade", "multiplier"]];
rigs.forEach((f, i) => { for (let s = 1; s <= 25; s++) out.rigged.push({ seed: s * 31 + i, features: f, o: pick(M.spinOutcome(V, 250, M.mulberry32(s * 31 + i), { rig: { features: f } })) }); });
for (const t of ["trail", "free"]) for (let s = 1; s <= 10; s++) out.rigged.push({ seed: s, trigger: t, o: pick(M.spinOutcome(V, 100, M.mulberry32(s), { rig: { trigger: t } })) });
for (let s = 1; s <= 200; s++) {
  const rng = M.mulberry32(s), st = M.trailStart(V, 100, rng);
  const rolls = M.trailPlayOut(V, st, rng);
  out.trails.push({ seed: s, total: st.total, pos: st.pos, rolls: rolls.map((r) => [r.bullets, r.from, r.path, r.events]), board: st.board });
}
// Battles: the even seeds aim at the last ship left (the target never changes the draw), the odd ones take the default.
for (let s = 1; s <= 200; s++) {
  const rng = M.mulberry32(s), bet = M.LADDER[s % 9], st = M.battleStart(V, bet), shots = [];
  while (!st.done) {
    const target = s % 2 ? undefined : st.ships.lastIndexOf(true);
    const r = M.battleShot(V, st, rng, target);
    shots.push([r.target, r.answered, r.events]);
  }
  out.battles.push({ seed: s, bet, shots, total: st.total, spins: st.spins, cleared: st.cleared, won: st.won });
}
// A variant where the bonus scatter and Buy Bonus play the battle (and the free-spins scatter plays it or the free games).
const VB = Object.assign({}, V, { routes: { BS: ["battle"], FS: ["free", "battle"], buy: ["battle"] } });
for (let s = 1; s <= 10; s++) out.rigged.push({ seed: s, trigger: "battle", o: pick(M.spinOutcome(VB, 100, M.mulberry32(s), { rig: { trigger: "battle" } })) });
const bs = M.simulate(VB, 20000, 100, 7), bb = M.simulateBuy(VB, 2000, 100, 9);
out.battleSim = { battle: bs.battle, battles: bs.battles, free: bs.free, frees: bs.frees, hits: bs.hits, buyMean: bb.mean, mean: M.simulateBattle(VB, 2000, 100, 9).mean };
for (let s = 1; s <= 50; s++) { const rng = M.mulberry32(s); const t = ["mini", "minor", "major", "grand"][s % 4]; out.picks.push({ seed: s, tier: t, p: M.pickSequence(t, rng) }); }
for (let s = 1; s <= 200; s++) { const rng = M.mulberry32(s); out.triggers.push(M.jackpotTrigger(M.LADDER[s % 9] * 400, rng)); }
const sim = M.simulate(V, 20000, 100, 7); out.sim = { plain: sim.plain, featured: sim.featured, trail: sim.trail, free: sim.free, instant: sim.instant, repeatExtra: sim.repeatExtra, trails: sim.trails, frees: sim.frees, hits: sim.hits };
const b = M.simulateBuy(V, 2000, 100, 9); out.buy = { mean: b.mean, prizepots: b.prizepots, rolls: b.rolls };
console.log(JSON.stringify(out));
