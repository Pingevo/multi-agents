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
        surface: '#1a1d28',
        'surface-2': '#222636',
        'surface-3': '#2a2d3a',
        border: '#2a2d3a',
        'border-light': '#3a3d4a',
        text: '#e4e6eb',
        'text-2': '#8b8e98',
        'text-3': '#5a5d68',
        accent: '#6366f1',
        'accent-hover': '#5558e3',
        'accent-light': '#8b5cf6',
        success: '#22c55e',
        warning: '#f59e0b',
        danger: '#ef4444',
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
