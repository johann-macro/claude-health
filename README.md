# Claude Health

Persönliches Trainings- und Erholungs-Dashboard im Stil der WHOOP-App,
gespeist aus Google-Fitbit-Daten. Alles bleibt lokal auf diesem Rechner.

## Stand

| Teil | Status |
|---|---|
| Projektordner, virtuelle Umgebung, Abhängigkeiten | fertig |
| Rechenlogik (Erholung, Belastung, Stress, Schlafbedarf) | fertig |
| Demo-Datensatz, 90 Tage | fertig |
| Dashboard (8 Ansichten, offline, eine Datei) | fertig |
| Aktivitäts-Auswertung + Nachtragen | fertig |
| Wischen zwischen Rubriken (Handy) | fertig |
| Lesbare Markdown-Notizen (`notes.py`) | fertig |
| Automatischer Lauf, täglich 06:45 | fertig, scharf getestet |
| Google-Anmeldung (`auth.py`) | geschrieben, **noch nicht ausgeführt** |
| API-Client + Sync (`api.py`, `sync.py`) | geschrieben, **ungetestet** – braucht ein Konto |
| Feldzuordnung der API-Antworten | **offen** – `probe.py` klärt das in Minuten |

## Der tägliche Lauf

Eingerichtet in der Windows-Aufgabenplanung als **„Claude Health"**, täglich
06:45. Aufgerufen wird direkt `pythonw.exe` der virtuellen Umgebung mit
`taeglich.py` — keine Batchdatei dazwischen, das ist eine bekannte
Fehlerquelle.

`taeglich.py` entscheidet selbst:

- Anmeldung vorhanden → `sync.py` holt echte Daten (14 Tage, holt Verpasstes nach)
- noch keine Anmeldung → `demo_data.py` hält das Dashboard am Leben

Es muss also nichts umgestellt werden, wenn die Uhr da ist.

Einstellungen: `StartWhenAvailable` (verpasste Läufe werden beim nächsten
Start nachgeholt), Zeitlimit 30 Minuten, kein Aufwecken aus dem Ruhezustand.
Der PC muss nicht durchlaufen — die Daten liegen bei Google und gehen nicht
verloren.

Protokoll: `logs/taeglich.log`

    # Lauf von Hand auslösen
    .venv\Scripts\python.exe taeglich.py

    # Aufgabe wieder entfernen
    Unregister-ScheduledTask -TaskName "Claude Health" -Confirm:$false

## Auf dem Handy

Das Dashboard ist als Artifact veröffentlicht und damit über eine eigene
Adresse im Handy-Browser erreichbar — privat, nur für den eigenen Account
sichtbar. Zum Startbildschirm hinzufügen, dann verhält es sich wie eine App.

**Wichtig:** Die Handy-Fassung ist ein Abzug, kein Live-Zugriff. Sie wird
erst neu, wenn sie neu veröffentlicht wird. Der tägliche Lauf auf dem PC
aktualisiert `dashboard.html` lokal — die veröffentlichte Seite bleibt bis
zur nächsten Veröffentlichung auf ihrem Stand.

## Journal

Ohne Eingabe wäre der Reiter „Verhaltensweisen" mit echten Daten **dauerhaft
leer** — Journal-Einträge stecken nur im Demo-Datensatz, Fitbit liefert
keine. Deshalb gibt es 13 antippbare Marken je Tag (Alkohol, Koffein nach
16 Uhr, spät gearbeitet, kalt geduscht …).

Die Auswertung rechnet **live in JavaScript**, nicht in Python: eigene
Einträge zählen sofort mit, statt erst beim nächsten Sync. Eigene Einträge
haben Vorrang vor dem, was im Datensatz steht. Gespeichert wird im
`localStorage`.

## Belastungsziel

`Ziel = 6 + Erholung/100 × 12`, Zielfenster ±1,5. Bei 86 % Erholung also
16,3 — bei 30 % nur 9,6. Der Balken zeigt das Fenster und den heutigen Stand.
Ohne Erholungswert erscheint kein Ziel, statt eines aus dem Nichts.

## Atemübung

Zwei Muster mit gegenläufiger Wirkung: **Beruhigen** (4 s ein, 2 s halten,
6 s aus — längeres Ausatmen bremst den Puls) und **Aktivieren** (6 s ein,
2 s aus). Vorgeschlagen wird nach dem Stresswert des Tages.

Die Schleife räumt sich selbst auf, sobald der Kreis nicht mehr im Dokument
steht — beim Rubrikwechsel also von allein. Der Start zeichnet die Ansicht
bewusst **nicht** neu, sonst bräche die laufende Übung ab.

## Gesundheitsmonitor

