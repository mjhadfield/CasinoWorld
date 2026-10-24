# Cut per-frame polygon redraws (GL churn)

**Branch:** `main` (or `task/gl-churn` if run alongside something else)

## Goal
An optimisation pass: find the nodes that redraw polygons, circles and arcs every frame on an ordinary floor view,
and stop them, so the client creates far fewer GL objects and spends less of each frame re-recording drawings.

## Background
On 2026-10-25 Mike's tab froze after about 49 minutes with `RangeError: Invalid array length` in
`glGenBuffers`. In GL Compatibility, every polygon, circle and arc in a `_draw()` gets a fresh GL buffer and
vertex array each time the node redraws, and Emscripten never reused their ids, so its id tables grew until V8
refused. `tools/patch_web_gl.py` (run by `tools/dev.sh export`) fixed the freeze by reusing freed ids
(docs/performance.md). The churn itself is still there:

- Standing on the dev floor (headless Chromium with the GPU, 60 fps): about 15,000 GL objects created a second,
  roughly 8,500 buffers and 6,500 vertex arrays. That's about 250 per frame, or roughly 100 polygons redrawn
  every frame. Mike's live session averaged about 45,000 a second (a faster screen, a busier view, or both).
- 18 scripts call `queue_redraw()` from `_process`. Most are gated by the performance pass rules, but these look
  likely to redraw a lot while NPC games run:
  - `scenes/table/casino_table.gd`: redraws the whole table every frame while a countdown or thinking ring
    shows (`_timer_end > now`), which is much of every round at NPC tables.
  - `scenes/table/jackpot_lights.gd`: every frame while the table has jackpot lights, with no on-screen check.
  - `scenes/table/card_shuffler.gd`: every frame until it's idle.
  - `scenes/table/crp_table.gd`, `scenes/table/rou_table.gd`, `scenes/slots/slot_screen.gd`,
    `scenes/table/jackpot_sign.gd`: check what they draw while animating.

## How to measure
Count GL objects per second with `tools/shot.py` on the dev instance by wrapping the WebGL prototype:

```fish
set P '(()=>{const c=window.__glc={n:0,t:performance.now()};const P=WebGL2RenderingContext.prototype;for(const m of ["createBuffer","createVertexArray"]){const o=P[m];P[m]=function(){c.n++;c[m]=(c[m]||0)+1;return o.apply(this,arguments)}}return "patched"})()'
set R '(()=>{const c=window.__glc,s=(performance.now()-c.t)/1000;return JSON.stringify({per_sec:Math.round(c.n/s),...c})})()'
tools/shot.py --gpu eval:$P wait:15000 eval:$R
```

To find the culprits, try the same view with one suspect's redraw disabled at a time, or seated at each kind of
table (`sit:TABLE`). Then apply docs/performance.md's rules: move what animates onto its own small node, animated
with properties (`rotation`, `position`, `modulate`) so the big drawing stays recorded, draw static parts once,
and redraw a countdown ring a few times a second rather than every frame.

## Files
The table and sign scripts above, as the measurements point to them. Not `tools/patch_web_gl.py`.

## Done when
- [ ] GL objects created per second on a normal floor view are a small fraction of 15,000, numbers in
      docs/performance.md
- [ ] Countdowns, glows and jackpot lights still look smooth to Mike
- [ ] `tools/dev.sh test` passes

## Handoff
- **State:** not started; this note is the plan
- **Changed:** nothing yet
- **Checked:** the 15,000/s measurement above (2026-10-25)
- **Questions for Mike:** none yet
