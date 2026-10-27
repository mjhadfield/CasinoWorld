"""B: The Promenade. A run of rooms on one axis, each a door further in and grander than the last, with the slots
kept in their own hall off to the side."""
from common import *  # noqa: F403

WALK = "#d9c69a"
PIT = "#6e1f2c"
HL = "#2a3550"
GARDEN = "#3a5a3a"

atrium = room("atrium", "Grand Hall", -464, -704, 1536, 640, "circ",
              doors=[("top", 768, 384, "archway"), ("left", 360, 160, "archway"), ("right", 360, 192, "archway")],
              items=[A("nocturne_medallion", 768, 420), A("stone_fountain", 768, 400),
                     A("statue_lady", 560, 300), A("statue_lady", 976, 300),
                     A("vegas_cashier_cage", 300, 174), NPC(300, 120, "Cashier", "cashier"), A("vegas_atm", 1240, 160),
                     A("vegas_atm", 1290, 160), A("modern_jackpot_screen", 1240, 70),
                     A("bench", 560, 540), A("bench", 976, 540), A("vegas_planter_palm", 180, 560),
                     A("vegas_planter_palm", 1356, 560)],
              patches=[patch(576, 70, 384, 560, WALK)],
              points=[(768, 560), (420, 360), (1120, 360)],
              note="1536 × 640, the lobby's archway opens onto it. Fountain on the axis, cashier cage and ATMs, archways "
                   "out to the slots on one side and the bar on the other. Nobody gambles here, it's where people meet.")

slot_items = [B(4, x, 134) for x in (140, 380, 620, 860, 1100)]
slot_items += [B(6, x, y) for x in (260, 580, 900) for y in (380, 572, 860, 1052)]
slot_items += [A("vegas_pylon_slots", 1180, 700), A("vegas_atm", 1200, 1220)]
slots = room("slots", "Slot Hall", -1744, -1344, 1280, 1280, "floor",
             doors=[("top", 640, 160, "door")],
             items=slot_items, patches=[patch(8, 700, 1264, 96, WALK)],
             points=[(640, 720), (1100, 980), (420, 250)],
             note="1280 × 1280, an archway off the Grand Hall. 92 slots: banks of 4 along the back wall and a grid of "
                  "banks of 6 split by a cross aisle. A door at the back leads out to the terrace.")

terrace = room("terrace", "Garden Terrace", -1744, -1728, 1280, 384, "feature", thin=True,
               items=[A("stone_fountain", 640, 220), *[A("plant_tall", x, 60) for x in range(120, 1200, 120)],
                      *dining(160, 200, 3, 1, 130), *dining(900, 200, 3, 1, 130), A("bench", 640, 340),
                      A("bird_bath", 470, 300), A("bird_bath", 810, 300)],
               patches=[patch(8, 8, 1264, 366, GARDEN)],
               points=[(640, 300), (300, 320), (1000, 320)],
               note="1280 × 384, open air (a thin back wall). Doors from the Slot Hall and the Grand Salon make a loop. "
                    "A fountain, café tables, somewhere for NPCs to step out.")

salon_items = pit(372, 150, ["blackjack", "blackjack"], ["blackjack", "three_card_poker"])
salon_items += pit(1164, 150, ["ultimate_texas_holdem", "mississippi_stud"], ["let_it_ride", "pai_gow_face_up"])
salon_items += [T("roulette", 372, 860), T("craps", 1164, 860), A("rug_gold_large", 768, 330), A("rug_gold_large", 768, 590),
                A("candelabra", 768, 200), NPC(700, 700, "Pit boss")]
salon = room("salon", "Grand Salon", -464, -1728, 1536, 1024, "floor",
             doors=[("top", 768, 96, "door"), ("left", 200, 128, "door"), ("right", 700, 128, "door")],
             items=salon_items,
             patches=[patch(708, 70, 120, 944, WALK), patch(8, 640, 1520, 64, WALK)],
             points=[(768, 960), (768, 460), (100, 620), (1440, 620)],
             note="1536 × 1024, through the big archway on the axis. Two pits of four card tables either side of the "
                  "axis aisle, with roulette and craps at the front. Doors out to the terrace, the restaurant and, "
                  "straight ahead, the Salle Privée.")

