# Overlay-Tastatur: Tippen mit beiden Trackpads.
# Linkes Pad zielt auf die linke Tastaturhälfte, rechtes Pad auf die rechte;
# LT/RT oder Pad-Klick tippt die markierte Taste. A Leer, B ⌫ (halten),
# Y Enter, RB groß, QAM schließt.
import ctypes
import queue
import threading

REIHEN = ["1234567890ß", "qwertzuiopü", "asdfghjklöä", "yxcvbnm,.!?"]
KW, KH, LUECKE, RAND = 50, 50, 6, 14
BREITE = RAND * 2 + 11 * KW + 10 * LUECKE
HOEHE = RAND * 2 + len(REIHEN) * KH + (len(REIHEN) - 1) * LUECKE + 30

# Tastenliste: (mitte_x, mitte_y, zeichen); Index = Tasten-Id
TASTEN = []
for _r, _reihe in enumerate(REIHEN):
    for _s, _z in enumerate(_reihe):
        TASTEN.append((RAND + _s * (KW + LUECKE) + KW / 2,
                       RAND + _r * (KH + LUECKE) + KH / 2, _z))
ZEICHEN = [t[2] for t in TASTEN]
_FELD_H = len(REIHEN) * KH + (len(REIHEN) - 1) * LUECKE


# Nur die inneren ~65 % des Pads decken die ganze Hälfte ab — die Ecken
# erreicht man so, ohne an den Pad-Rand zu müssen.
_REICHWEITE = 0.65


def treffer(links, x, y):
    """Pad-Position (roh ±32767) → Tasten-Index in der jeweiligen Hälfte."""
    nx = max(-1.0, min(1.0, x / (32767 * _REICHWEITE)))
    ny = max(-1.0, min(1.0, y / (32767 * _REICHWEITE)))
    halb = (BREITE - 2 * RAND) / 2
    px = RAND + (0 if links else halb) + (nx + 1) / 2 * halb
    py = RAND + (1 - (ny + 1) / 2) * _FELD_H
    beste, abstand = None, None
    for i, (tx, ty, _) in enumerate(TASTEN):
        if links != (tx < BREITE / 2):
            continue
        d = (tx - px) ** 2 + (ty - py) ** 2
        if abstand is None or d < abstand:
            beste, abstand = i, d
    return beste


def gross_zeichen(zeichen):
    g = zeichen.upper()
    return g if len(g) == 1 else zeichen    # ß bleibt ß


_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x80000
_WS_EX_TRANSPARENT = 0x20
_WS_EX_NOACTIVATE = 0x8000000
_WS_EX_TOPMOST = 0x8
_DURCHSICHTIG = "#010101"


class Tastatur:
    def __init__(self):
        self._q = queue.Queue()
        self._bereit = threading.Event()
        threading.Thread(target=self._lauf, daemon=True).start()
        self._bereit.wait(5)

    # — Aufrufe aus der Engine —
    def zeigen(self):
        self._q.put(("zeigen", None))

    def verbergen(self):
        self._q.put(("verbergen", None))

    def waehlen(self, links_id, rechts_id, gross):
        self._q.put(("waehlen", (links_id, rechts_id, gross)))

    def beenden(self):
        self._q.put(("ende", None))

    # — Tk-Thread —
    def _lauf(self):
        import tkinter as tk
        w = self._w = tk.Tk()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", _DURCHSICHTIG)
        sx = (w.winfo_screenwidth() - BREITE) // 2
        sy = w.winfo_screenheight() - HOEHE - 100
        w.geometry(f"{BREITE}x{HOEHE}+{sx}+{sy}")
        lw = self._lw = tk.Canvas(w, width=BREITE, height=HOEHE,
                                  bg=_DURCHSICHTIG, highlightthickness=0)
        lw.pack()
        w.withdraw()
        w.update_idletasks()
        h = ctypes.windll.user32.GetParent(w.winfo_id()) or w.winfo_id()
        stil = ctypes.windll.user32.GetWindowLongPtrW(h, _GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongPtrW(
            h, _GWL_EXSTYLE,
            stil | _WS_EX_LAYERED | _WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE | _WS_EX_TOPMOST)

        lw.create_rectangle(2, 2, BREITE - 2, HOEHE - 2, fill="#10151d",
                            outline="#45556b", width=2)
        self._felder, self._texte = [], []
        for tx, ty, z in TASTEN:
            self._felder.append(lw.create_rectangle(
                tx - KW / 2, ty - KH / 2, tx + KW / 2, ty + KH / 2,
                fill="#1c2430", outline="#45556b"))
            self._texte.append(lw.create_text(
                tx, ty, text=z, fill="#dde6f2",
                font=("Segoe UI", 13, "bold")))
        lw.create_text(BREITE / 2, HOEHE - 16, fill="#aabbcc",
                       font=("Segoe UI", 9),
                       text="LT/RT oder Pad-Klick tippt · A Leer · B ⌫ (halten)"
                            " · Y Enter · RB groß · QAM schließen")
        self._markiert = [None, None]
        self._gross = False
        self._bereit.set()
        self._takt()
        w.mainloop()

    def _faerben(self, idx, farbe):
        self._lw.itemconfig(self._felder[idx], fill=farbe)

    def _takt(self):
        try:
            while True:
                was, wert = self._q.get_nowait()
                if was == "zeigen":
                    self._w.deiconify()
                    self._w.attributes("-topmost", True)
                elif was == "verbergen":
                    self._w.withdraw()
                elif was == "waehlen":
                    li, re, gross = wert
                    for seite, neu, farbe in ((0, li, "#2f6fb3"),
                                              (1, re, "#2f8f5b")):
                        if neu != self._markiert[seite]:
                            if self._markiert[seite] is not None:
                                self._faerben(self._markiert[seite], "#1c2430")
                            self._markiert[seite] = neu
                            if neu is not None:
                                self._faerben(neu, farbe)
                    if gross != self._gross:
                        self._gross = gross
                        for tid, z in zip(self._texte, ZEICHEN):
                            self._lw.itemconfig(
                                tid, text=gross_zeichen(z) if gross else z)
                elif was == "ende":
                    self._w.destroy()
                    return
        except queue.Empty:
            pass
        self._w.after(16, self._takt)
