/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        petroleum: {
          50: '#f0f7ff',
          100: '#e0effe',
          500: '#0b6e99',
          600: '#095880',
          700: '#074566',
          900: '#032a3f',
        },
      },
    },
  },
  plugins: [],
}
