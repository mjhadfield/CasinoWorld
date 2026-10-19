"""Local picker for the Star Trek slot art: cycle through each symbol's variants, choose one, mark it for the
final set or for another round of variations. Choices save to docs/slots/startrek/selections.json, which
startrek_reiterate.py reads. New variants on disk show up on reload; nothing needs rebuilding.
usage: python docs/slots/tools/startrek_picker.py [port]   → http://127.0.0.1:8792/"""
import json, re, sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent / "startrek"
SELECTIONS = ROOT / "selections.json"
sys.path.insert(0, str(TOOLS))
from startrek_gen import CHARS
from startrek_frame import HUES, DEFAULT_HUE

GROUPS = [
    ("Characters", ["kirk", "spock", "worf", "picard", "data", "troi", "obrien"]),
    ("Ships & places", ["enterprise", "enterprise_d", "ds9", "borg_cube", "bird_of_prey", "warbird",
                        "earth", "red_planet", "gas_giant", "nebula"]),
    ("Insignia & kit", ["delta", "delta_gold", "red_delta", "communicator", "tricorder", "phaser", "mug"]),
    ("Specials", ["wild", "scatter"]),
    ("Royals", ["A", "K", "Q", "J", "10"]),
]
# Round 1 (sheet 1): Mike's favourite of the three, kept alongside everything newer. Spock had none.
FAVOURITES = {"delta": 2, "enterprise": 1, "kirk": 1, "worf": 1, "earth": 1, "red_planet": 1, "nebula": 1,
              "communicator": 1, "phaser": 1, "wild": 1, "scatter": 1, "red_delta": 1, "mug": 1, "ds9": 1,
              "A": 1, "K": 1, "Q": 1, "J": 1, "10": 1}
ROUND1 = set(FAVOURITES) | {"spock"}  # their unpicked round-1 variants (1-3) are left out

def numbered(folder, prefix):
    """{n: path} for folder/<prefix>_<n>.png (exact prefix, so delta doesn't pick up delta_gold)."""
    out = {}
    for p in (ROOT / folder).glob(f"{prefix}_*.png"):
        m = re.fullmatch(re.escape(prefix) + r"_(\d+)", p.stem)
        if m:
            out[int(m.group(1))] = p
    return dict(sorted(out.items()))

def manifest():
    groups = []
    for title, names in GROUPS:
        symbols = []
        for name in names:
            variants = []
            if name in FAVOURITES:
                n = FAVOURITES[name]
                variants.append({"id": f"cut/{name}_{n}.png", "label": f"Favourite ({n})", "fav": True,
                                 "src": f"cut/{name}_{n}.png"})
            for n, p in numbered("cut", name).items():
                if name in ROUND1 and n <= 3:
                    continue
                variants.append({"id": f"cut/{p.name}", "label": f"Take {n}", "src": f"cut/{p.name}"})
            if name in CHARS:
                for n in numbered("raw", f"bust_{name}"):
                    files = {h: f"chars/{name}_{n}_{h}.png" for h in HUES if (ROOT / f"chars/{name}_{n}_{h}.png").exists()}
                    if files:
                        variants.append({"id": f"chars/{name}_{n}", "label": f"Framed {n}", "hues": files})
            ref = CHARS.get(name, name)
            symbols.append({"name": name, "ref": f"ref/{ref}.png", "variants": variants,
                            "defaultHue": DEFAULT_HUE.get(name, "gold")})
        groups.append({"title": title, "symbols": symbols})
    return {"groups": groups, "hues": list(HUES)}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = (TOOLS / "startrek_picker.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/manifest":
            self._json(manifest())
        elif self.path == "/api/selections":
            self._json(json.loads(SELECTIONS.read_text()) if SELECTIONS.exists() else {})
        elif self.path.split("?")[0].split("/")[1] in ("ref", "cut", "chars"):
            super().do_GET()
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path != "/api/selections":
            return self.send_error(404)
        n = int(self.headers.get("Content-Length", 0))
        if n > 1_000_000:
            return self.send_error(413)
        try:
            data = json.loads(self.rfile.read(n))
            assert isinstance(data, dict)
        except Exception:
            return self.send_error(400)
        tmp = SELECTIONS.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
        tmp.replace(SELECTIONS)
        self._json({"ok": True})

    def end_headers(self):
        if self.path.split("?")[0].endswith(".png"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8792
    print(f"http://127.0.0.1:{port}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
