// Onboarding flow — 3 swipeable steps with calm illustrations and a single big CTA.

import { useState } from 'react';
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
import { setOnboarded } from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';
import { t } from '../src/i18n';

const SLIDES = [
  {
    key: 'translate',
    image: 'https://static.prod-images.emergentagent.com/jobs/1f0c6f21-2efe-4a5b-950e-770baf187f4d/images/f3c1092a5553559a52b9fee5cc730259954d0c214aa2c13e238cb266c39fa787.png',
    icon: Languages,
    titleKey: 'onb1_title' as const,
    bodyKey: 'onb1_body' as const,
  },
  {
    key: 'scan',
    image: 'https://static.prod-images.emergentagent.com/jobs/1f0c6f21-2efe-4a5b-950e-770baf187f4d/images/0b5b9d6fb4e6a1a07ee423bf490d131ccfc6cfc7932ed41c51e126f29e0135cb.png',
    icon: ScanLine,
    titleKey: 'onb2_title' as const,
    bodyKey: 'onb2_body' as const,
  },
  {
    key: 'privacy',
    image: 'https://static.prod-images.emergentagent.com/jobs/1f0c6f21-2efe-4a5b-950e-770baf187f4d/images/dfb7c0cde2961f6522cce0622e0475893ae84c46d863f8c6ae0ec4c4ad6b1fdc.png',
    icon: ShieldCheck,
    titleKey: 'onb3_title' as const,
    bodyKey: 'onb3_body' as const,
  },
];

export default function Onboarding() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [page, setPage] = useState(0);
  const lang = 'en'; // Pre-language default; locale picker is the next screen.

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const idx = Math.round(e.nativeEvent.contentOffset.x / width);
    if (idx !== page) setPage(idx);
  };

  const finish = async () => {
    await setOnboarded();
    router.replace('/language?from=onboarding');
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
                  source={{ uri: s.image }}
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
