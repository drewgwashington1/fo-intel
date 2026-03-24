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
          navy: '#0B1026',
          blue: '#2B4BCC',
          action: '#3B6BF5',
          frost: '#E9F0FF',
        },
        amber: {
          DEFAULT: '#F5A623',
        },
        surface: {
          DEFAULT: '#0E1420',
          card: '#151D2E',
          hover: '#1A2540',
          border: 'rgba(255, 255, 255, 0.08)',
        },
        status: {
          up: '#1BB981',
          down: '#F44444',
          neutral: '#8B95A5',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
