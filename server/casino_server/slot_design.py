"""
The admin page's Slot design tab: a wizard that builds a slot machine, one design per folder, in steps (STEPS):
Concept, Art, Value ladder, Scene, Features, Bonus games, Sprites, Sounds, Maths & payouts, Mockup & sign-off
and Build. Star Trek is the first design; New design starts another from TEMPLATE.

A design is a folder under server/slot_designs/<id>/ (CASINO_DESIGNS_DIR moves it, for tests and the dev
instance):
  design.json      the design: concept, step statuses, categories (with how many symbols the main game needs),
                   symbols and their choices, jobs, and each later step's settings
  source/          reference sheets (uploaded on the Concept step, where the sheet cutter cuts them up)
  ref/             one reference crop per symbol
  links/           reference images linked on the page (uploaded or fetched from a URL)
  raw/             what FLUX returned, before keying: <id>_<n>.png (objects), bust_<id>_<n>.png (characters)
  cut/             objects, keyed and fitted to 512²: <id>_<n>.png
  chars/           characters in the shared frame, one per frame colour: <id>_<n>_<hue>.png
A symbol's variants are found from those files, so anything added by hand shows up too; binned ones (the Art
step's Bin) are hidden until restored, and nothing is ever deleted.

The live server keeps each design in memory and saves over design.json, so changes to the format are
migrations in Design._migrate (applied when the server loads a design), never hand edits.

Generate queues a job per symbol marked Reiterate or newly added; one background task (run(), on
app.state for the server's lifespan) works through them with FLUX in Odysseus (slot_design_art.py).
Jobs live in design.json, so a restart carries on where it stopped. Cancelling a running job throws away
the picture FLUX is drawing and stops there.

A symbol not in use (not in the final set, on the ladder or followed by an art slot) can be hidden from
the Art board ("hide"); nothing about it changes otherwise.
"""
import asyncio
import hashlib
import io
import json
import re
import threading
import time
import urllib.request
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from casino_server import slot_design_art as art
from casino_server.slot_design_build import BuildMixin
from casino_server.slot_design_steps import (DesignError, StepsMixin, art_view, bonuses_view, features_view, ladder_view,
                                             maths_view, scene_view, signoff_view, sounds_view, sprites_view)

DEFAULT_DESIGNS_DIR = Path(__file__).resolve().parents[1] / "slot_designs"
SERVED = ("source", "ref", "links", "cut", "chars", "scene", "adj")   # adj: art slots with their adjustments baked in
MAX_IMAGE = 12 * 1024 * 1024
TAKES = 3  # images per job (a Reiterate can ask for 1, 3 or 5)
TAKE_CHOICES = (1, 3, 5)
KINDS = ("object", "character")
KEYS = ("magenta", "green")
STEPS = [("concept", "Concept"), ("art", "Art"), ("ladder", "Value ladder"), ("scene", "Scene"),
         ("features", "Features"), ("bonuses", "Bonus games"), ("sprites", "Sprites"), ("sounds", "Sounds"),
         ("maths", "Maths & payouts"), ("mockup", "Mockup & sign-off"), ("build", "Build")]
STATUSES = ("todo", "doing", "done")
ACTIVE = ("queued", "waiting", "running", "failed")  # a job not yet done
VOLATILITY = ("low", "medium", "high")
# The house standard (Armadillo Goes West): 2 high pays, 4 mid, 4 low, a Wild and two scatters.
TIER_SHAPE = {"high": 2, "mid": 4, "low": 4}
TIER_LIMITS = {"high": (1, 6), "mid": (1, 8), "low": (2, 8)}
ROLE_TITLES = {"low": "Royals", "high": "Symbol set 1 · high pays", "mid": "Symbol set 2 · mid pays",
               "specials": "Specials · wild & scatters", None: "Bonus screens"}
ROYALS = ["A", "K", "Q", "J", "10", "9", "8", "7"]
SPECIALS = [("wild", "Wild", "word WILD", "the WILD symbol: the word WILD on an emblem of the theme"),
            ("bonus_scatter", "Bonus scatter", "word BONUS", "the bonus scatter symbol: the word BONUS on a badge of the theme"),
            ("free_spins", "Free-spins scatter", "words FREE SPINS", "the free-spins scatter symbol: the words FREE SPINS on a badge of the theme")]


def _template(name: str, brief: str) -> dict:
    """A new design: the house standard's categories, and starter royals and specials waiting for Generate."""
    cats = [{"id": cid, "title": ROLE_TITLES[role], "role": role, "kind": kind,
             "required": TIER_SHAPE[role] if role in TIER_SHAPE else 3 if role == "specials" else None}
            for cid, role, kind in (("royals", "low", "object"), ("set1", "high", "character"), ("set2", "mid", "object"),
                                    ("specials", "specials", "object"), ("bonus", None, "object"))]
    symbols = [{"id": _slug(r), "name": r, "category": "royals", "kind": "object", "key": "magenta",
                "keep_text": f"{'number' if r.isdigit() else 'letter'} {r}", "refs": [], "added": True,
                "pending_new": True, "hue": "gold",
                "prompt": f"the {'number' if r.isdigit() else 'letter'} {r} as a royal (card rank) symbol"}
               for r in ROYALS[:TIER_SHAPE["low"]]]
    symbols += [{"id": sid, "name": nm, "category": "specials", "kind": "object", "key": "magenta", "keep_text": keep,
                 "refs": [], "added": True, "pending_new": True, "hue": "gold", "prompt": prompt}
                for sid, nm, keep, prompt in SPECIALS]
    return {"name": name, "concept": {"brief": brief}, "categories": cats, "symbols": symbols, "jobs": []}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def _numbered(folder: Path, prefix: str) -> dict[int, Path]:
    """{n: path} for folder/<prefix>_<n>.png (an exact prefix, so delta doesn't pick up delta_gold)."""
    out = {}
    if folder.is_dir():
        for p in folder.glob(f"{prefix}_*.png"):
            if m := re.fullmatch(re.escape(prefix) + r"_(\d+)", p.stem):
                out[int(m.group(1))] = p
    return dict(sorted(out.items()))


