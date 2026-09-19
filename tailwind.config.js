/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // AEGIS ALERT Official Design Tokens
        'aegis-dark': '#075B8A',     // Primary Dark Blue
        'aegis-blue': '#0B6E9E',     // Primary Blue
        'aegis-cyan': '#18C3D0',     // Cyan Accent
        'aegis-red': '#E94B68',      // Alert Red
        'aegis-yellow': '#F4C84A',   // Warning Yellow
        'aegis-green': '#45C79A',    // Success Green
        'aegis-text': '#18364A',     // Primary Text
        'aegis-subtext': '#708696',  // Secondary Text
        'aegis-border': '#DCEBED',   // Subtle Border
        'aegis-bg': '#F4F8FA',       // Pale Blue/White Background

        // Backward compatibility aliases
        'agies-dark': '#075B8A',
        'agies-blue': '#0B6E9E',
        'agies-cyan': '#18C3D0',
        'agies-red': '#E94B68',
        'agies-yellow': '#F4C84A',
        'agies-green': '#45C79A',
        'agies-text': '#18364A',
        'agies-subtext': '#708696',
        'agies-border': '#DCEBED',
        'agies-bg': '#F4F8FA',

        // Extended Surface & Hazard Shades
        background: '#F4F8FA',
        surface: '#FFFFFF',
        'surface-subtle': '#EEF5F8',
        'surface-card': '#FFFFFF',
        'surface-border': '#DCEBED',
        
        hazard: {
          critical: '#E94B68',
          'critical-bg': '#FEF1F3',
          'critical-border': '#FDC8D1',
          warning: '#F4C84A',
          'warning-bg': '#FFFBF0',
          'warning-border': '#FDE8A4',
          moderate: '#F59E0B',
          'moderate-bg': '#FFFDF5',
          'moderate-border': '#FEF08A',
          safe: '#45C79A',
          'safe-bg': '#EFFCF6',
          'safe-border': '#B7F1DC',
          info: '#18C3D0',
          'info-bg': '#EDFAFC',
          'info-border': '#AEEBF0',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Consolas', 'monospace'],
      },
      borderRadius: {
        'card': '20px',
        'card-lg': '24px',
        'pill': '9999px',
      },
      boxShadow: {
        'subtle': '0 1px 3px 0 rgba(7, 91, 138, 0.04), 0 1px 2px 0 rgba(7, 91, 138, 0.02)',
        'card': '0 4px 12px -2px rgba(7, 91, 138, 0.05), 0 2px 6px -1px rgba(7, 91, 138, 0.03)',
        'elevated': '0 12px 24px -4px rgba(7, 91, 138, 0.08), 0 6px 12px -2px rgba(7, 91, 138, 0.04)',
        'float': '0 20px 30px -6px rgba(7, 91, 138, 0.15), 0 10px 15px -3px rgba(7, 91, 138, 0.08)',
        'glow-cyan': '0 0 20px rgba(24, 195, 208, 0.4)',
        'glow-red': '0 0 20px rgba(233, 75, 104, 0.35)',
      },
      keyframes: {
        'pulse-radar': {
          '0%': { transform: 'scale(0.8)', opacity: '0.9' },
          '50%': { transform: 'scale(1.8)', opacity: '0.3' },
          '100%': { transform: 'scale(2.6)', opacity: '0' },
        },
        'beacon-glow': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        'marquee': {
          '0%': { transform: 'translateX(0%)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        'float-bubble': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-4px)' },
        }
      },
      animation: {
        'pulse-radar': 'pulse-radar 2.5s cubic-bezier(0.24, 0, 0.38, 1) infinite',
        'beacon-glow': 'beacon-glow 1.5s ease-in-out infinite',
        'marquee': 'marquee 40s linear infinite',
        'float-bubble': 'float-bubble 3s ease-in-out infinite',
      }
    },
  },
  plugins: [],
}
