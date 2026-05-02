// Brand assets for easli — icon + wordmark.
//
// Three reusable React-Native components:
//
//   <EasliMark size={32} />
//     • The official easli icon (gradient blue → teal "E" with paper-fold).
//       Loaded from `assets/images/easli-icon.png`. Always used at the same
//       1:1 aspect ratio with rounded corners.
//
//   <EasliWordmark size={28} tone="primary" />
//     • The text wordmark "easli" in Inter ExtraBold + Deep Blue.
//
//   <EasliLogo size={32} tone="primary" />
//     • Convenience: icon mark + wordmark, horizontally aligned.
//
// Brand-guide alignment
//   • Wordmark uses Deep Blue (#1E3A8A) — never teal — per Brand Guide §1.
//   • The icon is "loud" by design (gradient). In the UI we keep it small
//     (24–32 px) so it never competes with content.
//   • No drop-shadow on the icon when displayed in-app — the iOS launcher
//     shadow is fine on home-screen, but inside the UI it would clash with
//     the rest of our quiet-card aesthetic (Brand Guide §6).

import React from 'react';
import { View, Text, StyleSheet, Image } from 'react-native';
import { colors, fontFamily, radius } from './theme';

export type LogoTone = 'primary' | 'inverse' | 'mono';

interface BaseProps {
  size?: number;
  tone?: LogoTone;
}

function tonePalette(tone: LogoTone) {
  if (tone === 'inverse') {
    return { text: colors.white };
  }
  if (tone === 'mono') {
    return { text: colors.textPrimary };
  }
  // 'primary'
  return { text: colors.primary };
}

/** Icon-only square mark — the official easli "E" gradient icon. */
export function EasliMark({ size = 32 }: BaseProps) {
  return (
    <Image
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      source={require('../assets/images/easli-icon.png')}
      style={{
        width: size,
        height: size,
        // 22-26 % is the standard iOS app-icon mask.
        borderRadius: Math.round(size * 0.22),
      }}
      accessibilityIgnoresInvertColors
      accessibilityLabel="easli"
    />
  );
}

/** Text-only wordmark — "easli" in Inter ExtraBold + Deep Blue. */
export function EasliWordmark({ size = 28, tone = 'primary' }: BaseProps) {
  const pal = tonePalette(tone);
  return (
    <Text
      accessibilityLabel="easli"
      style={{
        fontSize: size,
        lineHeight: size * 1.05,
        color: pal.text,
        fontFamily: fontFamily.extrabold,
        letterSpacing: -0.6,
      }}
    >
      easli
    </Text>
  );
}

/** Convenience: icon mark + wordmark, horizontally aligned. */
export function EasliLogo({ size = 32, tone = 'primary' }: BaseProps) {
  return (
    <View style={[styles.row, { gap: Math.round(size * 0.32) }]}>
      <EasliMark size={size} />
      <EasliWordmark size={size * 0.78} tone={tone} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});

// Re-export so callers needing the radius constant for matching paper edges
// don't have to import from the theme separately.
export const _markRadius = radius;
