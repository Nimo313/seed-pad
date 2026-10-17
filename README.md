# SEED-Pad

SEED mit dem Steam Controller (2026, „Triton", auch über den Funk-Puck)
spielen — ohne Steam. Trackball-Maus auf dem rechten Pad, Zoom auf dem linken,
Radialmenü, frei belegbare Tasten, kleine Setup-Oberfläche mit Auto-Update.

## Benutzen

Fertige EXE: [Releases](https://github.com/Nimo313/seed-pad/releases) →
`SeedPad.exe` herunterladen, starten, **▶ Start**. Details in
[ANLEITUNG.md](paket/ANLEITUNG.md). Updates meldet die App selbst.

Aus dem Quelltext: `pip install hidapi`, dann `python pad_app.py`
(oder ohne Fenster `python seed_pad.py`).

## Technik

Liest den Controller direkt über HID — Protokoll nach
[SDL3](https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_steam_triton.c)
und [sc2-research](https://github.com/CouchTurtle/sc2-research). Eingaben gehen
per SendInput (Scancodes) an Windows; die eingebaute Maus-Emulation („Lizard
Mode") wird per Feature-Report stummgehalten.

| Datei | Zweck |
|---|---|
| `pad_app.py` | Fenster: Start/Stopp, Setup, Updater |
| `seed_pad.py` | Engine: Mapping-Schleife |
| `pad_hid.py` | Controller lesen (Report 0x42), Haptik |
| `pad_eingabe.py` | Maus/Tastatur erzeugen |
| `pad_radial.py` | Radialmenü-Overlay |
| `pad_update.py` | Auto-Update über die Releases hier |

## Release bauen

```
python -m PyInstaller --onefile --noconsole --name SeedPad --add-data "<pfad>\pad_belegung.json;." pad_app.py
gh release create vX.Y.Z dist/SeedPad.exe --title vX.Y.Z
```

Versionsnummer vorher in `pad_app.py` (`VERSION`) anheben — der Updater
vergleicht sie mit dem neuesten Release-Tag.
