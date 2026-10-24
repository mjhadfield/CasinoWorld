"""
Character art: composites a look (a body, skin, hair, clothes, accessories) into
the game's sprite sheet, from the Universal LPC Spritesheet Character
Generator's layers (pinned to one commit, so it's reproducible). The NPC
designer on the admin page builds looks here; tools/build_art.py uses the same
code for the looks that ship inside the game.

Sheet layout (64x64 frames, rows in LPC's up/left/down/right order):
  rows 0-3   walk, 9 frames
  rows 4-7   idle, 2 frames
  rows 8-11  sit (on a chair), 1 frame -- LPC's sit sheet column 2

A look spec is a dict:
  {"body": "male"|"female", "skin": <skin colour>,
   "hair": [style, colour] | None, "beard": [style, colour] | None,
   "top": [style, colour], "over": [style, colour] | None, "bottom": [style, colour],
   "shoes": [style, colour] | None, "neck": ..., "glasses": ..., "hat": ...}
Its id is a hash of the spec ("x_" + 12 hex digits); sheets are built on demand
and cached. OPTIONS is the designer's catalogue: what each slot can be, on which
bodies, in which colours.

LPC art is CC-BY-SA 3.0 / GPL 3.0 / OGA-BY 3.0 (see credits()).

  python -m casino_server.art prefetch   download every layer the catalogue uses
  python -m casino_server.art verify     check every option renders on its bodies
"""
import hashlib
import json
import sys
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import Image

COMMIT = "9bf06be193b053db256b2536824af426de046aa2"
RAW = f"https://raw.githubusercontent.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator/{COMMIT}"
CACHE = Path(__file__).resolve().parents[1] / "lpc_cache"
FRAME = 64
DIRS = 4
WALK_FRAMES, IDLE_FRAMES = 9, 2
SIT_CHAIR_COLUMN = 2  # LPC sit.png columns: ground, kneel, chair
BODIES = ("male", "female")
PALETTE_BASES = {"body": "light", "hair": "orange", "cloth": "white"}
SKINS = ("light", "amber", "olive", "taupe", "bronze", "brown", "black")   # the human tones (the palette has fantasy ones too)

