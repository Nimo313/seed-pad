# SEED-Pad: kleine Anwendung mit Start/Stopp und Setup-Oberfläche.
# Belegen durch Drücken der echten Taste (auch Kombis wie Shift+Y).
# Liest/schreibt pad_belegung.json neben der EXE bzw. den Skripten.
import json
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

HIER = Path(__file__).parent
sys.path.insert(0, str(HIER))

import pad_eingabe as ei
import pad_update
import seed_pad

VERSION = "1.1.0"

KNOEPFE = [
    ("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y"),
    ("LB", "LB (Schulter links)"), ("RB", "RB (Schulter rechts)"),
    ("L4", "L4 (Griff links oben)"), ("L5", "L5 (Griff links unten)"),
    ("R4", "R4 (Griff rechts oben)"), ("R5", "R5 (Griff rechts unten)"),
    ("L3", "L3 (Stick links drücken)"), ("R3", "R3 (Stick rechts drücken)"),
    ("View", "View"), ("Menu", "Menu"), ("QAM", "QAM (…-Taste)"),
    ("DPad_Oben", "Kreuz oben"), ("DPad_Unten", "Kreuz unten"),
    ("DPad_Links", "Kreuz links"), ("DPad_Rechts", "Kreuz rechts"),
    ("RPad_Klick", "Rechtes Pad fest klicken"),
]
STICKS = [("stick_links", "Linker Stick"), ("stick_rechts", "Rechter Stick")]
RICHTUNGEN = ["oben", "unten", "links", "rechts"]
ZAHLEN = [  # (gruppe, schluessel, beschriftung, von, bis, schrittweite)
    ("maus", "empfindlichkeit", "Cursortempo", 0.1, 2.0, 0.05),
    ("maus", "reibung", "Schwung-Reibung (höher = kürzer)", 1, 20, 0.5),
    ("maus", "schwung_ab", "Schwung erst ab (px/s, 99999 = aus)", 0, 99999, 50),
    ("maus", "klick_ruhe", "Cursor-Stillstand beim Klick (s)", 0.0, 0.5, 0.05),
    ("zoom", "weg_je_raste", "Streichweg je Zoom-Raste", 1000, 20000, 500),
]

# Tk-Tastennamen → Namen aus pad_eingabe
TK_NAMEN = {
    "Escape": "esc", "Tab": "tab", "Return": "enter", "space": "leer",
    "Delete": "entf", "Insert": "einfg", "Home": "pos1", "End": "ende",
    "Prior": "bildauf", "Next": "bildab",
    "Left": "links", "Up": "oben", "Right": "rechts", "Down": "unten",
    "plus": "plus", "minus": "minus",
    "KP_Add": "numplus", "KP_Subtract": "numminus",
}
for _i in range(1, 13):
    TK_NAMEN[f"F{_i}"] = f"f{_i}"
for _c in "abcdefghijklmnopqrstuvwxyz0123456789":
    TK_NAMEN[_c] = _c
MODS = {"Shift_L": "shift", "Shift_R": "shift",
        "Control_L": "strg", "Control_R": "strg",
        "Alt_L": "alt", "Alt_R": "alt"}
MOD_FOLGE = ["strg", "alt", "shift"]


