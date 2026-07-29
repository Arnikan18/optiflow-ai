/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Depth layers — dark ops background stack
        void:     'rgb(var(--bg-void) / <alpha-value>)',
        abyss:    'rgb(var(--bg-abyss) / <alpha-value>)',
        deep:     'rgb(var(--bg-deep) / <alpha-value>)',
        surface:  'rgb(var(--bg-surface) / <alpha-value>)',
        elevated: 'rgb(var(--bg-elevated) / <alpha-value>)',

        // Structural borders
        border: {
          dim:    'rgb(var(--border-dim) / <alpha-value>)',
          base:   'rgb(var(--border-base) / <alpha-value>)',
          bright: 'rgb(var(--border-bright) / <alpha-value>)',
        },

        // Accent palette — "Amber Neural"
        ops: {
          amber:         'rgb(var(--amber) / <alpha-value>)',
          'amber-bright':'rgb(var(--amber-bright) / <alpha-value>)',
          'amber-dim':   'rgb(var(--amber) / 0.08)',
          cyan:          'rgb(var(--cyan) / <alpha-value>)',
          'cyan-bright': 'rgb(var(--cyan) / <alpha-value>)',
          emerald:       'rgb(var(--emerald) / <alpha-value>)',
          rose:          'rgb(var(--rose) / <alpha-value>)',
          violet:        'rgb(var(--violet) / <alpha-value>)',
          orange:        'rgb(var(--orange) / <alpha-value>)',
        },

        // Text hierarchy
        ink: {
          primary:   'rgb(var(--text-primary) / <alpha-value>)',
          secondary: 'rgb(var(--text-secondary) / <alpha-value>)',
          muted:     'rgb(var(--text-muted) / <alpha-value>)',
          ghost:     'rgb(var(--text-ghost) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      animation: {
        'pulse-amber': 'pulse-amber 2s ease-in-out infinite',
        'pulse-cyan':  'pulse-cyan 1.5s ease-in-out infinite',
        'scan-in':     'scan-in 0.4s ease-out forwards',
        'fade-up':     'fade-up 0.35s ease-out forwards',
        'spin-slow':   'spin 3s linear infinite',
      },
      keyframes: {
        'pulse-amber': {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 0 0 rgba(245,158,11,0.4)' },
          '50%':       { opacity: '0.8', boxShadow: '0 0 0 8px rgba(245,158,11,0)' },
        },
        'pulse-cyan': {
          '0%, 100%': { opacity: '1' },
          '50%':       { opacity: '0.5' },
        },
        'scan-in': {
          from: { opacity: '0', transform: 'translateX(-16px)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
      boxShadow: {
        'amber-glow': '0 12px 30px rgba(240,90,42,0.20)',
        'cyan-glow':  '0 10px 26px rgba(20,125,117,0.16)',
        'card':       'var(--shadow-card)',
      },
      backgroundImage: {
        'grid-ops': "linear-gradient(rgb(var(--text-primary) / 0.045) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--text-primary) / 0.045) 1px, transparent 1px)",
      },
      backgroundSize: {
        'grid-ops': '48px 48px',
      },
    },
  },
  plugins: [],
}
