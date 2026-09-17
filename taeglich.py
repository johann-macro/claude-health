"""Einstiegspunkt fuer den automatischen Lauf.

Genau ein Programm fuer die Aufgabenplanung. Es entscheidet selbst, woher die
Daten kommen:

    Anmeldung vorhanden  -> sync.py holt echte Fitbit-Daten
    noch keine Anmeldung -> demo_data.py haelt das Dashboard am Leben

Damit funktioniert der geplante Lauf schon jetzt und schaltet von allein um,
sobald die Uhr da und die Anmeldung erledigt ist - ohne dass an der
Aufgabenplanung noch etwas geaendert werden muss.

Die Aufgabenplanung ruft direkt dieses Programm mit dem Python der virtuellen
Umgebung auf, nicht ueber eine Batchdatei. Zwischengeschaltete Skripte in
synchronisierten Ordnern sind eine haeufige Fehlerquelle.

Aufruf:  python taeglich.py [--tage N]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback
from datetime import datetime

from config import CLIENT_FILE, LOG_DIR, PROJECT_DIR, TOKEN_FILE

LOGDATEI = LOG_DIR / "taeglich.log"
PYTHON = sys.executable


def protokoll(text: str) -> None:
    zeit = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    zeile = f"{zeit}  {text}"
    print(zeile)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOGDATEI.open("a", encoding="utf-8") as f:
        f.write(zeile + "\n")


def starte(argumente: list[str]) -> int:
    """Ein Teilschritt. Ausgabe wandert ins Protokoll."""
    # Ohne PYTHONIOENCODING schreibt das Kindprogramm in der Windows-Codepage,
    # waehrend wir hier UTF-8 erwarten - Umlaute kaemen als Fragezeichen an.
    umgebung = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    ergebnis = subprocess.run(
        [PYTHON, *argumente],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=umgebung,
    )
    for zeile in (ergebnis.stdout or "").splitlines():
        if zeile.strip():
            protokoll(f"    {zeile}")
    for zeile in (ergebnis.stderr or "").splitlines():
        if zeile.strip():
            protokoll(f"    ! {zeile}")
    return ergebnis.returncode


def main() -> int:
    p = argparse.ArgumentParser(description="Täglicher Lauf: Daten holen und Dashboard bauen")
    p.add_argument("--tage", type=int, default=14,
                   help="Zeitraum in Tagen (Standard 14, holt Verpasstes nach)")
    args = p.parse_args()

    protokoll("=" * 58)
    angemeldet = TOKEN_FILE.exists() and CLIENT_FILE.exists()

    try:
        if angemeldet:
            protokoll("Lauf startet – echte Daten über die Google Health API")
            code = starte(["sync.py", "--tage", str(args.tage)])
            if code != 0:
                protokoll(f"FEHLER: sync.py endete mit Code {code}")
                return code
        else:
            protokoll("Lauf startet – noch keine Anmeldung, benutze Demo-Daten")
            code = starte(["demo_data.py", "90"])
            if code != 0:
                protokoll(f"FEHLER: demo_data.py endete mit Code {code}")
                return code
            code = starte(["notes.py"])
            if code != 0:
                protokoll(f"FEHLER: notes.py endete mit Code {code}")
                return code
            code = starte(["build_dashboard.py"])
            if code != 0:
                protokoll(f"FEHLER: build_dashboard.py endete mit Code {code}")
                return code

        # Sicherung: das Script prüft selbst, ob dieser Monat schon einen
        # Stand hat. Scheitert sie, ist das kein Grund, den Lauf als
        # fehlgeschlagen zu melden - die Daten sind ja geschrieben.
        code = starte(["sicherung.py"])
        if code != 0:
            protokoll(f"WARNUNG: Sicherung endete mit Code {code}")

        protokoll("Lauf erfolgreich beendet")
        return 0

    except Exception:                                    # noqa: BLE001
        # Ein geplanter Lauf darf nie stumm scheitern - alles ins Protokoll
        protokoll("ABBRUCH mit unerwartetem Fehler:")
        for zeile in traceback.format_exc().splitlines():
            protokoll(f"    {zeile}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
