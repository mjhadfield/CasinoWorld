/* Runs the tuner off the page: a million spins in chunks (reporting progress), then bought bonuses. */
importScripts("slots_math.js");
onmessage = (e) => {
  const M = SlotMath, V = M.ARMADILLO, { spins, buys } = e.data;
  const chunk = 50000, parts = [];
  for (let i = 0; i < spins / chunk; i++) {
    parts.push(M.simulate(V, chunk, 100, 1000 + i));
    postMessage({ progress: (i + 1) / (spins / chunk) * 0.85 });
  }
  const sum = (k) => parts.reduce((a, p) => a + p[k], 0);
  const r = { spins, staked: sum("staked") };
  for (const k of ["plain", "featured", "repeatExtra", "instant", "trail", "free", "hits", "trails", "frees", "featureSpins", "prizepots", "sumSq"]) r[k] = sum(k);
  r.max = Math.max(...parts.map((p) => p.max));
  r.featureCounts = {};
  for (const p of parts) for (const [k, v] of Object.entries(p.featureCounts)) r.featureCounts[k] = (r.featureCounts[k] || 0) + v;
  const pct = (v) => (100 * v) / r.staked;
  r.rtp = { plain: pct(r.plain), featured: pct(r.featured), repeat: pct(r.repeatExtra), instant: pct(r.instant), trail: pct(r.trail), free: pct(r.free), jackpot: 100 * M.jackpotRtp() };
  // The trail swings hard (a 2,000x prizepot about 1 in 250), so its value comes from its own long
  // run of trails, times how often the spins triggered it.
  r.buy = M.simulateBuy(V, buys, 100, 99);
  r.rtp.trailSampled = r.rtp.trail;
  r.rtp.trail = (100 * (r.trails / spins) * r.buy.mean);
  r.rtp.game = r.rtp.plain + r.rtp.featured + r.rtp.repeat + r.rtp.instant + r.rtp.trail + r.rtp.free;
  r.rtp.total = r.rtp.game + r.rtp.jackpot;
  r.sd = Math.sqrt(r.sumSq / spins - Math.pow(r.rtp.game / 100, 2));
  r.exact = 100 * M.exactLineRtp(V.strips);
  postMessage({ progress: 1, result: r });
};
