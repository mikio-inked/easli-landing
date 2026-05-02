// /legal — landing page that lists Impressum / Privacy / Contact. Designed
// to be discoverable from inside the app (Settings → Legal) AND to work as
// a public web URL the App Store / Play Store reviewer can visit.

import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft,
  ChevronRight,
  FileText,
  Mail,
  ShieldCheck,
} from 'lucide-react-native';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from '../../src/theme';
import { useEffect, useState } from 'react';
import { LanguageCode, t } from '../../src/i18n';
import { getLanguage as getStoredLanguage } from '../../src/store';

export default function LegalIndexScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');

  useEffect(() => {
    (async () => {
      const stored = await getStoredLanguage();
      if (stored) setLang(stored);
    })();
  }, []);

  return (
    <SafeAreaView style={styles.safe} testID="legal-index-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="legal-back">
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'legal')}</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.subtitle}>{t(lang, 'legal_subtitle')}</Text>

        <Card
          icon={<FileText color={colors.primary} size={22} strokeWidth={2.4} />}
          title={t(lang, 'impressum')}
          subtitle={t(lang, 'impressum_subtitle')}
          onPress={() => router.push('/legal/impressum' as any)}
          testID="legal-card-impressum"
        />

        <Card
          icon={<ShieldCheck color={colors.green.text} size={22} strokeWidth={2.4} />}
          iconBg={colors.green.bg}
          title={t(lang, 'privacy_policy')}
          subtitle={t(lang, 'privacy_short')}
          onPress={() => router.push('/legal/privacy' as any)}
          testID="legal-card-privacy"
        />

        <Card
          icon={<Mail color={colors.primary} size={22} strokeWidth={2.4} />}
          title={t(lang, 'contact')}
          subtitle={t(lang, 'contact_subtitle')}
          onPress={() => router.push('/legal/contact' as any)}
          testID="legal-card-contact"
        />

        <Text style={styles.footnote}>
          easli • Made with care in the EU
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Card({
  icon,
  iconBg,
  title,
  subtitle,
  onPress,
  testID,
}: {
  icon: React.ReactNode;
  iconBg?: string;
  title: string;
  subtitle: string;
  onPress: () => void;
  testID?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && { opacity: 0.7 }]}
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={title}
    >
      <View style={[styles.cardIcon, iconBg ? { backgroundColor: iconBg } : null]}>
        {icon}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.cardTitle}>{title}</Text>
        <Text style={styles.cardSubtitle}>{subtitle}</Text>
      </View>
      <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    gap: spacing.md,
    maxWidth: 720,
    alignSelf: 'center',
    width: '100%',
  },
  subtitle: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    lineHeight: 22,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    minHeight: 64,
    ...shadows.card,
  },
  cardIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    letterSpacing: -0.2,
  },
  cardSubtitle: {
    marginTop: 2,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  footnote: {
    marginTop: spacing.xl,
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textAlign: 'center',
  },
});
