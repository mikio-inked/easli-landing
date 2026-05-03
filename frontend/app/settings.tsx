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
  Scale,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Type,
} from 'lucide-react-native';
import { deleteAllAnalyses, exportMyData } from '../src/api';
import {
  ensureDeviceId,
  getLanguage as getStoredLanguage,
  resetAll,
  setLastResult,
} from '../src/store';
import { LanguageCode, getLanguage as getLanguageMeta, t } from '../src/i18n';
import { cancelAllReminders } from '../src/notifications';
import { deleteAllOriginals, getStorageStats, formatBytes } from '../src/originals';
import { getSaveOriginals, setSaveOriginals } from '../src/settings';
import { useUsage, getRemainingAnalyses } from '../src/usage';
import { useLargeFontMode } from '../src/largeFontMode';
import {
  isBillingAvailable,
  PaymentsUnavailableError,
  restorePurchases,
} from '../src/billing';
import * as Updates from 'expo-updates';
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
  const [storageStatsLabel, setStorageStatsLabel] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [restoring, setRestoring] = useState(false);

  const { usage, refresh: refreshUsage } = useUsage(deviceId);
  const remaining = getRemainingAnalyses(usage);
  const [largeFont, setLargeFontEnabled] = useLargeFontMode();

  // OTA Debug Block — hidden Easter egg: tap version text 5x to reveal
  const [versionTapCount, setVersionTapCount] = useState(0);
  const showOtaDebug = versionTapCount >= 5;
  const onTapVersion = useCallback(() => {
    setVersionTapCount((n) => n + 1);
  }, []);

  useFocusEffect(
    useCallback(() => {
      (async () => {
        setLang((await getStoredLanguage()) ?? 'en');
        setDeviceId(await ensureDeviceId());
      })();
      getSaveOriginals().then(setSaveOriginalsState);
      // Refresh storage stats label every time we re-focus Settings — gives
      // the user a sticky, glanceable confirmation that storage is alive.
      getStorageStats()
        .then((s) => {
          if (!s.available) {
            setStorageStatsLabel('Not available on this platform');
          } else if (s.count === 0) {
            setStorageStatsLabel('No originals saved yet');
          } else {
            setStorageStatsLabel(`${s.count} · ${formatBytes(s.totalBytes)}`);
          }
        })
        .catch(() => {
          setStorageStatsLabel(null);
        });
    }, [])
  );

  const onRestore = async () => {
    if (restoring) return;
    setRestoring(true);
    try {
      if (!isBillingAvailable()) {
        Alert.alert(
          'easli',
          Platform.OS === 'android'
            ? t(lang, 'paywall_payments_unavailable_apk')
            : t(lang, 'paywall_payments_unavailable')
        );
        return;
      }
      await restorePurchases();
      await refreshUsage();
      Alert.alert('easli', t(lang, 'paywall_restored'));
    } catch (e: any) {
      if (e instanceof PaymentsUnavailableError) {
        Alert.alert('easli', t(lang, 'paywall_payments_unavailable'));
        return;
      }
      Alert.alert('easli', t(lang, 'paywall_purchase_failed'));
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
      Alert.alert('easli', t(lang, 'paywall_payments_unavailable'));
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
          title: 'easli data export',
        },
        { dialogTitle: 'easli data export' }
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

  // The plan label shown in the Subscription section header.
  const planLabel = usage?.plus_active
    ? t(lang, 'usage_plus_status_active')
    : t(lang, 'usage_plus_status_inactive');
  // Pre-built usage rows so we can hide the ones that don't apply to the
  // current paywall mode (e.g. soft_extra is hidden on hard mode, plus is
  // hidden when not active).
  const usageEntries: { label: string; used: number; total?: number }[] = [
    {
      label: t(lang, 'usage_free'),
      used: usage?.free_analyses_used ?? 0,
      total: usage?.free_analyses_total ?? 0,
    },
    ...(usage?.paywall_mode === 'soft'
      ? [
          {
            label: t(lang, 'usage_soft_test'),
            used: usage?.soft_extra_used ?? 0,
            total: usage?.soft_extra_total ?? 0,
          },
        ]
      : []),
    {
      label: t(lang, 'usage_single_credits'),
      used: usage?.single_letter_credits ?? 0,
    },
    ...(usage?.plus_active
      ? [
          {
            label: t(lang, 'usage_plus_remaining'),
            used: usage?.plus_monthly_used ?? 0,
            total: usage?.plus_monthly_total ?? 0,
          },
        ]
      : []),
    {
      label: t(lang, 'usage_chat_total'),
      used: usage?.total_chat_questions_used ?? 0,
      total: usage?.total_chat_questions_total ?? 0,
    },
  ];

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
        {/* ---------- EU privacy banner — kept prominent on top ---------- */}
        <Pressable
          onPress={() => router.push('/privacy')}
          style={styles.euBanner}
          testID="settings-eu-banner"
        >
          <View style={styles.euBannerIcon}>
            <Globe2 color={colors.green.text} size={20} strokeWidth={2.6} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.euBannerTitle}>
              {t(lang, 'eu_badge')} · {t(lang, 'eu_badge_sub')}
            </Text>
            <Text style={styles.euBannerSub} numberOfLines={2}>
              {t(lang, 'privacy_p_residency')}
            </Text>
          </View>
          <ChevronRight color={colors.green.text} size={20} strokeWidth={2.4} />
        </Pressable>

        {/* ---------- Subscription / Usage ---------- */}
        <SectionLabel>{t(lang, 'usage_title')}</SectionLabel>
        <View style={styles.groupCard} testID="settings-usage-card">
          <View style={styles.usageHeader}>
            <View style={[styles.rowIcon, { backgroundColor: colors.primarySoft }]}>
              <BarChart3 color={colors.primary} size={18} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'usage_title')}</Text>
              <Text style={styles.rowSubMuted}>{planLabel}</Text>
            </View>
          </View>
          <View style={styles.usageGrid}>
            {usageEntries.map((u) => (
              <UsageRow key={u.label} label={u.label} used={u.used} total={u.total} />
            ))}
          </View>
          <View style={styles.divider} />
          <ListRow
            icon={<Crown color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'manage_plus')}
            onPress={onManagePlus}
            testID="settings-manage-plus"
          />
          <View style={styles.divider} />
          <ListRow
            icon={<RotateCw color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'paywall_restore')}
            onPress={onRestore}
            disabled={restoring}
            testID="settings-restore"
            isLast
          />
        </View>

        {/* ---------- Preferences ---------- */}
        <SectionLabel>{t(lang, 'settings_section_preferences')}</SectionLabel>
        <View style={styles.groupCard}>
          <ListRow
            icon={<LanguagesIcon color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'change_language')}
            valueText={`${langMeta.flag}  ${langMeta.nativeName}`}
            onPress={() => router.push('/language')}
            testID="settings-change-language"
          />
          <View style={styles.divider} />
          <ListRow
            icon={<Type color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'onb_large_font')}
            right={
              <Switch
                value={largeFont}
                onValueChange={(v) => {
                  setLargeFontEnabled(v).catch(() => {});
                }}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={colors.white}
                testID="settings-large-font-toggle"
              />
            }
            isLast
          />
        </View>

        {/* ---------- Privacy & Data ---------- */}
        <SectionLabel>{t(lang, 'settings_section_privacy_data')}</SectionLabel>
        <View style={styles.groupCard}>
          <ListRow
            icon={<HardDrive color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'save_originals')}
            right={
              <Switch
                value={saveOriginals}
                onValueChange={onToggleSaveOriginals}
                trackColor={{ false: colors.border, true: colors.primary }}
                thumbColor={colors.white}
                testID="settings-save-originals-toggle"
              />
            }
          />
          <View style={styles.divider} />
          <ListRow
            icon={<HardDrive color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'view_storage')}
            valueText={storageStatsLabel ?? '…'}
            onPress={() => router.push('/storage')}
            testID="settings-open-storage"
          />
          <View style={styles.divider} />
          <ListRow
            icon={<DownloadCloud color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'export_my_data')}
            onPress={onExport}
            disabled={exporting}
            testID="settings-export"
          />
          <View style={styles.divider} />
          <ListRow
            icon={<Trash2 color={colors.red.text} size={18} strokeWidth={2.4} />}
            iconBg={colors.red.bg}
            title={t(lang, 'delete_all_data')}
            onPress={onDeleteAll}
            destructive
            testID="settings-delete-all"
          />
          <View style={styles.divider} />
          <ListRow
            icon={<ShieldAlert color={colors.red.text} size={18} strokeWidth={2.4} />}
            iconBg={colors.red.bg}
            title={t(lang, 'delete_account')}
            onPress={onDeleteAccount}
            destructive
            testID="settings-delete-account"
            isLast
          />
        </View>

        {/* ---------- About easli ---------- */}
        <SectionLabel>{t(lang, 'settings_section_about')}</SectionLabel>
        <View style={styles.groupCard}>
          <ListRow
            icon={<ShieldCheck color={colors.green.text} size={18} strokeWidth={2.4} />}
            iconBg={colors.green.bg}
            title={t(lang, 'privacy_policy')}
            onPress={() => router.push('/privacy')}
            testID="settings-privacy-policy"
          />
          <View style={styles.divider} />
          <ListRow
            icon={<Lock color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'disclaimer_title')}
            // no onPress — informative only; modal-on-tap could come later
          />
          <View style={styles.divider} />
          <ListRow
            icon={<Scale color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'legal')}
            onPress={() => router.push('/legal' as any)}
            testID="settings-legal"
          />
          <View style={styles.divider} />
          <ListRow
            icon={<HelpCircle color={colors.primary} size={18} strokeWidth={2.4} />}
            title={t(lang, 'support')}
            valueText="support@easli.app"
            onPress={() =>
              Alert.alert(t(lang, 'support'), 'support@easli.app')
            }
            testID="settings-support"
            isLast
          />
        </View>

        {/* ---------- Dev tools (only in development builds) ---------- */}
        {__APP_DEV__ && (
          <>
            <SectionLabel>Dev tools</SectionLabel>
            <View style={styles.groupCard} testID="settings-devtools-card">
              <View style={styles.devHeader}>
                <View style={[styles.rowIcon, { backgroundColor: colors.yellow.bg }]}>
                  <FlaskConical color={colors.yellow.text} size={18} strokeWidth={2.4} />
                </View>
                <Text style={styles.devHeaderText}>
                  Only visible in development builds (__DEV__).
                </Text>
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
            </View>
          </>
        )}

        <Pressable onPress={onTapVersion} hitSlop={10}>
          <Text style={styles.version}>easli · v1.0.0 (MVP)</Text>
        </Pressable>

        {/* OTA Update Debug Block — hidden, reveal by tapping version 5 times */}
        {showOtaDebug && <OtaDebugBlock />}
      </ScrollView>
    </SafeAreaView>
  );
}

