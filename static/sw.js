// Alumni AI Progressive Web App (PWA) Service Worker
// Version: alumni-ai-static-v1.0.0

const CACHE_NAME = 'alumni-ai-static-v1.0.0';

// Essential core static assets for offline application shell
const STATIC_ASSETS = [
    '/',
    '/manifest.webmanifest',
    '/logo.png',
    '/icon-192.png',
    '/icon-512.png',
    '/icon-maskable.png',
    '/apple-touch-icon.png'
];

// Install Event: Pre-cache core application shell
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Alumni AI SW] Pre-caching static app shell');
            return cache.addAll(STATIC_ASSETS);
        }).then(() => {
            return self.skipWaiting();
        })
    );
});

// Activate Event: Clean up stale caches and claim clients immediately
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((name) => {
                    if (name !== CACHE_NAME) {
                        console.log('[Alumni AI SW] Purging obsolete cache:', name);
                        return caches.delete(name);
                    }
                })
            );
        }).then(() => {
            return self.clients.claim();
        })
    );
});

// Fetch Event: Smart routing & caching
self.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);

    // 1. API Calls (/api/...): Strictly Network-First
    // NEVER cache private chats, auth tokens, voice recordings, or streaming responses
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request).catch(() => {
                // Return clean, informative JSON response when network is unavailable
                return new Response(
                    JSON.stringify({
                        error: 'Offline',
                        offline: true,
                        message: 'You are currently offline. Please reconnect to use Alumni AI reasoning engines.'
                    }),
                    {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' }
                    }
                );
            })
        );
        return;
    }

    // 2. Navigation Requests (Page reloads, opening app): Stale-While-Revalidate with Cache Fallback
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
                    }
                    return networkResponse;
                })
                .catch(() => {
                    // Fall back to cached app shell
                    return caches.match('/') || caches.match(request);
                })
        );
        return;
    }

    // 3. Static Assets (Images, Icons, CSS, JS, Fonts): Cache-First with Network Fallback
    event.respondWith(
        caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
                // Revalidate in background for freshest assets
                fetch(request).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, networkResponse));
                    }
                }).catch(() => {});
                return cachedResponse;
            }

            // Not in cache: fetch from network and cache successful GET responses
            return fetch(request).then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200 && request.method === 'GET') {
                    // Only cache same-origin or trusted CDN resources
                    if (url.origin === location.origin || url.hostname.includes('cdn') || url.hostname.includes('fonts.')) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
                    }
                }
                return networkResponse;
            });
        })
    );
});
