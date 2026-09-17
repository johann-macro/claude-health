"""Zentrale Einstellungen fuer die Fitbit-Anbindung ueber die Google Health API.

Hintergrund: Die alte Fitbit Web API (dev.fitbit.com) wird am 30.09.2026
abgeschaltet. Dieses Projekt spricht deshalb ausschliesslich mit dem
offiziellen Nachfolger health.googleapis.com/v4.
"""
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

# Zugangsdaten - liegen bewusst in einem eigenen, abgeschotteten Ordner
SECRETS_DIR = PROJECT_DIR / ".secrets"
CLIENT_FILE = SECRETS_DIR / "client.json"   # Client-ID + Secret (von dir)
TOKEN_FILE = SECRETS_DIR / "token.json"     # Zugriffstoken (von Google)

# Ausgabe
HEALTH_DIR = PROJECT_DIR / "health"
DATA_JSON = HEALTH_DIR / "data.json"
DAYS_DIR = HEALTH_DIR / "tage"
WORKOUTS_DIR = HEALTH_DIR / "workouts"

DASHBOARD_DIR = PROJECT_DIR / "dashboard"
TEMPLATE_FILE = DASHBOARD_DIR / "template.html"
DASHBOARD_FILE = DASHBOARD_DIR / "dashboard.html"

LOG_DIR = PROJECT_DIR / "logs"

# Monatliche Sicherungen der Rohdaten.
# Zeigt dieser Pfad in einen Cloud-Ordner (z. B. OneDrive), ueberlebt die
# Sicherung auch einen Festplattenschaden - dann liegen die Daten allerdings
# beim jeweiligen Anbieter. Eine Zeile aendern genuegt:
#   SICHERUNG_DIR = Path.home() / "OneDrive" / "Claude Health Sicherungen"
SICHERUNG_DIR = PROJECT_DIR / "sicherungen"

# --- Firebase: Anmeldung und Datenbank fuer alle Geraete ---------------
# Der Dienstkonto-Schluessel gehoert NICHT ins Repository. Lokal liegt er in
# .secrets/, beim automatischen Abgleich kommt er aus einem geschuetzten
# Geheimnis der Ablaufumgebung (Umgebungsvariable FIREBASE_DIENSTKONTO).
FIREBASE_KEY_FILE = SECRETS_DIR / "firebase-dienstkonto.json"
FIREBASE_PROJEKT = "claude-health-d35b7"

# Wem die Daten gehoeren. Steht in Firebase unter Authentication > Nutzer.
NUTZER_UID = "wyTsDD0YWaPDJqEgZ7ldwSAFaG83"

API_BASE = "https://health.googleapis.com/v4"

# Nur Lesezugriff. Es gibt zu jedem Scope eine "writeonly"-Variante -
# die fordern wir bewusst nicht an, damit nie etwas zurueckgeschrieben
# werden kann, auch nicht versehentlich.
SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    # Gewicht, Groesse, Geburtsdatum - erspart die Fragen beim ersten Login,
    # sofern sie im Fitbit-Profil eingetragen sind
    "https://www.googleapis.com/auth/googlehealth.profile.readonly",
    # Zeitzone und Einheiten - ohne Zeitzone kippen Tagesgrenzen
    "https://www.googleapis.com/auth/googlehealth.settings.readonly",
    # Benachrichtigungen bei unregelmaessigem Herzrhythmus - fuer den
    # Gesundheitsmonitor, falls die Fitbit Air sie ausloest
    "https://www.googleapis.com/auth/googlehealth.irn.readonly",
]

# Von Google vorgegebene Redirect-URI fuer den Kopieren-Einfuegen-Ablauf
REDIRECT_URI = "https://www.google.com"
