"""Abgeleitete Werte, die das Fitbit nicht selbst liefert.

Fitbit misst HRV, Ruhepuls, Atemfrequenz, SpO2, Hauttemperatur, Schlafphasen
und Herzfrequenzzonen. Es liefert aber keinen Erholungswert, keine
Belastungszahl und keinen Stresswert. Diese drei rechnen wir hier aus den
gemessenen Groessen - nach der Logik, die in docs/whoop-referenz.md unter
Abschnitt 3 aus den Infotexten festgehalten ist.

Wichtig: Alles hier ist eine Schaetzung auf Basis echter Messwerte, keine
Messung. Das Dashboard kennzeichnet diese Werte entsprechend.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Herzfrequenzzonen als Anteil der maximalen Herzfrequenz
ZONE_BOUNDS = {
    "z0": (0.00, 0.50),
    "z1": (0.50, 0.60),
    "z2": (0.60, 0.70),
    "z3": (0.70, 0.80),
    "z4": (0.80, 0.90),
    "z5": (0.90, 1.00),
}

# Gewicht je Minute in der jeweiligen Zone. Ueberproportional nach oben,
# weil hohe Intensitaet den Koerper deutlich staerker beansprucht.
ZONE_WEIGHTS = {"z0": 0.0, "z1": 1.0, "z2": 1.9, "z3": 3.4, "z4": 6.0, "z5": 9.0}

GESUNDES_MINIMUM_MIN = 441  # 7 h 21 min


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# So viele Tage mit Messwerten braucht es, bevor von einem persoenlichen
# Normalbereich ueberhaupt die Rede sein kann. Aus weniger laesst sich keine
# Streuung schaetzen - und ohne Streuung ist jede Aussage "ueber" oder "unter
# deinem Normalwert" eine Behauptung ohne Grundlage.
MIN_TAGE_BASIS = 7


@dataclass
class Baseline:
    """Persoenlicher Normalbereich, gleitend ueber die letzten 30 Tage."""

    hrv_mean: float
    hrv_sd: float
    rhr_mean: float
    rhr_sd: float
    resp_mean: float
    resp_sd: float
    spo2_mean: float
    spo2_sd: float
    tage: int = 0

    @property
    def ausreichend(self) -> bool:
        return self.tage >= MIN_TAGE_BASIS


def recovery_score(
    *,
    hrv: float | None,
    rhr: float | None,
    resp: float | None,
    spo2: float | None,
    skin_temp_dev: float | None,
    sleep_performance: float | None,
    base: Baseline,
) -> tuple[int, dict]:
    """Erholungswert 0-100 aus den naechtlichen Vitalwerten.

    Die HRV ist mit Abstand der groesste Faktor - so beschreibt es auch der
    Infotext. Fehlende Einzelwerte werden uebersprungen und ihr Gewicht auf
    die vorhandenen verteilt, statt sie als Null zu werten.

    Rueckgabe: (Wert, Beitraege je Einzelgroesse als z-Wert)
    Wert ist None, solange kein persoenlicher Normalbereich vorliegt.
    """
    # Ohne belastbaren Normalbereich gibt es keinen Erholungswert. Frueher
    # sprang hier ein fest verdrahteter Ersatz ein (50 +/- 8 ms) - das ergab
    # am ersten Tag eine Zahl, die wie eine Messung aussah, aber gegen einen
    # erfundenen Vergleichswert gerechnet war.
    if not base.ausreichend:
        return None, {}

    beitraege: dict[str, float] = {}
    gewichte: dict[str, float] = {}

    if hrv is not None and base.hrv_sd > 0:
        # Hoehere HRV ist besser
        beitraege["hrv"] = _clamp((hrv - base.hrv_mean) / base.hrv_sd, -3, 3)
        gewichte["hrv"] = 0.45

    if rhr is not None and base.rhr_sd > 0:
        # Niedrigerer Ruhepuls ist besser -> Vorzeichen drehen
        beitraege["rhr"] = _clamp(-(rhr - base.rhr_mean) / base.rhr_sd, -3, 3)
        gewichte["rhr"] = 0.20

    if resp is not None and base.resp_sd > 0:
        # Jede Abweichung nach oben oder unten ist ungeunstig
        beitraege["resp"] = _clamp(-abs(resp - base.resp_mean) / base.resp_sd, -3, 0)
        gewichte["resp"] = 0.10

    if spo2 is not None and base.spo2_sd > 0:
        # Nur der Abfall zaehlt; ueberdurchschnittlich hoch ist kein Bonus
        beitraege["spo2"] = _clamp(min(0.0, (spo2 - base.spo2_mean) / base.spo2_sd), -3, 0)
        gewichte["spo2"] = 0.05

    if skin_temp_dev is not None:
        # Abweichung vom eigenen Normalwert in Grad Celsius
        beitraege["temp"] = _clamp(-abs(skin_temp_dev) / 0.5, -3, 0)
        gewichte["temp"] = 0.05

    if sleep_performance is not None:
        beitraege["sleep"] = _clamp((sleep_performance - 85.0) / 15.0, -3, 2)
        gewichte["sleep"] = 0.15

    if not gewichte:
        return None, {}

    # Fehlende Faktoren: Gewichte auf die vorhandenen normieren
    summe = sum(gewichte.values())
    kombiniert = sum(beitraege[k] * (gewichte[k] / summe) for k in gewichte)

    # Logistische Kurve, leicht nach oben verschoben - ein durchschnittlicher
    # Tag soll bei etwa 60 % landen, nicht bei 50 %.
    score = 100.0 / (1.0 + math.exp(-(1.9 * kombiniert + 0.45)))
    return int(round(_clamp(score, 1, 99))), beitraege


def recovery_zone(score: int) -> str:
    """gruen = belastbar, gelb = halten, rot = Ruhe."""
    if score >= 67:
        return "gruen"
    if score >= 34:
        return "gelb"
    return "rot"


def strain_from_zones(zones_sec: dict[str, float]) -> float:
    """Belastung 0-21 aus der Zeit in den Herzfrequenzzonen.

    Die Skala ist bewusst nicht linear: nach oben hin muss immer mehr
    Aufwand fuer den naechsten Punkt aufgebracht werden.
    """
    impuls = sum(
        (zones_sec.get(zone, 0) / 60.0) * gewicht for zone, gewicht in ZONE_WEIGHTS.items()
    )
    strain = 21.0 * (1.0 - math.exp(-impuls / 220.0))
    return round(_clamp(strain, 0.0, 21.0), 1)


def strain_label(strain: float) -> str:
    if strain >= 18.0:
        return "Alles gegeben"
    if strain >= 14.0:
        return "Anstrengend"
    if strain >= 10.0:
        return "Moderat"
    if strain >= 6.0:
        return "Leicht"
    return "Erholsam"


def sleep_need_minutes(
    *,
    strain_gestern: float,
    schlafdefizit_min: float,
    nickerchen_min: float,
) -> dict[str, int]:
    """Schlafbedarf nach der Formel aus dem Infotext.

    Bedarf = Gesundes Minimum + Belastung + Defizit - Nickerchen
    """
    belastung = round((strain_gestern / 21.0) ** 2 * 45.0)
    defizit = round(_clamp(schlafdefizit_min * 0.35, 0, 90))
    nickerchen = round(nickerchen_min * 0.8)
    bedarf = GESUNDES_MINIMUM_MIN + belastung + defizit - nickerchen
    return {
        "baseline": GESUNDES_MINIMUM_MIN,
        "strain": int(belastung),
        "debt": int(defizit),
        "naps": int(nickerchen),
        "total": int(max(300, bedarf)),
    }


def sleep_performance(duration_min: float, need_min: float) -> int:
    if need_min <= 0:
        return 0
    return int(round(_clamp(duration_min / need_min * 100.0, 0, 100)))


def stress_value(
    *,
    hr: float,
    hrv_now: float,
    rhr: float,
    max_hr: float,
    hrv_baseline: float,
    in_bewegung: bool,
) -> float:
    """Stresswert 0,0-3,0 aus aktueller Herzfrequenz und HRV.

    Verglichen wird gegen den persoenlichen Normalbereich. Bewegung wird
    beruecksichtigt: waehrend einer Aktivitaet ist ein hoher Puls erwartbar
    und wird nicht als Stress gewertet.
    """
    if max_hr <= rhr:
        return 0.0

    hf_anteil = _clamp((hr - rhr) / (max_hr - rhr), 0.0, 1.0)
    hrv_daempfung = _clamp((hrv_baseline - hrv_now) / max(hrv_baseline, 1.0), 0.0, 1.0)

    # Skalierung so gewaehlt, dass ein normaler Tagespuls (ca. 75 bpm bei
    # Ruhepuls 50) etwa 1,3 ergibt - also mittleres Niveau. Eine lineare
    # Abbildung auf die volle Herzfrequenzspanne wuerde den Alltag dauerhaft
    # bei 0,3 einfrieren und die Skala unbrauchbar machen.
    roh = 2.6 * hf_anteil + 0.9 * hrv_daempfung
    if in_bewegung:
        # Sport ist bekannter und positiver Stressfaktor - stark abgewertet
        roh *= 0.25

    return round(_clamp(roh * 2.4, 0.0, 3.0), 1)


def stress_label(value: float) -> str:
    if value >= 2.0:
        return "HOCH"
    if value >= 1.0:
        return "MITTEL"
    return "NIEDRIG"


def sleep_consistency(bedtimes: list[int], waketimes: list[int]) -> int | None:
    """Schlafkonsistenz 0-100 aus der Streuung von Zubettgeh- und Aufwachzeit.

    Abgeleitet, nicht gemessen: je gleichmaessiger die Zeiten, desto hoeher.
    Gerechnet wird ueber Winkel, damit 23:50 und 00:10 als benachbart gelten
    und nicht als 23 Stunden auseinander.
    """
    if len(bedtimes) < 4 or len(waketimes) < 4:
        return None

    def streuung(minuten: list[int]) -> float:
        winkel = [m / (24 * 60) * 2 * math.pi for m in minuten]
        x = sum(math.cos(a) for a in winkel) / len(winkel)
        y = sum(math.sin(a) for a in winkel) / len(winkel)
        laenge = math.sqrt(x * x + y * y)
        if laenge >= 0.9999:
            return 0.0
        # Kreisfoermige Standardabweichung, zurueck in Minuten
        return math.sqrt(-2 * math.log(laenge)) / (2 * math.pi) * 24 * 60

    mittel = (streuung(bedtimes) + streuung(waketimes)) / 2
    # 0 min Streuung -> 100, 60 min -> ~70, 120 min -> ~40
    return int(round(_clamp(100 - mittel * 0.5, 0, 100)))


def restorative_share(stages: dict[str, int]) -> int | None:
    """Anteil erholsamer Schlafphasen (Tief + REM) an der Schlafzeit.

    Direkt aus den gemessenen Phasen, keine Schaetzung.
    """
    schlaf = stages.get("light", 0) + stages.get("deep", 0) + stages.get("rem", 0)
    if schlaf <= 0:
        return None
    return int(round((stages.get("deep", 0) + stages.get("rem", 0)) / schlaf * 100))


def behaviour_impact(
    tage: list[dict], schluessel: str, mindestens: int = 4
) -> int | None:
    """Wirkung eines Verhaltens auf den Erholungswert, in Prozent.

    Vergleicht Tage mit und ohne das Verhalten. Gibt None zurueck, wenn zu
    wenige Tage in einer der beiden Gruppen liegen - lieber keine Aussage als
    eine aus drei Datenpunkten.
    """
    mit: list[float] = []
    ohne: list[float] = []
    for t in tage:
        wert = t.get("recovery", {}).get("score")
        if wert is None:
            continue
        (mit if t.get("journal", {}).get(schluessel) else ohne).append(wert)

    if len(mit) < mindestens or len(ohne) < mindestens:
        return None

    schnitt_ohne = sum(ohne) / len(ohne)
    if schnitt_ohne <= 0:
        return None
    schnitt_mit = sum(mit) / len(mit)
    return int(round((schnitt_mit - schnitt_ohne) / schnitt_ohne * 100))


def in_normalbereich(wert: float | None, mittel: float | None, sd: float | None) -> bool | None:
    """Liegt ein Wert innerhalb einer Standardabweichung um den Normalwert?

    None heisst: laesst sich nicht beurteilen. Das ist etwas anderes als
    'im Normalbereich' und wird im Dashboard auch anders dargestellt.
    """
    if wert is None or mittel is None or sd is None or sd <= 0:
        return None
    return abs(wert - mittel) <= sd


# ---------------------------------------------------------------------------
# Biologisches Alter
# ---------------------------------------------------------------------------
# Grundlage ist der gut belegte Zusammenhang zwischen naechtlicher HRV (RMSSD)
# und Lebensalter: die HRV faellt ueber die Lebensspanne annaehernd
# exponentiell. Zwei Stuetzpunkte aus veroeffentlichten Referenzbereichen:
#   25 Jahre -> etwa 55 ms      65 Jahre -> etwa 24 ms
# Daraus ergibt sich die Zerfallskonstante unten.
#
# WICHTIG - was das ist und was nicht:
# Das hier ist eine Schaetzung aus vier Groessen, die eine Uhr am Handgelenk
# messen kann. Ein biologisches Alter im medizinischen Sinn wird aus Dutzenden
# Markern bestimmt (Entzuendungswerte, Methylierung, Organfunktion). Diese
# Zahl ersetzt das nicht und ist keine Diagnose. Sie taugt dafuer, die eigene
# Entwicklung ueber Monate zu verfolgen - nicht fuer einen Vergleich mit
# anderen Menschen.
HRV_REF_ALTER = 25.0
HRV_REF_WERT = 55.0
HRV_ZERFALL = 0.0207          # je Lebensjahr
MIN_TAGE_BIOALTER = 14        # darunter keine Aussage


def erwartete_hrv(alter: float) -> float:
    """Typische naechtliche RMSSD fuer ein bestimmtes Lebensalter."""
    return HRV_REF_WERT * math.exp(-HRV_ZERFALL * (alter - HRV_REF_ALTER))


def biological_age(
    *,
    alter: float,
    hrv: float | None,
    rhr: float | None,
    schlaf_konsistenz: float | None,
    schlaf_dauer_min: float | None,
) -> tuple[float | None, dict]:
    """Biologisches Alter in Jahren, plus die Beitraege der Einzelgroessen.

    Gerechnet wird nicht "Alter aus Messwerten", sondern ein Abstand zum
    Lebensalter: Wie stehen deine Werte im Vergleich zu dem, was fuer dein
    Alter typisch waere? Das ist ehrlicher, weil die Uhr nur wenige Marker
    kennt - und es verhindert, dass eine gute HRV allein ein Alter von 19
    Jahren behauptet.

    Rueckgabe: (biologisches Alter, Beitraege in Jahren je Groesse)
    """
    if hrv is None or alter is None or alter <= 0:
        return None, {}

    beitraege: dict[str, float] = {}

    # HRV: groesster Faktor. Abweichung vom Erwartungswert, umgerechnet in Jahre.
    erwartet = erwartete_hrv(alter)
    if hrv > 0 and erwartet > 0:
        jahre = math.log(erwartet / hrv) / HRV_ZERFALL
        beitraege["hrv"] = _clamp(jahre, -10.0, 10.0)

    # Ruhepuls: ueber dem Bevoelkerungsschnitt von etwa 58 bpm kostet Jahre.
    if rhr is not None:
        beitraege["rhr"] = _clamp((rhr - 58.0) * 0.25, -5.0, 5.0)

    # Schlafkonsistenz: regelmaessige Zeiten wirken schuetzend.
    if schlaf_konsistenz is not None:
        beitraege["konsistenz"] = _clamp((78.0 - schlaf_konsistenz) * 0.06, -3.0, 3.0)

    # Schlafdauer: Abweichung von etwa 7,5 h in beide Richtungen ungueenstig.
    if schlaf_dauer_min is not None:
        abweichung = abs(schlaf_dauer_min - 450.0) / 60.0
        beitraege["dauer"] = _clamp(max(0.0, abweichung - 0.5) * 1.4, 0.0, 3.0)

    gewichte = {"hrv": 0.55, "rhr": 0.25, "konsistenz": 0.12, "dauer": 0.08}
    vorhanden = {k: g for k, g in gewichte.items() if k in beitraege}
    if not vorhanden:
        return None, {}
    summe = sum(vorhanden.values())
    versatz = sum(beitraege[k] * (g / summe) for k, g in vorhanden.items())

    # Nach oben und unten begrenzen: eine Uhr kann nicht belegen, dass jemand
    # zwoelf Jahre juenger ist als sein Ausweis sagt.
    versatz = _clamp(versatz, -10.0, 12.0)
    bio = _clamp(alter + versatz, max(16.0, alter - 10.0), alter + 12.0)
    return round(bio, 1), {k: round(v, 2) for k, v in beitraege.items()}


def pace_of_aging(punkte: list[tuple[int, float]]) -> float | None:
    """Wie schnell das biologische Alter gegenueber dem Kalender laeuft.

    punkte: (Tagesindex, biologisches Alter). Rueckgabe 1,0 = im Gleichschritt,
    darunter = das biologische Alter verbessert sich, darueber = es laeuft
    davon. Ohne genug Punkte: None.
    """
    sauber = [(x, y) for x, y in punkte if y is not None]
    if len(sauber) < 4:
        return None
    n = len(sauber)
    mx = sum(x for x, _ in sauber) / n
    my = sum(y for _, y in sauber) / n
    oben = sum((x - mx) * (y - my) for x, y in sauber)
    unten = sum((x - mx) ** 2 for x, _ in sauber)
    if unten == 0:
        return None
    # Steigung in Jahren je Tag -> Jahre je Kalenderjahr
    return round(_clamp(oben / unten * 365.0, -1.0, 3.0), 2)


def build_baseline(values: dict[str, list[float]]) -> Baseline:
    """Normalbereich aus den vorhandenen Werten der letzten Tage.

    Das Feld `tage` sagt, auf wie vielen Tagen der Normalbereich beruht.
    Liegt es unter MIN_TAGE_BASIS, ist der Normalbereich nicht belastbar -
    `recovery_score` verweigert dann die Aussage, statt eine Zahl gegen einen
    Ersatzwert zu rechnen.
    """

    def mean_sd(key: str, min_sd: float) -> tuple[float, float, int]:
        reihe = [v for v in values.get(key, []) if v is not None]
        if not reihe:
            return 0.0, 0.0, 0
        m = sum(reihe) / len(reihe)
        varianz = sum((v - m) ** 2 for v in reihe) / len(reihe)
        # Untergrenze fuer die Streuung: sonst wird ein zufaellig ruhiger
        # Zeitraum zum Massstab, und jede normale Schwankung schlaegt aus.
        return m, max(math.sqrt(varianz), min_sd), len(reihe)

    hrv_m, hrv_sd, n_hrv = mean_sd("hrv", 2.0)
    rhr_m, rhr_sd, _ = mean_sd("rhr", 0.8)
    resp_m, resp_sd, _ = mean_sd("resp", 0.15)
    spo2_m, spo2_sd, _ = mean_sd("spo2", 0.25)
    return Baseline(
        hrv_m, hrv_sd, rhr_m, rhr_sd, resp_m, resp_sd, spo2_m, spo2_sd, tage=n_hrv
    )
