import type { Config } from 'tailwindcss'

export default {
  content: [
    './components/**/*.{js,vue,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './plugins/**/*.{js,ts}',
    './composables/**/*.ts',
    './app.vue',
    './error.vue',
  ],

  // Theme toggle support (system / light / dark) — see plan section 4.1
  // The `<html>` element gets either `.light` or `.dark` from useTheme().
  darkMode: 'class',

  theme: {
    extend: {
      // Design system palette — section 4.1 of the plan
      colors: {
        laterite: {
          DEFAULT: '#B8472A',
          deep: '#7A2E1A',
        },
        ink: '#0F1410',
        char: '#1A1F1B',
        parchment: '#F5F1EA',
        bone: {
          DEFAULT: '#E5DDD0',
          warm: '#D9C9B0',
        },
        forest: {
          DEFAULT: '#1A4030',
          pale: '#A8B89E',
        },
        amber: '#C4926B',
      },

      // Type scale — 1.250 ratio, rem base
      fontSize: {
        'xs':  ['0.75rem',  { lineHeight: '1rem' }],
        'sm':  ['0.875rem', { lineHeight: '1.25rem' }],
        'base':['1rem',     { lineHeight: '1.5rem' }],
        'lg':  ['1.25rem',  { lineHeight: '1.75rem' }],
        'xl':  ['1.563rem', { lineHeight: '2rem' }],
        '2xl': ['1.953rem', { lineHeight: '2.25rem' }],
        '3xl': ['2.441rem', { lineHeight: '2.75rem' }],
        '4xl': ['3.052rem', { lineHeight: '3.25rem' }],
        '5xl': ['3.815rem', { lineHeight: '4rem' }],
        '6xl': ['4.768rem', { lineHeight: '5rem' }],
        'hero':['7.451rem', { lineHeight: '0.95', letterSpacing: '-0.03em' }],
      },

      // Spacing — 8px base scale
      spacing: {
        '0.5': '4px',
        '1':   '8px',
        '1.5': '12px',
        '2':   '16px',
        '3':   '24px',
        '4':   '32px',
        '6':   '48px',
        '8':   '64px',
        '12':  '96px',
        '16':  '128px',
      },

      // Border radius — section 4.3
      borderRadius: {
        'none': '0',
        'sm':   '4px',
        DEFAULT:'4px',
        'md':   '8px',
      },

      // Box shadows — section 4.3 (no soft glows)
      boxShadow: {
        'hairline': '0 1px 0 rgba(15, 20, 16, 0.08)',
        'none': 'none',
      },

      // Font families — section 4.2
      fontFamily: {
        'display': ['Fraunces', 'Georgia', 'serif'],
        'sans':    ['Public Sans', 'system-ui', 'sans-serif'],
        'mono':    ['JetBrains Mono', 'monospace'],
      },

      // Motion — section 4.3
      transitionTimingFunction: {
        'tufte': 'cubic-bezier(0.2, 0.7, 0, 1)',
      },
      transitionDuration: {
        '200': '200ms',
        '320': '320ms',
        '400': '400ms',
      },

      // Animation
      animation: {
        'fadein': 'fadein 600ms cubic-bezier(0.2, 0.7, 0, 1) both',
      },
      keyframes: {
        fadein: {
          'from': { opacity: '0', transform: 'translateY(4px)' },
          'to':   { opacity: '1', transform: 'translateY(0)' },
        },
      },

      // Layout
      width: {
        'rail': '320px',
        'detail': '480px',
        'editorial': '720px',
      },

      // Surface tokens that swap between light and dark. Components reference
      // `bg-surface-canvas`, `bg-surface-rail`, `text-surface-fg`, and the
      // value swaps automatically based on `.dark` on <html>.
      backgroundColor: {
        'surface-canvas': 'var(--surface-canvas)',
        'surface-rail':   'var(--surface-rail)',
      },
      textColor: {
        'surface-fg':     'var(--surface-fg)',
        'surface-muted':  'var(--surface-muted)',
      },
      borderColor: {
        'surface-line':   'var(--surface-line)',
      },
    },
  },

  plugins: [],
} satisfies Config
