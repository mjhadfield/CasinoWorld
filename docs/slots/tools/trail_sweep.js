const M = require("../mockup/slots_math.js");
const base = M.ARMADILLO;
const f = (x) => x.toFixed(2);
for (const [len, snake, heart, coinScale] of [[40,13,6,1],[40,22,4,1],[40,28,4,1],[50,25,4,1],[50,30,4,1],[60,28,4,1],[60,30,5,1]]) {
  const V = Object.assign({}, base, { trail: Object.assign({}, base.trail, { length: len,
    items: base.trail.items.map(([k, w]) => [k, k === "snake" ? snake : k === "heart" ? heart : w]),
    coins: base.trail.coins.map(([x, w]) => [x, x >= 20 ? w * coinScale : w]) }) });
  const b = M.simulateBuy(V, 60000, 100, 3);
  console.log(`len ${len} snake ${snake} heart ${heart} big-coin×${coinScale}: mean ${f(b.mean)}x rtp ${f(b.rtp)}% prizepot ${f(100*b.prizepots/b.n)}% rolls ${f(b.rolls)} max ${b.max}x`);
}
