const CACHE = 'viora-shell-v15.8.4';
const SHELL = ['/', '/static/favicon.svg', '/static/viora-logo.svg', '/static/viora-agent-mark.svg', '/static/viora-chart-art.png', '/static/viora-chart-art-v2.png', '/static/viora-v156.css', '/static/viora-v156.js', '/static/viora-v157.js', '/static/viora-v157.css', '/static/viora-v158.js', '/static/viora-v158.css', '/static/fonts/QurovaDEMO-Bold.otf', '/static/manifest.webmanifest'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('viora-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname === '/status' || url.pathname.startsWith('/command')) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put('/', response.clone()));
      return response;
    }).catch(async () => (await caches.match('/')) || Response.error()));
    return;
  }
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
      return response;
    })));
  }
});
