"""E: The Garden Loop (from GPT's concept sheet, ~/Projects/casino-floor-plan-concepts, plan B). A big floor round an
indoor garden, small side rooms along the back, and a high roller and dining wing down one side. GPT's rooms are kept
where its 112 × 88 module sheet put them (32 px a module), shifted so the floor's entrance sits over the Modern
lobby's top door; the lobby stands in for its own, and the dining foyer moves next to it (opening off the floor's
front, since the lobby's right wall is the reception desk). Tables and furniture are placed again to the real sizes."""
from common import *  # noqa: F403

WALK = "#d9c69a"
HL = "#2a3550"
GARDEN = "#3a5a3a"
OX, OY = -1728, -2368   # module (0, 0) on the plan


def M(mx, my, mw, mh):
    """GPT's room box in modules as (x, y, w, h) in plan pixels."""
    return OX + mx * 32, OY + my * 32, mw * 32, mh * 32


# The floor: 2560 × 1664. The garden in the middle (928-1568 × 512-1088) with a walk round it, the lobby's archway at
# x 2032 on the front wall, card tables in fours along the back and front, craps and roulette either side.
floor_items = []
for x, g in zip((320, 736, 1760, 2240), ("blackjack", "three_card_poker", "blackjack", "ultimate_texas_holdem")):
    floor_items.append(T(g, x, 270))
for x, g in zip((320, 736, 1520, 2370), ("let_it_ride", "mississippi_stud", "high_card_flush", "blackjack")):
    floor_items.append(T(g, x, 1440))
floor_items += [T("craps", 420, 880), T("roulette", 2140, 880)]
for x, y in ((140, 560), (600, 560), (140, 1160), (600, 1160), (1900, 560), (2380, 560), (2140, 1130)):
    floor_items.append(B(6, x, y))
floor_items += [A("stone_fountain", 1248, 830), A("bird_bath", 1100, 760), A("bird_bath", 1396, 760),
                *[A("vegas_planter_palm", x, y) for x in (990, 1506) for y in (600, 1060)],
                A("bench", 1248, 680), A("bench", 1248, 1000), NPC(1800, 1000, "Pit boss")]
main = room("floor", "Casino Floor", *M(0, 20, 80, 52), "floor",
            items=floor_items,
            patches=[patch(800, 384, 896, 832, WALK, "rounded", 64), patch(928, 512, 640, 576, GARDEN, "rounded", 32),
                     patch(1936, 1216, 192, 438, WALK), patch(1360, 1216, 768, 140, WALK)],
            points=[(1248, 900), (1248, 450), (860, 820), (1640, 820), (2032, 1580), (300, 900)],
            note="2560 × 1664, the lobby's archway at its front right. An indoor garden with a fountain in the middle "
                 "and a walk round it, 8 card tables along the back and front, craps and roulette either side, 42 "
                 "slots in bank-of-6 blocks. The side rooms open off the back wall and the wing off the right.")

cards = room("cards", "Side Card Room", *M(0, 0, 24, 20), "floor",
             doors=[("bottom", 384, 160, "door")],
             items=[T("blackjack", 200, 330, 90), T("pai_gow_face_up", 520, 330, 90)],
             points=[(384, 560)],
             note="768 × 640, a door at the back of the floor. Two tables turned side-on for quieter play.")

private = room("private", "Private Salon", *M(24, 0, 24, 20), "floor",
               doors=[("bottom", 384, 160, "door")],
               items=[T("master_table", 384, 330, 0, "Private table"), A("rug_gold_large", 384, 520),
                      A("vegas_sofa", 160, 540), A("vegas_sofa", 608, 540), NPC(680, 200, "Host")],
               points=[(384, 560)],
               note="768 × 640, a door off the floor: a Master table for a group to pick their game.")

music = room("music", "Music Lounge", *M(48, 0, 32, 20), "feature",
             doors=[("bottom", 512, 256, "archway")],
             items=[A("vegas_stage", 512, 400), A("grand_piano", 420, 260),
                    *[A("nocturne_banquette", x, 560) for x in (130, 894)], *[A("nocturne_cocktail", x, 480) for x in (130, 894)]],
             points=[(512, 520), (200, 420)],
             note="1024 × 640, a wide archway so the music carries onto the floor. Stage, piano, banquettes.")

