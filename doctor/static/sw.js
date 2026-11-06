// PEDO ALIGN Progressive Web App Service Worker
// Version 4.0 - Secure Static-Only Cache (No Private Healthcare Data Cached)
const CACHE_NAME = 'pedo-align-v4';

// Essential public static assets for offline branding and app shell only
const STATIC_ASSETS = [
    '/manifest.json',
    '/static/android-chrome-192x192.png',
    '/static/android-chrome-512x512.png',
    '/static/apple-touch-icon.png',
    '/static/favicon.ico',
    '/static/sidebar_glowing_logo.png',
    '/static/doctor/css/custom.css',
    '/static/patient/css/patient.css',
    '/static/doctor/js/main.js'
];

// Paths that must NEVER be cached to protect patient privacy and clinical records
const NEVER_CACHE_PATTERNS = [
    '/dashboard',
    '/patients',
    '/patient',
    '/media/',
    '/admin',
    '/login',
    '/logout',
    '/register',
    '/join',
    '/clinical',
    '/photos',
    '/prescriptions',
    '/download'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch((err) => {
                console.warn('PEDO ALIGN: Static cache addAll warning:', err);
            });
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Only handle GET requests
    if (event.request.method !== 'GET') return;
    
    // Ignore non-http requests (e.g. chrome-extension://)
    if (!event.request.url.startsWith('http')) return;

    const url = new URL(event.request.url);

    // SECURITY CHECK:
    // Strictly bypass cache for all dynamic, authenticated, and healthcare media routes
    const isSensitive = NEVER_CACHE_PATTERNS.some(pattern => url.pathname.includes(pattern));
    if (isSensitive) {
        // Direct network fetch without storing in cache
        event.respondWith(fetch(event.request));
        return;
    }

    // Network-first strategy for other requests with static cache fallback
    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                return networkResponse;
            })
            .catch(() => {
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    // Return clean offline notification for navigation requests
                    if (event.request.mode === 'navigate') {
                        return new Response(
                            '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>PEDO ALIGN - Offline</title><style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background:#F4F9FF;color:#1e293b;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px;box-sizing:border-box;text-align:center}.card{background:#fff;padding:32px 24px;border-radius:24px;max-width:360px;width:100%;box-shadow:0 10px 25px -5px rgba(0,0,0,0.08);border:1px solid #e2e8f0}h1{font-size:1.25rem;color:#0f172a;margin:12px 0 8px}p{font-size:0.875rem;color:#64748b;line-height:1.5;margin:0 0 20px}button{background:#2878F0;color:#fff;border:none;padding:12px 24px;border-radius:12px;font-weight:700;font-size:0.875rem;cursor:pointer}</style></head><body><div class="card"><div style="font-size:2.5rem">📡</div><h1>You are Offline</h1><p>PEDO ALIGN clinical records require an active connection for patient security. Reconnect to resume.</p><button onclick="window.location.reload()">Retry Connection</button></div></body></html>',
                            {
                                status: 503,
                                statusText: 'Service Unavailable',
                                headers: { 'Content-Type': 'text/html' }
                            }
                        );
                    }
                });
            })
    );
});
