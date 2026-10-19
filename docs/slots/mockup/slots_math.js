/* Casino World slots: the maths, shared by the mockup page, its tuner worker and node.
   Money is integer pence. Cells are numbered reel * 4 + row (row 0 = top).
   Everything random goes through an rng() returning [0, 1), so a seeded rng replays exactly. */
(function (root) {
  "use strict";

  // ------------------------------------------------------------------ the shared base
  const REELS = 5, ROWS = 4;
  // The 25 lines, decoded from the rules sheet's line chart: the row on each reel.
  const LINES = [
    [1,1,1,1,1], [2,2,2,2,2], [0,0,0,0,0], [3,3,3,3,3], [1,2,3,2,1],
    [2,1,0,1,2], [0,0,1,2,3], [3,3,2,1,0], [1,0,0,0,1], [2,3,3,3,2],
    [0,1,2,3,3], [3,2,1,0,0], [1,0,1,2,1], [2,3,2,1,2], [0,1,0,1,0],
    [3,2,3,2,3], [1,2,1,0,1], [2,1,2,3,2], [0,1,1,1,0], [3,2,2,2,3],
    [1,1,2,3,3], [2,2,1,0,0], [1,1,0,1,1], [2,2,3,2,2], [1,2,2,2,3],
  ];
  // Pays for 3, 4 and 5 of a kind, in multiples of the line bet (bet / 25).
  const PAYS = {
    W: [20, 40, 120], H1: [20, 40, 120], H2: [20, 40, 100],
    M1: [16, 24, 60], M2: [16, 24, 60], M3: [12, 20, 48], M4: [12, 20, 48],
    L1: [4, 8, 20], L2: [4, 8, 20], L3: [4, 8, 20], L4: [4, 8, 20],
  };
  const PAYING = Object.keys(PAYS);
  const SCATTERS = ["BS", "FS"];
  const UPGRADES = { L1: "M3", L2: "M3", L3: "M4", L4: "M4", M3: "M1", M4: "M2", M1: "H2", M2: "H2", H2: "H1" };
  const LADDER = [25, 50, 75, 100, 150, 250, 500, 1000, 2500];
  const FEATURES = ["wilds", "wildReels", "colossal", "multiplier", "upgrade", "repeat", "instant"];

  // ------------------------------------------------------------------ rng helpers
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const int = (rng, n) => Math.floor(rng() * n);
  function weighted(rng, table) {          // table: [[value, weight], ...]
    let total = 0;
    for (const [, w] of table) total += w;
    let r = rng() * total;
    for (const [v, w] of table) { if ((r -= w) < 0) return v; }
    return table[table.length - 1][0];
  }
  function shuffle(rng, a) {
    for (let i = a.length - 1; i > 0; i--) { const j = int(rng, i + 1); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }
  function sample(rng, list, n) { return shuffle(rng, list.slice()).slice(0, n); }

  // ------------------------------------------------------------------ strips
  /* A strip from symbol counts, shuffled with a fixed seed, then nudged so scatters sit at
     least ROWS apart (a reel never shows two) and no paying symbol runs three in a row. */
  function buildStrip(counts, seed) {
    const rng = mulberry32(seed);
    const strip = [];
    for (const [sym, n] of Object.entries(counts)) for (let i = 0; i < n; i++) strip.push(sym);
    shuffle(rng, strip);
    const len = strip.length;
    const bad = (i) => {
      const s = strip[i];
      if (SCATTERS.includes(s)) {
        for (let d = 1; d < ROWS; d++) {
          if (SCATTERS.includes(strip[(i + d) % len]) || SCATTERS.includes(strip[(i - d + len) % len])) return true;
        }
      }
      return s === strip[(i + 1) % len] && s === strip[(i + 2) % len];
    };
    for (let pass = 0; pass < 2000; pass++) {
      let fixed = true;
      for (let i = 0; i < len; i++) {
        if (bad(i)) { const j = int(rng, len); [strip[i], strip[j]] = [strip[j], strip[i]]; fixed = false; }
      }
      if (fixed) break;
    }
    return strip;
  }

  // ------------------------------------------------------------------ evaluation
  /* Line wins on a grid (array of 20 symbols, cell = reel*4+row). The longest match per line
     only; Wild stands in for everything but the scatters; a run of Wilds pays as Wilds when
     that's worth more. Returns [{line, sym, count, mult (line-bet multiple), cells}]. */
  function evaluate(grid) {
    const wins = [];
    for (let l = 0; l < LINES.length; l++) {
      const cells = LINES[l].map((row, reel) => reel * ROWS + row);
      const syms = cells.map((c) => grid[c]);
      let wildRun = 0;
      while (wildRun < REELS && syms[wildRun] === "W") wildRun++;
      const target = syms.find((s) => s !== "W");
      let best = null;
      if (wildRun >= 3) best = { sym: "W", count: wildRun, mult: PAYS.W[wildRun - 3] };
      if (target && PAYS[target]) {
        let n = 0;
        while (n < REELS && (syms[n] === target || syms[n] === "W")) n++;
        if (n >= 3) {
          const m = PAYS[target][n - 3];
          if (!best || m > best.mult) best = { sym: target, count: n, mult: m };
        }
      }
      if (best) wins.push({ line: l + 1, sym: best.sym, count: best.count, mult: best.mult, cells: cells.slice(0, best.count) });
    }
    return wins;
  }

  function countScatters(grid) {
    const out = { BS: [], FS: [] };
    grid.forEach((s, c) => { if (out[s]) out[s].push(c); });
    return out;
  }

  /* The exact return of the line pays with no features: every cell of a reel has the same
     symbol distribution, so one line's expectation, times 25, is the whole thing. */
  function exactLineRtp(strips) {
    const freq = strips.map((strip) => {
      const f = {};
      for (const s of strip) f[s] = (f[s] || 0) + 1 / strip.length;
      return Object.entries(f);
    });
    let ev = 0;
    const syms = new Array(REELS);
    const walk = (reel, p) => {
      if (reel === REELS) {
        const grid = new Array(REELS * ROWS).fill("L1");
        for (let r = 0; r < REELS; r++) grid[r * ROWS + 1] = syms[r];   // line 1 is row 1 throughout
        const w = evaluate(grid).find((x) => x.line === 1);
        if (w) ev += p * w.mult;
        return;
      }
      for (const [s, q] of freq[reel]) { syms[reel] = s; walk(reel + 1, p * q); }
    };
    walk(0, 1);
    return ev;   // in line-bet multiples per line == return per unit staked (25 lines, 25 line bets)
  }

  // ------------------------------------------------------------------ the spin pipeline
  /* One spin's whole outcome, in the order the screen shows it. `opts.free` uses the free-game
     strips and feature rates; `opts.rig` forces things for testing:
     {features: [names], trigger: "trail"|"free", jackpot: tier, stops: [5]} */
  function spinOutcome(V, bet, rng, opts = {}) {
    const free = !!opts.free, rig = opts.rig || {};
    const strips = free ? V.freeStrips : V.strips;
    const lineBet = bet / 25;
    let stops, grid, sc;
    for (let tries = 0; ; tries++) {
      stops = rig.stops || strips.map((s) => int(rng, s.length));
      grid = gridFromStops(strips, stops);
      if (rig.trigger && !rig.stops) forceTrigger(grid, rig.trigger, rng);
      sc = countScatters(grid);
      if (!(sc.BS.length >= 3 && sc.FS.length >= 3) || tries > 50) break;   // never both bonuses at once
    }
    const landed = grid.slice();
    const trigger = sc.BS.length >= 3 ? "trail" : sc.FS.length >= 3 ? "free" : null;

    // Which features fire. Free games guarantee at least one, and often several.
    const rates = free ? V.freeRates : V.rates;
    let on = {};
    if (rig.features) for (const f of rig.features) on[f] = true;
    else for (const f of FEATURES) if (rng() < rates[f]) on[f] = true;
    if (trigger) { delete on.wildReels; delete on.colossal; }
    if (trigger === "free") delete on.repeat;
    if (on.repeat && on.instant) delete on[rng() < 0.5 ? "repeat" : "instant"];
    if (free && !Object.keys(on).some((f) => f !== "repeat")) {
      on[weighted(rng, FEATURES.filter((f) => f !== "repeat").map((f) => [f, rates[f]]))] = true;
    }

    const out = { bet, free, stops, landed, trigger, scatters: sc, colossal: null, wildReels: [], wilds: [],
                  multiplier: 1, upgrade: null, repeat: 0, instant: 0 };
    const protectedCell = (c) => grid[c] === "W" || SCATTERS.includes(grid[c]);

    // Pre-stop: Colossal Reels (a span with no scatters showing), Wild Reels, Random Wilds, Multiplier.
    if (on.colossal) {
      const k = weighted(rng, V.colossalSizes);
      const spans = [];
      for (let s = 0; s + k <= REELS; s++) {
        let clean = true;
        for (let r = s; r < s + k; r++) for (let row = 0; row < ROWS; row++) if (SCATTERS.includes(grid[r * ROWS + row])) clean = false;
        if (clean) spans.push(s);
      }
      if (spans.length) {
        const start = spans[int(rng, spans.length)];
        const big = V.bigStrip, stop = int(rng, big.length), offset = int(rng, k);
        for (let r = start; r < start + k; r++) for (let row = 0; row < ROWS; row++) {
          grid[r * ROWS + row] = big[(stop + Math.floor((row + offset) / k)) % big.length];
        }
        out.colossal = { start, k, stop, offset };
      }
    }
    out.afterColossal = grid.slice();
    if (on.wildReels) {
      const fused = out.colossal ? (r) => r >= out.colossal.start && r < out.colossal.start + out.colossal.k : () => false;
      const reels = [...Array(REELS).keys()].filter((r) => !fused(r));
      out.wildReels = sample(rng, reels, Math.min(reels.length, weighted(rng, V.wildReelCounts))).sort();
      for (const r of out.wildReels) for (let row = 0; row < ROWS; row++) {
        const c = r * ROWS + row;
        if (!SCATTERS.includes(grid[c])) grid[c] = "W";
      }
    }
    if (on.wilds) {
      const open = [...Array(REELS * ROWS).keys()].filter((c) => !protectedCell(c));
      out.wilds = sample(rng, open, Math.min(open.length, weighted(rng, V.wildCounts))).sort((a, b) => a - b);
      for (const c of out.wilds) grid[c] = "W";
    }
    if (on.multiplier) out.multiplier = weighted(rng, V.multipliers);
    out.preGrid = grid.slice();

    // Post-stop: Symbol Upgrade, then the lines, then Repeat Win or Instant Win.
    if (on.upgrade) {
      const present = [...new Set(grid.filter((s) => UPGRADES[s]))];
      if (present.length) {
        const from = present[int(rng, present.length)], to = UPGRADES[from];
        const cells = [];
        grid.forEach((s, c) => { if (s === from) { grid[c] = to; cells.push(c); } });
        out.upgrade = { from, to, cells };
      }
    }
    out.grid = grid;
    out.wins = evaluate(grid).map((w) => ({ ...w, pence: Math.floor(w.mult * lineBet * out.multiplier) }));
    out.lineWin = out.wins.reduce((a, w) => a + w.pence, 0);
    if (on.repeat && out.lineWin > 0) out.repeat = weighted(rng, V.repeats);
    if (on.instant) out.instant = weighted(rng, V.instants) * bet;
    out.total = out.lineWin * (out.repeat || 1) + out.instant;
    out.features = Object.keys(on).filter((f) =>
      (f === "colossal" ? out.colossal : f === "wildReels" ? out.wildReels.length : f === "wilds" ? out.wilds.length :
       f === "upgrade" ? out.upgrade : f === "repeat" ? out.repeat : true));
    return out;
  }

  function gridFromStops(strips, stops) {
    const grid = new Array(REELS * ROWS);
    for (let r = 0; r < REELS; r++) for (let row = 0; row < ROWS; row++) {
      grid[r * ROWS + row] = strips[r][(stops[r] + row) % strips[r].length];
    }
    return grid;
  }
  function forceTrigger(grid, kind, rng) {   // test rig: 3 scatters of the kind on reels 1, 3 and 5
    const sym = kind === "trail" ? "BS" : "FS";
    for (let c = 0; c < grid.length; c++) if (SCATTERS.includes(grid[c])) grid[c] = "L1";
    for (const r of [0, 2, 4]) grid[r * ROWS + int(rng, ROWS)] = sym;
  }

  // ------------------------------------------------------------------ the Trail Bonus
  /* A fresh board for each bonus: space 0 is the start, the last space is the prizepot.
     At most one Double and one Spin Upgrade; no Snake within reach of a Lightning Roll. */
  function makeBoard(V, rng) {
    const T = V.trail, L = T.length, inner = L - 2;
    const pool = [];
    const add = (type, n) => { for (let i = 0; i < n; i++) pool.push(type); };
    for (const [type, n] of Object.entries(T.counts)) add(type, n);
    if (rng() < T.upgradeChance) pool.push("upgrade");
    if (rng() < T.doubleChance) pool.push("double");
    add("coin", inner - pool.length);
    shuffle(rng, pool);
    // Swap Snakes out of the first two spaces and out of a Lightning Roll's reach (6 spaces, or
    // 12 if a Spin Upgrade comes earlier), so the board keeps its exact count of each item.
    const reachOf = (i) => {
      const up = pool.slice(0, i).includes("upgrade");
      return up ? 12 : 6;
    };
    const unsafe = (i) => {
      if (pool[i] !== "snake") return false;
      if (i < 2) return true;
      for (let j = Math.max(0, i - 12); j < i; j++) if (pool[j] === "lightning" && i - j <= reachOf(j)) return true;
      return false;
    };
    for (let pass = 0; pass < 500; pass++) {
      let left = false;
      for (let i = 0; i < inner; i++) {
        if (!unsafe(i)) continue;
        left = true;
        const j = 2 + int(rng, inner - 2);
        if (pool[j] === "coin") [pool[i], pool[j]] = [pool[j], pool[i]];
      }
      if (!left) break;
    }
    const spaces = [{ type: "start" }];
    for (const type of pool) spaces.push(type === "coin" ? { type, x: weighted(rng, T.coins) } : { type });
    spaces.push({ type: "prizepot", x: T.prizepot });
    return spaces;
  }

  function trailStart(V, bet, rng, board) {
    return { bet, board: board || makeBoard(V, rng), pos: 0, hearts: 0, doubled: false, upgraded: false,
             lightning: false, total: 0, done: false, rolls: 0 };
  }

  /* One pull of the trigger. Returns {bullets, move, path, events, done}; `state` advances.
     Events: coin {pos, pence}, heart, heart_used, snake, double, upgrade, lightning, crate {r, pence},
     forward/back {n}, prizepot {pence}. */
  function trailRoll(V, state, rng, rigBullets) {
    const T = V.trail, b = state.board, end = b.length - 1;
    const bullets = rigBullets || 1 + int(rng, 6);
    const move = bullets * (state.upgraded ? 2 : 1);
    const ev = [], path = [];
    state.rolls++;
    const pay = (pos, pence, kind) => { state.total += pence; ev.push({ kind, pos, pence }); };
    const collectCoin = (pos) => {
      const sp = b[pos];
      if (sp.type === "coin" && !sp.taken) { sp.taken = true; pay(pos, sp.x * state.bet, "coin"); }
    };
    const finish = () => {
      const x = b[end].x;
      pay(end, x * state.bet, "prizepot");
      state.done = true;
    };
    const land = (pos, depth) => {
      state.pos = pos;
      const sp = b[pos];
      if (pos >= end) return finish();
      switch (sp.type) {
        case "coin": collectCoin(pos); break;
        case "heart": if (!sp.taken) { sp.taken = true; state.hearts++; ev.push({ kind: "heart", pos }); } break;
        case "snake":
          if (state.hearts > 0) { state.hearts--; ev.push({ kind: "heart_used", pos }); }
          else { ev.push({ kind: "snake", pos }); state.done = true; }
          break;
        case "double":
          if (!state.doubled) {
            state.doubled = true;
            for (const s of b) if ((s.type === "coin" && !s.taken) || s.type === "prizepot") s.x *= 2;
            ev.push({ kind: "double", pos });
          }
          break;
        case "upgrade": if (!state.upgraded) { state.upgraded = true; ev.push({ kind: "upgrade", pos }); } break;
        case "lightning": state.lightning = true; ev.push({ kind: "lightning", pos }); break;
        case "crate": {
          const r = weighted(rng, T.crateRadius);
          let pence = 0;
          for (let j = Math.max(1, pos - r); j <= Math.min(end - 1, pos + r); j++) {
            const s = b[j];
            if (s.type === "coin" && !s.taken) { s.taken = true; pence += s.x * state.bet; }
          }
          state.total += pence;
          ev.push({ kind: "crate", pos, r, pence });
          break;
        }
        case "forward": case "back": {
          if (depth > 3) break;
          const n = 1 + int(rng, 6);
          ev.push({ kind: sp.type, pos, n });
          const to = sp.type === "forward" ? Math.min(end, pos + n) : Math.max(0, pos - n);
          path.push(to);
          land(to, depth + 1);
          break;
        }
      }
    };
    const from = state.pos;
    if (state.lightning) {
      // The roll after a Lightning space collects every award it passes, landing included.
      // Signposts are passed over, and there's never a Snake in reach.
      state.lightning = false;
      ev.push({ kind: "lightning_roll", pos: from });
      const to = Math.min(end, from + move);
      for (let p = from + 1; p <= to; p++) {
        path.push(p);
        if (p >= end) { state.pos = end; finish(); break; }
        const t = b[p].type;
        if (t === "lightning" && p !== to) continue;     // only re-arms if you stop on it
        if (t !== "forward" && t !== "back" && t !== "snake") land(p, 9);
        state.pos = p;
      }
    } else {
      for (let p = from + 1; p <= Math.min(end, from + move); p++) path.push(p);
      land(Math.min(end, from + move), 0);
    }
    return { bullets, move, from, path, events: ev, done: state.done };
  }

  function trailPlayOut(V, state, rng) {   // a player who leaves mid-bonus: auto-fire to the end
    const rolls = [];
    for (let i = 0; i < 500 && !state.done; i++) rolls.push(trailRoll(V, state, rng));
    return rolls;
  }

  // ------------------------------------------------------------------ Combo Free Spins
  function freeGames(V, bet, rng, n = 3) {
    const games = [];
    for (let i = 0; i < n; i++) games.push(spinOutcome(V, bet, rng, { free: true }));
    return games;
  }

  // ------------------------------------------------------------------ the shared progressives
  const JACKPOT_TIERS = [
    // seed in pence, share of every bet, and how often it's won (1 in N pence wagered)
    { id: "mini", name: "MINI", seed: 1_000, rate: 0.0025, every: 150_000 },
    { id: "minor", name: "MINOR", seed: 5_000, rate: 0.0025, every: 1_000_000 },
    { id: "major", name: "MAJOR", seed: 50_000, rate: 0.005, every: 15_000_000 },
    { id: "grand", name: "GRAND", seed: 500_000, rate: 0.01, every: 200_000_000 },
  ];
  const JACKPOT_PER_PENCE = JACKPOT_TIERS.reduce((a, t) => a + 1 / t.every, 0);
  function jackpotTrigger(bet, rng) {
    if (rng() >= bet * JACKPOT_PER_PENCE) return null;
    return weighted(rng, JACKPOT_TIERS.map((t) => [t.id, 1 / t.every]));
  }
  /* The 12-coin board's reveal order, fixed in advance: the drawn tier is the first to reach
     three (on the last reveal), and no other tier gets more than two. */
  function pickSequence(tier, rng) {
    const seq = [tier, tier];
    for (const t of JACKPOT_TIERS) if (t.id !== tier) for (let i = 0, n = weighted(rng, [[1, 1], [2, 3]]); i < n; i++) seq.push(t.id);
    shuffle(rng, seq);
    seq.push(tier);
    const rest = [];   // what the unpicked coins show at the end
    const left = 12 - seq.length;
    const pool = JACKPOT_TIERS.flatMap((t) => [t.id, t.id, t.id]).filter((id) => id !== tier);
    shuffle(rng, pool);
    for (let i = 0; i < left; i++) rest.push(pool[i]);
    return { seq, rest };
  }

  // ------------------------------------------------------------------ simulation
  /* `spins` paid spins at `bet`, everything included. Returns pence by source, plus counts. */
  function simulate(V, spins, bet, seed) {
    const rng = mulberry32(seed);
    const r = { spins, bet, staked: spins * bet, plain: 0, featured: 0, repeatExtra: 0, instant: 0, trail: 0, free: 0,
                hits: 0, trails: 0, frees: 0, featureSpins: 0, featureCounts: {}, max: 0, sumSq: 0, prizepots: 0 };
    for (let i = 0; i < spins; i++) {
      const o = spinOutcome(V, bet, rng);
      let won = o.total;
      if (o.features.length) {
        r.featureSpins++;
        for (const f of o.features) r.featureCounts[f] = (r.featureCounts[f] || 0) + 1;
        r.featured += o.lineWin;
        r.repeatExtra += o.lineWin * Math.max(0, o.repeat - 1);
        r.instant += o.instant;
      } else r.plain += o.lineWin;
      if (o.trigger === "trail") {
        const s = trailStart(V, bet, rng);
        trailPlayOut(V, s, rng);
        r.trails++; r.trail += s.total; won += s.total;
        if (s.pos >= s.board.length - 1) r.prizepots++;
      } else if (o.trigger === "free") {
        const fs = freeGames(V, bet, rng, V.freeGames).reduce((a, g) => a + g.total, 0);
        r.frees++; r.free += fs; won += fs;
      }
      if (won > 0) r.hits++;
      r.max = Math.max(r.max, won);
      const x = won / bet;
      r.sumSq += x * x;
    }
    const pct = (v) => (100 * v) / r.staked;
    r.rtp = { plain: pct(r.plain), featured: pct(r.featured), repeat: pct(r.repeatExtra), instant: pct(r.instant),
              trail: pct(r.trail), free: pct(r.free), jackpot: 100 * jackpotRtp() };
    r.rtp.game = r.rtp.plain + r.rtp.featured + r.rtp.repeat + r.rtp.instant + r.rtp.trail + r.rtp.free;
    r.rtp.total = r.rtp.game + r.rtp.jackpot;
    const mean = r.rtp.game / 100;
    r.sd = Math.sqrt(r.sumSq / spins - mean * mean);
    return r;
  }
  function simulateBuy(V, n, bet, seed) {
    const rng = mulberry32(seed);
    let won = 0, max = 0, prizepots = 0, rolls = 0;
    for (let i = 0; i < n; i++) {
      const s = trailStart(V, bet, rng);
      trailPlayOut(V, s, rng);
      won += s.total; max = Math.max(max, s.total); rolls += s.rolls;
      if (s.pos >= s.board.length - 1) prizepots++;
    }
    return { n, rtp: (100 * won) / (n * bet * V.buyCost), mean: won / n / bet, max: max / bet, prizepots, rolls: rolls / n };
  }
  /* What the progressives return: every bet's share, plus each seed paid out once per win. */
  function jackpotRtp() { return JACKPOT_TIERS.reduce((a, t) => a + t.rate + t.seed / t.every, 0); }

  // ------------------------------------------------------------------ pacing
  /* How long the screen takes to show a spin, so NPCs and the server pace themselves to it. */
  function presentationSeconds(o, turbo) {
    let t = 1.3 + 0.18 * (REELS - 1);
    if (o.colossal) t += 0.9;
    if (o.wildReels.length) t += 0.7 * o.wildReels.length;
    if (o.wilds.length) t += 0.35 * o.wilds.length + 0.3;
    if (o.multiplier > 1) t += 0.7;
    if (o.upgrade) t += 1.1;
    if (o.wins.length) t += 1.2;
    if (o.repeat) t += 0.9 * o.repeat;
    if (o.instant) t += 1.6;
    const x = o.total / o.bet;
    if (x >= 10) t += x >= 50 ? 5 : x >= 25 ? 4 : 3;
    return turbo ? t * 0.55 : t;
  }

  // ------------------------------------------------------------------ the variant
  const BASE_COUNTS = [0, 1, 2, 3, 4].map((reel) => ({
    W: reel ? 4 : 0, H1: 3, H2: 3, M1: 5, M2: 5, M3: 5, M4: 5, L1: 6, L2: 6, L3: 6, L4: 6, BS: reel === 2 ? 2 : 1, FS: 1,
  }));
  function makeVariant(p) {
    const V = Object.assign({}, p);
    V.strips = p.counts.map((c, i) => buildStrip(c, 1000 + i));
    V.freeStrips = p.counts.map((c, i) => buildStrip(Object.fromEntries(Object.entries(c).filter(([s]) => !SCATTERS.includes(s))), 2000 + i));
    V.bigStrip = buildStrip(p.bigCounts, 3000);
    return V;
  }
  const ARMADILLO = makeVariant({
    id: "armadillo",
    name: "Armadillo Goes West",
    symbols: { W: "Wild", H1: "Armadillo", H2: "Snake", M1: "Hat", M2: "Horseshoe", M3: "Whiskey", M4: "Boots",
               L1: "Spade", L2: "Club", L3: "Diamond", L4: "Heart", BS: "Bonus", FS: "Free Spins" },
    counts: BASE_COUNTS,
    bigCounts: { W: 1, H1: 2, H2: 2, M1: 3, M2: 3, M3: 3, M4: 3, L1: 4, L2: 4, L3: 4, L4: 4 },
    rates: { wilds: 0.07, wildReels: 0.014, colossal: 0.02, multiplier: 0.035, upgrade: 0.06, repeat: 0.04, instant: 0.008 },
    freeRates: { wilds: 0.6, wildReels: 0.32, colossal: 0.3, multiplier: 0.5, upgrade: 0.45, repeat: 0.35, instant: 0.25 },
    wildCounts: [[1, 40], [2, 30], [3, 20], [4, 10]],
    wildReelCounts: [[1, 70], [2, 25], [3, 5]],
    colossalSizes: [[2, 60], [3, 30], [4, 10]],
    multipliers: [[2, 50], [3, 25], [4, 15], [5, 10]],
    repeats: [[2, 60], [3, 25], [4, 10], [5, 5]],
    instants: [[1, 30], [2, 25], [3, 15], [5, 12], [10, 9], [20, 5], [50, 2.5], [100, 1], [200, 0.5]],
    trail: {
      length: 120,
      prizepot: 2000,
      // Every board has exactly these, shuffled; the rest of its spaces are coins.
      counts: { snake: 20, heart: 2, forward: 3, back: 3, lightning: 2, crate: 3 },
      upgradeChance: 0.2,
      doubleChance: 0.4,
      coins: [[1, 30], [2, 26], [3, 17], [5, 12], [10, 8], [20, 4.5], [50, 2.2], [100, 0.9], [200, 0.4]],
      crateRadius: [[1, 50], [2, 35], [3, 15]],
    },
    buyCost: 45,
    freeGames: 3,
  });

  const api = { REELS, ROWS, LINES, PAYS, PAYING, SCATTERS, UPGRADES, LADDER, FEATURES, JACKPOT_TIERS, JACKPOT_PER_PENCE,
    mulberry32, weighted, buildStrip, evaluate, countScatters, exactLineRtp, spinOutcome, gridFromStops,
    makeBoard, trailStart, trailRoll, trailPlayOut, freeGames, jackpotTrigger, pickSequence, presentationSeconds,
    simulate, simulateBuy, jackpotRtp,
    makeVariant, ARMADILLO };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SlotMath = api;
})(typeof self !== "undefined" ? self : this);
