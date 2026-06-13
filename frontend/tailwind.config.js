/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#10b981',
        'primary-bg': '#ecfdf5',
        surface: '#ffffff',
        page: '#f5f7f5',
        border: '#e5e7eb',
        text1: '#111827',
        text2: '#4b5563',
        text3: '#9ca3af'
      }
    }
  },
  plugins: []
};
