/**
 * AEGIS ALERT - Design Tokens & Global Style Constants
 * Unified source of truth for branding, hazard scales, and layout metrics.
 */

export const AEGIS_TOKENS = {
  name: 'AEGIS ALERT',
  subtitle: 'MULTI-HAZARD EARLY WARNING SYSTEM',
  shortSubtitle: 'MULTI-HAZARD EARLY WARNING',
  region: 'INDIA REGION',
  commandCenter: 'SECURE COMMAND CENTER • INDIA REGION',

  colors: {
    bg: '#F4F8FA',             // Very pale blue/white background
    primaryDark: '#075B8A',     // Dark blue (Sidebar & primary hero)
    primaryBlue: '#0B6E9E',     // Accent Primary Blue
    cyan: '#18C3D0',            // Active cyan accent / rounded pill
    alertRed: '#E94B68',        // Critical alert red
    warningYellow: '#F4C84A',   // Warning yellow
    successGreen: '#45C79A',    // Success / operational green
    text: '#18364A',            // Primary deep slate text
    secondaryText: '#708696',   // Secondary muted text
    border: '#DCEBED',          // Subtle border
    cardBg: '#FFFFFF',          // Card white surface
  },

  sidebar: {
    widthDesktop: '216px',
    bg: '#075B8A',
    activePillBg: '#18C3D0',
    activePillText: '#075B8A',
    inactiveText: '#D1E6F0',
    hoverBg: 'rgba(255, 255, 255, 0.08)',
  },

  cards: {
    radius: '20px',             // 18-24px rounded corners
    border: '1px solid #DCEBED',
    shadow: '0 4px 12px -2px rgba(7, 91, 138, 0.05)',
  },

  hazardLevels: {
    critical: {
      label: 'Critical Alert',
      color: '#E94B68',
      bg: '#FEF1F3',
      border: '#FDC8D1',
      badgeClass: 'bg-[#FEF1F3] text-[#E94B68] border-[#FDC8D1]',
    },
    warning: {
      label: 'Warning',
      color: '#F4C84A',
      bg: '#FFFBF0',
      border: '#FDE8A4',
      badgeClass: 'bg-[#FFFBF0] text-[#B78809] border-[#FDE8A4]',
    },
    moderate: {
      label: 'Watch / Advisory',
      color: '#F59E0B',
      bg: '#FFFDF5',
      border: '#FEF08A',
      badgeClass: 'bg-[#FFFDF5] text-[#D97706] border-[#FEF08A]',
    },
    safe: {
      label: 'Normal / Operational',
      color: '#45C79A',
      bg: '#EFFCF6',
      border: '#B7F1DC',
      badgeClass: 'bg-[#EFFCF6] text-[#1E8A63] border-[#B7F1DC]',
    },
    info: {
      label: 'Informational',
      color: '#18C3D0',
      bg: '#EDFAFC',
      border: '#AEEBF0',
      badgeClass: 'bg-[#EDFAFC] text-[#0E7F89] border-[#AEEBF0]',
    },
  },
} as const;

export const AGIES_TOKENS = AEGIS_TOKENS;
export type HazardSeverityKey = keyof typeof AEGIS_TOKENS.hazardLevels;
