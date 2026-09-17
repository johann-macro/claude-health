# Betrieb ohne eigenen PC

## Die eine Frage, um die es geht

Das Dashboard ist bereits extern gehostet — als Artifact auf claude.ai,
kostenlos und privat. Das ist erledigt.

Offen ist nur: **Wer ruft täglich die Google Health API auf?** Das braucht
deinen OAuth-Token und muss irgendwo laufen. Entweder auf deinem PC (so wie
jetzt eingerichtet) oder auf einem Server. Die Seite selbst kann es nicht:
Ein Browser ist kein Ort für einen dauerhaften Zugangsschlüssel, und die
Artifact-Seite darf aus Sicherheitsgründen keine fremden Adressen aufrufen.

## Warum die Artifact-Datenbank es nicht löst

Artifacts können eine serverseitige Datenbank haben (`db`). Sie ist
verfügbar. Aber schreiben kann dort nur die Seite selbst oder Claude in
einem Gespräch — **nicht dein PC und kein fremder Dienst.** Damit bliebe
genau das Problem bestehen, das gelöst werden soll.

## Der kostenlose Weg

| Baustein | Dienst | Kosten | Aufgabe |
|---|---|---|---|
| Zeitplan + Abruf | GitHub Actions | kostenlos (privates Repo) | führt täglich `sync.py` aus |
| Hosting der Seite | Cloudflare Pages | kostenlos | liefert `dashboard.html` aus |
| Zugangsschutz | Cloudflare Access | kostenlos bis 50 Nutzer | nur deine E-Mail darf öffnen |

Beides zusammen: kein Euro, kein PC, Daten so lange gespeichert, wie du
willst — sechs Monate sind knapp 1,5 MB.

**Warum nicht GitHub Pages allein:** Bei einem privaten Repo ist Pages
kostenpflichtig. Ein öffentliches Repo wäre kostenlos, aber dann lägen
deine Gesundheitsdaten **öffentlich im Netz** — nicht „auf einem fremden
Server", sondern für jeden auffindbar. Das ist ein Unterschied.

## Schritte, wenn das Fitbit Air da ist

1. `auth.py` lokal ausführen (einmalig, siehe README)
2. `sync.py` gegen echte Daten prüfen und die Feldnamen festzurren
3. Privates GitHub-Repo anlegen, Projekt hochladen (`.gitignore` schützt
   Token und Gesundheitsdaten)
4. Zwei Secrets im Repo hinterlegen:
   - `CLAUDE_HEALTH_CLIENT` — Inhalt von `.secrets/client.json`
   - `CLAUDE_HEALTH_TOKEN` — Inhalt von `.secrets/token.json`
5. Cloudflare-Konto anlegen, Pages-Projekt mit dem Repo verbinden
6. In Cloudflare Access eine Regel anlegen: nur deine E-Mail
7. `.github/workflows/sync.yml` aktivieren

## Stolperstein: der Token-Umlauf

`sync.py` erneuert den Zugangstoken und schreibt ihn zurück. Auf GitHub
Actions ist das Dateisystem nach jedem Lauf weg — die Erneuerung geht also
verloren. Das ist meistens unkritisch, weil der **Refresh-Token** bestehen
bleibt und nur der kurzlebige Zugriffstoken erneuert wird.

Falls Google den Refresh-Token doch einmal austauscht, bricht der nächste
Lauf ab. Der Job meldet das dann im Protokoll, und es reicht, `auth.py`
lokal einmal zu wiederholen und das Secret neu zu setzen. Dieser Fall ist
selten, aber er ist der Grund, warum der Job seinen Exit-Code sauber
zurückgibt statt still zu scheitern.

## Was ich nicht tun kann

Konten anlegen, Zahlungsdaten hinterlegen oder deine Zugangsdaten
irgendwo eintragen. Die Schritte 3 bis 6 gehören in deine Hand — ich
führe dich klickgenau durch, sobald du so weit bist.