privee = room("privee", "Salle Privée", -240, -2432, 1088, 704, "high",
              doors=[("right", 400, 96, "door")],
              items=[T("baccarat", 200, 400, 0, "Baccarat £500"), T("blackjack", 544, 400, 0, "Blackjack £500"),
                     T("master_table", 888, 400, 0, "Private table"), A("nocturne_signature", 544, 70),
                     A("vegas_sofa", 160, 620), A("vegas_armchair", 80, 620, "right"), A("vegas_armchair", 240, 620, "left"),
                     A("vegas_side_table", 300, 620), *bar_run(860, 620, stools=0, back=False),
                     NPC(860, 560, "Butler"), NPC(620, 660, "Host"), NPC(470, 660, "Security", "security")],
              patches=[patch(8, 70, 1072, 624, HL)],
              points=[(544, 560), (300, 520)],
              note="1088 × 704, a door at the head of the axis. Three tables with high limits (a Master table "
                   "gives them every game), a lounge and a butler's bar. A side door leads to the High Limit Slots.")

hls = room("hl_slots", "High Limit Slots", 848, -2240, 512, 512, "high",
           items=[B(4, 140, 134), B(4, 380, 134), B(6, 140, 330), B(6, 380, 330)],
           patches=[patch(8, 70, 496, 432, HL)], points=[(256, 450)],
           note="512 × 512, through the Salle Privée only. 20 cabinets at the top denominations.")

lounge = room("lounge", "Lounge Bar", 1072, -704, 960, 640, "food",
              doors=[("top", 480, 96, "door")],
              items=[*bar_run(300, 200, stools=10), A("vegas_stage", 700, 446), A("grand_piano", 700, 300),
                     *[A("nocturne_banquette", x, 560) for x in (200, 420)], A("nocturne_cocktail", 310, 480),
                     A("vegas_high_top", 840, 560), A("vegas_high_top", 900, 560)],
              points=[(560, 400), (300, 420)],
              note="960 × 640, an archway off the Grand Hall. Long bar, piano stage and banquettes, with a door up "
                   "to the restaurant.")

rest = room("restaurant", "Restaurant", 1072, -1344, 960, 640, "food",
            items=[*dining(220, 250, 7, 4, 112, 100), A("wine_rack_mixed", 300, 150), A("wine_rack_red", 400, 150),
                   A("wine_rack_green", 500, 150), NPC(60, 420, "Maître d'")],
            points=[(80, 560), (880, 560)],
            note="960 × 640. Two ways in, from the Grand Salon and up from the Lounge Bar. 28 tables, a wine wall, and "
                 "the kitchen behind it.")

kitchen = room("kitchen", "Kitchen", 2032, -1200, 128, 160, "service", doors=[("left", 110, 48, "door")],
               points=[(64, 110, "arrival")], npc_only=True, note="NPCs only: waiters and diners.")
staff = room("staff", "Staff", -400, -1856, 128, 128, "service", doors=[("bottom", 64, 48, "door")],
             points=[(64, 100, "arrival")], npc_only=True, note="NPCs only: dealers coming on shift into the salon.")
wc = room("restrooms", "Restrooms", -400, -64, 128, 160, "service", doors=[("top", 64, 48, "door")],
          points=[(64, 110, "arrival")], npc_only=True, note="NPCs only, off the Grand Hall.")

ROOMS = [lobby(), *lifts(), atrium, slots, terrace, salon, privee, hls, lounge, rest, kitchen, staff, wc]

META = {"title": "The Promenade",
        "tagline": "A run of rooms on one axis, each grander than the last. The slots get their own hall and the high rollers sit at the far end.",
        "inspired": "the grand European casinos: an enfilade of salons, slots kept apart from the tables",
        "idea": "You walk in a straight line from the lobby through the Grand Hall and the Grand Salon to the Salle "
                "Privée, and each doorway shows the next room only once you reach it. The tables stay on the axis while "
                "the slots get their own hall, with a terrace linking it back to the salon so there's a loop to "
                "wander. It has the fewest tables of the three and the most sense of arrival.",
        "walks": {"Salle Privée": "privee", "Restaurant": "restaurant", "Slot Hall": "slots"}}
