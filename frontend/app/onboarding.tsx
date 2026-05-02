// easli — redesigned onboarding flow.
//
// Two screens, guided by a top progress bar, designed to convince the user of
// the value within ~20 seconds:
//
//   1. Language picker (7 big flag tiles) with an automatic preselection from
//      `expo-localization` — and a prominent "Larger text" toggle for elderly
//      users who will read long legal letters in this app.
//   2. A live, animated demo: a small facsimile of a German letter fades out
//      while three explanatory pills (Frist / Betrag / Kategorie) pop in one
//      by one in the user's chosen language, capped by a single big CTA
//      ("Scan your first letter now").

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  Dimensions,
  Easing,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Localization from 'expo-localization';
import {
  ArrowRight,
  Check,
  ChevronLeft,
  CalendarClock,
  Euro,
  FileText,
  Type,
} from 'lucide-react-native';
import { Button } from '../src/ui';
import { setConsent, setLanguage, getLanguage, setOnboarded } from '../src/store';
import { useLargeFontMode } from '../src/largeFontMode';
import { colors, fontSize, fontWeight, gradient, radius, shadows, spacing } from '../src/theme';
import { EasliMark, EasliWordmark } from '../src/brand';
import { LanguageCode, LANGUAGES, t } from '../src/i18n';
import { LinearGradient } from 'expo-linear-gradient';

// Map iOS/Android BCP-47 locales to the languages easli ships. Fallback is
// English — never German simple (that's an opt-in accessibility flavour).
function detectInitialLang(): LanguageCode {
  try {
    const locales = Localization.getLocales?.() ?? [];
    for (const l of locales) {
      const tag = (l.languageTag || l.languageCode || '').toLowerCase();
      if (!tag) continue;
      if (tag.startsWith('zh')) return 'zh';
      if (tag.startsWith('vi')) return 'vi';
      if (tag.startsWith('tr')) return 'tr';
      if (tag.startsWith('ru')) return 'ru';
      if (tag.startsWith('es')) return 'es';
      if (tag.startsWith('en')) return 'en';
      if (tag.startsWith('de')) return 'de_simple';
    }
  } catch {
    // expo-localization is safe-by-default but never throw during onboarding
  }
  return 'en';
}

