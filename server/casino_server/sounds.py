"""
Which sound plays for each game moment -- edited on the admin page's Sounds tab
(/maintenance#sounds) and fetched by every client when it starts and whenever it
changes, so trying a different sound needs no rebuild.

Sound sets
----------
The sounds are a tree of sets, each inheriting from the one above:

    casino                      the whole casino: the interface, the room, cards and chips
      blackjack, roulette, ...  one per table game (floor.GAMES)
      slots                     every slot machine
        slots.armadillo         one per slot machine (its variant, slots/variants.py)

A moment (MOMENTS) is defined in one set, its `home`, and can be given its own sounds
in any set below that whose game uses it: Blackjack can have its own card deal,
Armadillo Goes West its own reel stop. A set that doesn't set a moment plays its
parent's. Each table plays from its game's set (TABLE_SETS).

FACTORY is what each set starts with. Changes made on the page go in
<data dir>/sounds.json and win over it:

    {"version": 7, "sets": {"casino": {"deal": {"files": [...], "gain_db": 0.0}},
                            "slots.armadillo": {"reel_stop": {"inherit": true}}}}

`{"inherit": true}` hands a moment the factory gave a set back to its parent, and
`"files": []` silences it there (and below, unless a set below gives it a sound). A moment
with several files picks one at random each time it plays; `gain_db` trims its volume.

The library is the CC0 collection in server/sound_library/ (read-only, see its
LIBRARY.md) plus uploads in <data dir>/sounds/uploads/. A sound is named by its path in
the library, e.g. "kenney-casino/card-fan-1.ogg" or "uploads/my-chip.ogg".
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from casino_server import floor
from casino_server.slots.variants import VARIANTS

LIBRARY_DIR = Path(__file__).resolve().parents[1] / "sound_library"
PLAYABLE = {".ogg", ".mp3", ".wav"}          # what the Godot client can load at runtime
CONVERTIBLE = {".flac", ".m4a", ".aac", ".opus", ".webm", ".aiff", ".aif"}  # turned into .ogg on upload
MAX_UPLOAD = 20 * 1024 * 1024
GAIN_RANGE = (-30.0, 12.0)


# ------------------------------------------------------------------ the sets
def _sets() -> dict:
    """A set for every game the casino has, on the floor or not (so a table taken off the floor keeps its sounds)."""
    sets = {"casino": {"name": "Whole casino", "parent": None, "group": ""}}
    for game, name in floor.GAMES.items():
        sets[game] = {"name": name, "parent": "casino", "group": "Table games"}
    sets["slots"] = {"name": "Every slot machine", "parent": "casino", "group": "Slot machines"}
    for vid, v in VARIANTS.items():
        sets["slots." + vid] = {"name": v.name, "parent": "slots", "group": "Slot machines"}
    return sets


# The sets, which set each table plays from, and which sets a moment's `uses` names. Filled by refresh_sets(), now
# and again once built slots (slot_builds.py) have joined the floor; updated in place, so other modules' references
# stay good.
SETS: dict = {}
TABLE_SETS: dict = {}
_TABLE_GAMES: set = set()
_MACHINES: set = set()
USERS: dict = {}


def refresh_sets():
    SETS.clear()
    SETS.update(_sets())
    TABLE_SETS.clear()
    TABLE_SETS.update({tid: ("slots." + cfg["variant"] if cfg["game"] == "slots" else cfg["game"])
                       for tid, cfg in floor.TABLES.items()})
    _TABLE_GAMES.clear()
    _TABLE_GAMES.update(k for k, s in SETS.items() if s["group"] == "Table games")
    _MACHINES.clear()
    _MACHINES.update(k for k in SETS if k.startswith("slots."))
    USERS.update({
        "all": _TABLE_GAMES | _MACHINES | {"slots"},
        "tables": set(_TABLE_GAMES),
        "cards": _TABLE_GAMES - {"roulette", "craps"},
        "pai_gow": {k for k in _TABLE_GAMES if k.startswith("pai_gow")},
        "slots": set(_MACHINES),
        "none": set(),
    })


refresh_sets()

# ------------------------------------------------------------------ the moments
# Page order. Each: title, when it plays, its section on the page, its home set, which
# sets below home use it (a USERS key), and whether it loops while it lasts.
SECTIONS = ["Interface", "Room", "Cards", "Chips", "Wheel", "Dice",
            "Spin", "Wins", "Features", "Bonuses", "Trail Bonus", "Battle Bonus", "Voyage Bonus", "Expedition Bonus",
            "Jackpot Pick"]


def _m(title, when, section, home="casino", uses="none", loop=False):
    return {"title": title, "when": when, "section": section, "home": home, "uses": uses, "loop": loop}


MOMENTS = {
    "click": _m("Button press", "Every button in the game's bar and panels, and a slot machine's buttons.", "Interface", uses="all"),
    "turn": _m("Your turn", "Your decision starts, or the Pai Gow sorter opens.", "Interface", uses="tables"),
    "tick": _m("Timer running out", "Each of the last five seconds of a timer you're up against.", "Interface", uses="tables"),
    "room": _m("Background room", "A loop under everything, on its own volume slider in the game's Settings.", "Room", loop=True),
    "deal": _m("Card dealt", "Each batch of cards that leaves together: a 3-card packet at Three Card Poker, "
                             "a 7-card hand at Pai Gow, every card at Blackjack.", "Cards", uses="cards"),
    "flip": _m("Card turned face up", "The dealer's reveal, hands at settlement, Blackjack cards.", "Cards", uses="cards"),
    "shuffle": _m("Shuffler fed", "Cards going back through the shuffler after a hand, and a new Blackjack shoe.", "Cards", uses="cards"),
    "result": _m("Pai Gow result mark", "Each Pai Gow win or lose mark popping in.", "Cards", uses="pai_gow"),
    "bet": _m("Chip placed on a bet", "Anyone at the table putting chips on a spot.", "Chips", uses="tables"),
    "payout": _m("Winnings paid", "Chips from the tray placed beside a winning bet.", "Chips", uses="tables"),
    "sweep": _m("Losing bets swept", "The dealer taking chips back to the tray.", "Chips", uses="tables"),
    # roulette
    "ball_spin": _m("Ball launched", "The dealer spins the ball: it rolls round the track, slowing (about 6 seconds).", "Wheel", "roulette"),
    "ball_drop": _m("Ball drops", "The ball leaves the track and clatters off a deflector.", "Wheel", "roulette"),
    "ball_rattle": _m("Ball skids", "The ball clattering over the frets as it reaches the pockets (again every 1.6 s while the skid lasts).", "Wheel", "roulette"),
    "ball_hop": _m("Ball hops", "Each hop landing as the ball bounces between pockets, and the last click as it settles.", "Wheel", "roulette"),
    # craps
    "dice_out": _m("Dice pushed out", "The shooter picks up the dice the stickman pushed over.", "Dice", "craps"),
    "dice_land": _m("Dice land", "The dice coming down on the felt after the throw.", "Dice", "craps"),
    "dice_bounce": _m("Dice bounce", "Each knock of a die off the far wall's pyramids and the hops after (quieter for smaller ones).", "Dice", "craps"),
    # slot machines
    "spin_press": _m("Spin pressed", "The Spin button (or Space, or an auto spin) starting a spin.", "Spin", "slots", "slots"),
    "reel_spin": _m("Reels spinning", "Under the reels from the start of a spin until the last one stops.", "Spin", "slots", "slots", True),
    "reel_stop": _m("Reel stops", "Each reel landing, left to right, each a step higher.", "Spin", "slots", "slots"),
    "scatter_land": _m("Bonus symbol lands", "A reel stopping with a bonus wagon or free-spin pistols showing; the second and third ring higher.", "Spin", "slots", "slots"),
    "reel_tease": _m("Bonus tease", "Two bonus symbols are showing: the next reel spins on, glowing (repeats while it does).", "Spin", "slots", "slots", True),
    "win_small": _m("Line win", "A spin that wins: the lines light up.", "Wins", "slots", "slots"),
    "win_repeat": _m("Repeat win", "The line wins paying again (Repeat Win).", "Wins", "slots", "slots"),
    "win_bangup": _m("Win counting up", "Under the win meter while it counts up.", "Wins", "slots", "slots", True),
    "win_end": _m("Win counted", "The win meter reaching the total.", "Wins", "slots", "slots"),
    "big_win": _m("Big win", "BIG, MEGA or EPIC WIN fills the screen (and nearby, when someone else's machine does).", "Wins", "slots", "slots"),
    "big_win_loop": _m("Big win coins", "Under the big win screen while its total counts up.", "Wins", "slots", "slots", True),
    "cash_out": _m("Cash out", "Leaving the machine with your credit.", "Wins", "slots", "slots"),
    "feature_banner": _m("Feature announced", "Each feature's banner as the reels start: Colossal Reels, Wild Reels, Random Wilds, Multiplier.", "Features", "slots", "slots"),
    "feature_multiplier": _m("Multiplier", "The 2x to 5x multiplier badge lighting up.", "Features", "slots", "slots"),
    "feature_reels": _m("Wild Reels / Colossal", "The armadillo rolling down a reel, or reels fusing into a colossal one.", "Features", "slots", "slots"),
    "feature_wilds": _m("Random Wild shot", "Each wild shot onto the reels.", "Features", "slots", "slots"),
    "feature_upgrade": _m("Symbol Upgrade", "Symbols flipping one step up the chain.", "Features", "slots", "slots"),
    "instant_win": _m("Instant Win barrel", "The Random Prize barrel bursting.", "Features", "slots", "slots"),
    "bonus_trigger": _m("Bonus starts", "The Trail Bonus, the Combo Free Games or the Jackpot Pick begins (the battle, the voyage and the expedition have their own).", "Bonuses", "slots", "slots"),
    "free_spin": _m("Free game", "Each Combo Free Game starting.", "Bonuses", "slots", "slots"),
    "bonus_end": _m("Bonus paid", "The total of a Trail Bonus or the free games coming up.", "Bonuses", "slots", "slots"),
    "trail_fire": _m("Pistol loaded", "The cylinder loading and spinning before the armadillo moves.", "Trail Bonus", "slots", "slots"),
    "trail_hop": _m("Hop", "Each space the armadillo hops.", "Trail Bonus", "slots", "slots"),
    "trail_coin": _m("Coins collected", "Coins collected on the trail (a crate's too, and the prizepot).", "Trail Bonus", "slots", "slots"),
    "trail_special": _m("Special space", "Landing on double, spin upgrade, lightning roll, forward or back.", "Trail Bonus", "slots", "slots"),
    "trail_heart": _m("Heart", "A heart picked up, or one saving you from a snake.", "Trail Bonus", "slots", "slots"),
    "trail_snake": _m("Snake", "A snake strikes (the bonus ends unless a heart saves you).", "Trail Bonus", "slots", "slots"),
    "battle_alert": _m("Red alert", "The battle bonus beginning, and its boss arriving.", "Battle Bonus", "slots", "slots"),
    "battle_phaser": _m("Fire", "Each shot fired at an enemy ship or the boss.", "Battle Bonus", "slots", "slots"),
    "battle_boom": _m("Explosion", "A ship destroyed, the boss hit or destroyed, or your shields failing.", "Battle Bonus", "slots", "slots"),
    "battle_hit": _m("Shields hit", "An enemy ship cloaking and firing back.", "Battle Bonus", "slots", "slots"),
    "battle_wave": _m("Wave cleared", "Every ship in a wave destroyed: its reward, and shields restored.", "Battle Bonus", "slots", "slots"),
    "voyage_start": _m("Set sail", "The voyage bonus beginning.", "Voyage Bonus", "slots", "slots"),
    "voyage_sail": _m("Sailing", "The ship sailing to the next island (and to the final one).", "Voyage Bonus", "slots", "slots"),
    "voyage_find": _m("Found", "A prize, a key or an artefact found on an island.", "Voyage Bonus", "slots", "slots"),
    "voyage_sink": _m("Sunk", "Skull Island sinking the ship.", "Voyage Bonus", "slots", "slots"),
    "voyage_trade": _m("Trade", "A deal at Port Royal: something bought, or the relics sold.", "Voyage Bonus", "slots", "slots"),
    "voyage_chest": _m("Treasure", "Each part of the legendary treasure paying out on the final island.", "Voyage Bonus", "slots", "slots"),
    "expedition_start": _m("Course plotted", "The expedition bonus beginning, and a route chosen.", "Expedition Bonus", "slots", "slots"),
    "expedition_warp": _m("Warp", "The ship jumping to the next sector (and to the final destination).", "Expedition Bonus", "slots", "slots"),
    "expedition_find": _m("Found", "A planet explored: credits, a multiplier, an artefact or free games.", "Expedition Bonus", "slots", "slots"),
    "expedition_tech": _m("Tech", "A Scanner, Shuttle or Shields found, or a Scanner sweeping a sector.", "Expedition Bonus", "slots", "slots"),
    "expedition_hazard": _m("Hazard", "A hazard ending the expedition (or Shields absorbing it, or the shuttle lost).", "Expedition Bonus", "slots", "slots"),
    "expedition_final": _m("Destination", "The final destination paying (or a Wormhole opening to it).", "Expedition Bonus", "slots", "slots"),
    "pick_reveal": _m("Coin turned", "Each coin turned over in the Jackpot Pick.", "Jackpot Pick", "slots", "slots"),
    "jackpot_win": _m("Jackpot won", "Three matching coins: a Mini, Minor, Major or Grand (and nearby, when someone else wins one).", "Jackpot Pick", "slots", "slots"),
}


# ------------------------------------------------------------------ factory settings
def _c(*files, gain=0.0):
    return {"files": list(files), "gain_db": gain}


_ks, _ki, _sl, _w = "kenney-casino/", "kenney-interface/", "slots/", "western/"
FACTORY = {
    "casino": {
        "click": _c(_ki + "click_003.ogg", gain=-6.0),
        "turn": _c(_ki + "confirmation_001.ogg"),
        "tick": _c(_ki + "tick_001.ogg", gain=-4.0),
        "room": _c("rooms/mhtaylor67_277444-loop.ogg"),
        "deal": _c(*[f"edited/card-slide-{n}-soft.ogg" for n in range(2, 7)]),
        "flip": _c(_ks + "card-place-2.ogg", gain=-3.0),
        "shuffle": _c(_ks + "card-fan-1.ogg", _ks + "card-fan-2.ogg"),
        "result": _c(_ki + "bong_001.ogg"),
        "bet": _c(_ks + "chip-lay-1.ogg", _ks + "chip-lay-2.ogg"),
        "payout": _c(*[_ks + f"chips-stack-{n}.ogg" for n in (1, 4, 5, 6)]),
        "sweep": _c(_ks + "chips-handle-1.ogg"),
    },
    "roulette": {
        "ball_spin": _c("roulette/poenia_709624-spin.ogg"),
        "ball_drop": _c("roulette/gamer500_682661-drop.ogg"),
        "ball_rattle": _c("roulette/f_ilippo_59194-rattle.ogg"),
        "ball_hop": _c(*[f"roulette/f_ilippo_59194-hop-{n}.ogg" for n in range(1, 6)]),
    },
    "craps": {
        "dice_out": _c(_ks + "dice-grab-1.ogg", _ks + "dice-grab-2.ogg"),
        "dice_land": _c(*[_ks + f"dice-throw-{n}.ogg" for n in (1, 2, 3)]),
        "dice_bounce": _c(*[_ks + f"die-throw-{n}.ogg" for n in (1, 2, 3, 4)], gain=-3.0),
    },
    # Every slot machine: an electronic Vegas cabinet. A new machine starts with these.
    "slots": {
        "spin_press": _c(_sl + "David819_668435-reels-begin.ogg", gain=-9.5),
        "reel_spin": _c(_sl + "Johnmode_860886-spin-loop.ogg", gain=-16.0),
        "reel_stop": _c(_sl + "David819_668434-reel-stop.ogg", gain=1.0),
        "scatter_land": _c(_sl + "chennes_376807-ding.ogg", gain=0.5),
        "reel_tease": _c(_sl + "bigjoedrummer_77305-roll-loop.ogg", gain=-14.5),
        "win_small": _c(_sl + "FunWithSound_456965-glockenspiel.ogg", gain=-6.5),
        "win_repeat": _c(_sl + "steaq_387232-badge-coin.ogg", gain=-6.0),
        "win_bangup": _c(_sl + "KerDwyn_839951-count-loop.ogg", gain=-15.5),
        "win_end": _c(_sl + "MLaudio_511484-success-bell.ogg", gain=-10.5),
        "big_win": _c(_sl + "Johnmode_860886-winner.ogg", gain=-9.0),
        "big_win_loop": _c(_sl + "jack126guy_361346-coins-loop.ogg", gain=-8.5),
        "cash_out": _c(_sl + "Zott820_209578-cash-register.ogg", gain=-6.5),
        "feature_banner": _c(_sl + "qubodup_60013-whoosh.ogg", gain=-8.0),
        "feature_multiplier": _c("kenney-digital/powerUp2.ogg", gain=-6.0),
        "feature_reels": _c(_ki + "maximize_008.ogg", gain=-8.0),
        "feature_wilds": _c("pops/cogitollc-pop3.ogg", gain=-7.0),
        "feature_upgrade": _c("sparkles/nomiqbomi_578800.ogg", gain=1.0),
        "instant_win": _c(_sl + "rolandseer_443334-money.ogg", gain=-6.0),
        "bonus_trigger": _c(_sl + "IENBA_656643-reward.ogg", gain=-9.5),
        "free_spin": _c(_sl + "GameAudio_220184-win-spacey.ogg", gain=-7.5),
        "bonus_end": _c(_sl + "Kastenfrosch_162458-win.ogg", gain=-7.5),
        "trail_fire": _c(_ks + "dice-shake-2.ogg", gain=-3.5),
        "trail_hop": _c("pops/wubitog-pop1.ogg", gain=-0.5),
        "trail_coin": _c(_sl + "Gerent_558991-coins.ogg", gain=2.0),
        "trail_special": _c("kenney-digital/threeTone1.ogg", gain=-15.0),
        "trail_heart": _c("sparkles/LilMati_462095.ogg", gain=-12.5),
        "trail_snake": _c(_ki + "error_004.ogg", gain=-4.0),
        "battle_alert": _c("kenney-digital/twoTone1.ogg", gain=-10.0),
        "battle_phaser": _c("kenney-digital/phaserDown1.ogg", "kenney-digital/phaserDown3.ogg", gain=-8.0),
        "battle_boom": _c(*[f"kenney-digital/spaceTrash{n}.ogg" for n in (1, 2, 3)], gain=-2.0),
        "battle_hit": _c(*[f"kenney-impact/impactMetal_heavy_00{n}.ogg" for n in range(3)], gain=-6.0),
        "battle_wave": _c("kenney-digital/powerUp3.ogg", gain=-8.0),
        "voyage_start": _c("kenney-impact/impactBell_heavy_000.ogg", gain=-8.0),
        "voyage_sail": _c(*[f"kenney-rpg/creak{n}.ogg" for n in (1, 2, 3)], gain=-6.0),
        "voyage_find": _c("kenney-rpg/handleCoins.ogg", "kenney-rpg/handleCoins2.ogg", gain=-4.0),
        "voyage_sink": _c(*[f"kenney-impact/impactWood_heavy_00{n}.ogg" for n in range(3)], gain=-2.0),
        "voyage_trade": _c("kenney-rpg/metalLatch.ogg", gain=-6.0),
        "voyage_chest": _c(_sl + "chennes_376807-ding.ogg", gain=-6.0),
        "expedition_start": _c("kenney-digital/phaseJump1.ogg", gain=-8.0),
        "expedition_warp": _c("kenney-digital/zapThreeToneUp.ogg", gain=-10.0),
        "expedition_find": _c("kenney-digital/powerUp1.ogg", "kenney-digital/powerUp2.ogg", gain=-8.0),
        "expedition_tech": _c("kenney-digital/threeTone2.ogg", gain=-10.0),
        "expedition_hazard": _c("kenney-digital/spaceTrash4.ogg", "kenney-digital/spaceTrash5.ogg", gain=-3.0),
        "expedition_final": _c(_sl + "GameAudio_220184-win-spacey.ogg", gain=-7.0),
        "pick_reveal": _c(_ki + "glass_002.ogg", gain=-1.0),
        "jackpot_win": _c(_sl + "univ_lyon3_367462-jackpot-bell.ogg", gain=-5.5),
    },
    # Armadillo Goes West: wooden reels, six-shooters, banjo and a rattlesnake.
    "slots.armadillo": {
        "spin_press": _c(_w + "Dredile_111676-revolver-cock.ogg", gain=-5.5),
        "reel_spin": _c("edited/reel-ratchet-wood-loop.ogg", gain=-13.0),
        "reel_stop": _c(*[f"kenney-impact/impactWood_medium_00{n}.ogg" for n in range(5)], gain=-6.5),
        "scatter_land": _c(_w + "LilMati_481151-cowbells.ogg", gain=-3.5),
        "win_small": _c(_w + "Fupicat_521640-win-banjo.ogg", gain=-6.0),
        "win_repeat": _c(_w + "rentless_558140-banjo-plucks.ogg", gain=-5.0),
        "win_bangup": _c(_sl + "euanmj_442876-coins-loop.ogg", gain=-14.0),
        "win_end": _c(_w + "Neotone_75339-cowbell.ogg", gain=-8.0),
        "big_win": _c(_w + "vdublin_428150-saloon-piano.ogg", gain=-4.5),
        "feature_banner": _c(_w + "SciFiSounds_529925-whip.ogg", gain=-6.5),
        "feature_multiplier": _c(_w + "wjb_88_828860-harmonica-trill.ogg", gain=-6.5),
        "feature_reels": _c(_w + "martian_403002-slide-whistle.ogg", gain=-11.0),
        "feature_wilds": _c(_w + "Diboz_213925-pistol-ricochet.ogg", _w + "Bird_man_275151-gunshot.ogg", gain=-12.5),
        "instant_win": _c("kenney-impact/impactWood_heavy_002.ogg", gain=-5.0),
        "bonus_trigger": _c(_w + "Dandertuts_845920-yeehaw.ogg", gain=-14.5),
        "bonus_end": _c(_w + "Lynx_5969_404059-honky-tonk.ogg", gain=-8.0),
        "trail_fire": _c(_w + "jhka_139001-revolver-ratchet.ogg", gain=-1.5),
        "trail_hop": _c(_w + "wjb_88_828863-spur-step.ogg", gain=2.0),
        "trail_special": _c(_w + "CaptainSiberia_82545-jaw-harp.ogg", gain=-6.0),
        "trail_heart": _c(_w + "vacuumfan7072_505710-reed-pling.ogg", gain=2.0),
        "trail_snake": _c(_w + "logee72_559759-rattlesnake.ogg", gain=2.0),
    },
}

# Library folders: what's in each (the picker's folder list), and which sections it suits.
FOLDERS = {
    "slots": ("Slot machines: reels, coins, wins, jackpots", ["Spin", "Wins", "Features", "Bonuses", "Trail Bonus", "Jackpot Pick", "Battle Bonus", "Voyage Bonus",
                                                             "Expedition Bonus"]),
    "western": ("Wild West: guns, banjo, harmonica, snakes, horses", ["Spin", "Wins", "Features", "Bonuses", "Trail Bonus"]),
    "kenney-jingles": ("Kenney music jingles", ["Wins", "Bonuses", "Jackpot Pick", "Battle Bonus", "Voyage Bonus"]),
    "kenney-impact": ("Kenney impacts: wood, metal, bells", ["Spin", "Features", "Trail Bonus", "Dice", "Battle Bonus", "Voyage Bonus"]),
    "kenney-rpg": ("Kenney coins, latches and creaks", ["Wins", "Chips", "Trail Bonus", "Features", "Voyage Bonus"]),
    "kenney-digital": ("Kenney digital blips and power-ups", ["Spin", "Features", "Bonuses", "Trail Bonus", "Interface", "Battle Bonus",
                                                                   "Expedition Bonus"]),
    "kenney-casino": ("Kenney casino: cards, chips, dice", ["Cards", "Chips", "Dice", "Wins"]),
    "edited": ("Edited card slides, and the wooden reel loop", ["Cards", "Spin"]),
    "rooms": ("Casino floor recordings", ["Room"]),
    "roulette": ("Roulette wheel and ball", ["Wheel"]),
    "sparkles": ("Sparkles and chimes", ["Features", "Wins", "Bonuses", "Trail Bonus", "Jackpot Pick"]),
    "pops": ("Pops", ["Interface", "Features", "Trail Bonus", "Cards"]),
    "kenney-interface": ("Kenney interface", ["Interface", "Features", "Wins", "Trail Bonus", "Jackpot Pick"]),
    "kenney-ui-audio": ("Kenney UI clicks and switches", ["Interface", "Spin"]),
    "owlish-clicks": ("Clicks, snaps and switches", ["Interface", "Spin"]),
    "lokif-gui": ("Menu chimes", ["Interface"]),
    "qubodup-clicks": ("Button and mechanical clicks", ["Interface", "Spin"]),
    "clocks": ("A ticking clock", ["Interface"]),
    "uploads": ("Your uploads", SECTIONS),
}


def _ancestors(set_key: str) -> list[str]:
    out, s = [], set_key
    while s:
        out.append(s)
        s = SETS[s]["parent"]
    return out


def shows(set_key: str, key: str) -> bool:
    """Whether a moment can be set in a set: its home, or a set below that whose game uses it."""
    m = MOMENTS.get(key)
    if m is None or set_key not in SETS:
        return False
    return set_key == m["home"] or (set_key in USERS[m["uses"]] and m["home"] in _ancestors(set_key))


class SoundError(ValueError):
    """A request the sound settings can't take (shown to the page as-is)."""


