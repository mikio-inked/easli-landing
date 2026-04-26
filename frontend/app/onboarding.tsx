// Onboarding flow — 3 swipeable steps with calm illustrations and a single big CTA.

import { useEffect, useState } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  NativeSyntheticEvent,
  NativeScrollEvent,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowRight, ShieldCheck, ScanLine, Languages } from 'lucide-react-native';
import { Button } from '../src/ui';
import { getLanguage, setConsent, setOnboarded } from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';
import { LanguageCode, t } from '../src/i18n';

const SLIDES = [
  {
    key: 'translate',
    image: require('../assets/images/onb1_translate.png'),
    icon: Languages,
    titleKey: 'onb1_title' as const,
    bodyKey: 'onb1_body' as const,
  },
  {
    key: 'scan',
    image: require('../assets/images/onb2_deadlines.png'),
    icon: ScanLine,
    titleKey: 'onb2_title' as const,
    bodyKey: 'onb2_body' as const,
  },
  {
    key: 'privacy',
    image: require('../assets/images/onb3_privacy.png'),
    icon: ShieldCheck,
    titleKey: 'onb3_title' as const,
    bodyKey: 'onb3_body' as const,
  },
];

export default function Onboarding() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [page, setPage] = useState(0);
  const [lang, setLang] = useState<LanguageCode>('en');

  useEffect(() => {
    getLanguage().then((l) => {
      if (l) setLang(l);
    });
  }, []);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const idx = Math.round(e.nativeEvent.contentOffset.x / width);
    if (idx !== page) setPage(idx);
  };

  const finish = async () => {
    // Tapping the final CTA on the privacy slide is treated as the user's
    // active opt-in: they have read what KlarPost does with their data and
    // explicitly chose to continue. Recorded as a timestamped consent
    // record so we can reflect it later (e.g. on the Privacy screen).
    await setOnboarded();
    await setConsent();
    router.replace('/home');
  };

  const isLast = page === SLIDES.length - 1;

  return (
    <SafeAreaView style={styles.safe} testID="onboarding-screen">
      <View style={styles.topBar}>
        <View style={styles.brandRow}>
          <Image
            source={require('../assets/images/icon.png')}
            style={styles.brandLogo}
            resizeMode="cover"
            accessibilityLabel="KlarPost"
          />
          <Text style={styles.brand}>KlarPost</Text>
        </View>
        <Pressable onPress={finish} testID="onboarding-skip">
          <Text style={styles.skip}>{t(lang, 'skip')}</Text>
        </Pressable>
      </View>
      <ScrollView
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        style={{ flex: 1 }}
      >
        {SLIDES.map((s) => {
          const Icon = s.icon;
          return (
            <View key={s.key} style={[styles.slide, { width }]}>
              <View style={styles.illustrationWrap}>
                <Image
                  source={s.image}
                  style={styles.illustration}
                  resizeMode="contain"
                />
              </View>
              <View style={styles.iconChip}>
                <Icon color={colors.primary} size={22} strokeWidth={2.4} />
              </View>
              <Text style={styles.title}>{t(lang, s.titleKey)}</Text>
              <Text style={styles.body}>{t(lang, s.bodyKey)}</Text>
            </View>
          );
        })}
      </ScrollView>
      <View style={styles.dots}>
        {SLIDES.map((s, i) => (
          <View
            key={s.key}
            style={[styles.dot, i === page && styles.dotActive]}
          />
        ))}
      </View>
      <View style={styles.footer}>
        <Button
          label={isLast ? t(lang, 'onb_get_started') : t(lang, 'next')}
          onPress={() => {
            if (isLast) finish();
            else setPage((p) => Math.min(p + 1, SLIDES.length - 1));
          }}
          icon={<ArrowRight color={colors.white} size={20} strokeWidth={2.5} />}
          testID="onboarding-cta"
        />
        <Text style={styles.footnote}>{t(lang, 'disclaimer_short')}</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  topBar: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  brandLogo: {
    width: 36,
    height: 36,
    borderRadius: radius.md,
  },
  brand: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.5,
    color: colors.primary,
  },
  skip: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    fontWeight: fontWeight.semibold,
    padding: spacing.sm,
  },
  slide: {
    paddingHorizontal: spacing.lg,
    alignItems: 'flex-start',
    justifyContent: 'flex-start',
    paddingTop: spacing.md,
  },
  illustrationWrap: {
    width: '100%',
    height: 280,
    borderRadius: radius.xxl,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    marginBottom: spacing.lg,
  },
  illustration: {
    width: '100%',
    height: '100%',
  },
  iconChip: {
    width: 44,
    height: 44,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  title: {
    fontSize: fontSize['3xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.6,
    marginBottom: spacing.sm,
  },
  body: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
    lineHeight: 26,
  },
  dots: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: spacing.md,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.border,
  },
  dotActive: {
    backgroundColor: colors.primary,
    width: 22,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.sm,
  },
  footnote: {
    textAlign: 'center',
    color: colors.textMuted,
    fontSize: fontSize.sm,
    paddingHorizontal: spacing.md,
  },
});
