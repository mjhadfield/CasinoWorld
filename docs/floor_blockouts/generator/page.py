"""Check the three plans, write their blueprints and write the review page (../resort-floor-blockouts.html)."""
import html
import json
from pathlib import Path

from render import KIND_LABEL, NAMES, build

HERE = Path(__file__).parent
plans = build(["plan_a", "plan_b", "plan_c"])
LETTERS = "ABC"

CSS = r"""
:root{
  /* Layout: an architect's drawing set. Sheet header, then one sheet per variation (plan + room schedule). */
  --paper:#f2f3ee; --sheet:#fbfbf8; --ink:#1c2420; --muted:#5b6862; --rule:#cfd5ce; --accent:#0e6a52; --gold:#a8822a;
  --wall:#36403b; --signink:#f3ecd8; --band:#5a645f; --gridline:#e2e6df;
  --z-floor:#d3e3d7; --z-high:#cfd6ec; --z-food:#f0dfc6; --z-feature:#e4d8ec; --z-entry:#e7e5dd; --z-service:#dedfd8; --z-circ:#ece4cc;
  --aisle:#eadfbc; --pitcarpet:#bcd2c3; --hlcarpet:#b5c0e0; --garden:#c6dcc0; --boards:#e3cfae;
  --felt-card:#2e7b59; --felt-wheel:#8c2f2f; --felt-dice:#2c5d8a; --felt-master:#6a4f9e; --felt-bac:#9b762b;
  --cab:#c8901f; --furn:#948d7b; --bar:#6c4b2f; --npc:#cf4a2f; --seat:#1c2420; --flat:#7b7468;
  --display:"Josefin Sans", "Futura", "Century Gothic", system-ui, sans-serif;
  --body:"Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono:"JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --paper:#101614; --sheet:#151c19; --ink:#e3e9e5; --muted:#9aa8a1; --rule:#2c3632; --accent:#4fc39d; --gold:#d9b25a;
  --wall:#7d8a84; --signink:#0f1513; --band:#56625c; --gridline:#1d2522;
  --z-floor:#1f3a2d; --z-high:#232d4d; --z-food:#43341f; --z-feature:#382c45; --z-entry:#2b2e2b; --z-service:#262a28; --z-circ:#3a3422;
  --aisle:#4a4128; --pitcarpet:#2a4a3a; --hlcarpet:#2f3c66; --garden:#2b4a2c; --boards:#4d3d26;
  --felt-card:#3fa274; --felt-wheel:#c04b4b; --felt-dice:#4a86c0; --felt-master:#9478d0; --felt-bac:#c99d45;
  --cab:#e0aa3a; --furn:#7d7767; --bar:#a07250; --npc:#ff7a5c; --seat:#e3e9e5; --flat:#a39b8c; color-scheme:dark }}
:root[data-theme="dark"]{
  --paper:#101614; --sheet:#151c19; --ink:#e3e9e5; --muted:#9aa8a1; --rule:#2c3632; --accent:#4fc39d; --gold:#d9b25a;
  --wall:#7d8a84; --signink:#0f1513; --band:#56625c; --gridline:#1d2522;
  --z-floor:#1f3a2d; --z-high:#232d4d; --z-food:#43341f; --z-feature:#382c45; --z-entry:#2b2e2b; --z-service:#262a28; --z-circ:#3a3422;
  --aisle:#4a4128; --pitcarpet:#2a4a3a; --hlcarpet:#2f3c66; --garden:#2b4a2c; --boards:#4d3d26;
  --felt-card:#3fa274; --felt-wheel:#c04b4b; --felt-dice:#4a86c0; --felt-master:#9478d0; --felt-bac:#c99d45;
  --cab:#e0aa3a; --furn:#7d7767; --bar:#a07250; --npc:#ff7a5c; --seat:#e3e9e5; --flat:#a39b8c; color-scheme:dark }
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:15px/1.55 var(--body);
  padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px));padding-block:28px 64px}
.wrap{max-width:1240px;margin:0 auto;display:flex;flex-direction:column;gap:28px}
h1,h2,h3{font-family:var(--display);font-weight:600;text-wrap:balance;margin:0;letter-spacing:.01em}
h1{font-size:clamp(30px,4.4vw,46px);line-height:1.05}
h2{font-size:clamp(24px,3vw,32px);line-height:1.1}
h3{font-size:18px}
p{margin:0;max-width:68ch}
.eyebrow{font:600 12px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.muted{color:var(--muted)}
header.top{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px 32px;align-items:end;border-bottom:2px solid var(--ink);padding-bottom:18px}
header.top .intro{display:flex;flex-direction:column;gap:10px;min-width:0}
.titleblock{font:12px/1.5 var(--mono);border:1.5px solid var(--ink);display:grid;grid-template-columns:auto auto;min-width:0}
.titleblock div{padding:5px 10px;border-bottom:1px solid var(--rule)}
.titleblock div:nth-child(odd){color:var(--muted);border-right:1px solid var(--rule)}
.titleblock div:nth-last-child(-n+2){border-bottom:0}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:13px;color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:7px}
.sw{width:16px;height:12px;border-radius:2px;border:1px solid var(--wall);display:inline-block}
.sw.dot{width:10px;height:10px;border-radius:50%;border:0}
.compare{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.card{background:var(--sheet);border:1px solid var(--rule);padding:16px 18px;display:flex;flex-direction:column;gap:10px;text-decoration:none;color:inherit;min-width:0}
.card:hover,.card:focus-visible{border-color:var(--accent);outline:none}
.card .letter{font:600 13px/1 var(--mono);color:var(--gold);letter-spacing:.1em}
.card h3{font-size:22px}
.card p{font-size:14px;color:var(--muted)}
.nums{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;border-top:1px solid var(--rule);padding-top:10px;margin-top:auto}
.nums div{display:flex;flex-direction:column;font-variant-numeric:tabular-nums}
.nums b{font:600 20px/1.1 var(--mono)}
.nums small{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.chk{font:12px/1.3 var(--mono);color:var(--accent)}
.chk.bad{color:var(--npc)}
section.sheet{background:var(--sheet);border:1px solid var(--rule);display:flex;flex-direction:column;gap:18px;padding:22px 22px 26px;scroll-margin-top:16px}
.sheethead{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 18px;align-items:start}
.sheethead .big{font:600 64px/0.85 var(--display);color:var(--gold);grid-row:span 3}
.sheethead .insp{font-size:13px;color:var(--muted);font-style:italic}
.sheethead p{margin-top:6px}
.walks{display:flex;flex-wrap:wrap;gap:6px 10px;font:12px/1.4 var(--mono);color:var(--muted)}
.walks span{border:1px solid var(--rule);padding:3px 8px;border-radius:999px}
.walks b{color:var(--ink);font-weight:600}
figure{margin:0;overflow-x:auto;border:1px solid var(--rule);background:var(--paper)}
figure svg{display:block;width:100%;min-width:760px;height:auto}
.plan .grid line{stroke:var(--gridline);stroke-width:3}
.plan .wall{fill:var(--wall)}
.plan .band{fill:var(--band);opacity:.55}
.plan .k-floor .fl{fill:var(--z-floor)} .plan .k-high .fl{fill:var(--z-high)} .plan .k-food .fl{fill:var(--z-food)}
.plan .k-feature .fl{fill:var(--z-feature)} .plan .k-entry .fl{fill:var(--z-entry)} .plan .k-service .fl{fill:var(--z-service)}
.plan .k-circ .fl{fill:var(--z-circ)}
.plan .hatchline{stroke:var(--muted);stroke-width:3;opacity:.45}
.plan .patch.aisle{fill:var(--aisle)} .plan .patch.pitcarpet{fill:var(--pitcarpet)} .plan .patch.hlcarpet{fill:var(--hlcarpet)}
.plan .patch.garden{fill:var(--garden)} .plan .patch.boards{fill:var(--boards)}
.plan .leaf{stroke:var(--wall);stroke-width:4;stroke-dasharray:10 8}
.plan .flat{fill:none;stroke:var(--flat);stroke-width:4;stroke-dasharray:14 10}
.plan .wallitem{fill:var(--bar);opacity:.8}
.plan .felt{stroke:var(--wall);stroke-width:3}
.plan .f-card{fill:var(--felt-card)} .plan .f-wheel{fill:var(--felt-wheel)} .plan .f-dice{fill:var(--felt-dice)}
.plan .f-master{fill:var(--felt-master)} .plan .f-bac{fill:var(--felt-bac)}
.plan .sign{fill:var(--wall)}
.plan .seat{fill:var(--seat)}
.plan .tl{font:700 40px var(--mono);fill:#fff;text-anchor:middle;pointer-events:none}
.plan .cab{fill:var(--cab);stroke:var(--wall);stroke-width:2}
.plan .furn{fill:var(--furn)} .plan .furn.bar{fill:var(--bar)}
.plan .npc{fill:var(--npc)}
.plan .rl{font-family:var(--display);font-weight:600;fill:var(--signink);pointer-events:none;letter-spacing:.03em}
.plan .rl.in{fill:var(--ink)}
.plan .st.st2{text-anchor:start}
.plan .rd{font-family:var(--mono);font-weight:400;opacity:.75;letter-spacing:0}
.plan .existing .wall{fill:var(--muted)}
.plan .spawn circle{fill:none;stroke:var(--npc);stroke-width:6}
.plan .spawn .dot{fill:var(--npc);stroke:none}
.plan .sb0{fill:var(--ink)} .plan .sb1{fill:none;stroke:var(--ink);stroke-width:3}
.plan .st{font:34px var(--mono);fill:var(--muted);text-anchor:middle}
.plan .room{cursor:pointer;outline:none}
.plan .room.hot .fl:not(.gap){filter:brightness(1.07) saturate(1.25)}
.plan .room.hot .wall{fill:var(--gold)}
.plan .room:focus-visible .wall{fill:var(--accent)}
table.sched{width:100%;border-collapse:collapse;font-size:13.5px}
.schedwrap{overflow-x:auto}
table.sched th{font:600 11px/1.2 var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);text-align:left;padding:8px 10px;border-bottom:1.5px solid var(--ink);white-space:nowrap}
table.sched td{padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
table.sched td.size{font:13px var(--mono);white-space:nowrap;font-variant-numeric:tabular-nums}
table.sched td.nm{font-weight:600;white-space:nowrap}
table.sched td.nm i{display:block;font:400 11px var(--mono);color:var(--muted);font-style:normal;text-transform:uppercase;letter-spacing:.06em}
table.sched tr.hot td{background:color-mix(in srgb, var(--gold) 14%, transparent)}
table.sched .zsw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;border:1px solid var(--wall);vertical-align:0}
.notes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 28px}
.notes div{display:flex;flex-direction:column;gap:4px;min-width:0}
.notes h3{font-size:16px}
.notes p{font-size:14px;color:var(--muted)}
code{font:13px var(--mono)}
@media (max-width:860px){
  header.top{grid-template-columns:minmax(0,1fr)}
  .compare{grid-template-columns:minmax(0,1fr)}
  .notes{grid-template-columns:minmax(0,1fr)}
  .sheethead .big{font-size:44px}
  table.sched td.note{min-width:240px}
}
@media (prefers-reduced-motion:no-preference){ .card{transition:border-color .15s} }
"""

