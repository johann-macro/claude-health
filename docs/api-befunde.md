# Google Health API – Befunde am echten Konto

Stand: 17.09.2026, erste Nacht mit der Fitbit Air. Grundlage für `sync.py`.
Rohantworten: `docs/api-proben/` (nicht versioniert – enthält Gesundheitsdaten).

## Anfrageformate (bestätigt)

| Art | Aufruf | Anmerkung |
|---|---|---|
| Tageswerte `daily-*` | `GET .../dataPoints?filter=<typ_snake>.date >= "YYYY-MM-DD" AND ... < "..."` | Filter mit **snake_case**-Typname |
| Messpunkte (HFV, Gewicht, Größe, Puls roh) | `GET .../dataPoints?filter=<typ_snake>.sample_time.civil_time >= "YYYY-MM-DDT00:00:00"` | |
| Summen je Tag | `POST .../dataPoints:dailyRollUp` Body `{"range":{"start":CivilDT,"end":CivilDT},"windowSizeDays":1}` | CivilDT = `{"date":{y,m,d},"time":{"hours":0,"minutes":0}}`. Flache Form wird abgelehnt. **Kein `pageSize`** – bei `total-calories`/`heart-rate` sonst „Invalid argument“ |
| Sitzungen `sleep`, `respiratory-rate-sleep-summary` | `GET .../dataPoints` **ohne Filter** | `interval.start_time`/`civil_start_time` im Filter → `INVALID_DATA_POINT_FILTER_DATA_TYPE_MEMBER`. Neueste zuerst, Seiten über `nextPageToken` |
| Profil, Einstellungen, Geräte | `GET users/me/profile`, `/settings`, `/pairedDevices` | |

Zahlen kommen teils als **String** (`"beatsPerMinute": "52"`, `"countSum": "8813"`) – immer konvertieren.
`NaN` kommt als String `"NaN"` (z. B. Temperatur-Basislinie in den ersten Nächten).

## Zuordnung zu den App-Feldern

| App-Feld | Quelle | Feld |
|---|---|---|
| `recovery.hrv` | daily-heart-rate-variability | `averageHeartRateVariabilityMilliseconds` (zusätzlich `deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds`) |
| `recovery.rhr` | daily-resting-heart-rate | `beatsPerMinute` (`calculationMethod` z. B. `WITH_SLEEP`) |
| `recovery.resp` | daily-respiratory-rate | `breathsPerMinute` |
| `recovery.spo2` | daily-oxygen-saturation | `averagePercentage` (+ `lower/upperBoundPercentage`) |
| `recovery.skin_temp_dev` | daily-sleep-temperature-derivations | `nightlyTemperatureCelsius` − `baselineTemperatureCelsius`; Basislinie ist anfangs `NaN` → selbst über 30 Nächte bilden |
| `sleep.*` | sleep | `interval.startTime/endTime` (UTC + `startUtcOffset`), `summary.minutesAsleep/minutesAwake/minutesInSleepPeriod/minutesToFallAsleep`, `summary.stagesSummary[] {type AWAKE/LIGHT/DEEP/REM, minutes, count}`, `stages[]` (Hypnogramm), `shortAwakenings[]`, `metadata.mainSleep` |
| Hypnogramm-Puls | heart-rate (list, Rohwerte) | `beatsPerMinute` je Messzeitpunkt |
| `steps` | steps (dailyRollUp) | `steps.countSum` |
| `distance_km` | distance (dailyRollUp) | `distance.millimetersSum` / 1e6 |
| `strain.calories` | total-calories (dailyRollUp) | Feld noch zu prüfen; `active-energy-burned.kcalSum` für Aktivkalorien |
| Zonen für Belastung | time-in-heart-rate-zone (dailyRollUp) | `timeInHeartRateZones[] {heartRateZone LIGHT/MODERATE/VIGOROUS/PEAK, duration "60480s"}` – **nur 4 Fitbit-Zonen**, nicht die 6 der App → Belastung besser aus Rohpuls + eigener Zonengrenze rechnen |
| Aktive Zonenminuten | active-zone-minutes (dailyRollUp) | `sumInFatBurnHeartZone/CardioHeartZone/PeakHeartZone` |
| Stress-Verlauf | heart-rate (list) + heart-rate-variability (list, 5-Min-Raster, nachts) | HFV-Messpunkte gibt es **nur im Schlaf** (85 Punkte/Nacht) → Tagesstress nur aus Puls ableitbar |
| Training | exercise | noch leer – erst nach der ersten erfassten Einheit prüfbar |
| VO₂max | daily-vo2-max | noch leer – braucht Läufe |

## Profil und Gerät

- `profile`: **`age` (26), kein Geburtsdatum** → Geburtsdatum für das biologische Alter beim ersten Login erfragen
- `weight` / `height`: vorhanden (manuell in der Fitbit-App eingetragen) → nicht erfragen, solange vorhanden
- `settings.timeZone`: `Europe/Berlin` → Tagesgrenzen danach
- `pairedDevices[].batteryLevel` + `lastSyncTime`: **echter Akkustand** – darf jetzt angezeigt werden (vorher bewusst weggelassen, weil nicht messbar)
