// Reply-Language preference screen (Phase 4 / EU-1).
//
// Lets the user choose the global default behaviour for the reply draft's
// language. Two modes:
//
//   1. "Auto" (default) — match the detected sender language. e.g. a French
//      landlord letter → reply in French. This is what the existing Reply
//      Assistant already does per-analysis.
//
//   2. "Fixed" — always draft replies in a user-pinned language. Useful
//      for users who only ever want to reply in their native tongue
//      regardless of what the letter is in. When this mode is active the
//      user must pick one of the 32 REPLY_LANGUAGES.
//
// This is a GLOBAL preference. The per-analysis picker inside the Reply
// Assistant still overrides for a single letter.

import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, Check, Globe2, RefreshCw } from 'lucide-react-native';
import { Button } from '../src/ui';
import { LanguageCode, t } from '../src/i18n';
import { REPLY_LANGUAGES } from '../src/languages';
import { getAppLang, useReplyLangPref } from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

export default function ReplyLanguageScreen() {
  const router = useRouter();
  const [chromeLang, setChromeLang] = useState<LanguageCode>('en');
  const [pref, updatePref] = useReplyLangPref();
  const [localMode, setLocalMode] = useState<'auto' | 'fixed'>(pref.mode);
  const [localFixed, setLocalFixed] = useState<string | null>(pref.fixed);

  // Mirror the loaded pref into local edit state once it's available.
  useEffect(() => {
    setLocalMode(pref.mode);
    setLocalFixed(pref.fixed);
  }, [pref.mode, pref.fixed]);

  useEffect(() => {
    getAppLang().then(setChromeLang);
  }, []);

  const germanChrome = chromeLang === 'de_simple';

  const title = germanChrome ? 'Antwortsprache' : 'Reply language';
  const autoLabel = germanChrome ? 'Automatisch (Absender-Sprache)' : 'Automatic (match sender)';
  const autoSub = germanChrome
    ? 'Antworte in der Sprache des Briefes. Erkannt wird sie beim Scan.'
    : 'Reply in the same language the letter is written in. Detected automatically.';
  const fixedLabel = germanChrome ? 'Immer in fester Sprache' : 'Always in a fixed language';
  const fixedSub = germanChrome
    ? 'Antworte immer in der gewählten Sprache, unabhängig vom Absender.'
    : 'Always draft replies in your pinned language, regardless of the sender.';
  const pickLabel = germanChrome ? 'Antwortsprache wählen' : 'Pick reply language';
  const saveLabel = t(chromeLang, 'continue');

  const dirty = useMemo(
    () => localMode !== pref.mode || localFixed !== pref.fixed,
    [localMode, localFixed, pref.mode, pref.fixed],
  );
  const canSave = localMode === 'auto' || (localMode === 'fixed' && !!localFixed);

  const onSave = async () => {
    if (!canSave) return;
    await updatePref(localMode, localFixed);
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/settings');
    }
  };

  return (
    <SafeAreaView style={styles.safe} testID="reply-language-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="reply-language-back">
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Text style={styles.title}>{title}</Text>

        <View style={styles.modeList}>
          <Pressable
            onPress={() => setLocalMode('auto')}
            style={[styles.modeRow, localMode === 'auto' && styles.modeRowActive]}
            testID="reply-lang-mode-auto"
            accessibilityRole="radio"
            accessibilityState={{ selected: localMode === 'auto' }}
          >
            <View style={styles.modeIconWrap}>
              <RefreshCw color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.modeLabel}>{autoLabel}</Text>
              <Text style={styles.modeSub}>{autoSub}</Text>
            </View>
            <View
              style={[
                styles.radioDot,
                localMode === 'auto' && { borderColor: colors.primary },
              ]}
            >
              {localMode === 'auto' ? <View style={styles.radioDotInner} /> : null}
            </View>
          </Pressable>

          <Pressable
            onPress={() => setLocalMode('fixed')}
            style={[styles.modeRow, localMode === 'fixed' && styles.modeRowActive]}
            testID="reply-lang-mode-fixed"
            accessibilityRole="radio"
            accessibilityState={{ selected: localMode === 'fixed' }}
          >
            <View style={styles.modeIconWrap}>
              <Globe2 color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.modeLabel}>{fixedLabel}</Text>
              <Text style={styles.modeSub}>{fixedSub}</Text>
            </View>
            <View
              style={[
                styles.radioDot,
                localMode === 'fixed' && { borderColor: colors.primary },
              ]}
            >
              {localMode === 'fixed' ? <View style={styles.radioDotInner} /> : null}
            </View>
          </Pressable>
        </View>

        {localMode === 'fixed' ? (
          <View style={styles.fixedPicker}>
            <Text style={styles.sectionHeader}>{pickLabel}</Text>
            <View style={styles.list}>
              {REPLY_LANGUAGES.map((l) => {
                const isActive = localFixed === l.code;
                return (
                  <Pressable
                    key={l.code}
                    onPress={() => setLocalFixed(l.code)}
                    style={[styles.item, isActive && styles.itemActive]}
                    testID={`reply-lang-fixed-${l.code}`}
                    accessibilityRole="button"
                    accessibilityState={{ selected: isActive }}
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
                      {isActive ? <Check color={colors.white} size={18} strokeWidth={3} /> : null}
                    </View>
                  </Pressable>
                );
              })}
            </View>
          </View>
        ) : null}
      </ScrollView>
      <View style={styles.footer}>
        <Button label={saveLabel} onPress={onSave} disabled={!canSave || !dirty} testID="reply-language-save" />
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
    fontWeight: fontWeight.extrabold as any,
    color: colors.textPrimary,
    letterSpacing: -0.6,
    marginBottom: spacing.sm,
  },
  modeList: {
    gap: spacing.sm,
  },
  modeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 2,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    minHeight: 72,
  },
  modeRowActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  modeIconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modeLabel: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold as any,
    color: colors.textPrimary,
  },
  modeSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 20,
  },
  radioDot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioDotInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.primary,
  },
  fixedPicker: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  sectionHeader: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold as any,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingLeft: spacing.xs,
  },
  list: {
    gap: spacing.sm,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 2,
    borderColor: colors.borderLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    minHeight: 62,
  },
  itemActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  flag: { fontSize: 26 },
  itemTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold as any,
    color: colors.textPrimary,
  },
  itemSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  checkChip: {
    width: 26,
    height: 26,
    borderRadius: 13,
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
