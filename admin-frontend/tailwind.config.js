/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        matsu: {
          primary: '#E8971C',
          'primary-hover': '#C97E14',
          accent: '#3CADD8',
          dark: '#1C2A1E',
          steel: '#6b7c87',
        },
      },
    },
  },
  plugins: [],
}
