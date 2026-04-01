const CACHE_NAME = 'eldermind-v3'

const CORE_ASSETS = [
  '/',
  '/index.html',
  '/medication.html',
  '/activity.html',
  '/alert.html',
  '/summary.html',
  '/support.html',
  '/manifest.webmanifest',
  '/pwa-icon.svg',
]

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS)))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      await self.clients.claim()
    })(),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return

  if (request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(request)
          const cache = await caches.open(CACHE_NAME)
          cache.put('/index.html', response.clone())
          return response
        } catch {
          return (await caches.match('/index.html')) || Response.error()
        }
      })(),
    )
    return
  }

  event.respondWith(
    (async () => {
      const cached = await caches.match(request)
      if (cached) return cached

      try {
        const response = await fetch(request)
        const url = new URL(request.url)
        if (url.origin === self.location.origin && response.ok) {
          const cache = await caches.open(CACHE_NAME)
          cache.put(request, response.clone())
        }
        return response
      } catch {
        if (request.mode === 'navigate') {
          return (await caches.match('/index.html')) || Response.error()
        }
        return Response.error()
      }
    })(),
  )
})

self.addEventListener('push', (event) => {
  const payload = (() => {
    try {
      return event.data ? event.data.json() : {}
    } catch {
      return { title: 'Bhumi reminder', body: event.data?.text() || 'Open the app to check the latest update.' }
    }
  })()
  const title = payload.title || 'Bhumi reminder'
  const options = {
    body: payload.body || 'Open the app to continue.',
    icon: '/pwa-icon.svg',
    badge: '/pwa-icon.svg',
    data: { href: payload.href || '/index.html' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('message', (event) => {
  const data = event.data || {}
  if (data?.type !== 'SHOW_NOTIFICATION') return
  event.waitUntil(
    self.registration.showNotification(data.title || 'Bhumi', {
      body: data.body || 'Open the app to continue.',
      icon: '/pwa-icon.svg',
      badge: '/pwa-icon.svg',
      data: { href: data.href || '/index.html' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const href = event.notification.data?.href || '/index.html'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate?.(href)
          return client.focus()
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(href)
      return undefined
    }),
  )
})
