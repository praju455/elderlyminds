/* eslint-disable @typescript-eslint/no-explicit-any */
import barba from '@barba/core'
import { gsap } from 'gsap'

type NavigateArgs = {
  namespace: string
  container: HTMLElement
}

let started = false

export function initBarba({ onNavigate }: { onNavigate: (next: NavigateArgs) => void }) {
  if (started) return
  started = true

  gsap.defaults({ ease: 'power2.out', duration: 0.5 })

  barba.init({
    preventRunning: true,
    timeout: 8000,
    transitions: [
      {
        name: 'eldermind',
        async leave(this: any, data: any) {
          const done: () => void = this.async()
          const current = data.current.container as HTMLElement

          // Let taps feel immediate.
          gsap.to(current, { opacity: 0, y: -10, duration: 0.35, onComplete: done })
        },
        enter(data: any) {
          const next = data.next.container as HTMLElement
          gsap.set(next, { opacity: 0, y: 14 })
          gsap.to(next, { opacity: 1, y: 0, duration: 0.55 })
        },
        async afterEnter(data: any) {
          const next = data.next.container as HTMLElement
          onNavigate({ namespace: data.next.namespace, container: next })
        },
      },
    ],
    prevent({ el, event }: any) {
      const anchor = el as HTMLAnchorElement
      if (!anchor || anchor.tagName !== 'A') return false
      if (anchor.target && anchor.target !== '_self') return true
      if (anchor.hasAttribute('download')) return true
      if (event instanceof MouseEvent && (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey))
        return true
      const url = new URL(anchor.href, window.location.href)
      if (url.origin !== window.location.origin) return true
      return false
    },
  })

  // Preload pages gently in the background.
  barba.prefetch?.()
}

