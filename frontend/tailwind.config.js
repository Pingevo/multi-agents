/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // --- Retro palette ---
        canvas: '#e8dcc8',
        paper: '#fdfdf8',
        cream: '#f6ede3',
        'cream-2': '#f0e6d6',
        ink: '#2d2a26',
        'ink-2': '#6b6358',
        'ink-3': '#9a9088',
        line: '#d4c9b8',
        'line-2': '#c4b8a6',
        orange: { DEFAULT: '#c0501e', light: '#e8703a' },
        blue: { DEFAULT: '#3a6b8a', light: '#5a8baa' },
        green: { DEFAULT: '#5a7a4a', light: '#7a9a6a' },
        amber: { DEFAULT: '#c89220', light: '#e8b240' },
        red: { DEFAULT: '#a03020', light: '#c05040' },
        purple: '#6a4a7a',
        // --- Legacy dark theme (kept for backward compat) ---
        bg: '#0f1117',
        surface: '#18181b',
        'surface-2': '#27272a',
        'surface-3': '#3f3f46',
        'border-dark': '#27272a',
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
      fontFamily: {
        retro: ['Segoe UI', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        'retro': '4px',
        'retro-sm': '3px',
        'retro-lg': '8px',
      },
      boxShadow: {
        'retro': '0 1px 3px rgba(45,42,38,.08)',
        'retro-lg': '0 4px 16px rgba(45,42,38,.12)',
        'retro-active': '0 4px 24px rgba(45,42,38,.18), 0 0 0 1px #c4b8a6',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'flow': 'flow 2s linear infinite',
        'spin-retro': 'spin 1s linear infinite',
        'thinking': 'thinking 1.4s ease-in-out infinite',
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
        'thinking': {
          '0%, 80%, 100%': { opacity: '0.3' },
          '40%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
