// Email Inbox screen — Phase 4.
//
// Shows the user their personal easli-Inbox email address and the
// step-by-step instructions for forwarding letters to it.
//
// On mount, calls GET /api/inbox/me which lazily generates the token
// on the backend if this device doesn't have one yet. The endpoint is
// idempotent so a screen revisit just returns the existing address.

import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
  ActivityIndicator,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, Copy, Mail, RefreshCw, Share2 } from 'lucide-react-native';
import { LanguageCode, t } from '../src/i18n';
import { getLanguage, ensureDeviceId } from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';
import { API_BASE } from '../src/api';
import * as haptics from '../src/haptics';

interface InboxInfo {
  device_id: string;
  inbox_token: string;
  inbox_email: string;
  inbox_letters_received: number;
}

export default function InboxScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [info, setInfo] = useState<InboxInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const l = (await getLanguage()) ?? 'en';
      setLang(l);
      const did = await ensureDeviceId();
      const res = await fetch(`${API_BASE}/api/inbox/me?device_id=${encodeURIComponent(did)}`);
      if (!res.ok) throw new Error('inbox_fetch_failed');
      const json = (await res.json()) as InboxInfo;
      setInfo(json);
    } catch {
      Alert.alert('easli', t(lang, 'error_generic'));
    } finally {
      setLoading(false);
    }
  }, [lang]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCopy = useCallback(async () => {
    if (!info) return;
    haptics.tap();
    await Clipboard.setStringAsync(info.inbox_email);
    Alert.alert('easli', t(lang, 'inbox_copied'));
  }, [info, lang]);

  const onShare = useCallback(async () => {
    if (!info) return;
    haptics.tap();
    try {
      await Share.share({
        message: info.inbox_email,
        title: t(lang, 'inbox_share_title'),
      });
    } catch {
      // user cancelled — silent
    }
  }, [info, lang]);

  const onRotate = useCallback(async () => {
    if (!info) return;
    Alert.alert(
      t(lang, 'inbox_rotate_confirm_title'),
      t(lang, 'inbox_rotate_confirm_msg'),
      [
        { text: t(lang, 'cancel'), style: 'cancel' },
        {
          text: t(lang, 'inbox_rotate_confirm_cta'),
          style: 'destructive',
          onPress: async () => {
            haptics.warning();
            try {
              const did = await ensureDeviceId();
              const res = await fetch(`${API_BASE}/api/inbox/rotate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: did }),
              });
              if (!res.ok) throw new Error('rotate_failed');
              const json = (await res.json()) as InboxInfo;
              setInfo(json);
              haptics.success();
            } catch {
              haptics.error();
              Alert.alert('easli', t(lang, 'error_generic'));
            }
          },
        },
      ],
    );
  }, [info, lang]);

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12} testID="inbox-back">
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'inbox_title')}</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* ---- Hero ---- */}
        <View style={styles.heroCard}>
          <View style={styles.heroIcon}>
            <Mail color={colors.primary} size={28} strokeWidth={2.4} />
          </View>
          <Text style={styles.heroTitle}>{t(lang, 'inbox_hero_title')}</Text>
          <Text style={styles.heroSubtitle}>{t(lang, 'inbox_hero_subtitle')}</Text>
        </View>

        {/* ---- Address ---- */}
        {loading || !info ? (
          <View style={{ alignItems: 'center', marginTop: spacing.xl }}>
            <ActivityIndicator size="small" color={colors.primary} />
          </View>
        ) : (
          <>
            <View style={styles.addressCard}>
              <Text style={styles.label}>{t(lang, 'inbox_your_address')}</Text>
              <Pressable
                onPress={onCopy}
                style={({ pressed }) => [styles.addressRow, pressed && { opacity: 0.7 }]}
                testID="inbox-address"
              >
                <Text style={styles.address} selectable>
                  {info.inbox_email}
                </Text>
                <Copy color={colors.primary} size={18} strokeWidth={2.4} />
              </Pressable>
              <Text style={styles.statsLine}>
                {t(lang, 'inbox_letters_received').replace(
                  '{n}',
                  String(info.inbox_letters_received),
                )}
              </Text>
            </View>

            <View style={styles.buttonRow}>
              <Pressable
                onPress={onCopy}
                style={styles.actionBtn}
                testID="inbox-copy"
              >
                <Copy color={colors.primary} size={18} strokeWidth={2.4} />
                <Text style={styles.actionBtnLabel}>{t(lang, 'inbox_copy')}</Text>
              </Pressable>
              <Pressable
                onPress={onShare}
                style={styles.actionBtn}
                testID="inbox-share"
              >
                <Share2 color={colors.primary} size={18} strokeWidth={2.4} />
                <Text style={styles.actionBtnLabel}>{t(lang, 'inbox_share')}</Text>
              </Pressable>
            </View>

            {/* ---- How it works ---- */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>{t(lang, 'inbox_how_it_works')}</Text>
              <Step n={1} text={t(lang, 'inbox_step_1')} />
              <Step n={2} text={t(lang, 'inbox_step_2')} />
              <Step n={3} text={t(lang, 'inbox_step_3')} />
            </View>

            {/* ---- Rotate ---- */}
            <Pressable
              onPress={onRotate}
              style={styles.rotateBtn}
              testID="inbox-rotate"
            >
              <RefreshCw color={colors.textSecondary} size={16} strokeWidth={2.4} />
              <Text style={styles.rotateBtnLabel}>{t(lang, 'inbox_rotate')}</Text>
            </Pressable>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Step({ n, text }: { n: number; text: string }) {
  return (
    <View style={styles.stepRow}>
      <View style={styles.stepBubble}>
        <Text style={styles.stepNum}>{n}</Text>
      </View>
      <Text style={styles.stepText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  content: { padding: spacing.lg, gap: spacing.lg },
  heroCard: {
    backgroundColor: colors.primarySoft,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    alignItems: 'center',
  },
  heroIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  heroTitle: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: 4,
  },
  heroSubtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  addressCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  label: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: spacing.sm,
  },
  addressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.lg,
    paddingVertical: 12,
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  address: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.textPrimary,
    fontWeight: fontWeight.semibold,
  },
  statsLine: {
    marginTop: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },
  buttonRow: { flexDirection: 'row', gap: spacing.sm },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: 14,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    minHeight: 48,
  },
  actionBtnLabel: {
    fontSize: fontSize.md,
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  section: { gap: spacing.md },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  stepRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
  stepBubble: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNum: {
    color: colors.white,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
  },
  stepText: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  rotateBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    marginTop: spacing.md,
  },
  rotateBtnLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textDecorationLine: 'underline',
  },
});