# ---------------------------------------------------------------------- the catalogue
# slot -> {option id: (label, sheet definition)}. Colours and bodies come from the
# definition itself (its recolour material's palette, or its colour variants; the
# body types it has art for).
OPTIONS = {
    "hair": {
        "plain": ("Short", "hair/short/hair_plain.json"),
        "parted": ("Parted", "hair/short/hair_parted.json"),
        "bangsshort": ("Short bangs", "hair/short/hair_bangsshort.json"),
        "messy1": ("Messy", "hair/short/hair_messy1.json"),
        "buzzcut": ("Buzz cut", "hair/bald/hair_buzzcut.json"),
        "high_and_tight": ("High and tight", "hair/bald/hair_high_and_tight.json"),
        "balding": ("Balding", "hair/bald/hair_balding.json"),
        "afro": ("Afro", "hair/afro/hair_afro.json"),
        "natural": ("Natural", "hair/afro/hair_natural.json"),
        "cornrows": ("Cornrows", "hair/afro/hair_cornrows.json"),
        "bob": ("Bob", "hair/bob/hair_bob.json"),
        "lob": ("Long bob", "hair/bob/hair_lob.json"),
        "ponytail": ("Ponytail", "hair/braids/hair_ponytail.json"),
        "bun": ("Bun", "hair/braids/hair_bangs_bun.json"),
        "curly_short": ("Curly short", "hair/curly/hair_curly_short.json"),
        "curly_long": ("Curly long", "hair/curly/hair_curly_long.json"),
    },
    "beard": {
        "stubble": ("Stubble", "hair/beards/beards_5oclock_shadow.json"),
        "trimmed": ("Trimmed beard", "hair/beards/beards_trimmed.json"),
        "beard": ("Full beard", "hair/beards/beards_beard.json"),
        "mustache": ("Moustache", "hair/mustaches/beards_mustache.json"),
        "handlebar": ("Handlebar", "hair/mustaches/beards_handlebar.json"),
    },
    "top": {
        "longsleeve": ("Long sleeve", "torso/shirts/longsleeve/torso_clothes_longsleeve.json"),
        "polo_long": ("Polo, long sleeve", "torso/shirts/longsleeve/torso_clothes_longsleeve2_polo.json"),
        "cardigan": ("Cardigan", "torso/shirts/longsleeve/torso_clothes_longsleeve2_cardigan.json"),
        "formal": ("Formal shirt", "torso/shirts/longsleeve/torso_clothes_longsleeve_formal.json"),
        "tshirt": ("T-shirt", "torso/shirts/shortsleeve/torso_clothes_tshirt.json"),
        "polo": ("Polo", "torso/shirts/shortsleeve/torso_clothes_shortsleeve_polo.json"),
        "blouse": ("Blouse", "torso/shirts/torso_clothes_blouse.json"),
        "blouse_long": ("Blouse, long sleeve", "torso/shirts/torso_clothes_blouse_longsleeve.json"),
        "tanktop": ("Tank top", "torso/shirts/sleeveless/torso_clothes_sleeveless_tanktop.json"),
    },
    "over": {
        "vest": ("Waistcoat", "torso/vest/torso_clothes_vest.json"),
        "vest_open": ("Open waistcoat", "torso/vest/torso_clothes_vest_open.json"),
        "jacket": ("Collared coat", "torso/jacket/torso_jacket_collared.json"),
        "trench": ("Trench coat", "torso/jacket/torso_jacket_trench.json"),
    },
    "bottom": {
        "pants": ("Trousers", "legs/pants/legs_pants.json"),
        "formal": ("Formal trousers", "legs/pants/legs_formal.json"),
        "cuffed": ("Cuffed trousers", "legs/pants/legs_cuffed.json"),
        "shorts": ("Shorts", "legs/shorts/legs_shorts.json"),
        "skirt": ("Skirt", "legs/skirts/legs_skirts_plain.json"),
        "skirt_straight": ("Straight skirt", "legs/skirts/legs_skirt_straight.json"),
        "leggings": ("Leggings", "legs/leggings/legs_leggings.json"),
    },
    "shoes": {
        "shoes": ("Shoes", "feet/shoes/feet_shoes_basic.json"),
        "shoes_revised": ("Smart shoes", "feet/shoes/feet_shoes_revised.json"),
        "boots": ("Boots", "feet/boots/feet_boots_basic.json"),
        "sandals": ("Sandals", "feet/feet_sandals.json"),
    },
    "neck": {
        "bowtie": ("Bow tie", "headwear/neck/neck_bowtie.json"),
        "necktie": ("Tie", "headwear/neck/neck_necktie.json"),
        "necklace": ("Necklace", "headwear/neck/neck_necklace_simple.json"),
        "scarf": ("Scarf", "headwear/neck/neck_scarf.json"),
    },
    "glasses": {
        "glasses": ("Glasses", "headwear/accessories/glasses/facial_glasses.json"),
        "round": ("Round glasses", "headwear/accessories/glasses/facial_glasses_round.json"),
        "sunglasses": ("Sunglasses", "headwear/accessories/glasses/facial_glasses_sunglasses.json"),
        "shades": ("Shades", "headwear/accessories/glasses/facial_glasses_shades.json"),
    },
    "hat": {
        "bowler": ("Bowler", "headwear/hats/formal/hat_formal_bowler.json"),
        "tophat": ("Top hat", "headwear/hats/formal/hat_formal_tophat.json"),
    },
}
SLOT_LABELS = {"hair": "Hair", "beard": "Facial hair", "top": "Top", "over": "Over the top", "bottom": "Legs",
               "shoes": "Shoes", "neck": "Neck", "glasses": "Glasses", "hat": "Hat"}
REQUIRED = ("top", "bottom")          # every look has these; the rest can be "none"
BODY_DEFS = {"body": "body/body.json", "head_male": "head/heads/human/heads_human_male.json",
             "head_female": "head/heads/human/heads_human_female.json"}
SLOT_ORDER = ("hair", "beard", "top", "over", "bottom", "shoes", "neck", "glasses", "hat")

