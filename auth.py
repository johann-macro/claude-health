"""Einmalige Anmeldung bei Google + Token-Verwaltung.

Wichtig zum Verstaendnis: Dein Google-Passwort kommt hier NIRGENDS vor.
Die Anmeldung passiert im Browser direkt bei Google. Dieses Script sieht
nur den Freigabe-Code, den Google danach ausstellt, und tauscht ihn gegen
ein Token. Das ist der Grund, warum es hier kein Passwort-Feld gibt -
nicht Nachlaessigkeit, sondern der vorgesehene Weg.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from getpass import getpass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from config import CLIENT_FILE, REDIRECT_URI, SCOPES, SECRETS_DIR, TOKEN_FILE


def _lock_down(path) -> None:
    """Zugriff auf die Datei/den Ordner auf den aktuellen Benutzer beschraenken.

    Unter Linux/macOS ueber chmod (700 Ordner / 600 Dateien), unter Windows
    ueber icacls - dort haette chmod keine echte Wirkung.
    """
    if os.name == "nt":
        user = os.environ.get("USERNAME")
        if not user:
            return
        args = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)"]
        if path.is_dir():
            args = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"]
        subprocess.run(args, capture_output=True, check=False)
    else:
        path.chmod(stat.S_IRWXU if path.is_dir() else stat.S_IRUSR | stat.S_IWUSR)


def _require_terminal() -> None:
    """Ohne echtes Terminal keine Eingabe von Zugangsdaten."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit(
            "\nABBRUCH: Kein echtes Terminalfenster.\n"
            "Dieses Script fragt ein Client-Secret ab und muss die Eingabe\n"
            "verdecken koennen. Bitte in PowerShell direkt ausfuehren, nicht\n"
            "ueber einen Assistenten, eine IDE-Konsole oder eine Pipe.\n"
        )


def _ensure_secrets_dir():
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    _lock_down(SECRETS_DIR)


def _load_client() -> dict:
    """Client-ID und -Secret einlesen, beim ersten Mal abfragen."""
    if CLIENT_FILE.exists():
        return json.loads(CLIENT_FILE.read_text(encoding="utf-8"))

    _require_terminal()
    print("\n" + "=" * 62)
    print("  EINMALIGE EINRICHTUNG - Zugangsdaten deines Cloud-Projekts")
    print("=" * 62)
    print("Beide Werte findest du in der Google Cloud Console unter")
    print("'APIs & Dienste' > 'Anmeldedaten' > dein OAuth-Client.\n")

    client_id = input("Client-ID       : ").strip()
    if not client_id:
        sys.exit("Keine Client-ID eingegeben. Abbruch.")

    # Verdeckte Eingabe: erscheint nicht auf dem Bildschirm und landet
    # nicht im Verlauf des Terminals.
    client_secret = getpass("Client-Secret   : ").strip()
    if not client_secret:
        sys.exit("Kein Client-Secret eingegeben. Abbruch.")

    data = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    _ensure_secrets_dir()
    CLIENT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _lock_down(CLIENT_FILE)
    print(f"\nGespeichert in {CLIENT_FILE} (nur fuer dich lesbar).")
    return data


def _save_token(creds: Credentials) -> None:
    _ensure_secrets_dir()
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    _lock_down(TOKEN_FILE)


def login() -> Credentials:
    """Vollstaendige Erstanmeldung mit Browser-Freigabe."""
    _require_terminal()
    client = _load_client()

    flow = Flow.from_client_config(client, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, _ = flow.authorization_url(
        access_type="offline",      # damit wir ein Refresh-Token bekommen
        prompt="consent",           # erzwingt die Ausgabe des Refresh-Tokens
        include_granted_scopes="true",
    )

    print("\n" + "=" * 62)
    print("  FREIGABE IM BROWSER")
    print("=" * 62)
    print("\n1. Oeffne diese Adresse (ganze Zeile kopieren):\n")
    print(auth_url)
    print("\n2. Melde dich mit dem Google-Konto an, das zu deinem Fitbit gehoert.")
    print("3. Es erscheint eine Warnung 'App nicht ueberprueft' - das ist deine")
    print("   eigene App. Auf 'Erweitert' > 'Weiter zu ...' klicken.")
    print("4. Alle drei Haken setzen und bestaetigen.")
    print("5. Du landest auf google.com. Kopiere die KOMPLETTE Adresse aus der")
    print("   Adresszeile - darin steht der Code.\n")

    pasted = input("Adresse oder Code hier einfuegen: ").strip()
    if not pasted:
        sys.exit("Nichts eingegeben. Abbruch.")

    code = pasted
    if "code=" in pasted:
        from urllib.parse import parse_qs, unquote, urlparse
        query = urlparse(pasted).query or pasted.split("?", 1)[-1]
        values = parse_qs(query).get("code")
        if not values:
            sys.exit("In der Adresse war kein 'code=' zu finden. Abbruch.")
        code = unquote(values[0])

    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # noqa: BLE001
        sys.exit(
            f"\nDer Code wurde nicht akzeptiert: {exc}\n"
            "Haeufigste Ursachen: der Code wurde schon benutzt (jeder Code gilt\n"
            "nur einmal), oder er ist aelter als ein paar Minuten. Einfach das\n"
            "Script erneut starten und die Freigabe wiederholen.\n"
        )

    creds = flow.credentials
    if not creds.refresh_token:
        sys.exit(
            "\nGoogle hat kein dauerhaftes Token ausgestellt. Bitte unter\n"
            "myaccount.google.com/permissions den Zugriff dieser App entfernen\n"
            "und das Script noch einmal starten.\n"
        )

    _save_token(creds)
    print("\n" + "=" * 62)
    print("  FERTIG - Anmeldung gespeichert.")
    print("=" * 62)
    print(f"Token liegt in {TOKEN_FILE} und wird ab jetzt automatisch erneuert.")
    print("Es wird nie angezeigt, nie protokolliert und nie weitergegeben.\n")
    return creds


def get_credentials() -> Credentials:
    """Gueltige Zugangsdaten liefern - erneuert das Token bei Bedarf still.

    Beim automatischen Abgleich gibt es keine Dateien: dort steht der ganze
    Inhalt von token.json in der Umgebungsvariablen GOOGLE_TOKEN, als
    geschuetztes Geheimnis der Ablaufumgebung. Er wird nie ausgegeben.
    """
    aus_umgebung = os.environ.get("GOOGLE_TOKEN")
    if aus_umgebung:
        creds = Credentials.from_authorized_user_info(json.loads(aus_umgebung), SCOPES)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
        return creds

    if not TOKEN_FILE.exists():
        sys.exit(
            "Noch keine Anmeldung vorhanden.\n"
            "Bitte einmalig ausfuehren:  python auth.py"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds
    sys.exit(
        "Die Anmeldung ist abgelaufen und liess sich nicht erneuern.\n"
        "Bitte einmalig wiederholen:  python auth.py"
    )


if __name__ == "__main__":
    login()
