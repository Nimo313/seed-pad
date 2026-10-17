# Maus und Tastatur per SendInput erzeugen (Scancodes, damit Unity sie sieht).
import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32

_MAUS = 0
_TASTATUR = 1
_M_MOVE = 0x0001
_M_RAD = 0x0800
_T_AUF = 0x0002
_T_SCAN = 0x0008
_T_ERWEITERT = 0x0001

_MAUS_FLAGS = {  # name: (runter, hoch)
    "maus_links": (0x0002, 0x0004),
    "maus_rechts": (0x0008, 0x0010),
    "maus_mitte": (0x0020, 0x0040),
}

_VK = {
    "esc": 0x1B, "tab": 0x09, "enter": 0x0D, "leer": 0x20,
    "shift": 0xA0, "strg": 0xA2, "alt": 0xA4,
    "entf": 0x2E, "einfg": 0x2D, "pos1": 0x24, "ende": 0x23,
    "bildauf": 0x21, "bildab": 0x22,
    "links": 0x25, "oben": 0x26, "rechts": 0x27, "unten": 0x28,
    "numplus": 0x6B, "numminus": 0x6D,
    "plus": 0xBB, "minus": 0xBD,   # +/− der Schreibtastatur (de-Layout)
}
for _i in range(1, 13):
    _VK[f"f{_i}"] = 0x6F + _i
for _c in "abcdefghijklmnopqrstuvwxyz":
    _VK[_c] = ord(_c.upper())
for _c in "0123456789":
    _VK[_c] = ord(_c)

# Tasten, deren Scancode das Erweitert-Flag braucht
_ERWEITERT = {"entf", "einfg", "pos1", "ende", "bildauf", "bildab",
              "links", "oben", "rechts", "unten"}


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]


class _EINGABE(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _senden(e):
    _user32.SendInput(1, ctypes.byref(e), ctypes.sizeof(_EINGABE))


def cursor_pos():
    p = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def cursor_setzen(x, y):
    _user32.SetCursorPos(int(x), int(y))


def maus_bewegen(dx, dy):
    e = _EINGABE(type=_MAUS)
    e.mi = _MOUSEINPUT(int(dx), int(dy), 0, _M_MOVE, 0, None)
    _senden(e)


def rad(schritte):
    """Mausrad; schritte in 120er-Einheiten (positiv = hoch/rein)."""
    e = _EINGABE(type=_MAUS)
    e.mi = _MOUSEINPUT(0, 0, ctypes.c_uint32(schritte & 0xFFFFFFFF).value, _M_RAD, 0, None)
    _senden(e)


def maus_taste(name, runter):
    e = _EINGABE(type=_MAUS)
    e.mi = _MOUSEINPUT(0, 0, 0, _MAUS_FLAGS[name][0 if runter else 1], 0, None)
    _senden(e)


def _taste_roh(name, runter):
    vk = _VK[name]
    scan = _user32.MapVirtualKeyW(vk, 0)
    flags = _T_SCAN
    if name in _ERWEITERT:
        flags |= _T_ERWEITERT
    if not runter:
        flags |= _T_AUF
    e = _EINGABE(type=_TASTATUR)
    e.ki = _KEYBDINPUT(0, scan, flags, 0, None)
    _senden(e)


def kombi_parsen(text):
    """'strg+p' → ['strg', 'p']; prüft die Namen."""
    teile = [t.strip().lower() for t in text.split("+") if t.strip()]
    for t in teile:
        if t not in _VK and t not in _MAUS_FLAGS and t not in ("rad_hoch", "rad_runter"):
            raise ValueError(f"Unbekannte Taste: {t!r}")
    return teile


def aktion(teile, runter):
    """Tastenkombi oder Maustaste drücken/lösen. rad_* feuert nur beim Drücken."""
    folge = teile if runter else reversed(teile)
    for t in folge:
        if t in _MAUS_FLAGS:
            maus_taste(t, runter)
        elif t == "rad_hoch":
            if runter:
                rad(120)
        elif t == "rad_runter":
            if runter:
                rad(-120)
        else:
            _taste_roh(t, runter)


def alles_loslassen(gedrueckt):
    """Sicherheitsnetz beim Beenden: alle gehaltenen Aktionen lösen."""
    for teile in list(gedrueckt.values()):
        aktion(teile, False)
    gedrueckt.clear()
