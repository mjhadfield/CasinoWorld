"""
The Slot design wizard's last step, Build: a signed-off design becomes a slot the casino plays.

build() writes the design into its build folder (slot_builds.py explains the layout): the variant (its frozen
maths, from slot_design_steps.variant_from_design) with its theme (colours, fonts, frame, win animations, words,
rules screen, floor cabinet), every picture the game draws, the two fonts, its floor spot and its sounds, and an
IDEAS.md of any new feature or bonus it described (those need building in code). install() then restarts the live
server, which loads it: its cabinets appear on the floor and its art, fonts and sounds reach every game. A dev
instance is restarted by hand instead.
"""
import dataclasses
import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

from casino_server import slot_builds
from casino_server.slot_design_steps import (FONTS_DIR, DesignError, _font_path, art_view, deck_look, bonuses_view, ladder_view,
                                             signoff_view, sprites_view, variant_from_design)

REPO = Path(__file__).resolve().parents[2]
ARMADILLO_ART = Path(__file__).resolve().parents[1] / "slot_art" / "armadillo" / "flux2"


def _is_live() -> bool:
    return not os.environ.get("CASINO_DATA_DIR") and not os.environ.get("CASINO_SLOT_BUILDS_DIR")


def _spot_owner(root: Path, spot: str, did: str) -> str | None:
    for p in root.glob("*/variant.json") if root.is_dir() else []:
        try:
            v = json.loads(p.read_text())
        except (ValueError, OSError):
            continue
        if v.get("id") != did and v.get("extras", {}).get("floor", {}).get("spot") == spot:
            return v.get("name", v.get("id"))
    return None


