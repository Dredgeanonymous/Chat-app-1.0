// Minimal no-op SW just to satisfy PWA install requirements.
self.addEventListener('install', (e) => {
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  // Claim clients so the SW is active immediately.
  e.waitUntil(self.clients.claim());
});

self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());
// (Optional) add fetch handler if you want offline caching later.
