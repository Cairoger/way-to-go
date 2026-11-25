// Private API responses and map tiles are deliberately excluded from the shell cache.
const shell = 'waytogo-art-v2';
const assets = [
  '/offline.html',
  '/offline-reader.js',
  '/offline-reader.css',
  '/compass.svg',
  '/icon-192.png',
  '/icon-512.png',
  '/art/valley.webp',
  '/art/kyoto.webp',
  '/art/alps.webp',
  '/art/tainan.webp',
];
self.addEventListener('install', (e) =>
  e.waitUntil(
    caches
      .open(shell)
      .then((c) => c.addAll(assets))
      .then(() => self.skipWaiting()),
  ),
);
self.addEventListener('activate', (e) =>
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith('waytogo-art-') && k !== shell)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  ),
);
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (
    e.request.mode === 'navigate' &&
    e.request.method === 'GET' &&
    url.origin === self.location.origin &&
    url.pathname === '/' &&
    !url.searchParams.has('invite')
  ) {
    e.respondWith(
      fetch(e.request).catch(
        async () => (await (await caches.open(shell)).match('/offline.html')) || Response.error(),
      ),
    );
    return;
  }
  if (
    e.request.method === 'GET' &&
    url.origin === self.location.origin &&
    assets.includes(url.pathname)
  ) {
    e.respondWith(
      caches.open(shell).then(async (c) => (await c.match(e.request)) || fetch(e.request)),
    );
  }
});
async function showMention() {
  let noticeId;
  try {
    const response = await fetch('/api/v1/notifications', {
      credentials: 'same-origin',
      cache: 'no-store',
      signal: AbortSignal.timeout(4000),
    });
    if (response.ok) {
      const inbox = await response.json();
      const unread = inbox.items.filter((item) => !item.read);
      if (unread.length === 1) noticeId = unread[0].id;
    }
  } catch {
    // Offline recipients can still open the inbox once they reconnect.
  }
  await self.registration.showNotification('WayToGo 旅伴手札', {
    body: '旅伴在討論中提及了你。',
    icon: '/icon-192.png',
    tag: 'waytogo-mention',
    data: { noticeId },
  });
}
self.addEventListener('push', (event) => {
  event.waitUntil(showMention());
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL('/?notifications=1', self.location.origin);
  const id = event.notification.data?.noticeId;
  if (typeof id === 'string') target.hash = 'notice=' + encodeURIComponent(id);
  event.waitUntil(clients.openWindow(target.href));
});