Fünf Vitalwerte, jeder gegen den **eigenen** Normalbereich geprüft, nicht
gegen einen Bevölkerungswert: Ruheherzfrequenz, HFV, Atemfrequenz,
Blutsauerstoff, Hauttemperatur.

| Abstand vom Normalwert | Einstufung |
|---|---|
| bis 1 Standardabweichung | im Normalbereich |
| 1 bis 2 | leicht abweichend |
| über 2 | deutlich abweichend |

Die Hauttemperatur ist bereits eine Abweichung und nutzt feste Schwellen
(±0,5 °C / ±1,0 °C) — sie braucht deshalb keinen Verlauf und ist schon am
ersten Tag beurteilbar. Alle anderen brauchen `MIN_TAGE_BASIS` Messtage,
vorher steht „Normalbereich wird noch aufgebaut" statt einer Einstufung.

Weicht ein Wert ab, erscheint darunter eine Karte mit dem gemessenen Wert,
dem üblichen Bereich und den häufigen Gründen für eine Abweichung in diese
Richtung. Die Kachel auf der Übersicht nutzt dieselbe Funktion
(`vitalStand`) — eine Logik, zwei Anzeigen.

**Kein Ersatz für ärztlichen Rat.** Der Monitor vergleicht gegen den eigenen
Verlauf, nicht gegen medizinische Grenzwerte. Er kann auffallen lassen, dass
sich etwas verändert hat, nicht warum. Der Hinweis steht auch in der App.

## Profil und biologisches Alter

Über das Symbol oben links. Beim ersten Öffnen werden Name und Geburtsdatum
abgefragt — beides bleibt im `localStorage` des Browsers und wird nirgendwohin
geschickt. Ohne Geburtsdatum gibt es kein biologisches Alter, weil der
Bezugspunkt fehlt.

**Wie es gerechnet wird.** Nicht „Alter aus Messwerten", sondern ein Abstand
zum Lebensalter: Wie stehen die Werte im Vergleich zu dem, was für dieses
Alter typisch wäre? Grundlage ist der belegte Zusammenhang zwischen
nächtlicher HRV (RMSSD) und Lebensalter — die HRV fällt über die Lebensspanne
annähernd exponentiell (25 Jahre ≈ 55 ms, 65 Jahre ≈ 24 ms).

| Größe | Gewicht | Deckel |
|---|---|---|
| Herzfrequenzvariabilität | 55 % | ±10 Jahre |
| Ruheherzfrequenz | 25 % | ±5 Jahre |
| Schlafkonsistenz | 12 % | ±3 Jahre |
| Schlafdauer | 8 % | +3 Jahre |

Das Ergebnis wird auf −10 / +12 Jahre um das Lebensalter begrenzt: ein
Armband kann nicht belegen, dass jemand zwölf Jahre jünger ist als sein
Ausweis sagt. Unter 14 Messtagen in den letzten vier Wochen erscheint gar
kein Wert.

**Tempo des Alterns** ist die Steigung des biologischen Alters über die
Wochenpunkte, hochgerechnet aufs Jahr. 1,0× heißt Gleichschritt mit dem
Kalender. Verlässt der Wert die Skala von −1,0× bis 3,0×, steht „unter" bzw.
„über" davor statt einer an den Anschlag geklemmten Zahl.

**Was das nicht ist.** Ein biologisches Alter in der Medizin wird aus
Dutzenden Markern bestimmt — Entzündungswerte, Methylierung, Organfunktion.
Diese Zahl stammt aus vier Größen, die ein Armband messen kann. Sie taugt für
die eigene Entwicklung über Monate, nicht für den Vergleich mit anderen und
schon gar nicht als Diagnose. Der Hinweis steht auch in der App.

Die Formel liegt doppelt vor: in `metrics.biological_age` und gespiegelt in
JavaScript im Dashboard — nötig, weil das Geburtsdatum nur im Browser liegt.

## Monatliche Sicherung

`sicherung.py` legt einmal je Kalendermonat ein ZIP des gesamten
`health/`-Ordners in `sicherungen/` ab, liest es zum Prüfen gegen und behält
die letzten 24 Stände. Zugangsdaten sind nicht enthalten.

Der tägliche Lauf ruft es mit auf; das Script entscheidet selbst, ob dieser
Monat schon einen Stand hat. Scheitert die Sicherung, gilt der Lauf trotzdem
als erfolgreich — die Daten sind dann ja geschrieben.

Soll die Sicherung auch einen Festplattenschaden überleben, genügt eine Zeile
in `config.py`:

    SICHERUNG_DIR = Path.home() / "OneDrive" / "Claude Health Sicherungen"

    # von Hand auslösen
    .venv\Scripts\python.exe sicherung.py --jetzt

