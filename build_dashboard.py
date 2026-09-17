"""Baut aus Vorlage + Daten eine einzige, in sich geschlossene HTML-Datei.

Die Daten werden direkt in die Datei geschrieben. Das ist kein Schoenheits-
fehler, sondern noetig: eine lokal per Doppelklick geoeffnete HTML-Datei darf
aus Sicherheitsgruenden keine JSON-Datei nachladen - der Versuch scheitert
still und die Seite bliebe leer.

Aufruf:  python build_dashboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config import DASHBOARD_FILE, DATA_JSON, TEMPLATE_FILE

PLATZHALTER = "__CLAUDE_HEALTH_DATA__"


def js_pruefen(seite: str) -> str | None:
    """Prueft den Script-Block mit node, falls vorhanden.

    Grund: ein Syntaxfehler laesst die Seite komplett leer - sie laedt, aber
    kein einziger Knopf reagiert. Das faellt bei einem fluechtigen Blick nicht
    auf, kostet aber eine ganze Fehlersuche. Der Bau bricht deshalb lieber ab,
    als eine kaputte Datei zu schreiben.

    Rueckgabe: Fehlertext, oder None wenn alles in Ordnung ist bzw. node fehlt.
    """
    import re
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("node"):
        return None                      # ohne node wird eben nicht geprueft

    treffer = re.search(r"<script>(.*)</script>", seite, re.S)
    if not treffer:
        return None

    with tempfile.TemporaryDirectory() as ordner:
        datei = Path(ordner) / "block.js"
        datei.write_text(treffer.group(1), encoding="utf-8")
        lauf = subprocess.run(
            ["node", "--check", str(datei)], capture_output=True, text=True
        )
        if lauf.returncode == 0:
            return None
        # Nur die ersten Zeilen - der Rest ist node-Innenleben
        zeilen = [z for z in lauf.stderr.splitlines() if "node:internal" not in z]
        return "\n".join(zeilen[:8]).strip()


def bauen() -> int:
    if not TEMPLATE_FILE.exists():
        sys.exit(f"Vorlage fehlt: {TEMPLATE_FILE}")
    if not DATA_JSON.exists():
        sys.exit(
            f"Keine Daten: {DATA_JSON}\n"
            "Erst Daten erzeugen:  python demo_data.py   (oder spaeter: python sync.py)"
        )

    vorlage = TEMPLATE_FILE.read_text(encoding="utf-8")
    if PLATZHALTER not in vorlage:
        sys.exit(f"Platzhalter {PLATZHALTER} nicht in der Vorlage gefunden.")

    daten = json.loads(DATA_JSON.read_text(encoding="utf-8"))

    # </script> im JSON wuerde den Script-Block der Seite vorzeitig beenden
    roh = json.dumps(daten, ensure_ascii=False, separators=(",", ":"))
    roh = roh.replace("</", "<\\/")

    seite = vorlage.replace(PLATZHALTER, roh)

    fehler = js_pruefen(seite)
    if fehler:
        sys.exit(
            f"ABBRUCH: Das JavaScript der Seite ist fehlerhaft.\n\n{fehler}\n\n"
            "Es wurde nichts geschrieben - die vorherige, funktionierende Fassung\n"
            "bleibt unangetastet."
        )

    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_FILE.write_text(seite, encoding="utf-8")

    groesse = DASHBOARD_FILE.stat().st_size / 1024
    tage = daten.get("days", [])
    print(f"Dashboard gebaut : {DASHBOARD_FILE}")
    print(f"  Groesse        : {groesse:.0f} KB (alles eingebettet, offline lauffaehig)")
    print(f"  Zeitraum       : {tage[0]['date']} bis {tage[-1]['date']}" if tage else "  keine Tage")
    print(f"  Demo-Daten     : {'ja' if daten.get('is_demo') else 'nein'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(bauen())