salon = room("salon", "High Roller Salon", *M(80, 0, 32, 32), "high",
             doors=[("left", 832, 128, "door"), ("bottom", 512, 128, "door")],
             items=[T("blackjack", 256, 330, 0, "Blackjack £500"), T("baccarat", 768, 330, 0, "Baccarat £500"),
                    T("roulette", 400, 720, 0, "Roulette £100"), B(6, 820, 660), B(6, 820, 860),
                    NPC(560, 940, "Host"), NPC(80, 640, "Security", "security")],
             patches=[patch(8, 70, 1008, 944, HL)],
             points=[(512, 520), (200, 900)],
             note="1024 × 1024, a door off the floor's right wall. Three high limit tables and 12 high-denomination "
                  "cabinets; a door down into the VIP Lounge.")

vip = room("vip", "VIP Lounge", *M(80, 32, 32, 16), "high",
           doors=[("left", 320, 128, "door")],
           items=[*bar_run(260, 200, stools=8), A("vegas_sofa", 760, 300), A("vegas_armchair", 680, 300, "right"),
                  A("vegas_armchair", 840, 300, "left"), A("vegas_sofa", 760, 440), NPC(560, 200, "Host")],
           patches=[patch(8, 70, 1008, 432, HL)],
           points=[(500, 400)],
           note="1024 × 512, doors from the floor and the High Roller Salon. A private bar and sofas.")

rest = room("restaurant", "Restaurant", *M(80, 48, 32, 24), "food",
            doors=[("left", 288, 192, "archway")],
            items=[*dining(300, 250, 6, 4, 112, 104), A("reception_desk", 140, 540), NPC(140, 480, "Maître d'"),
                   A("wine_rack_mixed", 760, 150), A("wine_rack_red", 860, 150)],
            points=[(140, 300), (600, 700)],
            note="1024 × 768, an archway off the floor and another down to the Dining Foyer. 24 tables; the kitchen "
                 "behind it.")

bar = room("bar", "Bar & Lounge", *M(0, 72, 32, 16), "food",
           doors=[("top", 768, 256, "archway")],
           items=[*bar_run(300, 200, stools=10), *[A("nocturne_banquette", x, 430) for x in (560, 820)],
                  A("nocturne_cocktail", 690, 340), *[A("vegas_high_top", x, 330) for x in (120, 480)]],
           points=[(768, 300), (300, 360)],
           note="1024 × 512, open to the floor through a wide archway: the social end of the loop.")

wc = room("restrooms", "Restrooms", *M(32, 72, 16, 16), "service", doors=[("top", 256, 128, "door")],
          points=[(256, 300, "arrival")], npc_only=True, note="NPCs only: somewhere for people to pop off to.")

foyer = room("foyer", "Dining Foyer", 608, -64, 512, 512, "entry",
             doors=[("top", 112, 128, "door"), ("top", 368, 128, "archway")],
             items=[A("reception_desk", 300, 300), A("vegas_planter_palm", 460, 440), A("bench", 120, 440),
                    A("vegas_sofa", 300, 440)],
             points=[(256, 360)],
             note="512 × 512, beside the lobby: a door off the floor's front and an archway up into the restaurant, "
                  "the dining's own way in. (GPT had it open off the lobby, but that wall's the reception desk.)")

kitchen = room("kitchen", "Kitchen", 1120, -64, 512, 512, "service", doors=[("top", 256, 96, "door")],
               points=[(256, 300, "arrival")], npc_only=True, note="NPCs only: waiters, diners and dealers on shift.")

ROOMS = [lobby(), *lifts(), main, cards, private, music, salon, vip, rest, bar, wc, foyer, kitchen]

META = {"title": "The Garden Loop",
        "tagline": "A big floor round an indoor garden, small rooms to discover and a high roller and dining wing.",
        "inspired": "GPT's concept B, after Park MGM: a garden landmark in the middle and destinations round it",
        "idea": "The garden and fountain in the middle of the floor give everyone a landmark and a meeting place, "
                "with a walk round it. Small rooms along the back (cards, a private Master table, a music lounge) "
                "and a wing down the right (high rollers, their lounge, the restaurant) give you somewhere to go next.",
        "walks": {"High Roller Salon": "salon", "Restaurant": "restaurant", "Music Lounge": "music"}}
