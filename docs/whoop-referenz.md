# UI- und Funktionsreferenz (aus den Screenshots)

Quelle: Screenshots der WHOOP-App und der WHOOP-Website, vom Nutzer am 10.09.2026
bereitgestellt. Diese Datei ist die verbindliche Bauvorlage für das Dashboard.

**Lesart der Website-Bilder:** links Infotext (= was die App fachlich kann),
rechts das Handy-Mockup (= wie es aussieht). Für die Optik gilt immer rechts.

**Abgrenzung:** Nachgebaut wird die Gestaltungssprache, nicht die Marke. Kein
WHOOP-Wortzeichen, kein WHOOP-Logo im Produkt. Der Ringtext trägt den Namen des
Projekts. Reine Eigennutzung.

---

## 1. Gestaltungsraster

| Element | Wert |
|---|---|
| Hintergrund App | `#000000` reines Schwarz |
| Kartenfläche | `#12151A` bis `#1A1D23`, leicht aufgehellt gegen Schwarz |
| Kartenradius | 12–16 px, durchgehend gerundet |
| Primärtext | `#FFFFFF` |
| Sekundärtext | `#9BA1A9` (Labels, Achsen, Zeitstempel) |
| Label-Stil | GROSSBUCHSTABEN, weit getrackt (~0.08em), 11–12 px |
| Zahlen | sehr fett (700–800), groß, eng getrackt |
| Trennlinien | `#22262D`, 1 px |
| Schrift | serifenlose Grotesk, eng; System-Stack als Ersatz |

### Bedeutungsfarben (konsequent, nie wechselnd)

| Bedeutung | Farbe | Verwendung |
|---|---|---|
| Erholung hoch | `#00F19F` Grün | Ring, Balken, Statuspunkt |
| Erholung mittel | `#FFDE00` Gelb | Ring, Balken |
| Erholung niedrig | `#FF0026` Rot | Ring, Balken |
| Belastung / Strain | `#0093E7` Blau | Ring, Aktivitätsbalken |
| Schlaf | `#7BA1BB` Hellblau-Grau | Schlafring, Schlafkarten |
| Schlafphasen | Violett-Palette | siehe 2.4 |
| Hervorhebung / aktuell | `#FFFFFF` | letzter Datenpunkt, aktiver Tab |

### Ringe (das prägende Element)
- Kreisring, dicke Linie (~8–10 % des Durchmessers), runde Enden.
- Start oben (12 Uhr), im Uhrzeigersinn.
- Rest des Kreises als dunkler Spurring `#22262D`.
- In der Mitte: kleines Label oben (Markenname, sehr klein, grau),
  darunter die große Zahl, darunter das Metrik-Label klein und gesperrt.
- Drei Ringe nebeneinander als Tagesübersicht: SCHLAF / ERHOLUNG / BELASTUNG.

---

## 2. Bildschirme (Bild für Bild ausgelesen)

### 2.1 Startseite
- Kopfzeile: Profil-Icon, Datumsnavigation mit Pfeilen links/rechts, Akkustand rechts.
- Drei Ringe nebeneinander mit Werten darunter + Chevron.
- Einsicht-Karte, z. B. "Erhöhte HFV" mit Haken-Badge und Zähler.
  Text: "Deine HFV ist 6 % höher als üblich, was auf Spitzenerholung deutet."
- Zwei halbbreite Karten nebeneinander:
  - GESUNDHEITSMONITOR: grüner Haken, "IM NORMALBEREICH 5/5 Werte"
  - STRESSMONITOR: Zahl 0,7, Stufe NIEDRIG, Uhrzeit
- Abschnitt "Mein Tag" mit "Dein täglicher Ausblick"
- "HEUTIGE AKTIVITÄTEN" mit Aufklapp-Icon, darunter Zeilen
  (Mond-Icon, "6:24 SCHLAF", Zeitspanne rechts, farbiger Balken links).
- Buttons: "+ AKTIVITÄT HINZUFÜGEN", "AKTIVITÄT STARTEN"
- Karte "SCHLAF HEUTE NACHT": empfohlene Schlafenszeit / Weckzeit
- "MEIN JOURNAL" mit Button "AUSFÜLLEN"
- Untere Navigation: Start / Gesundheit / Community / Mehr, dazu ein
  schwebender runder Plus-Button unten rechts.

### 2.2 Mein Dashboard (Listenansicht)
Kopf: "Mein Dashboard" + pinkfarbene Pille "ANPASSEN".
Zeilenaufbau: Icon links, Label in Großbuchstaben, rechts große fette Zahl
mit Trend-Dreieck (auf = grün / ab = rot), darunter klein der Vergleichswert.

