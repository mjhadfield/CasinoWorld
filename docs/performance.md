# Performance

How fast the client runs, what makes it slow, the rules that keep it fast, how to measure it, and the
Graphics settings players can change.

## Where the time goes

The web export runs on one thread (`thread_support=false`), so GDScript, drawing and the GL calls all share a
single frame budget: 16.7 ms at 60 fps. The server is negligible. Idle, its 21 table runners are parked, and over
half an hour it uses about 0.2% CPU.

There are two big costs:
- **Rebuilding drawings.** A node's `_draw()` re-records every shape when `queue_redraw()` is called, whether
  or not it's on screen. Chairs, the roulette wheel, the cabinets and the slot screen all used to do this every
  frame (or every 4th frame, all on the same one).
- **Draw calls.** In GL Compatibility, every polygon, circle and antialiased line is its own draw call, replayed
  every frame even when nothing changed. A felt drawn straight is 300 to 400 of them, with three or four on screen.

There is also a fixed cost per frame that the game can't remove. Godot's web context uses explicit swap control,
so Emscripten copies an offscreen back buffer at the end of every frame and queries GL state while it does
(`blitOffscreenFramebuffer`, about 1 to 3 ms on the dev desktop).

## The rules

- **No unconditional `queue_redraw()` in `_process`.** Redraw when something changed, or while something is
  actually animating, and only while it's on screen (`FloorGame.on_screen_now`, from a
  `VisibleOnScreenNotifier2D` round each table and cabinet). Off screen, mark it and redraw on `screen_entered`.
- **Animate with properties, not redraws.** Turn a layer with `rotation` (the roulette rotor and turret), move it
  with `position` (the ball), and fade it with `modulate`. Each of those is one property write.
- **Draw static things once.** `FeltCache` paints each felt into a SubViewport at the screen's own resolution
  (times 1.25) and shows it as one texture. It repaints when the felt would have redrawn, and when the camera's
  zoom or the window changes its size on screen. Off screen for 3 s, a felt keeps only a half-scale copy.
  Chairs keep their built geometry in the style (`Seating.Ink`), as triangle lists played back in a few calls.
- **Spread periodic work.** A glowing chair "breathes" every 4th frame on a frame of its own
  (`FloorGame.breathes_now()`), so the tables don't all redraw on the same frame.
- **Don't draw what's covered.** While a slot's full-screen game is open, the floor (`World`) is hidden. It
  still processes, so the tables keep up.
- **Never use `Engine.max_fps` on the web.** It waits out the rest of each frame inside the frame (the CPU
  spins). `Settings.WEB_CAP` skips the browser's frames instead.

## Measuring

The `frames:` step in `tools/shot.py` times a stretch of frames in the browser and prints the frame rate, the gaps
between frames, and the main-thread work in each frame. It also prints Godot's own counts (draw calls, objects,
nodes, texture memory and the graphics preset), which the in-game overlay leaves in `window.__godotPerf`:

```fish
tools/shot.py --gpu frames:floor:6000 frames:walk:4000:KeyD sit:bj_2 frames:seated:4000 \
    send:'{"type":"stand"}' wait:3000 sit:b1_1 wait:2500 frames:slot_idle:3000 key:Space frames:slot_spin:2500
```

- **`--gpu`** draws with the real GPU. Without it, Chromium uses SwiftShader, a software renderer that stands in
  for a machine with no GPU acceleration.
- **`--cpu-slowdown 4`** stands in for a low-end CPU.
- **Work** is the time Godot's frame callback takes, and it's what to compare. The fps is capped by the display
  (and by the game's own frame cap).
- **Client changes:** export to a scratch folder and point a dev instance at it, so the live build only changes
  once the change is checked:
  ```fish
  cd client; godot --headless --export-release Web ../.dev/web/index.html; cd ..
  CASINO_WEB_DIR=$PWD/.dev/web tools/dev.sh server
  ```

**In the game:** Settings › Show the frame rate (or F3) shows the fps, the ms per frame, draw calls, nodes and
texture memory in the bottom-left corner.

**A desktop run** (`godot -s script.gd` in `client/`) can count draw calls node by node; hide a node and see what
it saves. A desktop run connects to the live server unless `CASINO_SERVER_URL` says otherwise. Point it at the
dev instance (`ws://127.0.0.1:8670/ws`).

## Measured (2026-10-21, 0 NPCs, 1280×720)

Median work per frame in ms, and the fps, before and after the performance pass. The GPU columns ran on the dev
desktop (RTX 3080 Ti, ANGLE Vulkan).

| | GPU | GPU, CPU 4× slower | SwiftShader (no GPU) |
|---|---|---|---|
| Walking the floor | 10.1, spikes to 70 every 4th frame (36 fps) → **4.5 (60 fps)** | 22, spikes to 200 (11 fps) → **8.3 (60 fps)** | 15 (14 fps) → **3.2 (55 fps)** |
| Seated at Blackjack | 11.0 (59 fps) → **4.1 (60 fps)** | 20.8 (42 fps) → **7.8 (59 fps)** | 12.1 (20 fps) → **3.3 (49 fps)** |
| Slot screen, idle | 11.5 (60 fps) → **1.8 (60 fps)** | 23.8 (39 fps) → **3.9 (60 fps)** | 13.4 (16 fps) → **3.1 (25 fps)** |
| Slot screen, spinning | ~12 → **3.7 (60 fps)** | → **8.2 (58 fps)** | → **4.4 (23 fps)** |

On the floor there were about 1,400 draw calls a frame; now there are about 400. Texture memory is about 258 MB,
most of it slot art.

What it means for players' machines:
- **Any machine with a working GPU** now has headroom at 60 fps.
- **Without GPU acceleration** the slot screen is limited by drawing the full screen in software, not by the
  game's own work. The Low preset's Fast resolution draws fewer pixels.

## Graphics settings

These are under Settings › Graphics, kept per device in `user://settings.cfg` (the `Settings` autoload):

| Setting | High | Balanced | Low |
|---|---|---|---|
| Frame rate cap | 60 | 60 | 30 |
| Resolution | Sharp: the screen's own pixels | Sharp | Fast: drawn at 720p and scaled up |
| Free seats breathe | on | off (a steady glow) | off |
| Slot effects | full | reduced: half the coins, no screen shake | reduced |

Changing a row by hand makes the preset "Custom".

**Auto step-down:** a new device starts on High. Once per session, while `graphics_auto` is on, `PerfOverlay`
times 10 s of frames on the floor, after a 3 s settle. Under 45 fps it steps High down to Balanced, and under
30 fps Balanced down to Low, with a toast saying so. Choosing anything in the Graphics section turns this off.
