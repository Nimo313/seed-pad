# SEED mit dem Steam Controller

Steuert SEED mit dem Steam Controller (2026er, auch über den Funk-Puck) —
ganz ohne Steam, ohne Installation.

## Start

1. Controller einschalten (Puck angesteckt), **Steam beenden** — sonst steuert
   Steam doppelt.
2. **`SeedPad.exe`** starten. Windows warnt beim ersten Mal („unbekannter
   Herausgeber"): *Weitere Informationen → Trotzdem ausführen*.
3. Im Fenster **▶ Start** drücken. Fertig.

Im Fenster lässt sich alles einstellen (Reiter *Tasten*, *Maus / Zoom*,
*Radialmenü*) — **Speichern & übernehmen** schreibt die Belegung und startet
die Steuerung gleich neu. Gespeichert wird in `pad_belegung.json` neben der
EXE; die Datei kann man auch direkt bearbeiten.

**Steam + X** = Pause (zum Tippen) · **Steam + B** = Steuerung stoppen.

Gibt es eine neue Version, zeigt die App oben rechts einen **⟳ Update**-Knopf —
ein Klick, sie tauscht sich selbst aus und startet neu.

## Belegung

| Eingabe | Wirkung |
|---|---|
| Rechtes Pad | Maus (Trackball mit Schwung) |
| Rechtes Pad antippen, fest klicken oder RT | Linksklick |
| LT | Rechtsklick halten (+ rechtes Pad = Kamera drehen) |
| Linkes Pad streichen | Zoom (Mausrad) |
| Linkes Pad **fest klicken** | Radialmenü: halten, Richtung wählen, loslassen |
| Linker Stick | Kamera bewegen (W A S D) |
| Rechter Stick | Kamera drehen Q/E, neigen R/F |
| A | Leertaste (auf Char fixieren) |
| L4 (Griff hinten links oben) | Tab (Char wechseln) |
| B / Menu | Esc |
| X / Y | Snap Position / Rotation (Baumodus) |
| LB | Shift halten (+ linkes Pad = Etage wechseln) |
| RB | Strg halten (Blöcke löschen, Objekt drehen) |
| Steuerkreuz | Pfeiltasten |
| View | Fotomodus (Strg+P) |
| **QAM (…-Taste)** | **Overlay-Tastatur**: linkes Pad zielt auf die linke Hälfte, rechtes auf die rechte; LT/RT oder Pad-Klick tippt. A Leer, B Löschen (halten = schnell), Y Enter, RB groß, QAM wieder zu |
| R5 halten | **Ebene 2**: zweite Belegung für alle Tasten/Sticks (Reiter Tasten → Ansicht „Ebene 2“; leere Felder = wie Ebene 1) |

**Profile:** oben rechts speichern und wechseln (z. B. „Bauen“ und „Alltag“).
**Test-Reiter:** zeigt live, was der Controller meldet — gut zum Prüfen.

## Alles anpassen

Am einfachsten im Fenster. Im Aufnahme-Dialog gibt es auch
**„Bildschirm-Klick…“**: Die Taste klickt dann eine feste Stelle an (z. B. das
Unternehmens- oder Society-Symbol) — Cursor springt hin, klickt und kommt
zurück. In `pad_belegung.json` steht dasselbe (Klick-Stellen als `klick:x,y`):

- **`tasten`** — jede Controller-Taste frei belegen (`null` = nichts).
  Es gehen Namen wie `a`–`z`, `0`–`9`, `f1`–`f12`, `esc`, `tab`, `enter`,
  `leer`, `shift`, `strg`, `alt`, `entf`, `einfg`, `pos1`, `ende`, `bildauf`,
  `bildab`, `links`/`rechts`/`oben`/`unten`, `plus`, `minus`, `numplus`,
  `numminus`, `maus_links`, `maus_rechts`, `maus_mitte`, `rad_hoch`,
  `rad_runter` — und Kombis mit `+`, z. B. `strg+p`.
- **`radial`** — die Einträge des Radialmenüs (`name` + `taste`), beliebig viele.
- **`stick_links` / `stick_rechts`** — die vier Richtungen je Stick.
- **`trigger`** — was LT/RT tun.
- **`maus`** — `empfindlichkeit` (Cursortempo), `reibung` + `schwung_ab`
  (Nachlauf-Schwung; aus = `schwung_ab` auf 99999), `tipp_klick` (Antippen =
  Klick), `klick_ruhe` (Cursor steht so viele Sekunden beim Klick still).
- **`zoom`** — `weg_je_raste`: wie weit streichen für eine Rad-Raste.

## Wenn etwas hakt

- Cursor bewegt sich von allein / doppelt → Steam läuft noch: beenden.
- „Suche Controller…" endlos → Puck angesteckt? Controller an (Steam-Taste)?
- Radialmenü unsichtbar → Spiel auf **Borderless** stellen (SEED-Settings →
  Graphics → Screen Mode).
- Virenscanner meckert über die EXE → das ist der übliche Fehlalarm bei
  selbstgebauten PyInstaller-Programmen; die Quelltexte liegen bei Nimo.
