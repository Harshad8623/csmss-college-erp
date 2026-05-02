// CSMSS College ERP — Service Worker for Web Push Notifications
// This file runs in the background even when the browser tab is closed.
// IMPORTANT: This file is served from the ROOT (/sw.js) so it can control all pages.

const CACHE_NAME = 'csmss-erp-v2';

// The site origin is injected by the server via the /sw.js route
// For background push, all asset URLs MUST be absolute (full https://... URLs)
const SITE_URL = self.registration.scope.replace(/\/$/, ''); // e.g. https://csmss-erp.onrender.com

// ── Install: activate immediately ────────────────────────────────────────────
self.addEventListener('install', (event) => {
  console.log('[SW] Installed');
  self.skipWaiting(); // Activate immediately, don't wait for old SW to die
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Activated, claiming clients...');
  event.waitUntil(clients.claim()); // Take control of all open pages immediately
});

// ── Push: fires when server sends a Web Push ──────────────────────────────────
// This fires even when the browser is CLOSED (on Android/Desktop Chrome)
self.addEventListener('push', (event) => {
  console.log('[SW] Push event received');

  let data = {
    title: 'CSMSS College ERP',
    body: 'You have a new notification.',
    type: 'info',
    url: '/notifications/',
  };

  if (event.data) {
    try {
      const parsed = event.data.json();
      data = { ...data, ...parsed };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  console.log('[SW] Showing notification:', data.title, data.body);

  // Vibration pattern: urgent = double pulse, otherwise single
  const vibrate = data.type === 'danger' ? [200, 100, 200, 100, 200] : [150, 50, 150];

  const options = {
    body: data.body,
    // MUST use absolute URLs here — relative paths don't work when browser is closed
    icon: SITE_URL + '/static/img/college_logo.png',
    badge: SITE_URL + '/static/img/college_logo.png',
    tag: 'csmss-notif-' + (data.type || 'info'),
    renotify: true,           // Always show even if same tag exists
    vibrate: vibrate,
    requireInteraction: false, // Auto-dismiss after a few seconds
    data: {
      url: data.url || '/notifications/',
      type: data.type,
    },
    actions: [
      { action: 'view',    title: '👁 View' },
      { action: 'dismiss', title: '✕ Dismiss' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'CSMSS ERP', options)
      .then(() => console.log('[SW] Notification shown successfully'))
      .catch(err => console.error('[SW] showNotification failed:', err))
  );
});

// ── Notification click: open/focus the app ───────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = SITE_URL + (
    (event.notification.data && event.notification.data.url)
      ? event.notification.data.url
      : '/notifications/'
  );

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // If there's already an open window for this site, focus it and navigate
      for (const client of windowClients) {
        if (client.url.startsWith(SITE_URL) && 'focus' in client) {
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

// ── Push subscription change: re-subscribe automatically ─────────────────────
// Fires when the browser invalidates our subscription (e.g. push server rotates keys)
// IMPORTANT: we must re-subscribe HERE — the page is not open when this fires.
self.addEventListener('pushsubscriptionchange', (event) => {
  console.log('[SW] pushsubscriptionchange fired — re-subscribing...');

  const SITE_URL_BASE = self.registration.scope.replace(/\/$/, '');

  event.waitUntil(
    (async () => {
      try {
        // Re-subscribe with the same application server key as before
        const appServerKey = event.oldSubscription
          ? event.oldSubscription.options.applicationServerKey
          : null;

        const newSub = await self.registration.pushManager.subscribe({
          userVisibleOnly: true,
          ...(appServerKey ? { applicationServerKey: appServerKey } : {}),
        });

        // POST the new subscription to our server
        await fetch(SITE_URL_BASE + '/notifications/api/subscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newSub.toJSON()),
          credentials: 'include',
        });
        console.log('[SW] Re-subscribed successfully after pushsubscriptionchange');
      } catch (err) {
        console.error('[SW] Failed to re-subscribe after pushsubscriptionchange:', err);
      }
    })()
  );
});
