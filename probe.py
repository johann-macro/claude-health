"""Ruft jeden Datentyp einmal ab und schreibt die Rohantwort weg.

Wozu: Adressen, Methoden und Grenzen der Google Health API sind dokumentiert
(developers.google.com/health/data-types und /reference/rest). Die genauen
Feldnamen INNERHALB der Antworten und die exakte Schreibweise der Filter
sind es nur lückenhaft. Dieses Script probiert je Datentyp die dokumentierte
Methode und bei Ablehnung die naheliegenden Varianten, und hält fest, was
funktioniert hat.

Danach stehen in docs/api-proben/ echte Antworten, und sync.py lässt sich in
Minuten richtigstellen statt zu raten.

Aufruf:  python probe.py [Anzahl Tage, Standard 3]
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta

from config import PROJECT_DIR

PROBEN_DIR = PROJECT_DIR / "docs" / "api-proben"

# Laut Referenz:
#   "tag"      -> Tageszusammenfassung, nur list (Filter über .date)
#   "rollup"   -> dailyRollUp (POST) funktioniert
#   "sitzung"  -> list mit Intervall (Schlaf, Training)
#   "probe"    -> list mit Messzeitpunkt (z. B. Gewicht)
KANDIDATEN = [
    ("daily-heart-rate-variability", "tag"),
    ("daily-resting-heart-rate", "tag"),
    ("daily-respiratory-rate", "tag"),
    ("daily-oxygen-saturation", "tag"),
    ("daily-sleep-temperature-derivations", "tag"),
    ("daily-heart-rate-zones", "tag"),
    ("daily-vo2-max", "tag"),
    ("respiratory-rate-sleep-summary", "sitzung"),
    ("heart-rate-variability", "probe"),
    ("steps", "rollup"),
    ("distance", "rollup"),
    ("total-calories", "rollup"),
    ("active-energy-burned", "rollup"),
    ("active-zone-minutes", "rollup"),
    ("time-in-heart-rate-zone", "rollup"),
    ("heart-rate", "rollup"),
    ("sleep", "sitzung"),
    ("exercise", "sitzung"),
    ("weight", "probe"),
    ("height", "probe"),
]

EINZELNE = ["users/me/identity", "users/me/profile", "users/me/settings",
            "users/me/pairedDevices"]


def pfade(objekt, prefix: str = "", tiefe: int = 0) -> list[str]:
    """Alle Feldpfade eines Objekts, damit man die Struktur auf einen Blick sieht."""
    if tiefe > 7:
        return [f"{prefix} …"]
    if isinstance(objekt, dict):
        raus = []
        for k, v in objekt.items():
            raus.extend(pfade(v, f"{prefix}.{k}" if prefix else k, tiefe + 1))
        return raus
    if isinstance(objekt, list):
        if not objekt:
            return [f"{prefix}[] (leer)"]
        return pfade(objekt[0], f"{prefix}[]", tiefe + 1)
    kurz = str(objekt)
    if len(kurz) > 40:
        kurz = kurz[:40] + "…"
    return [f"{prefix} = {kurz}  ({type(objekt).__name__})"]


def filter_varianten(datentyp: str, art: str, von: date, bis_excl: date) -> list[str | None]:
    """Mögliche Schreibweisen des Filters. Die Doku zeigt nur 'steps' als
    Beispiel - ob Typen mit Bindestrich im Filter als snake_case erscheinen,
    ist offen. Deshalb mehrere Versuche, zuletzt ganz ohne Filter."""
    namen = [datentyp.replace("-", "_"), datentyp]
    a, b = von.isoformat(), bis_excl.isoformat()
    raus: list[str | None] = []
    for n in namen:
        if art == "tag":
            raus.append(f'{n}.date >= "{a}" AND {n}.date < "{b}"')
        elif art == "sitzung":
            raus.append(f'{n}.interval.civil_start_time >= "{a}" AND '
                        f'{n}.interval.civil_start_time < "{b}"')
        else:  # probe
            raus.append(f'{n}.sample_time.civil_time >= "{a}T00:00:00" AND '
                        f'{n}.sample_time.civil_time < "{b}T00:00:00"')
    raus.append(None)
    return raus


def main() -> int:
    tage = 3
    if len(sys.argv) > 1:
        try:
            tage = max(1, min(14, int(sys.argv[1])))
        except ValueError:
            sys.exit("Aufruf:  python probe.py [Anzahl Tage]")

    from api import HealthAPI, civil  # erst hier: Hilfe läuft auch ohne Anmeldung

    heute = date.today()
    von = heute - timedelta(days=tage - 1)      # heute eingeschlossen: die Uhr
    bis_excl = heute + timedelta(days=1)        # wird erst seit Kurzem getragen

    PROBEN_DIR.mkdir(parents=True, exist_ok=True)
    api = HealthAPI()
    protokoll: dict = {"zeitpunkt": datetime.now().isoformat(timespec="seconds"),
                       "zeitraum": [von.isoformat(), heute.isoformat()],
                       "einzeln": {}, "datentypen": {}}

    print(f"Probeabruf {von} bis {heute}\n")
    print("Einzelne Ressourcen:")
    for pfad in EINZELNE:
        a = api.einzeln(pfad)
        name = pfad.split("/")[-1]
        print(f"  {name:<38} {'ok' if a.ok else 'FEHLER  ' + str(a.fehler)}")
        protokoll["einzeln"][name] = {"ok": a.ok, "fehler": a.fehler}
        if a.ok:
            (PROBEN_DIR / f"_{name}.json").write_text(
                json.dumps(a.daten, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDatentypen:")
    erfolg, leer, fehler = [], [], []
    for datentyp, art in KANDIDATEN:
        print(f"  {datentyp:<38} ", end="", flush=True)
        versuche = []
        treffer = None

        if art == "rollup":
            # Bestaetigt: Zeitraum als CivilDateTime (date + time). pageSize
            # weglassen - bei total-calories und heart-rate fuehrt ein Wert von
            # 50 zu "Invalid argument".
            for variante in ("civil",):
                rng = {"start": civil(von), "end": civil(bis_excl)}
                a = api._post(f"users/me/dataTypes/{datentyp}/dataPoints:dailyRollUp",
                              {"range": rng, "windowSizeDays": 1})
                versuche.append({"methode": f"dailyRollUp/{variante}", "ok": a.ok,
                                 "fehler": a.fehler})
                if a.ok:
                    treffer = ("dailyRollUp/" + variante, a.daten)
                    break
        else:
            for f in filter_varianten(datentyp, art, von, bis_excl):
                a = api.liste(datentyp, f,
                              seitengroesse=25 if datentyp in ("sleep", "exercise") else 1000,
                              max_seiten=5)
                versuche.append({"methode": "list", "filter": f, "ok": a.ok, "fehler": a.fehler})
                if a.ok:
                    treffer = ("list" + ("" if f else " ohne Filter"), a.daten)
                    break

        protokoll["datentypen"][datentyp] = {"versuche": versuche,
                                             "erfolg": treffer[0] if treffer else None}
        if not treffer:
            print(f"FEHLER  {versuche[-1]['fehler']}")
            fehler.append((datentyp, versuche))
            continue

        methode, daten = treffer
        punkte = next(iter((daten or {}).values()), []) if isinstance(daten, dict) else []
        (PROBEN_DIR / f"{datentyp}.json").write_text(
            json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
        if not punkte:
            print(f"leer    ({methode})")
            leer.append(datentyp)
        else:
            print(f"ok      {len(punkte):>4} Punkte  ({methode})")
            erfolg.append((datentyp, punkte[0]))

    (PROBEN_DIR / "_protokoll.json").write_text(
        json.dumps(protokoll, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 66)
    print(f"  {len(erfolg)} mit Daten · {len(leer)} leer · {len(fehler)} fehlerhaft")
    print("=" * 66)

    if erfolg:
        print("\nStruktur des jeweils ersten Punktes:\n")
        for datentyp, punkt in erfolg:
            print(f"── {datentyp}")
            for zeile in pfade(punkt):
                print(f"     {zeile}")
            print()

    if fehler:
        print("Fehlgeschlagen (letzter Versuch je Typ):")
        for datentyp, versuche in fehler:
            print(f"  {datentyp}: {versuche[-1]['fehler']}")

    print(f"\nRohantworten und Protokoll liegen in {PROBEN_DIR}")
    print("Diese Dateien enthalten deine Gesundheitsdaten und sind über .gitignore")
    print("von der Versionierung ausgeschlossen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
