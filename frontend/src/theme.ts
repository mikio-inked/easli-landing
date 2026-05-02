// Centralized theme tokens for **easli**.
//
// These values come 1:1 from the Brand Guide ("easli – final"):
//
//   Primary (Trust / Struktur)
//     Deep Blue           #1E3A8A   ← solid actions, headlines, anchors
//     Primary Hover       #2F6FED   ← pressed / hover state
//     Primary Light       #E8EDFF   ← chip backgrounds, info badges
//
//   Secondary (Accent — sparingly! ≤10% of UI surface)
//     Soft Teal           #2EC4B6   ← highlights, focus, accent CTA
//     Light Teal          #E6FAF8   ← subtle accent backgrounds
//
//   Neutrals
//     Background          #FAFAF7   ← warm off-white app canvas
//     Surface (Card)      #FFFFFF
//     Border              #E5E7EB
//     Text Primary        #0F172A
//     Text Secondary      #475569
//
//   Status (functional, never branding)
//     Success             #22C55E
//     Warning             #F59E0B
//     Error               #EF4444
//
// Brand mantra: "Modern clarity meets calm authority."  The icon is loud
// (gradient blue → teal). The UI must therefore be QUIET, CLEAR, STRUCTURED.
// → no decorative colour, no gradients in core UI, no illustration noise.

export const colors = {
  // Surfaces ----------------------------------------------------------------
  background: '#FAFAF7',
  surface: '#FFFFFF',
  surfaceMuted: '#F5F5F1',     // subtle row-divider / hover on warm bg
  surfaceElevated: '#FFFFFF',

  // Primary — Deep Blue (Trust) ---------------------------------------------
  primary: '#1E3A8A',
  primaryDark: '#172554',       // deeper for pressed state on light bg
  primaryHover: '#2F6FED',      // hover/pressed light state
  primarySoft: '#E8EDFF',       // chip/badge backgrounds
  primaryBorder: '#C7D2FE',
  primaryAccent: '#2F6FED',     // a brighter blue for hero accents

  // Secondary — Soft Teal (Accent) ------------------------------------------
  // Use sparingly — the Brand Guide explicitly forbids using teal as a
  // dominant colour. Reserved for: focus rings, success-positive nuance,
  // accent CTAs (≤10% of surface area).
  accent: '#2EC4B6',
  accentSoft: '#E6FAF8',
  accentBorder: '#A8E6E0',

  // Trust alias — kept for components that previously used `colors.trust*`
  // to avoid a wide-reaching rename. Maps to the new primary.
  trust: '#1E3A8A',
  trustDark: '#172554',
  trustSoft: '#E8EDFF',
  trustBorder: '#C7D2FE',
  trustText: '#1E3A8A',

  // Text --------------------------------------------------------------------
  textPrimary: '#0F172A',
  textSecondary: '#475569',
  textMuted: '#64748B',
  textInverse: '#FFFFFF',

  // Borders -----------------------------------------------------------------
  border: '#E5E7EB',
  borderLight: '#F1F1EE',
  borderStrong: '#CBD5E1',

  // Neutral utilities -------------------------------------------------------
  white: '#FFFFFF',
  black: '#000000',
  overlay: 'rgba(15, 23, 42, 0.55)',

  // Status — refreshed to Brand-Guide values --------------------------------
  // Risk badges (green/yellow/red) now map to the Tailwind-ish status
  // tokens specified in the guide.
  green: {
    bg: '#EAF7F1',         // positive badge bg
    text: '#0F6B36',       // legible green on light bg
    border: '#BBE5CC',
    solid: '#22C55E',      // success solid
  },
  yellow: {
    bg: '#FFF7ED',         // hint badge bg
    text: '#7C4D04',       // legible amber on light bg
    border: '#FCD9A1',
    solid: '#F59E0B',      // warning solid
  },
  red: {
    bg: '#FEEDEC',         // error badge bg
    text: '#9B2520',       // legible red on light bg
    border: '#F8C5C0',
    solid: '#EF4444',      // error solid
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

// Radii — Brand Guide says cards = 14px ------------------------------------
export const radius = {
  sm: 10,
  md: 14,         // ← Brand Guide default for cards, inputs, chips
  lg: 18,
  xl: 22,
  xxl: 28,
  pill: 999,
  full: 9999,
};

// Type scale aligned to the Brand Guide -------------------------------------
//   H1 (Hauptaussage):   28–32 px, SemiBold
//   H2 (Section):        18–20 px, Medium
//   Body:                14–16 px, Regular
//   Helper:              12–13 px
export const fontSize = {
  xs: 12,         // helper-min
  sm: 13,         // helper
  base: 16,       // body
  body: 14,       // body-min
  lg: 18,         // h2-min
  xl: 20,         // h2-max
  '2xl': 24,
  '3xl': 28,      // h1-min
  '4xl': 32,      // h1-max
  '5xl': 40,
  '6xl': 56,
};

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

export const lineHeight = {
  tight: 1.15,
  snug: 1.3,
  normal: 1.5,
  relaxed: 1.65,
};

// Shadows — Brand Guide specifies 0 2px 6px rgba(0,0,0,0.04) for cards. ----
export const shadows = {
  // Default content card — quiet, structural.
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  // Elevated surface (modal, sticky bar). Slightly more prominent.
  raised: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 24,
    elevation: 6,
  },
  // Primary button — deep-blue tint
  button: {
    shadowColor: '#1E3A8A',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 4,
  },
  // Trust button alias (legacy callsites) — same as button now.
  buttonTrust: {
    shadowColor: '#1E3A8A',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 16,
    elevation: 4,
  },
};

// Brand Gradient — ONLY for splash, onboarding hero, marketing surfaces ----
export const gradient = {
  brand: {
    colors: ['#1E3A8A', '#2EC4B6'] as [string, string],
    /** Approximation of the icon: top-left deep-blue → bottom-right teal. */
    start: { x: 0, y: 0 },
    end: { x: 1, y: 1 },
  },
};

// Brand metadata -------------------------------------------------------------
export const brand = {
  name: 'easli',
  tagline: 'Understand any letter.',
  hex: {
    primary: '#1E3A8A',
    primaryHover: '#2F6FED',
    primaryLight: '#E8EDFF',
    accent: '#2EC4B6',
    accentLight: '#E6FAF8',
    background: '#FAFAF7',
  },
};

// Easing curves & durations for spring-style microanimations ----------------
export const motion = {
  fast: 180,
  base: 240,
  slow: 360,
  bezier: {
    standard: [0.4, 0.0, 0.2, 1] as const,
    decel: [0.0, 0.0, 0.2, 1] as const,
    accel: [0.4, 0.0, 1, 1] as const,
  },
};