Belegte Zeilen laut Screenshot:
HERZFREQUENZVARIABILITÄT 52 auf (49) · RUHEHERZFREQUENZ 57 ab (56) ·
SCHRITTE 840 ab (8.929) · HF-ZONEN 1–3 (WÖCHENTLICH) 1:02 (0:46) ·
HF-ZONEN 4–5 (WÖCHENTLICH) 0:08 (0:20) · VO2MAX · KALORIEN 1.169 ab (2.523) ·
STRESSMONITOR mit Verlaufsleiste und Mond-Marker, Skala bis 3,0.

### 2.3 Erholung
- Großer Ring, Farbe nach Wert (grün/gelb/rot), Zahl in Prozent.
- Vier Beitragszeilen mit Icon: HERZFREQUENZVARIABILITÄT 124 ·
  RUHEHERZFREQUENZ 49 · ATEMFREQUENZ 14,5 · SCHLAFLEISTUNG 74 %
- Einsicht-Box mit blauem Rahmen und Verlaufsschimmer, darin ein Satz im
  Muster: "Deine HFV ist erhöht, während RHF, Atemfrequenz und
  Schlafleistung typisch sind. Das führt heute zu einem höheren
  Erholungswert." Darunter Link "ERFAHRE MEHR ..."
- Trendansicht: Säulen je Tag, eingefärbt nach Wert, Prozentzahl über
  jeder Säule, Wochentag + Datum darunter, feine waagerechte Gitterlinien
  bei 0/33/64/100 %.

### 2.4 Schlaf
- Ring "SCHLAFLEISTUNG" in Prozent, hellblau.
- Vier Zeilen mit Miniatur-Skalenbalken und Gütepunkt:
  STUNDEN VS. BEDARF · SCHLAFKONSISTENZ · SCHLAFEFFIZIENZ · HOHER SCHLAFSTRESS
  Legende: Schlecht (orange) / Ausreichend (gelb) / Optimal (grün)
- "Letzte Nacht", Vergleich "Heute vs. vorherige 30 Tage".
- Schlafphasen-Zeilen mit Punkt, Prozent, Balken, Dauer:
  WACH 10 % 0:43 · LEICHT 47 % 3:17 · TIEF (SWS) 27 % 1:57 · REM 16 % 1:10
  Farben: Wach = hellgrau, Leicht = helles Violett, Tief = kräftiges
  Violett/Magenta, REM = mittleres Violett.
- Hypnogramm: Herzfrequenzlinie über die Nacht in Grau, davor die
  Phasenblöcke als farbige Säulen, Sonnenunter-/Sonnenaufgang-Icon mit
  Uhrzeit an beiden Enden.
- STUNDEN VS. BEDARF als gestapelter Balken: Gesundes Minimum + Aktuelle
  Belastung + Schlafdefizit − Nickerchen = Schlafbedarf; daneben die
  tatsächliche Dauer.
- SCHLAFKONSISTENZ: Balken je Tag zwischen Zubettgeh- und Aufwachzeit,
  gestrichelte Linien für die optimalen Zeiten, heutiger Balken hervorgehoben.
- Schlafplan: "MORGEN MÖCHTE ICH:" mit Auswahlknopf, empfohlene
  Schlafenszeit / festgelegte Aufwachzeit, Balken "Zeit im Bett", Optimalfenster.
- Trend: zwei Linien (Schlafbedarf grün, Schlafdauer grau) mit Punktlabels.

### 2.5 Belastung (Strain)
- Blauer Ring, Skala **0 bis 21**, eine Nachkommastelle.
- Einstufungstext je Bereich, z. B. 14,0–17,9 = "Anstrengend".
- Aktivitätskarten: farbiger Balken links, Wert, Name, Uhrzeitspanne.
- HF-Zonen-Aufschlüsselung je Aktivität, sechs Zeilen:
  ZONE 5 (90–100 %) bis ZONE 0 (<50 %), je mit BPM-Bereich, Prozentanteil,
  gefülltem Balken vor schraffiertem Rest und der Dauer h:mm:ss.
  Farben von oben nach unten: Orange, Bernstein, Grün, Blau, Hellgrau, Weiß.
- Zonen-Übersicht als gestapeltes Säulendiagramm über mehrere Einheiten.
- Aktivitätsdetail: Herzfrequenzlinie, "TYPISCHER BEREICH", Dauer,
  Kennzahlen KALORIEN / DURCHSCHN. HF / MAX. HF / DAUER.
- Belastungsziel: Coach-Karte mit Begrüßung, Vorschlag mit Dauer und
  geschätzter Belastung, Intensitäts-Schieber niedrig/mittel/hoch.
- Aktivitätsbelastung mit Schieber AUSDAUER ↔ MUSKULÄR (Prozentaufteilung).

### 2.6 Stress
- Tacho-Bogen mit Farbverlauf Blau → Grün → Gelb → Orange, dünne
  Nadelmarkierung, Skala **0,0 bis 3,0**, große Zahl mit Stufenwort
  (NIEDRIG / MITTEL / HOCH), Zeitstempel "Letzte Aktualisierung".
