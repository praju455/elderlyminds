import { forwardRef, useLayoutEffect, useRef } from 'react'
import { gsap } from 'gsap'
import type React from 'react'

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'soft' | 'danger'
  size?: 'lg' | 'md'
}

const VARIANT =
  'transition-shadow active:shadow-none focus-visible:outline-none focus-visible:ring-0'

function setRefs<T>(refs: Array<React.Ref<T> | undefined>, value: T) {
  for (const ref of refs) {
    if (!ref) continue
    if (typeof ref === 'function') ref(value)
    else (ref as React.MutableRefObject<T | null>).current = value
  }
}

export const PressableButton = forwardRef<HTMLButtonElement, Props>(function PressableButton(
  { variant = 'soft', size = 'md', className = '', ...props },
  forwardedRef,
) {
  const localRef = useRef<HTMLButtonElement | null>(null)

  useLayoutEffect(() => {
    const el = localRef.current
    if (!el) return

    const ctx = gsap.context(() => {
      const press = () => gsap.to(el, { scale: 0.98, duration: 0.12, ease: 'power2.out' })
      const release = () => gsap.to(el, { scale: 1, duration: 0.22, ease: 'elastic.out(1, 0.55)' })

      el.addEventListener('pointerdown', press)
      el.addEventListener('pointerup', release)
      el.addEventListener('pointercancel', release)
      el.addEventListener('pointerleave', release)

      return () => {
        el.removeEventListener('pointerdown', press)
        el.removeEventListener('pointerup', release)
        el.removeEventListener('pointercancel', release)
        el.removeEventListener('pointerleave', release)
      }
    }, el)

    return () => ctx.revert()
  }, [])

  const base =
    'no-tap-highlight select-none rounded-xl2 px-4 py-3 font-semibold shadow-soft ' + VARIANT

  const sizes: Record<NonNullable<Props['size']>, string> = {
    md: 'text-base',
    lg: 'text-elder',
  }

  const variants: Record<NonNullable<Props['variant']>, string> = {
    soft: 'bg-white/70 text-ink shadow-soft ring-1 ring-black/5',
    primary: 'bg-ink text-paper shadow-float ring-1 ring-black/10',
    danger: 'bg-danger text-white shadow-float ring-1 ring-black/10',
  }

  return (
    <button
      ref={(node) => setRefs([localRef, forwardedRef], node)}
      className={[base, sizes[size], variants[variant], className].join(' ')}
      {...props}
    />
  )
})

