"""
Which sound plays for each game moment -- edited on the maintenance page
(/maintenance) and fetched by every client when it starts and whenever it
changes, so trying a different sound needs no rebuild.

The library is the CC0 collection in server/sound_library/ (read-only, see its
LIBRARY.md) plus anything uploaded, kept in <data dir>/sounds/uploads/. A sound
is named by its path in the library, e.g. "kenney-casino/card-fan-1.ogg" or
"uploads/my-chip.ogg". The choices live in <data dir>/sounds.json:

    {"version": 3, "moments": {"deal": {"files": [...], "gain_db": 0.0}, ...}}

A moment with several files picks one at random each time it plays; `gain_db`
trims its volume. Moments missing from the file use DEFAULTS.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parents[1] / "sound_library"
PLAYABLE = {".ogg", ".mp3", ".wav"}          # what the Godot client can load at runtime
CONVERTIBLE = {".flac", ".m4a", ".aac", ".opus", ".webm", ".aiff", ".aif"}  # turned into .ogg on upload
MAX_UPLOAD = 20 * 1024 * 1024
GAIN_RANGE = (-30.0, 12.0)

# The game's moments, in page order: key -> (title, when it plays).
MOMENTS = {
    "deal": ("Card dealt", "Each batch of cards that leaves together: a 3-card packet at Three Card Poker, "
                           "a 7-card hand at Pai Gow, every card at Blackjack."),
    "flip": ("Card turned face up", "The dealer's reveal, hands at settlement, Blackjack cards."),
    "shuffle": ("Shuffler fed", "Cards going back through the shuffler after a hand, and a new Blackjack shoe."),
    "bet": ("Chip placed on a bet", "Anyone at the table putting chips on a spot."),
    "payout": ("Winnings paid", "Chips from the tray placed beside a winning bet."),
    "sweep": ("Losing bets swept", "The dealer taking chips back to the tray."),
    "result": ("Result pop", "Each Pai Gow win or lose mark popping in."),
    "turn": ("Your turn", "Your decision starts, or the Pai Gow sorter opens."),
    "tick": ("Timer running out", "Each of the last five seconds of a timer you're up against."),
    "click": ("Button press", "Every button in the game's bar and panels."),
    "ball_spin": ("Roulette ball launched", "The dealer spins the ball: it rolls round the track, slowing (about 6 seconds)."),
    "ball_drop": ("Roulette ball drops", "The ball leaves the track and clatters off a deflector."),
    "ball_rattle": ("Roulette ball skids", "The ball clattering over the frets as it reaches the pockets (repeats while the skid lasts)."),
    "ball_hop": ("Roulette ball hops", "Each hop landing as the ball bounces between pockets, and the last click as it settles."),
    "dice_out": ("Dice pushed out", "The shooter picks up the dice the stickman pushed over."),
    "dice_land": ("Dice land", "The dice coming down on the felt after the throw."),
    "dice_bounce": ("Dice bounce", "Each knock of a die off the far wall's pyramids and the hops after (quieter for smaller ones)."),
    "room": ("Background room", "A loop under everything, on its own volume slider in the game's Settings."),
    # slots (placeholders from the library until Mike picks: see docs/slots/plan.md)
    "reel_spin": ("Slot reels spinning", "Under the reels while they spin (repeats until the last one stops)."),
    "reel_stop": ("Slot reel stops", "Each reel landing, left to right."),
    "reel_tease": ("Slot bonus tease", "Two scatters are showing: the last reels spin on, glowing."),
    "win_small": ("Slot line win", "A spin that wins: the lines light up."),
    "win_bangup": ("Slot win counting up", "The win meter counting up (repeats while it counts)."),
    "big_win": ("Slot big win", "BIG, MEGA or EPIC WIN fills the screen."),
    "feature_wilds": ("Random Wilds shot", "Each wild shot onto the reels."),
    "feature_reels": ("Wild Reels / Colossal", "The armadillo rolls down a reel, or reels fuse into a colossal one."),
    "feature_multiplier": ("Multiplier shown", "The 2x to 5x multiplier badge at the start of a spin."),
    "feature_upgrade": ("Symbol Upgrade", "Symbols flipping one step up the chain."),
    "instant_win": ("Instant Win barrel", "The Random Prize barrel bursting."),
    "bonus_trigger": ("Slot bonus starts", "The Trail Bonus, Combo Free Spins or the Jackpot Pick begins."),
    "trail_fire": ("Trail pistol fired", "The cylinder loads and spins before the armadillo moves."),
    "trail_hop": ("Trail hop", "Each space the armadillo hops."),
    "trail_coin": ("Trail coins collected", "Coins collected on the trail."),
    "trail_snake": ("Trail snake", "A snake strikes (a heart saves you, or the bonus ends)."),
    "pick_reveal": ("Jackpot coin turned", "Each coin turned over in the Jackpot Pick."),
    "jackpot_win": ("Slot jackpot won", "Three matching coins: a Mini, Minor, Major or Grand is won."),
}

_ks = "kenney-casino/"
_ki = "kenney-interface/"
DEFAULTS = {
    "deal": {"files": [f"edited/card-slide-{n}-soft.ogg" for n in range(2, 7)], "gain_db": 0.0},
    "flip": {"files": [_ks + "card-place-2.ogg"], "gain_db": -3.0},
    "shuffle": {"files": [_ks + "card-fan-1.ogg", _ks + "card-fan-2.ogg"], "gain_db": 0.0},
    "bet": {"files": [_ks + "chip-lay-1.ogg", _ks + "chip-lay-2.ogg"], "gain_db": 0.0},
    "payout": {"files": [_ks + f"chips-stack-{n}.ogg" for n in (1, 4, 5, 6)], "gain_db": 0.0},
    "sweep": {"files": [_ks + "chips-handle-1.ogg"], "gain_db": 0.0},
    "result": {"files": [_ki + "bong_001.ogg"], "gain_db": 0.0},
    "turn": {"files": [_ki + "confirmation_001.ogg"], "gain_db": 0.0},
    "tick": {"files": [_ki + "tick_001.ogg"], "gain_db": -4.0},
    "click": {"files": [_ki + "click_003.ogg"], "gain_db": -6.0},
    "ball_spin": {"files": ["roulette/poenia_709624-spin.ogg"], "gain_db": 0.0},
    "ball_drop": {"files": ["roulette/gamer500_682661-drop.ogg"], "gain_db": 0.0},
    "ball_rattle": {"files": ["roulette/f_ilippo_59194-rattle.ogg"], "gain_db": 0.0},
    "ball_hop": {"files": [f"roulette/f_ilippo_59194-hop-{n}.ogg" for n in range(1, 6)], "gain_db": 0.0},
    "dice_out": {"files": [_ks + "dice-grab-1.ogg", _ks + "dice-grab-2.ogg"], "gain_db": 0.0},
    "dice_land": {"files": [_ks + f"dice-throw-{n}.ogg" for n in (1, 2, 3)], "gain_db": 0.0},
    "dice_bounce": {"files": [_ks + f"die-throw-{n}.ogg" for n in (1, 2, 3, 4)], "gain_db": -3.0},
    "room": {"files": ["rooms/mhtaylor67_277444-loop.ogg"], "gain_db": 0.0},
    "reel_spin": {"files": [_ks + "dice-shake-1.ogg"], "gain_db": -6.0},
    "reel_stop": {"files": ["kenney-ui-audio/switch5.ogg", "kenney-ui-audio/switch6.ogg"], "gain_db": -3.0},
    "reel_tease": {"files": [_ki + "maximize_004.ogg"], "gain_db": 0.0},
    "win_small": {"files": [_ki + "confirmation_002.ogg"], "gain_db": 0.0},
    "win_bangup": {"files": [_ks + "chips-stack-3.ogg"], "gain_db": -3.0},
    "big_win": {"files": ["sparkles/LilMati_462093.ogg"], "gain_db": 0.0},
    "feature_wilds": {"files": ["pops/cogitollc-pop3.ogg"], "gain_db": 0.0},
    "feature_reels": {"files": [_ki + "maximize_008.ogg"], "gain_db": 0.0},
    "feature_multiplier": {"files": [_ki + "select_006.ogg"], "gain_db": 0.0},
    "feature_upgrade": {"files": ["sparkles/nomiqbomi_578800.ogg"], "gain_db": 0.0},
    "instant_win": {"files": [_ks + "chips-collide-3.ogg"], "gain_db": 0.0},
    "bonus_trigger": {"files": ["sparkles/MLaudio_511485.ogg"], "gain_db": 0.0},
    "trail_fire": {"files": [_ks + "dice-shake-2.ogg"], "gain_db": 0.0},
    "trail_hop": {"files": ["pops/wubitog-pop1.ogg"], "gain_db": -4.0},
    "trail_coin": {"files": [_ks + "chip-lay-3.ogg"], "gain_db": 0.0},
    "trail_snake": {"files": [_ki + "error_004.ogg"], "gain_db": 0.0},
    "pick_reveal": {"files": [_ki + "glass_002.ogg"], "gain_db": 0.0},
    "jackpot_win": {"files": ["sparkles/Fupicat_538147.ogg"], "gain_db": 0.0},
}


# Where each moment belongs on the maintenance page: "ui" (the game's own interface),
# "global" (any table) or "game:<key>" (one game's).
CATEGORIES = {
    "click": "ui", "turn": "ui", "tick": "ui",
    "deal": "global", "flip": "global", "shuffle": "global", "bet": "global", "payout": "global",
    "sweep": "global", "room": "global",
    "result": "game:pai_gow",
    "ball_spin": "game:roulette", "ball_drop": "game:roulette", "ball_rattle": "game:roulette", "ball_hop": "game:roulette",
    "dice_out": "game:craps", "dice_land": "game:craps", "dice_bounce": "game:craps",
    **{k: "game:slots" for k in ("reel_spin", "reel_stop", "reel_tease", "win_small", "win_bangup", "big_win",
                                 "feature_wilds", "feature_reels", "feature_multiplier", "feature_upgrade",
                                 "instant_win", "bonus_trigger", "trail_fire", "trail_hop", "trail_coin",
                                 "trail_snake", "pick_reveal", "jackpot_win")},
}
GAME_NAMES = {"pai_gow": "Pai Gow", "roulette": "Roulette", "craps": "Craps", "slots": "Slots"}
# And each library folder, so the library can be filtered the same way.
LIBRARY_GROUPS = {
    "kenney-interface": "ui", "kenney-ui-audio": "ui", "owlish-clicks": "ui", "lokif-gui": "ui",
    "qubodup-clicks": "ui", "clocks": "ui", "pops": "ui", "sparkles": "ui",
    "kenney-casino": "global", "edited": "global", "rooms": "global",
    "roulette": "game:roulette",
    "uploads": "uploads",
}


class SoundError(ValueError):
    """A request the sound settings can't take (shown to the page as-is)."""


