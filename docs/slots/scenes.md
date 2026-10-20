# Scenes: a slot screen's look

A slot's **scene** is its whole look on the slot screen: the shapes of its parts, its colours, frosted glass,
decor, fonts and words. Scene is the Slot design wizard's least automated step. Mike writes a **Brief** (words and
reference pictures) and presses **Ask Claude**. A Claude Code session then designs a **skin** by hand and saves it
to the design, where Mike picks it and tweaks it.

The layout never changes: the reels in the middle, the jackpot meters and logo on top, the random features on the
left, the bonus and Buy Bonus on the right, and the deck along the bottom. These positions are fixed in
`slot_screen.gd` (`LOGO_RECT`, `DECK_ROW`, ...), and the wizard's mockup uses the same 1280×720 coordinates. A skin
changes how those places look, not where they are.

## Designing a scene ("design the X scene")

1. `tools/scene.py brief <design>` prints Mike's brief and the paths to its reference pictures (look at them). It
   also prints the concept, the lettering font, the chosen art for each tier, the background, the logo and the
   chosen skin.
2. Stop the dev server, run `tools/scene.py fresh <design>`, then start it again (`tools/dev.sh server`, in the
   background). The dev instance now has its own copy of the design to try things on.
3. Write the skin as a JSON file in your scratchpad, then run `tools/scene.py shot <design> skin.json` and look at
   `.dev/shots/scene_<design>.png`.
   - Iterate on that one shot.
   - Then check the busy cases with `--bonus trail|free|battle|voyage`. A pop-up and every bonus panel use the
     skin's `panel`.
   - Shots are taken at 1164 px wide. Thin shapes and dark blocks read badly at that size, so crop and enlarge a
     region before you judge it.
4. `tools/scene.py put <design> skin.json` saves it to the live board, by Claude. Add `--choose` only if Mike asked
   for that. Without it, the skin appears on the Scene step for him to pick.
   - The brief is marked answered.
   - The skin keeps a copy as you made it, so **Reset to Claude's version** undoes his tweaks.
   - Never edit a live `design.json`.
5. If the scene needs a background or a logo, use the Scene step's own **Generate**, **Style the lettering** or
   **Render** on the live board. They're Mike's design's assets, and he picks the takes.

What to aim for: one clear idea taken from the brief and the art, plus the slot's lettering font (`@lettering`) on
every word. Every word stays readable at the sizes the screen uses, and nothing covers the working places (the
server refuses decor that does).

## The skin

```json
{
 "name": "Voyager LCARS", "base": "lcars", "note": "what it's after, for whoever tweaks it next",
 "palette": {"hl": "#9fe3ff", "a": "#4a7cab", "b": "#6aa5cf", "c": "#a6d3dc", "d": "#22446a", "warn": "#f5a623",
             "glass": "#08131f", "grand": "#f5a623", "major": "#b98fd6", "minor": "#7fc4c9", "mini": "#6f9fd8"},
 "colours": {"gold": "#9fdcff", "cream": "#e4f2ff", "win": "#ffd27a", "...": "the screen's eleven, below"},
 "glass": {"opacity": 0.55, "sheen": 0.12, "edge": 1.5, "blur": 14},
 "parts": {"meter": {"shape": "tab", "fill": "tier", "text": "goldHi"}, "...": "below"},
 "decor": [{"id": "sd", "kind": "text", "x": 796, "y": 87, "w": 230, "h": 20, "text": "STARDATE {stardate}", "colour": "c"}],
 "fonts": {"display": "@lettering", "ui": "@lettering"},
 "texts": {"spin": "ENGAGE", "features": "TACTICAL SUBSYSTEMS"}
}
```

Anything you leave out comes from the family's starter (`slot_design_scene.py` `CLASSIC`, `LCARS`). The server
checks everything and says what's wrong (`check_skin`).

- **base**: `classic` or `lcars`.
  - `classic` is the four frame styles: Armadillo's wood, plus metal, neon and glass. It uses `frame: {style,
    colour}` and `deck: {style, colour|null}`, and ignores `parts` and `decor`.
  - `lcars` draws every part from its own shapes.
- **colours**: the screen's eleven tones, used by every family.
  - `gold`: the accent.
  - `goldHi`, `goldLo`: its highlight and its shadow.
  - `edge`: the panel edges.
  - `cream`: the text.
  - `muted`: quiet text.
  - `ink`: text on colour.
  - `shade`: banners, pop-ups and dimming.
  - `win`: win amounts.
  - `spin`: the spin button.
  - `alert`: free games and FIRE.
- **palette**: the family's own tones.
  - `hl` is the highlight. `a`, `b`, `c` and `d` are blocks, with `d` the deep one. `warn` is an amber accent, used
    sparingly. `glass` is the tint of the glass.
  - `grand`, `major`, `minor` and `mini` are the jackpot tiers.
  - Anywhere a colour is wanted, give one of these names, one of the eleven, or a literal colour like `#8fd3ff`.
