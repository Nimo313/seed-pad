# Schreibrad: Tippen mit beiden Trackpads (Daisy-Wheel).
# Jedes Pad hat 8 Blütenblätter mit je 4 Zeichen (oben/links/rechts/unten),
# gewählt wird mit Y (oben), X (links), B (rechts), A (unten).
# Overlay wie pad_radial: Tk in eigenem Thread, klick-durchlässig, immer oben.
import ctypes
import math
import queue
import threading

LINKS = ["abcd", "efgh", "ijkl", "mnop", "qrst", "uvwx", "yzäö", "üß.,"]
RECHTS = ["1234", "5678", "90+-", "!?:;", "\"'()", "@/%&", "=*#_", "€$<>"]
TASTE_POS = {"Y": 0, "X": 1, "B": 2, "A": 3}   # Index im Blatt-Text

_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x80000
_WS_EX_TRANSPARENT = 0x20
_WS_EX_NOACTIVATE = 0x8000000
_WS_EX_TOPMOST = 0x8
_DURCHSICHTIG = "#010101"
_RAD = 185          # Radius eines Rads
_LUECKE = 60        # Abstand zwischen den Rädern


def blatt(winkel):
    """Winkel (0 = oben, im Uhrzeigersinn) → Blatt-Index 0..7."""
    return int(((winkel % 360) + 22.5) // 45) % 8


class Schreibrad:
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

    def waehlen(self, links_blatt, rechts_blatt, gross):
        """Markierte Blätter (Index oder None) und Groß-Zustand."""
        self._q.put(("waehlen", (links_blatt, rechts_blatt, gross)))

    def beenden(self):
        self._q.put(("ende", None))

    # — Tk-Thread —
    def _lauf(self):
        import tkinter as tk
        breite = 4 * _RAD + _LUECKE + 40
        hoehe = 2 * _RAD + 60
        w = self._w = tk.Tk()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", _DURCHSICHTIG)
        sx = (w.winfo_screenwidth() - breite) // 2
        sy = w.winfo_screenheight() - hoehe - 120
        w.geometry(f"{breite}x{hoehe}+{sx}+{sy}")
        lw = self._lw = tk.Canvas(w, width=breite, height=hoehe,
                                  bg=_DURCHSICHTIG, highlightthickness=0)
        lw.pack()
        w.withdraw()
        w.update_idletasks()
        h = ctypes.windll.user32.GetParent(w.winfo_id()) or w.winfo_id()
        stil = ctypes.windll.user32.GetWindowLongPtrW(h, _GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongPtrW(
            h, _GWL_EXSTYLE,
            stil | _WS_EX_LAYERED | _WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE | _WS_EX_TOPMOST)

        self._gross = False
        self._segmente = [[], []]   # je Rad: [(arc, [4 Text-Ids])]
        self._markiert = [None, None]
        for rad, zeichen in ((0, LINKS), (1, RECHTS)):
            mx = 20 + _RAD + rad * (2 * _RAD + _LUECKE)
            my = 30 + _RAD
            for i, gruppe in enumerate(zeichen):
                start_tk = 90 - i * 45 - 22.5
                seg = lw.create_arc(mx - _RAD, my - _RAD, mx + _RAD, my + _RAD,
                                    start=start_tk, extent=45,
                                    fill="#1c2430", outline="#45556b", width=2)
                wink = math.radians(90 - i * 45)
                bx = mx + math.cos(wink) * _RAD * 0.72
                by = my - math.sin(wink) * _RAD * 0.72
                texte = []
                # Raute: oben (Y), links (X), rechts (B), unten (A)
                for z, (dx, dy) in zip(gruppe, ((0, -20), (-18, 2), (18, 2), (0, 24))):
                    texte.append(lw.create_text(
                        bx + dx, by + dy, text=z, fill="#dde6f2",
                        font=("Segoe UI", 11, "bold")))
                self._segmente[rad].append((seg, texte))
            lw.create_oval(mx - 52, my - 52, mx + 52, my + 52,
                           fill="#10151d", outline="#45556b", width=2)
            lw.create_text(mx, my, text="Y oben · X links\nB rechts · A unten",
                           fill="#8899aa", justify="center",
                           font=("Segoe UI", 8))
        lw.create_text(breite / 2, hoehe - 14, fill="#aabbcc",
                       font=("Segoe UI", 9),
                       text="RT Leer · LT Löschen · RB groß · Pad-Klick rechts Enter · QAM schließen")
        self._bereit.set()
        self._takt()
        w.mainloop()

    def _faerben(self, rad, i, aktiv):
        seg, _ = self._segmente[rad][i]
        self._lw.itemconfig(seg, fill="#2f6fb3" if aktiv else "#1c2430")

    def _gross_zeichnen(self, gross):
        if gross == self._gross:
            return
        self._gross = gross
        for rad, zeichen in ((0, LINKS), (1, RECHTS)):
            for i, gruppe in enumerate(zeichen):
                _, texte = self._segmente[rad][i]
                for tid, z in zip(texte, gruppe):
                    self._lw.itemconfig(tid, text=z.upper() if gross else z)

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
                    links, rechts, gross = wert
                    for rad, neu in ((0, links), (1, rechts)):
                        if neu != self._markiert[rad]:
                            if self._markiert[rad] is not None:
                                self._faerben(rad, self._markiert[rad], False)
                            self._markiert[rad] = neu
                            if neu is not None:
                                self._faerben(rad, neu, True)
                    self._gross_zeichnen(gross)
                elif was == "ende":
                    self._w.destroy()
                    return
        except queue.Empty:
            pass
        self._w.after(16, self._takt)
