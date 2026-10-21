# Table styles: external assets and their licences

Every outside asset the table styles use, where it came from, and what was done to it. Casino World is a
non-profit project, but every asset here allows commercial use anyway. When an asset moves into the game
(`client/assets/`), add it to that folder's `CREDITS.md` as well.

## Textures (Poly Haven, CC0)

All of these are from [Poly Haven](https://polyhaven.com) under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
That means no attribution is required, but we give it anyway. Each was fetched on 2026-10-21 as its 1k diffuse JPG
through `https://api.polyhaven.com/files/<id>`. They were then processed by the mockup's tile script into
`docs/table_styles/mockup/textures/`: scaled to 1024×1024 (a few are 985–1026 px tall), then reduced to 512 px
(256 px for the felt weave).

| Our file | Poly Haven asset | Authors | What we changed |
|---|---|---|---|
| `wood_mahogany.jpg` | [Dark Wood](https://polyhaven.com/a/dark_wood) (`dark_wood`) | Dimitrios Savva (photography), Dario Barresi (baking), Rico Cilliers (tiling) | resized |
| `wood_walnut.jpg` | [Lacquered Cherry Wood](https://polyhaven.com/a/lacquered_cherry_wood) | Jenelle van Heerden (scanning), Rico Cilliers (processing) | resized, brightened ×1.25 |
| `wood_wenge.jpg` | [Wood Table 001](https://polyhaven.com/a/wood_table_001) | Dimitrios Savva (photography), Rico Cilliers (processing) | turned 90° (grain runs left–right), resized |
| `wood_rosewood.jpg` | [Rosewood Veneer 1](https://polyhaven.com/a/rosewood_veneer1) | Jenelle van Heerden | turned 90°, resized, darkened ×0.85 |
| `wood_ebony.jpg` | [Flamed Black Veneer](https://polyhaven.com/a/flamed_black_veneer) | Jenelle van Heerden | resized, darkened ×0.55, desaturated, contrast ×2.2 |
| `leather_detail.png` | [Leather White](https://polyhaven.com/a/leather_white) | Rob Tuytel | greyscale, high-pass to a mid-grey detail map (tinted by blending) |
| `leather_pebble.png` | [Brown Leather](https://polyhaven.com/a/brown_leather) | Rob Tuytel | greyscale, high-pass detail map (spare, not used by a preset) |
| `felt_weave.png` | [Terlenka](https://polyhaven.com/a/terlenka) | colormass (photography), Rico Cilliers (processing) | greyscale, high-pass detail map, 256 px |
| `felt_velvet.png` | [Velour Velvet](https://polyhaven.com/a/velour_velvet) | colormass (photography), Rico Cilliers (processing) | greyscale, high-pass detail map |

## Fonts (Google Fonts, SIL Open Font License 1.1)

The mockup loads these from Google Fonts. Any that go into the game are bundled as a static instance with
overlapping outlines merged (as Cinzel was, see `docs/tables.md`), with their OFL text alongside, as for
`client/assets/fonts/Cinzel-OFL.txt`.

| Font | Used for | Licence |
|---|---|---|
| [Cinzel](https://fonts.google.com/specimen/Cinzel) | Grand Mahogany printing (already in the game) | OFL 1.1 |
| [Cormorant SC](https://fonts.google.com/specimen/Cormorant+SC) | Monte Carlo printing | OFL 1.1 |
| [Josefin Sans](https://fonts.google.com/specimen/Josefin+Sans) | Midnight Deco printing | OFL 1.1 |
| [Montserrat](https://fonts.google.com/specimen/Montserrat) | Modern Vegas printing | OFL 1.1 |
| [Barlow / Barlow Condensed](https://fonts.google.com/specimen/Barlow) | the mockup page itself, chip and card lettering (Barlow Condensed is already in the game) | OFL 1.1 |

## The game's own art in the mockup

- `textures/carpet.png` is the game's carpet tile, made by `tools/build_art.py`. It's ours.
- `textures/dealer.png` is the game's dealer sprite sheet, built from the Universal LPC Spritesheet Character
  Generator (CC-BY-SA 3.0 / GPL 3.0 / OGA-BY 3.0). The full credits are in `client/assets/sprites/CREDITS.md`.

Everything else (the shuffler, shoe, discard rack, chips, card backs, spots and Jackpot discs) is drawn in code.
