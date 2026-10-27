"""C: The Boulevard. An indoor street runs across the front with the venues opening off it, and the casino
floor is behind three archways."""
from common import *  # noqa: F403

WALK = "#d9c69a"
PIT = "#6e1f2c"
HL = "#2a3550"
BOARDS = "#8a6a3a"

blvd = room("boulevard", "The Boulevard", -1296, -512, 3200, 448, "circ",
            doors=[("top", 700, 192, "archway"), ("top", 1600, 320, "archway"), ("top", 2500, 192, "archway"),
                   ("bottom", 416, 256, "archway"), ("bottom", 2400, 256, "archway"),
                   ("bottom", 912, 64, "door"), ("bottom", 1104, 64, "door"),
                   ("left", 254, 128, "door"), ("right", 254, 256, "archway")],
            items=[*[A("vegas_planter_palm", x, 210) for x in (250, 1150, 2050, 2950)],
                   *[A("bench", x, 330) for x in (450, 1150, 2050, 2750)],
                   A("modern_info_kiosk", 1600, 280), A("vegas_chip_sculpture", 1600, 200),
                   *[A("vegas_wall_sconce", x, 70) for x in (300, 1100, 2100, 2900)],
                   A("vegas_atm", 1900, 140), A("vegas_atm", 1300, 140)],
            patches=[patch(8, 200, 3184, 120, WALK)],
            points=[(800, 260), (1600, 380), (2400, 260), (120, 260), (3080, 260)],
            note="3200 × 448, an indoor street across the front. The lobby opens onto its middle. Three archways lead "
                 "north into the casino and the venues line the other three sides, with shop doors between them.")

fl = []
fl += pit(680, 150, ["blackjack", "blackjack", "blackjack"], ["blackjack", "three_card_poker", "ultimate_texas_holdem"])
fl += pit(2008, 150, ["mississippi_stud", "let_it_ride", "high_card_flush"], ["pai_gow_fortune", "three_card_poker", "blackjack"])
fl += [T("roulette", 520, 800), T("roulette", 960, 800), T("craps", 1800, 800), T("craps", 2260, 800)]
fl += [A("vegas_bar_counter", 1344, 400), *[A("vegas_bar_stool", 1218 + i * 28, 440) for i in range(10)], NPC(1344, 320, "Bartender")]
fl += [B(6, x, y) for x in (150, 660, 900, 1788, 2028, 2538) for y in (960, 1152)]
fl += [A("vegas_pylon_slots", 1200, 1060), A("vegas_pylon_slots", 1488, 1060), A("nocturne_medallion", 1344, 1140)]
casino = room("floor", "Casino Floor", -1040, -1792, 2688, 1280, "floor",
              doors=[("top", 1344, 96, "door"), ("left", 300, 96, "door"), ("right", 300, 96, "door")],
              items=fl,
              patches=[patch(8, 870, 2672, 400, PIT), patch(1184, 70, 320, 1200, WALK)],
              points=[(1344, 1200), (1344, 540), (140, 640), (2540, 640), (1100, 640)],
              note="2688 × 1280. Slots across the front by the archways, laid out tight so the sightlines stay short. "
                   "Behind them are two pits of six card tables round an island bar, then roulette and craps. "
                   "Doors lead out to the Vault, the Jade Room and the High Limit Slots.")

vault = room("vault", "The Vault", -240, -2640, 1088, 848, "high",
             doors=[("bottom", 544, 96, "door")],
             items=[T("blackjack", 204, 420, 0, "Blackjack £250"), T("baccarat", 544, 420, 0, "Baccarat £500"),
                    T("blackjack", 884, 420, 0, "Blackjack £1,000"), T("roulette", 300, 760), T("master_table", 760, 760),
                    *bar_run(260, 180, stools=8), A("vegas_sofa", 640, 190), A("vegas_armchair", 560, 190, "right"),
                    A("vegas_armchair", 720, 190, "left"), NPC(1000, 800, "Host"), NPC(1040, 600, "Security", "security")],
             patches=[patch(8, 70, 1072, 768, HL)], points=[(544, 560), (900, 200)],
             note="1088 × 848, a guarded door straight up the middle of the floor. Five tables with high limits, a private bar "
                  "and a lounge.")

jade = room("jade", "Jade Room", 1648, -1792, 960, 800, "high",
            items=[T("baccarat", 260, 380, 0, "Baccarat"), T("baccarat", 700, 380, 0, "Baccarat £100"),
                   T("pai_gow_fortune", 260, 690), T("pai_gow_face_up", 700, 690),
                   A("nocturne_divider", 480, 150), A("folding_screen", 80, 150), A("folding_screen", 880, 150),
                   A("lantern", 360, 120), A("lantern", 600, 120), NPC(60, 380, "Host")],
            points=[(480, 540), (900, 540)],
            note="960 × 800, a door off the floor. Baccarat and Pai Gow in a quieter salon of their own, the way "
                 "Macau resorts give these games their own rooms.")

