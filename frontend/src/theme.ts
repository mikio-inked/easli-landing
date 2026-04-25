// Centralized theme tokens for KlarPost.
// Trust Blue & Soft White — calm, elderly-friendly, German-market focused.

export const colors = {
  background: '#F8FAFC', // slate-50
  surface: '#FFFFFF',
  primary: '#1D4ED8', // blue-700
  primaryDark: '#1E40AF', // blue-800
  primarySoft: '#EFF6FF', // blue-50
  textPrimary: '#0F172A', // slate-900
  textSecondary: '#475569', // slate-600
  textMuted: '#64748B', // slate-500
  border: '#E2E8F0', // slate-200
  borderLight: '#F1F5F9', // slate-100
  white: '#FFFFFF',
  black: '#000000',
  // Status colors
  green: {
    bg: '#D1FAE5', // emerald-100
    text: '#065F46', // emerald-800
    border: '#A7F3D0', // emerald-200
    solid: '#10B981', // emerald-500
  },
  yellow: {
    bg: '#FEF3C7', // amber-100
    text: '#92400E', // amber-800
    border: '#FDE68A', // amber-200
    solid: '#F59E0B', // amber-500
  },
  red: {
    bg: '#FEE2E2', // red-100
    text: '#991B1B', // red-800
    border: '#FECACA', // red-200
    solid: '#EF4444', // red-500
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 40,
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  full: 9999,
};

export const fontSize = {
  xs: 12,
  sm: 14,
  base: 16,
  lg: 18,
  xl: 20,
  '2xl': 24,
  '3xl': 28,
  '4xl': 34,
};

export const fontWeight = {
  regular: '400' as const,
  medium: '500' as const,
  semibold: '600' as const,
  bold: '700' as const,
  extrabold: '800' as const,
};

export const shadows = {
  card: {
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  button: {
    shadowColor: '#1D4ED8',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 4,
  },
};
