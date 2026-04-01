import type React from 'react'

type StickerProps = React.SVGProps<SVGSVGElement> & { tone?: 'mint' | 'sky' | 'peach' | 'rose' }

const toneFill: Record<NonNullable<StickerProps['tone']>, string> = {
  mint: '#62D3A4',
  sky: '#76B9FF',
  peach: '#FFB38A',
  rose: '#FF7DAA',
}

export function ElderSticker({ tone = 'mint', ...props }: StickerProps) {
  const accent = toneFill[tone]
  return (
    <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" {...props}>
      <path
        d="M96 52c0 25-16 49-36 49S24 77 24 52 40 8 60 8s36 19 36 44Z"
        fill="rgba(255,255,255,0.82)"
      />
      <path
        d="M88 54c0 18-12 37-28 37S32 72 32 54 45 20 60 20s28 16 28 34Z"
        fill="#FFF8F1"
      />
      <path d="M44 54a6 6 0 1 0 0-.01Z" fill="#2A2228" />
      <path d="M76 54a6 6 0 1 0 0-.01Z" fill="#2A2228" />
      <path
        d="M45 70c4 5 9 8 15 8s11-3 15-8"
        stroke="#2A2228"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M24 52c0-25 16-44 36-44 13 0 24 8 30 20-6-4-13-6-20-6-23 0-42 22-42 46 0 9 2 17 6 24-6-9-10-23-10-40Z"
        fill="rgba(118,185,255,0.25)"
      />
      <path
        d="M22 96c9 10 23 16 38 16s29-6 38-16c-8-15-22-24-38-24s-30 9-38 24Z"
        fill="rgba(255,255,255,0.84)"
      />
      <path d="M18 42c10-14 25-20 42-20s32 6 42 20" stroke={accent} strokeWidth="8" strokeLinecap="round" />
      <path
        d="M12 44c12-22 31-32 48-32s36 10 48 32"
        stroke="rgba(42,34,40,0.12)"
        strokeWidth="10"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function PillSticker(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" {...props}>
      <rect x="20" y="28" width="80" height="64" rx="32" fill="rgba(255,255,255,0.78)" />
      <path
        d="M52 32c-17.7 0-32 14.3-32 32 0 14.2 9.2 26.2 22 30L88 48c-6-9.7-16.7-16-36-16Z"
        fill="rgba(118,185,255,0.35)"
      />
      <path d="M60 92c17.7 0 32-14.3 32-32 0-14.2-9.2-26.2-22-30L32 74c6 11.1 16.6 18 28 18Z" fill="rgba(255,179,138,0.45)" />
      <path d="M42 78 78 42" stroke="rgba(42,34,40,0.22)" strokeWidth="8" strokeLinecap="round" />
    </svg>
  )
}

export function HeartPulseSticker(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" {...props}>
      <path
        d="M60 102c-29-16-44-33-44-53 0-16 12-29 28-29 8 0 12 3 16 8 4-5 8-8 16-8 16 0 28 13 28 29 0 20-15 37-44 53Z"
        fill="rgba(255,255,255,0.8)"
      />
      <path
        d="M30 62h16l6-12 10 24 10-18h18"
        stroke="#FF4B5C"
        strokeWidth="7"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function SparkleSticker(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" {...props}>
      <path d="M60 18l8 22 22 8-22 8-8 22-8-22-22-8 22-8 8-22Z" fill="rgba(255,211,110,0.95)" />
      <path d="M24 70l4 11 11 4-11 4-4 11-4-11-11-4 11-4 4-11Z" fill="rgba(118,185,255,0.7)" />
      <path d="M90 64l4 11 11 4-11 4-4 11-4-11-11-4 11-4 4-11Z" fill="rgba(98,211,164,0.7)" />
    </svg>
  )
}

export function BellSticker(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" {...props}>
      <path
        d="M60 102c16 0 28-5 28-12H32c0 7 12 12 28 12Z"
        fill="rgba(42,34,40,0.16)"
      />
      <path
        d="M40 86V56c0-17 9-30 20-30s20 13 20 30v30l8 6H32l8-6Z"
        fill="rgba(255,255,255,0.82)"
      />
      <path
        d="M46 86V58c0-12 6-22 14-22s14 10 14 22v28"
        stroke="#FF9D5C"
        strokeWidth="8"
        strokeLinecap="round"
      />
      <circle cx="60" cy="24" r="7" fill="rgba(118,185,255,0.88)" />
      <path d="M52 96c2 6 5 9 8 9s6-3 8-9" stroke="#2A2228" strokeWidth="6" strokeLinecap="round" />
    </svg>
  )
}

export function FamilySticker({ tone = 'sky', ...props }: StickerProps) {
  const accent = toneFill[tone]
  return (
    <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" {...props}>
      <circle cx="38" cy="42" r="16" fill="rgba(255,255,255,0.84)" />
      <circle cx="82" cy="38" r="14" fill="rgba(255,255,255,0.84)" />
      <circle cx="64" cy="30" r="18" fill="rgba(255,255,255,0.92)" />
      <path
        d="M18 94c4-16 18-26 34-26s30 10 34 26"
        fill="rgba(255,255,255,0.82)"
      />
      <path
        d="M54 94c3-14 14-22 28-22 13 0 24 8 27 22"
        fill="rgba(255,255,255,0.74)"
      />
      <path
        d="M10 96c6-22 24-34 46-34s40 12 46 34"
        stroke={accent}
        strokeWidth="8"
        strokeLinecap="round"
      />
      <path
        d="M48 28c5-9 11-13 16-13 7 0 13 5 18 15"
        stroke="rgba(255,179,138,0.9)"
        strokeWidth="8"
        strokeLinecap="round"
      />
    </svg>
  )
}
