// Privacy / data-protection screen.
//
// Shown from Settings (and linked from the Home EU badge). Lays out KlarPost's
// data handling clearly in the user's selected language. Static content — the
// keys live in /src/i18n.ts and are translated for all 7 languages.

import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft,
  Eye,
  Globe2,
  Server,
  ShieldCheck,
  Trash2,
  Users,
} from 'lucide-react-native';
import { Card } from '../src/ui';
import { LanguageCode, t, UIKey } from '../src/i18n';
import { getLanguage as getStoredLanguage } from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

interface Section {
  icon: React.ComponentType<{ color: string; size: number; strokeWidth: number }>;
  titleKey: UIKey;
  bodyKey: UIKey;
  tint?: string;
  bg?: string;
}

const SECTIONS: Section[] = [
  {
    icon: Globe2,
    titleKey: 'privacy_h_residency',
    bodyKey: 'privacy_p_residency',
    tint: colors.green.text,
    bg: colors.green.bg,
  },
  {
    icon: Eye,
    titleKey: 'privacy_h_collect',
    bodyKey: 'privacy_p_collect',
  },
  {
    icon: Trash2,
    titleKey: 'privacy_h_delete',
    bodyKey: 'privacy_p_delete',
  },
  {
    icon: ShieldCheck,
    titleKey: 'privacy_h_no_tracking',
    bodyKey: 'privacy_p_no_tracking',
    tint: colors.green.text,
    bg: colors.green.bg,
  },
  {
    icon: Users,
    titleKey: 'privacy_h_third_parties',
    bodyKey: 'privacy_p_third_parties',
  },
];

export default function PrivacyScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');

  useFocusEffect(
    useCallback(() => {
      getStoredLanguage().then((l) => setLang(l ?? 'en'));
    }, [])
  );

  return (
    <SafeAreaView style={styles.safe} testID="privacy-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="privacy-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'privacy_policy')}</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.heroChip}>
          <ShieldCheck color={colors.primary} size={18} strokeWidth={2.6} />
          <Text style={styles.heroChipText}>{t(lang, 'eu_badge')} · {t(lang, 'eu_badge_sub')}</Text>
        </View>
        <Text style={styles.intro}>{t(lang, 'privacy_intro')}</Text>

        {SECTIONS.map((s) => {
          const Icon = s.icon;
          const tint = s.tint ?? colors.primary;
          const bg = s.bg ?? colors.primarySoft;
          return (
            <Card key={s.titleKey}>
              <View style={styles.row}>
                <View style={[styles.rowIcon, { backgroundColor: bg }]}>
                  <Icon color={tint} size={20} strokeWidth={2.4} />
                </View>
                <Text style={styles.sectionTitle}>{t(lang, s.titleKey)}</Text>
              </View>
              <Text style={styles.sectionBody}>{t(lang, s.bodyKey)}</Text>
            </Card>
          );
        })}

        <View style={styles.metaRow}>
          <Server color={colors.textMuted} size={14} strokeWidth={2.4} />
          <Text style={styles.meta}>Mistral AI · Paris, France 🇫🇷</Text>
        </View>
        <Text style={styles.updated}>{t(lang, 'privacy_updated')}</Text>
        <Text style={styles.footer}>support@klarpost.app</Text>
      </ScrollView>
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
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  heroChip: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    marginBottom: 4,
  },
  heroChipText: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    color: colors.primary,
  },
  intro: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    lineHeight: 23,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  rowIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sectionTitle: {
    flex: 1,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  sectionBody: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 22,
    marginTop: spacing.sm,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    justifyContent: 'center',
    marginTop: spacing.lg,
  },
  meta: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
  },
  updated: {
    textAlign: 'center',
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 4,
  },
  footer: {
    textAlign: 'center',
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
});
