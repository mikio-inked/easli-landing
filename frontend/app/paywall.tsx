// Paywall screen.
//
// Shows three purchase options + (in soft mode, before the test cap) a
// "Continue free" bypass. Designed to render gracefully when RevenueCat
// keys are missing — purchase buttons stay tappable and show a friendly
// "Zahlungen sind in dieser Testversion noch nicht verfügbar." instead of
// crashing.
//
// Always rendered in German per product decision (App-Store-relevant copy).

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  AlertOctagon,
  ArrowLeft,
  Check,
  CreditCard,
  Crown,
  RotateCw,
  Sparkles,
  X,
} from 'lucide-react-native';
import {
  PaymentsUnavailableError,
  PurchaseCancelledError,
  PRODUCT_IDS,
  findPackageForProductId,
  getCurrentOffering,
  isBillingAvailable,
  purchasePackage,
  restorePurchases,
} from '../src/billing';
import { ensureDeviceId, getLanguage as getStoredLanguage } from '../src/store';
import { LanguageCode, t } from '../src/i18n';
import { useUsage, usePaywallConfig, getRemainingAnalyses } from '../src/usage';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from '../src/theme';

interface OptionDef {
  productId: string;
  titleKey: 'paywall_option_single_title' | 'paywall_option_monthly_title' | 'paywall_option_yearly_title';
  priceKey: 'paywall_option_single_price' | 'paywall_option_monthly_price' | 'paywall_option_yearly_price';
  descKey: 'paywall_option_single_desc' | 'paywall_option_monthly_desc' | 'paywall_option_yearly_desc';
  highlight?: boolean;
}

const OPTIONS: OptionDef[] = [
  {
    productId: PRODUCT_IDS.singleLetter,
    titleKey: 'paywall_option_single_title',
    priceKey: 'paywall_option_single_price',
    descKey: 'paywall_option_single_desc',
  },
  {
    productId: PRODUCT_IDS.plusMonthly,
    titleKey: 'paywall_option_monthly_title',
    priceKey: 'paywall_option_monthly_price',
    descKey: 'paywall_option_monthly_desc',
    highlight: true,
  },
  {
    productId: PRODUCT_IDS.plusYearly,
    titleKey: 'paywall_option_yearly_title',
    priceKey: 'paywall_option_yearly_price',
    descKey: 'paywall_option_yearly_desc',
  },
];

