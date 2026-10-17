# SEED-Pad: kleine Anwendung mit Start/Stopp und Setup-Oberfläche.
# Belegen durch Drücken der echten Taste (auch Kombis wie Shift+Y),
# zwei Belegungsebenen, Profile, Live-Testansicht, Auto-Update.
import json
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

HIER = Path(__file__).parent
sys.path.insert(0, str(HIER))

import pad_eingabe as ei
import pad_update
import seed_pad

VERSION = "1.2.0"

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
TRIGGER = [("links", "LT (Trigger links)"), ("rechts", "RT (Trigger rechts)")]
ZAHLEN = [  # (gruppe, schluessel, beschriftung, von, bis, schrittweite)
    ("maus", "empfindlichkeit", "Cursortempo", 0.1, 2.0, 0.05),
    ("maus", "reibung", "Schwung-Reibung (höher = kürzer)", 1, 20, 0.5),
    ("maus", "schwung_ab", "Schwung erst ab (px/s, 99999 = aus)", 0, 99999, 50),
    ("maus", "klick_ruhe", "Cursor-Stillstand beim Klick (s)", 0.0, 0.5, 0.05),
    ("zoom", "weg_je_raste", "Streichweg je Zoom-Raste", 1000, 20000, 500),
]
KEINE = "(keine)"

