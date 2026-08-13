// Service worker mínimo: habilita instalación PWA. Sin cache de API (datos siempre frescos).
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());
self.addEventListener('fetch', e => {});