# The built-in uniforms (staff.py lays the admin page's changes and additions over them).
# The formal shirt and waistcoats only come in a male fit; the female uniforms use a blouse.
UNIFORMS = {
    "dealer": {
        "male": {"top": ["formal", "white"], "over": ["vest", "black"], "neck": ["bowtie", "black"],
                 "bottom": ["formal", "black"], "shoes": ["shoes", "black"]},
        "female": {"top": ["blouse_long", "white"], "neck": ["bowtie", "black"],
                   "bottom": ["formal", "black"], "shoes": ["shoes", "black"]}},
    "cocktail_waiter": {
        "male": {"top": ["formal", "white"], "over": ["vest_open", "maroon"], "neck": ["bowtie", "maroon"],
                 "bottom": ["formal", "black"], "shoes": ["shoes", "black"]},
        "female": {"top": ["blouse", "white"], "neck": ["bowtie", "maroon"],
                   "bottom": ["skirt_straight", "black"], "shoes": ["shoes", "black"]}},
    "pit_boss": {
        "male": {"top": ["formal", "white"], "over": ["jacket", "charcoal"], "neck": ["necktie", "maroon"],
                 "bottom": ["formal", "charcoal"], "shoes": ["shoes_revised", "black"]},
        "female": {"top": ["blouse_long", "gray"], "neck": ["necklace", "gold"],
                   "bottom": ["formal", "charcoal"], "shoes": ["shoes_revised", "black"]}},
    "cashier": {
        "male": {"top": ["polo_long", "navy"], "bottom": ["formal", "black"], "shoes": ["shoes", "black"]},
        "female": {"top": ["polo_long", "navy"], "bottom": ["formal", "black"], "shoes": ["shoes", "black"]}},
    "bartender": {
        "male": {"top": ["formal", "white"], "over": ["vest", "black"], "bottom": ["formal", "black"],
                 "shoes": ["shoes", "black"]},
        "female": {"top": ["blouse_long", "black"], "bottom": ["formal", "black"], "shoes": ["shoes", "black"]}},
}


class ArtError(ValueError):
    """A look that can't be built (shown to the admin page as-is)."""


# ---------------------------------------------------------------------- fetching
def fetch(rel: str) -> Path | None:
    """Repo-relative path -> cached local file, or None if it doesn't exist upstream."""
    dest = CACHE / rel
    missing = dest.with_name(dest.name + ".missing")
    if dest.exists():
        return dest
    if missing.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(f"{RAW}/{rel.replace(' ', '%20')}", timeout=20) as r:
            dest.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            missing.touch()
            return None
        raise
    return dest


@lru_cache(maxsize=None)
def load_json(rel: str) -> dict:
    f = fetch(rel)
    if f is None:
        raise ArtError(f"no such LPC file: {rel}")
    return json.loads(f.read_text())


def definition(rel: str) -> dict:
    return load_json(f"sheet_definitions/{rel}")


# ---------------------------------------------------------------------- recolouring
def hex_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def palette(material: str) -> dict:
    return load_json(f"palette_definitions/{material}/{material}_ulpc.json")


def _luma(rgb) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def recolour(img: Image.Image, material: str, target: str) -> Image.Image:
    """The generator's exact-colour palette swap (with its +-1 tolerance). Only each
    sheet's distinct colours are worked out; the swap itself is one pass over the pixels."""
    pal = palette(material)
    base, dest = pal[PALETTE_BASES[material]], pal[target]
    if base == dest:
        return img
    ramp = {hex_rgb(b): hex_rgb(d) for b, d in zip(base, dest)}
    colours = {c[1][:3] for c in (img.getcolors(1 << 16) or []) if c[1][3]}

    def near(c):
        for b, new in ramp.items():
            if abs(c[0] - b[0]) <= 1 and abs(c[1] - b[1]) <= 1 and abs(c[2] - b[2]) <= 1:
                return new
        return None

    mapping = {c: near(c) for c in colours}
    if colours and sum(v is not None for v in mapping.values()) < len(colours) / 2:
        # Drawn in some other ramp (e.g. formal trousers' 3 greens): map its own
        # colours, darkest to lightest, onto the target ramp by rank.
        target_ramp = sorted((hex_rgb(d) for d in dest), key=_luma)
        src = sorted(colours, key=_luma)
        mapping = {c: target_ramp[round(i * (len(target_ramp) - 1) / max(len(src) - 1, 1))] for i, c in enumerate(src)}
    mapping = {k: bytes(v) for k, v in mapping.items() if v is not None and v != k}
    if not mapping:
        return img
    raw = bytearray(img.tobytes())
    for i in range(0, len(raw), 4):
        if raw[i + 3]:
            new = mapping.get((raw[i], raw[i + 1], raw[i + 2]))
            if new:
                raw[i:i + 3] = new
    return Image.frombytes("RGBA", img.size, bytes(raw))


# ---------------------------------------------------------------------- one layer
@lru_cache(maxsize=None)
def colours_of(def_rel: str) -> list[str]:
    """The colours an option comes in: its material's palette, or those of its colour
    variants that actually have art (some listed ones don't)."""
    d = definition(def_rel)
    mat = (d.get("recolors") or {}).get("material")
    if mat:
        return [k for k in palette(mat) if isinstance(palette(mat)[k], list)]
    layer = _layers(def_rel)[0]
    paths = {_layer_rel(layer, b) for b in BODIES} - {None}
    return [c for c in d.get("variants", [])
            if any(fetch(f"spritesheets/{p}walk/{_file_colour(c)}.png") for p in paths)]


def _file_colour(colour: str) -> str:
    return colour.replace(" ", "_")   # "gray striped" is gray_striped.png


