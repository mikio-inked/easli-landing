// Reusable presentational sub-components for the Result screen.
// Extracted from app/result.tsx during Phase C modularisation.

import React, { useEffect, useRef } from 'react';
import {
  Animated,
  Easing,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { AlertTriangle, ChevronDown, Info, ShieldAlert } from 'lucide-react-native';
import { SectionTitle } from '../ui';
import { LanguageCode, t } from '../i18n';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from '../theme';

// ---------------------------------------------------------------------------
// riskMeta: returns the localized label, icon JSX, and palette for a risk
// level. Kept colocated with its consumers (Risk Hero card, Action Pyramid).
// ---------------------------------------------------------------------------
export function riskMeta(level: 'green' | 'yellow' | 'red', lang: LanguageCode) {
  if (level === 'green') {
    return {
      label: t(lang, 'risk_green'),
      icon: <Info color={colors.green.text} size={26} strokeWidth={2.4} />,
      palette: colors.green,
    };
  }
  if (level === 'yellow') {
    return {
      label: t(lang, 'risk_yellow'),
      icon: <AlertTriangle color={colors.yellow.text} size={26} strokeWidth={2.4} />,
      palette: colors.yellow,
    };
  }
  return {
    label: t(lang, 'risk_red'),
    icon: <ShieldAlert color={colors.red.text} size={26} strokeWidth={2.4} />,
    palette: colors.red,
  };
}

// ---------------------------------------------------------------------------
// SectionRow: small icon + section title used as a static header inside cards.
// ---------------------------------------------------------------------------
export function SectionRow({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <View style={localStyles.sectionIcon}>{icon}</View>
      <SectionTitle>{title}</SectionTitle>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Accordion: collapsible card. Header is fully tappable (44pt min target).
// Animated chevron rotates on toggle for clear affordance.
// ---------------------------------------------------------------------------
export function Accordion({
  id,
  title,
  icon,
  open,
  onToggle,
  testID,
  children,
}: {
  id: string;
  title: string;
  icon: React.ReactNode;
  open: boolean;
  onToggle: (id: string, currentlyOpen: boolean) => void;
  testID?: string;
  children: React.ReactNode;
}) {
  const rotation = useRef(new Animated.Value(open ? 1 : 0)).current;

  useEffect(() => {
    Animated.timing(rotation, {
      toValue: open ? 1 : 0,
      duration: 220,
      easing: Easing.out(Easing.ease),
      useNativeDriver: true,
    }).start();
  }, [open, rotation]);

  const rotateInterpolate = rotation.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '180deg'],
  });

  return (
    <View style={localStyles.accordionCard} testID={testID}>
      <Pressable
        onPress={() => onToggle(id, open)}
        style={({ pressed }) => [localStyles.accordionHeader, pressed && { opacity: 0.7 }]}
        hitSlop={4}
        testID={testID ? `${testID}-header` : undefined}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={title}
      >
        <View style={localStyles.sectionIcon}>{icon}</View>
        <Text style={localStyles.accordionTitle} numberOfLines={2}>
          {title}
        </Text>
        <Animated.View style={{ transform: [{ rotate: rotateInterpolate }] }}>
          <ChevronDown color={colors.textSecondary} size={22} strokeWidth={2.4} />
        </Animated.View>
      </Pressable>
      {open ? <View style={localStyles.accordionBody}>{children}</View> : null}
    </View>
  );
}

// Local styles — kept here (not in the parent's `styles`) so the components
// are self-contained and the parent stylesheet stays focused. Names and
// values are byte-identical to the originals in app/result.tsx so visuals
// don't drift.
const localStyles = StyleSheet.create({
  sectionIcon: {
    width: 30,
    height: 30,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  accordionCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: 'hidden',
    ...shadows.card,
  },
  accordionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    minHeight: 56, // ≥44pt touch target
  },
  accordionTitle: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    letterSpacing: -0.2,
  },
  accordionBody: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },
});
