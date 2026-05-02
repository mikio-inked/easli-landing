// /legal/contact — single contact page. Email is the canonical channel.
// Tap-to-mail uses Linking.openURL with the mailto: scheme so it works
// natively on iOS/Android and opens the user's default mail client on web.

import { useEffect, useState } from 'react';
import {
  Alert,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Clipboard from 'expo-clipboard';
import {
  ArrowLeft,
  CheckCircle2,
  Copy,
  Mail,
  ShieldCheck,
} from 'lucide-react-native';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from '../../src/theme';
import { LanguageCode, t } from '../../src/i18n';
import { getLanguage as getStoredLanguage } from '../../src/store';

// Replace this with the real address before publishing — it is also
// referenced from the Impressum / Privacy pages.
const CONTACT_EMAIL = 'kontakt@klarpost.app'; // [TODO]

export default function ContactScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      const stored = await getStoredLanguage();
      if (stored) setLang(stored);
    })();
  }, []);

  const onMail = async () => {
    const url = `mailto:${CONTACT_EMAIL}?subject=easli`;
    try {
      const can = await Linking.canOpenURL(url);
      if (can) {
        await Linking.openURL(url);
      } else if (Platform.OS === 'web') {
        // Some web browsers may not return canOpenURL=true for mailto;
        // attempting openURL will still hand off to the OS in most cases.
        await Linking.openURL(url);
      } else {
        Alert.alert('Email', CONTACT_EMAIL);
      }
    } catch {
      Alert.alert('Email', CONTACT_EMAIL);
    }
  };

  const onCopy = async () => {
    await Clipboard.setStringAsync(CONTACT_EMAIL);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <SafeAreaView style={styles.safe} testID="legal-contact-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="legal-contact-back">
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'contact')}</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.heroCard}>
          <View style={styles.heroIcon}>
            <Mail color={colors.white} size={26} strokeWidth={2.4} />
          </View>
          <Text style={styles.heroTitle}>{t(lang, 'contact')}</Text>
          <Text style={styles.heroSubtitle}>
            We answer in German or English. Please mention your easli language
            and the type of letter so we can help quickly.
          </Text>

          <Pressable
            onPress={onMail}
            style={({ pressed }) => [styles.mailBtn, pressed && { opacity: 0.85 }]}
            testID="legal-contact-mail"
            accessibilityRole="button"
            accessibilityLabel={`Email ${CONTACT_EMAIL}`}
          >
            <Mail color={colors.white} size={18} strokeWidth={2.5} />
            <Text style={styles.mailBtnLabel}>{CONTACT_EMAIL}</Text>
          </Pressable>

          <Pressable
            onPress={onCopy}
            style={styles.copyBtn}
            testID="legal-contact-copy"
            accessibilityRole="button"
            accessibilityLabel="Copy email address"
          >
            {copied ? (
              <CheckCircle2 color={colors.green.text} size={16} strokeWidth={2.5} />
            ) : (
              <Copy color={colors.primary} size={16} strokeWidth={2.5} />
            )}
            <Text style={[styles.copyBtnLabel, copied && { color: colors.green.text }]}>
              {copied ? 'Copied!' : 'Copy address'}
            </Text>
          </Pressable>
        </View>

        <View style={styles.docCard}>
          <Text style={styles.sectionHead}>Datenschutz / GDPR-related requests</Text>
          <Text style={styles.body}>
            Sie können Ihre Daten direkt in der App löschen oder exportieren
            (Einstellungen → Meine Daten). Falls Sie schriftlich Auskunft, Löschung,
            Berichtigung oder Datenübertragbarkeit nach Art. 15–21 DSGVO wünschen,
            schreiben Sie uns an die obige E-Mail-Adresse mit dem Betreff
            "DSGVO-Anfrage".
          </Text>
          <Text style={[styles.body, { marginTop: spacing.sm }]}>
            For GDPR requests (access, deletion, correction, portability) please email
            us with the subject "GDPR request".
          </Text>
        </View>

        <View style={styles.docCard}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <ShieldCheck color={colors.green.text} size={20} strokeWidth={2.5} />
            <Text style={styles.sectionHead}>What we will never ask for</Text>
          </View>
          <Text style={styles.body}>
            We will never ask for your full bank credentials, full credit-card
            numbers, or your easli analysis IDs by email. If you receive an
            email pretending to be easli asking for these, please forward it to
            us so we can warn other users.
          </Text>
        </View>

        <Text style={styles.footnote}>
          easli • Made with care in the EU
        </Text>
      </ScrollView>
    </SafeAreaView>
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
  heroCard: {
    backgroundColor: colors.primary,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    gap: spacing.md,
    alignItems: 'center',
    ...shadows.card,
  },
  heroIcon: {
    width: 56,
    height: 56,
    borderRadius: radius.lg,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroTitle: {
    color: colors.white,
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.4,
  },
  heroSubtitle: {
    color: colors.white,
    fontSize: fontSize.sm,
    lineHeight: 20,
    opacity: 0.95,
    textAlign: 'center',
    paddingHorizontal: spacing.sm,
  },
  mailBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: radius.full,
    marginTop: 4,
  },
  mailBtnLabel: {
    color: colors.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    letterSpacing: 0.2,
  },
  copyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  copyBtnLabel: {
    color: colors.white,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    opacity: 0.9,
  },
  docCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.sm,
  },
  sectionHead: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  body: {
    fontSize: fontSize.base,
    color: colors.textPrimary,
    lineHeight: 24,
  },
  footnote: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.md,
    fontStyle: 'italic',
  },
});
