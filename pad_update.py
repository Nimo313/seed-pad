# Auto-Updater: holt Releases von github.com/Nimo313/seed-pad.
# Nur die EXE tauscht sich selbst aus; aus den Skripten heraus wird nur gemeldet.
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "Nimo313/seed-pad"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
KOPF = {"User-Agent": "seed-pad"}


def _tupel(tag):
    teile = tag.lstrip("vV").split(".")
    return tuple(int(t) for t in teile if t.isdigit())


def pruefen(version):
    """Neuere Version verfügbar? → (tag, download_url), sonst None.
    Wirft bei Netz-/API-Fehlern (Aufrufer fängt ab)."""
    anfrage = urllib.request.Request(API, headers=KOPF)
    with urllib.request.urlopen(anfrage, timeout=10) as antwort:
        daten = json.load(antwort)
    tag = daten.get("tag_name", "")
    if not tag or _tupel(tag) <= _tupel(version):
        return None
    for anhang in daten.get("assets", []):
        if anhang.get("name") == "SeedPad.exe":
            return tag, anhang["browser_download_url"]
    return None


def installieren(url, melden=print):
    """Lädt die neue EXE neben die laufende und startet das Tausch-Skript.
    Danach muss die App sich beenden. True = Austausch angestoßen."""
    if not getattr(sys, "frozen", False):
        melden("Update bitte per git pull holen (läuft nicht als EXE).")
        return False
    ordner = Path(sys.executable).parent
    neu = ordner / "SeedPad_neu.exe"
    anfrage = urllib.request.Request(url, headers=KOPF)
    with urllib.request.urlopen(anfrage, timeout=60) as antwort, open(neu, "wb") as f:
        while True:
            stueck = antwort.read(1 << 16)
            if not stueck:
                break
            f.write(stueck)
    bat = ordner / "seedpad_update.bat"
    bat.write_text(
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        ':warte\r\n'
        'ping -n 2 127.0.0.1 >nul\r\n'
        'tasklist /FI "IMAGENAME eq SeedPad.exe" | find /i "SeedPad.exe" >nul'
        ' && goto warte\r\n'
        'move /y "SeedPad_neu.exe" "SeedPad.exe" >nul\r\n'
        'start "" "SeedPad.exe"\r\n'
        'del "%~f0"\r\n',
        encoding="ascii")
    subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(ordner),
                     creationflags=subprocess.CREATE_NO_WINDOW)
    return True
