"""Erzeugt einen realistischen Demo-Datensatz fuer Claude Health.

Solange keine Uhr da ist, fuellt dieses Script das Dashboard. Die Werte sind
erfunden, aber nicht zufaellig: ein harter Trainingstag senkt am Folgetag die
HRV, hebt den Ruhepuls und druckt den Erholungswert. Schlechter Schlaf wirkt
nach. So sehen die Kurven aus wie echte Kurven.

Sobald das Fitbit Air da ist, ersetzt sync.py dieses Script - das Datenformat
bleibt identisch, das Dashboard merkt keinen Unterschied.
"""
from __future__ import annotations

import json
import math
import random
from datetime import date, datetime, timedelta

import metrics
from config import DATA_JSON, HEALTH_DIR

TAGE = 90
MAX_HR = 190
DETAIL_TAGE = 14  # nur fuer die juengsten Tage Minutenwerte mitschreiben

rng = random.Random(20260910)

# Verhaltensweisen mit ihrer Haeufigkeit und ihrer tatsaechlichen Wirkung.
# Wichtig: die Wirkung wird beim Erzeugen wirklich angewandt. Die Prozentwerte
# im Dashboard werden hinterher aus den Daten zurueckgerechnet - sie sind also
# eine echte Auswertung und keine hingeschriebene Liste.
VERHALTEN = [
    # schluessel,          Text,                        p,     hrv,   schlaf_min, effizienz
    ("alkohol",            "Alkohol am Abend",          0.18, -0.13, -18, -4.5),
    ("koffein_spaet",      "Koffein nach 16 Uhr",       0.24, -0.07, -26, -2.5),
    ("spaet_arbeiten",     "Spät arbeiten",             0.22, -0.05, -21, -1.5),
    ("katze_im_zimmer",    "Katze im Schlafzimmer",     0.30, -0.01,  -4, -0.8),
    ("lesen_im_bett",      "Lesen im Bett",             0.34,  0.03,  11,  1.2),
    ("kein_bildschirm",    "Kein Bildschirm vor dem Schlafen", 0.38, 0.05, 15, 1.8),
    ("meditation",         "Atemübung am Abend",        0.26,  0.07,   9,  1.5),
]

SPORTARTEN = [
    ("Laufen", 0.75, 45, 5),
    ("Radfahren", 0.68, 75, 4),
    ("Krafttraining", 0.62, 55, 1),  # keine Distanz - Pace waere hier sinnlos
    ("Fussball", 0.78, 65, 5),
    ("Schwimmen", 0.70, 40, 4),
    ("Wandern", 0.55, 110, 2),
    ("Yoga", 0.45, 40, 1),
]


def _zonen_aus_einheit(intensitaet: float, dauer_min: int) -> dict[str, int]:
    """Verteilt die Trainingsdauer plausibel auf die Herzfrequenzzonen."""
    zentrum = intensitaet
    zonen = {z: 0.0 for z in metrics.ZONE_BOUNDS}
    for zone, (unten, oben) in metrics.ZONE_BOUNDS.items():
        mitte = (unten + oben) / 2
        # Glockenkurve um die Zielintensitaet
        gewicht = math.exp(-((mitte - zentrum) ** 2) / (2 * 0.09**2))
        zonen[zone] = gewicht
    summe = sum(zonen.values()) or 1.0
    verteilt = {z: int(round(dauer_min * 60 * g / summe)) for z, g in zonen.items()}
    return verteilt


def _hr_verlauf(intensitaet: float, dauer_min: int, rhr: int) -> list[int]:
    """Herzfrequenzkurve einer Einheit, ein Punkt je 30 Sekunden."""
    punkte = max(4, dauer_min * 2)
    ziel = rhr + (MAX_HR - rhr) * intensitaet
    reihe: list[int] = []
    aktuell = rhr + 15
    for i in range(punkte):
        fortschritt = i / punkte
        # Aufwaermen, Hauptteil, Ausklang
        if fortschritt < 0.12:
            soll = rhr + (ziel - rhr) * (fortschritt / 0.12)
        elif fortschritt > 0.9:
            soll = ziel - (ziel - rhr - 20) * ((fortschritt - 0.9) / 0.1)
        else:
            soll = ziel + math.sin(fortschritt * 14) * 9
        aktuell += (soll - aktuell) * 0.35 + rng.gauss(0, 2.5)
        reihe.append(int(round(max(rhr, min(MAX_HR, aktuell)))))
    return reihe


