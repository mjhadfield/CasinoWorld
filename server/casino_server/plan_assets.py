"""
The floor plan's asset library: furniture, decor and floor textures for the rooms (plan.py's "a:<id>" items and
floor textures), shown on the admin page's Floor plan tab and drawn by the game (its PlanArt autoload fetches
manifest() and the pictures, so new art needs no export).

  server/plan_assets/            the built-ins, cut from LPC packs by tools/build_plan_assets.py (catalogue.json,
                                 CREDITS.md)
  <data dir>/plan_assets/        uploads: their pictures and uploads.json (the same shape as the catalogue)

An asset: {"name", "category", "mount": floor|flat|wall, "credit", "facings": {facing: {"file", "anchor": [x, y],
"mirror"}}, "rect", "body", "by_facing": {facing: {"rect", "body"}}}. Its pictures stand on their anchor (the middle
of the base; a rug's middle); rect is the picture about the anchor, body the footprint that blocks walking (none
for rugs and wall pieces). A floor: {"name", "file", "credit"}, one seamless tile.

install() puts every asset and floor into plan.ASSETS and plan.FLOORS (with each picture's URL); uploads, edits and
deletes call it again and bump the version the game refetches by.
"""
import io
import json
import re
import time
from pathlib import Path

from PIL import Image

from casino_server import plan

BUILTIN_DIR = Path(__file__).resolve().parents[1] / "plan_assets"
MAX_UPLOAD = 8 * 1024 * 1024
MAX_SIDE = 512
MOUNTS = ("floor", "flat", "wall")
CATEGORIES = ("Seating", "Tables & desks", "Bar & counters", "Plants", "Lighting", "Statues & fountains", "Decor",
              "Rugs", "Wall decor", "Uploads")


class AssetError(ValueError):
    """An upload or edit the library can't take (shown to the page as-is)."""


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {"assets": {}, "floors": {}}


def default_body(w: int, h: int, depth: int | None = None) -> list:
    d = depth if depth is not None else max(8, min(28, round(h * 0.4)))
    inset = max(1, round(w * 0.08))
    return [-w / 2 + inset, -d, w - 2 * inset, d]


