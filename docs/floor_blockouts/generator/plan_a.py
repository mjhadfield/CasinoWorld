"""A: The Loop. One big open floor with a racetrack aisle round the pits, the centre bar at the head of the
entrance axis, and the side rooms opening off the floor's walls."""
from common import *  # noqa: F403

WALK = "#d9c69a"
PIT = "#6e1f2c"

FX, FY, FW, FH = -1040, -1664, 2688, 1600   # the main floor, centred on the lobby's top door (x 304)

floor_items = []
floor_items += pit(860, 506, ["blackjack", "blackjack"], ["blackjack", "three_card_poker"])
floor_items += pit(1828, 506, ["ultimate_texas_holdem", "mississippi_stud"], ["let_it_ride", "pai_gow_fortune"])
floor_items += [T("roulette", 630, 1120), T("roulette", 1050, 1120), T("craps", 1828, 1150)]
floor_items += bar_run(1344, 200, stools=10)
floor_items += [A("vegas_high_top", x, 250) for x in (1040, 1110, 1578, 1648)]
floor_items += [A("vegas_planter_palm", 1110, 150), A("vegas_planter_palm", 1578, 150)]
for y in (420, 612, 804, 996, 1188, 1380):
    floor_items += [B(6, 160, y), B(6, 2528, y)]
floor_items += [B(4, x, 1584, "up") for x in (440, 680, 920, 1160, 1940, 2180, 2420)]
floor_items += [A("vegas_cashier_cage", 1660, 1500), NPC(1660, 1440, "Cashier", "cashier")]
floor_items += [A("podium", 60, 300), NPC(40, 250, "Host")]

main = room("floor", "Casino Floor", FX, FY, FW, FH, "floor",
            doors=[("left", 200, 96, "door"), ("left", 1250, 96, "door"), ("right", 200, 192, "archway"),
                   ("right", 1100, 256, "archway")],
            items=floor_items,
            patches=[patch(312, 300, 2064, 1100, WALK, "rounded", 96), patch(440, 428, 1808, 844, PIT, "rounded", 48),
                     patch(1280, 428, 128, 844, WALK), patch(1280, 1400, 128, 190, WALK)],
            points=[(1344, 1520), (1344, 330), (900, 370), (2300, 850), (1344, 800), (380, 1300)],
            note="2688 × 1600. 8 card tables in two pits, 2 roulette, 1 craps inside a 128 px racetrack aisle; "
                 "72 slots in bank-of-6 columns down both sides, 28 more against the front wall; centre bar on the back wall "
                 "at the head of the entrance axis; cashier cage facing the entrance.")

salon = room("salon", "High Limit Salon", FX - 1088, FY, 1088, 900, "high",
             doors=[("bottom", 900, 96, "door")],
             items=[T("blackjack", 204, 420, 0, "Blackjack £100"), T("baccarat", 544, 420, 0, "Baccarat £250"),
                    T("blackjack", 884, 420, 0, "Blackjack £500"), T("roulette", 300, 780), T("master_table", 760, 780),
                    *bar_run(260, 180, stools=8), A("vegas_sofa", 620, 200), A("vegas_armchair", 540, 200, "right"),
                    A("vegas_armchair", 700, 200, "left"), NPC(1040, 200, "Host"), NPC(1040, 600, "Security", "security")],
             points=[(640, 540), (980, 220)],
             note="1088 × 900, door off the floor with a host. Five tables with high limits, a private bar and a lounge. "
                  "A second door drops into the High Limit Slots below.")

hls = room("hl_slots", "High Limit Slots", FX - 1088, FY + 900, 1088, 700, "high",
           items=[*[B(4, x, 134) for x in (150, 390, 630, 870)], *[B(6, x, y) for x in (220, 544, 868) for y in (400, 592)]],
           points=[(544, 260), (980, 640)],
           note="1088 × 700. 52 high-denomination cabinets; doors to the floor and up into the salon.")

