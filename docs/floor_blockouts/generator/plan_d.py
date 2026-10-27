"""D: The Grand Hall (from GPT's concept sheet, ~/Projects/casino-floor-plan-concepts, plan A). One big central hall
with a spine aisle from the lobby and a cross aisle between the side rooms, quieter rooms round its edges. GPT's
rooms are kept where its 112 × 88 module sheet put them (32 px a module), shifted so the hall's middle sits over the
Modern lobby's top door; the lobby stands in for its entrance lobby, and the tables and furniture are placed again
to the real sizes."""
from common import *  # noqa: F403

WALK = "#d9c69a"
PIT = "#6e1f2c"
HL = "#2a3550"
OX, OY = -1472, -2368   # module (0, 0) on the plan


def M(mx, my, mw, mh):
    """GPT's room box in modules as (x, y, w, h) in plan pixels."""
    return OX + mx * 32, OY + my * 32, mw * 32, mh * 32


# The hall: 2304 × 1664. Spine aisle up the middle (x 1046-1258), cross aisle (y 470-690) between the side rooms'
# archways. Three rows of four tables, slots in bank-of-6 columns down both walls.
hall_items = []
for x, g in zip((462, 882, 1422, 1842), ("blackjack", "blackjack", "three_card_poker", "ultimate_texas_holdem")):
    hall_items.append(T(g, x, 290))
for x, g in zip((462, 882, 1422, 1842), ("let_it_ride", "mississippi_stud", "high_card_flush", "pai_gow_fortune")):
    hall_items.append(T(g, x, 880))
hall_items += [T("roulette", 440, 1340), T("craps", 860, 1340), T("master_table", 1422, 1340), T("roulette", 1842, 1340)]
hall_items[-4]["props"]["sign"] = hall_items[-3]["props"]["sign"] = "left"   # (signs out of the spine aisle)
for y in (230, 400, 800, 990, 1180, 1370):
    hall_items += [B(6, 115, y), B(6, 2189, y)]
hall_items += [A("vegas_planter_palm", 1000, 1600), A("vegas_planter_palm", 1304, 1600), NPC(1152, 600, "Pit boss")]
hall = room("hall", "Grand Hall", *M(20, 20, 72, 52), "floor",
            items=hall_items,
            patches=[patch(1046, 70, 212, 1584, WALK), patch(8, 470, 2288, 220, WALK)],
            points=[(1152, 1560), (1152, 580), (300, 580), (2000, 580), (1152, 1060)],
            note="2304 × 1664, the lobby's archway opens onto its spine aisle. 12 tables in three rows of four (card "
                 "tables, then roulette, craps, a Master table and roulette), 72 slots in bank-of-6 columns down both "
                 "walls. The cross aisle runs from the Sports Lounge's archway to the Slot Salon's.")

rest = room("restaurant", "Restaurant", *M(0, 0, 36, 20), "food",
            doors=[("bottom", 928, 224, "archway")],
            items=[*dining(160, 250, 6, 3, 112, 110), A("reception_desk", 860, 560), NPC(920, 540, "Maître d'"),
                   A("wine_rack_mixed", 860, 150), A("wine_rack_red", 960, 150), A("grand_piano", 1060, 300)],
            points=[(928, 450), (400, 580)],
            note="1152 × 640, an archway down onto the hall. 18 tables for NPC diners, a maître d' and a wine wall; the "
                 "kitchen is next door.")

kitchen = room("kitchen", "Kitchen", *M(36, 0, 20, 20), "service", doors=[("left", 352, 96, "door")],
               points=[(320, 400, "arrival")], npc_only=True, note="NPCs only: waiters and diners come and go here.")

salon = room("salon", "High Roller Salon", *M(56, 0, 36, 20), "high",
             doors=[("bottom", 608, 160, "door"), ("right", 480, 128, "door")],
             items=[T("blackjack", 230, 330, 0, "Blackjack £500"), T("baccarat", 576, 330, 0, "Baccarat £500"),
                    T("blackjack", 922, 330, 0, "Blackjack £1,000"), NPC(1040, 560, "Host"),
                    NPC(140, 560, "Security", "security")],
             patches=[patch(8, 70, 1136, 560, HL)],
             points=[(576, 540)],
             note="1152 × 640, behind a door at the back of the hall. Three high limit tables and a host; a side door "
                  "into the VIP Lounge.")

