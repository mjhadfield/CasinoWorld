/* The Maths step's worker: simulates a design's variant off the page, and tunes one control to a target return.
   Messages in: {cmd: "sim", params, spins, buys} | {cmd: "tune", params, control, target, spins, buys} |
   {cmd: "sample", params}. Out: {progress} while it works, then {result} (sim), {tuned} (tune) or {sample}.
   Like the signed-off tuner (docs/slots/mockup/sim_worker.js), the trail's share comes from its own long run of
   trails times how often spins trigger it: the trail swings far too hard to sample from spins alone. The battle's
   share is measured the same way (its free games included). Buy Bonus is
   measured on its own run (one of the buyable bonuses at random each time). */
importScripts("/slot-design-ui/slots_math.js");
const M = self.SlotMath;

function report(V, spins, buys, progress = () => {}, seed = 1000) {
  const chunk = Math.min(50000, spins), parts = [];
  for (let i = 0; i < spins / chunk; i++) { parts.push(M.simulate(V, chunk, 100, seed + i)); progress((i + 1) / (spins / chunk) * 0.85); }
  const sum = (k) => parts.reduce((a, p) => a + p[k], 0);
  const r = {spins, staked: sum("staked")};
  for (const k of ["plain", "featured", "repeatExtra", "instant", "trail", "free", "battle", "hits", "trails", "frees", "battles", "featureSpins", "prizepots", "sumSq"]) r[k] = sum(k);
  r.max = Math.max(...parts.map((p) => p.max)) / 100;
  r.featureCounts = {};
  for (const p of parts) for (const [k, v] of Object.entries(p.featureCounts)) r.featureCounts[k] = (r.featureCounts[k] || 0) + v;
  const pct = (v) => (100 * v) / r.staked;
  r.rtp = {plain: pct(r.plain), featured: pct(r.featured), repeat: pct(r.repeatExtra), instant: pct(r.instant), trail: pct(r.trail),
           free: pct(r.free), battle: pct(r.battle), jackpot: 100 * M.jackpotRtp()};
  r.buy = V.buyCost && V.routes.buy.length ? M.simulateBuy(V, buys, 100, 99) : null;
  r.rtp.trailSampled = r.rtp.trail;
  r.rtp.trail = r.trails ? 100 * (r.trails / spins) * M.simulateTrail(V, buys, 100, 99).mean : 0;
  r.rtp.battleSampled = r.rtp.battle;
  if (r.battles) {
    const run = M.simulateBattle(V, Math.round(buys / 2), 100, 98);
    r.rtp.battle = 100 * (r.battles / spins) * run.mean;
    r.bosses = run.bosses; r.battleRun = run.n;
  }
  r.rtp.game = r.rtp.plain + r.rtp.featured + r.rtp.repeat + r.rtp.instant + r.rtp.trail + r.rtp.free + r.rtp.battle;
  r.rtp.total = r.rtp.game + r.rtp.jackpot;
  r.sd = Math.sqrt(r.sumSq / spins - Math.pow(r.rtp.game / 100, 2));
  r.exact = 100 * M.exactLineRtp(V.strips, V.pays);
  delete r.sumSq;
  progress(1);
  return r;
}

