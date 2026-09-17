// Zugangsdaten der Web-App. Die sehen nach Geheimnis aus, sind aber keins:
// Google baut sie bewusst in jede Web-App ein, sie stecken in jedem Browser,
// der die Seite oeffnet. Geschuetzt wird ueber die Regeln in firestore.rules -
// ohne Anmeldung kommt niemand an Daten, und angemeldet nur an die eigenen.
const firebaseConfig = {
  apiKey: "AIzaSyA9yJlQ5A6A2PJU1GlrcR2S6USiLs9yuOY",
  authDomain: "claude-health-d35b7.firebaseapp.com",
  projectId: "claude-health-d35b7",
  storageBucket: "claude-health-d35b7.firebasestorage.app",
  messagingSenderId: "637344784908",
  appId: "1:637344784908:web:5432d5595117a023514429"
};
