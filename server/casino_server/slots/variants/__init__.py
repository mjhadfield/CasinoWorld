"""Slot variants by id. A variant names the base tiers for its theme and supplies its reel
strips, its feature rates and its bonus games' settings; everything else is shared.
Armadillo is Python; slots built with the admin page's Slot design wizard join at startup
(slot_builds.install, from server/slot_builds/<id>/variant.json)."""
from casino_server.slots.variants import armadillo

VARIANTS = {armadillo.VARIANT.id: armadillo.VARIANT}
