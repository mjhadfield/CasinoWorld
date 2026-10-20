"""Slot variants by id. A variant names the base tiers for its theme and supplies its reel
strips, its feature rates and its bonus games' settings; everything else is shared.
Armadillo is Python; slots built with the admin page's Slot design wizard are <id>.json here."""
from pathlib import Path

from casino_server.slots.variant import from_json
from casino_server.slots.variants import armadillo

VARIANTS = {armadillo.VARIANT.id: armadillo.VARIANT}
for _path in sorted(Path(__file__).parent.glob("*.json")):
    _v = from_json(_path)
    VARIANTS[_v.id] = _v
