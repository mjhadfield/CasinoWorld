# Casino World

A living 2D casino you play together in the browser. You walk your character around the floor past other
players and NPCs, sit down at any of eleven tables or the slot machines, and play alongside dealers who deal,
call and pay out. It's the successor to `~/Projects/Casino` (v2), whose rules it ports.

- **client/** is a Godot 4.7 project written in GDScript, exported to the web, so players just open a link.
- **server/** is a Python FastAPI app, and it's authoritative: it runs the tables, the NPCs and the world,
  holds the wallets, and serves the web export.

| Doc | What's in it |
|---|---|
| [docs/games/](docs/games/README.md) | How to play: the floor, what every table shares, then one file per game |
| [docs/architecture.md](docs/architecture.md) | The design |
| [server/protocol.md](server/protocol.md) | Every WebSocket message |
| [docs/tables.md](docs/tables.md) | Building a table: the shared pieces, the layout rules, the layout audit |
| [docs/slots/](docs/slots/README.md) | The slots design record, and how to add another slot |
| [docs/PARALLEL.md](docs/PARALLEL.md) | Running two sessions side by side |

## Setup (one-off)
```fish
sudo pacman -S godot                      # 4.7.x, plus Web export templates from the editor
cd ~/Projects/CasinoWorld/server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium   # for tools/shot.py and tools/build_slot_art.py
```

## Run
The live server is Citadel's unit `hub-proj-casino-world`: HTTP on 8660 (editor), HTTPS on 8661 (browsers),
run from this folder with `server/data/`. `tools/dev.sh` does the everyday jobs:

```fish
tools/dev.sh restart        # after server changes
tools/dev.sh export         # after client changes, then reload the page (no restart needed)
tools/dev.sh server         # a scratch instance on its own port (8670 up) with .dev/data
```

- **Browser or phone:** open `https://192.168.0.66:8661`. Each device shows a "connection not private"
  warning once (Advanced › Proceed). The certificate is self-signed and the server generates it into
  `server/data/tls/`. Godot's web build only runs over HTTPS or on `localhost`.
- **Desktop:** open `client/project.godot` in Godot and press **F5**. It connects to
  `ws://127.0.0.1:8660/ws`, or to `CASINO_SERVER_URL` if set.
- **By hand:** `cd server; .venv/bin/python -m casino_server`.

Environment knobs:
- `CASINO_NPCS` pins how many NPCs roam, overriding the floor population on the admin page's Settings tab.
- `CASINO_SPEED` scales every table timer and NPC pace; `0.5` is twice as fast.
- `CASINO_DATA_DIR` sets where the SQLite database lives (default `server/data/`).
- `CASINO_PORT` and `CASINO_WEB_DIR` set the HTTP port (HTTPS is one above) and the web export served.
- `CASINO_DESIGNS_DIR` moves the Slot design board's folders (default `server/slot_designs/`), and
  `CASINO_SLOT_BUILDS_DIR` the built slots (default `server/slot_builds/`); dev instances use copies in `.dev/`,
  and the tests scratch directories.

## Admin page
Open **`/admin`** on the server (e.g. https://192.168.0.66:8661/admin; `/maintenance` still works). There's
no password: it's open to anyone who can reach the server, the same as the game, which is fine on the LAN
and Tailscale. It has six tabs:
- **Sounds:** the sound sets down the left: **Whole casino**, each table game, **Every slot machine** and each
  machine. A set plays the one above's sound for any moment it doesn't set itself, so Blackjack can have its
  own card deal and Armadillo Goes West its own reel stop while both click like everything else. Each set's
  moments are listed by section, marked own or borrowed; **Change…** opens the library beside them (the
  folders suited to that section first) to play, **Use** or **Add** a variant, or upload your own. **Same as …**
  hands a moment back to the set above, **No sound** makes it silent in that set (the set above doesn't fill in),
  and **Reset** puts it back to how it came. Moments that loop (the reels
  spinning, the win meter) preview on a loop. Changes save at once and every open game picks them up within a
  second.
  - The library is `server/sound_library/`, CC0 (credits in its `LIBRARY.md`); uploads go to
    `<data dir>/sounds/uploads/` and the changes to `<data dir>/sounds.json`. Each set starts with the
    `FACTORY` choices in `casino_server/sounds.py`, where the moments and sets are defined.
  - The game's `Sfx` fetches every set when it connects, plays each table's sounds from its game's set, and
    until then falls back to the sounds built into the client (`client/assets/audio/`).
- **NPCs:** the roster, seeded on first run with 20 punters and 20 dealers (tables `npcs` and `npc_visits`).
  - **Looks:** body, hair, clothes and accessories in their colours, plus Randomise and uniforms, with a live
    preview. The server builds each sheet from the LPC generator's layers (`casino_server/art.py`; downloads
    cached in `server/lpc_cache/`, `python -m casino_server.art prefetch` fetches the lot).
  - **How punters play:** a style (Grinder, Casual or Gambler), traits (Whale, Chaser, Hit-and-run,
    Superstitious, Regular, Card counter, VIP; see `casino_server/roster.py`), a budget range, lucky numbers
    and favourite games. Bulk create generates a batch to review before accepting.
  - **Visits:** each visit brings a budget they're willing to lose. They leave bust, done for the day, while
    ahead (Hit-and-run) or doubled up (a Gambler), then sit out a cooldown while others take their place.
  - **Stats** per NPC, and **Bring in now**, **Send home** and **Reset stats**.
  - Waiters, pit bosses, cashiers and bar staff can be designed, but don't work the floor yet.
- **Players:** everyone's lifetime staked, returned and net, per game, from the ledger.
- **Slots:** the jackpot meters, players' return on slots, and the symbol art set.
- **Floor:** the slot banks. A bank is any mix of slots (Armadillo and every built slot), each cabinet facing any
  way. The floor map shows the room, the tables and every bank: drag a bank to move it. The bank close up is a grid
  of half a cabinet: click it to put down a cabinet of the picked slot, drag, turn (R), remove (Delete), or re-slot
  the selected cabinets. Cabinets that would block a table, a walkway point, each other or a player's stool show
  red and can't be saved (the server checks the same). **Save** keeps them in `<data>/slot_banks.json`; **Apply**
  restarts the casino to put them on the floor. The map and the checks come from
  `server/casino_server/floor_map.json`: after moving or reshaping a table, run
  `cd client && godot --headless --path . -s ../tools/floor_map.gd`.
- **Slot design:** the slot machine builder (`#design/<design>/<step>`): a tab per design plus **New design**, and
  eleven steps down the side, each marked to do, in progress or done: Concept, Art, Value ladder, Scene, Features,
  Bonus games, Sprites, Sounds, Maths & payouts, Mockup & sign-off, Build. Star Trek is the first design. The
  wizard's UI is its own scripts in `casino_server/slot_design_web/`, which the tab loads; the server side is
  `casino_server/slot_design.py` (the designs and their steps) and `slot_design_art.py` (the image model, keying, the frame).
  - **Concept:** the name, a theme brief and style notes that lead every image-model prompt, the tier shape (how many
    high, mid and low pays, which sets the Art step's counts), the target return and volatility, and the sheet
    cutter: upload a reference sheet, drag a box round each symbol, and cut them into new symbols (Generate makes one faithful redraw of each).
  - **Art:** a section per category with how many the main game needs, and a card per symbol: cycle its takes,
    pick a character's frame colour, a royal's colour or a special's word, change its **Kind**, tick it into the final set, link reference images (upload, a web address, or
    art on the board), **First generate** (1, 2 or 3 takes in the Prompts styles from reference 1 or the description, as a new
    symbol gets; on any card, e.g. one whose first Generate was cancelled), **Reiterate** (1, 3 or 5 fresh takes from the chosen
    take or a reference, with a note; a reference redraw also goes by the symbol's description; marking one clears the other),
    **Refine** (one image-model edit that keeps everything but what you name), **Fit** (rescale, nudge and rotate it in its
    tile, previewed live; saved as a new take), **Split** (asks for a name, then moves the take shown into a new symbol of its own in the
    same section; the original goes to the Bin) and the **Bin** (✕ on a take; restorable, nothing is deleted).
    **New** adds a symbol to a category from a description, a reference or both, and stacks. **Generate** sends
    everything marked to the image model in Odysseus: any diffusers model started from Odysseus's Cookbook with
    CPU Offload ticked (FLUX.2-klein-4B, or Qwen-Image-2.1 with `--quantize nf4`). The board's bar names the model
    loaded, and jobs wait while none is. Edits need a model that takes a reference image; a marked card's **Queue** sends just that symbol and sets its Reiterate back to No; **Cancel** on a card or **Cancel all** stops jobs, a running one included (the picture being
    drawn is thrown away). A card's **Section** moves the symbol to another category. **Hide** takes a symbol that
    isn't in use (not in the final set, on the ladder or followed by an art slot) off the board, **Hide unused** does
    all of them at once, and **Hidden** shows them to unhide. The **Prompts** fold at the top sets how many takes a
    new symbol's first Generate makes by default (1, 2 or 3; take n uses style n; a sheet cut makes 1) and rewrites the three redraw-from-a-reference
    styles, the three from-a-description styles, the character portrait style, the specials' emblem style and the
    royals' repaint, per design (`art_prompts` in design.json; an emptied box or **Default** goes back to the code's
    prompt). Its **Lettering** sets the specials' font and colours and the royals' font (`lettering`; unset, the
    scene's display font and gold). The lettering font is the slot's font: the scene's words use it too. One worker draws every job, one picture
    at a time.
  - **Value ladder:** order the final set by value into the tiers of the tier shape (Wild, the bonus and
    free-spins scatters, then H1…, M1…, L1…), by dragging or click-to-place, with each tier's pays shown and the
    Symbol Upgrade chain beside it. Auto-fill takes the specials by name and each category in order.
  - **Scene:** the screen's whole look, as **scenes** (skins: `slot_design_scene.py`, and [docs/slots/scenes.md](docs/slots/scenes.md)).
    A design keeps several and plays the chosen one: a strip to pick, rename, duplicate, bin (restorable) or start a
    new Classic or LCARS one, and **Reset to Claude's version** for one Claude made. **Look**: the family (Classic,
    the four frame styles; LCARS, elbows and pills on frosted glass), the palette, glass, the two fonts (by default
    the Art step's lettering font), the screen's eleven colours and its words (SPIN, CREDIT, ...). **Parts**: a shape
    and colours per part (Classic: the reel frame's style and colour, and the deck's). **Decor**: the shapes Claude
    laid round the parts (show, colour, words, or the JSON). **Brief for Claude**: words and reference pictures, and
    **Ask Claude**; a Claude Code session answers with a new scene (`tools/scene.py`). The background (the image
    model, three takes; an upload; or art already on the board, fitted to 1280×720) and the logo (**Render** in a
    font with gradient colours, an outline and an optional emblem; **Style the lettering**: that rendering restyled
    by the image model, keeping the font's letters; **Generate**: drawn whole by the image model), each with its own
    **Bin** like Art's. The step shows the **mockup**: the real screen layout, playable, using the ladder's symbols.
    From here on, **Play the mockup** opens it from any step.
    The mockup is the signed-off Armadillo mockup made design-driven (`slot_design_web/mockup/`), running the
    shared maths, `docs/slots/mockup/slots_math.js`, served to it as `/slot-design-ui/slots_math.js`.
  - **Features:** the library's seven random features, each switched on or off with its chance on a paid spin
    and in the free games, its value table (value:weight pairs) and its name on the screen (which sign-off doesn't
    lock); **Show me** plays the mockup with it forced.
  - **Bonus games:** one column: "How players get in" at the top, then a row per bonus with its switch, tags for
    its ways in and pictures, and **Try it**. ▸ opens a row's settings, whether it's on or off (an off bonus keeps
    them): its ways in (started by either scatter or neither, ticked if Buy Bonus can give it), its pictures, and how
    it plays: the Trail bonus (its name, launcher, length, prizepot, special spaces and coin values), the free games,
    and the battle bonus (Red Alert: off until switched on; its name, hint, enemy and boss names, ships per wave,
    shields, return fire, ship prizes, free spins, wave rewards and the boss), and the voyage bonus (Dead Man's Map:
    off until switched on; its words, the four artefacts' names, legs and Hidden Coves, how often each island comes
    up, each island's prizes, Skull Island's sinking chance, Port Royal's prices, the chest, the parts and the
    legend), and the expedition bonus (Delta Quadrant: off until switched on; its words, the hazard levels' and
    hazards' names, route lengths, each level's weight, hazards, prize scale and final prize, the hazard ramp, how
    often each planet comes up, the tech and specials, and the prize tables). Bonuses sharing a way in play one at
    random; a scatter that starts nothing comes off the reels and the Value ladder (its reel counts go to 0, so
    re-freeze the maths). Then Buy Bonus's price and the always-on Jackpot Pick.
  - **Art slots:** the pictures drawn outside the reels: the mascot (Wild Reels and the trail's token) and the
    Instant Win prize on Features; the launcher and the trail's spaces under the Trail bonus, your ship,
    the enemy ship and the boss under the battle, and the voyage's ship, islands, chest, relic, key and four
    artefacts under the voyage, and the expedition's ship, unexplored planet, finds, hazard and final destination
    under the expedition, as a strip of tiles (pick one to change it). Each follows a symbol's chosen take or uses any image on the board, or **Make
    one** adds it to Bonus screens and generates it. **Adjust** tweaks it by hand: size, left/right, up/down,
    rotate (±90° buttons too), mirror, flip, brightness and colour, previewed live in its box. Saved adjustments are
    baked into `adj/<slot>_<hash>.png` in the design folder (the art view's `file`; `src` is the untouched picture),
    so the mockup and Build use the tweaked one. Until set, the mockup shows Armadillo's (the battle's,
    the voyage's and the expedition's are plain vector stand-ins, `docs/slots/tools/battle_standins.py`,
    `voyage_standins.py` and `expedition_standins.py`), which can't be adjusted; a picture for
    something switched off isn't counted as missing.
  - **New ideas:** a feature or bonus that isn't in the library is written up as a spec; Build turns specs into
    code tasks, and once built they join the library.
  - **Sprites:** win animations per tier group (pulse, bounce, shine, glow or spin, with a strength and glow
    colour) and the floor cabinet (body, trim, topper lettering and its words; **Match the scene**), previewed live:
    **Show it** lays a five-of-a-kind on the mockup. Both start from the scene's colours. Every tone the slot screen
    draws (mockup and `slot_screen.gd`) comes from the scene; only the wood style, the drawn dusk and the payline
    colours are fixed. An older design's frame, deck, colours and fonts became its Classic scene
    (`slot_design_scene.migrate`), the colours it never picked worked out from its edge and accent.
  - **Sounds:** the 30 slot moments, each playing what every slot machine plays until given this slot's own
    (from the Sounds tab's library or an upload, several at random, with a volume trim). Kept in the design until
    Build gives the slot its sound set.
  - **Maths & payouts:** the pays per tier, each reel's symbol counts and the Colossal mix. **Simulate** runs the
    shared engine (`slots_math.js`) in a Web Worker and reports the return by source, hit rate, bonus frequency,
    biggest win and volatility against the Concept's target. **Auto-tune** turns one control (low symbols or Wilds
    one at a time, the pays together, or the feature chances) until the return meets the target. **Freeze** keeps
    the strips once the server has replayed 200 of the browser's seeded spins with its own engine and matched them
    exactly, so the mockup and the cabinet play the same game. Changing what was measured shows the freeze as stale.
  - **Mockup & sign-off:** the whole machine, playable, with **Next spin** controls to force any feature, bonus
    or jackpot; the checklist (✗ what Build needs: a full Value ladder, art for every tier, frozen maths; • what's
    still a stand-in); the rules screen's words (written from the design, editable; INFO shows them); and **Sign it
    off**, which locks the Value ladder, Features, Bonus games and Maths until **Reopen**. Looks stay editable.
  - **Build:** writes `server/slot_builds/<id>/` (the variant, its art, fonts and an IDEAS.md for anything
    needing code) and **Install** restarts the live server, which loads it: the game downloads its art, fonts and
    sounds. Its cabinets go on the floor from the Floor tab. No client export is needed (`docs/slots/README.md`
    explains the path).
  - A design is a folder under `server/slot_designs/<id>/` with a `design.json`; `slot_design.py` explains the
    layout. Variants are found from the files. A symbol's kind decides how its takes are made, and for every kind
    but a plain object the code draws the part that has to match across the set. Characters are drawn as a bust
    and put into one shared frame in code, in six colours. Specials are drawn as an emblem with no words, and the
    code lays their word (Wild, Bonus, Scatter, Free spins or their own) over it in the design's shared lettering
    (font and colours in the Prompts fold, with a live sample). A lettering change redoes every special at once,
    with no image model. Royals start from their rank drawn by the code in the royal font, at one height, in their
    colour; the image model repaints it and the tile keeps that size and place. Switching a symbol's kind keeps
    its takes; the next ones are made the new way. Format changes are migrations applied when the server loads
    a design, because the live server saves over `design.json`.
- **Settings:** punters on the floor, cooldowns, dealer shift length.

## Money
`server/data/casino.sqlite` holds players, balances, the ledger and the jackpots; delete it to start
everyone fresh. Don't edit balances in the database by hand: they're whole numbers of pence, and an edit like
`100,000` gets stored as text, which disconnects that player when they bet (the server warns about it at
startup). Use the admin command, which records the change in the ledger and is safe while the server is up:
```fish
cd ~/Projects/CasinoWorld/server
.venv/bin/python -m casino_server.admin list
.venv/bin/python -m casino_server.admin set-balance Mike 1000      # pounds
```

## Tests
```fish
tools/dev.sh test                              # ~35s, on a scratch database
tools/dev.sh test tests/test_craps.py          # one file while you work
tools/dev.sh test --all                        # adds the slow slots return simulation (~2 min)
```
- **v2 parity:** every card game is matched to v2 to the penny over 8,000-20,000 hands, plus the special
  cases; NPC strategies are spot-checked against their published charts.
- **No v2 to match:** Roulette (all 157 bets cover the right numbers and every one's expected value is
  exactly -1/37), Craps (every bet's house edge), and Slots (a parity fixture from `slots_math.js`, the
  rules, and the signed-off return in the slow test).
- **Table machines,** driven tick by tick: turn order, timeouts, folds, side-bet reveals, privacy,
  inactivity, queued bets, Rebet and the jackpot.
- **NPCs** on simulated floors with a fake clock: budgets, visits, cooldowns, archetypes, dealer shifts.
- **The admin, sounds and slots APIs,** and **WebSocket flows:** presence, seated rounds, private cards,
  disconnects, away and resync.

The client has no unit tests. For layout, run the layout audit ([docs/tables.md](docs/tables.md)); to see it,
use `tools/shot.py`.

## Screenshots
`tools/shot.py` drives the web client in headless Chromium against a dev instance (`tools/dev.sh server`),
timing each step by the server's messages rather than by guesswork:
```fish
tools/shot.py sit:crp_1 until:roll_open send:'{"type":"bet","spot":"pass","add":500}' \
    until:throw wait:1500 shot:craps@240,60,800,600
```
Shots land in `.dev/shots/`. `tools/shot.py --help` lists the steps.

`tools/scene.py` is for designing a slot's scene in a session ([docs/slots/scenes.md](docs/slots/scenes.md)):
`brief` prints what Mike asked for, `fresh` copies a design to the dev instance, `shot` shoots the dev mockup with a
skin (and `--bonus` inside a bonus), and `put` saves a finished skin to the live board.

## Art
`python3 tools/build_art.py` rebuilds the built-in character sheets (the player, the dealer and 8 NPC looks,
in `LOOKS`), `client/assets/sprites/CREDITS.md`, the carpet and the felt grain (`build_art.py tiles` does just
the tiles). The layers come from the Universal LPC Spritesheet Character Generator, pinned to one commit,
under CC-BY-SA/GPL. Looks designed on the admin page are built by the server instead.

`server/.venv/bin/python tools/build_slot_art.py [variant]` renders a slot's vector art and lays out the art
library for the admin page's Slots tab. New slot art is designed on the admin page's Slot design tab.

## Code map
- **server/casino_server/**
  - `app.py`: the FastAPI app; `casino.py`: sessions and message routing; `world.py`: everyone on the floor.
  - `floor.py`: the table list, the slot bank and the floor point names.
  - `tables/base.py`: seating, betting, Ready and the clock, shared by every table machine.
  - `tables/<game>.py`: the timed table machines, which are pure and emit events;
    `tables/slot_machine.py` is a cabinet. `tables/runner.py` drives one in real time.
  - `engines/`: the rules (ported from v2, plus Roulette and Craps). `slots/`: the slot engine and variants.
  - `npc.py`: the NPC director; `roster.py`: archetypes and traits; `dealer.py`, `dealers.py`: dealer lines
    and shifts.
  - `store.py`, `jackpot.py`: storage and the progressive pool. `admin.py`, `maintenance.html`: the admin page.
  - `art.py`, `slot_art.py`: server-built character sheets and the slot art library. `sounds.py`: the sounds.
  - `slot_design.py`, `slot_design_steps.py`, `slot_design_scene.py`, `slot_design_build.py`, `slot_design_art.py`: the
    Slot design wizard (designs, its steps, the Scene step's skins, Build, and the image-model/keying/frame pipeline;
    designs in `server/slot_designs/`), its
    UI in `slot_design_web/` (with the design-driven mockup), and `slot_builds.py`: built slots joining at startup.
  - `slot_banks.py`: the slot banks on the floor (the Floor tab, its UI in `slot_banks_web/`), checked against
    `floor_map.json` (written by `tools/floor_map.gd`).
- **client/**
  - `scenes/world/`: the floor (`casino_floor`), avatars, the rooms (`room`), and the pit's podium and ropes (`pit_podium`, `pit_rope`).
  - `scenes/table/`: `floor_game` and `casino_table` (the bases), each game's `*_table` and `*_felt`, the
    shoe, shuffler, discard rack, cards and chips, the roulette wheel and the craps dice.
  - `scenes/slots/`: the cabinet, the full-screen `slot_screen` and `skin_draw` (a scene's LCARS shapes and glass).
  - `scenes/ui/`: the HUD, the Pai Gow `hand_sorter`, and the `settings_menu`, which edits the `Settings`
    autoload (saved to `user://settings.cfg`) and sets the Master, Effects and Ambience bus volumes. The buses
    are declared in `client/default_bus_layout.tres`; adding them in code breaks web audio.
  - `autoload/`: `net` (the socket), `session` (who you are, your balance), `sfx` (`Sfx.play(key)` for your own
    cues, `sfx_at(key, position)` on a table for its sounds that fade with distance, `Sfx.start_loop` and
    `stop_loop` for looping moments; each from the table's sound set), `settings`, `look_loader` and
    `slot_art`.
- **tools/**: `dev.sh`, `shot.py`, `scene.py`, `layout_audit.gd`, `build_art.py`, `build_slot_art.py`.