export default function Paywall() {
  const router = useRouter();
  const params = useLocalSearchParams<{ reason?: string; next?: string }>();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [offering, setOffering] = useState<any | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // productId currently processing
  const [restoring, setRestoring] = useState(false);

  const { config } = usePaywallConfig();
  const { usage, refresh: refreshUsage } = useUsage(deviceId);

  useFocusEffect(
    useCallback(() => {
      (async () => {
        setLang((await getStoredLanguage()) ?? 'en');
        const id = await ensureDeviceId();
        setDeviceId(id);
      })();
    }, [])
  );

  // Best-effort offering fetch — silently no-ops when billing isn't configured.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const o = await getCurrentOffering();
      if (!cancelled) setOffering(o);
    })();
    return () => { cancelled = true; };
  }, []);

  const isSoft = (config?.paywall_mode || 'soft') === 'soft';
  const reason = params.reason as string | undefined;
  const remaining = useMemo(() => getRemainingAnalyses(usage), [usage]);
  // Soft-mode bypass is only offered when the user is BELOW the soft cap
  // AND the backend hasn't already 429'd them on this entry.
  const canContinueFree =
    isSoft && reason !== 'test_limit_reached' && (remaining.soft > 0 || remaining.free > 0);
  const testLimitReached = reason === 'test_limit_reached';

  const handlePurchase = useCallback(
    async (productId: string) => {
      if (busy) return;
      setBusy(productId);
      try {
        // Soft fallback: when RevenueCat is not initialised (no keys, web
        // platform, APK without billing) we surface a friendly alert
        // instead of letting the SDK throw an opaque error.
        if (!isBillingAvailable()) {
          // On Android specifically, show the more pointed APK message.
          const message =
            Platform.OS === 'android'
              ? t(lang, 'paywall_payments_unavailable_apk')
              : t(lang, 'paywall_payments_unavailable');
          Alert.alert('KlarPost', message);
          return;
        }
        const pkg = findPackageForProductId(offering, productId);
        if (!pkg) {
          Alert.alert('KlarPost', t(lang, 'paywall_payments_unavailable'));
          return;
        }
        await purchasePackage(pkg);
        Alert.alert('KlarPost', t(lang, 'paywall_purchase_success'));
        // Webhook will update server-side usage; we still refresh in case
        // the device is online and the webhook lands quickly.
        await refreshUsage();
        // Privacy-safe: only the product id is logged on the client; never
        // the customer info object or transaction id.
        // eslint-disable-next-line no-console
        console.info('[paywall] purchase_success product=' + productId);
        router.back();
      } catch (e: any) {
        if (e instanceof PurchaseCancelledError) {
          Alert.alert('KlarPost', t(lang, 'paywall_purchase_cancelled'));
          return;
        }
        if (e instanceof PaymentsUnavailableError) {
          Alert.alert('KlarPost', t(lang, 'paywall_payments_unavailable'));
          return;
        }
        Alert.alert('KlarPost', t(lang, 'paywall_purchase_failed'));
      } finally {
        setBusy(null);
      }
    },
    [busy, offering, lang, refreshUsage, router]
  );

  const handleRestore = useCallback(async () => {
    if (restoring) return;
    setRestoring(true);
    try {
      if (!isBillingAvailable()) {
        Alert.alert(
          'KlarPost',
          Platform.OS === 'android'
            ? t(lang, 'paywall_payments_unavailable_apk')
            : t(lang, 'paywall_payments_unavailable')
        );
        return;
      }
      await restorePurchases();
      await refreshUsage();
      Alert.alert('KlarPost', t(lang, 'paywall_restored'));
    } catch (e: any) {
      if (e instanceof PaymentsUnavailableError) {
        Alert.alert('KlarPost', t(lang, 'paywall_payments_unavailable'));
        return;
      }
      Alert.alert('KlarPost', t(lang, 'paywall_purchase_failed'));
    } finally {
      setRestoring(false);
    }
  }, [restoring, lang, refreshUsage]);

  const handleContinueFree = useCallback(() => {
    if (!canContinueFree) return;
    // Pop back to whatever launched the paywall. The user can retry the
    // scan/upload on Home — backend allows up to soft_extra_total before
    // it returns 429 again.
    if (router.canGoBack()) router.back();
    else router.replace('/home');
  }, [canContinueFree, router]);

  return (
    <SafeAreaView style={styles.safe} testID="paywall-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="paywall-close">
          <X color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>KlarPost</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.heroIcon}>
          <Sparkles color={colors.primary} size={28} strokeWidth={2.4} />
        </View>
        <Text style={styles.title}>{t(lang, 'paywall_title')}</Text>
        <Text style={styles.subtitle}>{t(lang, 'paywall_subtitle')}</Text>

        {testLimitReached && (
          <View style={styles.testLimitCard} testID="paywall-test-limit">
            <View style={styles.testLimitIconWrap}>
              <AlertOctagon color={colors.red.text} size={22} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.testLimitTitle}>{t(lang, 'paywall_test_limit_title')}</Text>
              <Text style={styles.testLimitBody}>{t(lang, 'paywall_test_limit_body')}</Text>
            </View>
          </View>
        )}

        {OPTIONS.map((opt) => {
          const isLoading = busy === opt.productId;
          return (
            <Pressable
              key={opt.productId}
              onPress={() => handlePurchase(opt.productId)}
              disabled={!!busy}
              style={({ pressed }) => [
                styles.option,
                opt.highlight && styles.optionHighlight,
                pressed && { opacity: 0.92 },
              ]}
              testID={`paywall-option-${opt.productId}`}
            >
              <View
                style={[
                  styles.optionIconWrap,
                  opt.highlight && { backgroundColor: colors.primary },
                ]}
              >
                {opt.highlight ? (
                  <Crown color={colors.white} size={22} strokeWidth={2.4} />
                ) : (
                  <CreditCard color={colors.primary} size={22} strokeWidth={2.4} />
                )}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.optionTitle}>{t(lang, opt.titleKey)}</Text>
                <Text style={styles.optionPrice}>{t(lang, opt.priceKey)}</Text>
                <Text style={styles.optionDesc}>{t(lang, opt.descKey)}</Text>
              </View>
              {isLoading && (
                <ActivityIndicator size="small" color={colors.primary} />
              )}
            </Pressable>
          );
        })}

        {canContinueFree && (
          <Pressable
            onPress={handleContinueFree}
            style={({ pressed }) => [
              styles.continueFree,
              pressed && { opacity: 0.85 },
            ]}
            testID="paywall-continue-free"
          >
            <Check color={colors.green.text} size={20} strokeWidth={2.6} />
            <Text style={styles.continueFreeText}>
              {t(lang, 'paywall_continue_free_test')}
            </Text>
          </Pressable>
        )}

        {isSoft && (
          <Text style={styles.testNote}>{t(lang, 'paywall_test_note')}</Text>
        )}

        <Pressable
          onPress={handleRestore}
          disabled={restoring}
          style={({ pressed }) => [styles.restoreBtn, pressed && { opacity: 0.7 }]}
          testID="paywall-restore"
        >
          {restoring ? (
            <ActivityIndicator size="small" color={colors.primary} />
          ) : (
            <RotateCw color={colors.primary} size={16} strokeWidth={2.4} />
          )}
          <Text style={styles.restoreText}>{t(lang, 'paywall_restore')}</Text>
        </Pressable>

        <View style={styles.legalBlock}>
          <Text style={styles.legalText}>{t(lang, 'paywall_legal_note')}</Text>
          <Text style={styles.legalText}>{t(lang, 'paywall_privacy_note')}</Text>
        </View>
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
    paddingBottom: spacing.xl,
  },
  heroIcon: {
    alignSelf: 'center',
    width: 64,
    height: 64,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.sm,
  },
  title: {
    textAlign: 'center',
    fontSize: 26,
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  subtitle: {
    textAlign: 'center',
    fontSize: fontSize.base,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: spacing.sm,
  },
  testLimitCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.red.bg,
    borderWidth: 1,
    borderColor: colors.red.border,
  },
  testLimitIconWrap: {
    width: 38,
    height: 38,
    borderRadius: radius.full,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  testLimitTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.red.text,
  },
  testLimitBody: {
    marginTop: 2,
    fontSize: fontSize.sm,
    color: colors.red.text,
    lineHeight: 19,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadows.card,
  },
  optionHighlight: {
    borderColor: colors.primary,
    borderWidth: 2,
  },
  optionIconWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  optionPrice: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    color: colors.primary,
    marginTop: 2,
  },
  optionDesc: {
    marginTop: 4,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  continueFree: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.green.bg,
    borderWidth: 1,
    borderColor: colors.green.border,
    marginTop: spacing.sm,
  },
  continueFreeText: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.green.text,
  },
  testNote: {
    marginTop: spacing.sm,
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 17,
    fontStyle: 'italic',
  },
  restoreBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: spacing.md,
    marginTop: spacing.sm,
  },
  restoreText: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
  },
  legalBlock: {
    marginTop: spacing.md,
    gap: 6,
  },
  legalText: {
    textAlign: 'center',
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 17,
  },
});
