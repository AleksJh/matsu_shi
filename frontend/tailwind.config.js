/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        matsu: {
          primary: '#E8971C',
          'primary-hover': '#C97E14',
          'primary-tint': '#FDF3E0',
          dark: '#1C2A1E',
          'dark-hover': '#142018',
          accent: '#3CADD8',
          'accent-hover': '#2E9ECF',
          steel: '#6b7c87',
          charcoal: '#1A1A1F',
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
