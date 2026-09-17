"""Holt die Messwerte von Google, rechnet die Kennzahlen und legt sie ab.

Ablauf:
    1. Rohdaten je Datentyp abrufen (api.py)
    2. auf Tage umrechnen und zu einem Tagesdatensatz zusammensetzen
    3. daraus Erholung, Schlafleistung, Belastung und Stress rechnen (metrics.py)
    4. nach Firestore schreiben (speicher.py) und zusaetzlich als health/data.json

Der Tagesdatensatz hat bewusst dieselbe Form wie die Demodaten. Dadurch laeuft
das Dashboard unveraendert weiter, egal ob echte oder erfundene Zahlen drin
stehen.

Drei Dinge weichen von der urspruenglichen Planung ab. Sie stehen so in
docs/api-befunde.md und sind hier jeweils an Ort und Stelle begruendet:
    - Belastung aus dem Rohpuls statt aus Googles vier Zonen
    - Tagesstress nur aus dem Puls, weil HFV nur nachts gemessen wird
    - Temperatur-Basislinie selbst gebildet, weil Google sie anfangs als
      "NaN" liefert

Aufruf:
    python sync.py                  letzte 7 Tage
    python sync.py 90               letzte 90 Tage (erster Lauf)
    python sync.py 30 --nurdatei    ohne Firestore, nur health/data.json
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import metrics
from api import HealthAPI
from config import DATA_JSON, HEALTH_DIR

# Wie viele der juengsten Tage Minutenwerte bekommen (Hypnogramm, Stressverlauf).
# Fuer aeltere Tage nur die Tageswerte - sonst waechst jedes Dokument unnoetig.
DETAIL_TAGE = 14


# ---------------------------------------------------------------- Werkzeug
def zahl(wert, standard=None):
    """Google liefert Zahlen teils als String und Fehlwerte als "NaN"."""
    if wert is None:
        return standard
    try:
        f = float(wert)
    except (TypeError, ValueError):
        return standard
    return standard if math.isnan(f) else f


def versatz(text) -> int:
    """'7200s' -> 7200"""
    try:
        return int(str(text).rstrip("s"))
    except (TypeError, ValueError):
        return 0


def lokal(zeitstempel: str, offset_s: int) -> datetime:
    """RFC-3339 in Ortszeit umrechnen."""
    roh = datetime.fromisoformat(str(zeitstempel).replace("Z", "+00:00"))
    return roh + timedelta(seconds=offset_s)


def tagesminute(zeitpunkt: datetime) -> int:
    return zeitpunkt.hour * 60 + zeitpunkt.minute


def zivildatum(feld: dict) -> str | None:
    """{'year':2026,'month':9,'day':17} -> '2026-09-17'"""
    if not isinstance(feld, dict):
        return None
    d = feld.get("date", feld)
    try:
        return f"{int(d['year']):04d}-{int(d['month']):02d}-{int(d['day']):02d}"
    except (KeyError, TypeError, ValueError):
        return None


def tagesliste(von: date, bis: date) -> list[str]:
    return [(von + timedelta(days=i)).isoformat() for i in range((bis - von).days + 1)]


def feldname(typ: str) -> str:
    """'daily-resting-heart-rate' -> 'dailyRestingHeartRate'"""
    teile = typ.split("-")
    return teile[0] + "".join(w.capitalize() for w in teile[1:])


# ------------------------------------------------------------ Abruf je Typ
def tageswerte(api: HealthAPI, typ: str, von: date, bis: date) -> dict[str, dict]:
    """Datentypen der Form daily-*: ein Punkt je Tag, Filter ueber .date."""
    schluessel = typ.replace("-", "_")
    f = (f'{schluessel}.date >= "{von.isoformat()}" AND '
         f'{schluessel}.date < "{(bis + timedelta(days=1)).isoformat()}"')
    antwort = api.liste(typ, f)
    if not antwort.ok:
        print(f"    {typ}: {antwort.fehler}")
        return {}
    name = feldname(typ)
    raus = {}
    for punkt in antwort.daten["dataPoints"]:
        inhalt = punkt.get(name) or {}
        datum = zivildatum(inhalt.get("date"))
        if datum:
            raus[datum] = inhalt
    return raus


def summen(api: HealthAPI, typ: str, von: date, bis: date) -> dict[str, dict]:
    """Datentypen mit Tagessumme: dailyRollUp."""
    antwort = api.punkte(typ, von, bis, methode="dailyRollUp")
    if not antwort.ok:
        print(f"    {typ}: {antwort.fehler}")
        return {}
    name = feldname(typ)
    raus = {}
    for punkt in antwort.daten["rollupDataPoints"]:
        datum = zivildatum(punkt.get("civilStartTime"))
        if datum:
            raus[datum] = punkt.get(name) or {}
    return raus


def pulsproben(api: HealthAPI, tag: date) -> list[tuple[datetime, int]]:
    """Rohe Pulswerte eines Tages, nach Zeit sortiert."""
    f = (f'heart_rate.sample_time.civil_time >= "{tag.isoformat()}T00:00:00" AND '
         f'heart_rate.sample_time.civil_time < '
         f'"{(tag + timedelta(days=1)).isoformat()}T00:00:00"')
    antwort = api.liste("heart-rate", f)
    if not antwort.ok:
        print(f"    heart-rate {tag}: {antwort.fehler}")
        return []
    proben = []
    for punkt in antwort.daten["dataPoints"]:
        hr = punkt.get("heartRate") or {}
        st = hr.get("sampleTime") or {}
        bpm = zahl(hr.get("beatsPerMinute"))
        if bpm and st.get("physicalTime"):
            proben.append((lokal(st["physicalTime"], versatz(st.get("utcOffset"))), int(bpm)))
    proben.sort(key=lambda p: p[0])
    return proben


def schrittproben(api: HealthAPI, tag: date) -> list[tuple[datetime, int]]:
    """Schritte je Minute. Damit laesst sich erkennen, WANN Bewegung war -
    ohne das zaehlte jeder erhoehte Puls als Stress, auch beim Radfahren."""
    f = (f'steps.interval.civil_start_time >= "{tag.isoformat()}T00:00:00" AND '
         f'steps.interval.civil_start_time < '
         f'"{(tag + timedelta(days=1)).isoformat()}T00:00:00"')
    antwort = api.liste("steps", f)
    if not antwort.ok:
        return []
    raus = []
    for punkt in antwort.daten["dataPoints"]:
        s = punkt.get("steps") or {}
        intervall = s.get("interval") or {}
        anzahl = zahl(s.get("count"), 0)
        if anzahl and intervall.get("startTime"):
            raus.append((lokal(intervall["startTime"],
                               versatz(intervall.get("startUtcOffset"))), int(anzahl)))
    raus.sort(key=lambda p: p[0])
    return raus


def bewegungsfenster(schritte: list[tuple[datetime, int]],
                     ab_schritten: int = 60) -> list[tuple[datetime, datetime]]:
    """Zusammenhaengende Minuten mit zuegiger Bewegung.

    60 Schritte je Minute ist zuegiges Gehen. Benachbarte Minuten werden zu
    einem Fenster verschmolzen, kurze Pausen bis drei Minuten ueberbrueckt.
    """
    fenster = []
    for zeit, anzahl in schritte:
        if anzahl < ab_schritten:
            continue
        ende = zeit + timedelta(minutes=1)
        if fenster and (zeit - fenster[-1][1]).total_seconds() <= 180:
            fenster[-1] = (fenster[-1][0], ende)
        else:
            fenster.append((zeit, ende))
    return fenster


def schlafsitzungen(api: HealthAPI, von: date, bis: date) -> dict[str, dict]:
    """Schlaf laesst sich nicht filtern - alle Sitzungen holen und selbst
    zuordnen. Zugeordnet wird der Tag des AUFWACHENS, wie im Dashboard."""
    antwort = api.liste("sleep", None, seitengroesse=25, max_seiten=40)
    if not antwort.ok:
        print(f"    sleep: {antwort.fehler}")
        return {}
    raus = {}
    for punkt in antwort.daten["dataPoints"]:
        s = punkt.get("sleep") or {}
        intervall = s.get("interval") or {}
        if not intervall.get("endTime"):
            continue
        if not (s.get("metadata") or {}).get("mainSleep", True):
            continue          # Nickerchen zaehlen nicht als Nacht
        ende = lokal(intervall["endTime"], versatz(intervall.get("endUtcOffset")))
        datum = ende.date().isoformat()
        if von.isoformat() <= datum <= bis.isoformat():
            raus[datum] = s
    return raus


def einheiten(api: HealthAPI, von: date, bis: date) -> dict[str, list[dict]]:
    antwort = api.liste("exercise", None, seitengroesse=25, max_seiten=20)
    if not antwort.ok:
        return {}
    raus: dict[str, list] = defaultdict(list)
    for punkt in antwort.daten["dataPoints"]:
        e = punkt.get("exercise") or {}
        intervall = e.get("interval") or {}
        if not intervall.get("startTime"):
            continue
        start = lokal(intervall["startTime"], versatz(intervall.get("startUtcOffset")))
        datum = start.date().isoformat()
        if von.isoformat() <= datum <= bis.isoformat():
            raus[datum].append(e)
    return raus


# ------------------------------------------------------------- Umrechnung
def zonen_aus_puls(proben: list[tuple[datetime, int]], max_hr: float,
                   von: datetime | None = None, bis: datetime | None = None) -> dict[str, int]:
    """Sekunden je Herzfrequenzzone, aus den Rohwerten.

    Warum nicht Googles time-in-heart-rate-zone: Fitbit kennt nur vier Zonen
    (LIGHT, MODERATE, VIGOROUS, PEAK), die App rechnet mit sechs Zonen nach
    Anteil der maximalen Herzfrequenz. Aus vier Zonen liessen sich sechs nur
    schaetzen - aus den Rohwerten ergeben sie sich exakt.

    Jede Probe gilt bis zur naechsten, hoechstens aber fuenf Minuten. Laengere
    Luecken sind Zeiten ohne Messung und zaehlen gar nicht.
    """
    zonen = {z: 0 for z in metrics.ZONE_BOUNDS}
    for i, (zeit, bpm) in enumerate(proben):
        if (von and zeit < von) or (bis and zeit >= bis):
            continue
        if i + 1 < len(proben):
            dauer = min(300, max(0, (proben[i + 1][0] - zeit).total_seconds()))
        else:
            dauer = 60
        anteil = bpm / max_hr
        for name, (unten, oben) in metrics.ZONE_BOUNDS.items():
            if (unten <= anteil < oben) or (oben >= 1.0 and anteil >= unten):
                zonen[name] += int(dauer)
                break
    return zonen


def schlaf_umrechnen(sitzung: dict) -> dict:
    """Aus einer Google-Schlafsitzung den Schlafteil des Tagesdatensatzes."""
    intervall = sitzung.get("interval") or {}
    start = lokal(intervall["startTime"], versatz(intervall.get("startUtcOffset")))
    ende = lokal(intervall["endTime"], versatz(intervall.get("endUtcOffset")))
    z = sitzung.get("summary") or {}

    phasen = {"awake": 0, "light": 0, "deep": 0, "rem": 0}
    wach_bloecke = 0
    for eintrag in z.get("stagesSummary") or []:
        art = str(eintrag.get("type", "")).lower()
        if art in phasen:
            phasen[art] = int(zahl(eintrag.get("minutes"), 0))
        if art == "awake":
            wach_bloecke = int(zahl(eintrag.get("count"), 0))

    im_bett = int(zahl(z.get("minutesInSleepPeriod"), 0))
    geschlafen = int(zahl(z.get("minutesAsleep"), 0))
    wach = int(zahl(z.get("minutesAwake"), max(0, im_bett - geschlafen)))
    # minutesToFallAsleep meldet Google haeufig als 0. Die Fitbit-App zeigt
    # stattdessen die Zeit bis zum FESTEN Schlaf - und die steht in den Phasen:
    # der Abstand vom Zubettgehen bis zum ersten Tief- oder REM-Block.
    einschlafen = zahl(z.get("minutesToFallAsleep"), 0) or None
    for block in sitzung.get("stages") or []:
        if block.get("type") in ("DEEP", "REM"):
            b_von = lokal(block["startTime"], versatz(block.get("startUtcOffset")))
            einschlafen = max(0, int((b_von - start).total_seconds() // 60))
            break
    if not im_bett:
        im_bett = geschlafen + wach

    return {
        "bedtime_min": tagesminute(start),
        "waketime_min": tagesminute(ende),
        "duration_min": geschlafen,
        "time_in_bed_min": im_bett,
        "efficiency": int(round(geschlafen / im_bett * 100)) if im_bett else None,
        "stages": phasen,
        "wake_count": wach_bloecke + len(sitzung.get("shortAwakenings") or []),
        "awake_min": wach,
        "fall_asleep_min": einschlafen,
        "_start": start,
        "_ende": ende,
    }


def hypnogramm(sitzung: dict, proben: list[tuple[datetime, int]]) -> list[dict]:
    """Phasen im Fuenf-Minuten-Raster, dazu der Puls - fuer die Nachtkurve."""
    stufen = {"AWAKE": "awake", "LIGHT": "light", "DEEP": "deep", "REM": "rem"}
    intervall = sitzung.get("interval") or {}
    start = lokal(intervall["startTime"], versatz(intervall.get("startUtcOffset")))
    raus = []
    for block in sitzung.get("stages") or []:
        art = stufen.get(block.get("type"))
        if not art:
            continue
        b_von = lokal(block["startTime"], versatz(block.get("startUtcOffset")))
        b_bis = lokal(block["endTime"], versatz(block.get("endUtcOffset")))
        zeit = b_von
        while zeit < b_bis:
            nah = min(proben, key=lambda p: abs((p[0] - zeit).total_seconds()), default=None)
            eintrag = {"m": int((zeit - start).total_seconds() // 60), "s": art}
            if nah and abs((nah[0] - zeit).total_seconds()) < 600:
                eintrag["hr"] = nah[1]
            raus.append(eintrag)
            zeit += timedelta(minutes=5)
    return raus


def stressverlauf(proben: list[tuple[datetime, int]], rhr: float, hrv: float | None,
                  max_hr: float, aktiv: list[tuple[datetime, datetime]]) -> list[dict]:
    """Stresswert alle fuenf Minuten.

    Wichtige Einschraenkung: Fitbit misst die HFV nur im Schlaf. Tagsueber gibt
    es also keinen aktuellen HFV-Wert. Deshalb wird der Nachtwert als Bezug
    eingesetzt - der HFV-Anteil der Formel faellt damit weg, und der Wert haengt
    am Puls im Verhaeltnis zu Ruhe- und Maximalpuls. Das ist weniger, als die
    Formel koennte, aber es ist gemessen und nicht geraten.
    """
    if not proben or not rhr:
        return []
    bezug = hrv or 50.0
    reihe = []
    zeit = proben[0][0].replace(minute=proben[0][0].minute // 5 * 5, second=0, microsecond=0)
    ende = proben[-1][0]
    i = 0
    while zeit <= ende:
        while i + 1 < len(proben) and proben[i + 1][0] <= zeit:
            i += 1
        nah = proben[i]
        if abs((nah[0] - zeit).total_seconds()) <= 600:
            reihe.append({
                "t": f"{zeit.hour:02d}:{zeit.minute:02d}",
                "v": metrics.stress_value(
                    hr=nah[1], hrv_now=bezug, rhr=rhr, max_hr=max_hr,
                    hrv_baseline=bezug,
                    in_bewegung=any(a <= zeit < b for a, b in aktiv)),
            })
        zeit += timedelta(minutes=5)
    return reihe


def verteilung(reihe: list[dict]) -> dict[str, int]:
    return {
        "niedrig": sum(1 for p in reihe if p["v"] < 1.0) * 5,
        "mittel": sum(1 for p in reihe if 1.0 <= p["v"] < 2.0) * 5,
        "hoch": sum(1 for p in reihe if p["v"] >= 2.0) * 5,
    }


def nacht_stress(reihe_gestern: list[dict], reihe_heute: list[dict],
                 bett_min: int, im_bett_min: int) -> tuple[list[dict] | None, dict | None]:
    """Der Teil des Stressverlaufs, der in die Nacht faellt.

    Eine Nacht beginnt am Vorabend. Ohne den Vortag liesse sich nur der Teil
    nach Mitternacht auswerten - und der waere systematisch zu ruhig.
    """
    if bett_min is None or not im_bett_min:
        return None, None
    nach_minute = {}
    for p in reihe_gestern or []:
        st, mi = p["t"].split(":")
        nach_minute[int(st) * 60 + int(mi)] = p["v"]
    fuer_heute = {}
    for p in reihe_heute or []:
        st, mi = p["t"].split(":")
        fuer_heute[int(st) * 60 + int(mi)] = p["v"]

    start = bett_min if bett_min >= 12 * 60 else bett_min + 1440
    punkte = []
    for k in range(0, im_bett_min, 5):
        absolut = start + k
        quelle = nach_minute if absolut < 1440 else fuer_heute
        wert = quelle.get((absolut % 1440) // 5 * 5)
        if wert is not None:
            punkte.append({"m": k, "v": wert})
    if not punkte:
        return None, None
    werte = [p["v"] for p in punkte]
    return punkte, {
        "niedrig": sum(1 for v in werte if v < 1.0) * 5,
        "mittel": sum(1 for v in werte if 1.0 <= v < 2.0) * 5,
        "hoch": sum(1 for v in werte if v >= 2.0) * 5,
    }


# ------------------------------------------------------------------ Aufbau
def abgleich(tage_zurueck: int = 7, nur_datei: bool = False) -> dict:
    api = HealthAPI()
    bis = date.today()
    von = bis - timedelta(days=tage_zurueck - 1)
    print(f"Abgleich {von} bis {bis}\n")

    print("  Profil und Geraet")
    profil_roh = api.einzeln("users/me/profile").daten or {}
    einstellungen = api.einzeln("users/me/settings").daten or {}
    geraete = (api.einzeln("users/me/pairedDevices").daten or {}).get("pairedDevices") or []
    gewicht = api.liste("weight", None, seitengroesse=1, max_seiten=1)
    groesse = api.liste("height", None, seitengroesse=1, max_seiten=1)

    alter = zahl(profil_roh.get("age"))
    max_hr = 220 - alter if alter else 190
    profil = {
        "alter": alter,
        "max_hr": max_hr,
        "baseline_min_days": metrics.MIN_TAGE_BASIS,
        "zeitzone": einstellungen.get("timeZone"),
        "quelle": "Google Health API",
    }
    if gewicht.ok and gewicht.daten["dataPoints"]:
        g = zahl((gewicht.daten["dataPoints"][0].get("weight") or {}).get("weightGrams"))
        if g:
            profil["gewicht_kg"] = round(g / 1000, 1)
    if groesse.ok and groesse.daten["dataPoints"]:
        h = zahl((groesse.daten["dataPoints"][0].get("height") or {}).get("heightMillimeters"))
        if h:
            profil["groesse_cm"] = round(h / 10)
    if geraete:
        g = geraete[0]
        profil["geraet"] = {"name": g.get("deviceVersion"),
                            "akku": zahl(g.get("batteryLevel")),
                            "letzter_abgleich": g.get("lastSyncTime")}

    print("  Tageswerte")
    hfv_tag = tageswerte(api, "daily-heart-rate-variability", von, bis)
    rhf_tag = tageswerte(api, "daily-resting-heart-rate", von, bis)
    atem_tag = tageswerte(api, "daily-respiratory-rate", von, bis)
    spo2_tag = tageswerte(api, "daily-oxygen-saturation", von, bis)
    temp_tag = tageswerte(api, "daily-sleep-temperature-derivations", von, bis)

    print("  Summen")
    schritte = summen(api, "steps", von, bis)
    strecke = summen(api, "distance", von, bis)
    kalorien = summen(api, "total-calories", von, bis)
    aktivkalorien = summen(api, "active-energy-burned", von, bis)

    print("  Schlaf und Einheiten")
    schlaf_roh = schlafsitzungen(api, von, bis)
    einheiten_roh = einheiten(api, von, bis)

    print("  Puls")
    alle_daten = tagesliste(von, bis)
    puls_tag: dict[str, list] = {}
    schritt_tag: dict[str, list] = {}
    # Der Vortag des ersten Tages wird fuer die Nacht mitgeholt
    for datum in [(von - timedelta(days=1)).isoformat()] + alle_daten:
        puls_tag[datum] = pulsproben(api, date.fromisoformat(datum))
        schritt_tag[datum] = schrittproben(api, date.fromisoformat(datum))

    # ---- Tage zusammensetzen
    tage: list[dict] = []
    verlauf = {"hrv": [], "rhr": [], "resp": [], "spo2": []}
    bett_verlauf, wach_verlauf = [], []
    schlafdefizit = 0.0
    strain_gestern = 0.0
    temp_verlauf: list[float] = []
    stress_gestern: list[dict] = []
    detail_ab = alle_daten[-DETAIL_TAGE] if len(alle_daten) > DETAIL_TAGE else alle_daten[0]

    for datum in alle_daten:
        proben = puls_tag.get(datum) or []
        hrv = zahl((hfv_tag.get(datum) or {}).get("averageHeartRateVariabilityMilliseconds"))
        rhf = zahl((rhf_tag.get(datum) or {}).get("beatsPerMinute"))
        atem = zahl((atem_tag.get(datum) or {}).get("breathsPerMinute"))
        spo2 = zahl((spo2_tag.get(datum) or {}).get("averagePercentage"))

        # Temperatur: Google liefert die Basislinie in den ersten Naechten als
        # "NaN". Sie wird deshalb aus den bisherigen Naechten selbst gebildet -
        # solange es keine gibt, gibt es auch keine Abweichung.
        nacht_temp = zahl((temp_tag.get(datum) or {}).get("nightlyTemperatureCelsius"))
        basis_temp = zahl((temp_tag.get(datum) or {}).get("baselineTemperatureCelsius"))
        if basis_temp is None and len(temp_verlauf) >= 3:
            basis_temp = sum(temp_verlauf[-30:]) / len(temp_verlauf[-30:])
        haut_abw = (round(nacht_temp - basis_temp, 2)
                    if nacht_temp is not None and basis_temp is not None else None)
        if nacht_temp is not None:
            temp_verlauf.append(nacht_temp)

        for schluessel, wert in (("hrv", hrv), ("rhr", rhf), ("resp", atem), ("spo2", spo2)):
            verlauf[schluessel].append(wert)
        basis = metrics.build_baseline({k: v[-30:] for k, v in verlauf.items()})

        # ---- Schlaf
        sitzung = schlaf_roh.get(datum)
        bedarf = metrics.sleep_need_minutes(strain_gestern=strain_gestern,
                                            schlafdefizit_min=schlafdefizit,
                                            nickerchen_min=0)
        if sitzung:
            schlaf = schlaf_umrechnen(sitzung)
            start, ende = schlaf.pop("_start"), schlaf.pop("_ende")
            bett_verlauf.append(schlaf["bedtime_min"])
            wach_verlauf.append(schlaf["waketime_min"])
            schlaf["need"] = bedarf
            # Dauer allein reicht nicht: Tiefschlaf, REM, Wachzeit und
            # Einschlafdauer gehen mit ein (siehe metrics.sleep_performance_detail)
            schlaf["performance"], schlaf["performance_teile"] =                 metrics.sleep_performance_detail(
                    schlaf["duration_min"], bedarf["total"],
                    tief_min=schlaf["stages"]["deep"], rem_min=schlaf["stages"]["rem"],
                    wach_min=schlaf.get("awake_min"),
                    einschlaf_min=schlaf.get("fall_asleep_min"))
            schlaf["consistency"] = metrics.sleep_consistency(bett_verlauf[-14:],
                                                              wach_verlauf[-14:])
            schlaf["restorative"] = metrics.restorative_share(schlaf["stages"])
            schlafdefizit = max(0.0, schlafdefizit
                                + (bedarf["total"] - schlaf["duration_min"]) * 0.5)
            if datum >= detail_ab:
                vortag = (date.fromisoformat(datum) - timedelta(days=1)).isoformat()
                nachtproben = [p for p in (puls_tag.get(vortag, []) + proben)
                               if start <= p[0] <= ende]
                schlaf["hypnogram"] = hypnogramm(sitzung, nachtproben)
        else:
            schlaf = {"bedtime_min": None, "waketime_min": None, "duration_min": None,
                      "time_in_bed_min": None, "efficiency": None, "performance": None,
                      "consistency": None, "restorative": None, "wake_count": None,
                      "stages": {"awake": 0, "light": 0, "deep": 0, "rem": 0},
                      "need": bedarf}

        # ---- Einheiten und Belastung
        aktiv_fenster, akt_liste = [], []
        for e in einheiten_roh.get(datum, []):
            intervall = e.get("interval") or {}
            a_von = lokal(intervall["startTime"], versatz(intervall.get("startUtcOffset")))
            a_bis = lokal(intervall.get("endTime", intervall["startTime"]),
                          versatz(intervall.get("endUtcOffset")))
            aktiv_fenster.append((a_von, a_bis))
            a_zonen = zonen_aus_puls(proben, max_hr, a_von, a_bis)
            im_fenster = [p[1] for p in proben if a_von <= p[0] < a_bis]
            akt_liste.append({
                "name": e.get("activityName") or e.get("exerciseType") or "Einheit",
                "start_min": tagesminute(a_von),
                "duration_sec": int((a_bis - a_von).total_seconds()),
                "strain": metrics.strain_from_zones(a_zonen),
                "zones_sec": a_zonen,
                "avg_hr": int(sum(im_fenster) / len(im_fenster)) if im_fenster else None,
                "max_hr": max(im_fenster) if im_fenster else None,
                "calories": zahl((e.get("energyBurned") or {}).get("kcal")),
            })

        # Bewegung: erfasste Einheiten UND alles, was nach zuegigem Gehen
        # aussieht. Sonst zaehlte ein Spaziergang als Stress.
        aktiv_fenster += bewegungsfenster(schritt_tag.get(datum) or [])

        zonen = zonen_aus_puls(proben, max_hr)
        strain = metrics.strain_from_zones(zonen)
        kcal = (zahl((kalorien.get(datum) or {}).get("kcalSum"))
                or zahl((aktivkalorien.get(datum) or {}).get("kcalSum")))

        # ---- Stress
        reihe = stressverlauf(proben, rhf or 60, hrv, max_hr, aktiv_fenster)
        werte = [p["v"] for p in reihe]
        stress = {
            "avg": round(sum(werte) / len(werte), 1) if werte else None,
            "min": min(werte) if werte else None,
            "max": max(werte) if werte else None,
            "verteilung": verteilung(reihe),
        }
        nacht_punkte, nacht_vert = nacht_stress(stress_gestern, reihe,
                                                schlaf.get("bedtime_min"),
                                                schlaf.get("time_in_bed_min") or 0)
        if nacht_vert:
            schlaf["stress"] = nacht_vert
            if datum >= detail_ab:
                schlaf["stress_reihe"] = nacht_punkte
        if datum >= detail_ab and reihe:
            stress["series"] = reihe
            stress["einheiten"] = [{"name": a["name"], "von": a["start_min"],
                                    "bis": a["start_min"] + a["duration_sec"] // 60}
                                   for a in akt_liste]
            if schlaf.get("waketime_min") is not None and schlaf["waketime_min"] < 12 * 60:
                stress["nacht"] = [0, schlaf["waketime_min"]]

        # ---- Erholung
        erholung, beitraege = metrics.recovery_score(
            hrv=hrv, rhr=rhf, resp=atem, spo2=spo2, skin_temp_dev=haut_abw,
            sleep_performance=schlaf.get("performance"), base=basis)

        tage.append({
            "date": datum,
            "weekday": date.fromisoformat(datum).weekday(),
            "gap": not proben and not sitzung,
            "recovery": {
                "score": erholung,
                "zone": metrics.recovery_zone(erholung) if erholung is not None else None,
                "baseline_days": basis.tage,
                "calibrating": not basis.ausreichend,
                "hrv": hrv, "rhr": int(rhf) if rhf else None, "resp": atem, "spo2": spo2,
                "skin_temp_dev": haut_abw,
                "drivers": {k: round(v, 2) for k, v in beitraege.items()},
            },
            "sleep": schlaf,
            "strain": {"score": strain, "label": metrics.strain_label(strain),
                       "calories": int(kcal) if kcal else None, "zones_sec": zonen},
            "steps": int(zahl((schritte.get(datum) or {}).get("countSum"), 0)),
            "distance_km": round(zahl((strecke.get(datum) or {}).get("millimetersSum"), 0)
                                 / 1_000_000, 2),
            "stress": stress,
            "activities": akt_liste,
            "journal": {},
        })
        strain_gestern = strain
        stress_gestern = reihe

    datensatz = {
        "app": "Claude Health",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "is_demo": False,
        "profile": profil,
        "journal_impact": [],
        "journal_labels": {},
        "days": tage,
    }

    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    DATA_JSON.write_text(json.dumps(datensatz, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  health/data.json geschrieben ({len(tage)} Tage)")

    if not nur_datei:
        import speicher
        speicher.profil_schreiben(
            {"profil": profil,
             "letzter_abgleich": datetime.now().isoformat(timespec="seconds")})
        anzahl = speicher.tage_schreiben({t["date"]: t for t in tage})
        print(f"  Firestore: {anzahl} Tage geschrieben")

    return datensatz


def main() -> int:
    tage = 7
    nur_datei = "--nurdatei" in sys.argv
    for arg in sys.argv[1:]:
        if arg.isdigit():
            tage = max(1, min(180, int(arg)))
    datensatz = abgleich(tage, nur_datei)

    print("\n" + "=" * 64)
    for tag in datensatz["days"][-7:]:
        r, s = tag["recovery"], tag["sleep"]
        print(f"  {tag['date']}  Erholung {str(r['score'] if r['score'] is not None else '–'):>4}"
              f"  Schlaf {str(s['performance'] if s['performance'] is not None else '–'):>4}"
              f"  Belastung {tag['strain']['score']:>5}"
              f"  Schritte {tag['steps']:>6}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
