"""Baut aus der Vorlage die Fassung fuer Handy, Tablet und Rechner.

Unterschied zu build_dashboard.py: Dort werden die Daten fest in die Datei
geschrieben (eine Datei, offline, kein Login). Hier kommen sie nach der
Anmeldung aus Firestore - dieselbe Oberflaeche, aber auf jedem Geraet mit
denselben Daten.

Zwei Eingriffe reichen dafuer, der Rest der Vorlage bleibt unberuehrt:

  1. Der Platzhalter der Daten wird zu window.__DATEN__, und das ganze
     Programm wandert in die Funktion claudeHealthStart(). Die ruft start.js
     auf, sobald die Daten da sind.

  2. Jedes "localStorage." wird zu "CHSpeicher." - dieselben Methoden, aber
     die Ablage liegt in Firestore. Sonst haette man Logbuch und Plaene auf
     dem iPad neu anlegen muessen.

Aufruf:  python build_app.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from config import PROJECT_DIR, TEMPLATE_FILE

APP_DIR = PROJECT_DIR / "app"
ZIEL = APP_DIR / "index.html"
PLATZHALTER = "__CLAUDE_HEALTH_DATA__"

FIREBASE_VERSION = "10.12.2"

KOPF_ZUSATZ = """
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#070C11">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Claude Health">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" href="icon.svg" type="image/svg+xml">
"""

ANMELDE_STIL = """
/* ---------- Anmeldung, Laden, Onboarding ---------- */
#anmeldung,#laden{position:fixed;inset:0;z-index:200;display:flex;align-items:center;
  justify-content:center;padding:24px;background:
    radial-gradient(78% 40% at 64% 0%,rgba(28,116,116,.16) 0%,rgba(28,116,116,0) 64%),
    linear-gradient(180deg,#0A121A 0%,#070C12 56%,#04080C 100%)}
#anmeldung[hidden],#laden[hidden],#onboarding[hidden]{display:none}
.anmeldekasten{width:100%;max-width:340px;text-align:center}
.anmeldekasten .marke{height:auto;display:block;margin-bottom:34px}
.anmeldekasten .marke .n{font-family:var(--serif);font-size:30px;color:#fff}
.anmeldekasten .marke .p{font-size:22px;letter-spacing:.20em;font-weight:600;margin-left:.42em}
.anmeldekasten label{display:block;text-align:left;font-size:10.5px;letter-spacing:.10em;
  text-transform:uppercase;color:var(--dim2);font-weight:700;margin:0 0 6px 2px}
.anmeldekasten input{margin-bottom:14px;padding:13px 12px;font-size:15px}
.anmeldekasten .btn{padding:15px;border-radius:999px;font-size:11.5px}
.anmeldefehler{min-height:20px;margin-top:14px;font-size:12.5px;color:var(--z4)}
.anmeldefehler.still{color:var(--dim)}
.ladetext{color:var(--dim);font-size:14px;line-height:1.5;text-align:center}
.ladepunkt{width:34px;height:34px;margin:0 auto 16px;border-radius:50%;
  border:2.5px solid rgba(255,255,255,.16);border-top-color:var(--green);
  animation:drehen .9s linear infinite}
@keyframes drehen{to{transform:rotate(360deg)}}
.offlinehinweis{position:fixed;left:50%;bottom:82px;transform:translateX(-50%);z-index:90;
  background:#22262E;border:1px solid #343A43;border-radius:999px;padding:9px 16px;
  font-size:12px;color:var(--dim)}

#onboarding{position:fixed;inset:0;z-index:150;display:flex;align-items:center;
  justify-content:center;padding:22px;background:rgba(2,6,10,.86)}
.obkasten{background:#12181F;border-radius:20px;padding:24px 20px;width:100%;max-width:360px}
.obkasten h2{font-size:21px;font-weight:800;letter-spacing:-.02em;margin:0 0 10px}
.obkasten p{font-size:14px;line-height:1.5;color:rgba(255,255,255,.78);margin:0 0 18px}
.obwerte{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:18px}
.obwerte span{background:rgba(255,255,255,.07);border-radius:8px;padding:7px 10px;
  font-size:12px;color:var(--dim)}
.obfehler{min-height:18px;font-size:12.5px;color:var(--z4);margin-top:8px}
.obspaeter{display:block;margin:14px auto 0;background:none;border:0;color:var(--dim);
  font-family:inherit;font-size:12.5px;cursor:pointer;text-decoration:underline}
"""

ANMELDE_MARKUP = """
<div id="anmeldung" hidden>
  <form class="anmeldekasten" id="anmeldeform">
    <div class="marke"><span class="n">Claude</span><span class="p">HEALTH</span></div>
    <label for="a-mail">E-Mail</label>
    <input type="email" id="a-mail" autocomplete="username" required>
    <label for="a-pass">Passwort</label>
    <input type="password" id="a-pass" autocomplete="current-password" required>
    <button class="btn" type="submit">Anmelden</button>
    <div class="anmeldefehler" id="anmeldefehler"></div>
  </form>
</div>

<div id="laden">
  <div>
    <div class="ladepunkt"></div>
    <div class="ladetext">Daten werden geladen …</div>
  </div>
</div>

<div id="onboarding" hidden>
  <div class="obkasten">
    <h2>Noch eine Angabe</h2>
    <p>Dein Geburtsdatum liefert Google nicht mit — nur dein Alter in Jahren.
      Für das biologische Alter braucht es aber den Tag.</p>
    <div class="obwerte" id="ob-uebernommen"></div>
    <label for="ob-gebtag" style="display:block;text-align:left;font-size:10.5px;
      letter-spacing:.10em;text-transform:uppercase;color:var(--dim2);font-weight:700;
      margin:0 0 6px 2px">Geburtsdatum</label>
    <input type="date" id="ob-gebtag">
    <div class="obfehler" id="ob-fehler"></div>
    <button class="btn" id="ob-speichern" style="margin-top:12px;border-radius:999px;
      padding:14px">Speichern</button>
    <button class="obspaeter" id="ob-spaeter">Später</button>
  </div>
</div>
"""


def js_pruefen(js: str) -> str | None:
    """Wie beim Dashboard: lieber abbrechen als eine tote Seite ausliefern."""
    if not shutil.which("node"):
        return None
    with tempfile.TemporaryDirectory() as ordner:
        datei = Path(ordner) / "block.js"
        datei.write_text(js, encoding="utf-8")
        lauf = subprocess.run(["node", "--check", str(datei)],
                              capture_output=True, text=True)
        return None if lauf.returncode == 0 else (lauf.stderr or lauf.stdout)


def main() -> int:
    vorlage = TEMPLATE_FILE.read_text(encoding="utf-8")

    treffer = re.search(r"<script>(.*)</script>", vorlage, re.S)
    if not treffer:
        sys.exit("Im Vorlagen-HTML steckt kein <script>-Block.")
    js = treffer.group(1)
    rumpf = vorlage[:treffer.start()]

    # 1) Daten kommen jetzt von aussen
    if PLATZHALTER not in js:
        sys.exit(f"Platzhalter {PLATZHALTER} fehlt in der Vorlage.")
    js = js.replace(PLATZHALTER, "window.__DATEN__")

    # 2) Ablage: Firestore statt Browserspeicher
    js = js.replace("localStorage.", "CHSpeicher.")

    # 3) Alles in eine Startfunktion, die start.js aufruft
    # Ein schmales Fenster nach aussen: start.js muss nach dem Onboarding
    # neu zeichnen koennen, und Tests brauchen einen Griff. Alles andere
    # bleibt in der Funktion gekapselt.
    anfang = "function claudeHealthStart(){\n"
    schluss = "\n  window.CH = {render, S, D, DATA, setzeReiter};\n}"
    js_gewickelt = anfang + js + schluss

    fehler = js_pruefen(js_gewickelt)
    if fehler:
        print("ABBRUCH: Das JavaScript der App ist fehlerhaft.\n")
        print(fehler)
        return 1

    # Kopf ergaenzen, Anmeldung davor, App zunaechst versteckt
    rumpf = rumpf.replace("</style>", ANMELDE_STIL + "</style>", 1)
    rumpf = rumpf.replace("<style>", KOPF_ZUSATZ + "<style>", 1)
    rumpf = rumpf.replace('<div id="app">', ANMELDE_MARKUP + '\n<div id="app" hidden>', 1)

    basis = f"https://www.gstatic.com/firebasejs/{FIREBASE_VERSION}"
    seite = (rumpf
             + f'<script src="{basis}/firebase-app-compat.js"></script>\n'
             + f'<script src="{basis}/firebase-auth-compat.js"></script>\n'
             + f'<script src="{basis}/firebase-firestore-compat.js"></script>\n'
             + '<script src="../js/firebase-config.js"></script>\n'
             + "<script>\n" + js_gewickelt + "\n</script>\n"
             + '<script src="start.js"></script>\n')

    APP_DIR.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(seite, encoding="utf-8")
    groesse = ZIEL.stat().st_size / 1024
    print(f"App gebaut      : {ZIEL}")
    print(f"  Groesse       : {groesse:.0f} KB (ohne Daten - die kommen aus Firestore)")
    print(f"  Aufruf         : https://johann-macro.github.io/claude-health/app/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
