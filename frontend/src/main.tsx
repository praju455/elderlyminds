import { createRoot } from 'react-dom/client'
import './index.css'
import { initBarba } from './transitions/barba'
import { renderPage } from './renderPage'

const container = document.querySelector('[data-barba="container"]') as HTMLElement | null
const rootEl = document.getElementById('root')

if (!rootEl) throw new Error('Missing #root element')

// Initial mount
let currentRoot = createRoot(rootEl)
renderPage({
  root: currentRoot,
  page: document.body.dataset.page || container?.dataset.barbaNamespace || 'home',
})

// App-like transitions (no hard reload feeling)
initBarba({
  onNavigate: (next) => {
    const nextRootEl = next.container.querySelector('#root') as HTMLElement | null
    if (!nextRootEl) return

    currentRoot.unmount()
    currentRoot = createRoot(nextRootEl)
    renderPage({ root: currentRoot, page: next.namespace })
  },
})

async function clearOldServiceWorkers() {
  if (!('serviceWorker' in navigator)) return
  const regs = await navigator.serviceWorker.getRegistrations()
  await Promise.all(regs.map((reg) => reg.unregister()))
  if ('caches' in window) {
    const keys = await caches.keys()
    await Promise.all(keys.map((key) => caches.delete(key)))
  }
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    if (import.meta.env.DEV) {
      clearOldServiceWorkers().catch(() => {})
      return
    }
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
