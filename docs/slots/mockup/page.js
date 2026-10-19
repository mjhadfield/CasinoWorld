/* The page around the game: art and speed buttons, the rigs, the art sheet, the pay table, the
   lines chart and the tuner. */
(function () {
  "use strict";
  const M = SlotMath, V = M.ARMADILLO, G = window.SlotGame;
  const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
  const money = (p) => "\u00a3" + (p / 100).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const press = (group, on) => group.forEach((b) => b.setAttribute("aria-pressed", String(b === on)));

  // art, speed, top-up
  const artBtns = [$("#art-svg"), $("#art-flux")];
  artBtns.forEach((b) => b.addEventListener("click", () => { press(artBtns, b); G.setArt(b.id === "art-flux" ? "flux" : "svg"); }));
  const speedBtns = [$("#speed1"), $("#speed3")];
  speedBtns.forEach((b) => b.addEventListener("click", () => { press(speedBtns, b); G.setSpeed(b.id === "speed3" ? 3 : 1); }));
  $("#topup").addEventListener("click", () => G.topUp());

  // rigs for the next spin
  const rig = { features: [], trigger: null, jackpot: null };
  const sync = () => {
    $$("[data-rig]").forEach((b) => b.setAttribute("aria-pressed", String(rig.features.includes(b.dataset.rig))));
    $$("[data-trig]").forEach((b) => b.setAttribute("aria-pressed", String(rig.trigger === b.dataset.trig)));
    $$("[data-jp]").forEach((b) => b.setAttribute("aria-pressed", String(rig.jackpot === b.dataset.jp)));
    const bits = [...rig.features, rig.trigger && (rig.trigger === "trail" ? "Trail Bonus" : "Free Games"), rig.jackpot && rig.jackpot + " jackpot"].filter(Boolean);
    $("#rig-hint").textContent = bits.length ? `Next spin: ${bits.join(", ")}.` : "Pick anything above, then click the screen: it happens on that spin. Space also spins, and stops the reels early.";
    G.rig({ features: rig.features.slice(), trigger: rig.trigger, jackpot: rig.jackpot });
  };
  $$("[data-rig]").forEach((b) => b.addEventListener("click", () => {
    const f = b.dataset.rig, i = rig.features.indexOf(f);
    if (i >= 0) rig.features.splice(i, 1); else rig.features.push(f);
    sync();
  }));
  $$("[data-trig]").forEach((b) => b.addEventListener("click", () => { rig.trigger = rig.trigger === b.dataset.trig ? null : b.dataset.trig; sync(); }));
  $$("[data-jp]").forEach((b) => b.addEventListener("click", () => { rig.jackpot = rig.jackpot === b.dataset.jp ? null : b.dataset.jp; sync(); }));
  window.addEventListener("rig-used", () => { rig.features = []; rig.trigger = null; rig.jackpot = null; sync(); });

  // the art sheet
  const ASSETS = [["W", "Wild (sheriff's star)"], ["H1", "Armadillo"], ["H2", "Snake"], ["M1", "Hat"], ["M2", "Horseshoe"], ["M3", "Whiskey"],
    ["M4", "Boots"], ["L1", "Spade"], ["L2", "Club"], ["L3", "Diamond"], ["L4", "Heart"], ["BS", "Bonus wagon"], ["FS", "Free-spin pistols"],
    ["barrel", "Instant Win barrel"], ["armadillo", "Trail armadillo"], ["cylinder", "Pistol cylinder"], ["t_coin", "Trail: coins"],
    ["t_double", "Trail: double"], ["t_forward", "Trail: forward / back"], ["t_heart", "Trail: heart"], ["t_lightning", "Trail: lightning roll"],
    ["t_crate", "Trail: award all coins"], ["t_upgrade", "Trail: spin upgrade"], ["t_gold", "Trail: prizepot"], ["t_snake", "Trail: snake"]];
  $("#sheet").innerHTML = ASSETS.map(([id, name]) => `
    <div class="asset"><h3>${name}<span>${id}</span></h3><div class="trio">
      <figure><img src="art/svg/${id}.svg" alt="${name}, vector" loading="lazy"><figcaption>Vector</figcaption></figure>
      <figure><img src="art/flux/${id}_1.png" alt="${name}, FLUX candidate 1" loading="lazy"><figcaption>FLUX 1</figcaption></figure>
      <figure><img src="art/flux/${id}_2.png" alt="${name}, FLUX candidate 2" loading="lazy"><figcaption>FLUX 2</figcaption></figure>
    </div></div>`).join("") + `
    <div class="asset"><h3>Background and logo<span>FLUX only</span></h3><div class="trio" style="grid-template-columns:1fr">
      <figure><img src="art/flux/bg_1.jpg" alt="Painted desert canyon background" style="aspect-ratio:16/9" loading="lazy"><figcaption>Background</figcaption></figure>
      <figure><img src="art/flux/logo_1.png" alt="Painted logo" loading="lazy"><figcaption>FLUX logo: it can&#8217;t spell ARMADILLO, so both sets use lettering</figcaption></figure>
    </div></div>`;

  // the pay table, at the current bet
  let shownBet = 0;
  function paytable() {
    const b = G.bet();
    if (b === shownBet) return;
    shownBet = b;
    const lb = b / 25;
    const rows = ["W", "H1", "H2", "M1", "M2", "M3", "M4", "L1", "L2", "L3", "L4"].map((s) =>
      `<tr><td><img src="art/svg/${s}.svg" alt=""> ${V.symbols[s]}</td>${[5, 4, 3].map((k) => `<td class="num">${money(Math.floor(M.PAYS[s][k - 3] * lb))}</td>`).join("")}<td class="num">${M.PAYS[s][2]}\u00d7</td></tr>`);
    $("#paytable").innerHTML = `<thead><tr><th>Symbol (bet ${money(b)})</th><th class="num">5</th><th class="num">4</th><th class="num">3</th><th class="num">5 in line bets</th></tr></thead><tbody>${rows.join("")}</tbody>`;
  }
  paytable(); setInterval(paytable, 400);

  // the lines chart
  $("#lines").innerHTML = M.LINES.map((l, i) => {
    let cells = "";
    for (let row = 0; row < 4; row++) for (let reel = 0; reel < 5; reel++) cells += `<i class="${l[reel] === row ? "on" : ""}"></i>`;
    return `<div class="line"><span>Line ${i + 1}</span><div class="g">${cells}</div></div>`;
  }).join("");

  // the tuner
  const f2 = (x) => x.toFixed(2);
  $("#tune").addEventListener("click", () => {
    const btn = $("#tune"); btn.disabled = true; btn.textContent = "Running\u2026";
    const w = new Worker("sim_worker.js");
    w.onmessage = (e) => {
      $("#tune-bar").style.width = (100 * e.data.progress).toFixed(0) + "%";
      if (!e.data.result) return;
      const r = e.data.result, n = r.spins, b = r.buy;
      const rows = [["Line wins, no feature", r.rtp.plain], ["Line wins with a feature", r.rtp.featured], ["Repeat Win (the extra pays)", r.rtp.repeat],
        ["Instant Win", r.rtp.instant], ["Trail Bonus (from " + b.n.toLocaleString("en-GB") + " trails)", r.rtp.trail], ["Combo Free Games", r.rtp.free], ["Game total", r.rtp.game],
        ["Progressives (exact)", r.rtp.jackpot], ["Everything", r.rtp.total]];
      const feats = Object.entries(r.featureCounts).sort((a, b2) => b2[1] - a[1]).map(([k, v]) => `<tr><td>${k}</td><td class="num">1 in ${f2(n / v)}</td></tr>`).join("");
      const jp = M.LADDER.map((stake) => `<tr><td>${money(stake)}</td><td class="num">1 in ${Math.round(1 / (stake * M.JACKPOT_PER_PENCE)).toLocaleString("en-GB")}</td></tr>`).join("");
      $("#tune-out").innerHTML = `
        <div class="kpis">
          <div class="kpi"><b>${f2(r.rtp.total)}%</b><span>Return, everything</span></div>
          <div class="kpi"><b>${f2(r.rtp.game)}%</b><span>Return, the game</span></div>
          <div class="kpi"><b>${f2(b.rtp)}%</b><span>Return, Buy Bonus</span></div>
          <div class="kpi"><b>1 in ${f2(n / r.hits)}</b><span>Spins that win</span></div>
          <div class="kpi"><b>1 in ${Math.round(n / r.trails)}</b><span>Trail Bonus</span></div>
          <div class="kpi"><b>1 in ${Math.round(n / r.frees)}</b><span>Free Games</span></div>
          <div class="kpi"><b>${f2(r.sd)}</b><span>Volatility (SD, \u00d7 bet)</span></div>
        </div>
        <div class="two">
          <div class="tablewrap"><table><thead><tr><th>Where the return comes from</th><th class="num">% of stakes</th></tr></thead><tbody>
            ${rows.map(([k, v]) => `<tr><td>${k}</td><td class="num">${f2(v)}%</td></tr>`).join("")}
            <tr><td>Line pays alone, exact (no features)</td><td class="num">${f2(r.exact)}%</td></tr></tbody></table>
            <p class="hint">Runs differ by about half a percent: the 2,000× prizepot is rare. The build is checked against ten million spins.</p></div>
          <div class="tablewrap"><table><thead><tr><th>Feature</th><th class="num">How often</th></tr></thead><tbody>${feats}
            <tr><td>Any feature</td><td class="num">1 in ${f2(n / r.featureSpins)}</td></tr>
            <tr><td>Trail mean win</td><td class="num">${f2(b.mean)}\u00d7 bet</td></tr>
            <tr><td>Trail shots, on average</td><td class="num">${f2(b.rolls)}</td></tr>
            <tr><td>Trail reaches the prizepot</td><td class="num">1 in ${Math.round(b.n / b.prizepots)}</td></tr>
            <tr><td>Biggest single spin (incl. bonus)</td><td class="num">${f2(r.max / 100)}\u00d7 bet</td></tr></tbody></table></div>
          <div class="tablewrap"><table><thead><tr><th>Stake</th><th class="num">Jackpot Pick starts</th></tr></thead><tbody>${jp}</tbody></table></div>
        </div>`;
      btn.disabled = false; btn.textContent = "Run again"; w.terminate();
    };
    w.postMessage({ spins: 1000000, buys: 200000 });
  });
})();
