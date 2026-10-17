# Radialmenü-Overlay (Tkinter in eigenem Thread, klick-durchlässig, immer oben).
# Funktioniert über Borderless-Fenstern; SEED läuft laut Settings borderless.
import ctypes
import math
import queue
import threading

_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x80000
_WS_EX_TRANSPARENT = 0x20
_WS_EX_NOACTIVATE = 0x8000000
_WS_EX_TOPMOST = 0x8

_DURCHSICHTIG = "#010101"   # Transparenzfarbe
_GROESSE = 460


class Radialmenue:
    def __init__(self, eintraege):
        """eintraege: Liste von {'name': …, 'taste': …}."""
        self.eintraege = eintraege
        self._q = queue.Queue()
        self._auswahl = None
        self._bereit = threading.Event()
        t = threading.Thread(target=self._lauf, daemon=True)
        t.start()
        self._bereit.wait(5)

    # — Aufrufe aus dem Hauptthread —
    def zeigen(self):
        self._q.put(("zeigen", None))

    def waehlen(self, winkel):
        """winkel in Grad (0 = oben, im Uhrzeigersinn) oder None = Mitte."""
        self._q.put(("waehlen", winkel))

    def verbergen(self):
        """Menü zu; liefert den gewählten Eintrag oder None."""
        self._q.put(("verbergen", None))
        return None  # Auswahl holt der Aufrufer über letzte_auswahl()

    def letzte_auswahl(self):
        a, self._auswahl = self._auswahl, None
        return a

    def beenden(self):
        """Tk-Thread sauber schließen (für Neustart der Engine)."""
        self._q.put(("ende", None))

    # — Tk-Thread —
    def _lauf(self):
        import tkinter as tk
        n = max(1, len(self.eintraege))
        g = _GROESSE
        self._wurzel = tk.Tk()
        w = self._wurzel
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", _DURCHSICHTIG)
        bx = (w.winfo_screenwidth() - g) // 2
        by = (w.winfo_screenheight() - g) // 2
        w.geometry(f"{g}x{g}+{bx}+{by}")
        lw = tk.Canvas(w, width=g, height=g, bg=_DURCHSICHTIG,
                       highlightthickness=0)
        lw.pack()
        self._lw = lw
        w.withdraw()
        w.update_idletasks()

        # klick-durchlässig + nicht aktivierbar
        h = ctypes.windll.user32.GetParent(w.winfo_id()) or w.winfo_id()
        stil = ctypes.windll.user32.GetWindowLongPtrW(h, _GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongPtrW(
            h, _GWL_EXSTYLE,
            stil | _WS_EX_LAYERED | _WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE | _WS_EX_TOPMOST)

        self._segmente = []
        rand, mitte = 10, g / 2
        schritt = 360 / n
        for i, e in enumerate(self.eintraege):
            # Tk-Winkel: 0° = rechts, gegen Uhrzeiger. Segment i mittig um
            # „oben + i·schritt im Uhrzeigersinn".
            start_tk = 90 - i * schritt - schritt / 2
            seg = lw.create_arc(rand, rand, g - rand, g - rand,
                                start=start_tk, extent=schritt,
                                fill="#1c2430", outline="#45556b", width=2)
            wink = math.radians(90 - (i * schritt))  # Mitte des Segments, 0=oben
            tx = mitte + math.cos(wink) * (mitte - rand) * 0.68
            ty = mitte - math.sin(wink) * (mitte - rand) * 0.68
            txt = lw.create_text(tx, ty, text=e["name"], fill="#dde6f2",
                                 font=("Segoe UI", 11, "bold"))
            self._segmente.append((seg, txt))
        lw.create_oval(mitte - 48, mitte - 48, mitte + 48, mitte + 48,
                       fill="#10151d", outline="#45556b", width=2)
        self._mitte_txt = lw.create_text(mitte, mitte, text="×",
                                         fill="#8899aa", font=("Segoe UI", 16))
        self._markiert = None
        self._bereit.set()
        self._takt()
        w.mainloop()

    def _markieren(self, i):
        if i == self._markiert:
            return
        if self._markiert is not None:
            s, _ = self._segmente[self._markiert]
            self._lw.itemconfig(s, fill="#1c2430")
        self._markiert = i
        if i is not None:
            s, _ = self._segmente[i]
            self._lw.itemconfig(s, fill="#2f6fb3")

    def _takt(self):
        try:
            while True:
                was, wert = self._q.get_nowait()
                if was == "zeigen":
                    self._markieren(None)
                    self._wurzel.deiconify()
                    self._wurzel.attributes("-topmost", True)
                elif was == "waehlen":
                    if wert is None:
                        self._markieren(None)
                    else:
                        n = len(self.eintraege)
                        i = int(((wert % 360) + 360 / n / 2) // (360 / n)) % n
                        self._markieren(i)
                elif was == "verbergen":
                    if self._markiert is not None:
                        self._auswahl = self.eintraege[self._markiert]
                    self._wurzel.withdraw()
                elif was == "ende":
                    self._wurzel.destroy()
                    return
        except queue.Empty:
            pass
        self._wurzel.after(16, self._takt)