const clone = (x) => JSON.parse(JSON.stringify(x));
// The controls auto-tune can turn. "scale" ones multiply by k (1 = as now); "steps" ones add (or, below 0, take away)
// one symbol at a time, cycling across the reels and tiers, because reel counts are whole numbers and scaling them
// jumps (six royals a reel to five is +13 points of return). "rises": whether the return goes up as k does.
const lowsOf = (p) => Object.keys(p.counts[0]).filter((t) => t[0] === "L");
const CONTROLS = {
  pays: {kind: "scale", range: [0.4, 2.5], rises: true, describe: (k) => `All the pays ×${k.toFixed(3)}`, apply(p, k) {
    for (const t of Object.keys(p.pays)) {
      const [a, b, c] = p.pays[t].map((x) => Math.max(1, Math.round(x * k)));
      p.pays[t] = [a, Math.max(a, b), Math.max(a, b, c)];
    }
  }},
  features: {kind: "scale", range: [0, 3], rises: true, describe: (k) => `Every feature's chance ×${k.toFixed(3)}`, apply(p, k) {
    for (const f of Object.keys(p.rates)) p.rates[f] = Math.min(0.6, Math.round(p.rates[f] * k * 10000) / 10000);
  }},
  lows: {kind: "steps", range: [-40, 60], rises: false,
    describe: (n) => n > 0 ? `${n} more low symbols across the reels` : `${-n} fewer low symbols across the reels`,
    apply(p, n) {
      const lows = lowsOf(p);
      for (let i = 0; i < Math.abs(n); i++) {
        const reel = p.counts[i % 5], t = lows[Math.floor(i / 5) % lows.length];
        reel[t] = n > 0 ? reel[t] + 1 : Math.max(1, reel[t] - 1);
      }
    }},
  wilds: {kind: "steps", range: [-8, 20], rises: true,
    describe: (n) => n > 0 ? `${n} more Wilds across the reels` : `${-n} fewer Wilds across the reels`,
    apply(p, n) {   // only reels that have Wilds (Armadillo keeps reel 1 clear)
      const reels = p.counts.filter((r) => r.W > 0);
      for (let i = 0; i < Math.abs(n) && reels.length; i++) {
        const r = reels[i % reels.length];
        r.W = n > 0 ? r.W + 1 : Math.max(1, r.W - 1);
      }
    }},
};

function built(params, control, k) {
  const p = clone(params);
  p.strips = p.freeStrips = p.bigStrip = null;   // rebuilt from the (changed) counts
  CONTROLS[control].apply(p, k);
  return p;
}

onmessage = (e) => {
  const {cmd, params, spins = 200000, buys = 50000} = e.data;
  if (cmd === "sim") {
    const V = M.makeVariant(params);
    postMessage({result: report(V, spins, buys, (progress) => postMessage({progress}))});
  } else if (cmd === "tune") {
    const {control, target} = e.data, c = CONTROLS[control];
    // Bisect on runs of 200,000 spins with the same seeds each time (neighbouring tries differ only by the change),
    // then measure the two closest settings properly and keep whichever lands nearer the target.
    const quick = (k) => report(M.makeVariant(built(params, control, k)), 200000, 30000, () => {}, 7000).rtp.game;
    const want = (f) => (c.rises ? f < target : f > target);   // true: k must go up
    let [lo, hi] = c.range, steps = 0;
    const flo = quick(lo), fhi = quick(hi);
    let candidates;
    if (want(fhi)) candidates = [hi];
    else if (!want(flo)) candidates = [lo];
    else {
      while (steps++ < 12 && (c.kind === "steps" ? hi - lo > 1 : hi - lo > 0.004)) {
        const mid = c.kind === "steps" ? Math.round((lo + hi) / 2) : (lo + hi) / 2;
        if (want(quick(mid))) lo = mid; else hi = mid;
        postMessage({progress: steps / 16});
      }
      candidates = c.kind === "steps" ? [lo, hi] : [(lo + hi) / 2];
    }
    let best = null;
    candidates.forEach((k, i) => {
      const p = built(params, control, k);
      const result = report(M.makeVariant(p), spins, buys, (x) => postMessage({progress: 0.75 + (i + x) / candidates.length / 4}));
      if (!best || Math.abs(result.rtp.game - target) < Math.abs(best.result.rtp.game - target)) best = {params: p, k, result};
    });
    best.reached = Math.abs(best.result.rtp.game - target) <= 1.5;
    best.describe = c.describe(best.k);
    postMessage({tuned: best});
  } else if (cmd === "sample") {
    // What the server replays when the maths is frozen, to prove both engines play this slot the same.
    const V = M.makeVariant(params), sample = [];
    for (let s = 1; s <= 200; s++) {
      const bet = M.LADDER[s % 9], o = M.spinOutcome(V, bet, M.mulberry32(s));
      sample.push({seed: s, bet, stops: o.stops, total: o.total});
    }
    postMessage({sample: {sample, strips: V.strips, free_strips: V.freeStrips, big_strip: V.bigStrip, exact: 100 * M.exactLineRtp(V.strips, V.pays)}});
  }
};
