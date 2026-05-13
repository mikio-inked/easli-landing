// Full-screen lock overlay shown by the root layout when biometric lock
// is enabled. Calls the OS auth sheet immediately on mount, and again
// whenever the user taps the manual "Unlock" button (e.g. after the
// initial prompt was cancelled).
//
// While locked we hide the whole app behind the easli wordmark so any
// shoulder-surfer just sees branding, not the user's letters.

import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Image } from 'expo-image';
import { Lock } from 'lucide-react-native';
import { authenticate } from './appLock';
import { LanguageCode, t } from './i18n';
import { colors, fontSize, fontWeight, radius, spacing } from './theme';

interface Props {
  lang: LanguageCode;
  onUnlocked: () => void;
}

export function LockScreen({ lang, onUnlocked }: Props) {
  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const ok = await authenticate(t(lang, 'app_lock_prompt'));
      if (ok) onUnlocked();
    } finally {
      setBusy(false);
    }
  };

  // Auto-prompt on mount — common iOS UX (the user opened the app, they
  // expect Face ID to immediately ask).
  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <View style={styles.root} testID="app-lock-screen">
      <Image
        source={require('../assets/images/easli-icon.png')}
        style={styles.logo}
        contentFit="contain"
      />
      <Text style={styles.title}>{t(lang, 'app_lock_title')}</Text>
      <Text style={styles.subtitle}>{t(lang, 'app_lock_subtitle')}</Text>
      <Pressable
        onPress={run}
        style={({ pressed }) => [styles.cta, pressed && { opacity: 0.85 }]}
        disabled={busy}
        testID="app-lock-unlock-button"
        accessibilityRole="button"
      >
        <Lock color={colors.white} size={18} strokeWidth={2.4} />
        <Text style={styles.ctaText}>{t(lang, 'app_lock_unlock')}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
  },
  logo: {
    width: 96,
    height: 96,
    marginBottom: spacing.lg,
  },
  title: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
    lineHeight: 22,
  },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    minHeight: 48,
  },
  ctaText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
  },
});
