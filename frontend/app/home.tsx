// Home: two large action buttons + recent analyses, plus header chips for
// language, history, and settings.

import { useCallback, useState } from 'react';
import { Image, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View, Alert } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  Camera,
  ClipboardList,
  FileUp,
  History,
  Settings as SettingsIcon,
  ShieldCheck,
} from 'lucide-react-native';
import { Badge } from '../src/ui';
import { listAnalyses, AnalysisListItem } from '../src/api';
import { getUsage, type UsageState } from '../src/usage';
import {
  LanguageCode,
  getLanguage as getLanguageMeta,
  t,
} from '../src/i18n';
import {
  ensureDeviceId,
  getLanguage as getStoredLanguage,
  hasConsent,
  setConsent,
} from '../src/store';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from '../src/theme';
import { EasliMark, EasliWordmark } from '../src/brand';

function riskBadgeProps(level: 'green' | 'yellow' | 'red', lang: LanguageCode) {
  return {
    label: t(lang, level === 'green' ? 'risk_green' : level === 'yellow' ? 'risk_yellow' : 'risk_red'),
    variant: level,
  } as const;
}

function formatDate(iso: string, lang: LanguageCode): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();
  if (isToday) return t(lang, 'today');
  if (isYesterday) return t(lang, 'yesterday');
  return d.toLocaleDateString();
}

