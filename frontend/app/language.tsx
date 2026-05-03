// Language picker. Shown after onboarding (or from settings).
//
// Since Phase 4 (EU-1) this screen operates in two independent modes
// controlled by the `mode` query param:
//
//   mode='app'         — picks the UI-chrome language (7 first-class
//                        hand-translated bundles). Saves to
//                        `setAppLangOverride`. Used for users who want
//                        German UI but their AI explanations in a
//                        different tongue (e.g. Polish).
//
//   mode='explanation' — (default) picks the AI explanation language
//                        (25 options). Saves to `setExplanationLang`.
//                        Matches the previous /language behaviour.

import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, Check } from 'lucide-react-native';
import { Button } from '../src/ui';
import { LANGUAGES, LanguageCode, t } from '../src/i18n';
import { EXPLANATION_LANGUAGES, LanguageEntry, normalizeLanguageCode } from '../src/languages';
import {
  getAppLang,
  getAppLangOverride,
  getExplanationLang,
  isOnboarded,
  setAppLangOverride,
  setExplanationLang,
} from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

type PickerMode = 'app' | 'explanation';

export default function LanguageScreen() {
  const router = useRouter();
  const { from, mode } = useLocalSearchParams<{ from?: string; mode?: string }>();
  const pickerMode: PickerMode = mode === 'app' ? 'app' : 'explanation';
  const [selected, setSelected] = useState<LanguageCode | null>(null);
  const [initial, setInitial] = useState<LanguageCode | null>(null);

  useEffect(() => {
    // App-Language picker reads the override (may be null → no row selected,
    // which is fine — the resolved fallback is still shown in Settings).
    // Explanation-Language picker reads the raw explanation pref.
    const loader = pickerMode === 'app' ? getAppLangOverride() : getExplanationLang();
    loader.then((v) => {
      setInitial(v);
      setSelected(v);
    });
  }, [pickerMode]);

  const canGoBack = from !== 'onboarding' && from !== 'gateway';

  // Normalise the currently-stored code against the registry so a legacy
  // `de_simple` pick still highlights the single "Deutsch" row and doesn't
  // leave the list looking unselected. App-mode shows the 7-language
  // LANGUAGES list — code stays as-is (`de_simple` is a valid row there).
  const selectedKey = useMemo(() => {
    if (!selected) return null;
    if (pickerMode === 'app') {
      return selected.toLowerCase();
    }
    const norm = normalizeLanguageCode(selected).toLowerCase();
    return norm === 'de_simple' ? 'de' : norm;
  }, [selected, pickerMode]);

  // The active registry for this picker. App-mode: the 7 first-class
  // UI-translated bundles (from i18n.ts). Explanation-mode: the 25-
  // language EU-1 registry.
  const entries: LanguageEntry[] = useMemo(() => {
    if (pickerMode === 'app') {
      return LANGUAGES.map((l) => ({
        code: l.code,
        nativeName: l.nativeName,
        englishName: l.englishName,
        flag: l.flag,
      }));
    }
    return EXPLANATION_LANGUAGES;
  }, [pickerMode]);

  const onContinue = async () => {
    if (!selected) return;
    if (pickerMode === 'app') {
      await setAppLangOverride(selected);
    } else {
      await setExplanationLang(selected);
    }
    // First-run path: language picker is shown BEFORE the onboarding tutorial,
    // so we route into onboarding. From any other entry (settings / change-
    // language) we just go back or home.
    if (from === 'gateway') {
      const onboarded = await isOnboarded();
      if (!onboarded) {
        router.replace('/onboarding');
        return;
      }
    }
    if (canGoBack && router.canGoBack()) {
      router.back();
    } else {
      router.replace('/home');
    }
  };

  // Chrome lang for titles/buttons on THIS screen — we always resolve to the
  // UI-translated fallback via getAppLang() for predictable copy.
  const [chromeLang, setChromeLang] = useState<LanguageCode>('en');
  useEffect(() => {
    getAppLang().then(setChromeLang);
  }, [selected]);

  // Copy for the title/subtitle. App-mode uses a Settings-specific caption
  // to explain that this is the UI language, distinct from the AI
  // explanation language. Hardcoded English with a German variant — a full
  // i18n matrix for this sub-screen isn't worth 14×2 new keys.
  const germanChrome = chromeLang === 'de_simple';
  const title = pickerMode === 'app'
    ? (germanChrome ? 'App-Sprache' : 'App language')
    : t(chromeLang, 'choose_language');
  const subtitle = pickerMode === 'app'
    ? (germanChrome
        ? 'Sprache der Menüs, Buttons und Fehlermeldungen.'
        : 'The language of menus, buttons and error messages.')
    : t(chromeLang, 'choose_language_subtitle');

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
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.subtitle}>{subtitle}</Text>
        <View style={styles.list}>
          {entries.map((l) => {
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
