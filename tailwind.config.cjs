/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./static/index.html'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'Inter', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
    },
  },
};