ZVAR = {"floor": "--z-floor", "high": "--z-high", "food": "--z-food", "feature": "--z-feature", "entry": "--z-entry",
        "service": "--z-service", "circ": "--z-circ"}


def esc(s):
    return html.escape(str(s))


def card(p, L):
    s = p["stats"]
    ok = not p["problems"]
    walks = p["walks"]
    farthest = max(walks.values()) if walks else 0
    return f"""<a class="card" href="#{p['key']}">
  <span class="letter">VARIATION {L}</span>
  <h3>{esc(p['title'])}</h3>
  <p>{esc(p['tagline'])}</p>
  <div class="nums"><div><b>{s['tables']}</b><small>tables</small></div><div><b>{s['cabinets']}</b><small>slots</small></div>
  <div><b>{s['seats']}</b><small>seats</small></div><div><b>{farthest}s</b><small>far walk</small></div></div>
  <span class="chk{'' if ok else ' bad'}">{'✓ passes the floor plan checks' if ok else f"{len(p['problems'])} checker problems"}</span>
</a>"""


def sheet(p, L):
    rows = []
    for r in p["schedule"]:
        tag = KIND_LABEL[r["kind"]] + (" · live now" if r["existing"] else "")
        rows.append(f"""<tr data-room="{r['id']}"><td class="nm"><span class="zsw" style="background:var({ZVAR[r['kind']]})"></span>{esc(r['name'])}<i>{esc(tag)}</i></td>
<td class="size">{esc(r['size'])}</td><td>{esc(r['joins']) or '—'}</td><td>{esc(r['has']) or '—'}</td><td class="note">{esc(r['note'])}</td></tr>""")
    walks = "".join(f"<span>Spawn → {esc(k)} <b>{v}s</b></span>" for k, v in p["walks"].items())
    games = ", ".join(f"{n} {NAMES[g]}" for g, n in sorted(p["stats"]["games"].items(), key=lambda kv: -kv[1]))
    return f"""<section class="sheet" id="{p['key']}" data-plan="{p['key']}">
  <div class="sheethead"><span class="big">{L}</span><h2>{esc(p['title'])}</h2>
    <span class="insp">Inspired by {esc(p['inspired'])}</span><p>{esc(p['idea'])}</p></div>
  <div class="walks">{walks}<span>{esc(games)}</span></div>
  <figure>{p['svg']}</figure>
  <div class="schedwrap"><table class="sched"><thead><tr><th>Room</th><th>Size (px)</th><th>Joined by</th><th>Holds</th><th>Notes</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table></div>
</section>"""