## Die unbekannten Feldnamen

Adressen, Anfrageformat und die Zeitfenster-Grenzen der Google Health API
sind dokumentiert und in `api.py` umgesetzt (90 Tage je Abfrage, 14 Tage für
`heart-rate`, `total-calories`, `active-zone-minutes`).

Nicht dokumentiert sind die Feldnamen **innerhalb** der Antworten. Statt zu
raten steht in `sync.py` je Wert eine kurze Liste plausibler Schreibweisen;
genommen wird die erste, die eine Zahl liefert, und der Lauf meldet am Ende,
welche getroffen hat. `probe.py` ruft zusätzlich jeden Datentyp einmal ab und
legt die Rohantwort in `docs/api-proben/` — danach lässt sich die Zuordnung
auf je einen Eintrag eindampfen.

## Warum Google Health API und nicht Fitbit Web API

Die klassische Fitbit Web API (`dev.fitbit.com`) wird **Ende September 2026
abgeschaltet**. Nachfolger und einziger tragfähiger Weg ist die
**Google Health API** (`health.googleapis.com/v4`). Ein Setup auf der alten
API hätte binnen Wochen aufgehört zu funktionieren.

Ein Garmin-Weg (`python-garminconnect`) ist hier gegenstandslos – anderer
Hersteller, andere Server, andere Messwerte.

## Bedienung

Dashboard neu bauen (Demo-Daten):

    .venv\Scripts\python.exe demo_data.py
    .venv\Scripts\python.exe build_dashboard.py

Dann `dashboard\dashboard.html` doppelklicken. Keine Internetverbindung nötig.

