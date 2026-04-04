/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        matsu: {
          green: '#1e5c38',
          'green-hover': '#17472c',
          'green-tint': '#edf7f1',
          yellow: '#FFC200',
          'yellow-dark': '#E6AF00',
          steel: '#6b7c87',
          charcoal: '#2b2d32',
        },
      },
    },
    typography: {
      DEFAULT: {
        css: {
          color: 'inherit',
          a: { color: 'inherit' },
          strong: { color: 'inherit' },
          code: { color: 'inherit' },
          h1: { color: 'inherit' },
          h2: { color: 'inherit' },
          h3: { color: 'inherit' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
