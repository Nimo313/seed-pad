# SEED mit dem Steam Controller (2026) spielen — ohne Steam.
# Rechtes Pad = Trackball-Maus, linkes Pad = Zoom-Rad, Pad-Klick links = Radialmenü,
# Sticks = Kamera (WASD / QERF), Trigger = Maustasten, LB/RB = Shift/Strg.
# Beenden: Steam + B. Pause (z. B. zum Tippen): Steam + X.
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).parent
sys.path.insert(0, str(HIER))

import pad_eingabe as ei
import pad_hid
import pad_tastatur
from pad_radial import Radialmenue
from pad_tastatur import Tastatur

TRIGGER_AN, TRIGGER_AUS = 13000, 9000
STICK_AN, STICK_AUS = 11000, 8000
RADIAL_RING = 10000

LETZTER = None   # jüngster Controller-Zustand, für die Testansicht der App


def basis():
    """Ordner neben der EXE (gefroren) bzw. neben den Skripten."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return HIER


def config_pfad():
    return basis() / "pad_belegung.json"


def config_laden():
    p = config_pfad()
    if not p.exists():
        # EXE ohne Belegung daneben: mitgelieferten Standard herauslegen
        quelle = Path(getattr(sys, "_MEIPASS", HIER)) / "pad_belegung.json"
        p.write_text(quelle.read_text(encoding="utf-8"), encoding="utf-8")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def steam_laeuft():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq steam.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, encoding="cp850", errors="replace")
    return "steam.exe" in (r.stdout or "")


class Halter:
    """Merkt gehaltene Aktionen, löst sie sauber wieder. Bei Anker-Tasten
    (Kamera drehen/ziehen) springt der Cursor beim Loslassen zurück."""
    def __init__(self, anker_tasten=()):
        self.offen = {}
        self.anker_tasten = set(anker_tasten)
        self.anker = {}

    def setzen(self, name, teile, runter):
        if runter and name not in self.offen:
            if self.anker_tasten.intersection(teile):
                self.anker[name] = ei.cursor_pos()
            ei.aktion(teile, True)
            self.offen[name] = teile
        elif not runter and name in self.offen:
            ei.aktion(self.offen.pop(name), False)
            p = self.anker.pop(name, None)
            if p:
                ei.cursor_setzen(*p)

    def alles_loesen(self):
        ei.alles_loslassen(self.offen)
        self.anker.clear()


class Trackball:
    def __init__(self, cfg):
        self.faktor = 0.045 * cfg.get("empfindlichkeit", 1.0)
        self.reibung = cfg.get("reibung", 4.0)
        self.schwung_ab = cfg.get("schwung_ab", 500.0)
        self.lx = self.ly = None
        self.vx = self.vy = 0.0
        self.rx = self.ry = 0.0      # Pixel-Reste
        self.gleitet = False

    def tick(self, beruehrt, x, y, dt):
        dx = dy = 0.0
        if beruehrt:
            self.gleitet = False
            if self.lx is not None:
                dx = (x - self.lx) * self.faktor
                dy = -(y - self.ly) * self.faktor
                if dt > 0:
                    a = 0.35
                    self.vx = (1 - a) * self.vx + a * dx / dt
                    self.vy = (1 - a) * self.vy + a * dy / dt
            self.lx, self.ly = x, y
        else:
            if self.lx is not None:          # gerade losgelassen
                self.lx = self.ly = None
                if math.hypot(self.vx, self.vy) >= self.schwung_ab:
                    self.gleitet = True
            if self.gleitet:
                d = math.exp(-self.reibung * dt)
                self.vx *= d
                self.vy *= d
                if math.hypot(self.vx, self.vy) < 60:
                    self.gleitet = False
                    self.vx = self.vy = 0.0
                else:
                    dx, dy = self.vx * dt, self.vy * dt
        if dx or dy:
            self.rx += dx
            self.ry += dy
            gx, gy = int(self.rx), int(self.ry)
            self.rx -= gx
            self.ry -= gy
            if gx or gy:
                ei.maus_bewegen(gx, gy)

    def stopp(self):
        """Pad ignorieren (z. B. Handballen streift es, während der Stick
        benutzt wird): Position vergessen, keinen Schwung aufbauen."""
        self.lx = self.ly = None
        self.vx = self.vy = 0.0
        self.gleitet = False


class Rollrad:
    def __init__(self, cfg, tipp):
        self.schritt = cfg.get("weg_je_raste", 6000)
        self.tipp = tipp
        self.ly = None
        self.rest = 0.0

    def tick(self, beruehrt, y):
        if not beruehrt:
            self.ly = None
            self.rest = 0.0
            return
        if self.ly is not None:
            self.rest += y - self.ly
            while abs(self.rest) >= self.schritt:
                r = 1 if self.rest > 0 else -1
                self.rest -= r * self.schritt
                ei.rad(120 * r)
                self.tipp()
        self.ly = y


class Kreuz:
    """Stick → 4 gehaltene Tasten mit Hysterese. Ebene 2 greift beim Drücken
    (Belegung dort gesetzt → sie, sonst Ebene 1)."""
    def __init__(self, halter, kennung, belegung, belegung2=None):
        self.h = halter
        self.k = kennung
        self.b1 = {r: ei.kombi_parsen(t) for r, t in belegung.items() if t}
        self.b2 = {r: ei.kombi_parsen(t)
                   for r, t in (belegung2 or {}).items() if t}
        self.an = {r: False for r in set(self.b1) | set(self.b2)}

    def tick(self, x, y, ebene2=False):
        werte = {"rechts": x, "links": -x, "oben": y, "unten": -y}
        for r in self.an:
            w = werte[r]
            if not self.an[r] and w > STICK_AN:
                teile = (self.b2.get(r) if ebene2 else None) or self.b1.get(r)
                if teile:
                    self.an[r] = True
                    self.h.setzen(f"{self.k}:{r}", teile, True)
            elif self.an[r] and w < STICK_AUS:
                self.an[r] = False
                self.h.setzen(f"{self.k}:{r}", [], False)


def lauf(stop=None, melden=print):
    """Engine-Schleife. stop: threading.Event zum Beenden von außen,
    melden: bekommt Statuszeilen."""
    global LETZTER
    cfg = config_laden()
    if steam_laeuft():
        melden("⚠ Steam läuft: Steam Input steuert sonst doppelt."
               " Steam beenden oder dort die Steuerung für diesen Controller abschalten.")

    sc = pad_hid.Controller()
    melden("Suche Controller… (einschalten: Steam-Taste)")
    if not sc.verbinden(lambda: melden("Noch nichts gefunden — Puck angesteckt, Controller an?"),
                        stop=stop):
        return
    melden("Controller verbunden.")

    maus_cfg = cfg.get("maus", {})
    radial = Radialmenue(cfg.get("radial", []))
    halter = Halter(maus_cfg.get("anker", ["maus_rechts", "maus_mitte"]))
    anker_festhalten = maus_cfg.get("anker_festhalten", False)
    ball = Trackball(maus_cfg)
    rolle = Rollrad(cfg.get("zoom", {}), lambda: sc.haptik_ton(0, 1200, 8, -6))
    eb2_cfg = cfg.get("ebene2", {})

    def rs_drehen(belegung):
        b = dict(belegung)
        inv = cfg.get("stick_rechts_invert", {})
        if inv.get("hoch_runter"):
            b["oben"], b["unten"] = b.get("unten"), b.get("oben")
        if inv.get("links_rechts"):
            b["links"], b["rechts"] = b.get("rechts"), b.get("links")
        return b

    sticks = [
        Kreuz(halter, "ls", cfg.get("stick_links", {}),
              eb2_cfg.get("stick_links", {})),
        Kreuz(halter, "rs", rs_drehen(cfg.get("stick_rechts", {})),
              rs_drehen(eb2_cfg.get("stick_rechts", {}))),
    ]
    tasten1 = {n: ei.kombi_parsen(t)
               for n, t in cfg.get("tasten", {}).items() if t}
    tasten2 = {n: ei.kombi_parsen(t)
               for n, t in eb2_cfg.get("tasten", {}).items() if t}

    def trigger_parsen(quelle):
        roh = {"lt": quelle.get("links"), "rt": quelle.get("rechts")}
        return {k: ei.kombi_parsen(v) for k, v in roh.items() if v}

    trigger1 = trigger_parsen(cfg.get("trigger",
                                      {"links": "maus_rechts",
                                       "rechts": "maus_links"}))
    trigger2 = trigger_parsen(eb2_cfg.get("trigger", {}))
    trigger_an = {"lt": False, "rt": False}

    ebene_taste = cfg.get("ebene", {}).get("taste")
    sr_cfg = cfg.get("schreibrad", {})
    sr_taste = sr_cfg.get("taste", "QAM") if sr_cfg.get("an", True) else None
    tastatur = Tastatur() if sr_taste else None
    sr_aktiv = False
    sr_gezeigt = (None, None, False)
    sr_loeschen_ab = None      # nächster Wiederhol-Zeitpunkt für ⌫ (B halten)
    reserviert = {ebene_taste, sr_taste} - {None}

    tipp_klick = maus_cfg.get("tipp_klick", True)
    tipp_start = None          # (Zeit, x, y)
    tipp_tot = False           # zu lange, zu weit oder fester Klick dabei
    # Beim Klicken muss der Cursor stillstehen, sonst schluckt SEED den Klick:
    # nach jedem Linksklick-Beginn kurz einfrieren
    klick_ruhe_dauer = maus_cfg.get("klick_ruhe", 0.15)
    klick_ruhe = 0.0

    pause = False
    radial_offen = False
    alt = None
    letzte_zeit = time.monotonic()
    letzte_batterie = None

    melden("Läuft. Beenden: Steam + B · Pause: Steam + X")
    try:
        while not (stop and stop.is_set()):
            try:
                z = sc.lesen(4)
            except ConnectionError:
                halter.alles_loesen()
                melden("Verbindung weg — suche neu…")
                sc.schliessen()
                if not sc.verbinden(stop=stop):
                    break
                alt = None
                melden("Wieder verbunden.")
                continue
            jetzt = time.monotonic()
            dt = min(jetzt - letzte_zeit, 0.05)

            if sc.batterie and sc.batterie != letzte_batterie:
                letzte_batterie = sc.batterie
                melden(f"Akku: {letzte_batterie[0]} %"
                       + (" (lädt)" if letzte_batterie[1] else ""))

            if z is None:
                if not pause:
                    ball.tick(False, 0, 0, dt)   # Schwung weiterlaufen lassen
                letzte_zeit = jetzt
                continue
            letzte_zeit = jetzt
            LETZTER = z

            steam = z.gedrueckt("Steam")
            if alt is not None and steam:
                if z.gedrueckt("B") and not alt.gedrueckt("B"):
                    break
                if z.gedrueckt("X") and not alt.gedrueckt("X"):
                    pause = not pause
                    halter.alles_loesen()
                    sc.haptik_ton(1, 400 if pause else 900, 60, -3)
                    melden("Pause." if pause else "Weiter.")
            if pause or alt is None:
                alt = z
                continue

            # Tastatur an/aus und Tipp-Modus
            if (sr_taste and not steam and z.gedrueckt(sr_taste)
                    and not alt.gedrueckt(sr_taste)):
                sr_aktiv = not sr_aktiv
                halter.alles_loesen()
                ball.stopp()
                sr_loeschen_ab = None
                if sr_aktiv:
                    tastatur.zeigen()
                else:
                    tastatur.verbergen()
                sc.haptik_ton(1, 900 if sr_aktiv else 500, 40, -3)
            if sr_aktiv:
                lk = (pad_tastatur.treffer(True, z.lpx, z.lpy)
                      if z.gedrueckt("LPad_Touch") else None)
                rk = (pad_tastatur.treffer(False, z.rpx, z.rpy)
                      if z.gedrueckt("RPad_Touch") else None)
                gross = z.gedrueckt("RB")
                if (lk, rk, gross) != sr_gezeigt:
                    sr_gezeigt = (lk, rk, gross)
                    tastatur.waehlen(lk, rk, gross)

                def tippen(idx, seite):
                    if idx is None:
                        return
                    zeichen = pad_tastatur.ZEICHEN[idx]
                    if gross:
                        zeichen = pad_tastatur.gross_zeichen(zeichen)
                    ei.text_tippen(zeichen)
                    sc.haptik_ton(seite, 1400, 10, -6)

                # LT/RT tippen die markierte Taste ihrer Hälfte
                for name, wert, idx, seite in (("lt", z.lt, lk, 0),
                                               ("rt", z.rt, rk, 1)):
                    if not trigger_an[name] and wert > TRIGGER_AN:
                        trigger_an[name] = True
                        tippen(idx, seite)
                    elif trigger_an[name] and wert < TRIGGER_AUS:
                        trigger_an[name] = False
                if z.gedrueckt("LPad_Klick") and not alt.gedrueckt("LPad_Klick"):
                    tippen(lk, 0)
                if z.gedrueckt("RPad_Klick") and not alt.gedrueckt("RPad_Klick"):
                    tippen(rk, 1)
                if z.gedrueckt("A") and not alt.gedrueckt("A"):
                    ei.text_tippen(" ")
                    sc.haptik_ton(1, 1000, 10, -6)
                if z.gedrueckt("Y") and not alt.gedrueckt("Y"):
                    ei.aktion(["enter"], True)
                    ei.aktion(["enter"], False)
                # B löscht; halten wiederholt
                if z.gedrueckt("B"):
                    if not alt.gedrueckt("B"):
                        ei.aktion(["ruecktaste"], True)
                        ei.aktion(["ruecktaste"], False)
                        sc.haptik_ton(1, 800, 10, -6)
                        sr_loeschen_ab = jetzt + 0.45
                    elif sr_loeschen_ab and jetzt >= sr_loeschen_ab:
                        ei.aktion(["ruecktaste"], True)
                        ei.aktion(["ruecktaste"], False)
                        sr_loeschen_ab = jetzt + 0.08
                else:
                    sr_loeschen_ab = None
                alt = z
                continue

            ebene2 = bool(ebene_taste) and z.gedrueckt(ebene_taste)

            # rechtes Pad: Maus — aber nicht, solange der rechte Stick
            # ausgelenkt ist (Daumenballen streift sonst das Pad)
            rs_aktiv = abs(z.rsx) > STICK_AUS or abs(z.rsy) > STICK_AUS
            if rs_aktiv:
                ball.stopp()
                tipp_start, tipp_tot = None, True
            else:
                beruehrt = z.gedrueckt("RPad_Touch")
                if jetzt < klick_ruhe or z.gedrueckt("RPad_Klick"):
                    ball.stopp()        # Cursor steht, solange geklickt wird
                else:
                    ball.tick(beruehrt, z.rpx, z.rpy, dt)
                if tipp_klick:
                    if beruehrt and tipp_start is None:
                        tipp_start, tipp_tot = (jetzt, z.rpx, z.rpy), False
                    elif beruehrt and not tipp_tot:
                        if (jetzt - tipp_start[0] > 0.18
                                or abs(z.rpx - tipp_start[1]) > 2500
                                or abs(z.rpy - tipp_start[2]) > 2500
                                or z.gedrueckt("RPad_Klick")):
                            tipp_tot = True
                    elif not beruehrt and tipp_start is not None:
                        if not tipp_tot:        # kurzes Antippen → Linksklick
                            klick_ruhe = jetzt + klick_ruhe_dauer
                            ei.maus_taste("maus_links", True)
                            ei.maus_taste("maus_links", False)
                        tipp_start = None
            if anker_festhalten and halter.anker:
                ei.cursor_setzen(*next(iter(halter.anker.values())))

            # linkes Pad: Radialmenü (geklickt) oder Zoom-Rad (nur berührt)
            klick = z.gedrueckt("LPad_Klick")
            if klick and not radial_offen:
                radial_offen = True
                radial.zeigen()
                sc.haptik_ton(0, 800, 25, -3)
            if radial_offen:
                r = math.hypot(z.lpx, z.lpy)
                if r > RADIAL_RING:
                    winkel = math.degrees(math.atan2(z.lpx, z.lpy)) % 360
                    radial.waehlen(winkel)
                else:
                    radial.waehlen(None)
                if not klick:
                    radial_offen = False
                    radial.verbergen()
                    time.sleep(0.05)             # Tk-Thread verarbeiten lassen
                    wahl = radial.letzte_auswahl()
                    if wahl and wahl.get("taste"):
                        teile = ei.kombi_parsen(wahl["taste"])
                        ei.aktion(teile, True)
                        time.sleep(0.03)
                        ei.aktion(teile, False)
                        sc.haptik_ton(0, 1500, 30, -3)
            else:
                # gleiche Handballen-Regel links: Stick ausgelenkt → kein Zoom
                ls_aktiv = abs(z.lsx) > STICK_AUS or abs(z.lsy) > STICK_AUS
                rolle.tick(z.gedrueckt("LPad_Touch") and not ls_aktiv, z.lpy)

            # Trigger → Maustasten (Ebene 2 greift beim Drücken)
            for name, wert in (("lt", z.lt), ("rt", z.rt)):
                if not trigger_an[name] and wert > TRIGGER_AN:
                    trigger_an[name] = True
                    teile = ((trigger2.get(name) if ebene2 else None)
                             or trigger1.get(name))
                    if teile:
                        if "maus_links" in teile:
                            klick_ruhe = jetzt + klick_ruhe_dauer
                        halter.setzen(name, teile, True)
                elif trigger_an[name] and wert < TRIGGER_AUS:
                    trigger_an[name] = False
                    halter.setzen(name, [], False)

            # Sticks → Kamera
            sticks[0].tick(z.lsx, z.lsy, ebene2)
            sticks[1].tick(z.rsx, z.rsy, ebene2)

            # Knöpfe → Tasten (nicht während Steam gehalten ist)
            if not steam:
                for name in set(tasten1) | set(tasten2):
                    if name in reserviert:
                        continue
                    war = alt.gedrueckt(name)
                    ist = z.gedrueckt(name)
                    if ist == war:
                        continue
                    if ist:
                        teile = ((tasten2.get(name) if ebene2 else None)
                                 or tasten1.get(name))
                        if teile:
                            if "maus_links" in teile:
                                klick_ruhe = jetzt + klick_ruhe_dauer
                            halter.setzen(name, teile, True)
                    else:
                        halter.setzen(name, [], False)

            alt = z
    finally:
        LETZTER = None
        halter.alles_loesen()
        sc.schliessen()
        radial.beenden()
        if tastatur:
            tastatur.beenden()
        melden("Beendet, alle Tasten gelöst.")


def main():
    try:
        lauf()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