hls = room("hl_slots", "High Limit Slots", -1968, -1792, 928, 640, "high",
           items=[*[B(4, x, 134) for x in (150, 390, 630)], *[B(6, x, y) for x in (240, 560) for y in (360, 552)]],
           patches=[patch(8, 70, 912, 560, HL)], points=[(800, 300), (800, 560)],
           note="928 × 640, a door off the floor's west wall. 36 cabinets at the top denominations.")

rest = room("restaurant", "Restaurant", -2256, -832, 960, 768, "food",
            items=[*dining(160, 280, 7, 4, 108, 110), A("wine_rack_mixed", 200, 150), A("wine_rack_red", 300, 150),
                   A("grand_piano", 820, 200), A("reception_desk", 880, 520), NPC(880, 460, "Maître d'")],
            points=[(880, 640), (480, 690)],
            note="960 × 768, a door at the boulevard's west end. 28 tables for NPC diners, with the kitchen behind.")

show = room("show", "Show Lounge", 1904, -832, 960, 768, "food",
            items=[A("vegas_stage", 600, 446), *bar_run(160, 200, stools=6),
                   *[A("nocturne_banquette", x, y) for x in (420, 700) for y in (600, 720)],
                   A("vegas_led_column", 330, 420), A("vegas_led_column", 870, 420)],
            points=[(560, 540), (140, 520)],
            note="960 × 768, a wide archway at the boulevard's east end so the show spills out. Stage, bar, booths.")

cafe = room("cafe", "Café", -1296, -64, 816, 512, "food",
            items=[*bar_run(408, 190, stools=6), *dining(160, 330, 5, 1, 120), A("vegas_planter_trough", 700, 470)],
            points=[(408, 440)],
            note="816 × 512, an archway off the boulevard. Quick food and coffee, open all hours.")

book = room("sportsbook", "Sportsbook & Bar", 608, -64, 1296, 640, "feature",
            items=[A("vegas_video_wall", 260, 70), A("vegas_video_wall", 648, 70), A("vegas_video_wall", 1036, 70),
                   *[A("vegas_armchair", x, y, "up") for x in range(180, 1000, 72) for y in (320, 410)],
                   *bar_run(1080, 520, stools=8, back=False), *[A("vegas_high_top", x, 540) for x in (200, 300, 400)],
                   *[A("reception_desk", x, 520) for x in (600, 720)], NPC(660, 470, "Writer", "cashier")],
            points=[(648, 230), (1200, 300)],
            note="1296 × 640, an archway off the boulevard. Video walls, rows of seats, a sports bar and a betting "
                 "counter for later.")

shop = room("boutique", "Boutique", -448, -64, 160, 160, "service", points=[(80, 110, "arrival")], npc_only=True,
            note="NPCs only: a shop door off the boulevard that shoppers come out of.")
wc = room("restrooms", "Restrooms", -256, -64, 128, 160, "service", points=[(64, 110, "arrival")], npc_only=True,
          note="NPCs only.")
kitchen = room("kitchen", "Kitchen", -2384, -600, 128, 160, "service", doors=[("right", 110, 48, "door")],
               points=[(64, 110, "arrival")], npc_only=True, note="NPCs only: behind the restaurant.")
staff = room("staff", "Staff", -1000, -1920, 128, 128, "service", doors=[("bottom", 64, 48, "door")],
             points=[(64, 100, "arrival")], npc_only=True, note="NPCs only: dealers on shift.")

ROOMS = [lobby(), *lifts(), blvd, casino, vault, jade, hls, rest, show, cafe, book, shop, wc, kitchen, staff]

META = {"title": "The Boulevard",
        "tagline": "An indoor street across the front with the venues off it. The casino is behind three archways, with salons off its back.",
        "inspired": "integrated resorts with indoor shopping streets, plus the Macau habit of separate baccarat salons",
        "idea": "The spawn opens onto a street rather than the casino. The restaurant, show lounge, café, sportsbook and "
                "shop doors all open off it, so there's life before you place a bet. Three archways lead north onto a "
                "big floor with tight slot clusters at the front, then the pits round an island bar. The Vault, the "
                "Jade Room and the High Limit Slots open off its back and sides. It's the biggest of the three and has "
                "the most to wander through.",
        "walks": {"The Vault": "vault", "Restaurant": "restaurant", "Show Lounge": "show"}}