class BuildMixin:
    builds_dir: Path = slot_builds.DEFAULT_DIR   # app.py sets it from CASINO_SLOT_BUILDS_DIR

    def build_view(self, d) -> dict:
        built = None
        p = self.builds_dir / d.id / "variant.json"
        if p.is_file():
            try:
                v = json.loads(p.read_text())
                built = {"at": v.get("extras", {}).get("built_at"), **v.get("extras", {}).get("floor", {}),
                         "loaded": d.id in slot_builds.BUILT}
            except (ValueError, OSError):
                built = {"at": None, "loaded": False}
        return {"spots": [{"id": k, "label": s["label"], "taken_by": _spot_owner(self.builds_dir, k, d.id)} for k, s in slot_builds.SPOTS.items()],
                "max_cabinets": len(slot_builds.BANK), "built": built, "live": _is_live(),
                "ideas": d.data.get("specs", []), "signed_off": bool(d.data.get("signed_off"))}

    def build(self, did: str, spot: str, count: int) -> dict:
        with self.lock:
            d = self.design(did)
            if not d.data.get("signed_off"):
                raise DesignError("Sign the slot off first (Mockup & sign-off).")
            if spot not in slot_builds.SPOTS:
                raise DesignError("Pick one of the floor spots.")
            if not isinstance(count, int) or not 1 <= count <= len(slot_builds.BANK):
                raise DesignError(f"A bank has 1 to {len(slot_builds.BANK)} cabinets.")
            owner = _spot_owner(self.builds_dir, spot, did)
            if owner:
                raise DesignError(f"{owner} already stands there.")
            if did == "armadillo":
                raise DesignError("That id is Armadillo Goes West's.")
            v = variant_from_design(d)
            lad, sp, sc, b, arts = ladder_view(d), sprites_view(d), d.data.get("scene", {}), bonuses_view(d), art_view(d)
            names = {s["id"]: s["name"] for s in d.data["symbols"]}
            # the pictures: each tier's chosen take, the feature and bonus art (Armadillo's where none was chosen),
            # the logo and the background
            pictures = {t: d.path(d.chosen_file(d.symbol(lad["slots"][t]))) for t in lad["tiers"]}
            for key, a in arts.items():
                pictures[key] = d.path(a["file"]) if a["file"] else ARMADILLO_ART / f"{key}.png"
            if sc.get("logo", {}).get("file"):
                pictures["logo"] = d.path(sc["logo"]["file"])
            if sc.get("background"):
                pictures["bg"] = d.path(sc["background"])
            missing = [k for k, p in pictures.items() if not p or not Path(p).is_file()]
            if missing:
                raise DesignError("Pictures missing: " + ", ".join(missing))
            labels = {t: f"{names.get(lad['slots'][t], t)} ({t})" for t in lad["tiers"]}
            labels.update({k: a["label"] for k, a in arts.items()})
            labels.update({k: n for k, n in (("logo", "Logo"), ("bg", "Background")) if k in pictures})
            fonts = {role: _font_path(d, name) for role, name in sp["fonts"].items()}
            theme = {
                "colours": sp["colours"], "fonts": {role: f"{role}{p.suffix.lower()}" for role, p in fonts.items()},
                "frame": sc.get("frame", {"style": "metal", "colour": "#c9a24a"}), "deck": deck_look(sc), "win": sp["win"], "labels": False,
                "texts": {"tagline": "GOOD LUCK", "trail": b["trail"]["name"].upper(), "launcher": b["trail"]["launcher"].upper(),
                          "hint": b["trail"]["hint"], "free": b["free"]["name"].upper(),
                          "battle": b["battle"]["name"].upper(), "battle_hint": b["battle"]["hint"],
                          "enemy": b["battle"]["enemy"].upper(), "boss": b["battle"]["boss_name"].upper(),
                          "bonus_line": f"3+ {v.symbols.get('BS', 'BS').upper()}", "free_line": f"3+ {v.symbols.get('FS', 'FS').upper()}"},
                "rules": signoff_view(d)["rules"], "cabinet": sp["cabinet"], "background": "bg" in pictures}
            data = json.loads(json.dumps(dataclasses.asdict(v)))
            data.update(theme=theme, extras={"assets": labels, "floor": {"spot": spot, "count": count},
                                             "sounds": d.data.get("sounds", {}), "design": d.id,
                                             "built_at": datetime.datetime.now().isoformat(timespec="seconds")})
            out = self.builds_dir / d.id
            tmp = self.builds_dir / f".{d.id}.building"
            shutil.rmtree(tmp, ignore_errors=True)
            (tmp / "art").mkdir(parents=True)
            (tmp / "fonts").mkdir()
            for key, src in pictures.items():
                shutil.copyfile(src, tmp / "art" / f"{key}.png")
            for role, src in fonts.items():
                shutil.copyfile(src, tmp / "fonts" / theme["fonts"][role])
            ideas = d.data.get("specs", [])
            if ideas:
                (tmp / "IDEAS.md").write_text(f"# {v.name}: ideas to build\n\nDescribed on the Slot design wizard; each needs the engine "
                    "(server/casino_server/slots/, docs/slots/mockup/slots_math.js), the mockup and the game's slot screen.\n\n"
                    + "\n".join(f"## {x['name']} ({x['kind']}, {x['timing']})\n\n{x['description']}\n\nPictures: {x['art'] or '—'}\n" for x in ideas))
            (tmp / "variant.json").write_text(json.dumps(data, indent=1))
            shutil.rmtree(out, ignore_errors=True)
            tmp.rename(out)
            d.data["steps"]["build"] = "doing"
            d.save()
            return self.build_view(d)

    def install(self, did: str) -> str:
        """Restart the live server so it loads the build (from its own unit: a request can't restart its server)."""
        with self.lock:
            d = self.design(did)
            if not (self.builds_dir / d.id / "variant.json").is_file():
                raise DesignError("Build it first.")
        if not _is_live():
            raise DesignError("This is a test or dev instance: restart it (tools/dev.sh server) to load the build.")
        try:
            subprocess.run(["systemd-run", "--user", "--collect", "--quiet", f"--unit=casino-install-{did}-{int(datetime.datetime.now().timestamp())}",
                            str(REPO / "tools" / "dev.sh"), "restart"], check=True, timeout=20, capture_output=True)
        except (OSError, subprocess.SubprocessError) as e:
            raise DesignError(f"Couldn't start the restart: {e}")
        with self.lock:
            d.data["steps"]["build"] = "done"
            d.save()
        return "Restarting the casino in a moment: games reconnect by themselves."