class Design:
    def __init__(self, folder: Path):
        self.folder = folder
        self.id = folder.name
        self.data = json.loads((folder / "design.json").read_text())
        before = json.dumps(self.data, sort_keys=True)
        self._migrate()
        for job in self.data["jobs"]:
            if job["status"] in ("running", "waiting"):
                job["status"] = "queued"  # the server stopped mid-job: carry on
        if json.dumps(self.data, sort_keys=True) != before:
            self.save()

    def _migrate(self):
        """Bring an older design.json up to date (see the module docstring)."""
        d = self.data
        d.setdefault("jobs", [])
        roles = {"royals": "low", "set1": "high", "set2": "mid", "specials": "specials"}
        for c in d.setdefault("categories", []):
            c.setdefault("role", roles.get(c["id"]))
        req = {c["role"]: c.get("required") for c in d["categories"] if c.get("role") in TIER_SHAPE}
        concept = d.setdefault("concept", {})
        concept.setdefault("brief", "")
        concept.setdefault("style", "")
        concept.setdefault("tiers", {k: req.get(k) or v for k, v in TIER_SHAPE.items()})
        concept.setdefault("target_rtp", 91.5)
        concept.setdefault("volatility", "medium")
        steps = d.setdefault("steps", {})
        for sid, _ in STEPS:
            steps.setdefault(sid, "doing" if sid == "art" and d.get("symbols") else "todo")
        for s in d.setdefault("symbols", []):
            if "hidden" in s:  # round 1's unpicked takes: into the Bin, where they can be restored
                s["binned"] = list(dict.fromkeys(s.get("binned", []) + s.pop("hidden")))
        # A design with its own colours takes none of Armadillo's: the shades it never picked (outlines, highlight,
        # text, and the shade and accent shadow added later) are worked out from its edge and accent colours.
        cols = d.get("sprites", {}).get("colours")
        if cols:
            rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
            hexc = lambda c: "#" + "".join(f"{round(v):02x}" for v in c)
            dark = lambda h, t: hexc(v * (1 - t) for v in rgb(h))
            light = lambda h, t: hexc(v + (255 - v) * t for v in rgb(h))
            edge, gold = cols.get("edge", "#d9a54a"), cols.get("gold", "#f4c94f")
            for k, v in (("shade", dark(edge, 0.88)), ("goldLo", dark(gold, 0.4)), ("ink", dark(edge, 0.82)),
                         ("goldHi", light(gold, 0.75)), ("cream", light(edge, 0.88))):
                cols.setdefault(k, v)

    def save(self):
        tmp = self.folder / "design.json.tmp"
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.folder / "design.json")

    def symbol(self, sid: str) -> dict:
        for s in self.data["symbols"]:
            if s["id"] == sid:
                return s
        raise DesignError(f"There's no symbol {sid!r}.")

    def category_ids(self) -> list[str]:
        return [c["id"] for c in self.data["categories"]]

    def path(self, rel, folders=SERVED) -> Path | None:
        """A board image by its relative path, or None -- never anything outside the given folders."""
        if not isinstance(rel, str) or "\\" in rel or rel.startswith("/") or rel.split("/")[0] not in folders:
            return None
        path = (self.folder / rel).resolve()
        if not path.is_relative_to(self.folder.resolve()) or not path.is_file() or path.suffix.lower() != ".png":
            return None
        return path

    # ------------------------------------------------------------- variants
    def all_variants(self, s: dict) -> list[dict]:
        """Every variant on disk, binned or not, with any label a Refine or Fit gave it."""
        sid, out = s["id"], []
        fav = s.get("favourite")
        if fav and self.path(fav):
            out.append({"id": fav, "label": "Favourite", "fav": True, "src": fav})
        for n, p in _numbered(self.folder / "cut", sid).items():
            if f"cut/{p.name}" != fav:
                out.append({"id": f"cut/{p.name}", "label": f"Take {n}", "src": f"cut/{p.name}"})
        for n in _numbered(self.folder / "raw", f"bust_{sid}"):
            hues = {h: f"chars/{sid}_{n}_{h}.png" for h in art.HUES if (self.folder / f"chars/{sid}_{n}_{h}.png").exists()}
            if hues:
                out.append({"id": f"bust/{sid}_{n}", "label": f"Framed {n}", "hues": hues})
        labels = s.get("labels", {})
        for v in out:
            v["label"] = labels.get(v["id"], v["label"])
        return out

    def variants(self, s: dict) -> list[dict]:
        binned = set(s.get("binned", []))
        return [v for v in self.all_variants(s) if v["id"] not in binned]

    def binned(self, s: dict) -> list[dict]:
        binned = set(s.get("binned", []))
        return [v for v in self.all_variants(s) if v["id"] in binned]

    def variant(self, s: dict, vid: str) -> dict:
        v = next((v for v in self.all_variants(s) if v["id"] == vid), None)
        if not v:
            raise DesignError(f"{vid!r} isn't one of {s['id']}'s variants.")
        return v

    def raw_of(self, s: dict, vid: str) -> tuple[str, dict]:
        """The picture a variant was made from (relative path) and the Fit it was made with: a Fit or Refine
        starts from there, not from the finished tile."""
        fit = s.get("fits", {}).get(vid)
        if fit:
            return fit["src"], fit["fit"]
        if vid.startswith("bust/"):
            return f"raw/bust_{vid.split('/', 1)[1]}.png", {}
        raw = "raw/" + Path(vid).name
        return (raw if (self.folder / raw).is_file() else vid), {}

    def chosen(self, s: dict) -> dict | None:
        vs = self.variants(s)
        return next((v for v in vs if v["id"] == s.get("choice")), vs[0] if vs else None)

    def chosen_file(self, s: dict) -> str | None:
        v = self.chosen(s)
        if not v:
            return None
        return v["hues"].get(s.get("hue"), next(iter(v["hues"].values()))) if "hues" in v else v["src"]

    def adjusted(self, key: str, rel: str, a: dict) -> str:
        """An art slot's picture with its adjustments baked in (adj/<key>_<hash>.png, made once and replacing the
        slot's last one), or the picture itself when there are none."""
        a = art.adjust_values(a)
        p = self.path(rel)
        if a == art.ADJUST or not p:
            return rel
        tag = hashlib.sha1(json.dumps([rel, p.stat().st_mtime_ns, a], sort_keys=True).encode()).hexdigest()[:10]
        folder, name = self.folder / "adj", f"{key}_{tag}.png"
        if not (folder / name).is_file():
            folder.mkdir(exist_ok=True)
            self.clear_adjusted(key)
            tmp = folder / f".{name}"
            art.adjust(Image.open(p), a).save(tmp, "PNG")
            tmp.replace(folder / name)
        return f"adj/{name}"

    def clear_adjusted(self, key: str) -> None:
        """Remove an art slot's baked picture (adj/<key>_<hash>.png)."""
        for old in (self.folder / "adj").glob(f"{key}_*.png"):
            if re.fullmatch(rf"{re.escape(key)}_[0-9a-f]{{10}}\.png", old.name):
                old.unlink()

    def next_n(self, prefix: str) -> int:
        ns = list(_numbered(self.folder / "raw", prefix)) + list(_numbered(self.folder / "cut", prefix))
        return max(ns, default=0) + 1