def bodies_of(def_rel: str) -> list[str]:
    layer = definition(def_rel).get("layer_1", {})
    return [b for b in BODIES if b in layer]


def _layers(def_rel: str) -> list[dict]:
    d = definition(def_rel)
    return [d[k] for k in sorted(d) if k.startswith("layer_")]


def _layer_rel(layer: dict, body: str) -> str | None:
    return layer.get(body) or layer.get("male")


def layer_anim(def_rel: str, layer: dict, body: str, colour: str, anim: str) -> Image.Image | None:
    """One animation sheet of one layer, in `colour`. Cached on disk once recoloured."""
    path = _layer_rel(layer, body)
    if not path:
        return None
    d = definition(def_rel)
    material = (d.get("recolors") or {}).get("material")
    if def_rel == BODY_DEFS["body"] or def_rel.startswith("head/"):
        material = "body"
    out = CACHE / "_coloured" / f"{path}{anim}.{_file_colour(colour)}.png"
    if out.exists():
        return Image.open(out).convert("RGBA")
    for rel, recolourable in ((f"spritesheets/{path}{anim}.png", True),
                              (f"spritesheets/{path}{anim}/{_file_colour(colour)}.png", False)):
        f = fetch(rel)
        if f:
            img = Image.open(f).convert("RGBA")
            if recolourable and material:
                img = recolour(img, material, colour)
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(out)
            return img
    return None


# ---------------------------------------------------------------------- a look
def parts_of(spec: dict) -> list[tuple[str, str]]:
    """(sheet definition, colour) for every layer a spec needs, body first."""
    body, skin = spec["body"], spec["skin"]
    parts = [(BODY_DEFS["body"], skin), (BODY_DEFS[f"head_{body}"], skin)]
    for slot in SLOT_ORDER:
        choice = spec.get(slot)
        if not choice:
            continue
        option, colour = choice
        parts.append((OPTIONS[slot][option][1], colour))
    return parts


def validate(spec: dict) -> dict:
    """A clean copy of `spec`, or ArtError saying what's wrong."""
    if spec.get("body") not in BODIES:
        raise ArtError("Pick a body: male or female.")
    clean = {"body": spec["body"], "skin": str(spec.get("skin", ""))}
    if clean["skin"] not in SKINS:
        raise ArtError(f"Unknown skin tone {clean['skin']!r}.")
    for slot in SLOT_ORDER:
        choice = spec.get(slot)
        if not choice:
            if slot in REQUIRED:
                raise ArtError(f"{SLOT_LABELS[slot]} is required.")
            clean[slot] = None
            continue
        option, colour = choice[0], choice[1]
        if option not in OPTIONS[slot]:
            raise ArtError(f"Unknown {SLOT_LABELS[slot].lower()}: {option!r}.")
        def_rel = OPTIONS[slot][option][1]
        if clean["body"] not in bodies_of(def_rel):
            raise ArtError(f"{OPTIONS[slot][option][0]} doesn't come in a {clean['body']} fit.")
        if colour not in colours_of(def_rel):
            raise ArtError(f"{OPTIONS[slot][option][0]} doesn't come in {colour!r}.")
        clean[slot] = [option, colour]
    return clean


def look_id(spec: dict) -> str:
    return "x_" + hashlib.sha1(json.dumps(validate(spec), sort_keys=True).encode()).hexdigest()[:12]


def build_sheet(spec: dict) -> Image.Image:
    spec = validate(spec)
    out = Image.new("RGBA", (WALK_FRAMES * FRAME, 12 * FRAME))
    layers = []
    for def_rel, colour in parts_of(spec):
        for layer in _layers(def_rel):
            layers.append((layer.get("zPos", 0), def_rel, layer, colour))
    layers.sort(key=lambda x: x[0])
    for _, def_rel, layer, colour in layers:
        body = spec["body"]
        walk = layer_anim(def_rel, layer, body, colour, "walk")
        if walk is None:
            continue
        idle = layer_anim(def_rel, layer, body, colour, "idle")
        sit = layer_anim(def_rel, layer, body, colour, "sit")
        out.alpha_composite(walk.crop((0, 0, WALK_FRAMES * FRAME, DIRS * FRAME)), (0, 0))
        for row in range(DIRS):
            if idle is not None:
                strip = idle.crop((0, row * FRAME, IDLE_FRAMES * FRAME, (row + 1) * FRAME))
            else:  # stand still on walk frame 0
                frame0 = walk.crop((0, row * FRAME, FRAME, (row + 1) * FRAME))
                strip = Image.new("RGBA", (IDLE_FRAMES * FRAME, FRAME))
                for i in range(IDLE_FRAMES):
                    strip.paste(frame0, (i * FRAME, 0))
            out.alpha_composite(strip, (0, (4 + row) * FRAME))
            if sit is not None:
                cell = sit.crop((SIT_CHAIR_COLUMN * FRAME, row * FRAME, (SIT_CHAIR_COLUMN + 1) * FRAME, (row + 1) * FRAME))
            else:  # no seated art (e.g. the formal shirt, coats): the standing pose, which the rail hides below the waist
                cell = walk.crop((0, row * FRAME, FRAME, (row + 1) * FRAME))
            out.alpha_composite(cell, (0, (8 + row) * FRAME))
    return out