/**
 * Small diagnostic block showing the current OTA Update state.
 * Helps verify whether `eas update` pushes are reaching the device.
 * Safe to ship to production — only shows non-sensitive metadata.
 */
function OtaDebugBlock() {
  const updates = Updates.useUpdates();
  const [checking, setChecking] = useState(false);

  const fmt = (d?: Date | null) =>
    d ? new Date(d).toLocaleString() : '—';

  const onCheckNow = useCallback(async () => {
    setChecking(true);
    try {
      const res = await Updates.checkForUpdateAsync();
      if (res.isAvailable) {
        Alert.alert(
          'Update gefunden',
          'Wird heruntergeladen…',
        );
        await Updates.fetchUpdateAsync();
        Alert.alert(
          'Update bereit',
          'App startet jetzt neu, um das Update zu aktivieren.',
          [
            { text: 'Abbrechen', style: 'cancel' },
            { text: 'Neu starten', onPress: () => Updates.reloadAsync() },
          ],
        );
      } else {
        Alert.alert('Kein Update', 'Du nutzt bereits die neueste Version.');
      }
    } catch (e: any) {
      Alert.alert('Fehler', String(e?.message ?? e));
    } finally {
      setChecking(false);
    }
  }, []);

  const running = updates.currentlyRunning;
  const available = updates.availableUpdate;

  return (
    <View style={otaStyles.card}>
      <Text style={otaStyles.title}>OTA Update Status</Text>

      <DebugRow label="Channel" value={(Updates.channel as string) || '—'} />
      <DebugRow label="Runtime Version" value={Updates.runtimeVersion || '—'} />
      <DebugRow
        label="Backend URL"
        value={(process.env.EXPO_PUBLIC_BACKEND_URL as string) || '(empty)'}
      />
      <DebugRow
        label="Embedded Build"
        value={running?.isEmbeddedLaunch ? 'Yes (no OTA applied)' : 'No (running OTA bundle)'}
      />
      <DebugRow
        label="Active Update ID"
        value={running?.updateId ? running.updateId.slice(0, 8) + '…' : 'embedded'}
      />
      <DebugRow
        label="Created At"
        value={fmt(running?.createdAt)}
      />
      <DebugRow
        label="Last Check"
        value={fmt(updates.lastCheckForUpdateTimeSinceRestart)}
      />
      <DebugRow
        label="Update Available?"
        value={updates.isUpdateAvailable ? 'YES — pending' : 'No'}
      />
      <DebugRow
        label="Update Pending?"
        value={updates.isUpdatePending ? 'YES — restart to apply' : 'No'}
      />
      {available?.updateId && (
        <DebugRow
          label="Available ID"
          value={available.updateId.slice(0, 8) + '…'}
        />
      )}
      {!!updates.checkError && (
        <DebugRow
          label="Check Error"
          value={String(updates.checkError.message)}
        />
      )}
      {!!updates.downloadError && (
        <DebugRow
          label="Download Error"
          value={String(updates.downloadError.message)}
        />
      )}

      <Pressable
        style={[otaStyles.btn, checking && otaStyles.btnDisabled]}
        onPress={onCheckNow}
        disabled={checking}
      >
        <Text style={otaStyles.btnText}>
          {checking ? 'Prüfe…' : 'Jetzt nach Update prüfen'}
        </Text>
      </Pressable>

      {updates.isUpdatePending && (
        <Pressable
          style={[otaStyles.btn, otaStyles.btnPrimary]}
          onPress={() => Updates.reloadAsync()}
        >
          <Text style={[otaStyles.btnText, otaStyles.btnTextPrimary]}>
            Update jetzt anwenden (App neu starten)
          </Text>
        </Pressable>
      )}
    </View>
  );
}

function DebugRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={otaStyles.row}>
      <Text style={otaStyles.rowLabel}>{label}</Text>
      <Text style={otaStyles.rowValue} numberOfLines={2}>{value}</Text>
    </View>
  );
}

const otaStyles = StyleSheet.create({
  card: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    marginBottom: spacing.xl,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  title: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingVertical: 4,
    gap: spacing.sm,
  },
  rowLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    flexShrink: 0,
  },
  rowValue: {
    fontSize: fontSize.xs,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium,
    textAlign: 'right',
    flexShrink: 1,
  },
  btn: {
    marginTop: spacing.md,
    paddingVertical: 10,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  btnDisabled: { opacity: 0.5 },
  btnPrimary: {
    marginTop: spacing.sm,
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  btnText: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.textPrimary,
  },
  btnTextPrimary: { color: colors.surface },
});

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
  // Tighter outer rhythm: only spacing.sm between section-label and its
  // group-card so the sections feel connected. Each group-card is its own
  // padded container, so we don't need spacing inside `content` between
  // unrelated rows.
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xl,
  },
  // EU privacy banner (kept on top, prominent).
  euBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.green.bg,
    borderWidth: 1,
    borderColor: colors.green.border ?? colors.green.bg,
    marginBottom: spacing.md,
  },
  euBannerIcon: {
    width: 38,
    height: 38,
    borderRadius: radius.full,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  euBannerTitle: {
    fontSize: fontSize.body,
    fontWeight: fontWeight.bold,
    color: colors.green.text,
    letterSpacing: -0.2,
  },
  euBannerSub: {
    marginTop: 2,
    fontSize: fontSize.xs,
    color: colors.green.text,
    lineHeight: 17,
    opacity: 0.9,
  },
  // iOS-Settings-style section label rendered above each group-card.
  sectionLabel: {
    fontSize: 12,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.xs,
  },
  // Group card — one card per section, each row separated by a hairline
  // divider rendered between rows.
  groupCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  // List row — compact, ~52 px high, single-line title by default.
  listRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: 12,
    paddingHorizontal: spacing.md,
    minHeight: 52,
  },
  listRowDisabled: {
    opacity: 0.5,
  },
  // Legacy alias — preserved for usage-card header rendered through plain
  // <View> rather than <ListRow>.
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  cardLike: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  rowIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowTitle: {
    fontSize: fontSize.body,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  rowTitleDestructive: {
    color: colors.red.text,
  },
  rowSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 18,
  },
  rowSubMuted: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 1,
  },
  // Right-aligned secondary text inside a list row (e.g. current language
  // pick, storage size, support email).
  listRowValue: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    maxWidth: 160,
    textAlign: 'right',
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
    // Indent under the icon column so the hairline doesn't run into it —
    // standard iOS settings-row treatment.
    marginLeft: spacing.md + 32 + spacing.md,
  },
  version: {
    textAlign: 'center',
    color: colors.textMuted,
    fontSize: fontSize.xs,
    marginTop: spacing.xl,
    marginBottom: spacing.lg,
  },
  // Subscription card internals -------------------------------------------
  usageHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.md,
  },
  usageGrid: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    gap: 6,
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
  // Dev-tools card internals ----------------------------------------------
  devHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.md,
  },
  devHeaderText: {
    flex: 1,
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    lineHeight: 17,
  },
  devGrid: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
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

