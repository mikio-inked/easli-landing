// Settings screen — change language, delete data, view privacy / disclaimer.

import { useCallback, useState } from 'react';
import {
  Alert,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft,
  BarChart3,
  ChevronRight,
  Crown,
  DownloadCloud,
  FlaskConical,
  Globe2,
  HardDrive,
  HelpCircle,
  Languages as LanguagesIcon,
  Lock,
  RotateCw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from 'lucide-react-native';
import { Card } from '../src/ui';
import { deleteAllAnalyses, exportMyData } from '../src/api';
import {
  ensureDeviceId,
  getLanguage as getStoredLanguage,
  resetAll,
  setLastResult,
} from '../src/store';
import { LanguageCode, getLanguage as getLanguageMeta, t } from '../src/i18n';
import { cancelAllReminders } from '../src/notifications';
import { deleteAllOriginals } from '../src/originals';
import { getSaveOriginals, setSaveOriginals } from '../src/settings';
import { useUsage, getRemainingAnalyses } from '../src/usage';
import {
  isBillingAvailable,
  PaymentsUnavailableError,
  restorePurchases,
} from '../src/billing';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const __APP_DEV__ =
  // Expo / Metro injects __DEV__ at bundle time; fall back to NODE_ENV.
  (typeof __DEV__ !== 'undefined' && (__DEV__ as boolean)) ||
  process.env.NODE_ENV === 'development';

export default function SettingsScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [saveOriginals, setSaveOriginalsState] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [restoring, setRestoring] = useState(false);

  const { usage, refresh: refreshUsage } = useUsage(deviceId);
  const remaining = getRemainingAnalyses(usage);

  useFocusEffect(
    useCallback(() => {
      (async () => {
        setLang((await getStoredLanguage()) ?? 'en');
        setDeviceId(await ensureDeviceId());
      })();
      getSaveOriginals().then(setSaveOriginalsState);
    }, [])
  );

  const onRestore = async () => {
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
  };

  const onManagePlus = () => {
    // Take the user to the official Apple/Google subscription management
    // surface. RevenueCat does not own this UX. On unsupported platforms we
    // simply show the test-mode message.
    if (Platform.OS === 'ios') {
      Linking.openURL('https://apps.apple.com/account/subscriptions').catch(() => {});
    } else if (Platform.OS === 'android') {
      Linking.openURL('https://play.google.com/store/account/subscriptions').catch(() => {});
    } else {
      Alert.alert('KlarPost', t(lang, 'paywall_payments_unavailable'));
    }
  };

  const callDevTool = async (path: string, query: string) => {
    if (!__APP_DEV__) return;
    if (!deviceId) return;
    try {
      const res = await fetch(
        `${BACKEND}/api/dev/usage/${path}?device_id=${encodeURIComponent(deviceId)}${query ? '&' + query : ''}`,
        { method: 'POST' }
      );
      if (!res.ok) {
        Alert.alert('Dev tools', `HTTP ${res.status}`);
        return;
      }
      await refreshUsage();
    } catch (e: any) {
      Alert.alert('Dev tools', e?.message || 'Failed');
    }
  };

  const onToggleSaveOriginals = async (value: boolean) => {
    setSaveOriginalsState(value);
    await setSaveOriginals(value);
    if (!value) {
      // Turning OFF the toggle clears any locally saved originals.
      await deleteAllOriginals();
    }
  };

  const onExport = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const id = await ensureDeviceId();
      const payload = await exportMyData(id);
      const json = JSON.stringify(payload, null, 2);
      await Share.share(
        {
          message: json,
          title: 'KlarPost data export',
        },
        { dialogTitle: 'KlarPost data export' }
      );
    } catch (e: any) {
      Alert.alert(t(lang, 'export_failed'), e?.message || '');
    } finally {
      setExporting(false);
    }
  };

  const onDeleteAll = () => {
    Alert.alert(t(lang, 'confirm_delete_all'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          const id = await ensureDeviceId();
          try {
            await deleteAllAnalyses(id);
            await cancelAllReminders();
            await deleteAllOriginals();
            setLastResult(null);
            Alert.alert(t(lang, 'done'));
          } catch (e: any) {
            Alert.alert(t(lang, 'error_generic'), e?.message || '');
          }
        },
      },
    ]);
  };

  const onDeleteAccount = () => {
    Alert.alert(t(lang, 'confirm_delete_all'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          const id = await ensureDeviceId();
          try {
            await deleteAllAnalyses(id);
          } catch {
            // ignore
          }
          await cancelAllReminders();
          await deleteAllOriginals();
          await resetAll();
          setLastResult(null);
          router.replace('/onboarding');
        },
      },
    ]);
  };

  const langMeta = getLanguageMeta(lang);

  return (
    <SafeAreaView style={styles.safe} testID="settings-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="settings-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'settings_title')}</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Pressable
          onPress={() => router.push('/privacy')}
          style={styles.euBanner}
          testID="settings-eu-banner"
        >
          <View style={styles.euBannerIcon}>
            <Globe2 color={colors.green.text} size={22} strokeWidth={2.6} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.euBannerTitle}>
              {t(lang, 'eu_badge')} · {t(lang, 'eu_badge_sub')}
            </Text>
            <Text style={styles.euBannerSub} numberOfLines={2}>
              {t(lang, 'privacy_p_residency')}
            </Text>
          </View>
          <ChevronRight color={colors.green.text} size={22} strokeWidth={2.4} />
        </Pressable>

        <Card>
          <View style={styles.row}>
            <View style={[styles.rowIcon, { backgroundColor: colors.primarySoft }]}>
              <HardDrive color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'save_originals')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'save_originals_sub')}</Text>
            </View>
            <Switch
              value={saveOriginals}
              onValueChange={onToggleSaveOriginals}
              trackColor={{ false: colors.border, true: colors.primary }}
              thumbColor={colors.white}
              testID="settings-save-originals-toggle"
            />
          </View>
        </Card>

        <Card>
          <Pressable
            onPress={() => router.push('/language')}
            style={styles.row}
            testID="settings-change-language"
          >
            <View style={styles.rowIcon}>
              <LanguagesIcon color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'change_language')}</Text>
              <Text style={styles.rowSub}>
                {langMeta.flag}  {langMeta.nativeName} · {langMeta.englishName}
              </Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        <Card>
          <Pressable
            onPress={onExport}
            style={styles.row}
            disabled={exporting}
            testID="settings-export"
          >
            <View style={styles.rowIcon}>
              <DownloadCloud color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'export_my_data')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'export_my_data_sub')}</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        <Card>
          <Pressable
            onPress={onDeleteAll}
            style={styles.row}
            testID="settings-delete-all"
          >
            <View style={[styles.rowIcon, { backgroundColor: colors.red.bg }]}>
              <Trash2 color={colors.red.text} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'delete_all_data')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'privacy_short')}</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
          <View style={styles.divider} />
          <Pressable
            onPress={onDeleteAccount}
            style={styles.row}
            testID="settings-delete-account"
          >
            <View style={[styles.rowIcon, { backgroundColor: colors.red.bg }]}>
              <ShieldAlert color={colors.red.text} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'delete_account')}</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        <Card>
          <Pressable
            onPress={() => router.push('/privacy')}
            style={styles.row}
            testID="settings-privacy-policy"
          >
            <View style={[styles.rowIcon, { backgroundColor: colors.green.bg }]}>
              <ShieldCheck color={colors.green.text} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'privacy_policy')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'privacy_short')}</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
          <View style={styles.divider} />
          <View style={styles.row}>
            <View style={styles.rowIcon}>
              <Lock color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'disclaimer_title')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'disclaimer_long')}</Text>
            </View>
          </View>
        </Card>

        <Card>
          <Pressable
            onPress={() =>
              Alert.alert(t(lang, 'support'), 'support@klarpost.app')
            }
            style={styles.row}
            testID="settings-support"
          >
            <View style={styles.rowIcon}>
              <HelpCircle color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'support')}</Text>
              <Text style={styles.rowSub}>support@klarpost.app</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        {/* ---------- Subscription / Usage ---------- */}
        <Card testID="settings-usage-card">
          <View style={styles.row}>
            <View style={[styles.rowIcon, { backgroundColor: colors.primarySoft }]}>
              <BarChart3 color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'usage_title')}</Text>
              <Text style={styles.rowSub}>
                {usage?.plus_active
                  ? t(lang, 'usage_plus_status_active')
                  : t(lang, 'usage_plus_status_inactive')}
              </Text>
            </View>
          </View>

          <View style={styles.usageGrid}>
            <UsageRow
              label={t(lang, 'usage_free')}
              used={usage?.free_analyses_used ?? 0}
              total={usage?.free_analyses_total ?? 0}
            />
            {usage?.paywall_mode === 'soft' && (
              <UsageRow
                label={t(lang, 'usage_soft_test')}
                used={usage?.soft_extra_used ?? 0}
                total={usage?.soft_extra_total ?? 0}
              />
            )}
            <UsageRow
              label={t(lang, 'usage_single_credits')}
              used={usage?.single_letter_credits ?? 0}
            />
            {usage?.plus_active && (
              <UsageRow
                label={t(lang, 'usage_plus_remaining')}
                used={usage?.plus_monthly_used ?? 0}
                total={usage?.plus_monthly_total ?? 0}
              />
            )}
            <UsageRow
              label={t(lang, 'usage_chat_total')}
              used={usage?.total_chat_questions_used ?? 0}
              total={usage?.total_chat_questions_total ?? 0}
            />
          </View>
        </Card>

        <Card>
          <Pressable
            onPress={onManagePlus}
            style={styles.row}
            testID="settings-manage-plus"
          >
            <View style={[styles.rowIcon, { backgroundColor: colors.primarySoft }]}>
              <Crown color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'manage_plus')}</Text>
              <Text style={styles.rowSub}>
                {usage?.plus_active
                  ? t(lang, 'usage_plus_status_active')
                  : t(lang, 'usage_plus_status_inactive')}
              </Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
          <View style={styles.divider} />
          <Pressable
            onPress={onRestore}
            disabled={restoring}
            style={styles.row}
            testID="settings-restore"
          >
            <View style={styles.rowIcon}>
              <RotateCw color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'paywall_restore')}</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        {/* ---------- Dev tools (only in development builds) ---------- */}
        {__APP_DEV__ && (
          <Card testID="settings-devtools-card">
            <View style={styles.row}>
              <View style={[styles.rowIcon, { backgroundColor: colors.yellow.bg }]}>
                <FlaskConical color={colors.yellow.text} size={20} strokeWidth={2.4} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.rowTitle}>Dev tools</Text>
                <Text style={styles.rowSub}>
                  Only visible in development builds (__DEV__).
                </Text>
              </View>
            </View>
            <View style={styles.devGrid}>
              <DevButton
                label="Reset usage"
                onPress={() => callDevTool('reset', '')}
                testID="dev-reset"
              />
              <DevButton
                label="Free limit"
                onPress={() => callDevTool('simulate', 'scenario=free_limit')}
                testID="dev-free-limit"
              />
              <DevButton
                label="Soft limit"
                onPress={() => callDevTool('simulate', 'scenario=soft_limit')}
                testID="dev-soft-limit"
              />
              <DevButton
                label="Plus active"
                onPress={() => callDevTool('simulate', 'scenario=plus_active')}
                testID="dev-plus-active"
              />
              <DevButton
                label="Plus expired"
                onPress={() => callDevTool('simulate', 'scenario=plus_expired')}
                testID="dev-plus-expired"
              />
              <DevButton
                label="Plus monthly limit"
                onPress={() => callDevTool('simulate', 'scenario=plus_monthly_limit')}
                testID="dev-plus-monthly-limit"
              />
              <DevButton
                label="Add 1-letter credit"
                onPress={() => callDevTool('simulate', 'scenario=add_single_letter')}
                testID="dev-add-credit"
              />
              <DevButton
                label="Reset chat"
                onPress={() => callDevTool('simulate', 'scenario=reset_chat')}
                testID="dev-reset-chat"
              />
            </View>
          </Card>
        )}

        <Text style={styles.version}>KlarPost · v1.0.0 (MVP)</Text>
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
  euBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.xl,
    backgroundColor: colors.green.bg,
    borderWidth: 1,
    borderColor: colors.green.border ?? colors.green.bg,
  },
  euBannerIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.full,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  euBannerTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.extrabold,
    color: colors.green.text,
    letterSpacing: -0.2,
  },
  euBannerSub: {
    marginTop: 2,
    fontSize: fontSize.sm,
    color: colors.green.text,
    lineHeight: 19,
    opacity: 0.9,
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
  rowTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  rowSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 20,
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginVertical: 4,
  },
  version: {
    textAlign: 'center',
    color: colors.textMuted,
    fontSize: fontSize.xs,
    marginTop: spacing.lg,
  },
  usageGrid: {
    marginTop: spacing.md,
    gap: 8,
  },
  usageItemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
  },
  usageItemLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  usageItemValue: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    color: colors.primary,
    fontVariant: ['tabular-nums'],
  },
  devGrid: {
    marginTop: spacing.md,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  devButton: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: radius.md,
    backgroundColor: colors.yellow.bg,
    borderWidth: 1,
    borderColor: colors.yellow.border,
  },
  devButtonText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    color: colors.yellow.text,
  },
});

// ---- Sub-components scoped to settings.tsx -----------------------------

function UsageRow({
  label,
  used,
  total,
}: {
  label: string;
  used: number;
  total?: number;
}) {
  const value =
    typeof total === 'number'
      ? `${used} / ${total}`
      : String(used);
  return (
    <View style={styles.usageItemRow}>
      <Text style={styles.usageItemLabel}>{label}</Text>
      <Text style={styles.usageItemValue}>{value}</Text>
    </View>
  );
}

function DevButton({
  label,
  onPress,
  testID,
}: {
  label: string;
  onPress: () => void;
  testID?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.devButton, pressed && { opacity: 0.7 }]}
      testID={testID}
    >
      <Text style={styles.devButtonText}>{label}</Text>
    </Pressable>
  );
}