class Aufnahme(tk.Toplevel):
    """Modaler Dialog: nächste Taste/Kombi oder Maustaste wird die Belegung.
    fertig(None) = abgebrochen, fertig("") = geleert, sonst die Kombi."""

    def __init__(self, elter, titel, fertig):
        super().__init__(elter)
        self.fertig = fertig
        self.gehalten = []
        self.title(titel)
        self.resizable(False, False)
        self.transient(elter)
        ttk.Label(self, text=f"Belegung für: {titel}",
                  font=("Segoe UI", 10, "bold")).pack(padx=16, pady=(12, 2))
        self.anzeige = tk.StringVar(
            value="Taste oder Kombi drücken (z. B. Shift+Y) …")
        ttk.Label(self, textvariable=self.anzeige).pack(padx=16, pady=2)
        self.maus_feld = tk.Label(
            self, text="…oder hier klicken / rollen\nfür Maustaste und Mausrad",
            relief="groove", padx=14, pady=10)
        self.maus_feld.pack(padx=16, pady=8)
        leiste = ttk.Frame(self)
        leiste.pack(pady=(0, 12))
        ttk.Button(leiste, text="Leeren",
                   command=lambda: self._ende("")).pack(side="left", padx=4)
        ttk.Button(leiste, text="Abbrechen",
                   command=lambda: self._ende(None)).pack(side="left", padx=4)
        self.bind("<KeyPress>", self._taste_runter)
        self.bind("<KeyRelease>", self._taste_hoch)
        for knopf, name in ((1, "maus_links"), (2, "maus_mitte"),
                            (3, "maus_rechts")):
            self.maus_feld.bind(f"<Button-{knopf}>",
                                lambda e, n=name: self._maus(n))
        self.maus_feld.bind("<MouseWheel>", self._rad)
        self.grab_set()
        self.focus_set()
        # mittig über dem Hauptfenster
        self.update_idletasks()
        self.geometry(f"+{elter.winfo_rootx() + 180}+{elter.winfo_rooty() + 180}")

    def _kombi(self, taste):
        mods = [m for m in MOD_FOLGE if m in self.gehalten and m != taste]
        return "+".join(mods + [taste])

    def _taste_runter(self, e):
        mod = MODS.get(e.keysym)
        if mod:
            if mod not in self.gehalten:
                self.gehalten.append(mod)
            self.anzeige.set(" + ".join(self.gehalten) + " + …")
            return
        taste = TK_NAMEN.get(e.keysym)
        if taste is None:
            self.anzeige.set(f"„{e.keysym}“ kennt SEED-Pad nicht — andere Taste?")
            return
        self._ende(self._kombi(taste))

    def _taste_hoch(self, e):
        mod = MODS.get(e.keysym)
        if mod and mod in self.gehalten:
            # Modifier gedrückt und ohne weitere Taste losgelassen → er selbst
            self._ende(self._kombi(mod))

    def _maus(self, name):
        self._ende(self._kombi(name))

    def _rad(self, e):
        self._ende(self._kombi("rad_hoch" if e.delta > 0 else "rad_runter"))

    def _ende(self, wert):
        self.grab_release()
        self.destroy()
        self.fertig(wert)


