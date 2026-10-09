/* ResolveAI Service Worker - Handles push notifications */
'use strict';

const CACHE_NAME = 'resolveai-v1';

// Install event - cache essential assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll([
                '/',
                '/static/css/style.css',
                '/static/js/app.js',
            ]);
        })
    );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            );
        })
    );
    self.clients.claim();
});

// Push event - show notification when push message arrives
self.addEventListener('push', (event) => {
    let data = {};
    try {
        if (event.data) {
            data = event.data.json();
        }
    } catch (e) {
        data = {
            title: 'ResolveAI Notification',
            body: event.data ? event.data.text() : 'New update available',
        };
    }

    const title = data.title || 'ResolveAI';
    const options = {
        body: data.body || 'You have a new notification',
        icon: '/static/img/icon-192.png',
        badge: '/static/img/icon-72.png',
        tag: data.tag || 'resolveai-notification',
        renotify: true,
        requireInteraction: false,
        data: {
            url: data.url || '/',
            ticketId: data.ticketId || null,
        },
        actions: data.actions || [
            { action: 'view', title: 'View' },
            { action: 'dismiss', title: 'Dismiss' },
        ],
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Notification click event
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const notificationData = event.notification.data || {};
    let targetUrl = notificationData.url || '/';

    if (event.action === 'dismiss') {
        return;
    }

    if (event.action === 'view' || !event.action) {
        event.waitUntil(
            clients.matchAll({ type: 'window', includeUncontrolled: true })
                .then((clientList) => {
                    // If a window is already open, focus it
                    for (const client of clientList) {
                        if (client.url.includes(self.location.origin) && 'focus' in client) {
                            client.focus();
                            if (notificationData.ticketId) {
                                client.navigate(targetUrl);
                            }
                            return;
                        }
                    }
                    // Otherwise open a new window
                    if (clients.openWindow) {
                        return clients.openWindow(targetUrl);
                    }
                })
        );
    }
});

// Message event - handle messages from the main thread
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
