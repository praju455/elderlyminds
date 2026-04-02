import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { BottomNav } from './BottomNav'
import { ElderSticker } from './stickers'
import type React from 'react'
import { getBackendHealth } from '../lib/api'

function BackendOfflineIcon() {
  return (
    <div
      className="flex h-10 w-10 items-center justify-center rounded-2xl border border-rose/30 bg-rose/12 text-rose shadow-soft"
      title="Backend is not connected"
      aria-label="Backend is not connected"
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4.9 19.1A10 10 0 0 1 12 16a10 10 0 0 1 7.1 3.1" />
        <path d="M8.5 15.5A5 5 0 0 1 12 14a5 5 0 0 1 3.5 1.5" />
        <path d="M12 20h.01" />
        <path d="M2 2l20 20" />
      </svg>
    </div>
  )
}

export function AppShell({
  title,
  subtitle,
  showNav = true,
  children,
}: {
  title: string
  subtitle?: string
  showNav?: boolean
  children: React.ReactNode
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [backendConnected, setBackendConnected] = useState(true)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return

    const ctx = gsap.context(() => {
      const cards = el.querySelectorAll('[data-float-card]')
      gsap.fromTo(
        cards,
        { y: 18, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.6, stagger: 0.06, ease: 'power2.out' },
      )
    }, el)

    return () => ctx.revert()
  }, [])

  useEffect(() => {
    let active = true

    const checkBackend = async () => {
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), 4000)
      try {
        await getBackendHealth(controller.signal)
        if (active) setBackendConnected(true)
      } catch {
        if (active) setBackendConnected(false)
      } finally {
        window.clearTimeout(timeout)
      }
    }

    void checkBackend()

    const onFocus = () => {
      void checkBackend()
    }
    const onOnline = () => {
      void checkBackend()
    }
    const pollId = window.setInterval(() => {
      void checkBackend()
    }, 30000)

    window.addEventListener('focus', onFocus)
    window.addEventListener('online', onOnline)

    return () => {
      active = false
      window.clearInterval(pollId)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('online', onOnline)
    }
  }, [])

  return (
    <>
      <div ref={ref} className="mx-auto min-h-[100svh] w-full max-w-[430px] px-4 pb-28 pt-6">
        <header className="mb-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold tracking-[0.18em] text-ink/60">BHUMI</p>
              <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-ink">{title}</h1>
              {subtitle ? <p className="mt-1 text-base text-ink/70">{subtitle}</p> : null}
            </div>
            <div className="mt-1 flex items-center gap-2">
              {!backendConnected ? <BackendOfflineIcon /> : null}
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/70 shadow-soft ring-1 ring-black/5">
                <ElderSticker className="h-9 w-9" tone="mint" />
              </div>
            </div>
          </div>
        </header>

        <div className="space-y-4">{children}</div>
      </div>
      {showNav ? <BottomNav /> : null}
    </>
  )
}
