"""
The admin page's Slot design tab: a working board for a slot machine's art, from reference sheets to the
final symbol set. Star Trek is the first design; any later slot starts as a new folder.

A design is a folder under server/slot_designs/<id>/ (CASINO_DESIGNS_DIR moves it, for tests and the dev
instance):
  design.json      the board: categories (with how many symbols the main game needs), symbols, choices, jobs
  source/          the reference sheets the design started from
  ref/             one reference crop per symbol (docs/slots/tools/startrek_crop.py made Star Trek's)
  links/           reference images linked on the page (uploaded or fetched from a URL)
  raw/             what FLUX returned, before keying: <id>_<n>.png (objects), bust_<id>_<n>.png (characters)
  cut/             objects, keyed and fitted to 512²: <id>_<n>.png
  chars/           characters in the shared frame, one per frame colour: <id>_<n>_<hue>.png
A symbol's variants are found from those files, so anything added by hand shows up too.

Generate queues a job per symbol marked Reiterate or newly added; one background task (run(), on
app.state for the server's lifespan) works through them with FLUX in Odysseus (slot_design_art.py).
Jobs live in design.json, so a restart carries on where it stopped.
"""
import asyncio
import io
import json
import re
import threading
import time
import urllib.request
from pathlib import Path

from casino_server import slot_design_art as art

DEFAULT_DESIGNS_DIR = Path(__file__).resolve().parents[1] / "slot_designs"
SERVED = ("source", "ref", "links", "cut", "chars")
MAX_IMAGE = 12 * 1024 * 1024
TAKES = 3  # images per job
KINDS = ("object", "character")
KEYS = ("magenta", "green")


class DesignError(ValueError):
    """A request the board can't take (shown to the page as-is)."""


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
        for job in self.data.setdefault("jobs", []):
            if job["status"] in ("running", "waiting"):
                job["status"] = "queued"  # the server stopped mid-job: carry on

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
    def variants(self, s: dict) -> list[dict]:
        sid, out = s["id"], []
        fav = s.get("favourite")
        hidden = set(s.get("hidden", [])) | {fav}
        if fav and self.path(fav):
            out.append({"id": fav, "label": "Favourite", "fav": True, "src": fav})
        for n, p in _numbered(self.folder / "cut", sid).items():
            if f"cut/{p.name}" not in hidden:
                out.append({"id": f"cut/{p.name}", "label": f"Take {n}", "src": f"cut/{p.name}"})
        for n in _numbered(self.folder / "raw", f"bust_{sid}"):
            hues = {h: f"chars/{sid}_{n}_{h}.png" for h in art.HUES if (self.folder / f"chars/{sid}_{n}_{h}.png").exists()}
            if hues and f"bust/{sid}_{n}" not in hidden:
                out.append({"id": f"bust/{sid}_{n}", "label": f"Framed {n}", "hues": hues})
        return out

    def chosen(self, s: dict) -> dict | None:
        vs = self.variants(s)
        return next((v for v in vs if v["id"] == s.get("choice")), vs[0] if vs else None)

    def chosen_file(self, s: dict) -> str | None:
        v = self.chosen(s)
        if not v:
            return None
        return v["hues"].get(s.get("hue"), next(iter(v["hues"].values()))) if "hues" in v else v["src"]

    def next_n(self, prefix: str) -> int:
        ns = list(_numbered(self.folder / "raw", prefix)) + list(_numbered(self.folder / "cut", prefix))
        return max(ns, default=0) + 1


