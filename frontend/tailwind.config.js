/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './*.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#FFF8F1',
        cream: '#FFF1E3',
        cocoa: '#2A2228',
        ink: '#1E1A22',
        mint: '#62D3A4',
        sky: '#76B9FF',
        peach: '#FFB38A',
        rose: '#FF7DAA',
        lemon: '#FFD36E',
        danger: '#FF4B5C',
      },
      boxShadow: {
        soft: '0 18px 50px rgba(18, 16, 22, 0.10)',
        float: '0 24px 70px rgba(18, 16, 22, 0.16)',
        insetSoft: 'inset 0 0 0 1px rgba(30, 26, 34, 0.08)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
      fontSize: {
        elder: ['1.15rem', { lineHeight: '1.5' }],
      },
      keyframes: {
        gentleFloat: {
          '0%,100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        slowGlow: {
          '0%,100%': { filter: 'drop-shadow(0 0 0 rgba(98, 211, 164, 0.0))' },
          '50%': { filter: 'drop-shadow(0 10px 18px rgba(98, 211, 164, 0.35))' },
        },
      },
      animation: {
        gentleFloat: 'gentleFloat 6s ease-in-out infinite',
        slowGlow: 'slowGlow 2.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}