def _hypnogramm(start: datetime, phasen: dict[str, int], rhr: int) -> list[dict]:
    """Schlafphasen als Blockfolge, dazu die Herzfrequenz je 5 Minuten."""
    # Realistische Abfolge: Leicht -> Tief frueh in der Nacht, REM gegen Morgen
    blocks: list[tuple[str, int]] = []
    rest = dict(phasen)
    zyklen = 5
    for z in range(zyklen):
        anteil = 1.0 / (zyklen - z)
        for phase in ("light", "deep", "rem", "awake"):
            if rest.get(phase, 0) <= 0:
                continue
            # Tiefschlaf frueh, REM spaet gewichten
            faktor = 1.0
            if phase == "deep":
                faktor = 1.8 - 0.3 * z
            if phase == "rem":
                faktor = 0.3 + 0.45 * z
            menge = int(rest[phase] * anteil * max(0.15, faktor))
            menge = min(menge, rest[phase])
            if menge > 0:
                blocks.append((phase, menge))
                rest[phase] -= menge
    for phase, uebrig in rest.items():
        if uebrig > 0:
            blocks.append((phase, uebrig))

    reihe: list[dict] = []
    minute = 0
    hr_basis = {"awake": 12, "light": 3, "deep": -4, "rem": 7}
    for phase, dauer in blocks:
        for _ in range(0, max(5, dauer), 5):
            hr = rhr + hr_basis.get(phase, 0) + rng.gauss(0, 2.2)
            reihe.append(
                {
                    "m": minute,
                    "s": phase,
                    "hr": int(round(max(38, hr))),
                }
            )
            minute += 5
    return reihe


