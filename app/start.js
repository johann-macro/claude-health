/* Anmeldung, Daten laden, App starten.
 *
 * Aufbau: Diese Datei kuemmert sich um alles, was mit Firebase zu tun hat.
 * Die eigentliche App (aus dashboard/template.html) weiss davon nichts - sie
 * bekommt ihre Daten in window.__DATEN__ gereicht und wird dann gestartet.
 *
 * Einstellungen, Logbuch und Plaene liegen ebenfalls in Firestore statt im
 * Browser. Nur so sehen Handy, iPad und Rechner dasselbe. Damit der App-Code
 * unveraendert bleiben konnte, ersetzt der Bau jedes "localStorage." durch
 * "CHSpeicher." - dieselben Methoden, andere Ablage.
 */
(function () {
  "use strict";

  const CACHE = "claudehealth.zwischenspeicher";
  const meldung = (text, art) => {
    const el = document.getElementById("anmeldefehler");
    if (!el) return;
    el.textContent = text || "";
    el.className = "anmeldefehler" + (art ? " " + art : "");
  };

  /* ---------- Speicher: gleiche Methoden wie localStorage, andere Ablage ---- */
  window.CHSpeicher = {
    daten: {},
    _ref: null,
    _warte: null,
    getItem(k) { return Object.prototype.hasOwnProperty.call(this.daten, k) ? this.daten[k] : null; },
    setItem(k, v) { this.daten[k] = String(v); this._sichern(); },
    removeItem(k) { delete this.daten[k]; this._sichern(); },
    clear() { this.daten = {}; this._sichern(); },
    // Gesammelt schreiben: beim Antippen einer Logbuchzeile sollen nicht
    // drei Schreibvorgaenge hintereinander losgehen.
    _sichern() {
      if (!this._ref) return;
      clearTimeout(this._warte);
      this._warte = setTimeout(() => {
        this._ref.set({ werte: this.daten }, { merge: true })
          .catch(e => console.warn("Einstellungen nicht gespeichert:", e.message));
      }, 600);
    },
  };

  /* ---------- Firebase ---------------------------------------------------- */
  firebase.initializeApp(firebaseConfig);
  const auth = firebase.auth();
  const db = firebase.firestore();

  /* ---------- Anmeldung --------------------------------------------------- */
  document.getElementById("anmeldeform").addEventListener("submit", async (e) => {
    e.preventDefault();
    const mail = document.getElementById("a-mail").value.trim();
    const pass = document.getElementById("a-pass").value;
    if (!mail || !pass) return meldung("Bitte E-Mail und Passwort eingeben.");
    meldung("Anmeldung läuft …", "still");
    try {
      await auth.signInWithEmailAndPassword(mail, pass);
    } catch (err) {
      meldung(({
        "auth/invalid-credential": "E-Mail oder Passwort stimmt nicht.",
        "auth/wrong-password": "E-Mail oder Passwort stimmt nicht.",
        "auth/user-not-found": "Zu dieser E-Mail gibt es kein Konto.",
        "auth/too-many-requests": "Zu viele Versuche. Bitte später erneut.",
        "auth/network-request-failed": "Keine Verbindung.",
      })[err.code] || ("Anmeldung fehlgeschlagen: " + err.code));
    }
  });

  window.abmelden = function () {
    try { localStorage.removeItem(CACHE); } catch (e) { /* egal */ }
    auth.signOut().then(() => location.reload());
  };

  /* ---------- Daten laden ------------------------------------------------- */
  async function datenLaden(uid) {
    const nutzer = db.collection("nutzer").doc(uid);

    const [stamm, tage, einstellungen] = await Promise.all([
      nutzer.get(),
      nutzer.collection("tage").orderBy("date").get(),
      nutzer.collection("app").doc("einstellungen").get(),
    ]);

    CHSpeicher._ref = nutzer.collection("app").doc("einstellungen");
    CHSpeicher.daten = (einstellungen.exists && einstellungen.data().werte) || {};

    const stammdaten = stamm.exists ? stamm.data() : {};
    return {
      app: "Claude Health",
      generated_at: stammdaten.letzter_abgleich || null,
      is_demo: false,
      profile: Object.assign({ baseline_min_days: 7 }, stammdaten.profil || {}),
      journal_impact: [],
      journal_labels: {},
      days: tage.docs.map(d => d.data()),
    };
  }

  function starten(daten) {
    window.__DATEN__ = daten;
    document.getElementById("anmeldung").hidden = true;
    document.getElementById("laden").hidden = true;
    document.getElementById("app").hidden = false;
    try { claudeHealthStart(); } catch (e) {
      document.getElementById("laden").hidden = false;
      document.getElementById("laden").innerHTML =
        '<div class="ladetext">Die App konnte nicht starten.<br><small>' +
        (e.message || e) + "</small></div>";
      throw e;
    }
    pruefeOnboarding();
  }

  /* ---------- Geburtsdatum: das Einzige, was Google nicht liefert ---------- */
  function pruefeOnboarding() {
    let profil = {};
    try { profil = JSON.parse(CHSpeicher.getItem("claudehealth.profil") || "{}") || {}; }
    catch (e) { profil = {}; }
    if (profil.geburtstag) return;

    const p = (window.__DATEN__ && window.__DATEN__.profile) || {};
    const box = document.getElementById("onboarding");
    document.getElementById("ob-uebernommen").innerHTML =
      [p.alter ? "Alter " + Math.round(p.alter) + " Jahre" : null,
       p.gewicht_kg ? p.gewicht_kg + " kg" : null,
       p.groesse_cm ? p.groesse_cm + " cm" : null,
       p.zeitzone || null]
        .filter(Boolean).map(t => "<span>" + t + "</span>").join("");
    box.hidden = false;

    document.getElementById("ob-speichern").addEventListener("click", () => {
      const wert = document.getElementById("ob-gebtag").value;
      if (!wert) { document.getElementById("ob-fehler").textContent =
        "Bitte ein Datum angeben."; return; }
      const jahre = (Date.now() - new Date(wert).getTime()) / 31557600000;
      if (jahre < 10 || jahre > 110) { document.getElementById("ob-fehler").textContent =
        "Bitte ein plausibles Geburtsdatum angeben."; return; }
      profil.geburtstag = wert;
      CHSpeicher.setItem("claudehealth.profil", JSON.stringify(profil));
      box.hidden = true;
      if (window.CH) window.CH.render();
    });
    document.getElementById("ob-spaeter").addEventListener("click", () => { box.hidden = true; });
  }

  /* ---------- Installierbar und offline startbar ------------------------ */
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(e => console.warn("Offline-Hülle:", e.message));
  }

  /* ---------- Ablauf ------------------------------------------------------ */
  auth.onAuthStateChanged(async (nutzer) => {
    if (!nutzer) {
      document.getElementById("laden").hidden = true;
      document.getElementById("anmeldung").hidden = false;
      return;
    }
    document.getElementById("anmeldung").hidden = true;
    document.getElementById("laden").hidden = false;

    try {
      const daten = await datenLaden(nutzer.uid);
      try { localStorage.setItem(CACHE, JSON.stringify(daten)); } catch (e) { /* voll */ }
      starten(daten);
    } catch (err) {
      // Ohne Netz die zuletzt geladenen Daten zeigen, statt gar nichts.
      let zwischen = null;
      try { zwischen = JSON.parse(localStorage.getItem(CACHE) || "null"); } catch (e) { /* egal */ }
      if (zwischen) {
        starten(zwischen);
        const hinweis = document.createElement("div");
        hinweis.className = "offlinehinweis";
        hinweis.textContent = "Keine Verbindung — zuletzt geladener Stand.";
        document.getElementById("app").appendChild(hinweis);
        setTimeout(() => hinweis.remove(), 5000);
      } else {
        document.getElementById("laden").innerHTML =
          '<div class="ladetext">Daten konnten nicht geladen werden.<br><small>' +
          (err.message || err) + "</small></div>";
      }
    }
  });
})();
