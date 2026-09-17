"""Kleiner Client fuer die Google Health API.

Nur lesend. Kuemmert sich um Anmeldung, Wiederholungen, Seitenweiser und die
Zeitfenster-Grenzen - alles Dinge, die unabhaengig davon feststehen, welche
Feldnamen die Antworten am Ende tragen.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta

import requests
from google.auth.transport.requests import AuthorizedSession

from auth import get_credentials
from config import API_BASE

# Von Google dokumentierte Obergrenzen fuer eine einzelne Abfrage.
# Wer mehr will, muss stueckeln - sonst kommt eine Fehlermeldung statt Daten.
MAX_TAGE_STANDARD = 90
MAX_TAGE_ENG = 14
ENGE_TYPEN = {
    "heart-rate",
    "total-calories",
    "active-zone-minutes",
    "calories-in-heart-rate-zone",
}

TIMEOUT = 30
VERSUCHE = 4


def max_fenster(datentyp: str) -> int:
    return MAX_TAGE_ENG if datentyp in ENGE_TYPEN else MAX_TAGE_STANDARD


def zeitraeume(von: date, bis: date, max_tage: int) -> list[tuple[date, date]]:
    """Zerlegt einen Zeitraum in Stuecke, die die API noch annimmt."""
    stuecke: list[tuple[date, date]] = []
    start = von
    while start <= bis:
        ende = min(bis, start + timedelta(days=max_tage - 1))
        stuecke.append((start, ende))
        start = ende + timedelta(days=1)
    return stuecke


def civil(tag: date, stunde: int = 0) -> dict:
    """CivilDateTime, wie die API es fuer Zeitraeume erwartet.

    Am echten Konto bestaetigt (17.09.2026): Datum und Uhrzeit liegen in
    getrennten Unterobjekten. Die flache Form year/month/day/hours lehnt die
    API mit "Unknown name year at range.start" ab.
    """
    return {
        "date": {"year": tag.year, "month": tag.month, "day": tag.day},
        "time": {"hours": stunde, "minutes": 0},
    }


@dataclass
class Antwort:
    ok: bool
    daten: dict | None
    fehler: str | None
    status: int | None = None


class HealthAPI:
    """Spricht mit health.googleapis.com. Wirft nie - meldet zurueck.

    Der Aufrufer soll je Datentyp einzeln entscheiden koennen, ob ein
    fehlender Wert das Ende bedeutet (tut er nie) oder einfach eine Luecke.
    """

    def __init__(self) -> None:
        self.session = AuthorizedSession(get_credentials())

    def _post(self, pfad: str, koerper: dict) -> Antwort:
        url = f"{API_BASE}/{pfad}"
        for versuch in range(VERSUCHE):
            try:
                antwort = self.session.post(url, json=koerper, timeout=TIMEOUT)
            except requests.RequestException as exc:
                if versuch == VERSUCHE - 1:
                    return Antwort(False, None, f"Netzwerkfehler: {exc}")
                time.sleep(2**versuch)
                continue

            if antwort.status_code == 200:
                try:
                    return Antwort(True, antwort.json(), None, 200)
                except ValueError:
                    return Antwort(False, None, "Antwort war kein JSON", 200)

            # Zu viele Anfragen oder Serverproblem: warten und erneut versuchen
            if antwort.status_code in (429, 500, 502, 503, 504) and versuch < VERSUCHE - 1:
                warte = float(antwort.headers.get("Retry-After", 2**versuch))
                time.sleep(min(warte, 30))
                continue

            # Fehlertext kuerzen - er kann sehr lang werden
            text = (antwort.text or "")[:300].replace("\n", " ")
            return Antwort(False, None, f"HTTP {antwort.status_code}: {text}",
                           antwort.status_code)
        return Antwort(False, None, "unbekannter Fehler")

    def _get(self, pfad: str, parameter: dict | None = None) -> Antwort:
        url = f"{API_BASE}/{pfad}"
        for versuch in range(VERSUCHE):
            try:
                antwort = self.session.get(url, params=parameter or {}, timeout=TIMEOUT)
            except requests.RequestException as exc:
                if versuch == VERSUCHE - 1:
                    return Antwort(False, None, f"Netzwerkfehler: {exc}")
                time.sleep(2**versuch)
                continue
            if antwort.status_code == 200:
                try:
                    return Antwort(True, antwort.json(), None, 200)
                except ValueError:
                    return Antwort(False, None, "Antwort war kein JSON", 200)
            if antwort.status_code in (429, 500, 502, 503, 504) and versuch < VERSUCHE - 1:
                warte = float(antwort.headers.get("Retry-After", 2**versuch))
                time.sleep(min(warte, 30))
                continue
            text = (antwort.text or "")[:300].replace(chr(10), " ")
            return Antwort(False, None, f"HTTP {antwort.status_code}: {text}",
                           antwort.status_code)
        return Antwort(False, None, "unbekannter Fehler")

    def einzeln(self, pfad: str) -> Antwort:
        """Einzelne Ressource, etwa users/me/profile oder users/me/settings."""
        return self._get(pfad)

    def liste(self, datentyp: str, filter_ausdruck: str | None,
              seitengroesse: int = 1000, max_seiten: int = 50) -> Antwort:
        """GET .../dataPoints mit AIP-160-Filter, ueber alle Seiten.

        Laut Referenz ist list ein GET mit Filter im Query-String - nicht ein
        POST mit Koerper wie dailyRollUp.
        """
        alle: list[dict] = []
        seite = None
        for _ in range(max_seiten):
            parameter: dict = {"pageSize": seitengroesse}
            if filter_ausdruck:
                parameter["filter"] = filter_ausdruck
            if seite:
                parameter["pageToken"] = seite
            antwort = self._get(f"users/me/dataTypes/{datentyp}/dataPoints", parameter)
            if not antwort.ok:
                return antwort
            nutz = antwort.daten or {}
            alle.extend(nutz.get("dataPoints") or [])
            seite = nutz.get("nextPageToken")
            if not seite:
                break
        return Antwort(True, {"dataPoints": alle}, None, 200)

    def punkte(
        self,
        datentyp: str,
        von: date,
        bis: date,
        methode: str = "dailyRollUp",
        seitengroesse: int = 1000,
    ) -> Antwort:
        """Holt alle Datenpunkte eines Typs, ueber Seiten und Zeitstuecke hinweg.

        methode: "dailyRollUp" fuer Tageswerte, "list" fuer Sitzungen
        (Schlaf, Workouts), die keine Tagesaggregation sind.
        """
        alle: list[dict] = []
        schluessel = "rollupDataPoints" if methode == "dailyRollUp" else "dataPoints"

        for stueck_von, stueck_bis in zeitraeume(von, bis, max_fenster(datentyp)):
            seite = None
            while True:
                koerper: dict = {
                    "range": {
                        "start": civil(stueck_von),
                        # Ende ist ausschliesslich, deshalb ein Tag mehr
                        "end": civil(stueck_bis + timedelta(days=1)),
                    },
                }
                if methode == "dailyRollUp":
                    # Ohne pageSize: bei total-calories und heart-rate lehnt die
                    # API kleine Werte als "Invalid argument" ab
                    koerper["windowSizeDays"] = 1
                else:
                    koerper["pageSize"] = seitengroesse
                if seite:
                    koerper["pageToken"] = seite

                pfad = f"users/me/dataTypes/{datentyp}/dataPoints:{methode}"
                antwort = self._post(pfad, koerper)
                if not antwort.ok:
                    return Antwort(False, None,
                                   f"{datentyp} {stueck_von}–{stueck_bis}: {antwort.fehler}",
                                   antwort.status)

                nutz = antwort.daten or {}
                alle.extend(nutz.get(schluessel) or [])
                seite = nutz.get("nextPageToken")
                if not seite:
                    break

        return Antwort(True, {schluessel: alle}, None, 200)
