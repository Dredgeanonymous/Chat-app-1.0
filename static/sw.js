// static/sw.js

// keep the SW super-minimal so Bubblewrap/PWA install works
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// optional: pass-through fetch so SW never blocks requests
self.addEventListener('fetch', () => {});