/** Small uppercase label rendered above each group-card. */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return <Text style={styles.sectionLabel}>{children}</Text>;
}

interface ListRowProps {
  /** Lucide icon node, sized 18 px. */
  icon: React.ReactNode;
  /** Optional override for the icon-bubble background colour. */
  iconBg?: string;
  title: string;
  /** Right-aligned secondary text (e.g. current value). Mutually exclusive
   *  with `right` — when `right` is provided the value text is ignored. */
  valueText?: string;
  /** Custom right-side slot (e.g. <Switch />). Wins over `valueText`. */
  right?: React.ReactNode;
  onPress?: () => void;
  destructive?: boolean;
  disabled?: boolean;
  testID?: string;
  /** When true, the chevron and right-padding hairline alignment treat this
   *  row as the last in its group (used purely for the divider element
   *  rendered between rows by the parent — this prop is informational and
   *  doesn't change the row itself today). */
  isLast?: boolean;
}

function ListRow({
  icon,
  iconBg,
  title,
  valueText,
  right,
  onPress,
  destructive,
  disabled,
  testID,
}: ListRowProps) {
  // Pick the right-side slot. Priority: explicit `right` → valueText →
  // chevron (when navigable) → nothing.
  const rightSlot =
    right ??
    (valueText ? (
      <Text style={styles.listRowValue} numberOfLines={1}>
        {valueText}
      </Text>
    ) : onPress ? (
      <ChevronRight color={colors.textMuted} size={18} strokeWidth={2.4} />
    ) : null);

  const content = (
    <>
      <View style={[styles.rowIcon, iconBg ? { backgroundColor: iconBg } : null]}>
        {icon}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[styles.rowTitle, destructive && styles.rowTitleDestructive]}>
          {title}
        </Text>
      </View>
      {rightSlot}
    </>
  );

  if (!onPress) {
    return <View style={[styles.listRow, disabled && styles.listRowDisabled]}>{content}</View>;
  }
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      testID={testID}
      style={({ pressed }) => [
        styles.listRow,
        disabled && styles.listRowDisabled,
        pressed && { backgroundColor: colors.surfaceMuted },
      ]}
    >
      {content}
    </Pressable>
  );
}

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