- Umschalter STRESS / HERZFREQUENZ.
- Tagesverlauf als Linie, deren Farbe sich entlang des Wertes ändert
  (blau unten → grün → orange oben). Extremwerte links/rechts beschriftet.
- Atemübung: großer Kreis mit weichem Farbverlauf, Zähler in der Mitte,
  zwei Anweisungszeilen mit farbigen Punkten.

### 2.7 Verhaltensweisen / Journal
- Karte mit Nullachse in der Mitte: links SCHADET, rechts HILFT,
  Überschrift "AUSWIRKUNG IN %".
- Zeilen mit Verhalten und divergierendem Balken vom Mittelpunkt aus,
  grün nach rechts, orange nach links, Prozentwert am Zeilenende,
  runder Griffpunkt am Nullpunkt, schraffierter Resthintergrund.
  Beispiele: SCHLAFLEISTUNG >81 % +21 % · LESEN IM BETT +13 % ·
  KATZE IM SCHLAFZIMMER −1 % · SPÄT ARBEITEN −6 %

### 2.8 Gesundheitsmonitor
- Große Kennzahl mit Einheit, z. B. HERZFREQUENZ 89 S/MIN, blaue Linie,
  weißer Punkt am letzten Wert, Zonenangabe darunter.
- Kachelraster weiterer Vitalwerte, je mit grünem Balken "IM NORMALBEREICH".
- Abweichungsmeldung als eigene Seite, z. B. "HAUTTEMPERATUR ERHÖHT" mit
  Erklärtext und Bereichsangaben grün/orange/rot.

### 2.9 Navigation (Website-Bilder)
Pillen-Reiter in einer Zeile: SCHLAF · BELASTUNG · WIEDERHERSTELLUNG ·
STRESS · VERHALTENSWEISEN · GESUNDHEIT.
Aktiv = weiß gefüllte Pille mit schwarzer Schrift.
Inaktiv = transparent mit dünnem hellen Rand.

---

## 3. Rechenlogik aus den Infotexten

### 3.1 Erholungswert (0–100 %)
Laut Infotext berechnet aus: **Herzfrequenzvariabilität (größter Faktor)**,
Ruheherzfrequenz, Atemfrequenz, Blutsauerstoffsättigung und Hauttemperatur
während des Schlafs sowie der Schlafleistung.
Farbzonen: grün = mehr Leistung möglich, gelb = Niveau halten,
rot = mehr Ruhe nötig.

### 3.2 Schlafbedarf
Bedarf = Gesundes Minimum + Aktuelle Belastung + Schlafdefizit − Nickerchen.
Schlafleistung = Dauer / Bedarf.

### 3.3 Stresswert (0,0–3,0)
Aus aktueller Herzfrequenz und HRV, verglichen mit den **Normalwerten der
letzten 14 Tage**. Körperbewegung wird berücksichtigt, um Sport von
sonstigem Stress zu trennen.

### 3.4 Belastung (0–21)
Bildet kardiovaskuläre und muskuläre Beanspruchung ab, aus Zeit in den
Herzfrequenzzonen. Nicht linear, oben gestaucht.

---

## 4. Machbarkeit mit Fitbit-Daten (Google Health API)

| Funktion | Fitbit-Datenlage | Umsetzung |
|---|---|---|
| Schlafphasen, Dauer, Effizienz | `sleep` mit Phasen | direkt |
| HRV | `daily-heart-rate-variability` | direkt |
| Ruhepuls | `daily-resting-heart-rate` | direkt |
| Atemfrequenz | `daily-respiratory-rate` | direkt |
| Blutsauerstoff | `daily-oxygen-saturation` | direkt |
| Hauttemperatur | `daily-sleep-temperature-derivations` | direkt |
| HF-Zonen | `daily-heart-rate-zones`, `heart-rate` | direkt |
| Schritte, Distanz, Kalorien | `steps`, `distance`, `total-calories` | direkt |
| Workouts | `exercise` | direkt |
| **Erholungswert** | kein Fitbit-Pendant in der API | **berechnet**, Formel 3.1 |
| **Belastung 0–21** | kein Pendant | **berechnet** aus Zonenzeiten |
| **Stress 0–3** | kein Pendant | **berechnet**, Formel 3.3 |
| **Schlafbedarf** | kein Pendant | **berechnet**, Formel 3.2 |
| Journal / Verhaltensweisen | keine Messung nötig | Eingabe durch Nutzer |
| VO2max | ggf. vorhanden | später prüfen |
| Blutdruck | **nicht verfügbar** | entfällt |
| EKG | **nicht verfügbar** | entfällt |
| Biologisches Alter / Healthspan | proprietär | entfällt |

Alles Berechnete wird im Dashboard sichtbar als solches gekennzeichnet.
