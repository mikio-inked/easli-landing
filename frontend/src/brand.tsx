// Brand assets for easli.
//
// Export 3 reusable React-Native components:
//
//   <EasliWordmark size={28} tone="primary" />
//     • The text wordmark "easli" rendered in Inter ExtraBold with a small
//       sage-green dot accent. Primary tone uses the deep-blue trust colour;
//       "inverse" tone is for use on dark surfaces (e.g. paywall hero).
//
//   <EasliMark size={32} tone="primary" />
//     • The icon-only mark — a single rounded square with the letter "e"
//       cut out + a sage dot. Used for tab bars, splash, history rows.
//
//   <EasliLogo size={32} tone="primary" />
//     • Convenience: the icon-mark + wordmark side by side.
//
// Implementation notes
//  • All three are PURE React Native (no SVG / no PNG dependency). The
//    wordmark uses Text + a 6-px sage dot drawn with a View. The icon mark
//    is a colored square with a Text "e" overlay (clean, scales perfectly,
//    works across iOS/Android/web with zero external assets).
//  • This is the PLACEHOLDER LOGO for Phase R1 of the rebrand. Once the
//    user provides the final logo file, we'll swap in an <Image>/<SVG>
//    here and every screen automatically picks up the change.

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, fontFamily } from './theme';

export type LogoTone = 'primary' | 'inverse' | 'mono';

interface BaseProps {
  size?: number;
  tone?: LogoTone;
}

function tonePalette(tone: LogoTone) {
  if (tone === 'inverse') {
    return {
      text: colors.white,
      mark: colors.white,
      dot: colors.primaryAccent,
      markText: colors.trust,
    };
  }
  if (tone === 'mono') {
    return {
      text: colors.textPrimary,
      mark: colors.textPrimary,
      dot: colors.textPrimary,
      markText: colors.surface,
    };
  }
  // 'primary'
  return {
    text: colors.trust,
    mark: colors.trust,
    dot: colors.primaryAccent,
    markText: colors.white,
  };
}

/** Text-only wordmark — "easli" in Inter ExtraBold + sage dot. */
export function EasliWordmark({ size = 28, tone = 'primary' }: BaseProps) {
  const pal = tonePalette(tone);
  const dotSize = Math.max(4, Math.round(size * 0.18));
  return (
    <View style={styles.row} accessibilityLabel="easli">
      <Text
        style={{
          fontSize: size,
          lineHeight: size * 1.05,
          color: pal.text,
          fontFamily: fontFamily.extrabold,
          letterSpacing: -0.5,
        }}
      >
        easli
      </Text>
      <View
        style={{
          width: dotSize,
          height: dotSize,
          borderRadius: dotSize / 2,
          backgroundColor: pal.dot,
          marginLeft: Math.max(2, Math.round(size * 0.05)),
          marginBottom: Math.max(2, Math.round(size * 0.1)),
          alignSelf: 'flex-end',
        }}
      />
    </View>
  );
}

/** Icon-only square mark — for tab bars, splash, list-row avatars. */
export function EasliMark({ size = 32, tone = 'primary' }: BaseProps) {
  const pal = tonePalette(tone);
  const radius = Math.round(size * 0.26);
  const dotSize = Math.max(3, Math.round(size * 0.18));
  return (
    <View
      style={{
        width: size,
        height: size,
        backgroundColor: pal.mark,
        borderRadius: radius,
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
    >
      <Text
        style={{
          color: pal.markText,
          fontSize: Math.round(size * 0.62),
          lineHeight: Math.round(size * 0.62) * 1.0,
          fontFamily: fontFamily.extrabold,
          letterSpacing: -0.5,
          marginBottom: -1,
        }}
      >
        e
      </Text>
      <View
        style={{
          width: dotSize,
          height: dotSize,
          borderRadius: dotSize / 2,
          backgroundColor: pal.dot,
          position: 'absolute',
          right: Math.round(size * 0.16),
          bottom: Math.round(size * 0.16),
        }}
      />
    </View>
  );
}

/** Convenience: icon mark + wordmark, horizontally aligned. */
export function EasliLogo({ size = 32, tone = 'primary' }: BaseProps) {
  return (
    <View style={[styles.row, { gap: Math.round(size * 0.3) }]}>
      <EasliMark size={size} tone={tone} />
      <EasliWordmark size={size * 0.9} tone={tone} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
