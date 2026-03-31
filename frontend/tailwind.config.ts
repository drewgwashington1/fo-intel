import type { Config } from 'tailwindcss'

export default {
  content: [
    './components/**/*.{vue,js,ts}',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './app.vue',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        fo: {
          navy: '#1A2332',
          blue: '#2B4BCC',
          action: '#3B6BF5',
          frost: '#E9F0FF',
        },
        amber: {
          DEFAULT: '#D97706',
        },
        surface: {
          DEFAULT: '#F3F4F8',
          card: '#FFFFFF',
          hover: '#F0F1F5',
          border: 'rgba(0, 0, 0, 0.10)',
        },
        status: {
          up: '#16A34A',
          down: '#DC2626',
          neutral: '#6B7280',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
