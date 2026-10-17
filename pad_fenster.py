# Katalog der SEED-Fenster und -Knöpfe mit festen Bildschirmpositionen
# (1920×1080 Borderless; vermessen in spielwissen/01-oberflaeche.md und
# 04-rechte-leiste.md). Belegung als "fenster:<kennung>" — der Cursor springt
# hin, klickt und kehrt zurück.

# (Anzeigename, x, y)
FENSTER = [
    # Linke Leiste — Hauptmenüs
    ("Wallet", 32, 116),
    ("Jobs", 32, 158),
    ("Scheduler", 32, 200),
    ("Social", 32, 242),
    ("Groups", 32, 282),
    ("Photos", 32, 324),
    ("Spark", 32, 367),
    ("Seedling Chat", 32, 422),
    # Rechte Leiste — Fenster
    ("Properties", 1888, 115),
    ("Business", 1888, 159),
    ("Societies Leiste", 1888, 204),
    ("Marketplace", 1888, 248),
    ("Chats", 1888, 303),
    ("Real Estate", 1888, 347),      # Vollbildmodus, Exit unten rechts
    ("Land Planner", 1888, 391),     # Vollbildmodus, Exit unten rechts
    ("Seed Store", 1888, 435),
    # Oben rechts
    ("PAM", 1637, 26),
    ("Objectives", 1687, 26),
    ("Societies", 1740, 26),
    ("Checkliste", 1782, 26),
    ("Catalog", 1824, 26),
    ("Benachrichtigungen", 1878, 26),
    # Rechte Leiste — Ansicht und Kamera
    ("Compass", 1888, 759),
    ("Visibility", 1888, 803),
    ("World View", 1888, 851),
    ("Map View", 1888, 896),
    ("Society View", 1888, 940),
    ("Focus Mode", 1888, 984),
]


def kennung(name):
    return name.lower().replace(" ", "_")


POSITIONEN = {kennung(n): (x, y) for n, x, y in FENSTER}
NAMEN = {kennung(n): n for n, _, _ in FENSTER}