LEGEND = """<div class="legend">
<span><i class="sw" style="background:var(--z-floor)"></i>Gaming floor</span>
<span><i class="sw" style="background:var(--z-high)"></i>High limit</span>
<span><i class="sw" style="background:var(--z-food)"></i>Food &amp; drink</span>
<span><i class="sw" style="background:var(--z-feature)"></i>Feature</span>
<span><i class="sw" style="background:var(--z-circ)"></i>Circulation</span>
<span><i class="sw" style="background:repeating-linear-gradient(45deg,var(--z-service) 0 3px,var(--muted) 3px 4px)"></i>NPCs only</span>
<span><i class="sw" style="background:var(--felt-card)"></i>Card table</span>
<span><i class="sw" style="background:var(--felt-wheel)"></i>Roulette</span>
<span><i class="sw" style="background:var(--felt-dice)"></i>Craps</span>
<span><i class="sw" style="background:var(--felt-bac)"></i>Baccarat</span>
<span><i class="sw" style="background:var(--felt-master)"></i>Master table</span>
<span><i class="sw" style="background:var(--cab)"></i>Slot cabinet</span>
<span><i class="sw dot" style="background:var(--seat)"></i>Seat</span>
<span><i class="sw dot" style="background:var(--npc)"></i>Staff / spawn</span>
<span><i class="sw" style="background:none;border-style:dashed"></i>Door (dashed leaf) · gap = archway</span>
</div>"""

