// =============================================================================
// sw.js — TCU++ Service Worker
// Handles push notifications even when the browser is closed.
// =============================================================================

const CACHE_NAME = 'tcuplusplus-v1';

// ── Install ───────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
});

// ── Activate ──────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(clients.claim());
});

// ── Push notifications ────────────────────────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'TCU++', body: event.data.text() };
  }

  const title   = payload.title || 'TCU++';
  const options = {
    body:    payload.body || '',
    icon:    payload.icon || '/icon-192.png',
    badge:   '/icon-192.png',
    vibrate: [200, 100, 200],
    tag:     'tcu-alert',
    renotify: true,
    data: { url: '/' }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// ── Notification click — open dashboard ───────────────────────────────────────
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(clientList => {
        // Focus existing window if open
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            return client.focus();
          }
        }
        // Otherwise open new window
        return clients.openWindow('/dashboard');
      })
  );
});
