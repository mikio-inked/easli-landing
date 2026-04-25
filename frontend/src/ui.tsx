// Reusable UI primitives for KlarPost.

import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
  TextStyle,
  StyleProp,
} from 'react-native';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from './theme';

interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  icon?: React.ReactNode;
  loading?: boolean;
  disabled?: boolean;
  testID?: string;
  fullWidth?: boolean;
  size?: 'lg' | 'md';
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  icon,
  loading,
  disabled,
  testID,
  fullWidth = true,
  size = 'lg',
}: ButtonProps) {
  const v = variant;
  const isDisabled = disabled || loading;
  const containerBase: ViewStyle = {
    height: size === 'lg' ? 56 : 48,
    borderRadius: radius.xl,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: spacing.lg,
    width: fullWidth ? '100%' : undefined,
  };
  const containerVariant: ViewStyle =
    v === 'primary'
      ? { backgroundColor: colors.primary, ...shadows.button }
      : v === 'secondary'
      ? { backgroundColor: colors.surface, borderWidth: 2, borderColor: colors.border }
      : v === 'danger'
      ? { backgroundColor: colors.red.bg, borderWidth: 1, borderColor: colors.red.border }
      : { backgroundColor: 'transparent' };
  const labelColor =
    v === 'primary'
      ? colors.white
      : v === 'danger'
      ? colors.red.text
      : v === 'secondary'
      ? colors.primary
      : colors.primary;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      testID={testID}
      style={({ pressed }) => [
        containerBase,
        containerVariant,
        pressed && { opacity: 0.85 },
        isDisabled && { opacity: 0.5 },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={labelColor} />
      ) : (
        <>
          {icon}
          <Text
            style={{
              color: labelColor,
              fontSize: size === 'lg' ? fontSize.lg : fontSize.base,
              fontWeight: fontWeight.bold,
              letterSpacing: 0.2,
            }}
          >
            {label}
          </Text>
        </>
      )}
    </Pressable>
  );
}

interface CardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function Card({ children, style, testID }: CardProps) {
  return (
    <View testID={testID} style={[styles.card, style]}>
      {children}
    </View>
  );
}

interface SectionTitleProps {
  children: React.ReactNode;
  style?: StyleProp<TextStyle>;
}

export function SectionTitle({ children, style }: SectionTitleProps) {
  return <Text style={[styles.sectionTitle, style]}>{children}</Text>;
}

interface BodyProps {
  children: React.ReactNode;
  style?: StyleProp<TextStyle>;
  muted?: boolean;
}

export function Body({ children, style, muted }: BodyProps) {
  return (
    <Text style={[styles.body, muted && { color: colors.textSecondary }, style]}>
      {children}
    </Text>
  );
}

interface BadgeProps {
  label: string;
  variant?: 'green' | 'yellow' | 'red' | 'neutral';
  testID?: string;
}

export function Badge({ label, variant = 'neutral', testID }: BadgeProps) {
  const palette =
    variant === 'green'
      ? colors.green
      : variant === 'yellow'
      ? colors.yellow
      : variant === 'red'
      ? colors.red
      : { bg: colors.borderLight, text: colors.textSecondary, border: colors.border };
  return (
    <View
      testID={testID}
      style={{
        paddingHorizontal: 12,
        paddingVertical: 6,
        borderRadius: radius.full,
        backgroundColor: palette.bg,
        borderWidth: 1,
        borderColor: palette.border,
        alignSelf: 'flex-start',
      }}
    >
      <Text style={{ color: palette.text, fontWeight: fontWeight.bold, fontSize: fontSize.sm }}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.md,
    ...shadows.card,
  },
  sectionTitle: {
    color: colors.textPrimary,
    fontSize: fontSize.xl,
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.2,
  },
  body: {
    color: colors.textPrimary,
    fontSize: fontSize.lg,
    lineHeight: 26,
  },
});
