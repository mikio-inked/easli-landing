// Language picker. Shown after onboarding (or from settings).
//
// Since Phase EU-1 this picker shows all 25 EXPLANATION_LANGUAGES. For the
// 7 languages with hand-translated UI chrome we show "Deutsch", "English",
// etc. in the user's chosen language; for the other 18, the AI explanation
// renders in that language while the UI chrome stays English.

import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, Check } from 'lucide-react-native';
import { Button } from '../src/ui';
import { LanguageCode, t } from '../src/i18n';
import { EXPLANATION_LANGUAGES, normalizeLanguageCode } from '../src/languages';
import { getLanguage, isOnboarded, setLanguage } from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

export default function LanguageScreen() {
  const router = useRouter();
  const { from } = useLocalSearchParams<{ from?: string }>();
  const [selected, setSelected] = useState<LanguageCode | null>(null);
  const [initial, setInitial] = useState<LanguageCode | null>(null);

  useEffect(() => {
    getLanguage().then((v) => {
      setInitial(v);
      setSelected(v);
    });
  }, []);

  const canGoBack = from !== 'onboarding' && from !== 'gateway';

  // Normalise the currently-stored code against the registry so a legacy
  // `de_simple` pick still highlights the single "Deutsch" row and doesn't
  // leave the list looking unselected.
  const selectedKey = useMemo(() => {
    if (!selected) return null;
    const norm = normalizeLanguageCode(selected).toLowerCase();
    // `de_simple` maps to `de` in EXPLANATION_LANGUAGES.
    return norm === 'de_simple' ? 'de' : norm;
  }, [selected]);

  const onContinue = async () => {
    if (!selected) return;
    await setLanguage(selected);
    // First-run path: language picker is shown BEFORE the onboarding tutorial,
    // so we route into onboarding. From any other entry (settings / change-
    // language) we just go home.
    if (from === 'gateway') {
      const onboarded = await isOnboarded();
      if (!onboarded) {
        router.replace('/onboarding');
        return;
      }
    }
    router.replace('/home');
  };

  // For the onboarding/gateway path we use English chrome until they pick.
  // After that we can render in their chosen language live.
  const chromeLang: LanguageCode = selected ?? initial ?? 'en';

  return (
    <SafeAreaView style={styles.safe} testID="language-screen">
      <View style={styles.header}>
        {canGoBack ? (
          <Pressable onPress={() => router.back()} testID="language-back" hitSlop={12}>
            <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
          </Pressable>
        ) : (
          <View style={{ width: 26 }} />
        )}
        <View style={{ width: 26 }} />
      </View>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>{t(chromeLang, 'choose_language')}</Text>
        <Text style={styles.subtitle}>{t(chromeLang, 'choose_language_subtitle')}</Text>
        <View style={styles.list}>
          {EXPLANATION_LANGUAGES.map((l) => {
            const lcode = l.code.toLowerCase();
            const isActive = selectedKey === lcode;
            return (
              <Pressable
                key={l.code}
                onPress={() => setSelected(l.code as LanguageCode)}
                style={[styles.item, isActive && styles.itemActive]}
                testID={`language-option-${l.code}`}
                accessibilityRole="button"
                accessibilityState={{ selected: isActive }}
                accessibilityLabel={l.englishName}
              >
                <Text style={styles.flag}>{l.flag}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.itemTitle}>{l.nativeName}</Text>
                  <Text style={styles.itemSubtitle}>{l.englishName}</Text>
                </View>
                <View
                  style={[
                    styles.checkChip,
                    isActive && { backgroundColor: colors.primary, borderColor: colors.primary },
                  ]}
                >
                  {isActive ? (
                    <Check color={colors.white} size={18} strokeWidth={3} />
                  ) : null}
                </View>
              </Pressable>
            );
          })}
        </View>
      </ScrollView>
      <View style={styles.footer}>
        <Button
          label={t(chromeLang, 'continue')}
          onPress={onContinue}
          disabled={!selected}
          testID="language-continue"
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },
  title: {
    fontSize: fontSize['3xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.6,
  },
  subtitle: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: spacing.sm,
  },
  list: {
    gap: spacing.sm,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderWidth: 2,
    borderColor: colors.borderLight,
    minHeight: 68,
    gap: spacing.md,
  },
  itemActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  flag: { fontSize: 28 },
  itemTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  itemSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  checkChip: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
});