- **glass**: frosted panels.
  - `opacity`: the tint over the blurred background.
  - `sheen`: the light across the top of a panel.
  - `edge`: the edge width, in px.
  - `blur`: how much of the background shows through. The mockup blurs it live; the build bakes
    `art/bg_glass.png`. With no background, the glass is only its tint over deep space.
- **parts**: a shape for each part (the first shape listed is the default), and the colours that shape takes.

  | part | shapes | colours |
  |---|---|---|
  | `meter`: the jackpot meters | `tab` (a tier-coloured cap on the outer end and a glass body), `pill`, `glass` | `fill` (`"tier"`: each tier's own), `text` |
  | `panel`: the side panels, pop-ups and bonus panels | `elbow` (elbows top and bottom on the spine side, the spine in blocks, a glass body), `glass` | `top`, `bottom`, `spine` (a list of 1 to 4), `fill`, `edge`, `title` |
  | `frame`: the reel well | `elbow` (top-left and bottom-right elbows, with bars running on in blocks), `glass` | `top`, `bottom`, `edge`, `fill` |
  | `box`: credit, bet and win, the feature list, the info boxes | `pill` (rounded when tall), `glass` | `fill`, `edge`, `label`, `value` |
  | `button` | `pill`, `half` (rounded on the right only) | `fill`, `on` (switched on), `text` |
  | `spin` | `pill` (wide, across 1036..1164), `disc` | `fill`, `text` |
  | `deck`: the bottom band | `elbow` (an elbow at the left end and a rail along the top), `bar` | `fill`, `edge`, `accent` |

  The side panels' spines run in the screen's margin (x 4..20 and 1260..1276).
- **decor**: free shapes. Every item has these fields:
  - `id`, `kind`.
  - A box: `x`, `y`, `w`, `h`.
  - `colour`.
  - `layer`: `under` (drawn before the parts) or `over` (after the deck).
  - `show`, `alpha`.

  The kinds:
  - `elbow`: `corner` (`tl`, `tr`, `bl` or `br`), `arm` (the vertical arm's width), `bar` (the bar's height) and `r`
    (the outer radius).
  - `bar`: `round` (`none`, `left`, `right` or `both`).
  - `pill`: a bar rounded both ends, with optional `text`, `text_colour`, `size`, `font` and `align`.
  - `text`: `text`, `size`, `font` (`display` or `ui`) and `align`. The text fits its box's width. The tokens
    `{stardate}`, `{date}`, `{time}` and `{name}` fill themselves in.
  - `readout`: an LCARS number cluster. `cells` gives the digits in each cell, e.g. `[2, 5, 2]`. It also takes
    `colours` (a list, cycled), `text_colour`, `tick` (seconds between changes, 0 for still) and `seed`.

  Rules:
  - Every box stays inside the safe area, 4,4 to 1276,716.
  - An `over` item may not touch `PROTECTED`: the reels, the meters, the deck's readouts and buttons, and the side
    panels' contents.
  - Decor stays in the chrome because the panels' contents change with the Features and Bonus games steps.

  Free places for decor:
  - The band between the meters and the panels: y 86..106, x 18..488 and 792..1262. The logo sits in 494..786.
  - The screen's margins.
  - The ends of the deck rail.
- **fonts**: `display` (titles, labels, the spin label) and `ui` (numbers, lists). Each is `@lettering` (the Art
  step's lettering font, so the slot's font carries over) or a font file the design has. A glyph the font lacks
  falls back to Barlow Condensed (StarTrek Film has no `£`). A font browsers refuse is served patched
  (`slot_design_art.web_font`).
- **texts**: the screen's words, relabelled: `spin`, `stop`, `fire`, `sail`, `credit`, `bet`, `win`, `info`,
  `turbo`, `auto`, `cashout`, `features` (the left panel's title), `buy`, `tagline` (the deck's message), `collect`
  and `settings`.
  - The features' names belong to the Features step.
  - The bonuses' names belong to Bonus games.

## Where it's drawn

- The wizard's mockup: `slot_design_web/mockup/game.js`, the section "the skin's shapes" (`lcarsPanel`,
  `lcarsMeter`, `drawDecor`, ...).
- The game: `client/scenes/slots/slot_screen.gd`, the section "the skin" (`_lcars_panel`, ...), with the polygons
  in `skin_draw.gd`.
- Both draw the same shapes at the same coordinates. A new family, shape or decor kind goes in both, in
  `slot_design_scene.py` (`BASES`, `PARTS`, `DECOR_KINDS`), and here.
