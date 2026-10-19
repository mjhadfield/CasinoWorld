const M = require("../mockup/slots_math.js");
const base = M.ARMADILLO, f = (x) => x.toFixed(2);
for (const [len, snake, heart] of JSON.parse(process.argv[2])) {
  const V = Object.assign({}, base, { trail: Object.assign({}, base.trail, { length: len, counts: Object.assign({}, base.trail.counts, { snake, heart }) }) });
  const b = M.simulateBuy(V, 60000, 100, 3);
  console.log(`len ${len} snakes ${snake} hearts ${heart}: mean ${f(b.mean)}x rtp ${f(b.rtp)}% end ${f(100*b.prizepots/b.n)}% rolls ${f(b.rolls)}`);
}