class SoundBoard:
    def __init__(self, data_dir: Path, library_dir: Path = LIBRARY_DIR):
        self.library_dir = library_dir
        self.uploads_dir = data_dir / "sounds" / "uploads"
        self.path = data_dir / "sounds.json"
        self.version, self.moments = 0, {}
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                self.version = int(saved.get("version", 0))
                self.moments = {k: v for k, v in saved.get("moments", {}).items() if k in MOMENTS}
            except (ValueError, OSError):
                pass

    # ------------------------------------------------------------- reading
    def choice(self, key: str) -> dict:
        chosen = self.moments.get(key) or DEFAULTS[key]
        return {"files": [f for f in chosen["files"] if self.file_path(f)], "gain_db": float(chosen["gain_db"])}

    def manifest(self) -> dict:
        """What the game loads: each moment's files (as URLs) and volume trim."""
        def url(f):  # the file's change time on the end, so a replaced upload isn't served stale
            return f"/sound-files/{f}?v={int(self.file_path(f).stat().st_mtime)}"
        return {"version": self.version,
                "moments": {k: {"files": [url(f) for f in self.choice(k)["files"]],
                                "gain_db": self.choice(k)["gain_db"]} for k in MOMENTS}}

    def overview(self) -> dict:
        """Everything the maintenance page shows."""
        return {"version": self.version,
                "moments": [{"key": k, "title": t, "when": w, "category": CATEGORIES.get(k, "global"), **self.choice(k),
                             "is_default": k not in self.moments} for k, (t, w) in MOMENTS.items()],
                "library": self.library(), "games": GAME_NAMES}

    def library(self) -> list[dict]:
        items = []
        for root, prefix in ((self.library_dir, ""), (self.uploads_dir, "uploads/")):
            if not root.exists():
                continue
            for f in sorted(root.rglob("*")):
                if f.is_file() and f.suffix.lower() in PLAYABLE:
                    rel = prefix + f.relative_to(root).as_posix()
                    group = rel.split("/")[0]
                    items.append({"id": rel, "group": group, "category": LIBRARY_GROUPS.get(group, "global"),
                                  "name": f.stem, "bytes": f.stat().st_size})
        return items

    def file_path(self, sound_id: str) -> Path | None:
        """The file a sound id names, or None -- never anything outside the library."""
        if not isinstance(sound_id, str) or "\\" in sound_id or sound_id.startswith("/"):
            return None
        root, rel = (self.uploads_dir, sound_id[len("uploads/"):]) if sound_id.startswith("uploads/") \
            else (self.library_dir, sound_id)
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.suffix.lower() not in PLAYABLE:
            return None
        return path

    # ------------------------------------------------------------- changing
    def set_choice(self, key: str, files, gain_db) -> dict:
        if key not in MOMENTS:
            raise SoundError(f"There's no moment called {key!r}.")
        if not isinstance(files, list) or not files:
            raise SoundError("Pick at least one sound (remove the moment's sounds by resetting it instead).")
        missing = [f for f in files if not self.file_path(f)]
        if missing:
            raise SoundError(f"Not in the library: {', '.join(map(str, missing))}")
        try:
            gain = round(min(max(float(gain_db), GAIN_RANGE[0]), GAIN_RANGE[1]), 1)
        except (TypeError, ValueError):
            raise SoundError("The volume trim has to be a number of dB.")
        self.moments[key] = {"files": list(dict.fromkeys(files)), "gain_db": gain}
        self._save()
        return self.choice(key)

    def reset(self, key: str | None = None):
        if key is None:
            self.moments = {}
        elif key in MOMENTS:
            self.moments.pop(key, None)
        else:
            raise SoundError(f"There's no moment called {key!r}.")
        self._save()

    def upload(self, filename: str, data: bytes) -> dict:
        """Add a file to uploads/. Formats the game can't load are converted to .ogg (needs ffmpeg)."""
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).stem).strip(".-")[:60] or "sound"
        ext = Path(filename).suffix.lower()
        if not data:
            raise SoundError("That file is empty.")
        if len(data) > MAX_UPLOAD:
            raise SoundError("That file is over 20 MB; trim it first.")
        if ext not in PLAYABLE | CONVERTIBLE:
            raise SoundError(f"Can't use {ext or 'that'} files: upload .ogg, .mp3, .wav (or .flac, .m4a, .opus).")
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        if ext in PLAYABLE:
            target = self.uploads_dir / f"{stem}{ext}"
            target.write_bytes(data)
        else:
            if not shutil.which("ffmpeg"):
                raise SoundError("Converting that format needs ffmpeg on the server; upload .ogg, .mp3 or .wav.")
            source = self.uploads_dir / f".incoming{ext}"
            source.write_bytes(data)
            target = self.uploads_dir / f"{stem}.ogg"
            try:
                subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(source),
                                "-c:a", "libvorbis", "-q:a", "5", str(target)], check=True, timeout=60)
            except (subprocess.SubprocessError, OSError):
                target.unlink(missing_ok=True)
                raise SoundError("ffmpeg couldn't read that file.")
            finally:
                source.unlink(missing_ok=True)
        rel = "uploads/" + target.name
        return {"id": rel, "group": "uploads", "name": target.stem, "bytes": target.stat().st_size}

    def delete_upload(self, sound_id: str):
        path = self.file_path(sound_id) if sound_id.startswith("uploads/") else None
        if path is None:
            raise SoundError("Only uploaded sounds can be deleted.")
        in_use = [k for k in MOMENTS if sound_id in self.choice(k)["files"]]
        if in_use:
            raise SoundError(f"Still used for: {', '.join(MOMENTS[k][0] for k in in_use)}. Swap it out first.")
        path.unlink()

    def _save(self):
        self.version += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": self.version, "moments": self.moments}, indent=1))
        tmp.replace(self.path)