class App:
    def __init__(self):
        self.cfg = seed_pad.config_laden()
        self.stop = None
        self.thread = None
        self.meldungen = queue.Queue()
        self.update_info = None
        self.update_knopf = None

        w = self.w = tk.Tk()
        w.title(f"SEED-Pad v{VERSION}")
        w.geometry("760x640")
        w.minsize(660, 520)

        kopf = ttk.Frame(w, padding=8)
        kopf.pack(fill="x")
        self.start_knopf = ttk.Button(kopf, text="▶ Start", command=self.start_stopp)
        self.start_knopf.pack(side="left")
        self.status = tk.StringVar(value="Bereit.")
        ttk.Label(kopf, textvariable=self.status).pack(side="left", padx=10)
        self.kopf = kopf

        self.mappe = ttk.Notebook(w)
        self.mappe.pack(fill="both", expand=True, padx=8, pady=4)
        self._tab_tasten()
        self._tab_maus()
        self._tab_radial()

        fuss = ttk.Frame(w, padding=8)
        fuss.pack(fill="x")
        ttk.Button(fuss, text="Speichern & übernehmen",
                   command=self.speichern).pack(side="left")
        ttk.Label(fuss, text="Steam + X = Pause · Steam + B = Stopp"
                  ).pack(side="right")

        self.protokoll = tk.Text(w, height=5, state="disabled",
                                 font=("Consolas", 9))
        self.protokoll.pack(fill="x", padx=8, pady=(0, 8))

        w.protocol("WM_DELETE_WINDOW", self.schliessen)
        w.after(150, self._takt)
        threading.Thread(target=self._update_pruefen, daemon=True).start()

    # — Belegungs-Knöpfe —
    def _belegung(self, elter, zeile, spalte, text, wert):
        """Label + Knopf; Klick öffnet die Aufnahme. Liefert die StringVar."""
        ttk.Label(elter, text=text).grid(row=zeile, column=spalte * 2,
                                         sticky="w", padx=(8, 4), pady=2)
        var = tk.StringVar(value=wert or "")
        knopf = ttk.Button(elter, text=wert or "—", width=16)

        def fertig(neu, var=var, knopf=knopf):
            if neu is None:
                return
            var.set(neu)
            knopf.config(text=neu or "—")

        knopf.config(command=lambda: Aufnahme(self.w, text, fertig))
        knopf.grid(row=zeile, column=spalte * 2 + 1, sticky="w", pady=2)
        return var

    # — Tabs —
    def _rollbar(self, elter):
        aussen = ttk.Frame(elter)
        lw = tk.Canvas(aussen, highlightthickness=0)
        balken = ttk.Scrollbar(aussen, orient="vertical", command=lw.yview)
        innen = ttk.Frame(lw)
        innen.bind("<Configure>",
                   lambda e: lw.configure(scrollregion=lw.bbox("all")))
        lw.create_window((0, 0), window=innen, anchor="nw")
        lw.configure(yscrollcommand=balken.set)
        lw.pack(side="left", fill="both", expand=True)
        balken.pack(side="right", fill="y")
        aussen.pack(fill="both", expand=True)
        return aussen, innen

    def _tab_tasten(self):
        rahmen = ttk.Frame(self.mappe)
        self.mappe.add(rahmen, text="Tasten")
        _, innen = self._rollbar(rahmen)
        self.v_tasten = {}
        tasten_cfg = self.cfg.get("tasten", {})
        for i, (name, text) in enumerate(KNOEPFE):
            self.v_tasten[name] = self._belegung(innen, i % 10, i // 10, text,
                                                 tasten_cfg.get(name))
        zeile = 10
        ttk.Separator(innen, orient="horizontal").grid(
            row=zeile, column=0, columnspan=4, sticky="ew", pady=6)
        tr = self.cfg.get("trigger", {})
        self.v_lt = self._belegung(innen, zeile + 1, 0, "LT (Trigger links)",
                                   tr.get("links"))
        self.v_rt = self._belegung(innen, zeile + 1, 1, "RT (Trigger rechts)",
                                   tr.get("rechts"))
        self.v_sticks = {}
        for s, (schluessel, text) in enumerate(STICKS):
            cfg_s = self.cfg.get(schluessel, {})
            for r, richtung in enumerate(RICHTUNGEN):
                self.v_sticks[(schluessel, richtung)] = self._belegung(
                    innen, zeile + 2 + r, s, f"{text} {richtung}",
                    cfg_s.get(richtung))
        ttk.Label(innen, foreground="#666", text=(
            "Knopf anklicken, dann die gewünschte Taste, Kombi (z. B. Shift+Y)\n"
            "oder Maustaste drücken. „Leeren“ nimmt die Belegung weg."
        )).grid(row=zeile + 7, column=0, columnspan=4, sticky="w",
                padx=8, pady=8)

    def _tab_maus(self):
        rahmen = ttk.Frame(self.mappe, padding=8)
        self.mappe.add(rahmen, text="Maus / Zoom")
        self.v_zahlen = {}
        for i, (gruppe, schluessel, text, von, bis, schritt) in enumerate(ZAHLEN):
            ttk.Label(rahmen, text=text).grid(row=i, column=0, sticky="w", pady=4)
            wert = self.cfg.get(gruppe, {}).get(schluessel, von)
            var = tk.StringVar(value=str(wert))
            ttk.Spinbox(rahmen, textvariable=var, from_=von, to=bis,
                        increment=schritt, width=10).grid(row=i, column=1,
                                                          sticky="w", padx=8)
            self.v_zahlen[(gruppe, schluessel)] = var
        maus = self.cfg.get("maus", {})
        self.v_tipp = tk.BooleanVar(value=maus.get("tipp_klick", True))
        ttk.Checkbutton(rahmen, text="Antippen des rechten Pads = Linksklick",
                        variable=self.v_tipp).grid(row=len(ZAHLEN), column=0,
                                                   columnspan=2, sticky="w",
                                                   pady=6)
        self.v_festhalten = tk.BooleanVar(value=maus.get("anker_festhalten", False))
        ttk.Checkbutton(rahmen,
                        text="Cursor beim Kameradrehen/-ziehen festnageln",
                        variable=self.v_festhalten).grid(row=len(ZAHLEN) + 1,
                                                         column=0, columnspan=2,
                                                         sticky="w")
        inv = self.cfg.get("stick_rechts_invert", {})
        self.v_inv_y = tk.BooleanVar(value=inv.get("hoch_runter", False))
        ttk.Checkbutton(rahmen, text="Rechten Stick hoch/runter invertieren",
                        variable=self.v_inv_y).grid(row=len(ZAHLEN) + 2,
                                                    column=0, columnspan=2,
                                                    sticky="w")
        self.v_inv_x = tk.BooleanVar(value=inv.get("links_rechts", False))
        ttk.Checkbutton(rahmen, text="Rechten Stick links/rechts invertieren",
                        variable=self.v_inv_x).grid(row=len(ZAHLEN) + 3,
                                                    column=0, columnspan=2,
                                                    sticky="w")

    def _tab_radial(self):
        rahmen = ttk.Frame(self.mappe, padding=8)
        self.mappe.add(rahmen, text="Radialmenü")
        ttk.Label(rahmen, text="Linkes Pad fest klicken → Menü."
                  " Einträge (Name · Belegung):").pack(anchor="w")
        self.radial_rahmen = ttk.Frame(rahmen)
        self.radial_rahmen.pack(fill="x", pady=4)
        self.v_radial = []
        for e in self.cfg.get("radial", []):
            self._radial_zeile(e.get("name", ""), e.get("taste", ""))
        ttk.Button(rahmen, text="+ Eintrag",
                   command=lambda: self._radial_zeile("", "")).pack(anchor="w")

    def _radial_zeile(self, name, taste):
        zeile = ttk.Frame(self.radial_rahmen)
        zeile.pack(fill="x", pady=1)
        vn, vt = tk.StringVar(value=name), tk.StringVar(value=taste)
        ttk.Entry(zeile, textvariable=vn, width=20).pack(side="left")
        knopf = ttk.Button(zeile, text=taste or "—", width=16)

        def fertig(neu):
            if neu is None:
                return
            vt.set(neu)
            knopf.config(text=neu or "—")

        knopf.config(command=lambda: Aufnahme(
            self.w, vn.get() or "Radial-Eintrag", fertig))
        knopf.pack(side="left", padx=4)
        eintrag = (vn, vt, zeile)
        ttk.Button(zeile, text="−", width=3,
                   command=lambda: (zeile.destroy(),
                                    self.v_radial.remove(eintrag))
                   ).pack(side="left")
        self.v_radial.append(eintrag)

    # — Speichern —
    def einsammeln(self):
        fehler = []

        def pruefen(wo, text):
            text = text.strip()
            if not text:
                return None
            try:
                ei.kombi_parsen(text)
            except ValueError as e:
                fehler.append(f"{wo}: {e}")
            return text

        cfg = self.cfg
        cfg.setdefault("tasten", {})
        for name, var in self.v_tasten.items():
            cfg["tasten"][name] = pruefen(name, var.get())
        cfg["trigger"] = {"links": pruefen("LT", self.v_lt.get()),
                          "rechts": pruefen("RT", self.v_rt.get())}
        for (schluessel, richtung), var in self.v_sticks.items():
            cfg.setdefault(schluessel, {})[richtung] = pruefen(
                f"{schluessel} {richtung}", var.get())
        for (gruppe, schluessel), var in self.v_zahlen.items():
            try:
                cfg.setdefault(gruppe, {})[schluessel] = float(
                    var.get().replace(",", "."))
            except ValueError:
                fehler.append(f"{schluessel}: keine Zahl: {var.get()!r}")
        cfg["maus"]["tipp_klick"] = self.v_tipp.get()
        cfg["maus"]["anker_festhalten"] = self.v_festhalten.get()
        cfg["stick_rechts_invert"] = {"hoch_runter": self.v_inv_y.get(),
                                      "links_rechts": self.v_inv_x.get()}
        cfg["radial"] = [{"name": vn.get().strip(), "taste": pruefen(
            f"Radial {vn.get()}", vt.get()) or ""}
            for vn, vt, _ in self.v_radial if vn.get().strip()]
        return fehler

    def speichern(self):
        fehler = self.einsammeln()
        if fehler:
            messagebox.showerror("Belegung prüfen", "\n".join(fehler))
            return
        seed_pad.config_pfad().write_text(
            json.dumps(self.cfg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        lief = self.thread is not None and self.thread.is_alive()
        if lief:
            self.stoppen()
            self.starten()
            self.melden("Gespeichert, Steuerung neu gestartet.")
        else:
            self.melden("Gespeichert.")

    # — Update —
    def _update_pruefen(self):
        try:
            self.update_info = pad_update.pruefen(VERSION)
        except Exception:
            return
        if self.update_info:
            self.melden(f"Update {self.update_info[0]} verfügbar.")

    def _update_starten(self):
        tag, url = self.update_info
        self.update_knopf.config(state="disabled")
        self.stoppen()
        self.melden(f"Lade {tag} …")

        def laden():
            try:
                if pad_update.installieren(url, self.melden):
                    self.meldungen.put("@@ende")
            except Exception as e:
                self.meldungen.put(f"Update fehlgeschlagen: {e}")

        threading.Thread(target=laden, daemon=True).start()

    # — Engine —
    def melden(self, text):
        self.meldungen.put(text)

    def starten(self):
        self.stop = threading.Event()
        self.thread = threading.Thread(target=seed_pad.lauf,
                                       args=(self.stop, self.melden),
                                       daemon=True)
        self.thread.start()
        self.start_knopf.config(text="■ Stopp")

    def stoppen(self):
        if self.stop:
            self.stop.set()
        if self.thread:
            self.thread.join(3)
        self.thread = None
        self.start_knopf.config(text="▶ Start")

    def start_stopp(self):
        if self.thread is not None and self.thread.is_alive():
            self.stoppen()
        else:
            self.starten()

    def _takt(self):
        try:
            while True:
                text = self.meldungen.get_nowait()
                if text == "@@ende":
                    self.melden("Update wird eingespielt, App startet neu …")
                    self.w.after(400, self.schliessen)
                    continue
                self.status.set(text)
                self.protokoll.config(state="normal")
                self.protokoll.insert("end", text + "\n")
                self.protokoll.see("end")
                self.protokoll.config(state="disabled")
        except queue.Empty:
            pass
        if self.update_info and self.update_knopf is None:
            self.update_knopf = ttk.Button(
                self.kopf, text=f"⟳ Update {self.update_info[0]}",
                command=self._update_starten)
            self.update_knopf.pack(side="right")
        # Steam+B beendet nur die Engine → Knopf nachziehen
        if self.thread is not None and not self.thread.is_alive():
            self.thread = None
            self.start_knopf.config(text="▶ Start")
        self.w.after(150, self._takt)

    def schliessen(self):
        self.stoppen()
        self.w.destroy()


if __name__ == "__main__":
    App().w.mainloop()
