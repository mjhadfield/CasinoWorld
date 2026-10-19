"""Batch-generate the FLUX art set: 2 candidates per asset into flux/<id>_<n>.png (skips existing)."""
import os, subprocess, sys
STYLE = ("glossy polished 3D casino slot game art, warm golden rim lighting, rich saturated colours, "
         "crisp thick dark outline, centred and filling most of the frame, isolated on a perfectly flat "
         "solid magenta background, no text, no letters, no border")
A = {
 "W": "a single slot machine symbol: a gleaming gold six-pointed sheriff star badge with round ball tips and a blank smooth centre disc",
 "H1": "a single slot machine symbol: head-and-shoulders portrait of a cute cartoon armadillo outlaw wearing a brown cowboy hat and a red bandana, confident grin",
 "H2": "a single slot machine symbol: a coiled rattlesnake with tan and brown diamond scales, head raised, tongue out",
 "M1": "a single slot machine symbol: a battered brown leather cowboy hat with a silver star band",
 "M2": "a single slot machine symbol: a shiny golden lucky horseshoe with nail holes, open end up",
 "M3": "a single slot machine symbol: an old western whiskey bottle with amber liquid, cork stopper and a plain cream paper label",
 "M4": "a single slot machine symbol: a tall tooled-leather cowboy boot with a silver spur",
 "L1": "a single slot machine symbol: a playing-card spade shape carved from weathered dark wood with deep purple painted inlay",
 "L2": "a single slot machine symbol: a playing-card club shape carved from weathered dark wood with turquoise painted inlay",
 "L3": "a single slot machine symbol: a playing-card diamond shape carved from weathered dark wood with orange painted inlay",
 "L4": "a single slot machine symbol: a playing-card heart shape carved from weathered dark wood with red painted inlay",
 "BS": "a single slot machine symbol: an old west covered wagon with white canvas top and wooden wheels, three-quarter view",
 "FS": "a single slot machine symbol: two crossed ornate silver revolvers with gold engraving and ivory grips",
 "barrel": "a single slot machine symbol: a wooden whiskey barrel overflowing with shiny gold coins",
 "t_coin": "a single game icon: a thick shiny gold coin embossed with a star",
 "t_double": "a single game icon: a red diamond-shaped wooden sign with gold trim, blank face",
 "t_forward": "a single game icon: a wooden arrow signpost on a post, arrow pointing right",
 "t_heart": "a single game icon: a glossy red heart",
 "t_lightning": "a single game icon: a bright yellow lightning bolt crackling with energy",
 "t_crate": "a single game icon: an open wooden crate bursting with gold coins",
 "t_upgrade": "a single game icon: a wooden sign on a post painted with yellow and black chevron arrows pointing right",
 "t_gold": "a single game icon: a pyramid stack of shiny gold bars",
 "t_snake": "a single game icon: an angry rattlesnake head striking with fangs bared",
 "armadillo": "a single game character: full body side view of a cute cartoon armadillo walking upright, wearing a brown cowboy hat and red bandana, facing right",
 "cylinder": "a single game icon: a revolver cylinder seen straight on from the front, six empty chambers, polished steel",
}
SPECIAL = {
 "bg": ("a wide painterly western desert canyon landscape at dusk, red mesas and buttes, saguaro cacti silhouettes, "
        "orange and purple sky with first stars, warm cinematic lighting, casino slot game background art, no people, no text", "1344x768"),
 "logo": ("a western slot game title logo reading ARMADILLO GOES WEST in bold carved wooden and gold letters, "
          "with a small cartoon armadillo in a cowboy hat, " + "isolated on a perfectly flat solid magenta background", "1344x768"),
}
jobs = [(k, f"{v}, {STYLE}", "1024x1024") for k, v in A.items()] + [(k, p, s) for k, (p, s) in SPECIAL.items()]
for n in (1, 2):
    for key, prompt, size in jobs:
        out = f"flux/{key}_{n}.png"
        if os.path.exists(out):
            continue
        r = subprocess.run([sys.executable, "-I", "flux_gen.py", out, prompt, size], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip()[-300:], flush=True)
print("DONE", flush=True)