class DesignBoard(StepsMixin, BuildMixin):
    def __init__(self, root: Path = DEFAULT_DESIGNS_DIR):
        self.root = root
        self.lock = threading.RLock()
        self.designs = {}
        if root.is_dir():
            for f in sorted(root.iterdir()):
                if (f / "design.json").is_file():
                    self.designs[f.name] = Design(f)
        self._flux = (0.0, False)

    def design(self, did: str) -> Design:
        if did not in self.designs:
            raise DesignError(f"There's no design called {did!r}.")
        return self.designs[did]

    def flux_ready(self, fresh: bool = False) -> bool:
        """Cached for 15 s: the page polls while jobs run."""
        at, ready = self._flux
        if fresh or time.monotonic() - at > 15:
            ready = art.flux_ready()
            self._flux = (time.monotonic(), ready)
        return ready

    # ------------------------------------------------------------- reading
    def listing(self) -> list[dict]:
        return [{"id": d.id, "name": d.data.get("name", d.id)} for d in self.designs.values()]

    def overview(self, did: str) -> dict:
        with self.lock:
            d = self.design(did)
            jobs = d.data["jobs"]
            used = _in_use(d)
            symbols = []
            for s in d.data["symbols"]:
                active = [j for j in jobs if j["symbol"] == s["id"] and j["status"] in ("queued", "waiting", "running", "failed")]
                v = d.chosen(s)
                symbols.append({
                    **{k: s.get(k) for k in ("id", "name", "category", "kind", "key", "keep_text", "prompt", "hue", "note", "base")},
                    "keep": bool(s.get("keep")), "reiterate": bool(s.get("reiterate")), "added": bool(s.get("added")),
                    "takes": s.get("takes", TAKES), "hide": bool(s.get("hide")), "in_use": s["id"] in used,
                    "pending_new": bool(s.get("pending_new")), "refs": s.get("refs", []),
                    "variants": d.variants(s), "binned": d.binned(s), "fits": s.get("fits", {}),
                    "choice": v["id"] if v else None, "file": d.chosen_file(s),
                    "job": active[-1] if active else None})
            categories = []
            for c in d.data["categories"]:
                mine = [s for s in d.data["symbols"] if s["category"] == c["id"]]
                categories.append({**c, "count": len(mine), "in_set": sum(bool(s.get("keep")) for s in mine),
                                   "hidden": sum(bool(s.get("hide")) for s in mine)})
            running = next((j for j in jobs if j["status"] in ("running", "waiting")), None)
            sources = sorted(f"source/{p.name}" for p in (d.folder / "source").glob("*.png")) \
                if (d.folder / "source").is_dir() else []
            return {"id": d.id, "name": d.data.get("name", d.id), "note": d.data.get("note", ""),
                    "concept": d.data["concept"], "sources": sources, "signed_off": d.data.get("signed_off"),
                    "ladder": ladder_view(d), "scene": scene_view(d), "features": features_view(d),
                    "bonuses": bonuses_view(d), "art": art_view(d), "sprites": sprites_view(d),
                    "sounds": sounds_view(d, self.sounds), "maths": maths_view(d), "signoff": signoff_view(d),
                    "build": self.build_view(d),
                    "scene_jobs": [j for j in jobs if j["symbol"] is None and j["status"] in ("queued", "waiting", "running", "failed")],
                    "steps": [{"id": k, "title": t, "status": d.data["steps"].get(k, "todo")} for k, t in STEPS],
                    "categories": categories, "symbols": symbols, "hues": list(art.HUES),
                    "pending": sum(bool(s.get("reiterate") or s.get("pending_new")) for s in d.data["symbols"]),
                    "queued": sum(j["status"] == "queued" for j in jobs), "running": running,
                    "art_jobs": sum(j["symbol"] is not None and j["status"] in ACTIVE for j in jobs)}

    def status(self, did: str) -> dict:
        with self.lock:
            jobs = self.design(did).data["jobs"]
            busy = any(j["status"] in ("queued", "waiting", "running") for j in jobs)
        return {"flux": self.flux_ready(), "busy": busy}

    # ------------------------------------------------------------- changing
    def update_symbol(self, did: str, sid: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
            for k, v in ch.items():
                if k == "choice":
                    if v not in [x["id"] for x in d.variants(s)]:
                        raise DesignError(f"{v!r} isn't one of {sid}'s variants.")
                    s["choice"] = v
                elif k == "hue":
                    if v not in art.HUES:
                        raise DesignError(f"There's no {v!r} frame.")
                    s["hue"] = v
                elif k in ("keep", "reiterate"):
                    s[k] = bool(v)
                    if k == "keep" and v:
                        s.pop("hide", None)  # in the set means in use
                elif k == "takes":
                    if v not in TAKE_CHOICES:
                        raise DesignError("A Reiterate makes 1, 3 or 5 takes.")
                    s["takes"] = v
                elif k == "hide":
                    if v and s["id"] in _in_use(d):
                        raise DesignError(f"{s['name']} is in use: take it out of the final set, the ladder and any art slot first.")
                    if v:
                        s["hide"] = True
                    else:
                        s.pop("hide", None)
                elif k in ("note", "prompt", "keep_text"):
                    s[k] = str(v or "").strip()[:500]
                elif k == "name":
                    if not str(v).strip():
                        raise DesignError("A symbol needs a name.")
                    s["name"] = str(v).strip()[:40]
                elif k == "category":
                    if v not in d.category_ids():
                        raise DesignError(f"There's no category {v!r}.")
                    s["category"] = v
                elif k == "key":
                    if v not in KEYS:
                        raise DesignError("The background key is magenta or green.")
                    s["key"] = v
                elif k == "base":
                    if v and v not in s.get("refs", []):
                        raise DesignError("Reiterate can only start from the chosen image or a linked reference.")
                    s["base"] = v or None
                elif k == "add_ref":
                    if not d.path(v):
                        raise DesignError(f"Not on the board: {v}")
                    if v not in s.setdefault("refs", []):
                        s["refs"].append(v)
                elif k == "remove_ref":
                    s["refs"] = [r for r in s.get("refs", []) if r != v]
                    if s.get("base") == v:
                        s["base"] = None
                else:
                    raise DesignError(f"Can't change {k!r}.")
            d.save()

    def add_symbol(self, did: str, body: dict) -> str:
        with self.lock:
            d = self.design(did)
            name = str(body.get("name") or "").strip()[:40]
            category, kind = body.get("category"), body.get("kind", "object")
            prompt, ref = str(body.get("prompt") or "").strip()[:500], body.get("ref")
            if not name:
                raise DesignError("Give the new symbol a name.")
            if category not in d.category_ids():
                raise DesignError(f"There's no category {category!r}.")
            if kind not in KINDS:
                raise DesignError("A symbol is an object or a character.")
            if ref and not d.path(ref):
                raise DesignError(f"Not on the board: {ref}")
            if not prompt and not ref:
                raise DesignError("Describe the new symbol, or link a reference image for it (or both).")
            sid = self._new_id(d, name)
            d.data["symbols"].append({"id": sid, "name": name, "category": category, "kind": kind,
                                      "key": body.get("key") if body.get("key") in KEYS else "magenta",
                                      "prompt": prompt, "refs": [ref] if ref else [], "added": True, "pending_new": True,
                                      "hue": "gold"})
            d.save()
            return sid

    def delete_symbol(self, did: str, sid: str) -> None:
        """Only symbols added on the page; their images stay in the folder."""
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
            if not s.get("added"):
                raise DesignError("Only symbols added on this page can be removed.")
            d.data["symbols"].remove(s)
            d.data["jobs"] = [j for j in d.data["jobs"] if not (j["symbol"] == sid and j["status"] in ("queued", "failed"))]
            d.save()

    def hide_unused(self, did: str) -> int:
        """Hide every symbol that isn't in use and has nothing in hand (no Reiterate mark, no job). Returns how many."""
        with self.lock:
            d = self.design(did)
            used = _in_use(d)
            busy = {j["symbol"] for j in d.data["jobs"] if j["status"] in ACTIVE}
            n = 0
            for s in d.data["symbols"]:
                if not (s.get("hide") or s["id"] in used or s["id"] in busy or s.get("reiterate") or s.get("pending_new")):
                    s["hide"] = True
                    n += 1
            d.save()
            return n

    def update_category(self, did: str, cid: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            c = next((c for c in d.data["categories"] if c["id"] == cid), None)
            if not c:
                raise DesignError(f"There's no category {cid!r}.")
            if "required" in ch:
                r = ch["required"]
                if r is not None and (not isinstance(r, int) or not 0 <= r <= 30):
                    raise DesignError("How many are needed is a whole number from 0 to 30.")
                c["required"] = r
            if "title" in ch and str(ch["title"]).strip():
                c["title"] = str(ch["title"]).strip()[:60]
            d.save()

    # ------------------------------------------------------------- linking reference images
    def link_image(self, did: str, filename: str, data: bytes) -> str:
        """Store an uploaded (or fetched) image under links/, fitted within 1024²."""
        d = self.design(did)
        im = self._read_image(data)
        im.thumbnail((1024, 1024), Image.LANCZOS)
        with self.lock:
            return self._save_unique(im, d.folder / "links", _slug(Path(filename).stem) or "image", "links")

    def link_url(self, did: str, url: str) -> str:
        if not re.match(r"https?://", url or ""):
            raise DesignError("Paste a web address starting http:// or https://.")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CasinoWorld-SlotDesign/1"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read(MAX_IMAGE + 1)
        except Exception as e:
            raise DesignError(f"Couldn't fetch that address: {e}")
        name = Path(url.split("?")[0].rstrip("/")).name or "web-image"
        return self.link_image(did, name, data)

    # ------------------------------------------------------------- designs, Concept and step statuses
    def create_design(self, name: str, brief: str = "") -> str:
        name = str(name or "").strip()[:40]
        if not name:
            raise DesignError("Give the new slot a name.")
        with self.lock:
            did, i = _slug(name) or "slot", 1
            base = did
            while did in self.designs or (self.root / did).exists():
                i += 1
                did = f"{base}_{i}"
            folder = self.root / did
            for sub in ("source", "ref", "links", "raw", "cut", "chars"):
                (folder / sub).mkdir(parents=True)
            (folder / "design.json").write_text(json.dumps(_template(name, str(brief or "").strip()[:600]), indent=1))
            self.designs[did] = Design(folder)
            return did

    def update_concept(self, did: str, ch: dict) -> None:
        with self.lock:
            d = self.design(did)
            c = d.data["concept"]
            for k, v in ch.items():
                if k == "name":
                    if not str(v).strip():
                        raise DesignError("The slot needs a name.")
                    d.data["name"] = str(v).strip()[:40]
                elif k in ("brief", "style"):
                    c[k] = str(v or "").strip()[:600]
                elif k == "target_rtp":
                    if not isinstance(v, (int, float)) or not 85 <= v <= 98:
                        raise DesignError("The target return is a percentage from 85 to 98.")
                    c[k] = round(float(v), 2)
                elif k == "volatility":
                    if v not in VOLATILITY:
                        raise DesignError("Volatility is low, medium or high.")
                    c[k] = v
                elif k == "tiers":
                    if not isinstance(v, dict) or set(v) != set(TIER_SHAPE):
                        raise DesignError("The tier shape gives how many high, mid and low pays.")
                    for tier, n in v.items():
                        lo, hi = TIER_LIMITS[tier]
                        if not isinstance(n, int) or not lo <= n <= hi:
                            raise DesignError(f"{tier.title()} pays: a whole number from {lo} to {hi}.")
                    c["tiers"] = dict(v)
                    for cat in d.data["categories"]:  # the Art step's counts follow the shape
                        if cat.get("role") in v:
                            cat["required"] = v[cat["role"]]
                else:
                    raise DesignError(f"Can't change {k!r}.")
            d.save()

    def set_step(self, did: str, step: str, status: str) -> None:
        if step not in dict(STEPS) or status not in STATUSES:
            raise DesignError("A step is todo, doing or done.")
        with self.lock:
            d = self.design(did)
            d.data["steps"][step] = status
            d.save()

    def add_source(self, did: str, filename: str, data: bytes) -> str:
        """A reference sheet for the sheet cutter (kept up to 4096 px)."""
        im = self._read_image(data)
        im.thumbnail((4096, 4096), Image.LANCZOS)
        with self.lock:
            d = self.design(did)
            return self._save_unique(im, d.folder / "source", _slug(Path(filename).stem) or "sheet", "source")

    def cut_sheet(self, did: str, sheet: str, boxes: list) -> list[str]:
        """Cut boxes out of a sheet, each into a new symbol with its reference crop, waiting for Generate (which makes
        one take of it, the faithful redraw)."""
        with self.lock:
            d = self.design(did)
            path = d.path(sheet, ("source",))
            if not path:
                raise DesignError(f"There's no sheet {sheet!r}.")
            if not isinstance(boxes, list) or not boxes:
                raise DesignError("Draw at least one box on the sheet.")
            im = Image.open(path).convert("RGB")
            made = []
            for b in boxes:
                try:
                    x, y, w, h = (int(round(float(b[k]))) for k in ("x", "y", "w", "h"))
                except (KeyError, TypeError, ValueError):
                    raise DesignError("Each box needs x, y, w and h.")
                x, y = max(0, x), max(0, y)
                w, h = min(w, im.width - x), min(h, im.height - y)
                if w < 16 or h < 16:
                    raise DesignError("A box is too small (16 px at least).")
                name = str(b.get("name") or "").strip()[:40]
                if not name:
                    raise DesignError("Name every box.")
                category = b.get("category")
                if category not in d.category_ids():
                    raise DesignError(f"There's no category {category!r}.")
                kind = b.get("kind") or next(c.get("kind", "object") for c in d.data["categories"] if c["id"] == category)
                if kind not in KINDS:
                    raise DesignError("A symbol is an object or a character.")
                sid = self._new_id(d, name)
                (d.folder / "ref").mkdir(exist_ok=True)
                art.fit_square(im.crop((x, y, x + w, y + h)), 1024).save(d.folder / f"ref/{sid}.png")
                d.data["symbols"].append({"id": sid, "name": name, "category": category, "kind": kind,
                                          "key": b.get("key") if b.get("key") in KEYS else "magenta", "prompt": "",
                                          "refs": [f"ref/{sid}.png"], "added": True, "pending_new": True, "hue": "gold",
                                          "from_sheet": True})
                made.append(sid)
            d.save()
            return made

    def _new_id(self, d: Design, name: str) -> str:
        taken = {s["id"] for s in d.data["symbols"]}
        base = sid = _slug(name) or "symbol"
        i = 1
        while sid in taken:
            i += 1
            sid = f"{base}_{i}"
        return sid

    def _read_image(self, data: bytes) -> Image.Image:
        if not data:
            raise DesignError("That file is empty.")
        if len(data) > MAX_IMAGE:
            raise DesignError("That image is over 12 MB.")
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
        except (UnidentifiedImageError, OSError):
            raise DesignError("That isn't an image the server can read (use PNG, JPEG or WebP).")
        return im.convert("RGBA")

    def _save_unique(self, im, folder: Path, stem: str, prefix: str) -> str:
        folder.mkdir(exist_ok=True)
        n, name = 1, f"{stem}.png"
        while (folder / name).exists():
            n += 1
            name = f"{stem}_{n}.png"
        im.save(folder / name)
        return f"{prefix}/{name}"

    # ------------------------------------------------------------- Art: Bin, Refine and Fit
    def bin_variant(self, did: str, sid: str, vid: str) -> None:
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
            d.variant(s, vid)
            if vid not in s.setdefault("binned", []):
                s["binned"].append(vid)
            if s.get("choice") == vid:
                s.pop("choice")
            d.save()

    def restore_variant(self, did: str, sid: str, vid: str) -> None:
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
            if vid not in s.get("binned", []):
                raise DesignError(f"{vid!r} isn't in the Bin.")
            s["binned"].remove(vid)
            d.save()

    def split_variant(self, did: str, sid: str, vid: str, name: str | None = None) -> str:
        """Move a take out into a new symbol of its own, in the same section, with that take as its only one (copied
        as take 1; the original goes to the old symbol's Bin, so nothing is lost), named `name` or "<name> 2".
        Returns the new symbol's id."""
        import shutil
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
            v = d.variant(s, vid)
            names = {x["name"] for x in d.data["symbols"]}
            base = s["name"][:37]
            k = 2
            while f"{base} {k}" in names:
                k += 1
            name = str(name or "").strip()[:40] or f"{base} {k}"
            new = self._new_id(d, name)
            for sub in ("raw", "cut", "chars"):
                (d.folder / sub).mkdir(exist_ok=True)
            if "hues" in v:
                n = vid.split("/", 1)[1]
                shutil.copyfile(d.folder / f"raw/bust_{n}.png", d.folder / f"raw/bust_{new}_1.png")
                for hue, rel in v["hues"].items():
                    shutil.copyfile(d.folder / rel, d.folder / f"chars/{new}_1_{hue}.png")
                nvid = f"bust/{new}_1"
            else:
                shutil.copyfile(d.folder / v["src"], d.folder / f"cut/{new}_1.png")
                raw = d.folder / "raw" / Path(v["src"]).name
                if raw.is_file():
                    shutil.copyfile(raw, d.folder / f"raw/{new}_1.png")
                nvid = f"cut/{new}_1.png"
            sym = {"id": new, "name": name, "category": s["category"], "kind": "character" if "hues" in v else "object",
                   **{k: s[k] for k in ("key", "keep_text", "prompt", "hue") if k in s},
                   "refs": list(s.get("refs", [])), "added": True, "choice": nvid}
            fit = s.get("fits", {}).get(vid)
            if fit:  # a fitted take keeps refitting from the picture it was fitted from
                sym["fits"] = {nvid: dict(fit)}
            d.data["symbols"].insert(d.data["symbols"].index(s) + 1, sym)
            if vid not in s.setdefault("binned", []):
                s["binned"].append(vid)
            if s.get("choice") == vid:
                s.pop("choice")
            d.save()
            return new

    def refine(self, did: str, sid: str, vid: str, instruction: str) -> dict:
        """Queue one targeted FLUX edit of a variant: everything kept but what the instruction names."""
        instruction = str(instruction or "").strip()[:400]
        if not instruction:
            raise DesignError("Say what to change.")
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
            v = d.variant(s, vid)
            src, _ = d.raw_of(s, vid)
            if not d.path(src, SERVED + ("raw",)):
                raise DesignError("There's no picture behind that variant to refine.")
            job = self._queue(d, s, {"how": "refine", "src": src, "text": instruction, "action": "refine",
                                     "out": "character" if "hues" in v else "object",
                                     "label": f"{v['label']}, refined"}, count=1)
            d.save()
            return job

    def _fit_render(self, d: Design, s: dict, vid: str, fit: dict, hues=None):
        v = d.variant(s, vid)
        src, _ = d.raw_of(s, vid)
        path = d.path(src, SERVED + ("raw",))
        if not path:
            raise DesignError("There's no picture behind that variant to fit.")
        im = Image.open(path)
        if "hues" in v:
            return src, art.compose_character(im.convert("RGB"), fit, hues)
        return src, art.symbol(im if im.mode == "RGBA" else im.convert("RGB"), fit)

    def fit_preview(self, did: str, sid: str, vid: str, fit: dict, hue: str = "gold") -> bytes:
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
        _, out = self._fit_render(d, s, vid, fit, [hue if hue in art.HUES else "gold"])
        im = next(iter(out.values())) if isinstance(out, dict) else out
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()

    def fit_save(self, did: str, sid: str, vid: str, fit: dict) -> str:
        """A new variant: the same picture, refitted. A Fit of a Fit starts again from the original."""
        import shutil
        with self.lock:
            d = self.design(did)
            s = d.symbol(sid)
            label = d.variant(s, vid)["label"]
        f = art.fit_values(fit)
        src, out = self._fit_render(d, s, vid, f)
        with self.lock:
            character = isinstance(out, dict)
            prefix = f"bust_{sid}" if character else sid
            n = d.next_n(prefix)
            (d.folder / "raw").mkdir(exist_ok=True)
            if src.startswith("raw/"):
                shutil.copyfile(d.folder / src, d.folder / f"raw/{prefix}_{n}.png")
            if character:
                (d.folder / "chars").mkdir(exist_ok=True)
                for hue, im in out.items():
                    im.save(d.folder / f"chars/{sid}_{n}_{hue}.png", optimize=True)
                new = f"bust/{sid}_{n}"
            else:
                (d.folder / "cut").mkdir(exist_ok=True)
                out.save(d.folder / f"cut/{sid}_{n}.png", optimize=True)
                new = f"cut/{sid}_{n}.png"
            s.setdefault("fits", {})[new] = {"src": src, "fit": f}
            s.setdefault("labels", {})[new] = f"{label.split(', fitted')[0]}, fitted"
            s["choice"] = new
            d.save()
            return new

    # ------------------------------------------------------------- jobs
    def generate(self, did: str, sid: str | None = None) -> int:
        """Queue a job for every symbol marked Reiterate (its 1, 3 or 5 takes) or newly added (3), or just for `sid`
        (a card's Queue). Returns how many."""
        with self.lock:
            d = self.design(did)
            queued = 0
            for s in [d.symbol(sid)] if sid else d.data["symbols"]:
                count = TAKES
                if s.get("pending_new"):
                    ref = s["refs"][0] if s.get("refs") else None
                    job = {"how": "redraw" if ref else "text", "src": ref, "text": s.get("prompt", ""),
                           "out": s["kind"], "action": "new"}
                    s["pending_new"] = False
                    if s.get("from_sheet"):
                        count = 1  # a sheet cut: the faithful redraw only (style 1)
                elif s.get("reiterate"):
                    job = self._reiterate_job(d, s)
                    s["reiterate"] = False
                    s.setdefault("history", []).append({"from": job["src"], "note": job["text"]})
                    count = s.get("takes", TAKES)
                else:
                    continue
                self._queue(d, s, job, count)
                queued += 1
            d.save()
            return queued

    def _queue(self, d: Design, s: dict | None, job: dict, count: int = TAKES) -> dict:
        """Add a job (the caller saves): for a symbol, or for the Scene (s None). Keeps the last 50 finished."""
        jobs = d.data["jobs"]
        job = {"id": max((j["id"] for j in jobs), default=0) + 1, "symbol": s["id"] if s else None, "status": "queued",
               "done": 0, "count": count, "made": [], "error": "", **job}
        jobs.append(job)
        done = [j for j in jobs if j["status"] == "done"]
        if len(done) > 50:
            d.data["jobs"] = [j for j in jobs if j["status"] != "done" or j in done[-50:]]
        return job

    def _reiterate_job(self, d: Design, s: dict) -> dict:
        note = s.get("note", "")
        # Redrawing a reference or drawing from scratch goes by the symbol's description (a New symbol's) as well;
        # a variation of a take already has it.
        described = " ".join(x.strip().rstrip(".") + "." for x in (s.get("prompt", ""), note) if x.strip())
        if s.get("base"):  # a linked reference: redraw it as this symbol
            return {"how": "redraw", "src": s["base"], "text": described, "out": s["kind"], "action": "reiterate"}
        v = d.chosen(s)
        if not v:
            if s.get("refs"):
                return {"how": "redraw", "src": s["refs"][0], "text": described, "out": s["kind"], "action": "reiterate"}
            return {"how": "text", "src": None, "text": described, "out": s["kind"], "action": "reiterate"}
        src, _ = d.raw_of(s, v["id"])  # a framed character varies the bust it was made from
        return {"how": "variation", "src": src, "text": note, "out": "character" if "hues" in v else "object",
                "action": "reiterate"}

    def retry(self, did: str, job_id: int) -> None:
        with self.lock:
            d = self.design(did)
            job = next((j for j in d.data["jobs"] if j["id"] == job_id), None)
            if not job or job["status"] != "failed":
                raise DesignError("Only a failed job can be retried.")
            job.update(status="queued", error="")
            d.save()

    def cancel(self, did: str, job_id: int) -> None:
        with self.lock:
            d = self.design(did)
            job = next((j for j in d.data["jobs"] if j["id"] == job_id), None)
            if not job or job["status"] not in ACTIVE:
                raise DesignError("That job has already finished.")
            d.data["jobs"].remove(job)  # a running one: run() sees it's gone and stops
            d.save()

    def cancel_all(self, did: str) -> int:
        """Cancel every Art job not yet done (queued, waiting, running or failed); the Scene's are left alone."""
        with self.lock:
            d = self.design(did)
            jobs = d.data["jobs"]
            d.data["jobs"] = [j for j in jobs if j["symbol"] is None or j["status"] not in ACTIVE]
            d.save()
            return len(jobs) - len(d.data["jobs"])

    def _next_job(self):
        with self.lock:
            for d in self.designs.values():
                for j in d.data["jobs"]:
                    if j["status"] in ("queued", "waiting"):
                        return d, j
        return None

    def _set(self, d: Design, job: dict, **kw):
        with self.lock:
            job.update(kw)
            d.save()

    def make_one(self, d: Design, job: dict) -> str:
        """One FLUX picture for a job, keyed and saved; returns the raw file's name."""
        if job["out"] == "background":
            return self._make_background(d, job)
        with self.lock:
            s = d.symbol(job["symbol"])
            key, keep_text = s.get("key", "magenta"), s.get("keep_text")
            prefix = f"bust_{s['id']}" if job["out"] == "character" else s["id"]
            n = d.next_n(prefix)
            c = d.data["concept"]
            theme = "; ".join(x for x in (c.get("brief", ""), c.get("style", "")) if x.strip())
        i, text, how = job["done"] + 1, job.get("text", ""), job["how"]
        if how == "refine":
            prompt = art.refine_prompt(job["out"], key, text)
        elif job["out"] == "character":
            prompt = (art.bust_text_prompt(key, text) if how == "text" else
                      art.variation_prompt("character", key, text) if how == "variation" else art.bust_prompt(key, text))
        else:
            prompt = (art.object_text_prompt(i, key, text) if how == "text" else
                      art.variation_prompt("object", key, text) if how == "variation" else
                      art.object_prompt(i, key, keep_text, text))
        if how == "text":
            raw = art.flux_generate(art.themed(prompt, theme))
        else:
            src = d.path(job["src"], SERVED + ("raw",))
            if not src:
                raise art.FluxError(f"The reference {job['src']} has gone.")
            raw = art.flux_edit(Image.open(src), art.themed(prompt, theme))
        if job["out"] == "character":
            tiles = art.compose_character(raw)
        else:
            tile = art.symbol(raw)
        with self.lock:
            if not _live(d, job):
                raise Cancelled()
            for sub in ("raw", "cut", "chars"):
                (d.folder / sub).mkdir(exist_ok=True)
            n = max(n, d.next_n(prefix))  # in case a file appeared meanwhile
            raw.save(d.folder / f"raw/{prefix}_{n}.png")
            if job["out"] == "character":
                for hue, im in tiles.items():
                    im.save(d.folder / f"chars/{s['id']}_{n}_{hue}.png", optimize=True)
                vid = f"bust/{s['id']}_{n}"
            else:
                tile.save(d.folder / f"cut/{prefix}_{n}.png", optimize=True)
                vid = f"cut/{prefix}_{n}.png"
            if job.get("label"):
                s.setdefault("labels", {})[vid] = job["label"].replace("{n}", str(n))
        return f"{prefix}_{n}"

    def _make_background(self, d: Design, job: dict) -> str:
        with self.lock:
            c = d.data["concept"]
            theme = "; ".join(x for x in (c.get("brief", ""), c.get("style", "")) if x.strip())
        im = art.flux_generate(art.themed(art.background_prompt(job["text"]), theme), "1344x768")
        with self.lock:
            if not _live(d, job):
                raise Cancelled()
            out = self._next_scene(d, "bg")
            art.fit_cover(im, (1280, 720)).save(d.folder / out)
            d.data.setdefault("scene", {}).setdefault("background", out)
        return Path(out).stem

    async def run(self):
        """The worker: one job at a time, one picture at a time. Waits while FLUX is off."""
        while True:
            nxt = self._next_job()
            if not nxt:
                await asyncio.sleep(2)
                continue
            d, job = nxt
            if not await asyncio.to_thread(self.flux_ready, True):
                self._set(d, job, status="waiting")
                await asyncio.sleep(15)
                continue
            with self.lock:
                if not _live(d, job):  # cancelled while waiting
                    continue
            self._set(d, job, status="running")
            while job["done"] < job["count"]:
                with self.lock:
                    if not _live(d, job):  # cancelled between pictures
                        break
                try:
                    made = await asyncio.to_thread(self.make_one, d, job)
                except Cancelled:
                    break
                except (art.FluxError, DesignError, OSError) as e:
                    self._set(d, job, status="failed", error=str(e))
                    break
                with self.lock:
                    job["made"].append(made)
                    job["done"] += 1
                    d.save()
            else:
                self._set(d, job, status="done")


class Cancelled(Exception):
    """The job was cancelled while FLUX drew its picture: the picture is thrown away."""


def _live(d: Design, job: dict) -> bool:
    return any(j is job for j in d.data["jobs"])


def _in_use(d: Design) -> set[str]:
    """Symbols in use: in the final set, on the value ladder (scatters too) or followed by an art slot."""
    used = {s["id"] for s in d.data["symbols"] if s.get("keep")}
    used |= set(d.data.get("ladder", {}).get("slots", {}).values())
    used |= {v[4:] for v in d.data.get("art_slots", {}).values() if isinstance(v, str) and v.startswith("sym:")}
    return used
