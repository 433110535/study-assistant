/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#000000',
        surface: '#141414',
        'surface-2': '#0A0A0A',
        accent: {
          DEFAULT: '#FAFF69',
          active: '#F4F692',
        },
        secondary: '#166534',
        border: 'rgba(65, 65, 65, 0.8)',
        text: {
          primary: '#FFFFFF',
          secondary: '#A1A1AA',
          muted: '#71717A',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['Inconsolata', 'Menlo', 'Monaco', 'Courier New', 'monospace'],
      },
      borderRadius: {
        none: '0px',
        sm: '4px',
        DEFAULT: '4px',
        md: '8px',
        lg: '8px',
        full: '999px',
      },
      letterSpacing: {
        label: '1.4px',
      },
      screens: {
        sm: '390px',
        md: '768px',
        lg: '1024px',
        xl: '1440px',
      },
    },
  },
  plugins: [],
};
