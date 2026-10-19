"""Edit/redraw a reference image with Odysseus's FLUX.2-klein server (inside the container).
usage: flux_edit.py ref.png out.png "prompt" [size]"""
import base64, json, subprocess, sys, time
ref, out, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
size = sys.argv[4] if len(sys.argv) > 4 else "1024x1024"
t = time.time()
r = subprocess.run(["docker", "exec", "-i", "-u", "odysseus", "-e", "HOME=/app", "odysseus-odysseus-1",
                    "curl", "-s", "-X", "POST", "localhost:8000/v1/images/edits",
                    "-F", "image=@-;type=image/png;filename=ref.png", "--form-string", f"prompt={prompt}",
                    "--form-string", f"size={size}", "--form-string", "quality=high"],
                   input=open(ref, "rb").read(), capture_output=True, timeout=900)
d = json.loads(r.stdout)
if "data" not in d:
    sys.exit(f"error: {str(d)[:300]}")
open(out, "wb").write(base64.b64decode(d["data"][0]["b64_json"]))
print(f"{out} {time.time()-t:.1f}s")