## Dateien

    config.py             Pfade, Scopes, API-Adresse
    metrics.py            Formeln für Erholung, Belastung, Stress, Schlafbedarf
    demo_data.py          erzeugt den Demo-Datensatz   [Anzahl Tage] optional
    notes.py              schreibt lesbare Markdown-Notizen aus data.json
    auth.py               einmalige Google-Anmeldung (nur im echten Terminal)
    build_dashboard.py    schreibt die Daten in die Vorlage
    dashboard/template.html   Aussehen  (hier wird gestaltet)
    dashboard/dashboard.html  fertige Seite (wird erzeugt, nicht bearbeiten)
    docs/whoop-referenz.md    UI- und Funktionsvorlage aus den Screenshots
    health/UEBERSICHT.md      Einstieg zum Lesen
    health/tage/*.md          eine Notiz je Tag
    health/workouts/*.md      eine Notiz je Einheit
    health/data.json          dieselben Daten maschinenlesbar
    .secrets/                 Zugangsdaten, nur für den eigenen Benutzer lesbar

## Kalibrierung: die ersten Tage

Erholung, Stress und die Normalbereichs-Prüfungen vergleichen gegen den
**eigenen** Verlauf. Vor `metrics.MIN_TAGE_BASIS` (7) Messtagen gibt es diesen
Verlauf nicht — dann wird **kein Wert ausgegeben**, sondern „Kalibrierung
läuft, noch N Tage".

Vorher sprang hier eine fest verdrahtete Ersatz-Basis ein (HFV 50 ± 8 ms).
Das erzeugte am ersten Tag mit der neuen Uhr eine Zahl, die wie eine Messung
aussah, aber gegen einen erfundenen Vergleichswert gerechnet war.

Getestet mit 1, 3, 7, 30 und 90 Tagen: alle acht Ansichten rendern, kein
`NaN`, kein `undefined`, keine Konsolenfehler.

    .venv\Scripts\python.exe demo_data.py 3    # Kalibrierungsfall nachstellen

## Grundregel: keine erfundenen Werte

Jeder Wert im Dashboard ist entweder **gemessen** oder **aus Gemessenem
gerechnet**. Was sich aus den vorhandenen Daten nicht belegen lässt,
erscheint nicht — auch nicht als Platzhalter, der wie eine Messung aussieht.

Berechnete Werte tragen ein **oranges Sechseck mit zwei Zahnrädern**. Der
Tooltip nennt jeweils die Eingangsgrößen. Alles ohne Zeichen kommt
unverändert von der Uhr.

Konkret entfernt bzw. hergeleitet (Stand 10.09.2026):

| war vorher | ist jetzt |
|---|---|
| Akkustand „72 %" in der Kopfzeile | entfernt – steht in keiner API |
| Verhaltens-Prozente als feste Liste | aus den Tagesdaten zurückgerechnet |
| „Gesundheitsmonitor 5/5" zählte nur vorhandene Werte | echte Prüfung gegen den Normalbereich |
| Schlafkonsistenz gewürfelt | aus der Streuung der Schlafenszeiten |
| „Hoher Schlafstress" gewürfelt | ersetzt durch gemessenen Tief-/REM-Anteil |
| Kachelbalken mit willkürlicher Länge | Marker an der echten Position im Normalbereich |

Auswertungen mit zu wenigen Datenpunkten geben `None` zurück und werden gar
nicht angezeigt (`metrics.behaviour_impact`, `metrics.sleep_consistency`).

## Aktivitäts-Auswertung

Der Reiter „Aktivitäten" vergleicht je Sportart Tage **mit** dieser Einheit
gegen Tage **ohne** — und benutzt dafür bewusst zwei verschiedene
Kontrollgruppen:

| Wirkung auf | Wann gemessen | Verglichen mit |
|---|---|---|
| Stress | selber Tag | allen anderen Tagen |
| Erholung | Nacht danach | **anderen Trainingstagen** |
| Schlafleistung | Nacht danach | **anderen Trainingstagen** |

Der Grund für die zweite Spalte: Nimmt man für die Erholung alle anderen Tage
als Vergleich, stecken lauter Ruhetage darin. Dann sieht jede harte Einheit
verheerend aus, und gemessen wäre nur „Sport gegen Nichtstun" statt
„diese Sportart gegen andere Sportarten".

Unter drei Tagen je Gruppe erscheint keine Zahl, unter 3 % Unterschied steht
„kein erkennbarer Unterschied".

### Einheiten nachtragen

Das Air ist bildschirmlos — Workouts werden automatisch erkannt oder über das
Handy gestartet. Was die Automatik nicht erwischt (Golf, Krafttraining), lässt
sich im Reiter „Aktivitäten" nachtragen: Datum, Sportart, Dauer.

Das ist eine **Beschriftung, keine Messung** — kein Puls, keine Zonen. Für die
Auswertung reicht es, weil dort Tage verglichen werden. Die Einträge liegen im
`localStorage` des Browsers, nicht in `data.json`; über „Als JSON zum
Übernehmen" lassen sie sich dauerhaft in die Datendatei überführen.

## Bedienung am Handy

- **Wischen** nach links/rechts wechselt die Rubrik, eine Bewegung = eine Rubrik.
  In der Reiterleiste und in der Rohdaten-Tabelle nicht — dort schiebt man den Inhalt.
- **Pfeiltasten** links/rechts tun am Rechner dasselbe.
- Der gewählte Reiter wird immer vollständig ins Bild geschoben.
- `scrollbar-gutter: stable` reserviert die Scrollleiste dauerhaft, damit die
  Spalte beim Reiterwechsel nicht springt.

## Was gemessen und was gerechnet ist

Fitbit misst: Schlafphasen, HRV, Ruhepuls, Atemfrequenz, SpO₂,
Hauttemperatur, Herzfrequenzzonen, Schritte, Distanz, Workouts.

Fitbit liefert **nicht**: Erholungswert, Belastungszahl, Stresswert,
Schlafbedarf. Diese vier berechnet `metrics.py` aus den gemessenen Größen,
verglichen gegen den eigenen Normalbereich der letzten 30 Tage. Im Dashboard
sind sie als berechnet gekennzeichnet.

Nicht verfügbar und deshalb nicht enthalten: Blutdruck, EKG, biologisches
Alter.

## Sicherheit

- Nur lesende Scopes (`.readonly`). Zurückschreiben ist auf Google-Ebene
  ausgeschlossen, nicht nur im Code.
- `auth.py` verweigert den Start ohne echtes Terminal.
- Das Google-Passwort kommt im Projekt nirgends vor – die Anmeldung läuft
  im Browser bei Google.
- `.gitignore` schließt Token, Gesundheitsdaten, Logs und `.venv` aus.

## Nächste Schritte, wenn das Fitbit Air da ist

1. Uhr mit der Fitbit-App am Handy koppeln (die App ist zwingend — nur sie
   lädt die Daten der Uhr zu Google hoch).
2. Google-Cloud-Projekt anlegen, Health API aktivieren, OAuth-Client
   (Webanwendung, Weiterleitung `https://www.google.com`), eigene Adresse
   als Testnutzer eintragen. Die drei Scopes stehen in `config.py`.
3. Einmalig im echten Terminal:

       .venv\Scripts\python.exe auth.py

4. Struktur der Antworten ansehen:

       .venv\Scripts\python.exe probe.py

5. Feldzuordnung in `sync.py` festzurren, dann Probelauf ohne Schreiben:

       .venv\Scripts\python.exe sync.py --tage 3 --trocken

6. Erst danach echt schreiben und die Historie holen:

       .venv\Scripts\python.exe sync.py --tage 60

Ab dann läuft der tägliche Job von allein auf echte Daten um.