export default function Home() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const l = (await getStoredLanguage()) ?? 'en';
    setLang(l);
    const id = await ensureDeviceId();
    try {
      const data = await listAnalyses(id);
      setItems(data);
    } catch {
      setItems([]);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const langMeta = getLanguageMeta(lang);

  // Active opt-in gate. If a legacy user has been onboarded but never gave
  // an explicit consent_v1 record, prompt them now before sending anything
  // to Mistral. The same dialog is reused for scan + upload entry points.
  const ensureConsentThen = async (next: () => void) => {
    if (await hasConsent()) {
      next();
      return;
    }
    Alert.alert(
      t(lang, 'privacy_h_residency'),
      t(lang, 'privacy_p_residency'),
      [
        { text: t(lang, 'cancel'), style: 'cancel' },
        {
          text: t(lang, 'continue'),
          onPress: async () => {
            await setConsent();
            next();
          },
        },
      ],
      { cancelable: true }
    );
  };

  // Proactive paywall trigger.
  //
  // We call GET /api/usage/{device_id} BEFORE letting the user open the
  // camera/picker, so they don't waste a capture on a quota that's already
  // exhausted. The backend remains the single source of truth — the
  // reactive 402/429 handling in /analyzing.tsx still catches cases where
  // usage changed between this check and the actual /api/analyze call.
  //
  // Decision tree:
  //   primary quota > 0      → proceed to scan/upload
  //   primary == 0, soft mode, soft slots remain
  //                          → /paywall?next=<target> (Continue free visible)
  //   primary == 0, soft mode, soft exhausted
  //                          → /paywall?reason=test_limit_reached&next=<target>
  //   primary == 0, hard mode
  //                          → /paywall?reason=payment_required&next=<target>
  //   network error          → proceed; backend will gate on /analyze.
  //
  // Privacy: only event names + device_id (anonymous) hit console.info — we
  // never log the usage values themselves.
  const routeWithEntitlement = async (target: '/scan' | '/upload') => {
    await ensureConsentThen(async () => {
      const id = await ensureDeviceId();
      // eslint-disable-next-line no-console
      console.info('[paywall] proactive_paywall_check device=' + id);

      let usage: UsageState | null = null;
      try {
        usage = await getUsage(id);
      } catch {
        // Network or backend hiccup — be permissive and let the user try.
        // The backend will still enforce on /api/analyze and route to the
        // paywall reactively if usage was actually exhausted.
        // eslint-disable-next-line no-console
        console.info('[paywall] proactive_paywall_check_failed');
        router.push(target);
        return;
      }

      // Privacy: we intentionally log ONLY the event name + anonymous device
      // id, never the actual usage counters or any document data.
      const r = getRemainingForLog(usage);

      // Primary quota = real entitlement (free + Plus + single-letter).
      // Soft slots are TEST allowance and intentionally NOT counted here so
      // that the paywall fires after the free trial even when soft slots
      // remain — that's the whole point of the proactive trigger.
      const freeRemaining = r.freeRemaining;
      const plusRemaining = r.plusRemaining;
      const primaryRemaining =
        freeRemaining + plusRemaining + usage.single_letter_credits;

      if (primaryRemaining > 0) {
        router.push(target);
        return;
      }

      // No primary quota left — pick the right paywall variant.
      const next = target.replace(/^\//, '');
      if (usage.paywall_mode === 'soft') {
        const softRemaining = r.softRemaining;
        if (softRemaining <= 0) {
          // eslint-disable-next-line no-console
          console.info('[paywall] proactive_paywall_route reason=test_limit_reached');
          router.push(`/paywall?reason=test_limit_reached&next=${next}`);
        } else {
          // eslint-disable-next-line no-console
          console.info('[paywall] proactive_paywall_route reason=soft_offer');
          router.push(`/paywall?next=${next}`);
        }
      } else if (usage.paywall_mode === 'hard') {
        // eslint-disable-next-line no-console
        console.info('[paywall] proactive_paywall_route reason=payment_required');
        router.push(`/paywall?reason=payment_required&next=${next}`);
      } else {
        // 'disabled' — no paywall, proceed.
        router.push(target);
      }
    });
  };

  // small helper extracted so the gate above stays readable
  const getRemainingForLog = (u: UsageState) => ({
    freeRemaining: Math.max(0, u.free_analyses_total - u.free_analyses_used),
    plusRemaining: u.plus_active
      ? Math.max(0, u.plus_monthly_total - u.plus_monthly_used)
      : 0,
    softRemaining: Math.max(0, u.soft_extra_total - u.soft_extra_used),
  });

  return (
    <SafeAreaView style={styles.safe} testID="home-screen">
      <View style={styles.topBar}>
        <View style={styles.brandRow}>
          <EasliMark size={32} tone="primary" />
          <EasliWordmark size={22} tone="primary" />
        </View>
        <View style={styles.topActions}>
          <Pressable
            onPress={() => router.push('/language')}
            style={styles.iconChip}
            testID="home-language-chip"
            hitSlop={6}
          >
            <Text style={styles.iconChipFlag}>{langMeta.flag}</Text>
            <Text style={styles.iconChipLabel}>{langMeta.nativeName}</Text>
          </Pressable>
          <Pressable
            onPress={() => router.push('/history')}
            style={styles.iconBtn}
            testID="home-history-btn"
            hitSlop={6}
          >
            <History color={colors.textPrimary} size={22} strokeWidth={2.4} />
          </Pressable>
          <Pressable
            onPress={() => router.push('/settings')}
            style={styles.iconBtn}
            testID="home-settings-btn"
            hitSlop={6}
          >
            <SettingsIcon color={colors.textPrimary} size={22} strokeWidth={2.4} />
          </Pressable>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.heroTitle}>{t(lang, 'home_quick_help')}</Text>
        <Text style={styles.heroBody}>{t(lang, 'home_intro')}</Text>

        <Pressable
          onPress={() => routeWithEntitlement('/scan')}
          style={({ pressed }) => [styles.heroButton, pressed && { opacity: 0.95 }]}
          testID="home-scan-btn"
        >
          <View style={styles.heroIconWrap}>
            <Camera color={colors.white} size={28} strokeWidth={2.5} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.heroButtonTitle}>{t(lang, 'scan_document')}</Text>
            <Text style={styles.heroButtonSubtitle}>
              {t(lang, 'tip_full_page')}
            </Text>
          </View>
        </Pressable>

        <Pressable
          onPress={() => routeWithEntitlement('/upload')}
          style={({ pressed }) => [styles.heroButtonAlt, pressed && { opacity: 0.95 }]}
          testID="home-upload-btn"
        >
          <View style={styles.heroIconWrapAlt}>
            <FileUp color={colors.primary} size={28} strokeWidth={2.5} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.heroButtonTitleAlt}>{t(lang, 'upload_file')}</Text>
            <Text style={styles.heroButtonSubtitleAlt}>PDF · JPG · PNG · WEBP</Text>
          </View>
        </Pressable>

        <Pressable
          onPress={() => router.push('/privacy')}
          style={({ pressed }) => [styles.privacyRow, pressed && { opacity: 0.7 }]}
          testID="home-privacy-banner"
        >
          <ShieldCheck color={colors.green.solid} size={16} strokeWidth={2.6} />
          <Text style={styles.privacyText}>
            <Text style={styles.privacyEU}>{t(lang, 'eu_badge')} · </Text>
            {t(lang, 'eu_badge_sub')} — {t(lang, 'privacy_short')}
          </Text>
        </Pressable>

        <View style={styles.recentHeader}>
          <Text style={styles.recentTitle}>{t(lang, 'recent_analyses')}</Text>
          {items.length > 0 ? (
            <Pressable onPress={() => router.push('/history')} testID="home-see-all">
              <Text style={styles.recentLink}>{t(lang, 'see_all')}</Text>
            </Pressable>
          ) : null}
        </View>

        {items.length === 0 ? (
          <View style={styles.emptyCard} testID="home-empty">
            <ClipboardList color={colors.textMuted} size={24} strokeWidth={2.2} />
            <Text style={styles.emptyText}>{t(lang, 'no_history')}</Text>
          </View>
        ) : (
          <View style={{ gap: spacing.sm }}>
            {items.slice(0, 3).map((it) => {
              const badge = riskBadgeProps(it.risk_level, lang);
              return (
                <Pressable
                  key={it.id}
                  onPress={() => router.push(`/result?id=${encodeURIComponent(it.id)}`)}
                  style={styles.recentItem}
                  testID={`home-recent-${it.id}`}
                >
                  <View style={{ flex: 1, gap: 6 }}>
                    <View style={styles.recentHeaderRow}>
                      <Text style={styles.recentItemTitle} numberOfLines={1}>
                        {it.document_type || it.sender || t(lang, 'document_type')}
                      </Text>
                      <Text style={styles.recentItemDate}>
                        {formatDate(it.created_at, lang)}
                      </Text>
                    </View>
                    <Text style={styles.recentItemSummary} numberOfLines={2}>
                      {it.summary_translated || it.sender || ''}
                    </Text>
                    <View style={{ marginTop: 4 }}>
                      <Badge label={badge.label} variant={badge.variant} />
                    </View>
                  </View>
                </Pressable>
              );
            })}
          </View>
        )}

        <View style={{ height: spacing.xl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  topBar: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  brandLogo: {
    width: 36,
    height: 36,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandText: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  topActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  iconChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  iconChipFlag: { fontSize: 18 },
  iconChipLabel: {
    fontSize: fontSize.sm,
    color: colors.textPrimary,
    fontWeight: fontWeight.semibold,
    maxWidth: 80,
  },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    gap: spacing.lg,
  },
  heroTitle: {
    fontSize: fontSize['3xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.6,
  },
  heroBody: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    lineHeight: 22,
    marginTop: -spacing.sm,
  },
  heroButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    borderRadius: radius.xxl,
    minHeight: 96,
    ...shadows.button,
  },
  heroIconWrap: {
    width: 56,
    height: 56,
    borderRadius: radius.lg,
    backgroundColor: 'rgba(255,255,255,0.18)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroButtonTitle: {
    color: colors.white,
    fontSize: fontSize.xl,
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.2,
  },
  heroButtonSubtitle: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: fontSize.sm,
    marginTop: 4,
  },
  heroButtonAlt: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    borderRadius: radius.xxl,
    minHeight: 96,
    borderWidth: 2,
    borderColor: colors.border,
  },
  heroIconWrapAlt: {
    width: 56,
    height: 56,
    borderRadius: radius.lg,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroButtonTitleAlt: {
    color: colors.textPrimary,
    fontSize: fontSize.xl,
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.2,
  },
  heroButtonSubtitleAlt: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
    marginTop: 4,
  },
  privacyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: radius.lg,
    backgroundColor: colors.green.bg,
    borderWidth: 1,
    borderColor: colors.green.border,
  },
  privacyText: {
    fontSize: fontSize.sm,
    color: colors.green.text,
    flex: 1,
    lineHeight: 19,
  },
  privacyEU: {
    fontWeight: fontWeight.extrabold,
  },
  recentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  recentTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  recentLink: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderStyle: 'dashed' as const,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
  },
  emptyText: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  recentItem: {
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
    ...shadows.card,
  },
  recentHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  recentItemTitle: {
    flex: 1,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  recentItemDate: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
  },
  recentItemSummary: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
