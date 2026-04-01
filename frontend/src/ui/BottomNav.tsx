import { useLayoutEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { ElderSticker, HeartPulseSticker, PillSticker, SparkleSticker } from './stickers'
import { getStoredSession } from '../lib/session'
import type React from 'react'

type NavItem = {
  href: string
  label: string
  key: string
  Icon: (props: React.SVGProps<SVGSVGElement>) => React.ReactNode
}

const elderItems: NavItem[] = [
  { key: 'home', href: '/index.html', label: 'Home', Icon: (p) => <ElderSticker {...p} tone="mint" /> },
  { key: 'medication', href: '/medication.html', label: 'Meds', Icon: (p) => <PillSticker {...p} /> },
  { key: 'alert', href: '/alert.html', label: 'Health', Icon: (p) => <HeartPulseSticker {...p} /> },
  { key: 'summary', href: '/summary.html', label: 'Week', Icon: (p) => <SparkleSticker {...p} /> },
  { key: 'settings', href: '/settings.html', label: 'Settings', Icon: (p) => <SparkleSticker {...p} /> },
]

const supportItems: NavItem[] = [
  { key: 'support', href: '/support.html', label: 'Dashboard', Icon: (p) => <ElderSticker {...p} tone="mint" /> },
  { key: 'settings', href: '/settings.html', label: 'Settings', Icon: (p) => <SparkleSticker {...p} /> },
]

function currentKey(items: NavItem[]): string {
  const page = (document.body.dataset.page || 'home').toLowerCase()
  if (page === 'caregiver' || page === 'caretaker' || page === 'support') return 'support'
  if (page === 'activity') return 'alert'
  const match = items.find((it) => it.key === page)
  return match ? match.key : items[0].key
}

export function BottomNav() {
  const ref = useRef<HTMLDivElement | null>(null)
  const session = getStoredSession()
  const isSupport = session?.role === 'support'
  const items = isSupport ? supportItems : elderItems
  const active = currentKey(items)

  const goTo = (href: string) => {
    if (window.location.pathname === href) return
    window.location.assign(href)
  }

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const activeEl = el.querySelector(`[data-active="true"]`) as HTMLElement | null
    if (!activeEl) return
    const ctx = gsap.context(() => {
      gsap.fromTo(activeEl, { y: 6, opacity: 0.7 }, { y: 0, opacity: 1, duration: 0.55, ease: 'elastic.out(1,0.6)' })
    }, el)
    return () => ctx.revert()
  }, [active])

  return (
    <div ref={ref} className="fixed bottom-3 left-0 right-0 z-30 mx-auto w-[min(430px,calc(100%-24px))]">
      <nav className="glass rounded-2xl shadow-float ring-1 ring-black/5">
        <ul className={`grid gap-1 p-2 ${isSupport ? 'grid-cols-2' : 'grid-cols-5'}`}>
          {items.map((it) => {
            const isActive = it.key === active
            return (
              <li key={it.key}>
                <a
                  href={it.href}
                  onClick={(e) => { e.preventDefault(); goTo(it.href) }}
                  onTouchEnd={(e) => { e.preventDefault(); goTo(it.href) }}
                  data-active={isActive ? 'true' : 'false'}
                  className={[
                    'flex flex-col items-center justify-center rounded-xl2 px-1 py-2 touch-manipulation transition-colors',
                    isActive ? 'bg-white/80 shadow-soft ring-1 ring-black/5' : 'hover:bg-white/50',
                  ].join(' ')}
                >
                  <span className={['h-8 w-8', isActive ? 'animate-gentleFloat' : ''].join(' ')}>
                    {it.Icon({ className: 'h-8 w-8' })}
                  </span>
                  <span className="mt-1 text-[12px] font-semibold tracking-wide text-ink/80">{it.label}</span>
                </a>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
