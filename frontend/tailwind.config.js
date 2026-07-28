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
        void:     '#f4f1e8',
        abyss:    '#fffdf8',
        deep:     '#f8f5ed',
        surface:  '#ece7db',
        elevated: '#ffffff',

        // Structural borders
        border: {
          dim:    '#ded8ca',
          base:   '#c3bbab',
          bright: '#817868',
        },

        // Accent palette — "Amber Neural"
        ops: {
          amber:        '#f05a2a',
          'amber-bright': '#ff7448',
          'amber-dim':  'rgba(240,90,42,0.08)',
          cyan:         '#147d75',
          'cyan-bright':'#0d968a',
          emerald:      '#2e7d4f',
          rose:         '#c53e4c',
          violet:       '#6654a5',
          orange:       '#d9772f',
        },

        // Text hierarchy
        ink: {
          primary:   '#1d2926',
          secondary: '#59635f',
          muted:     '#8a918d',
          ghost:     '#b9bdb8',
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
        'card':       '0 14px 40px rgba(48,53,47,0.08)',
      },
      backgroundImage: {
        'grid-ops': "linear-gradient(rgba(29,41,38,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(29,41,38,0.045) 1px, transparent 1px)",
      },
      backgroundSize: {
        'grid-ops': '48px 48px',
      },
    },
  },
  plugins: [],
}
