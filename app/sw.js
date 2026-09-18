/* Offline-Huelle der App.
 *
 * Nur die App selbst wird zwischengespeichert (Seite, Skripte, Icons), nie
 * Gesundheitsdaten - die liegen in Firestore bzw. im Zwischenspeicher von
 * start.js. Eigene Dateien: erst Netz, dann Ablage, damit ein neuer Stand
 * sofort ankommt. Firebase-Bibliotheken: erst Ablage, sie tragen die
 * Versionsnummer im Pfad und aendern sich nie.
 */
const ABLAGE = "claude-health-v2";
const HUELLE = ["./", "index.html", "start.js", "manifest.webmanifest",
                "icon.svg", "icon-180.png", "icon-192.png", "icon-512.png",
                "../js/firebase-config.js"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(ABLAGE).then(c => c.addAll(HUELLE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(n => Promise.all(n.filter(x => x !== ABLAGE).map(x => caches.delete(x))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;

  if (url.hostname === "www.gstatic.com" && url.pathname.startsWith("/firebasejs/")) {
    e.respondWith(caches.match(e.request).then(t => t || fetch(e.request).then(r => {
      const kopie = r.clone();
      caches.open(ABLAGE).then(c => c.put(e.request, kopie));
      return r;
    })));
    return;
  }

  if (url.origin !== location.origin) return;   // Firestore, Anmeldung: nie anfassen
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const kopie = r.clone(); caches.open(ABLAGE).then(c => c.put(e.request, kopie)); }
    return r;
  }).catch(() => caches.match(e.request, { ignoreSearch: true })
    .then(t => t || caches.match("index.html"))));
});