def _stress_verlauf(rhr: int, hrv: float, aktivitaeten: list[dict]) -> list[dict]:
    """Stresswert alle fuenf Minuten ueber den Tag.

    Feiner als fuenf Minuten bringt nichts: die zugrunde liegende HRV wird
    ohnehin nur ueber Fenster von mehreren Minuten bestimmt.
    """
    reihe: list[dict] = []
    aktiv_fenster = [
        (a["start_min"], a["start_min"] + a["duration_sec"] // 60) for a in aktivitaeten
    ]
    grundspannung = rng.uniform(0.25, 0.6)
    for minute in range(0, 24 * 60, 5):
        stunde = minute / 60
        in_bewegung = any(s <= minute <= e for s, e in aktiv_fenster)

        # Tagesrhythmus: nachts ruhig, Vormittag und spaeter Nachmittag hoeher
        tages = 0.0
        if 7 <= stunde <= 22:
            tages = 0.35 + 0.30 * math.sin((stunde - 7) / 15 * math.pi)
        else:
            tages = -0.15
            # Einschlafphase: der Koerper faehrt nicht schlagartig herunter.
            # In den ersten Stunden nach dem Zubettgehen liegt die Spannung
            # deutlich hoeher als spaeter in der Nacht.
            if stunde >= 22 or stunde < 1:
                naehe = (stunde - 22) if stunde >= 22 else (stunde + 2)
                tages += 0.75 * max(0.0, 1 - naehe / 3)
            # Kurze Weckreaktionen - Traeume, Lage wechseln, Geraeusche
            if rng.random() < 0.05:
                tages += rng.uniform(0.45, 1.20)

        hf = rhr + (tages + grundspannung) * 26 + rng.gauss(0, 4)
        if in_bewegung:
            hf = rhr + (MAX_HR - rhr) * 0.62

        wert = metrics.stress_value(
            hr=hf,
            hrv_now=hrv * rng.uniform(0.88, 1.12),
            rhr=rhr,
            max_hr=MAX_HR,
            hrv_baseline=hrv,
            in_bewegung=in_bewegung,
        )
        reihe.append({"t": f"{minute // 60:02d}:{minute % 60:02d}", "v": wert})
    return reihe


def _nacht_stress(reihe_gestern, reihe_heute, zubett_min: int, im_bett_min: int):
    """Schneidet aus den Tagesreihen das Stueck heraus, das in der Nacht liegt.

    Die Nacht beginnt am Vorabend und endet am Morgen, laeuft also ueber
    Mitternacht. Gerechnet wird auf einer Zeitachse, auf der 0 Uhr des
    Vortages der Nullpunkt ist: der Vortag deckt 0 bis 1440, der heutige Tag
    1440 bis 2880 ab. Ohne Vortagsreihe (erster Tag) gibt es keine Nacht.
    """
    if reihe_gestern is None:
        return None, None
    start = zubett_min if zubett_min >= 12 * 60 else zubett_min + 1440
    punkte = []
    for k in range(0, im_bett_min, 5):
        absolut = start + k
        quelle = reihe_gestern if absolut < 1440 else reihe_heute
        i = (absolut % 1440) // 5
        if i >= len(quelle):
            continue
        punkte.append({"m": k, "v": quelle[i]["v"]})
    if not punkte:
        return None, None
    werte = [q["v"] for q in punkte]
    verteilung = {
        "niedrig": sum(1 for v in werte if v < 1.0) * 5,
        "mittel": sum(1 for v in werte if 1.0 <= v < 2.0) * 5,
        "hoch": sum(1 for v in werte if v >= 2.0) * 5,
    }
    return punkte, verteilung


def erzeuge(tage_gesamt: int = TAGE) -> dict:
    heute = date(2026, 9, 10)
    start = heute - timedelta(days=tage_gesamt - 1)

    # Persoenliche Ausgangswerte, driften ueber den Zeitraum leicht
    hrv_basis = 54.0
    rhr_basis = 54.0

    tage: list[dict] = []
    strain_gestern = 8.0
    schlafdefizit = 0.0
    verlauf = {"hrv": [], "rhr": [], "resp": [], "spo2": []}
    bett_verlauf: list[int] = []
    wach_verlauf: list[int] = []
    # Der Stressverlauf des Vortages wird gebraucht, weil eine Nacht am
    # Vorabend beginnt. Ohne ihn liesse sich nur der Teil nach Mitternacht
    # auswerten - und der waere systematisch zu ruhig.
    stress_reihe_gestern: list[dict] | None = None

    for i in range(tage_gesamt):
        tag = start + timedelta(days=i)
        wochentag = tag.weekday()
        ist_juengst = i >= tage_gesamt - DETAIL_TAGE

        # Leichte Formsteigerung ueber den Zeitraum
        trend = i / max(1, tage_gesamt)
        hrv_soll = hrv_basis + trend * 6
        rhr_soll = rhr_basis - trend * 3

        # Verhalten dieses Abends wuerfeln - die Wirkung wird danach wirklich
        # auf HRV, Schlafdauer und Effizienz angewandt.
        journal = {k: rng.random() < p for k, _t, p, _h, _s, _e in VERHALTEN}
        v_hrv = sum(h for k, _t, _p, h, _s, _e in VERHALTEN if journal[k])
        v_schlaf = sum(s for k, _t, _p, _h, s, _e in VERHALTEN if journal[k])
        v_eff = sum(e for k, _t, _p, _h, _s, e in VERHALTEN if journal[k])

        # Nachwirkung des Vortags
        ermuedung = (strain_gestern - 9.0) / 6.0
        hrv = (hrv_soll - ermuedung * 5.5 + rng.gauss(0, 4.0)) * (1 + v_hrv)
        rhr = rhr_soll + ermuedung * 2.6 + rng.gauss(0, 1.8)
        resp = 14.4 + ermuedung * 0.35 + rng.gauss(0, 0.45)
        spo2 = 96.4 - max(0.0, ermuedung) * 0.5 + rng.gauss(0, 0.7)
        haut_abw = ermuedung * 0.25 + rng.gauss(0, 0.22)

        # Gelegentlich ein Infekt-artiger Ausreisser
        if rng.random() < 0.035:
            hrv *= 0.72
            rhr += 5.5
            resp += 1.3
            haut_abw += 0.75

        hrv = max(18.0, hrv)
        rhr = max(38.0, rhr)

        # Ein paar Tage ohne Traguebereitschaft - Luecken in den Daten
        luecke = rng.random() < 0.035
        if luecke:
            hrv_w = rhr_w = resp_w = spo2_w = haut_w = None
        else:
            hrv_w, rhr_w = round(hrv, 1), round(rhr)
            resp_w, spo2_w = round(resp, 1), round(spo2, 1)
            haut_w = round(haut_abw, 2)

        for key, wert in (("hrv", hrv_w), ("rhr", rhr_w), ("resp", resp_w), ("spo2", spo2_w)):
            verlauf[key].append(wert)
        basis = metrics.build_baseline({k: v[-30:] for k, v in verlauf.items()})

        # --- Schlaf der Nacht auf diesen Tag ---
        bedarf = metrics.sleep_need_minutes(
            strain_gestern=strain_gestern,
            schlafdefizit_min=schlafdefizit,
            nickerchen_min=0,
        )
        wunsch = bedarf["total"]
        gesch = wunsch * rng.uniform(0.72, 1.06) + v_schlaf
        if wochentag in (4, 5):  # Freitag/Samstagnacht kuerzer
            gesch *= rng.uniform(0.82, 0.95)
        dauer = int(max(240, min(600, gesch)))

        effizienz = int(round(min(98, max(62, rng.gauss(91, 3.2) + v_eff))))
        zeit_im_bett = int(dauer / (effizienz / 100))
        wach = zeit_im_bett - dauer
        tief = int(dauer * rng.uniform(0.18, 0.28))
        rem = int(dauer * rng.uniform(0.16, 0.24))
        leicht = dauer - tief - rem

        zubett_min = (22 * 60 + int(rng.gauss(75, 42))) % (24 * 60)
        aufwach_min = (zubett_min + zeit_im_bett) % (24 * 60)
        einschlafen = int(max(2, rng.gauss(14, 7)))
        leistung, leistung_teile = metrics.sleep_performance_detail(
            dauer, wunsch, tief_min=tief, rem_min=rem, wach_min=wach,
            einschlaf_min=einschlafen)

        # Konsistenz und erholsamer Anteil werden hergeleitet, nicht gewuerfelt.
        bett_verlauf.append(zubett_min)
        wach_verlauf.append(aufwach_min)
        konsistenz = metrics.sleep_consistency(bett_verlauf[-14:], wach_verlauf[-14:])
        erholsam = metrics.restorative_share(
            {"awake": wach, "light": leicht, "deep": tief, "rem": rem}
        )

        schlafdefizit = max(0.0, schlafdefizit + (wunsch - dauer) * 0.5)

        schlaf = {
            "bedtime_min": zubett_min % (24 * 60),
            "waketime_min": aufwach_min,
            "duration_min": dauer,
            "time_in_bed_min": zeit_im_bett,
            "need": bedarf,
            "performance": leistung,
            "performance_teile": leistung_teile,
            "awake_min": wach,
            "fall_asleep_min": einschlafen,
            "efficiency": effizienz,
            "consistency": konsistenz,
            "restorative": erholsam,
            "stages": {"awake": wach, "light": leicht, "deep": tief, "rem": rem},
            # Zahl der Wachphasen. Die Fitbit-Schnittstelle liefert sie je
            # Nacht mit; hier wird sie aus der Wachzeit abgeleitet, weil der
            # Demo-Datensatz keine echte Messung hat.
            "wake_count": max(1 if wach > 0 else 0,
                              int(round(wach / 2.0 + rng.gauss(0, 1.4)))),
        }
        if ist_juengst and not luecke:
            schlaf["hypnogram"] = _hypnogramm(
                datetime.combine(tag, datetime.min.time()), schlaf["stages"], int(rhr)
            )

        # --- Erholung ---
        erholung, beitraege = metrics.recovery_score(
            hrv=hrv_w,
            rhr=rhr_w,
            resp=resp_w,
            spo2=spo2_w,
            skin_temp_dev=haut_w,
            sleep_performance=leistung,
            base=basis,
        )

        # --- Aktivitaeten ---
        aktivitaeten: list[dict] = []
        trainiert = wochentag in (0, 1, 3, 5) or rng.random() < 0.22
        if erholung is not None and erholung < 32 and rng.random() < 0.6:
            trainiert = False  # bei schlechter Erholung eher Pause
        if trainiert and not luecke:
            anzahl = 2 if rng.random() < 0.16 else 1
            for _ in range(anzahl):
                name, intens, dauer_typ, dist_faktor = rng.choice(SPORTARTEN)
                intensitaet = max(0.35, min(0.92, intens + rng.gauss(0, 0.06)))
                a_dauer = int(max(18, rng.gauss(dauer_typ, dauer_typ * 0.28)))
                zonen = _zonen_aus_einheit(intensitaet, a_dauer)
                start_min = 8 * 60 + int(rng.gauss(150, 190))
                start_min = max(6 * 60, min(20 * 60, start_min))
                a_strain = metrics.strain_from_zones(zonen)
                avg_hr = int(round(int(rhr) + (MAX_HR - int(rhr)) * intensitaet * 0.86))
                akt = {
                    "name": name,
                    "start_min": start_min,
                    "duration_sec": a_dauer * 60,
                    "strain": a_strain,
                    "avg_hr": avg_hr,
                    "max_hr": int(round(min(MAX_HR, avg_hr + rng.uniform(14, 30)))),
                    "calories": int(a_dauer * rng.uniform(7.5, 13.5)),
                    "zones_sec": zonen,
                }
                if dist_faktor >= 2:
                    akt["distance_km"] = round(a_dauer / 60 * dist_faktor * rng.uniform(0.85, 1.15), 2)
                if ist_juengst:
                    akt["hr_series"] = _hr_verlauf(intensitaet, a_dauer, int(rhr))
                aktivitaeten.append(akt)

        # --- Tagesbelastung: Aktivitaeten plus Alltag ---
        tages_zonen = {z: 0 for z in metrics.ZONE_BOUNDS}
        for akt in aktivitaeten:
            for z, sek in akt["zones_sec"].items():
                tages_zonen[z] += sek
        # Alltagsbewegung
        tages_zonen["z1"] += int(rng.gauss(52, 18) * 60)
        tages_zonen["z2"] += int(rng.gauss(16, 9) * 60)
        tages_zonen = {z: max(0, s) for z, s in tages_zonen.items()}
        strain = metrics.strain_from_zones(tages_zonen)

        schritte = int(max(900, rng.gauss(8200, 2600) + len(aktivitaeten) * 2600))
        distanz = round(schritte * 0.00073 * rng.uniform(0.92, 1.08), 2)
        kalorien = int(1750 + strain * 62 + rng.gauss(0, 130))

        # --- Stress ---
        stress_reihe = _stress_verlauf(int(rhr), hrv, aktivitaeten)
        werte = [p["v"] for p in stress_reihe]
        # Verteilung in Minuten - wird fuer JEDEN Tag mitgeschrieben, auch ohne
        # Minutenwerte. Sonst reichte die Trendansicht nur so weit zurueck wie
        # die Detailtage.
        schritt_min = 5
        stress = {
            "avg": round(sum(werte) / len(werte), 1),
            "min": min(werte),
            "max": max(werte),
            "verteilung": {
                "niedrig": sum(1 for v in werte if v < 1.0) * schritt_min,
                "mittel": sum(1 for v in werte if 1.0 <= v < 2.0) * schritt_min,
                "hoch": sum(1 for v in werte if v >= 2.0) * schritt_min,
            },
        }
        # --- Schlafstress: derselbe Wert, aber nur ueber das Schlaffenster ---
        nacht_punkte, nacht_verteilung = _nacht_stress(
            stress_reihe_gestern, stress_reihe, zubett_min, zeit_im_bett
        )
        if nacht_verteilung:
            schlaf["stress"] = nacht_verteilung
            if ist_juengst:
                schlaf["stress_reihe"] = nacht_punkte

        if ist_juengst:
            stress["series"] = stress_reihe
            # Fenster fuer die Markierungen im Tagesverlauf
            stress["nacht"] = [0, aufwach_min] if aufwach_min < 12 * 60 else None
            stress["einheiten"] = [
                {"name": a["name"], "von": a["start_min"],
                 "bis": a["start_min"] + a["duration_sec"] // 60}
                for a in aktivitaeten
            ]

        eintrag = {
            "date": tag.isoformat(),
            "weekday": tag.weekday(),
            "gap": luecke,
            "recovery": {
                "score": None if luecke else erholung,
                "zone": None if (luecke or erholung is None) else metrics.recovery_zone(erholung),
                # Wie viele Tage stecken im Normalbereich, und reicht das schon?
                "baseline_days": basis.tage,
                "calibrating": not basis.ausreichend,
                "hrv": hrv_w,
                "rhr": rhr_w,
                "resp": resp_w,
                "spo2": spo2_w,
                "skin_temp_dev": haut_w,
                "drivers": {k: round(v, 2) for k, v in beitraege.items()},
            },
            "sleep": schlaf,
            "strain": {
                "score": strain,
                "label": metrics.strain_label(strain),
                "calories": kalorien,
                "zones_sec": tages_zonen,
            },
            "steps": schritte,
            "distance_km": distanz,
            "stress": stress,
            "activities": aktivitaeten,
            "journal": journal,
        }
        tage.append(eintrag)
        stress_reihe_gestern = stress_reihe
        strain_gestern = strain

    # Wirkung der Verhaltensweisen aus den erzeugten Tagen zurueckrechnen.
    # Kein fester Wert wird hier hingeschrieben - was sich nicht belegen
    # laesst, faellt raus.
    wirkung = []
    for schluessel, text, *_ in VERHALTEN:
        wert = metrics.behaviour_impact(tage, schluessel)
        if wert is None:
            continue
        mit = sum(1 for t in tage if t["journal"].get(schluessel))
        wirkung.append({"key": schluessel, "label": text, "impact": wert, "days": mit})
    wirkung.sort(key=lambda w: -w["impact"])

    return {
        "app": "Claude Health",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "is_demo": True,
        "profile": {
            "name": "Johann",
            "max_hr": MAX_HR,
            "baseline_min_days": metrics.MIN_TAGE_BASIS,
        },
        "journal_impact": wirkung,
        # Lesbare Bezeichnungen zu den Journal-Schluesseln, damit die Notizen
        # "Kein Bildschirm vor dem Schlafen" schreiben und nicht "kein_bildschirm".
        "journal_labels": {k: text for k, text, *_ in VERHALTEN},
        "days": tage,
    }


if __name__ == "__main__":
    import sys

    # Optional die Anzahl Tage vorgeben - damit laesst sich pruefen, wie sich
    # das Dashboard am ersten Tag mit echten Daten verhaelt, wenn noch kein
    # Normalbereich existiert.
    anzahl = TAGE
    if len(sys.argv) > 1:
        try:
            anzahl = max(1, min(365, int(sys.argv[1])))
        except ValueError:
            sys.exit("Aufruf:  python demo_data.py [Anzahl Tage]")

    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    daten = erzeuge(anzahl)
    DATA_JSON.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")

    tage = daten["days"]
    mit_werten = sum(1 for t in tage if not t["gap"])
    einheiten = sum(len(t["activities"]) for t in tage)
    groesse = DATA_JSON.stat().st_size / 1024

    print(f"Demo-Daten geschrieben: {DATA_JSON}")
    print(f"  Zeitraum      : {tage[0]['date']} bis {tage[-1]['date']}")
    print(f"  Tage gesamt   : {len(tage)}")
    print(f"  mit Werten    : {mit_werten}")
    print(f"  Luecken       : {len(tage) - mit_werten}")
    print(f"  Einheiten     : {einheiten}")
    print(f"  Dateigroesse  : {groesse:.0f} KB")
    letzter = tage[-1]
    print(
        f"  Letzter Tag   : Erholung {letzter['recovery']['score']} %, "
        f"Belastung {letzter['strain']['score']}, "
        f"Schlaf {letzter['sleep']['duration_min'] // 60}:{letzter['sleep']['duration_min'] % 60:02d}"
    )

