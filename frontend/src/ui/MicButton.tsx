import { useLayoutEffect, useMemo, useRef } from 'react'
import { gsap } from 'gsap'

export function MicButton({
  speaking,
  busy,
  onToggle,
}: {
  speaking: boolean
  busy?: boolean
  onToggle: () => void
}) {
  const rootRef = useRef<HTMLButtonElement | null>(null)
  const ringRef = useRef<HTMLDivElement | null>(null)
  const waveRef = useRef<HTMLDivElement | null>(null)

  const label = useMemo(() => {
    if (busy) return 'Working…'
    return speaking ? 'Listening… tap to stop' : 'Tap to speak'
  }, [speaking, busy])

  useLayoutEffect(() => {
    const root = rootRef.current
    const ring = ringRef.current
    const wave = waveRef.current
    if (!root || !ring || !wave) return

    const ctx = gsap.context(() => {
      gsap.killTweensOf([root, ring, wave])

      const breathe = gsap.timeline({ repeat: -1, yoyo: true })
      breathe.to(ring, { scale: 1.04, duration: 1.2, ease: 'sine.inOut' })

      const float = gsap.timeline({ repeat: -1, yoyo: true })
      float.to(root, { y: -4, duration: 2.4, ease: 'sine.inOut' })

      const waveTl = gsap.timeline({ repeat: -1 })
      waveTl
        .to(wave, { opacity: 1, duration: 0.2 })
        .fromTo(
          wave.children,
          { scale: 0.86, opacity: 0.0 },
          { scale: 1.18, opacity: 0, duration: 1.0, stagger: 0.16, ease: 'sine.out' },
          0,
        )

      if (speaking) {
        gsap.to(ring, { boxShadow: '0 24px 70px rgba(98, 211, 164, 0.35)', duration: 0.25 })
        waveTl.timeScale(1.35)
      } else {
        gsap.to(ring, { boxShadow: '0 18px 50px rgba(18, 16, 22, 0.10)', duration: 0.25 })
        waveTl.timeScale(0.9)
      }

      if (busy) {
        gsap.to(root, { scale: 0.985, duration: 0.25, yoyo: true, repeat: -1, ease: 'sine.inOut' })
        waveTl.timeScale(0.65)
      }

      return () => {
        breathe.kill()
        float.kill()
        waveTl.kill()
      }
    }, root)

    return () => ctx.revert()
  }, [speaking, busy])

  return (
    <div className="flex flex-col items-center justify-center py-2">
      <button
        ref={rootRef}
        onClick={onToggle}
        disabled={busy}
        className={[
          'no-tap-highlight relative grid h-[156px] w-[156px] place-items-center rounded-full',
          'shadow-float ring-1 ring-black/10',
          'bg-gradient-to-br from-white/80 to-white/50',
          busy ? 'opacity-80' : '',
        ].join(' ')}
        aria-pressed={speaking}
        aria-label={label}
      >
        <div
          ref={ringRef}
          className={[
            'absolute inset-0 rounded-full',
            speaking ? 'ring-4 ring-mint/60' : 'ring-2 ring-sky/40',
          ].join(' ')}
        />

        <div ref={waveRef} className="absolute inset-0 opacity-80">
          <span className="absolute inset-0 rounded-full border-2 border-mint/40" />
          <span className="absolute inset-0 rounded-full border-2 border-mint/30" />
          <span className="absolute inset-0 rounded-full border-2 border-mint/25" />
        </div>

        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z"
            stroke="#2A2228"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <path
            d="M5.5 11a6.5 6.5 0 0 0 13 0"
            stroke="#2A2228"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <path
            d="M12 17.5V21"
            stroke="#2A2228"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
        </svg>
      </button>
      <p className="mt-3 text-base font-semibold text-ink/75">
        {busy ? 'Thinking…' : speaking ? 'Listening…' : 'Tap and speak'}
      </p>
      <p className="mt-1 max-w-[28ch] text-center text-sm text-ink/60">
        {busy
          ? 'One moment — I’m preparing a gentle reply.'
          : speaking
            ? 'I’m here. Take your time.'
            : 'Ask anything — medicines, mood, or just chat.'}
      </p>
    </div>
  )
}

