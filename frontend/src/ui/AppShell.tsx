import { useLayoutEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { BottomNav } from './BottomNav'
import { ElderSticker } from './stickers'
import type React from 'react'

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
            <div className="mt-1 flex h-12 w-12 items-center justify-center rounded-2xl bg-white/70 shadow-soft ring-1 ring-black/5">
              <ElderSticker className="h-9 w-9" tone="mint" />
            </div>
          </div>
        </header>

        <div className="space-y-4">{children}</div>
      </div>
      {showNav ? <BottomNav /> : null}
    </>
  )
}
