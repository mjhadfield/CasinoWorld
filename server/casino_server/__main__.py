"""
Runs the server on two ports:
  - HTTP  (CASINO_PORT, default 8660): the Godot editor/desktop build connects here (ws://).
  - HTTPS (CASINO_PORT + 1, default 8661): browsers on other devices use this one. Godot's web
    build refuses to start outside a "secure context" -- HTTPS, or localhost -- so
    http://<LAN IP>:8660 shows "Secure Context ... missing" in the browser.

The HTTPS certificate is self-signed and generated on first run into data/tls/, so each
device clicks through a one-time "not private" warning. Delete data/tls/ to regenerate it
(e.g. if the machine's LAN IP changes).
"""

import asyncio
import os
import socket
import subprocess
from pathlib import Path

import uvicorn

from casino_server.app import app

TLS_DIR = Path(__file__).resolve().parents[1] / "data" / "tls"


def lan_ip() -> str | None:
    """The address other devices reach this machine on (no packets are actually sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def ensure_cert() -> tuple[Path, Path] | None:
    cert, key = TLS_DIR / "cert.pem", TLS_DIR / "key.pem"
    if cert.exists() and key.exists():
        return cert, key
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    names = ["DNS:localhost", f"DNS:{socket.gethostname()}", "IP:127.0.0.1"]
    if ip := lan_ip():
        names.append(f"IP:{ip}")
    try:
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-days", "825",  # Apple rejects longer-lived server certs
             "-keyout", str(key), "-out", str(cert), "-subj", "/CN=Casino World",
             "-addext", f"subjectAltName={','.join(names)}",
             "-addext", "extendedKeyUsage=serverAuth"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"Could not create a TLS certificate ({e}); serving HTTP only.")
        return None
    return cert, key


async def serve(host: str, port: int):
    servers = [uvicorn.Server(uvicorn.Config(app, host=host, port=port))]
    if tls := ensure_cert():
        cert, key = tls
        app.state.https_port = port + 1
        servers.append(uvicorn.Server(uvicorn.Config(
            app, host=host, port=port + 1, ssl_certfile=str(cert), ssl_keyfile=str(key))))
        print(f"Browsers: https://{lan_ip() or 'localhost'}:{port + 1}  (accept the certificate warning once per device)", flush=True)
    await asyncio.gather(*(s.serve() for s in servers))


def main():
    host = os.environ.get("CASINO_HOST", "0.0.0.0")
    port = int(os.environ.get("CASINO_PORT", "8660"))
    asyncio.run(serve(host, port))


if __name__ == "__main__":
    main()