NOTES = """<section class="sheet"><h2>Building it in CasinoWorld</h2><div class="notes">
<div><h3>Doors or archways</h3><p>Rooms joined by an archway draw together, so archways carry the floor's noise and bustle into the bar, lounge and sportsbook. A room behind a door stays hidden until you reach the doorway, which is right for the high limit rooms and the restaurant. They feel private, and each door gets a named tab on the minimap.</p></div>
<div><h3>Lobby kept as is</h3><p>All three plans build north of the live Modern lobby (608 × 400) and keep the two lifts. The only change is turning the lobby's 64 px top door into a 192 px archway, so you can see the casino from the spawn point.</p></div>
<div><h3>NPCs-only rooms</h3><p>Kitchen, staff, restrooms and the lifts are dead ends in the same way the lifts are now. NPCs arrive there and walk back in, so the restaurant gets waiters, the pits get dealers walking in for a shift change, and people pop off to the restrooms, with none of it costing any art.</p></div>
<div><h3>Table count and performance</h3><p>These plans have 13 to 25 tables. Every room is built on every client, and the architecture notes say that past a few dozen tables the server should only send each player the tables in rooms they can see. That cut-off is worth doing before the biggest of these goes live.</p></div>
<div><h3>High limit tools you already have</h3><p>Table limits and the limits sign set the high-limit rooms apart (the labels like "Blackjack £500" are only suggestions). A Master table gives a small salon every game without adding tables, and the cashier cage and ATMs tie in with the Bank.</p></div>
<div><h3>Walking distances</h3><p>At 105 px a second, the furthest rooms are about half a minute from spawn in every plan (route lengths from the server's own walk timer). If that feels long in play, shrink the main floor rather than the side rooms, or add a second spawn point nearer the action.</p></div>
<div><h3>Mixing them</h3><p>The parts swap between plans: A's racetrack aisle would fit inside C's floor, B's terrace loop could hang off A's slot side, and C's Jade Room works as a side room in any of them. Each room is its own blueprint, so a hybrid is mostly moving rooms around on the Floor plan tab.</p></div>
<div><h3>What's a placeholder</h3><p>Restaurant tables are round tables with armchairs, the sportsbook counter is reception desks, and every slot is set to Armadillo so the checker passes. The real art would come from the Vegas, Modern and Nocturne sets or new uploads.</p></div>
</div></section>"""

