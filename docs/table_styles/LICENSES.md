# Table styles: external assets and their licences

Every outside asset the table styles use, where it came from, and what was done to it. Casino World is a
non-profit project, but every asset here allows commercial use anyway.

The assets live in three places:
- **The game's tiles:** `client/assets/tiles/table/`, with a pointer back here in that folder's `CREDITS.md`.
- **The admin designer's copies:** `server/casino_server/table_styles_web/textures/` and `fonts/`.
- **The mockup's own processed copies:** `docs/table_styles/mockup/textures/`.

`tools/build_table_tiles.py` makes the first two from the same downloads, so they match. Change its `WOODS`/`SHADES`, and this file, together.

## Textures (Poly Haven, CC0)

The game and designer tiles are the same scans, processed by `tools/build_table_tiles.py`:
- **Woods** (`wood_<name>.jpg`, 512 px): the adjustments below, plus a faint warm tint laid over with "screen".
- **Leather and cloth** (`leather_shade.png`, `weave_shade.png`): the high-pass detail (taken with the scan wrapped
  round, so it tiles without a seam) turned into white where lighter and black where darker, with the difference as
  alpha. Leather is from Leather White, the woven cloth from Terlenka.
- **Velvet** (`velvet_shade.png`): made by the script from noise (soft sheen brushed along the nap over a faint
  pile), not from a scan, so it has no outside source.

The table below describes the mockup's copies (the mockup still has the first velvet, from the Velour Velvet scan).

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

The mockup loads these from Google Fonts. The game bundles them in `client/assets/fonts/`, as static instances with
overlapping outlines merged (as Cinzel was, see `docs/tables.md`), each with its OFL text alongside:
`Cinzel-OFL.txt`, `OFL-CormorantSC.txt`, `OFL-JosefinSans.txt` and `OFL-Montserrat.txt`.

The game's copies came from the Google Fonts repository (`github.com/google/fonts`, `ofl/`) on 2026-10-21:
- **Cormorant SC:** `CormorantSC-Bold.ttf`, overlaps removed.
- **Josefin Sans:** `JosefinSans[wght].ttf`, instanced at weight 600 with `--remove-overlaps`.
- **Montserrat:** `Montserrat[wght].ttf`, instanced at weight 600 with `--remove-overlaps`.

The admin designer serves copies of the game's files, plus DejaVu Sans Bold (already in the game, with
`DejaVu-LICENSE.txt`).

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