rest = room("restaurant", "Restaurant", 448, FY - 800, 1136, 800, "food",
            doors=[("bottom", 412, 96, "door")],
            items=[*dining(150, 260, 8, 4, 116, 110), A("reception_desk", 412, 720), NPC(470, 700, "Maître d'"),
                   A("wine_rack_mixed", 160, 150), A("wine_rack_red", 260, 150), A("wine_rack_green", 360, 150),
                   A("grand_piano", 1040, 300)],
            points=[(560, 680), (1040, 560)],
            note="1136 × 800, door at the back of the floor. 32 tables for NPC diners, a maître d' at the door, piano "
                 "and wine wall; the kitchen is an NPCs-only room behind it.")

kitchen = room("kitchen", "Kitchen", 1584, FY - 600, 128, 160, "service", doors=[("left", 100, 48, "door")],
               points=[(64, 110, "arrival")], npc_only=True, note="NPCs only: waiters and diners come and go here.")
staff = room("staff", "Staff", FX + 636, FY - 128, 128, 128, "service", doors=[("bottom", 64, 48, "door")],
             points=[(64, 100, "arrival")], npc_only=True,
             note="NPCs only: dealers' shift changes walk in and out behind the pits.")

lounge = room("lounge", "Showroom Lounge", FX + FW, FY, 1024, 800, "food",
              items=[A("vegas_stage", 640, 446), *bar_run(180, 200, stools=8),
                     *[A("nocturne_banquette", x, y) for x in (500, 780) for y in (640, 760)],
                     *[A("nocturne_cocktail", x, 700) for x in (360, 920)], A("vegas_led_column", 340, 420),
                     A("vegas_led_column", 940, 420)],
              points=[(640, 560), (200, 360)],
              note="1024 × 800, a wide archway so the music carries onto the floor. Stage, bar, banquettes.")

wc = room("restrooms", "Restrooms", FX + FW + 1024, FY + 260, 128, 160, "service", doors=[("left", 100, 48, "door")],
          points=[(64, 110, "arrival")], npc_only=True, note="NPCs only: somewhere for people to pop off to.")

book = room("sportsbook", "Sportsbook", FX + FW, FY + 800, 1024, 800, "feature",
            items=[A("vegas_video_wall", 300, 70), A("vegas_video_wall", 724, 70),
                   *[A("vegas_armchair", x, y, "up") for x in range(180, 900, 72) for y in (420, 520)],
                   *[A("reception_desk", x, 700) for x in (380, 512, 644)], NPC(512, 640, "Writer", "cashier"),
                   *[A("vegas_high_top", x, 300) for x in (160, 860)]],
            points=[(512, 300), (900, 620)],
            note="1024 × 800, archway off the floor. Video walls and rows of seats NPCs linger in; a betting counter "
                 "for when there's something to bet on.")

ROOMS = [lobby(), *lifts(), main, salon, hls, rest, kitchen, staff, lounge, wc, book]

META = {"title": "The Loop", "tagline": "One big open floor. A racetrack aisle circles the pits, slots line the outside, and the centre bar pulls you in.", "inspired": "Las Vegas Strip resorts: the racetrack aisle and open, high-ceilinged floor",
        "idea": "Everything is in one big room. A ring aisle circles the pits and the slots line the outside, so you can see the "
                "whole floor from anywhere on the loop. The centre bar sits at the far end of the entrance aisle and pulls "
                "you across the floor. The side rooms open off the floor's walls: archways where the noise should carry "
                "(lounge, sportsbook), doors where it shouldn't (high limit, restaurant).",
        "walks": {"High Limit Salon": "salon", "Restaurant": "restaurant", "Showroom Lounge": "lounge"}}

if __name__ == "__main__":
    import json
    cleaned, probs = check(ROOMS)
    for p in probs:
        print(p["room"], "|", p["message"])
    print(len(probs), "problems")
