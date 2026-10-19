"""Contact sheet of an art folder: python contact.py <dir> <out.png> [ext]"""
import sys, pathlib
from playwright.sync_api import sync_playwright
d = pathlib.Path(sys.argv[1]).resolve(); out = sys.argv[2]; ext = sys.argv[3] if len(sys.argv) > 3 else "svg"
files = sorted(d.glob(f"*.{ext}"))
cells = "".join(f'<figure><img src="{f.as_uri()}"><figcaption>{f.stem}</figcaption></figure>' for f in files)
html = f"""<html><body style="margin:0;background:#3a2414;font:14px sans-serif;color:#f1e4c4">
<div style="display:grid;grid-template-columns:repeat(7,180px);gap:10px;padding:12px">{cells}</div>
<style>figure{{margin:0;background:#5a3820;border-radius:8px;text-align:center}}img{{width:170px;height:170px}}</style></body></html>"""
p = pathlib.Path(out).resolve().with_suffix(".html"); p.write_text(html)
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1350, "height": 900})
    pg.goto(p.as_uri()); pg.wait_for_timeout(500); pg.screenshot(path=out, full_page=True); b.close()
print(out)
