"""
Slot art: renders a variant's vector set (docs/slots/mockup/art/svg, from docs/slots/tools/gen_svg.py)
to 512x512 PNGs with Chromium (so the SVG filters and glows survive, which Godot's SVG import
drops), and lays out the art library the admin page's Slots > Art tab offers:

  client/assets/slots/<variant>/<id>.png            the built-in set (the vector one, signed off)
  server/slot_art/<variant>/vector/<id>.png         the candidates: vector...
  server/slot_art/<variant>/flux1|flux2/<id>.png    ...and the two FLUX.2-klein sets

Run with a Python that has Playwright (the HomeDashboard venv):
  ~/Projects/HomeDashboard/.venv/bin/python tools/build_slot_art.py [variant]
"""
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
VARIANT = sys.argv[1] if len(sys.argv) > 1 else "armadillo"
SRC = ROOT / "docs" / "slots" / "mockup" / "art"
CLIENT = ROOT / "client" / "assets" / "slots" / VARIANT
LIBRARY = ROOT / "server" / "slot_art" / VARIANT
SIZE = 512


def render_vectors():
    svgs = sorted((SRC / "svg").glob("*.svg"))
    CLIENT.mkdir(parents=True, exist_ok=True)
    (LIBRARY / "vector").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": SIZE, "height": SIZE})
        for svg in svgs:
            page.goto(svg.as_uri())     # the SVG itself (512x512), so nothing else is drawn
            out = CLIENT / f"{svg.stem}.png"
            page.screenshot(path=str(out), omit_background=True, clip={"x": 0, "y": 0, "width": SIZE, "height": SIZE})
            shutil.copy(out, LIBRARY / "vector" / out.name)
            print("vector", svg.stem)
        browser.close()


# The logo: lettering, not a picture (FLUX can't spell). Drawn 4x the size it's shown at
# (296x100 in the game's 1280x720 screen) so it stays sharp on big windows.
LOGOS = {"armadillo": ("ARMADILLO", "GOES WEST")}
LOGO_SIZE = (1184, 400)


def render_logo():
    line1, line2 = LOGOS[VARIANT]
    font = (ROOT / "client" / "assets" / "fonts" / "Rye-Regular.ttf").as_uri()
    w, h = LOGO_SIZE
    def line(text, y, size):
        common = f'x="{w / 2}" y="{y}" font-size="{size}" text-anchor="middle" font-family="Rye"'
        return (f'<text {common} fill="#1a0802" stroke="#1a0802" stroke-width="{size * 0.2}" stroke-linejoin="round" transform="translate(0 9)">{text}</text>'
                f'<text {common} fill="#2b1004" stroke="#2b1004" stroke-width="{size * 0.17}" stroke-linejoin="round">{text}</text>'
                f'<text {common} fill="none" stroke="#fff1b0" stroke-width="{size * 0.05}" stroke-linejoin="round">{text}</text>'
                f'<text {common} fill="url(#gold)">{text}</text>')
    html = f"""<html><head><style>
@font-face {{ font-family: Rye; src: url('{font}'); }}
html, body {{ margin: 0; background: transparent; }}
</style></head><body>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs><linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff8d2"/><stop offset="0.35" stop-color="#ffd970"/>
    <stop offset="0.6" stop-color="#eba832"/><stop offset="1" stop-color="#9a5a14"/></linearGradient></defs>
  {line(line1, 186, 160)}
  {line(line2, 346, 128)}
</svg></body></html>"""
    page_file = CLIENT / ".logo.html"
    page_file.write_text(html)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto(page_file.as_uri())
        page.wait_for_function("document.fonts.status === 'loaded'")
        page.wait_for_timeout(300)
        out = CLIENT / "logo.png"
        page.screenshot(path=str(out), omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
        browser.close()
    page_file.unlink()
    (LIBRARY / "vector").mkdir(parents=True, exist_ok=True)
    shutil.copy(out, LIBRARY / "vector" / "logo.png")
    print("logo", out)


def copy_flux():
    for n in (1, 2):
        dest = LIBRARY / f"flux{n}"
        dest.mkdir(parents=True, exist_ok=True)
        for png in sorted((SRC / "flux").glob(f"*_{n}.png")):
            if png.stem.startswith("logo"):
                continue     # FLUX can't spell ARMADILLO: the logo is lettering
            shutil.copy(png, dest / f"{png.stem.rsplit('_', 1)[0]}.png")
        print(f"flux{n}", len(list(dest.glob("*.png"))))


if __name__ == "__main__":
    if sys.argv[2:3] == ["logo"]:
        render_logo()
    else:
        render_vectors()
        render_logo()
        copy_flux()
