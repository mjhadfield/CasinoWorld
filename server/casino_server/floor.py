"""
The casino floor as the server sees it: which tables exist, and the named
spots NPCs walk between. The server needs no geometry -- each name here must
exist as a Marker2D in the client's casino_floor.tscn (group "floor_points"),
and the client works out paths and positions. A Godot check asserts the two
lists match.
"""

TABLES = {
    "tcp_1": {"game": "three_card_poker", "name": "Three Card Poker", "seats": 6},
    "bj_1": {"game": "blackjack", "name": "Blackjack", "seats": 6},
    "ms_1": {"game": "mississippi_stud", "name": "Mississippi Stud", "seats": 6},
    "pgf_1": {"game": "pai_gow_fortune", "name": "Fortune Pai Gow", "seats": 6},
    "pgu_1": {"game": "pai_gow_face_up", "name": "Face Up Pai Gow", "seats": 6},
    "uth_1": {"game": "ultimate_texas_holdem", "name": "Ultimate Texas Hold'em", "seats": 6},
    "lir_1": {"game": "let_it_ride", "name": "Let It Ride", "seats": 5},     # five, spread out for room
    "hcf_1": {"game": "high_card_flush", "name": "High Card Flush", "seats": 5},
    "bac_1": {"game": "baccarat", "name": "Baccarat", "seats": 6},
    "rou_1": {"game": "roulette", "name": "Roulette", "seats": 6},
    "crp_1": {"game": "craps", "name": "Craps", "seats": 8},
}
# The slot bank: ten Armadillo Goes West cabinets in the south-east corner (one seat each).
SLOTS = {f"slot_{i}": {"game": "slots", "variant": "armadillo", "name": "Armadillo Goes West", "seats": 1}
         for i in range(1, 11)}
TABLES.update(SLOTS)
SLOTS_FOR_HUMANS = 2   # NPCs leave at least this many cabinets of a bank free

ENTRANCE = "entrance"

# Places NPCs wander to between games: spots in the aisles between the tables (the
# floor has no decor to visit yet).
WANDER_POINTS = ["aisle_w", "aisle_mid", "aisle_e", "corner_w", "corner_e"]

ALL_POINTS = [ENTRANCE] + WANDER_POINTS
