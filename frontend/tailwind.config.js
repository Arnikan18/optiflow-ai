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
        void:     '#070b14',
        abyss:    '#0d1424',
        deep:     '#111d35',
        surface:  '#162040',
        elevated: '#1a2850',

        // Structural borders
        border: {
          dim:    '#1e3055',
          base:   '#2d4a7a',
          bright: '#3d5fa0',
        },

        // Accent palette — "Amber Neural"
        ops: {
          amber:        '#f59e0b',
          'amber-bright': '#fbbf24',
          'amber-dim':  'rgba(245,158,11,0.08)',
          cyan:         '#06b6d4',
          'cyan-bright':'#22d3ee',
          emerald:      '#10b981',
          rose:         '#f43f5e',
          violet:       '#8b5cf6',
          orange:       '#f97316',
        },

        // Text hierarchy
        ink: {
          primary:   '#e2e8f0',
          secondary: '#94a3b8',
          muted:     '#475569',
          ghost:     '#1e3055',
        },
      },
      fontFamily: {
        sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
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
        'amber-glow': '0 0 20px rgba(245,158,11,0.25), 0 0 40px rgba(245,158,11,0.08)',
        'cyan-glow':  '0 0 16px rgba(6,182,212,0.25)',
        'card':       '0 2px 16px rgba(0,0,0,0.4)',
      },
      backgroundImage: {
        'grid-ops': "linear-gradient(rgba(45,74,122,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(45,74,122,0.12) 1px, transparent 1px)",
      },
      backgroundSize: {
        'grid-ops': '48px 48px',
      },
    },
  },
  plugins: [],
}
