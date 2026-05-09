// /legal/privacy — formal GDPR/DSGVO privacy policy. This is the public,
// legally-binding version. The in-app /privacy screen is a friendly summary
// for the user; this is the document the App Store / Play Store reviewer
// links to.
//
// Bilingual: German first (binding for the German market) + English summary.
// All operator-specific values are filled below (anchor: Verantwortliche Stelle).

import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft } from 'lucide-react-native';
import { colors, fontSize, fontWeight, radius, spacing } from '../../src/theme';
import { useEffect, useState } from 'react';
import { LanguageCode, t } from '../../src/i18n';
import { getLanguage as getStoredLanguage } from '../../src/store';

export default function PrivacyPublicScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');

  useEffect(() => {
    (async () => {
      const stored = await getStoredLanguage();
      if (stored) setLang(stored);
    })();
  }, []);

  return (
    <SafeAreaView style={styles.safe} testID="legal-privacy-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="legal-privacy-back">
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'privacy_policy')}</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* ========== DEUTSCH ========== */}
        <View style={styles.docCard}>
          <Text style={styles.docTitle}>Datenschutzerklärung</Text>
          <Text style={styles.docKicker}>
            Information gemäß Art. 13 / 14 DSGVO • Letzte Aktualisierung: April 2026
          </Text>

          <Section title="1. Verantwortlicher">
            <Text style={styles.body}>
              Verantwortlicher im Sinne der DSGVO ist:{'\n'}
              Martin Tran (Freiberufler){'\n'}
              Alfred-Delp-Str. 33{'\n'}
              68623 Lampertheim, Deutschland{'\n'}
              E-Mail: kontakt@easli.app
            </Text>
          </Section>

          <Section title="2. Welche Daten verarbeiten wir?">
            <Text style={styles.body}>
              easli ist bewusst datenarm gebaut. Wir verarbeiten nur die folgenden
              Daten, und nur dann, wenn Sie die App aktiv nutzen:
            </Text>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Anonyme Geräte-ID:</Text> Eine zufällige UUID,
                die ausschließlich auf Ihrem Gerät erzeugt wird. Sie enthält keine
                Apple-/Google-/Werbe-IDs und ist mit keiner E-Mail-Adresse verknüpft.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Briefinhalt zur Analyse:</Text> Das von Ihnen
                aufgenommene Foto bzw. PDF wird verschlüsselt an unseren Server in der EU
                gesendet und sofort an Mistral AI (Paris, EU) zur Analyse weitergeleitet.
                Das Bild bzw. PDF selbst wird <Text style={styles.bold}>nicht</Text> dauerhaft
                gespeichert.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Strukturiertes Analyseergebnis:</Text>
                {' '}Zusammenfassung, Kategorisierung, Fristen, Antwortentwurf usw. werden
                in unserer MongoDB-Datenbank in der EU gespeichert und sind ausschließlich
                über Ihre anonyme Geräte-ID abrufbar.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Nutzungs-Zähler:</Text> Anzahl der Analysen, um
                das kostenlose Kontingent durchzusetzen. Keine Inhaltsdaten.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Nicht erhoben:</Text> Name, Adresse, Geburtsdatum,
                Standort, Telefon-IDs, Werbe-IDs, Cookies, Tracking.
              </Text>
            </Bullet>
          </Section>

          <Section title="3. Zwecke und Rechtsgrundlagen">
            <Text style={styles.body}>
              Die Verarbeitung erfolgt zur Erbringung des von Ihnen angeforderten Dienstes
              (Übersetzen und Erklären deutscher Behörden- und Geschäftspost) auf Grundlage
              von <Text style={styles.bold}>Art. 6 Abs. 1 lit. b DSGVO</Text> (Vertrag bzw.
              vorvertragliche Maßnahmen).
            </Text>
            <Text style={styles.body}>
              Soweit wir Daten zur Verbesserung der Dienstqualität verarbeiten, geschieht
              dies auf Basis von <Text style={styles.bold}>Art. 6 Abs. 1 lit. f DSGVO</Text>
              {' '}(berechtigtes Interesse an einem stabilen, missbrauchsfreien Betrieb).
            </Text>
          </Section>

          <Section title="4. Empfänger / Auftragsverarbeiter">
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Mistral AI</Text> (96 Boulevard Haussmann, 75008
                Paris, Frankreich). Sprachmodell für OCR, Analyse und Erklärung. Daten
                werden in der EU verarbeitet, kein Transfer in Drittländer für easli-Anfragen.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>MongoDB Atlas</Text> (MongoDB Limited, EU-Region
                Frankfurt). Speicherung der strukturierten Analyseergebnisse.
                Auftragsverarbeitungsvertrag (AVV) gemäß Art. 28 DSGVO geschlossen.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Railway Corp.</Text> (USA, mit Server-Standort
                EU). Hosting des Backend-Servers (api.easli.app). Standardvertragsklauseln
                der EU-Kommission, Daten werden in einer EU-Region gehostet.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>RevenueCat, Inc.</Text> (USA), nur falls Sie
                ein Abonnement abschließen. Es werden ausschließlich App-interne
                Kauf-IDs (kein Klartext-Identifier) übertragen. Standardvertragsklauseln
                EU-Kommission. Im Soft-Mode (Beta) deaktiviert.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Apple App Store / Google Play Store</Text>
                {' '}— für die Bereitstellung der App und die Abwicklung von Käufen. Zahlungs-
                und Abrechnungsdaten verarbeiten Apple/Google in eigener Verantwortung.
              </Text>
            </Bullet>
          </Section>

          <Section title="5. Speicherdauer">
            <Text style={styles.body}>
              Analyseergebnisse werden in unserer Datenbank automatisch nach
              <Text style={styles.bold}> 90 Tagen </Text>
              gelöscht (TTL-Index). Sie können Ihre Daten jederzeit selbst löschen über
              {' '}<Text style={styles.bold}>Einstellungen → Meine Daten löschen</Text>.
              Originale (Foto, PDF, OCR-Volltext) werden niemals dauerhaft gespeichert.
            </Text>
            <Text style={styles.body}>
              <Text style={styles.bold}>Gesetzliche Aufbewahrungspflichten:</Text> Für
              Rechnungen und steuerrelevante Unterlagen gelten Aufbewahrungsfristen von
              bis zu <Text style={styles.bold}>10 Jahren</Text> (§ 147 AO, § 257 HGB).
              Diese betreffen Zahlungs- und Abrechnungsdaten, die ausschließlich bei
              Apple, Google und RevenueCat verarbeitet und dort gemäß deren
              Datenschutzrichtlinien gespeichert werden. easli selbst erhält und
              speichert keine Klartext-Zahlungs- oder Rechnungsdaten.
            </Text>
          </Section>

          <Section title="6. Keine KI-Trainingsnutzung">
            <Text style={styles.body}>
              Ihre Briefe, Fragen und Antwortentwürfe werden
              <Text style={styles.bold}> nicht zum Training </Text>
              von KI-Modellen verwendet — weder durch uns noch durch unsere
              Auftragsverarbeiter.
            </Text>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Mistral AI</Text> (Paris, EU) verarbeitet Ihre
                Daten ausschließlich zur Beantwortung der jeweiligen Anfrage und
                garantiert vertraglich, dass API-Anfragen
                {' '}<Text style={styles.bold}>nicht</Text> zur Verbesserung oder zum
                Training von Modellen genutzt werden
                (<Text style={styles.italic}>Mistral AI Data Processing Addendum</Text>).
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>easli</Text> analysiert keine Inhalte, erstellt
                keine Nutzerprofile und verkauft keine Daten an Dritte.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                Analysen werden pro Gerät gespeichert und sind ausschließlich über Ihre
                anonyme Geräte-ID abrufbar. Keine Verknüpfung mit E-Mail, Name oder
                sonstigen Identifikatoren.
              </Text>
            </Bullet>
          </Section>

          <Section title="7. Ihre Rechte (Art. 15–21 DSGVO)">
            <Text style={styles.body}>
              Sie haben das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Löschung
              (Art. 17), Einschränkung (Art. 18), Datenübertragbarkeit (Art. 20) und
              Widerspruch (Art. 21). Diese Rechte können Sie direkt in der App ausüben:
            </Text>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Datenexport</Text>. Einstellungen → Meine Daten
                exportieren (JSON).
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Löschung</Text>. Einstellungen → Meine Daten
                löschen.
              </Text>
            </Bullet>
            <Text style={styles.body}>
              Alternativ erreichen Sie uns per E-Mail unter kontakt@easli.app.
            </Text>
          </Section>

          <Section title="8. Beschwerderecht">
            <Text style={styles.body}>
              Sie haben das Recht, sich bei einer Aufsichtsbehörde zu beschweren. Für
              easli ist die zuständige Aufsichtsbehörde:
            </Text>
            <Text style={styles.body}>
              <Text style={styles.bold}>
                Der Hessische Beauftragte für Datenschutz und Informationsfreiheit (HBDI)
              </Text>
              {'\n'}Gustav-Stresemann-Ring 1{'\n'}
              65189 Wiesbaden{'\n'}
              Telefon: +49 611 1408-0{'\n'}
              E-Mail: poststelle@datenschutz.hessen.de{'\n'}
              Web: www.datenschutz.hessen.de
            </Text>
            <Text style={styles.body}>
              Alternativ können Sie sich an die für Ihren Wohnsitz zuständige
              Landesdatenschutzbehörde oder an den Bundesbeauftragten für den
              Datenschutz und die Informationsfreiheit (BfDI) wenden.
            </Text>
          </Section>

          <Section title="9. Sicherheit">
            <Text style={styles.body}>
              Übertragungen erfolgen ausschließlich verschlüsselt (TLS). API-Schlüssel,
              Briefinhalte und IP-Adressen werden nicht in Klartext geloggt. Logs enthalten
              ausschließlich anonymisierte Metadaten (z. B. Zeitstempel, Endpunkt, Status
              und die anonyme Geräte-ID).
            </Text>
          </Section>

          <Section title="10. Änderungen dieser Erklärung">
            <Text style={styles.body}>
              Wir können diese Erklärung anpassen, sofern technische oder rechtliche
              Änderungen das erforderlich machen. Die jeweils aktuelle Fassung ist über
              diesen Bildschirm bzw. über unsere Website abrufbar.
            </Text>
          </Section>
        </View>

        {/* ========== ENGLISH SUMMARY ========== */}
        <View style={styles.docCard}>
          <Text style={styles.docTitleEn}>Privacy policy (English summary)</Text>
          <Text style={styles.docKicker}>
            Information per Art. 13 / 14 GDPR • Last updated: April 2026
          </Text>

          <Section title="Controller">
            <Text style={styles.body}>
              Martin Tran (Freelancer){'\n'}Alfred-Delp-Str. 33{'\n'}68623 Lampertheim, Germany{'\n'}
              Email: kontakt@easli.app
            </Text>
          </Section>

          <Section title="Data we process">
            <Bullet>
              <Text style={styles.body}>
                Anonymous device-ID (random UUID, generated on your device only).
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                The letter content you upload, sent over TLS to our EU server, immediately
                forwarded to Mistral AI (Paris, EU) for analysis. The original image / PDF
                is <Text style={styles.bold}>not</Text> persisted.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                Structured analysis result (summary, deadlines, risk, reply draft), stored
                in our EU MongoDB tied to your anonymous device-ID only.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                Usage counter for the free quota. <Text style={styles.bold}>No</Text>
                {' '}name, address, location, advertising-ID or tracking cookies.
              </Text>
            </Bullet>
          </Section>

          <Section title="Legal basis">
            <Text style={styles.body}>
              Art. 6 (1) (b) GDPR, performance of the service you requested. Where we
              rely on legitimate interest (e.g. abuse prevention) it is Art. 6 (1) (f).
            </Text>
          </Section>

          <Section title="Processors">
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Mistral AI</Text> (Paris, France), language model.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>MongoDB</Text>. EU-hosted database.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>RevenueCat, Inc.</Text> (USA), only if you take
                a paid subscription. Standard Contractual Clauses. Disabled in soft-mode beta.
              </Text>
            </Bullet>
            <Bullet>
              <Text style={styles.body}>
                <Text style={styles.bold}>Apple / Google</Text>, store distribution and
                payment processing.
              </Text>
            </Bullet>
          </Section>

          <Section title="Retention">
            <Text style={styles.body}>
              Analysis results auto-delete after
              <Text style={styles.bold}> 90 days</Text>. You can also delete them yourself
              any time via Settings → Delete my data.
            </Text>
            <Text style={styles.body}>
              <Text style={styles.bold}>Statutory retention (billing data):</Text> German
              tax and commercial law (§ 147 AO, § 257 HGB) require invoices and
              payment records to be kept for up to
              <Text style={styles.bold}> 10 years</Text>. These records are stored by
              Apple, Google and RevenueCat under their own privacy policies. easli
              itself neither receives nor stores payment data.
            </Text>
          </Section>

          <Section title="No AI training">
            <Text style={styles.body}>
              Your letters, questions and reply drafts are
              <Text style={styles.bold}> not used to train </Text>
              AI models — neither by us nor by our processors. Mistral AI contractually
              guarantees that API requests are not used for model training or
              improvement (Mistral AI Data Processing Addendum). easli does not build
              user profiles and does not sell data to third parties.
            </Text>
          </Section>

          <Section title="Your rights">
            <Text style={styles.body}>
              Access, rectification, erasure, restriction, portability, objection, all
              available directly in the app (Settings → Export / Delete) or by email at
              kontakt@easli.app. You may also lodge a complaint with the
              competent data protection authority.
            </Text>
          </Section>

          <Section title="Supervisory authority">
            <Text style={styles.body}>
              <Text style={styles.bold}>
                Hessian Commissioner for Data Protection and Freedom of Information (HBDI)
              </Text>
              {'\n'}Gustav-Stresemann-Ring 1, 65189 Wiesbaden, Germany{'\n'}
              Phone: +49 611 1408-0{'\n'}
              Email: poststelle@datenschutz.hessen.de{'\n'}
              Web: www.datenschutz.hessen.de
            </Text>
          </Section>

          <Section title="Security">
            <Text style={styles.body}>
              All transfers are TLS-encrypted. API keys, letter content and IP addresses
              are not logged in clear text. Logs contain only anonymised metadata.
            </Text>
          </Section>
        </View>

        <Text style={styles.footnote}>
          The German version above is the legally binding version.
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

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.bullet}>
      <View style={styles.bulletDot} />
      <View style={{ flex: 1 }}>{children}</View>
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
  bold: {
    fontWeight: fontWeight.bold,
  },
  italic: {
    fontStyle: 'italic',
  },
  bullet: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingVertical: 2,
  },
  bulletDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
    marginTop: 10,
  },
  footnote: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.md,
    fontStyle: 'italic',
  },
});
