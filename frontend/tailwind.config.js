/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {},
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