class SoundBoard:
    def __init__(self, data_dir: Path, library_dir: Path = LIBRARY_DIR):
        self.library_dir = library_dir
        self.uploads_dir = data_dir / "sounds" / "uploads"
        self.path = data_dir / "sounds.json"
        self.version, self.saved = 0, {}
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                self.version = int(saved.get("version", 0))
                if "sets" in saved:
                    for s, moments in saved["sets"].items():
                        for k, e in moments.items():
                            if shows(s, k) and isinstance(e, dict):
                                self.saved.setdefault(s, {})[k] = e
                else:  # before sets: one choice per moment, which now belongs to its home set
                    for k, e in saved.get("moments", {}).items():
                        if k in MOMENTS and isinstance(e, dict):
                            self.saved.setdefault(MOMENTS[k]["home"], {})[k] = e
            except (ValueError, OSError, AttributeError):
                pass

    # ------------------------------------------------------------- reading
    def own(self, set_key: str, key: str) -> dict | None:
        """The set's own choice for a moment (saved, else factory), or None if it plays its parent's."""
        e = self.saved.get(set_key, {}).get(key)
        if e is None:
            e = FACTORY.get(set_key, {}).get(key)
        if e is None or e.get("inherit"):
            return None
        files = e.get("files", [])
        kept = [f for f in files if self.file_path(f)]
        if files and not kept:
            return None   # its files have gone from the library: the set above plays, rather than silence
        return {"files": kept, "gain_db": float(e.get("gain_db", 0.0))}   # [] is chosen silence

    def resolve(self, set_key: str, key: str) -> tuple[dict, str | None]:
        """What a moment plays in a set, and the set that decides it."""
        for s in _ancestors(set_key):
            e = self.own(s, key)
            if e is not None:
                return e, s
        return {"files": [], "gain_db": 0.0}, None

    def row(self, set_key: str, key: str) -> dict:
        """One moment as the page shows it in a set."""
        chosen, source = self.resolve(set_key, key)
        return {"key": key, "own": source == set_key, "from": source, **chosen,
                "changed": key in self.saved.get(set_key, {}),
                "can_inherit": set_key != MOMENTS[key]["home"]}

    def manifest(self) -> dict:
        """What the game loads: each set's own moments (files as URLs, and the volume trim), each
        set's parent, and which set each table plays from. A moment a set doesn't have comes from
        the nearest set above it that does."""
        def url(f):  # the file's change time on the end, so a replaced upload isn't served stale
            return f"/sound-files/{f}?v={int(self.file_path(f).stat().st_mtime)}"
        sets = {}
        for s, info in SETS.items():
            moments = {}
            for k in MOMENTS:
                e = self.own(s, k) if shows(s, k) else None
                if e is not None:
                    moments[k] = {"files": [url(f) for f in e["files"]], "gain_db": e["gain_db"]}
            sets[s] = {"parent": info["parent"], "moments": moments}
        return {"version": self.version, "sets": sets, "tables": TABLE_SETS}

    def overview(self) -> dict:
        """Everything the admin page shows."""
        return {
            "version": self.version, "sections": SECTIONS,
            "moments": {k: {key: m[key] for key in ("title", "when", "section", "home", "loop")} for k, m in MOMENTS.items()},
            "sets": [{"key": s, **info, "moments": [self.row(s, k) for k in MOMENTS if shows(s, k)]} for s, info in SETS.items()],
            "folders": {f: {"label": label, "sections": secs} for f, (label, secs) in FOLDERS.items()},
            "library": self.library(),
        }

    def library(self) -> list[dict]:
        items = []
        for root, prefix in ((self.library_dir, ""), (self.uploads_dir, "uploads/")):
            if not root.exists():
                continue
            for f in sorted(root.rglob("*")):
                if f.is_file() and f.suffix.lower() in PLAYABLE:
                    rel = prefix + f.relative_to(root).as_posix()
                    items.append({"id": rel, "group": rel.split("/")[0], "name": f.stem, "bytes": f.stat().st_size})
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
    def _check(self, set_key: str, key: str):
        if set_key not in SETS:
            raise SoundError(f"There's no sound set called {set_key!r}.")
        if key not in MOMENTS:
            raise SoundError(f"There's no moment called {key!r}.")
        if not shows(set_key, key):
            raise SoundError(f"{SETS[set_key]['name']} doesn't use {MOMENTS[key]['title']}.")

    def set_choice(self, set_key: str, key: str, files, gain_db) -> dict:
        self._check(set_key, key)
        if not isinstance(files, list):
            raise SoundError("Expected a list of sounds (an empty one for silence).")
        missing = [f for f in files if not self.file_path(f)]
        if missing:
            raise SoundError(f"Not in the library: {', '.join(map(str, missing))}")
        try:
            gain = round(min(max(float(gain_db), GAIN_RANGE[0]), GAIN_RANGE[1]), 1)
        except (TypeError, ValueError):
            raise SoundError("The volume trim has to be a number of dB.")
        choice = {"files": list(dict.fromkeys(files)), "gain_db": gain}
        if FACTORY.get(set_key, {}).get(key) == choice:
            self.saved.get(set_key, {}).pop(key, None)    # back to how it came
        else:
            self.saved.setdefault(set_key, {})[key] = choice
        self._save()
        return self.row(set_key, key)

    def inherit(self, set_key: str, key: str) -> dict:
        """Play the parent set's sounds for this moment."""
        self._check(set_key, key)
        if set_key == MOMENTS[key]["home"]:
            raise SoundError(f"{MOMENTS[key]['title']} starts in {SETS[set_key]['name']}: there's nothing above it to use.")
        if key in FACTORY.get(set_key, {}):
            self.saved.setdefault(set_key, {})[key] = {"inherit": True}
        else:
            self.saved.get(set_key, {}).pop(key, None)
        self._save()
        return self.row(set_key, key)

    def reset(self, set_key: str | None = None, key: str | None = None):
        """Back to how it came: one moment in one set, a whole set, or everything."""
        if set_key is None:
            self.saved = {}
        elif key is None:
            if set_key not in SETS:
                raise SoundError(f"There's no sound set called {set_key!r}.")
            self.saved.pop(set_key, None)
        else:
            self._check(set_key, key)
            self.saved.get(set_key, {}).pop(key, None)
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
        in_use = [f"{MOMENTS[k]['title']} ({SETS[s]['name']})" for s in SETS for k in MOMENTS
                  if shows(s, k) and sound_id in (self.own(s, k) or {"files": []})["files"]]
        if in_use:
            raise SoundError(f"Still used for: {', '.join(in_use)}. Swap it out first.")
        path.unlink()

    def _save(self):
        self.version += 1
        self.saved = {s: m for s, m in self.saved.items() if m}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": self.version, "sets": self.saved}, indent=1))
        tmp.replace(self.path)
