# Steam Controller 2 (Triton) über HID lesen — ohne Steam.
# Protokoll: SDL3 (SDL_hidapi_steam_triton.c, controller_structs.h) und
# https://github.com/CouchTurtle/sc2-research (Report-0x42-Layout).
import time

import hid

VID_VALVE = 0x28DE
# 1302/1303 = Controller per USB, 1304 = Puck (Proteus), 1305 = Dongle (Nereid)
PIDS = {0x1302, 0x1303, 0x1304, 0x1305}

# Feature-Report (64 Byte, Report-ID 1)
ID_SET_SETTINGS_VALUES = 0x87
SETTING_LIZARD_MODE = 9
LIZARD_MODE_OFF = 0

# Report-IDs der Eingangsdaten
REP_STATE = 0x42        # 54 B (mit Quaternion) oder 46 B
REP_BATTERIE = 0x43
REP_STATE_BLE = 0x45    # gleicher Aufbau
REP_STATE_TS = 0x47     # gleicher Aufbau vorn, 16-Bit-IMU-Zeit hinten

# Tasten-Bits in Bytes 0x02..0x05 (uint32 LE); (byte-2)*8 + bit
KNOEPFE = {
    "A": 0, "B": 1, "X": 2, "Y": 3, "QAM": 4, "R3": 5, "View": 6, "R4": 7,
    "R5": 8, "RB": 9, "DPad_Unten": 10, "DPad_Rechts": 11, "DPad_Links": 12,
    "DPad_Oben": 13, "Menu": 14, "L3": 15,
    "Steam": 16, "L4": 17, "L5": 18, "LB": 19, "RStick_Touch": 20,
    "RPad_Touch": 21, "RPad_Klick": 22, "RTrig_Klick": 23,
    "LStick_Touch": 24, "LPad_Touch": 25, "LPad_Klick": 26, "LTrig_Klick": 27,
    "RGriff_Touch": 28, "LGriff_Touch": 29,
}


def _i16(lo, hi):
    w = lo | (hi << 8)
    return w - 0x10000 if w >= 0x8000 else w


class Zustand:
    __slots__ = ("knoepfe", "lt", "rt", "lsx", "lsy", "rsx", "rsy",
                 "lpx", "lpy", "lpd", "rpx", "rpy", "rpd", "seq")

    def gedrueckt(self, name):
        return bool(self.knoepfe & (1 << KNOEPFE[name]))


def zustand_lesen(d):
    """Report 0x42/0x45/0x47 → Zustand, sonst None."""
    z = Zustand()
    z.seq = d[1]
    z.knoepfe = d[2] | (d[3] << 8) | (d[4] << 16) | (d[5] << 24)
    z.lt = _i16(d[6], d[7])          # 0..32767
    z.rt = _i16(d[8], d[9])
    z.lsx = _i16(d[10], d[11])       # Sticks: ±32767, roh +Y = oben
    z.lsy = _i16(d[12], d[13])
    z.rsx = _i16(d[14], d[15])
    z.rsy = _i16(d[16], d[17])
    z.lpx = _i16(d[18], d[19])       # Pads: ±32767, roh +Y = oben
    z.lpy = _i16(d[20], d[21])
    z.lpd = d[22] | (d[23] << 8)     # Druck 0..32767
    z.rpx = _i16(d[24], d[25])
    z.rpy = _i16(d[26], d[27])
    z.rpd = d[28] | (d[29] << 8)
    return z


class Controller:
    """Findet den aktiven Triton (Puck-Slot oder USB) und liest Zustände."""

    def __init__(self):
        self.geraet = None
        self.pfad = None
        self._letzter_lizard = 0.0
        self.batterie = None       # (prozent, laedt)

    def _kandidaten(self):
        pfade = []
        for info in hid.enumerate(VID_VALVE):
            if info["product_id"] in PIDS and info["usage_page"] >= 0xFF00:
                pfade.append(info["path"])
        return pfade

    def verbinden(self, warte_meldung=None, stop=None):
        """Blockiert, bis ein Interface Zustandsreports liefert.
        True = verbunden, False = über stop abgebrochen."""
        gemeldet = False
        while not (stop and stop.is_set()):
            offen = []
            for pfad in self._kandidaten():
                try:
                    g = hid.device()
                    g.open_path(pfad)
                    g.set_nonblocking(1)
                    offen.append((pfad, g))
                except OSError:
                    pass
            ende = time.monotonic() + 2.0
            while time.monotonic() < ende:
                for pfad, g in offen:
                    try:
                        d = g.read(64)
                    except OSError:
                        continue
                    if d and d[0] in (REP_STATE, REP_STATE_BLE, REP_STATE_TS, REP_BATTERIE):
                        for p2, g2 in offen:
                            if p2 != pfad:
                                g2.close()
                        g.set_nonblocking(0)   # ab jetzt blockend mit Timeout
                        self.geraet, self.pfad = g, pfad
                        self.lizard_aus(erzwingen=True)
                        return True
                time.sleep(0.01)
            for _, g in offen:
                g.close()
            if warte_meldung and not gemeldet:
                warte_meldung()
                gemeldet = True
            time.sleep(1.0)
        return False

    def lizard_aus(self, erzwingen=False):
        """Eingebaute Maus/Tastatur-Emulation stummschalten (Watchdog: alle ~8 s
        wieder an, darum wie SDL alle 3 s auffrischen)."""
        jetzt = time.monotonic()
        if not erzwingen and jetzt - self._letzter_lizard < 3.0:
            return
        self._letzter_lizard = jetzt
        puffer = bytearray(64)
        puffer[0] = 1                        # Report-ID des Feature-Reports
        puffer[1] = ID_SET_SETTINGS_VALUES
        puffer[2] = 3                        # 1 × ControllerSetting (3 Byte)
        puffer[3] = SETTING_LIZARD_MODE
        puffer[4] = LIZARD_MODE_OFF
        puffer[5] = 0
        try:
            self.geraet.send_feature_report(bytes(puffer))
        except OSError:
            pass

    def lesen(self, zeit_ms=4):
        """Nächsten Report holen; Zustand oder None. Pflegt Batterie + Lizard."""
        self.lizard_aus()
        try:
            d = self.geraet.read(64, timeout_ms=zeit_ms)
        except OSError:
            raise ConnectionError("Verbindung zum Controller verloren")
        if not d:
            return None
        if d[0] in (REP_STATE, REP_STATE_BLE, REP_STATE_TS):
            return zustand_lesen(d)
        if d[0] == REP_BATTERIE and len(d) >= 3:
            self.batterie = (d[2], d[1] in (2, 3, 4))
        return None

    def haptik_ton(self, seite, frequenz, dauer_ms, gain_db=0):
        """Kurzer Ton über die Pad-Aktoren (Report 0x83, MsgHapticLfoTone).
        seite: 0 = Pad links, 1 = Pad rechts."""
        if gain_db < 0:
            gain_db += 0x100
        d = bytes([0x83, seite, gain_db,
                   frequenz & 0xFF, frequenz >> 8,
                   dauer_ms & 0xFF, dauer_ms >> 8,
                   0, 0, 0])
        try:
            self.geraet.write(d)
        except OSError:
            pass

    def schliessen(self):
        if self.geraet:
            try:
                self.geraet.close()
            except OSError:
                pass
            self.geraet = None
