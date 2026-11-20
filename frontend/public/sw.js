// Private API responses and map tiles are deliberately excluded from the shell cache.
const shell = 'waytogo-art-v1';
const assets = ['/compass.svg','/icon-192.png','/icon-512.png','/art/valley.webp','/art/kyoto.webp','/art/alps.webp','/art/tainan.webp'];
self.addEventListener('install', e => e.waitUntil(caches.open(shell).then(c => c.addAll(assets))));
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('waytogo-art-') && k !== shell).map(k => caches.delete(k))))));
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method === 'GET' && url.origin === self.location.origin && assets.includes(url.pathname)) {
    e.respondWith(caches.open(shell).then(async c => (await c.match(e.request)) || fetch(e.request)));
  }
});
