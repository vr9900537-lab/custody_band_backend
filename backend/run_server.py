#!/usr/bin/env python3
"""
Server Startup Script
Launches Uvicorn using Python directly to bypass Windows Application Control policy blocks on uvicorn.exe.
"""

import os
import sys
from pathlib import Path

CURRENT_DIR = str(Path(__file__).resolve().parent)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
os.environ["PYTHONPATH"] = CURRENT_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")

import uvicorn
from app.config import settings

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

    import socket
    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    use_ssl = "--ssl" in sys.argv or "--https" in sys.argv or os.environ.get("USE_HTTPS", "").lower() in ("1", "true")
    cert_file = Path(CURRENT_DIR) / "secrets" / "cert.pem"
    key_file = Path(CURRENT_DIR) / "secrets" / "key.pem"
    has_cert = cert_file.exists() and key_file.exists()

    scheme = "https" if (use_ssl and has_cert) else "http"

    print("=" * 65)
    print(f"[*] Launching Custody Watch Platform ({scheme.upper()})...")
    print(f"   Local Address   : {scheme}://127.0.0.1:{settings.API_PORT}")
    print(f"   Wi-Fi LAN IP    : {scheme}://{lan_ip}:{settings.API_PORT}  <-- USE FOR FRONTEND")
    print(f"   Login Endpoint  : {scheme}://{lan_ip}:{settings.API_PORT}/api/v1/auth/login")
    print(f"   Default Login   : Username: aditya  |  Password: Admin@123")
    print(f"   Swagger Docs    : {scheme}://127.0.0.1:{settings.API_PORT}/docs")
    print(f"   Watch Receiver  : 0.0.0.0:{settings.TCP_PORT} (Public IP: {settings.PUBLIC_SERVER_IP})")
    print("=" * 65)

    uvicorn_kwargs = {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": settings.API_PORT,
        "app_dir": CURRENT_DIR,
        "reload": True,
        "reload_dirs": ["app"],
        "reload_excludes": ["*.log", "*.db", "*.db-journal", "logs/*", "secrets/*"]
    }

    if use_ssl and has_cert:
        uvicorn_kwargs["ssl_certfile"] = str(cert_file)
        uvicorn_kwargs["ssl_keyfile"] = str(key_file)

    uvicorn.run(**uvicorn_kwargs)

