import subprocess, sys
STYLE = ("glossy polished 3D casino slot game art, warm golden rim lighting, rich saturated colours, crisp thick dark outline, "
         "centred and filling most of the frame, isolated on a perfectly flat solid magenta background, no text, no letters, no border")
JOBS = {
 "H1": "a single slot machine symbol: head-and-shoulders portrait of a cartoon nine-banded armadillo outlaw, long narrow pointed snout, "
       "large upright leathery ears, armoured head shield and segmented tan shell bands across its shoulders, small beady eyes, "
       "wearing a brown cowboy hat and a red bandana, confident smirk",
 "armadillo": "a single game character: full body side view of a cartoon nine-banded armadillo, domed segmented armoured shell with clear "
              "bands, long pointed snout, large ears, long scaly tapering tail, short legs, wearing a small brown cowboy hat and a red "
              "bandana, walking to the right",
}
for n in (3, 4):
    for k, p in JOBS.items():
        r = subprocess.run([sys.executable, "-I", "flux_gen.py", f"flux/{k}_{n}.png", f"{p}, {STYLE}"], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr[-300:], flush=True)
print("DONE", flush=True)
