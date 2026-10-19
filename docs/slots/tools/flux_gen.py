"""Generate images with Odysseus's FLUX.2-klein server (inside the container).
usage: flux_gen.py out.png "prompt" [size]"""
import base64, json, subprocess, sys, time
out, prompt = sys.argv[1], sys.argv[2]
size = sys.argv[3] if len(sys.argv) > 3 else "1024x1024"
body = json.dumps({"prompt": prompt, "size": size, "quality": "high"})
t = time.time()
r = subprocess.run(["docker", "exec", "-i", "-u", "odysseus", "-e", "HOME=/app", "odysseus-odysseus-1",
                    "curl", "-s", "-X", "POST", "localhost:8000/v1/images/generations",
                    "-H", "Content-Type: application/json", "--data-binary", "@-"],
                   input=body.encode(), capture_output=True, timeout=900)
d = json.loads(r.stdout)
if "data" not in d:
    sys.exit(f"error: {str(d)[:300]}")
open(out, "wb").write(base64.b64decode(d["data"][0]["b64_json"]))
print(f"{out} {time.time()-t:.1f}s")
