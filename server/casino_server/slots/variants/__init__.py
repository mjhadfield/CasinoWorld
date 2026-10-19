"""Slot variants by id. A variant names the base tiers for its theme and supplies its reel
strips, its feature rates and its bonus games' settings; everything else is shared."""
from casino_server.slots.variants import armadillo

VARIANTS = {armadillo.VARIANT.id: armadillo.VARIANT}
