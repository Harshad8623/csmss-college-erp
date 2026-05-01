// CSMSS College ERP — Service Worker for Web Push Notifications
// This file runs in the background even when the browser tab is closed.

const CACHE_NAME = 'csmss-erp-v1';

// ── Install: cache the app shell ─────────────────────────────────────────────
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

// ── Push: fires when server sends a Web Push ──────────────────────────────────
self.addEventListener('push', (event) => {
  let data = {
    title: 'CSMSS College ERP',
    body: 'You have a new notification.',
    icon: '/static/img/college_logo.png',
    badge: '/static/img/college_logo.png',
    tag: 'csmss-notif',
    url: '/notifications/',
    type: 'info',
  };

  if (event.data) {
    try {
      const parsed = event.data.json();
      data = { ...data, ...parsed };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  // Color the notification badge based on type
  const vibrate = data.type === 'danger' ? [200, 100, 200] : [100];

  const options = {
    body: data.body,
    icon: data.icon || '/static/img/college_logo.png',
    badge: data.badge || '/static/img/college_logo.png',
    tag: data.tag || 'csmss-notif',
    renotify: true,         // Always show even if same tag exists
    vibrate: vibrate,
    data: { url: data.url || '/notifications/' },
    actions: [
      { action: 'view', title: '👁 View' },
      { action: 'dismiss', title: '✕ Dismiss' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'CSMSS ERP', options)
  );
});

// ── Notification click: open/focus the app ───────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = (event.notification.data && event.notification.data.url)
    ? event.notification.data.url
    : '/notifications/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // If there's already an open window, focus it and navigate
      for (const client of windowClients) {
        if ('focus' in client) {
          client.focus();
          client.navigate(targetUrl);
          return;
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
