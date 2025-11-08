# cloudflare_tunnel.py
# Gère Cloudflare Tunnel (Quick Tunnel ou tunnel nommé).
# - Crée/maj config.yml
# - Ajoute la route DNS si nécessaire
# - Lance cloudflared en arrière-plan
# - Stoppe proprement à la fermeture

import os
import atexit
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# --- Config via variables d'environnement ---
APP_HOST = os.getenv("APP_HOST", "127.0.0.1").strip()
APP_PORT = os.getenv("APP_PORT", "8000").strip()

TUNNEL_NAME = os.getenv("CLOUDFLARE_TUNNEL_NAME", "liacoaching-home").strip()
CREDENTIALS_FILE = os.getenv(
    "CLOUDFLARE_CREDENTIALS_FILE",
    str(Path.home() / ".cloudflared" / "81ab986e-21c9-47c6-98ea-10d47f71bf26.json")
).strip()
HOSTNAME = os.getenv("CLOUDFLARE_HOSTNAME", "").strip()

CLOUDFLARED = os.getenv("CLOUDFLARED_PATH") or shutil.which("cloudflared") or "cloudflared"
CLOUDFLARED_DIR = Path.home() / ".cloudflared"
CONFIG_FILE = CLOUDFLARED_DIR / "config.yml"

_proc: Optional[subprocess.Popen] = None


def _log(msg: str) -> None:
    print(f"[cloudflared] {msg}", flush=True)


def _ensure_named_config():
    """Crée/maj ~/.cloudflared/config.yml pour tunnel nommé."""
    if not Path(CREDENTIALS_FILE).exists():
        raise FileNotFoundError(
            f"Credentials introuvables : {CREDENTIALS_FILE}\n"
            f"→ Fais : cloudflared tunnel create {TUNNEL_NAME}"
        )
    CLOUDFLARED_DIR.mkdir(parents=True, exist_ok=True)
    content = (
        f"tunnel: {TUNNEL_NAME}\n"
        f"credentials-file: {CREDENTIALS_FILE}\n\n"
        f"ingress:\n"
        f"  - hostname: {HOSTNAME}\n"
        f"    service: http://{APP_HOST}:{APP_PORT}\n"
        f"  - service: http_status:404\n"
    )
    CONFIG_FILE.write_text(content, encoding="utf-8")
    _log(f"config.yml écrit → {CONFIG_FILE}")


def _ensure_route_dns():
    """Ajoute la route DNS Cloudflare (hostname → tunnel)."""
    cmd = [CLOUDFLARED, "tunnel", "route", "dns", TUNNEL_NAME, HOSTNAME]
    _log("Ajout de la route DNS…")
    try:
        subprocess.run(cmd, check=True)
        _log(f"Route DNS configurée : {HOSTNAME} → {TUNNEL_NAME}")
    except subprocess.CalledProcessError as e:
        _log(f"⚠️ Erreur lors de la config DNS : {e}")


def _terminate():
    global _proc
    if _proc and _proc.poll() is None:
        _log(f"Arrêt du tunnel (PID={_proc.pid})…")
        try:
            if os.name == "nt":
                _proc.terminate()
            else:
                _proc.send_signal(signal.SIGTERM)
        except Exception:
            pass
        time.sleep(1)
        if _proc.poll() is None:
            _proc.kill()
        _log("Tunnel arrêté.")


def start_cloudflared():
    """Démarre cloudflared (Quick Tunnel si pas de hostname, sinon tunnel nommé + DNS)."""
    global _proc
    if not (shutil.which(CLOUDFLARED) or Path(CLOUDFLARED).exists()):
        raise FileNotFoundError("cloudflared introuvable (PATH ou CLOUDFLARED_PATH).")

    if HOSTNAME:
        _ensure_named_config()
        _ensure_route_dns()  # <<< ajout automatique de la route DNS
        cmd = [CLOUDFLARED, "tunnel", "run", TUNNEL_NAME]
        _log("Démarrage du tunnel nommé…")
        _proc = subprocess.Popen(cmd)
        _log(f"Tunnel actif → https://{HOSTNAME}")
    else:
        cmd = [CLOUDFLARED, "tunnel", "--url", f"http://{APP_HOST}:{APP_PORT}"]
        _log("Démarrage Quick Tunnel (URL temporaire)…")
        _proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # Tente d'afficher l'URL .trycloudflare.com
        t0 = time.time()
        while time.time() - t0 < 15:
            line = _proc.stdout.readline() if _proc.stdout else ""
            if not line:
                continue
            sys.stdout.write("[cloudflared] " + line)
            if "trycloudflare.com" in line:
                break

    atexit.register(_terminate)
    if os.name != "nt":
        signal.signal(signal.SIGINT, lambda *_: _terminate())
        signal.signal(signal.SIGTERM, lambda *_: _terminate())
    return _proc
