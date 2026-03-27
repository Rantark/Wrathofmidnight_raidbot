/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui'] },
      colors: {
        // WoW class colors
        warrior: '#C79C6E',
        paladin: '#F58CBA',
        hunter: '#ABD473',
        rogue: '#FFF569',
        priest: '#E8E8E8',
        'death-knight': '#C41F3B',
        shaman: '#0070DE',
        mage: '#40C7EB',
        warlock: '#8788EE',
        monk: '#00FF96',
        druid: '#FF7D0A',
        'demon-hunter': '#A330C9',
        evoker: '#33937F',
      },
      backgroundImage: {
        'gradient-app': 'linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%)',
      },
      backdropBlur: { xs: '2px' },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        slideIn: { from: { opacity: '0', transform: 'translateX(-16px)' }, to: { opacity: '1', transform: 'translateX(0)' } },
      },
    },
  },
  plugins: [],
}