export default function Onboarding() {
  const router = useRouter();
  const [step, setStep] = useState<0 | 1>(0);
  const [lang, setLangState] = useState<LanguageCode>(() => detectInitialLang());
  const [largeFont, setLargeFont] = useLargeFontMode();

  // On first mount, prefer any previously-persisted language pick over the
  // auto-detected locale. Without this, toggling large-font mode (which
  // re-renders the screen) would *visually* feel correct, but the very next
  // mount cycle of this component (e.g. after a Stack remount earlier on)
  // would wipe the user's choice back to the system locale. Reading
  // AsyncStorage once on mount keeps the previous selection sticky.
  useEffect(() => {
    let cancelled = false;
    getLanguage()
      .then((persisted) => {
        if (!cancelled && persisted) setLangState(persisted);
      })
      .catch(() => {
        // ignore — fall back to the locale-detected initial value
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist whenever the user explicitly picks a language.
  const onPickLanguage = (code: LanguageCode) => {
    setLangState(code);
    setLanguage(code).catch(() => {
      // swallow — AsyncStorage failures shouldn't block the tour
    });
  };

  const finish = async () => {
    await setLanguage(lang);
    await setOnboarded();
    await setConsent();
    router.replace('/home');
  };

  return (
    <SafeAreaView style={styles.safe} testID="onboarding-screen">
      <View style={styles.topBar}>
        {step === 1 ? (
          <Pressable
            onPress={() => setStep(0)}
            style={styles.backBtn}
            hitSlop={12}
            testID="onboarding-back"
            accessibilityRole="button"
            accessibilityLabel={t(lang, 'back')}
          >
            <ChevronLeft color={colors.textSecondary} size={22} strokeWidth={2.4} />
          </Pressable>
        ) : (
          <View style={styles.brandRow}>
            <EasliMark size={28} tone="primary" />
            <EasliWordmark size={20} tone="primary" />
          </View>
        )}
        <View style={styles.progressRow}>
          <View style={[styles.progressDot, step >= 0 && styles.progressDotActive]} />
          <View style={[styles.progressDot, step >= 1 && styles.progressDotActive]} />
        </View>
      </View>

      {step === 0 ? (
        <LanguageStep
          lang={lang}
          onPick={onPickLanguage}
          largeFont={largeFont}
          onToggleLargeFont={setLargeFont}
          onContinue={() => setStep(1)}
        />
      ) : (
        <LiveDemoStep lang={lang} onGetStarted={finish} />
      )}
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Screen 1 — language grid + large-font toggle
// ---------------------------------------------------------------------------

interface LanguageStepProps {
  lang: LanguageCode;
  onPick: (c: LanguageCode) => void;
  largeFont: boolean;
  onToggleLargeFont: (v: boolean) => Promise<void> | void;
  onContinue: () => void;
}

function LanguageStep({ lang, onPick, largeFont, onToggleLargeFont, onContinue }: LanguageStepProps) {
  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        contentContainerStyle={styles.stepScroll}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.stepTitle}>{t(lang, 'onb_pick_lang_title')}</Text>
        <Text style={styles.stepSubtitle}>{t(lang, 'choose_language_subtitle')}</Text>

        <View style={styles.grid}>
          {LANGUAGES.map((l) => {
            const selected = l.code === lang;
            return (
              <Pressable
                key={l.code}
                onPress={() => onPick(l.code)}
                style={({ pressed }) => [
                  styles.langTile,
                  selected && styles.langTileSelected,
                  pressed && { opacity: 0.85 },
                ]}
                testID={`onb-lang-${l.code}`}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                accessibilityLabel={l.englishName}
              >
                <Text style={styles.langFlag}>{l.flag}</Text>
                <Text
                  style={[styles.langName, selected && styles.langNameSelected]}
                  numberOfLines={1}
                >
                  {l.nativeName}
                </Text>
                {selected ? (
                  <View style={styles.langCheck}>
                    <Check color={colors.white} size={12} strokeWidth={3} />
                  </View>
                ) : null}
              </Pressable>
            );
          })}
        </View>

        <Pressable
          style={styles.largeFontRow}
          onPress={() => onToggleLargeFont(!largeFont)}
          accessibilityRole="switch"
          accessibilityState={{ checked: largeFont }}
          testID="onb-large-font-toggle"
        >
          <View style={styles.largeFontIconWrap}>
            <Type color={colors.primary} size={20} strokeWidth={2.4} />
          </View>
          <Text style={styles.largeFontLabel}>{t(lang, 'onb_large_font')}</Text>
          <View style={[styles.switchTrack, largeFont && styles.switchTrackOn]}>
            <View style={[styles.switchThumb, largeFont && styles.switchThumbOn]} />
          </View>
        </Pressable>
      </ScrollView>

      <View style={styles.footer}>
        <Button
          label={t(lang, 'next')}
          onPress={onContinue}
          icon={<ArrowRight color={colors.white} size={20} strokeWidth={2.5} />}
          testID="onboarding-cta"
        />
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Screen 2 — live demo with animated transformation
// ---------------------------------------------------------------------------

// Demo content per language. Keeping this locally-defined rather than pushing
// into i18n.ts on purpose: these strings are only ever shown in the onboarding
// demo and are short enough to maintain in place.
const DEMO: Record<LanguageCode, { summary: string; deadline: string; amount: string; category: string; cta: string }> = {
  de_simple: {
    summary: 'Rundfunkbeitrag: 55,08 € offen — bitte bis zum Stichtag zahlen.',
    deadline: 'Frist: 30.11.2026',
    amount: 'Betrag: 55,08 €',
    category: 'Behörde',
    cta: 'Jetzt dein erstes Schreiben scannen',
  },
  en: {
    summary: 'German TV licence fee: €55.08 due — please pay before the deadline.',
    deadline: 'Due: 30 Nov 2026',
    amount: 'Amount: €55.08',
    category: 'Authority',
    cta: 'Scan your first letter now',
  },
  es: {
    summary: 'Canon audiovisual: 55,08 € pendientes — paga antes de la fecha límite.',
    deadline: 'Vence: 30 nov 2026',
    amount: 'Importe: 55,08 €',
    category: 'Administración',
    cta: 'Escanea ahora tu primera carta',
  },
  vi: {
    summary: 'Phí truyền thông Đức: còn 55,08 € — hãy thanh toán trước hạn.',
    deadline: 'Hạn: 30.11.2026',
    amount: 'Số tiền: 55,08 €',
    category: 'Cơ quan nhà nước',
    cta: 'Quét bức thư đầu tiên ngay',
  },
  tr: {
    summary: 'Almanya yayın katkı payı: 55,08 € bakiye — lütfen son tarihe kadar ödeyin.',
    deadline: 'Son tarih: 30.11.2026',
    amount: 'Tutar: 55,08 €',
    category: 'Resmi kurum',
    cta: 'İlk mektubunu şimdi tara',
  },
  ru: {
    summary: 'Взнос на немецкое вещание: 55,08 € к оплате — до указанной даты.',
    deadline: 'Срок: 30.11.2026',
    amount: 'Сумма: 55,08 €',
    category: 'Гос. учреждение',
    cta: 'Отсканируй своё первое письмо',
  },
  zh: {
    summary: '德国广电费：应付 55.08 欧元 — 请在截止日期前支付。',
    deadline: '截止：2026-11-30',
    amount: '金额：55,08 €',
    category: '政府机构',
    cta: '立即扫描第一封信',
  },
};

function LiveDemoStep({ lang, onGetStarted }: { lang: LanguageCode; onGetStarted: () => void }) {
  const demo = DEMO[lang] || DEMO.en;

  // Animated values: letter fades down, three pills rise and fade in, then
  // the summary card fades in. Reanimated would be cleaner but the stock
  // RN Animated API is already imported elsewhere and covers this case
  // without a worklet dependency.
  const letterOpacity = useRef(new Animated.Value(1)).current;
  const letterTranslate = useRef(new Animated.Value(0)).current;
  const pill1 = useRef(new Animated.Value(0)).current;
  const pill2 = useRef(new Animated.Value(0)).current;
  const pill3 = useRef(new Animated.Value(0)).current;
  const summaryOpacity = useRef(new Animated.Value(0)).current;

  const runAnimation = useMemo(
    () => () => {
      letterOpacity.setValue(1);
      letterTranslate.setValue(0);
      pill1.setValue(0);
      pill2.setValue(0);
      pill3.setValue(0);
      summaryOpacity.setValue(0);
      Animated.sequence([
        Animated.delay(250),
        Animated.parallel([
          Animated.timing(letterOpacity, {
            toValue: 0.15,
            duration: 600,
            easing: Easing.out(Easing.quad),
            useNativeDriver: true,
          }),
          Animated.timing(letterTranslate, {
            toValue: -20,
            duration: 600,
            easing: Easing.out(Easing.quad),
            useNativeDriver: true,
          }),
        ]),
        Animated.stagger(180, [
          Animated.timing(pill1, {
            toValue: 1,
            duration: 380,
            easing: Easing.out(Easing.back(1.4)),
            useNativeDriver: true,
          }),
          Animated.timing(pill2, {
            toValue: 1,
            duration: 380,
            easing: Easing.out(Easing.back(1.4)),
            useNativeDriver: true,
          }),
          Animated.timing(pill3, {
            toValue: 1,
            duration: 380,
            easing: Easing.out(Easing.back(1.4)),
            useNativeDriver: true,
          }),
        ]),
        Animated.timing(summaryOpacity, {
          toValue: 1,
          duration: 400,
          useNativeDriver: true,
        }),
      ]).start();
    },
    [letterOpacity, letterTranslate, pill1, pill2, pill3, summaryOpacity],
  );

  useEffect(() => {
    runAnimation();
  }, [runAnimation, lang]);

  const pillStyle = (v: Animated.Value) => ({
    opacity: v,
    transform: [
      {
        translateY: v.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }),
      },
      {
        scale: v.interpolate({ inputRange: [0, 1], outputRange: [0.92, 1] }),
      },
    ],
  });

  const stageWidth = Math.min(Dimensions.get('window').width - spacing.lg * 2, 420);

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        contentContainerStyle={styles.demoScroll}
        showsVerticalScrollIndicator={false}
      >
        {/* Phase R3 — Brand-gradient hero (Brand-Guide approved for
            onboarding/marketing surfaces only). Sets a calm authority tone
            on first launch and previews the icon's gradient identity. */}
        <LinearGradient
          colors={gradient.brand.colors}
          start={gradient.brand.start}
          end={gradient.brand.end}
          style={styles.heroGradient}
        >
          <View style={styles.heroIconWrap}>
            <EasliMark size={48} />
          </View>
          <Text style={styles.heroTitle}>{t(lang, 'app_tagline')}</Text>
          <Text style={styles.heroSubtitle}>{t(lang, 'onb_demo_subtitle')}</Text>
        </LinearGradient>

        <View style={[styles.stage, { width: stageWidth }]}>
          {/* Original German letter (fades out) */}
          <Animated.View
            style={[
              styles.letter,
              {
                opacity: letterOpacity,
                transform: [{ translateY: letterTranslate }],
              },
            ]}
            pointerEvents="none"
          >
            <View style={styles.letterHeader}>
              <View style={styles.letterLogoDot} />
              <View style={styles.letterLogoLines}>
                <View style={[styles.letterLine, { width: 90 }]} />
                <View style={[styles.letterLine, { width: 64, opacity: 0.4 }]} />
              </View>
            </View>
            <View style={{ height: spacing.md }} />
            <Text style={styles.letterFromLabel}>Beitragsservice ARD ZDF</Text>
            <Text style={styles.letterTo}>Festsetzungsbescheid</Text>
            <View style={{ height: spacing.sm }} />
            <Text style={styles.letterParagraph}>
              Sehr geehrte Damen und Herren,{'\n'}
              für Ihre Wohnung sind folgende Rundfunkbeiträge rückständig:{'\n'}
              <Text style={{ fontWeight: fontWeight.bold }}>55,08 €</Text>.
            </Text>
            <Text style={styles.letterParagraph}>
              Fälligkeitstag: <Text style={{ fontWeight: fontWeight.bold }}>30.11.2026</Text>
            </Text>
            <Text style={styles.letterStamp}>Amtliches Schreiben</Text>
          </Animated.View>

          {/* Summary card (fades in) */}
          <Animated.View
            pointerEvents="none"
            style={[
              styles.summaryCard,
              {
                opacity: summaryOpacity,
                transform: [
                  {
                    translateY: summaryOpacity.interpolate({
                      inputRange: [0, 1],
                      outputRange: [12, 0],
                    }),
                  },
                ],
              },
            ]}
          >
            <Text style={styles.summaryHeadline} numberOfLines={3}>
              {demo.summary}
            </Text>
          </Animated.View>

          {/* Floating pills */}
          <Animated.View style={[styles.pill, styles.pillRed, styles.pillTopRight, pillStyle(pill1)]}>
            <CalendarClock color={colors.red.text} size={14} strokeWidth={2.4} />
            <Text style={[styles.pillText, { color: colors.red.text }]}>{demo.deadline}</Text>
          </Animated.View>
          <Animated.View style={[styles.pill, styles.pillYellow, styles.pillMidLeft, pillStyle(pill2)]}>
            <Euro color={colors.yellow.text} size={14} strokeWidth={2.4} />
            <Text style={[styles.pillText, { color: colors.yellow.text }]}>{demo.amount}</Text>
          </Animated.View>
          <Animated.View style={[styles.pill, styles.pillBlue, styles.pillBotRight, pillStyle(pill3)]}>
            <FileText color={colors.primary} size={14} strokeWidth={2.4} />
            <Text style={[styles.pillText, { color: colors.primary }]}>{demo.category}</Text>
          </Animated.View>
        </View>

        <Pressable
          onPress={runAnimation}
          style={styles.replay}
          testID="onb-replay"
          accessibilityRole="button"
          accessibilityLabel="Replay demo"
        >
          <Text style={styles.replayText}>↻</Text>
        </Pressable>

        <Text style={styles.privacyFootnote}>{t(lang, 'privacy_short')}</Text>
      </ScrollView>

      <View style={styles.footer}>
        <Button
          label={demo.cta}
          onPress={onGetStarted}
          icon={<ArrowRight color={colors.white} size={20} strokeWidth={2.5} />}
          testID="onboarding-finish"
        />
        <Text style={styles.legalFootnote}>{t(lang, 'disclaimer_short')}</Text>
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  topBar: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 48,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  brandLogo: { width: 32, height: 32, borderRadius: radius.md },
  brand: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.4,
    color: colors.primary,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  progressRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  progressDot: {
    width: 24,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.border,
  },
  progressDotActive: { backgroundColor: colors.primary, width: 28 },

  stepScroll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
  },
  // LiveDemo step uses its own scroll style — hero is full-bleed (no
  // horizontal padding) so the gradient reaches edge-to-edge, then
  // content below sits in its usual lg padding via the stage's own
  // marginHorizontal: 'auto'.
  demoScroll: {
    paddingTop: 0,
    paddingBottom: spacing.lg,
    alignItems: 'center',
  },
  // Brand-gradient hero — used ONLY on onboarding (Brand Guide §6 forbids
  // gradient in core UI). Soft rounded bottom corners give it a "card"
  // feel without dominating the page.
  heroGradient: {
    width: '100%',
    paddingTop: spacing.xl,
    paddingBottom: spacing.xl,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    borderBottomLeftRadius: radius.xxl,
    borderBottomRightRadius: radius.xxl,
    marginBottom: spacing.lg,
  },
  heroIconWrap: {
    backgroundColor: 'rgba(255,255,255,0.18)',
    padding: 6,
    borderRadius: 16,
    marginBottom: spacing.md,
  },
  heroTitle: {
    fontSize: fontSize['3xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.white,
    letterSpacing: -0.5,
    textAlign: 'center',
    lineHeight: fontSize['3xl'] * 1.15,
    marginBottom: spacing.xs,
  },
  heroSubtitle: {
    fontSize: fontSize.base,
    color: 'rgba(255,255,255,0.92)',
    textAlign: 'center',
    lineHeight: 22,
    maxWidth: 320,
  },
  stepTitle: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.5,
    marginBottom: spacing.xs,
  },
  stepSubtitle: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
    lineHeight: 22,
  },

  // Language grid ---------------------------------------------------------
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    rowGap: spacing.sm,
  },
  langTile: {
    width: '48%',
    aspectRatio: 2.4,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 2,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    overflow: 'hidden',
  },
  langTileSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  langFlag: { fontSize: 26 },
  langName: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
    flexShrink: 1,
  },
  langNameSelected: { color: colors.primaryDark },
  langCheck: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Large-font toggle -----------------------------------------------------
  largeFontRow: {
    marginTop: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    gap: spacing.md,
  },
  largeFontIconWrap: {
    width: 36,
    height: 36,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  largeFontLabel: {
    flex: 1,
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  switchTrack: {
    width: 48,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.border,
    padding: 3,
    justifyContent: 'center',
  },
  switchTrackOn: { backgroundColor: colors.primary },
  switchThumb: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.white,
    ...shadows.card,
  },
  switchThumbOn: { transform: [{ translateX: 20 }] },

  // Stage / live demo -----------------------------------------------------
  stage: {
    alignSelf: 'center',
    height: 340,
    backgroundColor: colors.primarySoft,
    borderRadius: radius.xl,
    padding: spacing.md,
    overflow: 'hidden',
    marginBottom: spacing.md,
  },
  letter: {
    position: 'absolute',
    top: spacing.md,
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    ...shadows.card,
  },
  letterHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  letterLogoDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.textMuted,
  },
  letterLogoLines: { gap: 4 },
  letterLine: { height: 6, borderRadius: 3, backgroundColor: colors.borderLight },
  letterFromLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  letterTo: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    marginTop: 2,
  },
  letterParagraph: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
    marginTop: 4,
  },
  letterStamp: {
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
    fontSize: fontSize.xs,
    color: colors.textMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  summaryCard: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadows.card,
  },
  summaryHeadline: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
    lineHeight: 22,
  },

  // Pills -----------------------------------------------------------------
  pill: {
    position: 'absolute',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.full,
    borderWidth: 1,
    ...shadows.card,
  },
  pillText: { fontSize: fontSize.xs, fontWeight: fontWeight.bold },
  pillRed: { backgroundColor: colors.red.bg, borderColor: colors.red.border },
  pillYellow: { backgroundColor: colors.yellow.bg, borderColor: colors.yellow.border },
  pillBlue: { backgroundColor: colors.primarySoft, borderColor: colors.primary + '33' },
  pillTopRight: { top: spacing.md + 6, right: spacing.md + 6 },
  pillMidLeft: { top: 140, left: spacing.md + 2 },
  pillBotRight: { top: 180, right: spacing.md + 6 },

  replay: {
    alignSelf: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.border,
    minWidth: 56,
    alignItems: 'center',
  },
  replayText: {
    fontSize: fontSize.lg,
    color: colors.primary,
    fontWeight: fontWeight.bold,
    lineHeight: 22,
  },
  privacyFootnote: {
    textAlign: 'center',
    color: colors.textMuted,
    fontSize: fontSize.sm,
    paddingHorizontal: spacing.md,
    marginTop: spacing.xs,
  },

  // Footer ----------------------------------------------------------------
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
    gap: spacing.sm,
  },
  legalFootnote: {
    textAlign: 'center',
    color: colors.textMuted,
    fontSize: fontSize.sm,
    paddingHorizontal: spacing.md,
  },
});
