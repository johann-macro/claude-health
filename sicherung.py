"""Monatliche Sicherung der Rohdaten.

Legt einmal je Kalendermonat ein ZIP mit dem gesamten health-Ordner an -
data.json, alle Tagesnotizen, alle Workouts. Zugangsdaten sind NICHT dabei;
ein Token gehoert nicht in eine Sicherung, die man weiterreicht.

Wozu, wo die Daten doch schon lokal liegen: gegen einen Sync, der kaputte
Werte ueber gute schreibt, gegen versehentliches Loeschen, gegen einen
halben Schreibvorgang. Die laufende Datei ist kein Archiv.

Aufruf:
    python sicherung.py            nur wenn dieser Monat noch fehlt
    python sicherung.py --jetzt    in jedem Fall
"""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime

from config import DATA_JSON, HEALTH_DIR, SICHERUNG_DIR

# So viele Monatsstaende bleiben liegen, aeltere werden entfernt
BEHALTEN = 24


def vorhandene() -> list:
    if not SICHERUNG_DIR.exists():
        return []
    return sorted(SICHERUNG_DIR.glob("claude-health-*.zip"))


def schon_diesen_monat() -> bool:
    marke = datetime.now().strftime("%Y-%m")
    return any(f.name.startswith(f"claude-health-{marke}") for f in vorhandene())


def sichern() -> dict:
    SICHERUNG_DIR.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime("%Y-%m-%d")
    ziel = SICHERUNG_DIR / f"claude-health-{stempel}.zip"

    dateien = [p for p in HEALTH_DIR.rglob("*") if p.is_file()]
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in dateien:
            z.write(p, p.relative_to(HEALTH_DIR.parent))

    # Alte Staende entfernen
    entfernt = 0
    alle = vorhandene()
    for alt in alle[:-BEHALTEN] if len(alle) > BEHALTEN else []:
        alt.unlink()
        entfernt += 1

    return {"datei": ziel, "dateien": len(dateien),
            "groesse_kb": round(ziel.stat().st_size / 1024), "entfernt": entfernt}


def pruefe(ziel) -> str:
    """Sicherung gegenlesen - eine ZIP, die sich nicht oeffnen laesst, ist keine."""
    try:
        with zipfile.ZipFile(ziel) as z:
            kaputt = z.testzip()
            if kaputt:
                return f"beschädigt bei {kaputt}"
            namen = z.namelist()
            treffer = [n for n in namen if n.endswith("data.json")]
            if not treffer:
                return "data.json fehlt im Archiv"
            json.loads(z.read(treffer[0]).decode("utf-8"))
        return "ok"
    except Exception as exc:                              # noqa: BLE001
        return f"nicht lesbar: {exc}"


def main() -> int:
    p = argparse.ArgumentParser(description="Monatliche Sicherung der Gesundheitsdaten")
    p.add_argument("--jetzt", action="store_true",
                   help="sichern, auch wenn dieser Monat schon einen Stand hat")
    args = p.parse_args()

    if not DATA_JSON.exists():
        print("Nichts zu sichern – es gibt noch keine Daten.")
        return 0

    if not args.jetzt and schon_diesen_monat():
        letzte = vorhandene()[-1].name
        print(f"Für diesen Monat liegt bereits eine Sicherung vor: {letzte}")
        return 0

    ergebnis = sichern()
    zustand = pruefe(ergebnis["datei"])

    print(f"Sicherung: {ergebnis['datei']}")
    print(f"  Dateien   : {ergebnis['dateien']}")
    print(f"  Größe     : {ergebnis['groesse_kb']} KB")
    print(f"  Gegenlesen: {zustand}")
    if ergebnis["entfernt"]:
        print(f"  Entfernt  : {ergebnis['entfernt']} alte Stände (es bleiben {BEHALTEN})")
    print(f"  Bestand   : {len(vorhandene())} Sicherungen")

    if zustand != "ok":
        print("\nACHTUNG: Die Sicherung ließ sich nicht gegenlesen.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
