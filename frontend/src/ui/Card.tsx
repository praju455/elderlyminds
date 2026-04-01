import type React from 'react'

export function Card({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      data-float-card
      className={[
        'glass rounded-2xl p-4 shadow-soft ring-1 ring-black/5',
        'relative overflow-hidden',
        className,
      ].join(' ')}
    >
      {children}
    </section>
  )
}