class DesignBoard:
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
            symbols = []
            for s in d.data["symbols"]:
                active = [j for j in jobs if j["symbol"] == s["id"] and j["status"] in ("queued", "waiting", "running", "failed")]
                v = d.chosen(s)
                symbols.append({
                    **{k: s.get(k) for k in ("id", "name", "category", "kind", "key", "keep_text", "prompt", "hue", "note", "base")},
                    "keep": bool(s.get("keep")), "reiterate": bool(s.get("reiterate")), "added": bool(s.get("added")),
                    "pending_new": bool(s.get("pending_new")), "refs": s.get("refs", []),
                    "variants": d.variants(s), "choice": v["id"] if v else None, "file": d.chosen_file(s),
                    "job": active[-1] if active else None})
            categories = []
            for c in d.data["categories"]:
                mine = [s for s in d.data["symbols"] if s["category"] == c["id"]]
                categories.append({**c, "count": len(mine), "in_set": sum(bool(s.get("keep")) for s in mine)})
            running = next((j for j in jobs if j["status"] in ("running", "waiting")), None)
            return {"id": d.id, "name": d.data.get("name", d.id), "note": d.data.get("note", ""),
                    "categories": categories, "symbols": symbols, "hues": list(art.HUES),
                    "pending": sum(bool(s.get("reiterate") or s.get("pending_new")) for s in d.data["symbols"]),
                    "queued": sum(j["status"] == "queued" for j in jobs), "running": running}

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
            base, sid, i = _slug(name) or "symbol", None, 1
            taken = {s["id"] for s in d.data["symbols"]}
            sid = base
            while sid in taken:
                i += 1
                sid = f"{base}_{i}"
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
        from PIL import Image, UnidentifiedImageError
        d = self.design(did)
        if not data:
            raise DesignError("That file is empty.")
        if len(data) > MAX_IMAGE:
            raise DesignError("That image is over 12 MB.")
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
        except (UnidentifiedImageError, OSError):
            raise DesignError("That isn't an image the server can read (use PNG, JPEG or WebP).")
        im = im.convert("RGBA")
        im.thumbnail((1024, 1024), Image.LANCZOS)
        stem = _slug(Path(filename).stem) or "image"
        with self.lock:
            folder = d.folder / "links"
            folder.mkdir(exist_ok=True)
            n, name = 1, f"{stem}.png"
            while (folder / name).exists():
                n += 1
                name = f"{stem}_{n}.png"
            im.save(folder / name)
        return f"links/{name}"

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

    # ------------------------------------------------------------- jobs
    def generate(self, did: str) -> int:
        """Queue a job for every symbol marked Reiterate or newly added. Returns how many were queued."""
        with self.lock:
            d = self.design(did)
            jobs = d.data["jobs"]
            next_id = max((j["id"] for j in jobs), default=0) + 1
            queued = 0
            for s in d.data["symbols"]:
                if s.get("pending_new"):
                    ref = s["refs"][0] if s.get("refs") else None
                    job = {"how": "redraw" if ref else "text", "src": ref, "text": s.get("prompt", ""),
                           "out": s["kind"], "action": "new"}
                    s["pending_new"] = False
                elif s.get("reiterate"):
                    job = self._reiterate_job(d, s)
                    s["reiterate"] = False
                    s.setdefault("history", []).append({"from": job["src"], "note": job["text"]})
                else:
                    continue
                jobs.append({"id": next_id, "symbol": s["id"], "status": "queued", "done": 0, "count": TAKES,
                             "made": [], "error": "", **job})
                next_id += 1
                queued += 1
            d.data["jobs"] = [j for j in jobs if j["status"] != "done"][-100:] + \
                [j for j in jobs if j["status"] == "done"][-50:]
            d.data["jobs"].sort(key=lambda j: j["id"])
            d.save()
            return queued

    def _reiterate_job(self, d: Design, s: dict) -> dict:
        note = s.get("note", "")
        if s.get("base"):  # a linked reference: redraw it as this symbol
            return {"how": "redraw", "src": s["base"], "text": note, "out": s["kind"], "action": "reiterate"}
        v = d.chosen(s)
        if not v:
            if s.get("refs"):
                return {"how": "redraw", "src": s["refs"][0], "text": note, "out": s["kind"], "action": "reiterate"}
            return {"how": "text", "src": None, "text": f"{s.get('prompt', '')} {note}".strip(), "out": s["kind"],
                    "action": "reiterate"}
        if "hues" in v:  # a framed character: vary the bust it was made from
            return {"how": "variation", "src": f"raw/bust_{v['id'].split('/', 1)[1]}.png", "text": note,
                    "out": "character", "action": "reiterate"}
        raw = "raw/" + Path(v["src"]).name
        return {"how": "variation", "src": raw if (d.folder / raw).exists() else v["src"], "text": note,
                "out": "object", "action": "reiterate"}

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
            if not job or job["status"] not in ("queued", "failed", "waiting"):
                raise DesignError("Only a queued, waiting or failed job can be cancelled.")
            d.data["jobs"].remove(job)
            d.save()

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
        with self.lock:
            s = d.symbol(job["symbol"])
            key, keep_text = s.get("key", "magenta"), s.get("keep_text")
            prefix = f"bust_{s['id']}" if job["out"] == "character" else s["id"]
            n = d.next_n(prefix)
        i, text, how = job["done"] + 1, job.get("text", ""), job["how"]
        if job["out"] == "character":
            prompt = (art.bust_text_prompt(key, text) if how == "text" else
                      art.variation_prompt("character", key, text) if how == "variation" else art.bust_prompt(key, text))
        else:
            prompt = (art.object_text_prompt(i, key, text) if how == "text" else
                      art.variation_prompt("object", key, text) if how == "variation" else
                      art.object_prompt(i, key, keep_text, text))
        if how == "text":
            raw = art.flux_generate(prompt)
        else:
            from PIL import Image
            src = d.path(job["src"], SERVED + ("raw",))
            if not src:
                raise art.FluxError(f"The reference {job['src']} has gone.")
            raw = art.flux_edit(Image.open(src), prompt)
        if job["out"] == "character":
            tiles = art.compose_character(raw)
        else:
            tile = art.symbol(raw)
        with self.lock:
            for sub in ("raw", "cut", "chars"):
                (d.folder / sub).mkdir(exist_ok=True)
            n = max(n, d.next_n(prefix))  # in case a file appeared meanwhile
            raw.save(d.folder / f"raw/{prefix}_{n}.png")
            if job["out"] == "character":
                for hue, im in tiles.items():
                    im.save(d.folder / f"chars/{s['id']}_{n}_{hue}.png", optimize=True)
            else:
                tile.save(d.folder / f"cut/{prefix}_{n}.png", optimize=True)
        return f"{prefix}_{n}"

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
                if job not in d.data["jobs"]:  # cancelled while waiting
                    continue
            self._set(d, job, status="running")
            while job["done"] < job["count"]:
                try:
                    made = await asyncio.to_thread(self.make_one, d, job)
                except (art.FluxError, DesignError, OSError) as e:
                    self._set(d, job, status="failed", error=str(e))
                    break
                with self.lock:
                    job["made"].append(made)
                    job["done"] += 1
                    d.save()
            else:
                self._set(d, job, status="done")
