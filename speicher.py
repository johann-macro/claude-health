"""Schreibt und liest die Daten in Firestore.

Warum eine eigene Datei: Der Abgleich soll nichts davon wissen, WO die Daten
landen, und die Auswertung nichts davon, WOHER sie kommen. Alles, was mit der
Datenbank zu tun hat, steht deshalb hier.

Zugang: lokal ueber .secrets/firebase-dienstkonto.json, in der automatischen
Ausfuehrung ueber die Umgebungsvariable FIREBASE_DIENSTKONTO (der komplette
Inhalt derselben Datei als geschuetztes Geheimnis). Der Schluessel wird nie
ausgegeben und nie protokolliert.

Aufbau:
    nutzer/<uid>                     Profil, Einstellungen, Stand des Abgleichs
    nutzer/<uid>/tage/<JJJJ-MM-TT>   ein Dokument je Tag
    nutzer/<uid>/logbuch/<JJJJ-MM-TT>
    nutzer/<uid>/plan/<name>
"""
from __future__ import annotations

import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_KEY_FILE, NUTZER_UID

_db = None


def _zugang() -> credentials.Base:
    """Dienstkonto aus der Umgebung oder aus der lokalen Datei."""
    roh = os.environ.get("FIREBASE_DIENSTKONTO")
    if roh:
        return credentials.Certificate(json.loads(roh))
    if FIREBASE_KEY_FILE.exists():
        return credentials.Certificate(str(FIREBASE_KEY_FILE))
    raise SystemExit(
        "Kein Firebase-Zugang gefunden.\n"
        f"Erwartet: {FIREBASE_KEY_FILE}\n"
        "oder die Umgebungsvariable FIREBASE_DIENSTKONTO."
    )


def db():
    """Verbindung zur Datenbank, einmal aufgebaut und dann wiederverwendet."""
    global _db
    if _db is None:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(_zugang())
        _db = firestore.client()
    return _db


def nutzer(uid: str | None = None):
    return db().collection("nutzer").document(uid or NUTZER_UID)


# ---------------------------------------------------------------- schreiben
def tag_schreiben(datum: str, daten: dict, uid: str | None = None) -> None:
    """Einen Tag ablegen. merge=True, damit spaetere Teillieferungen den Tag
    ergaenzen statt ihn zu ueberschreiben - Fitbit liefert manches erst
    Stunden spaeter nach."""
    nutzer(uid).collection("tage").document(datum).set(daten, merge=True)


def tage_schreiben(tage: dict[str, dict], uid: str | None = None) -> int:
    """Mehrere Tage in einem Rutsch. Firestore erlaubt 500 Schreibvorgaenge
    je Stapel; bei 90 Tagen reicht einer, die Grenze wird trotzdem beachtet."""
    geschrieben = 0
    posten = list(tage.items())
    for anfang in range(0, len(posten), 400):
        stapel = db().batch()
        for datum, daten in posten[anfang:anfang + 400]:
            stapel.set(nutzer(uid).collection("tage").document(datum), daten, merge=True)
            geschrieben += 1
        stapel.commit()
    return geschrieben


def profil_schreiben(daten: dict, uid: str | None = None) -> None:
    nutzer(uid).set(daten, merge=True)


# ------------------------------------------------------------------- lesen
def tage_lesen(ab: str | None = None, uid: str | None = None) -> list[dict]:
    """Alle Tage aufsteigend nach Datum, optional erst ab einem Datum."""
    abfrage = nutzer(uid).collection("tage")
    if ab:
        abfrage = abfrage.where(filter=firestore.FieldFilter("date", ">=", ab))
    return [d.to_dict() for d in abfrage.order_by("date").stream()]


def profil_lesen(uid: str | None = None) -> dict:
    schnapp = nutzer(uid).get()
    return schnapp.to_dict() or {} if schnapp.exists else {}


def pruefen() -> str:
    """Kurzer Selbsttest: schreiben, lesen, aufraeumen."""
    ref = nutzer().collection("_test").document("verbindung")
    ref.set({"zeit": firestore.SERVER_TIMESTAMP, "hinweis": "Selbsttest"})
    gelesen = ref.get().to_dict()
    ref.delete()
    return "ok" if gelesen else "geschrieben, aber nichts gelesen"


if __name__ == "__main__":
    print("Projekt :", __import__("config").FIREBASE_PROJEKT)
    print("Nutzer  :", NUTZER_UID)
    print("Test    :", pruefen())
