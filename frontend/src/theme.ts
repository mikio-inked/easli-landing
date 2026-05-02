// Centralized theme tokens for **easli** (Phase R1 — Brand Foundation).
//
// Brand DNA:
//  • Primary (Sage Green #7FD4A6) — calm, modern, trustworthy
//  • Trust (Deep Blue #1E3A8A) — financial credibility, anchor for serious info
//  • Warm Off-White (#FAFAF7) — soft, paper-like backdrop
//  • Inter typography — universal, excellent multi-script i18n
//
// Backwards-compatibility: The legacy `colors.primary*` keys still exist and
// now map to the new sage palette. Most existing screens read
// `colors.primary` / `colors.primarySoft` and will pick up the new look
// automatically. Components that explicitly want the trust-blue use
// `colors.trust*`.

export const colors = {
  // Surfaces ----------------------------------------------------------------
  background: '#FAFAF7', // warm off-white, paper-like
  surface: '#FFFFFF',
  surfaceMuted: '#F4F4EF', // subtle card divider / hover
  surfaceElevated: '#FFFFFF',

  // Primary — Sage Green (calm, modern) -------------------------------------
  primary: '#5BBE8C', // sage 500 — solid actions, links
  primaryDark: '#3F9F6F', // sage 700 — pressed state
  primarySoft: '#E8F7EF', // sage 50 — chip backgrounds, soft fills
  primaryBorder: '#B8E3CB', // sage 200 — outlined inputs / dividers
  primaryAccent: '#7FD4A6', // sage 400 — hero accents, illustrations

  // Trust — Deep Blue (financial credibility) -------------------------------
  trust: '#1E3A8A', // indigo-blue 800
  trustDark: '#172554', // indigo-blue 900 — high-emphasis text on cards
  trustSoft: '#EEF2FF', // indigo 50 — backdrop pills
  trustBorder: '#C7D2FE', // indigo 200
  trustText: '#1E3A8A', // for KPI numbers, deadlines

  // Text --------------------------------------------------------------------
  textPrimary: '#0F172A', // near-black, very high contrast
  textSecondary: '#475569', // body text
  textMuted: '#64748B', // captions, metadata
  textInverse: '#FFFFFF',

  // Borders -----------------------------------------------------------------
  border: '#E5E5E0', // hairline on warm bg
  borderLight: '#EFEFEA',
  borderStrong: '#CFCFCA',

  // Neutral utilities -------------------------------------------------------
  white: '#FFFFFF',
  black: '#000000',
  overlay: 'rgba(15, 23, 42, 0.55)', // modal scrim

  // Status colors — refreshed to match the new palette ----------------------
  green: {
    bg: '#E8F7EF',
    text: '#1F6B45',
    border: '#B8E3CB',
    solid: '#5BBE8C',
  },
  yellow: {
    bg: '#FFF6E2',
    text: '#7A4F00',
    border: '#FBE3A1',
    solid: '#E5A53A',
  },
  red: {
    bg: '#FDECEC',
    text: '#8C1F1F',
    border: '#F6C2C2',
    solid: '#D94F4F',
  },
};

// 8pt grid -------------------------------------------------------------------
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 40,
  '3xl': 56,
};

// Radii — slightly rounder for modern feel ----------------------------------
export const radius = {
  sm: 10,
  md: 14,
  lg: 18,
  xl: 22,
  xxl: 28,
  pill: 999,
  full: 9999,
};

// Type scale — slightly tighter than before for modern hierarchy ------------
export const fontSize = {
  xs: 12,
  sm: 14,
  base: 16,
  lg: 18,
  xl: 20,
  '2xl': 24,
  '3xl': 30,
  '4xl': 36,
  '5xl': 44,
  '6xl': 56, // for hero headlines
};

// Font families — set on <Text> via font_loader.tsx -------------------------
//  When the Inter family fails to load (rare, e.g. air-plane mode boot), we
//  fall back to the platform default by NOT setting fontFamily at all. The
//  helper `tx()` in components handles that gracefully.
export const fontFamily = {
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semibold: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
  extrabold: 'Inter_800ExtraBold',
};

export const fontWeight = {
  regular: '400' as const,
  medium: '500' as const,
  semibold: '600' as const,
  bold: '700' as const,
  extrabold: '800' as const,
};

// Line-heights paired to the type scale --------------------------------------
export const lineHeight = {
  tight: 1.15,
  snug: 1.3,
  normal: 1.5,
  relaxed: 1.65,
};

// Shadows — softer, paper-like ----------------------------------------------
export const shadows = {
  // Subtle hairline + tiny elevation. The default for content cards.
  card: {
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 10,
    elevation: 2,
  },
  // Elevated surface (modal, sticky bar). Slightly more prominent.
  raised: {
    shadowColor: '#0F172A',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 24,
    elevation: 6,
  },
  // Primary button — sage tint
  button: {
    shadowColor: '#3F9F6F',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 4,
  },
  // Trust button — deep blue tint
  buttonTrust: {
    shadowColor: '#1E3A8A',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 4,
  },
};

// Brand metadata -------------------------------------------------------------
export const brand = {
  name: 'easli',
  tagline: 'Understand any letter.',
  // Hex strings re-exported for places that need raw colour values
  // (animations, gradients, native modules) without importing the whole
  // palette object.
  hex: {
    sage: '#7FD4A6',
    sageDark: '#3F9F6F',
    deepBlue: '#1E3A8A',
    offWhite: '#FAFAF7',
  },
};

// Easing curves & durations for spring-style microanimations -----------------
export const motion = {
  fast: 180,
  base: 240,
  slow: 360,
  // Cubic-bezier values matching iOS spring-feel
  bezier: {
    standard: [0.4, 0.0, 0.2, 1] as const,
    decel: [0.0, 0.0, 0.2, 1] as const,
    accel: [0.4, 0.0, 1, 1] as const,
  },
};