vip = room("vip", "VIP Lounge", *M(92, 0, 20, 20), "high",
           items=[*bar_run(320, 200, stools=6), A("vegas_sofa", 200, 460), A("vegas_armchair", 120, 460, "right"),
                  A("vegas_armchair", 280, 460, "left"), A("vegas_sofa", 460, 560), A("vegas_side_table", 540, 560),
                  NPC(520, 300, "Host")],
           patches=[patch(8, 70, 624, 560, HL)],
           points=[(320, 420), (480, 460)],
           note="640 × 640, through the High Roller Salon only. A private bar and sofas.")

sports = room("sports", "Sports Lounge", *M(0, 20, 20, 24), "feature",
              doors=[("right", 576, 224, "archway")],
              items=[A("vegas_video_wall", 300, 70), *[A("vegas_armchair", x, y, "up") for x in range(100, 560, 64)
                                                       for y in (300, 400)],
                     *[A("vegas_high_top", x, 640) for x in (120, 260)]],
              points=[(320, 520), (160, 560)],
              note="640 × 768, an archway onto the hall's cross aisle. A video wall and rows of seats NPCs linger in.")

cards = room("cards", "Side Card Room", *M(0, 44, 20, 20), "floor",
             doors=[("right", 544, 128, "door")],
             items=[T("blackjack", 150, 340, 90), T("pai_gow_face_up", 420, 340, 90), A("podium", 560, 160)],
             points=[(320, 560)],
             note="640 × 640, a door off the hall. Two tables turned side-on for quieter play.")

cage = room("cashier", "Cashier", *M(0, 64, 20, 8), "service",
            doors=[("right", 128, 96, "archway")],
            items=[A("vegas_cashier_cage", 260, 200), NPC(260, 130, "Cashier", "cashier"), A("vegas_atm", 520, 200)],
            points=[(460, 220)],
            note="640 × 256, an archway off the hall: the cage and an ATM.")

slots = room("slot_salon", "Slot Salon", *M(92, 20, 20, 24), "floor",
             doors=[("left", 576, 192, "archway")],
             items=[B(4, 170, 134), B(4, 470, 134), B(6, 420, 400), B(6, 420, 620)],
             points=[(160, 640), (320, 300)],
             note="640 × 768, an archway at the end of the cross aisle. 20 cabinets.")

wc = room("restrooms", "Restrooms", *M(92, 44, 20, 16), "service", doors=[("left", 288, 128, "door")],
          points=[(320, 300, "arrival")], npc_only=True, note="NPCs only: somewhere for people to pop off to.")
staff = room("staff", "Staff & Security", *M(92, 60, 20, 12), "service", doors=[("left", 192, 96, "door")],
             points=[(320, 240, "arrival")], npc_only=True, note="NPCs only: dealers coming on shift.")

bar = room("bar", "Bar & Lounge", *M(0, 72, 36, 16), "food",
           doors=[("top", 896, 256, "archway")],
           items=[*bar_run(400, 200, stools=10), *[A("nocturne_banquette", x, 420) for x in (180, 420)],
                  A("nocturne_cocktail", 300, 340), *[A("vegas_high_top", x, 300) for x in (700, 800)]],
           points=[(900, 380), (400, 300)],
           note="1152 × 512, open to the hall through a wide archway. Long bar, banquettes and high tops.")

hotel = room("hotel", "Hotel Lounge", *M(76, 72, 36, 16), "feature",
             doors=[("top", 192, 224, "archway")],
             items=[A("vegas_sofa", 500, 300), A("vegas_armchair", 420, 300, "right"), A("vegas_armchair", 580, 300, "left"),
                    A("vegas_sofa", 800, 400), A("reception_desk", 1000, 200), A("vegas_planter_palm", 1100, 440),
                    A("bench", 300, 440)],
             points=[(200, 380), (700, 360)],
             note="1152 × 512, an archway off the hall's front. A hotel lobby to grow into, sofas for now.")

ROOMS = [lobby(), *lifts(), hall, rest, kitchen, salon, vip, sports, cards, cage, slots, wc, staff, bar, hotel]

META = {"title": "The Grand Hall",
        "tagline": "One big hall with a spine and a cross aisle, quieter rooms all round its edges.",
        "inspired": "GPT's concept A, after Bellagio: a main casino ringed by dining, lounges and high limit rooms",
        "idea": "The lobby opens straight onto the hall's spine aisle, so the whole floor is in front of you as you "
                "walk in. A cross aisle runs between the Sports Lounge and the Slot Salon. Everything else (dining, "
                "the bar, the side card room, the high rollers) has its own room round the edge.",
        "walks": {"High Roller Salon": "salon", "Restaurant": "restaurant", "Slot Salon": "slot_salon"}}