# Tk-Tastennamen → Namen aus pad_eingabe
TK_NAMEN = {
    "Escape": "esc", "Tab": "tab", "Return": "enter", "space": "leer",
    "BackSpace": "ruecktaste",
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
        w.geometry("780x680")
        w.minsize(680, 560)

        kopf = self.kopf = ttk.Frame(w, padding=8)
        kopf.pack(fill="x")
        self.start_knopf = ttk.Button(kopf, text="▶ Start", command=self.start_stopp)
        self.start_knopf.pack(side="left")
        self.status = tk.StringVar(value="Bereit.")
        ttk.Label(kopf, textvariable=self.status).pack(side="left", padx=10)
        ttk.Button(kopf, text="Profil speichern…",
                   command=self._profil_speichern).pack(side="right", padx=4)
        self.v_profil = tk.StringVar(value=KEINE)
        self.profil_feld = ttk.Combobox(kopf, textvariable=self.v_profil,
                                        state="readonly", width=16)
        self.profil_feld.pack(side="right")
        self.profil_feld.bind("<<ComboboxSelected>>", self._profil_laden)
        ttk.Label(kopf, text="Profil:").pack(side="right", padx=4)
        self._profile_auflisten()

        fuss = self.fuss = ttk.Frame(w, padding=8)
        self.protokoll = tk.Text(w, height=5, state="disabled",
                                 font=("Consolas", 9))
        self._oberflaeche_bauen()
        fuss.pack(fill="x")
        ttk.Button(fuss, text="Speichern & übernehmen",
                   command=self.speichern).pack(side="left")
        ttk.Label(fuss, text="Steam + X = Pause · Steam + B = Stopp"
                  ).pack(side="right")
        self.protokoll.pack(fill="x", padx=8, pady=(0, 8))

        w.protocol("WM_DELETE_WINDOW", self.schliessen)
        w.after(150, self._takt)
        w.after(300, self._test_takt)
        threading.Thread(target=self._update_pruefen, daemon=True).start()

    # — Oberfläche (neu) aufbauen —
    def _oberflaeche_bauen(self):
        self._variablen_laden()
        self.mappe = ttk.Notebook(self.w)
        self.mappe.pack(fill="both", expand=True, padx=8, pady=4)
        self._tab_tasten()
        self._tab_maus()
        self._tab_radial()
        self._tab_test()

    def _oberflaeche_neu(self):
        self.mappe.destroy()
        self._oberflaeche_bauen()
        self.mappe.pack_configure(before=self.fuss)

    def _variablen_laden(self):
        cfg = self.cfg
        eb2 = cfg.get("ebene2", {})
        quellen = {
            "1": (cfg.get("tasten", {}), cfg.get("trigger", {}),
                  {s: cfg.get(s, {}) for s, _ in STICKS}),
            "2": (eb2.get("tasten", {}), eb2.get("trigger", {}),
                  {s: eb2.get(s, {}) for s, _ in STICKS}),
        }
        self.v_tasten, self.v_trigger, self.v_sticks = {}, {}, {}
        for e, (tasten, trigger, sticks) in quellen.items():
            self.v_tasten[e] = {n: tk.StringVar(value=tasten.get(n) or "")
                                for n, _ in KNOEPFE}
            self.v_trigger[e] = {s: tk.StringVar(value=trigger.get(s) or "")
                                 for s, _ in TRIGGER}
            self.v_sticks[e] = {(s, r): tk.StringVar(
                value=sticks[s].get(r) or "")
                for s, _ in STICKS for r in RICHTUNGEN}
        self.v_ansicht = tk.StringVar(value="1")
        self.v_ebene_taste = tk.StringVar(
            value=cfg.get("ebene", {}).get("taste") or KEINE)
        sr = cfg.get("schreibrad", {})
        self.v_sr_an = tk.BooleanVar(value=sr.get("an", True))
        self.v_sr_taste = tk.StringVar(value=sr.get("taste", "QAM"))
        maus = cfg.get("maus", {})
        self.v_zahlen = {(g, s): tk.StringVar(
            value=str(cfg.get(g, {}).get(s, von)))
            for g, s, _, von, _, _ in ZAHLEN}
        self.v_tipp = tk.BooleanVar(value=maus.get("tipp_klick", True))
        self.v_festhalten = tk.BooleanVar(value=maus.get("anker_festhalten", False))
        inv = cfg.get("stick_rechts_invert", {})
        self.v_inv_y = tk.BooleanVar(value=inv.get("hoch_runter", False))
        self.v_inv_x = tk.BooleanVar(value=inv.get("links_rechts", False))

    # — Belegungs-Knöpfe —
    def _belegung(self, elter, zeile, spalte, text, var):
        ttk.Label(elter, text=text).grid(row=zeile, column=spalte * 2,
                                         sticky="w", padx=(8, 4), pady=2)
        knopf = ttk.Button(elter, text=var.get() or "—", width=16)

        def fertig(neu, var=var, knopf=knopf):
            if neu is None:
                return
            var.set(neu)
            knopf.config(text=neu or "—")

        knopf.config(command=lambda: Aufnahme(self.w, text, fertig))
        knopf.grid(row=zeile, column=spalte * 2 + 1, sticky="w", pady=2)

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
        oben = ttk.Frame(rahmen, padding=(8, 6))
        oben.pack(fill="x")
        ttk.Label(oben, text="Ansicht:").pack(side="left")
        for e, text in (("1", "Ebene 1"), ("2", "Ebene 2")):
            ttk.Radiobutton(oben, text=text, value=e, variable=self.v_ansicht,
                            command=self._ebene_zeigen).pack(side="left", padx=4)
        ttk.Label(oben, text="   Ebenen-Taste (halten):").pack(side="left")
        namen = [KEINE] + [n for n, _ in KNOEPFE]
        ttk.Combobox(oben, textvariable=self.v_ebene_taste, values=namen,
                     state="readonly", width=12).pack(side="left", padx=4)
        _, innen = self._rollbar(rahmen)
        self.tasten_bereich = innen
        self._ebene_zeigen()

    def _ebene_zeigen(self):
        for kind in self.tasten_bereich.winfo_children():
            kind.destroy()
        innen = self.tasten_bereich
        e = self.v_ansicht.get()
        for i, (name, text) in enumerate(KNOEPFE):
            self._belegung(innen, i % 10, i // 10, text, self.v_tasten[e][name])
        zeile = 10
        ttk.Separator(innen, orient="horizontal").grid(
            row=zeile, column=0, columnspan=4, sticky="ew", pady=6)
        for s, (schluessel, text) in enumerate(TRIGGER):
            self._belegung(innen, zeile + 1, s, text,
                           self.v_trigger[e][schluessel])
        for s, (schluessel, text) in enumerate(STICKS):
            for r, richtung in enumerate(RICHTUNGEN):
                self._belegung(innen, zeile + 2 + r, s,
                               f"{text} {richtung}",
                               self.v_sticks[e][(schluessel, richtung)])
        hinweis = ("Knopf anklicken, dann die gewünschte Taste, Kombi (z. B."
                   " Shift+Y)\noder Maustaste drücken. „Leeren“ nimmt die"
                   " Belegung weg.")
        if e == "2":
            hinweis = ("Ebene 2 gilt, solange die Ebenen-Taste gehalten wird.\n"
                       "Leere Felder übernehmen die Belegung von Ebene 1.")
        ttk.Label(innen, foreground="#666", text=hinweis).grid(
            row=zeile + 7, column=0, columnspan=4, sticky="w", padx=8, pady=8)

    def _tab_maus(self):
        rahmen = ttk.Frame(self.mappe, padding=8)
        self.mappe.add(rahmen, text="Maus / Zoom")
        for i, (gruppe, schluessel, text, von, bis, schritt) in enumerate(ZAHLEN):
            ttk.Label(rahmen, text=text).grid(row=i, column=0, sticky="w", pady=4)
            ttk.Spinbox(rahmen, textvariable=self.v_zahlen[(gruppe, schluessel)],
                        from_=von, to=bis, increment=schritt,
                        width=10).grid(row=i, column=1, sticky="w", padx=8)
        z = len(ZAHLEN)
        for i, (text, var) in enumerate((
                ("Antippen des rechten Pads = Linksklick", self.v_tipp),
                ("Cursor beim Kameradrehen/-ziehen festnageln", self.v_festhalten),
                ("Rechten Stick hoch/runter invertieren", self.v_inv_y),
                ("Rechten Stick links/rechts invertieren", self.v_inv_x),
                ("Schreibrad an (Tippen mit den Pads)", self.v_sr_an))):
            ttk.Checkbutton(rahmen, text=text, variable=var).grid(
                row=z + i, column=0, columnspan=2, sticky="w",
                pady=(6 if i == 0 else 0))
        ttk.Label(rahmen, text="Schreibrad-Taste:").grid(
            row=z + 5, column=0, sticky="w", pady=4)
        ttk.Combobox(rahmen, textvariable=self.v_sr_taste,
                     values=[n for n, _ in KNOEPFE], state="readonly",
                     width=12).grid(row=z + 5, column=1, sticky="w", padx=8)

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

    # — Testansicht —
    def _tab_test(self):
        rahmen = ttk.Frame(self.mappe, padding=8)
        self.mappe.add(rahmen, text="Test")
        self.test_lw = tk.Canvas(rahmen, width=700, height=300,
                                 bg="#10151d", highlightthickness=0)
        self.test_lw.pack(fill="both", expand=True)

    def _test_takt(self):
        try:
            self._test_zeichnen()
        except tk.TclError:
            pass    # Reiter wird gerade neu aufgebaut
        self.w.after(100, self._test_takt)

    def _test_zeichnen(self):
        lw = self.test_lw
        lw.delete("alle")
        z = seed_pad.LETZTER
        if z is None:
            lw.create_text(350, 150, tags="alle", fill="#8899aa",
                           text="▶ Start drücken — dann zeigen sich hier\n"
                                "Pads, Sticks, Trigger und Tasten live.",
                           justify="center", font=("Segoe UI", 11))
        else:
            def punkt(mx, my, groesse, x, y, beruehrt, farbe="#5fb4ff"):
                if beruehrt:
                    px = mx + x / 32767 * groesse / 2
                    py = my - y / 32767 * groesse / 2
                    lw.create_oval(px - 6, py - 6, px + 6, py + 6,
                                   tags="alle", fill=farbe, outline="")

            # Pads (Quadrate) und Sticks (Kreise)
            for mx, feld, klick in ((110, ("lpx", "lpy", "LPad_Touch"),
                                     "LPad_Klick"),
                                    (590, ("rpx", "rpy", "RPad_Touch"),
                                     "RPad_Klick")):
                rand = "#e3b341" if z.gedrueckt(klick) else "#45556b"
                lw.create_rectangle(mx - 70, 20, mx + 70, 160, tags="alle",
                                    outline=rand, width=3)
                punkt(mx, 90, 140, getattr(z, feld[0]), getattr(z, feld[1]),
                      z.gedrueckt(feld[2]))
            for mx, (sx, sy) in ((260, ("lsx", "lsy")), (440, ("rsx", "rsy"))):
                lw.create_oval(mx - 50, 40, mx + 50, 140, tags="alle",
                               outline="#45556b", width=3)
                punkt(mx, 90, 100, getattr(z, sx), getattr(z, sy), True,
                      "#7ee787")
            # Trigger-Balken
            for mx, wert, name in ((330, z.lt, "LT"), (370, z.rt, "RT")):
                hoch = int(wert / 32767 * 100)
                lw.create_rectangle(mx, 160 - 100, mx + 20, 160, tags="alle",
                                    outline="#45556b")
                lw.create_rectangle(mx, 160 - hoch, mx + 20, 160, tags="alle",
                                    fill="#e3b341", outline="")
                lw.create_text(mx + 10, 172, tags="alle", text=name,
                               fill="#8899aa", font=("Segoe UI", 8))
            gedrueckt = [n for n, _ in KNOEPFE if z.gedrueckt(n)]
            if z.gedrueckt("Steam"):
                gedrueckt.insert(0, "Steam")
            lw.create_text(350, 220, tags="alle", fill="#dde6f2",
                           font=("Segoe UI", 11),
                           text="Gedrückt: " + (", ".join(gedrueckt) or "—"))
            lw.create_text(350, 250, tags="alle", fill="#8899aa",
                           font=("Segoe UI", 9),
                           text=f"Links-Pad {z.lpx:6d}/{z.lpy:6d}   "
                                f"Rechts-Pad {z.rpx:6d}/{z.rpy:6d}   "
                                f"LT {z.lt:5d}  RT {z.rt:5d}")

    # — Profile —
    def _profil_ordner(self):
        p = seed_pad.basis() / "profile"
        p.mkdir(exist_ok=True)
        return p

    def _profile_auflisten(self):
        namen = sorted(d.stem for d in self._profil_ordner().glob("*.json"))
        self.profil_feld["values"] = [KEINE] + namen

    def _profil_speichern(self):
        fehler = self.einsammeln()
        if fehler:
            messagebox.showerror("Belegung prüfen", "\n".join(fehler))
            return
        name = simpledialog.askstring("Profil speichern",
                                      "Name des Profils:", parent=self.w)
        if not name:
            return
        name = "".join(c for c in name if c.isalnum() or c in " -_").strip()
        (self._profil_ordner() / f"{name}.json").write_text(
            json.dumps(self.cfg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        self._profile_auflisten()
        self.v_profil.set(name)
        self.melden(f"Profil „{name}“ gespeichert.")

    def _profil_laden(self, _=None):
        name = self.v_profil.get()
        if name == KEINE:
            return
        pfad = self._profil_ordner() / f"{name}.json"
        try:
            self.cfg = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            messagebox.showerror("Profil", f"{pfad.name}: {e}")
            return
        seed_pad.config_pfad().write_text(
            json.dumps(self.cfg, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        self._oberflaeche_neu()
        if self.thread is not None and self.thread.is_alive():
            self.stoppen()
            self.starten()
        self.melden(f"Profil „{name}“ geladen.")

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
        cfg["tasten"] = {n: pruefen(n, v.get())
                         for n, v in self.v_tasten["1"].items()}
        cfg["trigger"] = {s: pruefen(f"Trigger {s}", v.get())
                          for s, v in self.v_trigger["1"].items()}
        for schluessel, _ in STICKS:
            cfg[schluessel] = {r: pruefen(f"{schluessel} {r}",
                                          self.v_sticks["1"][(schluessel, r)].get())
                               for r in RICHTUNGEN}
        cfg["ebene2"] = {
            "tasten": {n: pruefen(f"Ebene 2 {n}", v.get())
                       for n, v in self.v_tasten["2"].items() if v.get().strip()},
            "trigger": {s: pruefen(f"Ebene 2 Trigger {s}", v.get())
                        for s, v in self.v_trigger["2"].items()
                        if v.get().strip()},
        }
        for schluessel, _ in STICKS:
            cfg["ebene2"][schluessel] = {
                r: pruefen(f"Ebene 2 {schluessel} {r}",
                           self.v_sticks["2"][(schluessel, r)].get())
                for r in RICHTUNGEN
                if self.v_sticks["2"][(schluessel, r)].get().strip()}
        taste = self.v_ebene_taste.get()
        cfg["ebene"] = {"taste": None if taste == KEINE else taste}
        cfg["schreibrad"] = {"an": self.v_sr_an.get(),
                             "taste": self.v_sr_taste.get()}
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
