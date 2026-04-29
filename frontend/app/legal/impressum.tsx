// /legal/impressum — German legal disclosure required by § 5 TMG.
//
// IMPORTANT: All entity-specific values are placeholders ([TODO ...]).
// Replace before publishing on the App Store / Play Store / public web.
//
// Layout: bilingual (German first because the legal source language is
// German for the German market, then a short English translation summary).

import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft } from 'lucide-react-native';
import { colors, fontSize, fontWeight, radius, spacing } from '../../src/theme';
import { useEffect, useState } from 'react';
import { LanguageCode, t } from '../../src/i18n';
import { getLanguage as getStoredLanguage } from '../../src/store';

export default function ImpressumScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');

  useEffect(() => {
    (async () => {
      const stored = await getStoredLanguage();
      if (stored) setLang(stored);
    })();
  }, []);

  return (
    <SafeAreaView style={styles.safe} testID="legal-impressum-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="legal-impressum-back">
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'impressum')}</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* ========== DEUTSCH ========== */}
        <View style={styles.docCard}>
          <Text style={styles.docTitle}>Impressum</Text>
          <Text style={styles.docKicker}>Angaben gemäß § 5 TMG</Text>

          <Section title="Anbieter">
            <Text style={styles.body}>Martin Tran</Text>
            <Text style={styles.body}>Freiberuflich tätig</Text>
            <Text style={styles.body}>Alfred-Delp-Str. 33</Text>
            <Text style={styles.body}>68623 Lampertheim</Text>
            <Text style={styles.body}>Deutschland</Text>
          </Section>

          <Section title="Vertreten durch">
            <Text style={styles.body}>Martin Tran</Text>
          </Section>

          <Section title="Kontakt">
            <Text style={styles.body}>E-Mail: kontakt@klarpost.app</Text>
          </Section>

          <Section title="Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV">
            <Text style={styles.body}>Martin Tran</Text>
            <Text style={styles.body}>Anschrift wie oben</Text>
          </Section>

          <Section title="Haftung für Inhalte">
            <Text style={styles.body}>
              Als Diensteanbieter sind wir gemäß § 7 Abs. 1 TMG für eigene Inhalte auf
              diesen Seiten nach den allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis
              10 TMG sind wir als Diensteanbieter jedoch nicht verpflichtet, übermittelte
              oder gespeicherte fremde Informationen zu überwachen oder nach Umständen
              zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen.
            </Text>
            <Text style={styles.body}>
              Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen
              nach den allgemeinen Gesetzen bleiben hiervon unberührt. Eine diesbezügliche
              Haftung ist jedoch erst ab dem Zeitpunkt der Kenntnis einer konkreten
              Rechtsverletzung möglich. Bei Bekanntwerden von entsprechenden
              Rechtsverletzungen werden wir diese Inhalte umgehend entfernen.
            </Text>
          </Section>

          <Section title="Haftung für Links">
            <Text style={styles.body}>
              Unser Angebot enthält ggf. Links zu externen Websites Dritter, auf deren
              Inhalte wir keinen Einfluss haben. Deshalb können wir für diese fremden
              Inhalte auch keine Gewähr übernehmen. Für die Inhalte der verlinkten
              Seiten ist stets der jeweilige Anbieter oder Betreiber der Seiten
              verantwortlich.
            </Text>
          </Section>

          <Section title="Urheberrecht">
            <Text style={styles.body}>
              Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen
              Seiten unterliegen dem deutschen Urheberrecht. Die Vervielfältigung,
              Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der
              Grenzen des Urheberrechtes bedürfen der schriftlichen Zustimmung des
              jeweiligen Autors bzw. Erstellers.
            </Text>
          </Section>

          <Section title="Streitschlichtung">
            <Text style={styles.body}>
              Die Europäische Kommission stellt eine Plattform zur Online-
              Streitbeilegung (OS) bereit:{'\n'}
              https://ec.europa.eu/consumers/odr{'\n'}
              Unsere E-Mail-Adresse finden Sie oben im Impressum.
            </Text>
            <Text style={styles.body}>
              Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren
              vor einer Verbraucherschlichtungsstelle teilzunehmen.
            </Text>
          </Section>
        </View>

        {/* ========== ENGLISH ========== */}
        <View style={styles.docCard}>
          <Text style={styles.docTitleEn}>Imprint (English summary)</Text>
          <Text style={styles.docKicker}>Statutory information according to § 5 TMG</Text>

          <Section title="Provider">
            <Text style={styles.body}>Martin Tran</Text>
            <Text style={styles.body}>Freelancer (independent professional)</Text>
            <Text style={styles.body}>Alfred-Delp-Str. 33</Text>
            <Text style={styles.body}>68623 Lampertheim</Text>
            <Text style={styles.body}>Germany</Text>
          </Section>

          <Section title="Represented by">
            <Text style={styles.body}>Martin Tran</Text>
          </Section>

          <Section title="Contact">
            <Text style={styles.body}>Email: kontakt@klarpost.app</Text>
          </Section>

          <Section title="Editorially responsible (§ 18 (2) MStV)">
            <Text style={styles.body}>Martin Tran, address as above</Text>
          </Section>

          <Section title="Liability for content & links">
            <Text style={styles.body}>
              As a service provider we are responsible for our own content on this
              site according to general laws (§ 7 (1) TMG). According to §§ 8 to 10
              TMG we are however not obliged to monitor third-party information or
              to investigate circumstances pointing to illegal activity. The full
              German wording above is the legally binding version.
            </Text>
          </Section>

          <Section title="Online dispute resolution">
            <Text style={styles.body}>
              The European Commission provides a platform for online dispute
              resolution: https://ec.europa.eu/consumers/odr{'\n'}
              We are neither willing nor obliged to participate in dispute resolution
              proceedings before a consumer arbitration board.
            </Text>
          </Section>
        </View>

        <Text style={styles.footnote}>
          Last updated: April 2026. The German version above is the legally
          binding version.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <View style={styles.sectionBody}>{children}</View>
    </View>
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
  docCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.md,
  },
  docTitle: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  docTitleEn: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  docKicker: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: fontWeight.medium,
    letterSpacing: 0.2,
  },
  section: {
    gap: 6,
  },
  sectionTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  sectionBody: {
    gap: 6,
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