class AssetLibrary:
    def __init__(self, data_dir: Path, builtin_dir: Path = BUILTIN_DIR):
        self.builtin_dir = builtin_dir
        self.dir = data_dir / "plan_assets"
        self.version = int(time.time())
        self.install()

    # ------------------------------------------------------------------ what there is
    def builtins(self) -> dict:
        return _read(self.builtin_dir / "catalogue.json")

    def uploads(self) -> dict:
        return _read(self.dir / "uploads.json")

    def _save_uploads(self, data: dict):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / "uploads.tmp"
        tmp.write_text(json.dumps(data, indent=1))
        tmp.replace(self.dir / "uploads.json")

    def _url(self, file: str, uploaded: bool) -> str:
        path = (self.dir if uploaded else self.builtin_dir) / file
        stamp = int(path.stat().st_mtime) if path.is_file() else 0
        return f"/plan-art/{'u/' if uploaded else ''}{file}?v={stamp}"

    def install(self):
        """Every asset and floor into plan.ASSETS / plan.FLOORS, with URLs."""
        plan.ASSETS.clear()
        for f in [k for k in plan.FLOORS if k not in ("carpet", "plain")]:
            plan.FLOORS.pop(f)
        for uploaded, data in ((False, self.builtins()), (True, self.uploads())):
            for aid, a in data["assets"].items():
                a = json.loads(json.dumps(a))
                for f in a["facings"].values():
                    f["url"] = self._url(f["file"], uploaded)
                plan.ASSETS[aid] = {**a, "uploaded": uploaded}
            for fid, f in data["floors"].items():
                plan.FLOORS[fid] = {**f, "url": self._url(f["file"], uploaded), "uploaded": uploaded}
        self.version += 1

    def manifest(self) -> dict:
        """What the game draws with: {version, assets: {id: {mount, facings: {f: {url, anchor, mirror}}, body,
        by_facing}}, floors: {id: url}}."""
        return {"version": self.version,
                "assets": {aid: {"mount": a["mount"], "body": a.get("body"), "by_facing": a.get("by_facing", {}),
                                 "facings": {f: {k: v[k] for k in ("url", "anchor", "mirror") if k in v} for f, v in a["facings"].items()}}
                           for aid, a in plan.ASSETS.items()},
                "floors": {fid: f["url"] for fid, f in plan.FLOORS.items() if "url" in f}}

    def file_path(self, rel: str) -> Path | None:
        uploaded = rel.startswith("u/")
        root = self.dir if uploaded else self.builtin_dir
        path = (root / (rel[2:] if uploaded else rel)).resolve()
        if not path.is_relative_to(root.resolve()) or path.suffix != ".png" or not path.is_file():
            return None
        return path

    # ------------------------------------------------------------------ uploads
    def _picture(self, body: bytes, floor: bool = False) -> Image.Image:
        if not body:
            raise AssetError("That file is empty.")
        if len(body) > MAX_UPLOAD:
            raise AssetError("That file is too big (8 MB at most).")
        try:
            im = Image.open(io.BytesIO(body))
            im.load()
        except Exception:
            raise AssetError("That isn't a picture the library can read (PNG, WebP, GIF or JPEG).")
        im = im.convert("RGBA")
        if max(im.size) > MAX_SIDE:
            raise AssetError(f"That picture is {im.size[0]}×{im.size[1]}: {MAX_SIDE}px a side at most "
                             "(pixel art is drawn at its own size: an LPC tile is 32px).")
        if not floor:
            bb = im.getchannel("A").point(lambda a: 255 if a >= 16 else 0).getbbox()
            if bb is None:
                raise AssetError("That picture is see-through all over.")
            im = im.crop(bb)
        return im

    def _new_id(self, name: str) -> str:
        base = "u_" + (re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:28] or "asset")
        taken = set(plan.ASSETS) | set(plan.FLOORS)
        aid, n = base, 2
        while aid in taken:
            aid, n = f"{base}_{n}", n + 1
        return aid

    def upload(self, filename: str, body: bytes, kind: str = "asset") -> dict:
        """A new asset (or floor texture, kind "floor") from a picture: named after the file, standing on the floor
        on the middle of its base, its footprint the bottom of the picture (edit them with update)."""
        floor = kind == "floor"
        im = self._picture(body, floor)
        stem = Path(filename).stem
        aid = self._new_id(stem)
        self.dir.mkdir(parents=True, exist_ok=True)
        im.save(self.dir / f"{aid}.png")
        data = self.uploads()
        name = " ".join(re.sub(r"[_-]+", " ", stem).split())[:40].capitalize() or "Upload"
        if floor:
            data["floors"][aid] = {"name": name, "file": f"{aid}.png", "credit": ""}
        else:
            w, h = im.size
            data["assets"][aid] = {"name": name, "category": "Uploads", "mount": "floor", "credit": "",
                                   "facings": {"down": {"file": f"{aid}.png", "anchor": [w // 2, h]}},
                                   "rect": [-(w // 2), -h, w, h], "body": default_body(w, h)}
        self._save_uploads(data)
        self.install()
        return {"id": aid, "kind": kind}

    def upload_facing(self, aid: str, facing: str, body: bytes) -> dict:
        """Another way an uploaded asset faces: its own picture (the anchor and footprint scaled to fit)."""
        data = self.uploads()
        a = data["assets"].get(aid)
        if a is None:
            raise AssetError("Only uploaded assets can be given more pictures.")
        if facing not in plan.FACINGS or facing == "down":
            raise AssetError("Give a picture for up, left or right (down is the asset's own).")
        im = self._picture(body)
        file = f"{aid}_{facing}.png"
        im.save(self.dir / file)
        w, h = im.size
        a["facings"][facing] = {"file": file, "anchor": [w // 2, h]}
        a.setdefault("by_facing", {})[facing] = {"rect": [-(w // 2), -h, w, h], "body": default_body(w, h, round(-a["body"][1]) if a.get("body") else None)}
        self._save_uploads(data)
        self.install()
        return self.describe(aid)

    def update(self, aid: str, changes: dict) -> dict:
        """Edit an uploaded asset's name, category, credit, mount, anchor, footprint ("body", about the anchor) or
        mirrored facings ({"mirror": {"right": "left"}}); a floor's name and credit."""
        data = self.uploads()
        if aid in data["floors"]:
            f = data["floors"][aid]
            for k in ("name", "credit"):
                if k in changes:
                    f[k] = " ".join(str(changes[k]).split())[:80 if k == "credit" else 40]
            self._save_uploads(data)
            self.install()
            return {"id": aid}
        a = data["assets"].get(aid)
        if a is None:
            raise AssetError("Built-in assets can't be changed here (tools/build_plan_assets.py makes them).")
        if "name" in changes:
            a["name"] = " ".join(str(changes["name"]).split())[:40] or a["name"]
        if "category" in changes:
            a["category"] = " ".join(str(changes["category"]).split())[:30] or "Uploads"
        if "credit" in changes:
            a["credit"] = " ".join(str(changes["credit"]).split())[:200]
        if "mount" in changes:
            if changes["mount"] not in MOUNTS:
                raise AssetError(f"An asset stands on the floor, lies flat or hangs on the wall ({', '.join(MOUNTS)}).")
            a["mount"] = changes["mount"]
        down = a["facings"]["down"]
        img_w, img_h = a["rect"][2], a["rect"][3]
        if "anchor" in changes:
            try:
                ax, ay = (round(float(v)) for v in changes["anchor"])
            except (TypeError, ValueError):
                raise AssetError("An anchor is [x, y] on the picture.")
            if not (0 <= ax <= img_w and 0 <= ay <= img_h):
                raise AssetError("The anchor must be on the picture.")
            down["anchor"] = [ax, ay]
            a["rect"] = [-ax, -ay, img_w, img_h]
        if "body" in changes:
            try:
                bx, by, bw, bh = (round(float(v) * 2) / 2 for v in changes["body"])
            except (TypeError, ValueError):
                raise AssetError("A footprint is [x, y, width, height] about the anchor.")
            if bw < 2 or bh < 2:
                raise AssetError("A footprint needs some size.")
            a["body"] = [bx, by, bw, bh]
        for facing, of in (changes.get("mirror") or {}).items():
            if facing not in ("left", "right", "up") or of not in a["facings"] or a["facings"][of].get("mirror"):
                raise AssetError("Mirror one facing's own picture: left of right, or right of left.")
            a["facings"][facing] = {**a["facings"][of], "mirror": True}
            if of in a.get("by_facing", {}):
                a["by_facing"][facing] = a["by_facing"][of]
        a["body"] = a["body"] if a["mount"] == "floor" else None
        if a["mount"] == "floor" and not a.get("body"):
            a["body"] = default_body(img_w, img_h)
        self._save_uploads(data)
        self.install()
        return self.describe(aid)

    def describe(self, aid: str) -> dict:
        return {"id": aid, **plan.ASSETS[aid]} if aid in plan.ASSETS else {"id": aid, **plan.FLOORS[aid]}

    def delete(self, aid: str, plans: list[dict]) -> None:
        """Delete an upload, unless a room uses it (in the draft, on the floor, or a blueprint in the library)."""
        data = self.uploads()
        if aid not in data["assets"] and aid not in data["floors"]:
            raise AssetError("Only uploads can be deleted.")
        for p in plans:
            for room in p["rooms"]:
                used = any(i["asset"] == "a:" + aid for i in room["items"]) or room["floor"]["texture"] == aid \
                    or any(x["texture"] == aid for x in room["patches"])
                if used:
                    raise AssetError(f"{room['name']} uses it: take it out of the room first.")
        entry = data["assets"].pop(aid, None) or data["floors"].pop(aid)
        files = [f["file"] for f in entry.get("facings", {}).values()] if "facings" in entry else [entry["file"]]
        for file in set(files):
            (self.dir / file).unlink(missing_ok=True)
        self._save_uploads(data)
        self.install()
