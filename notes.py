"""Schreibt aus data.json lesbare Markdown-Notizen.

Zweck: data.json ist fuer Maschinen. Diese Notizen sind dafuer da, dass ein
Mensch - oder Claude in einem spaeteren Gespraech - die Daten einfach lesen
und darueber reden kann, ohne 278 KB JSON zu durchsuchen.

Es entstehen:
    health/UEBERSICHT.md          Einstieg: letzte 14 Tage plus Kennzahlen
    health/tage/JJJJ-MM-TT.md     eine Notiz je Tag
    health/workouts/...md         eine Notiz je Einheit

Aufruf:  python notes.py
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date

from config import DATA_JSON, DAYS_DIR, HEALTH_DIR, WORKOUTS_DIR

WOCHENTAG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONAT = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
ZONEN_TEXT = {
    "z5": "Zone 5 (90–100 %)", "z4": "Zone 4 (80–90 %)", "z3": "Zone 3 (70–80 %)",
    "z2": "Zone 2 (60–70 %)", "z1": "Zone 1 (50–60 %)", "z0": "Zone 0 (< 50 %)",
}
PHASEN_TEXT = {"awake": "Wach", "light": "Leicht", "deep": "Tief", "rem": "REM"}


def hm(minuten) -> str:
    if minuten is None:
        return "–"
    minuten = int(round(minuten))
    return f"{minuten // 60}:{minuten % 60:02d}"


def uhr(minuten) -> str:
    if minuten is None:
        return "–"
    minuten = int(round(minuten)) % (24 * 60)
    return f"{minuten // 60:02d}:{minuten % 60:02d}"


def za(wert, einheit: str = "", nachkomma: int = 1) -> str:
    """Zahl deutsch formatieren. None wird ausdruecklich zu 'keine Daten'."""
    if wert is None:
        return "keine Daten"
    if isinstance(wert, float) and abs(wert - round(wert)) >= 0.05:
        text = f"{wert:.{nachkomma}f}".replace(".", ",")
    else:
        text = f"{int(round(wert)):,}".replace(",", ".")
    return f"{text} {einheit}".strip()


def dez(wert) -> str:
    """Immer eine Nachkommastelle - fuer Tabellenspalten, damit 8 und 0,8
    nicht untereinander stehen und verschieden aussehen."""
    if wert is None:
        return "–"
    return f"{wert:.1f}".replace(".", ",")


def lang(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{WOCHENTAG[d.weekday()]}, {d.day}. {MONAT[d.month - 1]} {d.year}"


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "einheit"


def tagesnotiz(tag: dict, profil: dict) -> str:
    r, s, st = tag["recovery"], tag["sleep"], tag["strain"]
    z = []
    z.append(f"# {lang(tag['date'])}")
    z.append("")

    if tag.get("gap"):
        z.append("> **Keine Messwerte an diesem Tag.** Die Uhr wurde nicht getragen.")
        z.append("")
        return "\n".join(z)

    # --- Erholung ---
    if r.get("calibrating"):
        fehlt = max(1, profil.get("baseline_min_days", 7) - (r.get("baseline_days") or 0))
        z.append("## Erholung: noch nicht berechenbar")
        z.append("")
        z.append(
            f"Der Normalbereich beruht bisher auf {r.get('baseline_days', 0)} Messtagen; "
            f"nötig sind {profil.get('baseline_min_days', 7)}. Noch {fehlt} Tage. "
            "Bis dahin wird kein Wert ausgegeben — eine Zahl gegen einen erfundenen "
            "Vergleichswert wäre keine Aussage."
        )
    elif r.get("score") is None:
        z.append("## Erholung: keine Daten")
    else:
        zone = {"gruen": "grün – belastbar", "gelb": "gelb – Niveau halten",
                "rot": "rot – Ruhe nötig"}.get(r.get("zone"), "")
        z.append(f"## Erholung: {r['score']} %  ({zone})")
        z.append("")
        z.append(
            "*Berechnet* aus HFV, Ruhepuls, Atemfrequenz, Blutsauerstoff, Hauttemperatur "
            "und Schlafleistung, verglichen mit dem eigenen Normalbereich."
        )
    z.append("")

    # --- Vitalwerte (gemessen) ---
    z.append("### Gemessene Vitalwerte")
    z.append("")
    z.append("| Wert | Messung |")
    z.append("|---|---|")
    z.append(f"| Herzfrequenzvariabilität | {za(r.get('hrv'), 'ms')} |")
    z.append(f"| Ruheherzfrequenz | {za(r.get('rhr'), 'bpm')} |")
    z.append(f"| Atemfrequenz | {za(r.get('resp'), '/min')} |")
    z.append(f"| Blutsauerstoff | {za(r.get('spo2'), '%')} |")
    temp = r.get("skin_temp_dev")
    z.append(
        f"| Hauttemperatur | {'keine Daten' if temp is None else f'{temp:+.2f} °C vom Normalwert'.replace('.', ',')} |"
    )
    z.append("")

    # --- Schlaf ---
    stg = s.get("stages", {})
    z.append(f"## Schlaf: {hm(s.get('duration_min'))} h  (Leistung {za(s.get('performance'), '%')})")
    z.append("")
    z.append(f"- Im Bett {uhr(s.get('bedtime_min'))} – {uhr(s.get('waketime_min'))} "
             f"({hm(s.get('time_in_bed_min'))} h), Effizienz {za(s.get('efficiency'), '%')}")
    z.append("- Phasen: " + " · ".join(
        f"{PHASEN_TEXT[k]} {hm(stg.get(k))}" for k in ("awake", "light", "deep", "rem")))
    z.append(f"- Erholsamer Anteil (Tief + REM): {za(s.get('restorative'), '%')}")
    z.append(f"- Schlafkonsistenz: {za(s.get('consistency'), '%')}")
    n = s.get("need", {})
    z.append(
        f"- *Berechneter* Bedarf {hm(n.get('total'))} h = {hm(n.get('baseline'))} Grundbedarf "
        f"+ {hm(n.get('strain'))} Belastung + {hm(n.get('debt'))} Defizit"
        + (f" − {hm(n.get('naps'))} Nickerchen" if n.get("naps") else "")
    )
    z.append("")

    # --- Belastung ---
    z.append(f"## Belastung: {za(st.get('score'))} von 21  ({st.get('label', '')})")
    z.append("")
    z.append("*Berechnet* aus der gemessenen Zeit in den Herzfrequenzzonen.")
    z.append("")
    zonen = st.get("zones_sec", {})
    for k in ("z5", "z4", "z3", "z2", "z1", "z0"):
        # unter einer Minute nicht auffuehren - stuende sonst als "0:00 h" da
        if zonen.get(k, 0) >= 60:
            z.append(f"- {ZONEN_TEXT[k]}: {hm(zonen[k] / 60)} h")
    z.append("")
    z.append(f"Schritte {za(tag.get('steps'))} · Distanz {za(tag.get('distance_km'), 'km')} "
             f"· {za(st.get('calories'), 'kcal')}")
    z.append("")

    # --- Einheiten ---
    akt = tag.get("activities", [])
    if akt:
        z.append("## Einheiten")
        z.append("")
        for a in akt:
            dauer = a["duration_sec"] / 60
            z.append(f"### {a['name']} · {uhr(a['start_min'])}–{uhr(a['start_min'] + dauer)}")
            teile = [
                f"Belastung {za(a.get('strain'))}",
                f"Dauer {hm(dauer)} h",
                f"⌀ {za(a.get('avg_hr'), 'bpm')}",
                f"max {za(a.get('max_hr'), 'bpm')}",
                f"{za(a.get('calories'), 'kcal')}",
            ]
            if a.get("distance_km"):
                pace = dauer / a["distance_km"]
                teile.insert(2, f"{za(a['distance_km'], 'km')}")
                teile.insert(3, f"Pace {int(pace)}:{int(round(pace % 1 * 60)):02d} min/km")
            z.append(" · ".join(teile))
            z.append("")
    else:
        z.append("## Einheiten")
        z.append("")
        z.append("Keine Einheit — Ruhetag.")
        z.append("")

    # --- Stress ---
    stress = tag.get("stress", {})
    stufe = ("hoch" if (stress.get("avg") or 0) >= 2 else
             "mittel" if (stress.get("avg") or 0) >= 1 else "niedrig")
    z.append(f"## Stress: ⌀ {za(stress.get('avg'))} von 3,0 ({stufe})")
    z.append("")
    z.append(f"Spanne {za(stress.get('min'))} – {za(stress.get('max'))}. "
             "*Berechnet* aus Herzfrequenz und HFV gegen den 14-Tage-Normalwert.")
    z.append("")

    # --- Journal ---
    journal = tag.get("journal", {})
    labels = profil.get("_journal_labels", {})
    aktiv = sorted(labels.get(k, k) for k, v in journal.items() if v)
    if aktiv:
        z.append("## Journal")
        z.append("")
        z.append(", ".join(aktiv))
        z.append("")

    return "\n".join(z)


def workoutnotiz(tag: dict, a: dict) -> str:
    dauer = a["duration_sec"] / 60
    z = [f"# {a['name']} — {lang(tag['date'])}", ""]
    z.append(f"{uhr(a['start_min'])}–{uhr(a['start_min'] + dauer)} · {hm(dauer)} h")
    z.append("")
    z.append("| Wert | |")
    z.append("|---|---|")
    z.append(f"| Belastung (berechnet) | {za(a.get('strain'))} von 21 |")
    z.append(f"| Durchschnittspuls | {za(a.get('avg_hr'), 'bpm')} |")
    z.append(f"| Maximalpuls | {za(a.get('max_hr'), 'bpm')} |")
    z.append(f"| Kalorien | {za(a.get('calories'), 'kcal')} |")
    if a.get("distance_km"):
        pace = dauer / a["distance_km"]
        z.append(f"| Distanz | {za(a['distance_km'], 'km')} |")
        z.append(f"| Pace | {int(pace)}:{int(round(pace % 1 * 60)):02d} min/km |")
    z.append("")
    z.append("## Zeit in den Herzfrequenzzonen")
    z.append("")
    for k in ("z5", "z4", "z3", "z2", "z1", "z0"):
        sek = a.get("zones_sec", {}).get(k, 0)
        if sek >= 60:
            z.append(f"- {ZONEN_TEXT[k]}: {hm(sek / 60)} h")
    z.append("")
    z.append(f"Erholung in der Nacht danach siehe `../tage/{tag['date']}.md` (Folgetag).")
    z.append("")
    return "\n".join(z)


def uebersicht(daten: dict) -> str:
    tage = daten["days"]
    profil = daten.get("profile", {})
    letzte = tage[-14:][::-1]

    z = ["# Claude Health — Überblick", ""]
    if daten.get("is_demo"):
        z.append("> ⚠️ **Demo-Daten.** Noch keine Uhr verbunden. Die Werte sind erzeugt, "
                 "aber physiologisch plausibel gekoppelt.")
        z.append("")
    z.append(f"Zeitraum {tage[0]['date']} bis {tage[-1]['date']} · {len(tage)} Tage · "
             f"Stand {daten.get('generated_at', '')}")
    z.append("")
    z.append("## Letzte 14 Tage")
    z.append("")
    z.append("| Datum | Erholung | HFV | RHF | Atem | SpO₂ | Schlaf | Belastung | Stress | Schritte |")
    z.append("|---|---|---|---|---|---|---|---|---|---|")
    for t in letzte:
        r, s = t["recovery"], t["sleep"]
        erh = "kalibriert" if r.get("calibrating") else (
            f"{r['score']} %" if r.get("score") is not None else "–")
        z.append(
            f"| {t['date']} | {erh} | {za(r.get('hrv'))} | {za(r.get('rhr'))} | "
            f"{za(r.get('resp'))} | {za(r.get('spo2'))} | {hm(s.get('duration_min'))} | "
            f"{dez(t['strain'].get('score'))} | {dez(t['stress'].get('avg'))} | "
            f"{za(t.get('steps'))} |"
        )
    z.append("")

    # Kennzahlen ueber den ganzen Zeitraum
    def schnitt(f):
        w = [f(t) for t in tage]
        w = [x for x in w if x is not None]
        return sum(w) / len(w) if w else None

    z.append("## Durchschnitt über den Zeitraum")
    z.append("")
    z.append(f"- Erholung: {za(schnitt(lambda t: t['recovery'].get('score')), '%')}")
    z.append(f"- HFV: {za(schnitt(lambda t: t['recovery'].get('hrv')), 'ms')}")
    z.append(f"- Ruhepuls: {za(schnitt(lambda t: t['recovery'].get('rhr')), 'bpm')}")
    z.append(f"- Schlaf: {hm(schnitt(lambda t: t['sleep'].get('duration_min')))} h")
    z.append(f"- Belastung: {za(schnitt(lambda t: t['strain'].get('score')))}")
    z.append(f"- Schritte: {za(schnitt(lambda t: t.get('steps')))}")
    z.append("")

    wirkung = daten.get("journal_impact", [])
    if wirkung:
        z.append("## Wirkung der Verhaltensweisen auf die Erholung")
        z.append("")
        z.append("Vergleich der Tage mit und ohne das jeweilige Verhalten. "
                 "Zusammenhang, keine Ursache.")
        z.append("")
        for w in wirkung:
            z.append(f"- {w['label']}: {w['impact']:+d} % (an {w['days']} Tagen)")
        z.append("")

    z.append("## Aufbau")
    z.append("")
    z.append("- `tage/JJJJ-MM-TT.md` — eine Notiz je Tag")
    z.append("- `workouts/` — eine Notiz je Einheit")
    z.append("- `data.json` — dieselben Daten maschinenlesbar")
    z.append("")
    z.append("Werte mit dem Hinweis *berechnet* stammen nicht direkt von der Uhr, "
             "sondern aus einer Formel über gemessene Größen. Alles andere ist gemessen. "
             "Fehlende Werte stehen als „keine Daten“ und nie als Null.")
    z.append("")
    return "\n".join(z)


def schreibe(daten: dict) -> dict:
    DAYS_DIR.mkdir(parents=True, exist_ok=True)
    WORKOUTS_DIR.mkdir(parents=True, exist_ok=True)

    # Alte Notizen entfernen, damit keine Leichen aus frueheren Laeufen bleiben
    for ordner in (DAYS_DIR, WORKOUTS_DIR):
        for alt in ordner.glob("*.md"):
            alt.unlink()

    profil = dict(daten.get("profile", {}))
    profil["_journal_labels"] = daten.get("journal_labels", {})
    anzahl_tage = anzahl_workouts = 0

    for tag in daten["days"]:
        (DAYS_DIR / f"{tag['date']}.md").write_text(
            tagesnotiz(tag, profil), encoding="utf-8")
        anzahl_tage += 1
        for i, a in enumerate(tag.get("activities", []), 1):
            name = f"{tag['date']}-{i}-{slug(a['name'])}.md"
            (WORKOUTS_DIR / name).write_text(workoutnotiz(tag, a), encoding="utf-8")
            anzahl_workouts += 1

    (HEALTH_DIR / "UEBERSICHT.md").write_text(uebersicht(daten), encoding="utf-8")
    return {"tage": anzahl_tage, "workouts": anzahl_workouts}


if __name__ == "__main__":
    import sys

    if not DATA_JSON.exists():
        sys.exit(f"Keine Daten: {DATA_JSON}\nErst erzeugen:  python demo_data.py")
    daten = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    ergebnis = schreibe(daten)
    print(f"Notizen geschrieben nach {HEALTH_DIR}")
    print(f"  Tagesnotizen : {ergebnis['tage']}")
    print(f"  Workouts     : {ergebnis['workouts']}")
    print(f"  Überblick    : {HEALTH_DIR / 'UEBERSICHT.md'}")
