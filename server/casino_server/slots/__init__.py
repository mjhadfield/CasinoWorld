"""
Slot machines: one shared base (a 5x4 grid, 25 lines, a pay table by tier, a stake ladder)
and the shared Mini/Minor/Major/Grand progressives; each variant (variants/) composes its
own random features and bonus games on top. Ported line for line from the signed-off
mockup's maths (docs/slots/mockup/slots_math.js), with the same seeded generator, so a
seed gives the same outcome in both -- tests/test_slots_parity.py holds them together.
"""
