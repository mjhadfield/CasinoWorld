const M = require("../mockup/slots_math.js");
const base = M.ARMADILLO;
const f = (x) => x.toFixed(2);
function trial(len, snake, heart, upg, dbl, coinScale) {
  const w = { coin: 52, snake, heart, forward: 5, back: 5, lightning: 2, crate: 6, upgrade: upg, double: dbl };
  const V = Object.assign({}, base, { trail: Object.assign({}, base.trail, { length: len, items: Object.entries(w),
    coins: base.trail.coins.map(([x, wt]) => [x, x >= 20 ? wt * coinScale : wt]) }) });
  const b = M.simulateBuy(V, 60000, 100, 3);
  console.log(`len ${len} snake ${snake} heart ${heart} upg ${upg} dbl ${dbl} big×${coinScale}: mean ${f(b.mean)}x rtp ${f(b.rtp)}% end ${f(100*b.prizepots/b.n)}% rolls ${f(b.rolls)}`);
}
for (const a of [[50,40,4,1,1.5,1],[60,40,4,1,1.5,1],[60,45,4,1,1.5,1],[70,42,4,1,1.5,1],[60,50,5,1,1.5,1],[50,50,5,1,1.5,1]]) trial(...a);
