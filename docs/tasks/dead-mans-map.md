# Dead Man's Map: the island voyage bonus

**Branch:** `main`

## Goal
A new library bonus game, built from the Pirates Of The Carribean design's spec (Build step "Ideas to build in
code"): sail a branching map of islands from the start port to the final island, choosing each destination, and
claim the parts of a legendary treasure your artefacts unlock. Any slot can switch it on in the wizard's Bonus games
step; Pirates will start it from a scatter (Mike routes it).

## How it plays (Mike's picks, 2026-10-20)
- **Real choices, balanced.** The whole map is visible from the start: 6 legs of 3 islands (5 felt short of
  collecting all four artefacts), each island showing what it is. From an island you can sail to the one level with it on the next leg or either side (2 or 3 choices).
  What an island gives is drawn when you land. Routes are tuned to pay about the same on average whatever you pick
  (tests check several strategies against each other); Skull Island routes swing more.
- **Islands:** Treasure Island (a sure prize), Shipwreck (relics, and maybe a key or an artefact), Skull Island
  (a big prize, but it can **sink you**: the voyage ends, you keep what you've won and lose the final island),
  Port Royal (trade relics: an artefact you're missing, a key, free games, or sell them all for cash), and a
  locked Hidden Cove (a key opens it: a big prize and an artefact).
- **Tuning (defaults, against Armadillo's free-game value ~16x):** random routes ~45x, careful 45x, Skull-heavy 49.5x,
  collecting 50.5x (all four artefacts 8% of the time); ±7% of each other. SD 18 careful to 41 bold. A strategy
  sweep script lived in the session scratchpad; `test_voyage_routes_pay_about_the_same_whatever_you_choose` keeps
  them within 15%.
- **The final island:** the legendary treasure is a chest with four locks. You always get the chest's base; each
  of the four artefacts you hold opens its lock and pays its part; all four pay the legend on top. Relics left over
  sell there.
- **Free games** bought at Port Royal are banked and play as the slot's Combo Free Games afterwards (like the battle).
- No spare hull (Mike left supplies out of Port Royal).
- It waits for you; after `voyage_auto` seconds it chooses for you (a random open island; at Port Royal the auto
  rule: an artefact if affordable, else free games, else sell).

Engine key `voyage` (base.BONUSES); variant field `voyage` (base.VOYAGE defaults); display name "DEAD MAN'S MAP".

## Files
- engine: `server/casino_server/slots/` (base, bonuses, variant, sim), `docs/slots/mockup/slots_math.js`
- cabinet: `tables/slot_machine.py`, `casino.py` (action), `npc.py`, `server/protocol.md`
- wizard: `slot_design_steps.py`, `slot_design_build.py`, `slot_design_web/steps/bonuses.js`, `maths.js`,
  `mockup/sim_worker.js`, `mockup/game.js`, `mockup/design.js`, `artslot.js`
- game: `client/scenes/slots/slot_screen.gd`; `sounds.py`
- docs: `docs/games/slots.md`, `docs/slots/README.md`, README

## Done when
- [x] Engine in Python and JS, draw for draw (parity test), sims include it
- [x] Cabinet plays it (voyage_choose, auto choose, stand-up plays it out, banked free games follow), NPCs play it
- [x] Wizard: Voyage card (on/off, ways in, words, settings, pictures), maths measures it, Build writes its texts
- [x] Mockup plays it (Try it)
- [x] The game's slot screen plays it
- [x] Sounds, docs
- [x] `tools/dev.sh test --all` passes
- [ ] Mike: reopen Pirates' sign-off, switch the voyage on (route it), pictures, re-freeze maths, sign off, Build, Install

## Handoff
- **State:** the bonus is built and in the library (committed 2026-10-20). What's left is Mike's, on the live board:
  reopen Pirates' sign-off, switch the voyage bonus on and choose its way in (Pirates has no bonus scatter, so the
  free-spins scatter, shared with the free games, or Buy Bonus), pick its fourteen pictures (stand-ins until then),
  re-freeze the maths (the voyage adds return), sign off, Build, Install. Then remove "Dead Man's Map" from Bonus
  games › New bonus ideas, or Build keeps listing it in IDEAS.md.
- **Changed:** engine `slots/bonuses.py` voyage_* + `base.VOYAGE` + `variant.voyage` + `sim.py` (voyage_value,
  simulate_voyage, expected_rtp); JS twin in `slots_math.js` (parity fixture regenerated: old parts identical);
  cabinet phase `voyage` + `voyage_choose` + bought free games (`pending` 5-tuple with its source); NPCs choose at
  random; wizard Voyage row (words, artefacts, map, islands, Port Royal, treasure), art slots v_* (stand-ins by
  `docs/slots/tools/voyage_standins.py`), maths report rows (sunk, all four), Build texts voyage_*; mockup and
  Godot screens (same layout, timings match `_VOYAGE_SECONDS`); six sound moments (Voyage Bonus section).
- **Checked:** 688 tests (`--all`), including a balance test across four route strategies; the mockup played to the
  end in headless Chromium (trading, sinking, the final reveal); the game's voyage screenshotted on the dev
  instance (the map, Port Royal's deals, the reveal), using a dev-only copy of the Pirates build routed to it.
- **Questions for Mike:** the default words and artefacts are Pirates' (Compass, Medallion, Spyglass, Cutlass) and
  editable; the sounds are the nearest fits in the library (no sea sounds there yet).
