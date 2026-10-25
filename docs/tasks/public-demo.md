# Public demo (Oracle Cloud Always-Free ARM)

**Branch:** `task/public-demo` (later)

## Goal
A public demo of Casino World at `https://casino.mikehadfield.co.uk`, on Oracle's Always-Free Ampere A1 VM, moving to a paid VPS later once there's more than one project to host. Long term it links from www.mikehadfield.co.uk (GitHub Pages).

This first pass only makes it **playable at the public URL**. The demo-branch trimming (fixed roster, no admin code) is phase 2; until then, Caddy keeps the admin side off the internet.

## Files
- New `deploy/` (`Caddyfile`, `casino-demo.service`)
- New `tools/deploy_demo.sh`
- README: a hosting section
- Phase 2 (demo branch) touches `server/casino_server/app.py` and `__main__.py`

## Context
- The domain is registered with 123 Reg, whose DNS runs on GoDaddy's servers (`ns51/52.domaincontrol.com`, as GoDaddy owns 123 Reg). DNS records are edited in the 123 Reg control panel.
- `CASINO_HOST`, `CASINO_PORT`, `CASINO_DATA_DIR`, `CASINO_WEB_DIR`, `CASINO_DESIGNS_DIR` and `CASINO_SLOT_BUILDS_DIR` are in `server/casino_server/__main__.py` and the README. The server can bind to `127.0.0.1:8660` with Caddy doing TLS; the built-in self-signed HTTPS on 8661 stays unused.
- The client derives every URL from `location.origin` (`client/autoload/{sfx,slot_art,look_loader}.gd`), so it works on a new domain with no client change.
- **`/admin` has no password** (README). A public deploy must block it.
- The client only calls these HTTP routes: `/api/look-options`, `/api/looks/preview`, `/api/plan/art`, `/api/slots/art/manifest`, `/api/sounds/manifest`, `/looks/*.png` and the art/sound file routes. Every other `/api/*` route is admin-only.
- The wasm export is architecture-independent, so `build/web` is copied as-is. The deps (fastapi, uvicorn[standard], pillow, numpy, httpx) all ship aarch64 wheels. Playwright isn't needed on the server.

## Steps

### 1. Mike: Oracle account and VM (console, about 30 min)
1. Sign up at cloud.oracle.com. **The home region is permanent, and free A1 instances only run there**: pick UK South (London), or Frankfurt if London keeps saying "out of capacity". A card is needed for verification.
2. Strongly consider **upgrading to Pay-As-You-Go** straight away (it stays £0 within the free limits). It mostly fixes "out of host capacity", and it stops Oracle **reclaiming idle Always-Free instances**, which are reclaimed if CPU, network and memory stay under 20% for 7 days, and a demo will. Add a £1 budget alert under Billing › Budgets.
3. Create the instance:
   - Shape: **VM.Standard.A1.Flex, 2 OCPU / 12 GB**, which leaves half the free allowance for later projects.
   - Image: **Ubuntu 24.04** (aarch64).
   - Network: the default "create new VCN" with a public subnet and a public IPv4.
   - SSH: paste in a public key (`~/.ssh/id_ed25519.pub`).
4. Networking › VCN › Security List: add ingress rules for **TCP 80 and 443** from `0.0.0.0/0`.
5. Note the public IP. Optionally convert it to a *reserved* IP so it survives the instance being recreated.

### 2. Mike: DNS (123 Reg control panel)
- 123 Reg › Manage domain › **Manage DNS** › Advanced DNS: add an `A` record, hostname `casino` → the VM's IP. Leave the existing GitHub Pages `www` and apex records alone.

### 3. Server setup (over SSH; Claude can run this once Mike gives the host)
```sh
sudo apt update && sudo apt full-upgrade -y
# Oracle's Ubuntu image has its own iptables that REJECTs everything but 22, the classic gotcha:
sudo iptables -I INPUT 5 -p tcp -m multiport --dports 80,443 -m state --state NEW -j ACCEPT
sudo netfilter-persistent save
# Python 3.14 to match the project (Ubuntu ships 3.12):
curl -LsSf https://astral.sh/uv/install.sh | sh
# Caddy from its apt repo (caddyserver.com/docs/install#debian-ubuntu-raspbian)
sudo apt install -y caddy
sudo useradd -r -m -d /srv/casino casino
```

### 4. Claude, locally: deploy bundle and script (`tools/deploy_demo.sh` + `deploy/`)
- **Demo data dir, built from a copy of live** (`sqlite3 .backup`, never touching the live file). Delete accounts, players and ledger rows so nobody inherits Mike's wallet; keep the roster, meta/settings, the floor plan, `looks/`, `plan/`, `plan_assets/` and the sounds/slot JSON. Skip `tls/` and the `*.pre-*.sqlite` backups.
- **What to ship:**
  - `server/casino_server` and `requirements.txt` (minus pytest and playwright)
  - `build/web`
  - `lpc_cache`, `sound_library`, `slot_art` and `slot_builds`, about 85 MB
  - **not** `slot_designs/` (397 MB, admin-only), unless a check shows that built slots read from it at runtime
- **`deploy/Caddyfile`:**
  ```
  casino.mikehadfield.co.uk {
      encode zstd gzip
      @admin path /admin* /maintenance* /admin-ui/* /slot-design* /credits
      @adminapi {
          path /api/*
          not path /api/look-options /api/looks/preview /api/plan/art /api/slots/art/manifest /api/sounds/manifest
      }
      respond @admin 404
      respond @adminapi 404
      reverse_proxy 127.0.0.1:8660
  }
  ```
  (`/credits` is kept public if the client links to it; to be checked.)
- **`deploy/casino-demo.service`** (systemd): `User=casino`, `WorkingDirectory=/srv/casino/server`, `ExecStart=.venv/bin/python -m casino_server`, `Environment=CASINO_HOST=127.0.0.1 CASINO_PORT=8660 CASINO_DATA_DIR=/srv/casino/data CASINO_WEB_DIR=/srv/casino/web`, `Restart=always`, `MemoryMax=2G`.
- **`tools/deploy_demo.sh HOST`:** an rsync of code and export (the data dir only on the first deploy, so demo players aren't wiped), `uv venv -p 3.14 && uv pip install -r`, then `systemctl restart casino-demo`.

### 5. First run
`sudo systemctl enable --now casino-demo caddy`. Caddy gets the Let's Encrypt certificate on the first request once DNS has propagated.

## Phase 2 (later, not this pass)
- The `demo` branch with a `CASINO_DEMO=1` flag (no admin routes or Odysseus worker, a fixed roster and floor), a nightly data reset, and a name filter or pick-list for characters.
- A "Play the demo" project page in `~/Projects/webserver`.
- Moving to the paid VPS is the same steps 3–5 against a new host.

## Done when
- [ ] On the VM: `curl -s 127.0.0.1:8660/ | head` returns the export's index.html
- [ ] `curl -I https://casino.mikehadfield.co.uk` returns 200, and `curl -I https://casino.mikehadfield.co.uk/admin` and `…/api/players` return 404
- [ ] One `tools/shot.py` run against the public URL joins the floor over `wss://`
- [ ] Mike opens it in Edge on a work PC (firewall plus the no-GPU WebGL path)

## Handoff
Rewrite this whenever a session stops, so the next one can carry on.
- **State:** not started, waiting for Mike to finish refining the game and say go. Mike does steps 1–2 (Oracle, 123 Reg) first.
- **Changed:** nothing yet
- **Checked:** nothing yet
- **Questions for Mike:** none yet
