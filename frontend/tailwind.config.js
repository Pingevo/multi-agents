/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0f1117',
        surface: '#18181b',
        'surface-2': '#27272a',
        'surface-3': '#3f3f46',
        border: '#27272a',
        'border-light': '#3f3f46',
        text: '#e4e4e7',
        'text-2': '#a1a1aa',
        'text-3': '#71717a',
        accent: '#6366f1',
        'accent-hover': '#5558e9',
        'accent-light': '#8b5cf6',
        success: '#4ade80',
        warning: '#fbbf24',
        danger: '#f87171',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'flow': 'flow 2s linear infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(99, 102, 241, 0.3)' },
          '50%': { boxShadow: '0 0 0 6px rgba(99, 102, 241, 0)' },
        },
        'flow': {
          '0%': { strokeDashoffset: '20' },
          '100%': { strokeDashoffset: '0' },
        },
      },
    },
  },
  plugins: [],
}