class LookCache:
    """Built sheets, by look id, under <data>/looks/ (with the spec beside each). A sheet
    depends only on its spec, so ones built already this run are kept in memory too."""
    _built: dict[str, bytes] = {}

    def __init__(self, data_dir: Path):
        self.dir = data_dir / "looks"

    def path(self, look: str) -> Path | None:
        p = self.dir / f"{look}.png"
        return p if p.exists() else None

    def ensure(self, spec: dict) -> str:
        spec = validate(spec)
        lid = look_id(spec)
        if not (self.dir / f"{lid}.png").exists():
            self.dir.mkdir(parents=True, exist_ok=True)
            if lid not in self._built:
                import io
                buf = io.BytesIO()
                build_sheet(spec).save(buf, format="PNG")
                self._built[lid] = buf.getvalue()
            (self.dir / f"{lid}.png").write_bytes(self._built[lid])
            (self.dir / f"{lid}.json").write_text(json.dumps(spec, sort_keys=True))
        return lid


# ---------------------------------------------------------------------- for the designer
def catalogue() -> dict:
    """What the designer offers: every slot's options with their bodies and colours."""
    return {
        "bodies": list(BODIES),
        "skins": list(SKINS),
        "slots": [{"slot": slot, "label": SLOT_LABELS[slot], "required": slot in REQUIRED,
                   "options": [{"id": oid, "label": label, "bodies": bodies_of(rel), "colours": colours_of(rel)}
                               for oid, (label, rel) in OPTIONS[slot].items()]} for slot in SLOT_ORDER],
    }


def credits() -> list[dict]:
    """LPC attribution for every layer the catalogue can use."""
    out = []
    rels = list(BODY_DEFS.values()) + [rel for slot in OPTIONS.values() for _, rel in slot.values()]
    for rel in rels:
        d = definition(rel)
        for c in d.get("credits", []):
            out.append({"name": d.get("name", rel), "file": c.get("file", ""), "authors": c.get("authors", []),
                        "licenses": c.get("licenses", []), "urls": c.get("urls", [])})
    return out


# ---------------------------------------------------------------------- command line
def _every_layer_file():
    rels = list(BODY_DEFS.values()) + [rel for slot in OPTIONS.values() for _, rel in slot.values()]
    for rel in rels:
        for layer in _layers(rel):
            for body in BODIES:
                yield rel, layer, body


def prefetch():
    for mat in PALETTE_BASES:
        palette(mat)
    n = 0
    for rel, layer, body in _every_layer_file():
        path = _layer_rel(layer, body)
        if not path:
            continue
        colours = colours_of(rel)
        for anim in ("walk", "idle", "sit"):
            if fetch(f"spritesheets/{path}{anim}.png") is None:  # per-colour files instead
                for colour in colours:
                    fetch(f"spritesheets/{path}{anim}/{_file_colour(colour)}.png")
            n += 1
    print(f"prefetched layers for {n} layer/body/animation combinations into {CACHE}")


def verify() -> list[str]:
    """Every option on every body it claims: does it have walk, idle and sit art?"""
    problems = []
    for slot, opts in OPTIONS.items():
        for oid, (label, rel) in opts.items():
            try:
                bodies, colours = bodies_of(rel), colours_of(rel)
            except ArtError as e:
                problems.append(f"{slot}/{oid}: {e}")
                continue
            if not colours:
                problems.append(f"{slot}/{oid}: no colours")
                continue
            for body in bodies:   # (no idle or sit art is fine: the standing pose stands in)
                layer = _layers(rel)[0]
                if layer_anim(rel, layer, body, colours[0], "walk") is None:
                    problems.append(f"{slot}/{oid} ({body}): no walk")
            if not bodies:
                problems.append(f"{slot}/{oid}: no body fits")
    return problems


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "prefetch":
        prefetch()
    elif cmd == "verify":
        issues = verify()
        print("\n".join(issues) or "every option renders")
    else:
        print(__doc__)