JS = r"""
document.querySelectorAll('[data-plan]').forEach(sec=>{
  const set=(id,on)=>sec.querySelectorAll(`[data-room="${id}"]`).forEach(el=>el.classList.toggle('hot',on));
  sec.querySelectorAll('[data-room]').forEach(el=>{
    const id=el.dataset.room;
    el.addEventListener('mouseenter',()=>set(id,true));
    el.addEventListener('mouseleave',()=>set(id,false));
    el.addEventListener('focus',()=>set(id,true));
    el.addEventListener('blur',()=>set(id,false));
    if(el.tagName==='g') el.addEventListener('click',()=>{
      const row=sec.querySelector(`tr[data-room="${id}"]`); if(row) row.scrollIntoView({block:'nearest',behavior:'smooth'});
    });
  });
});
"""

total_ok = all(not p["problems"] for p in plans)
doc = f"""<title>Resort Floor Blockouts</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@500;600;700&family=Public+Sans:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;600;700&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="top">
  <div class="intro"><span class="eyebrow">CasinoWorld · floor plan blockouts</span>
  <h1>A medium resort casino, three ways</h1>
  <p class="muted">Three layouts for a medium casino, drawn at game scale on top of the live Modern lobby. They're blockouts, not a build, but every room, door, table and slot bank was laid out as a real floor plan and run through the server's own floor plan checks, so the sizes are ones the game will take. Hover a room to find it in the schedule.</p></div>
  <div class="titleblock"><div>Project</div><div>CasinoWorld</div><div>Sheet</div><div>A-101 to A-103</div>
  <div>Scale</div><div>game px (1:1 plan)</div><div>North</div><div>back wall up</div><div>Date</div><div>27 Oct 2026</div>
  <div>Checks</div><div>{'all pass' if total_ok else 'see sheets'}</div></div>
</header>
{LEGEND}
<div class="compare">{''.join(card(p, L) for p, L in zip(plans, LETTERS))}</div>
{''.join(sheet(p, L) for p, L in zip(plans, LETTERS))}
{NOTES}
</div>
<script>{JS}</script>
"""
(HERE.parent / "resort-floor-blockouts.html").write_text(doc)
print("wrote", len(doc) // 1024, "KB")
