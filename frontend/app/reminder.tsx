// Reminder picker — modal route for choosing when to be reminded about a deadline.
// Routes here as /reminder?analysisId=...&deadlineKey=...&deadlineIso=...&description=...

import { useEffect, useState } from 'react';
import {
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Bell, Check, ChevronRight, X } from 'lucide-react-native';
import { Button } from '../src/ui';
import { LanguageCode, t } from '../src/i18n';
import { getLanguage as getStoredLanguage } from '../src/store';
import { scheduleReminder } from '../src/notifications';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

type Preset = '7d' | '3d' | '1d' | 'dayof' | 'custom';

function isoToDate(iso?: string): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

function presetDate(preset: Preset, deadline: Date | null): Date | null {
  if (!deadline) return null;
  const d = new Date(deadline);
  if (preset === '7d') {
    d.setDate(d.getDate() - 7);
    d.setHours(9, 0, 0, 0);
    return d;
  }
  if (preset === '3d') {
    d.setDate(d.getDate() - 3);
    d.setHours(9, 0, 0, 0);
    return d;
  }
  if (preset === '1d') {
    d.setDate(d.getDate() - 1);
    d.setHours(9, 0, 0, 0);
    return d;
  }
  if (preset === 'dayof') {
    d.setHours(9, 0, 0, 0);
    return d;
  }
  return null;
}

function formatRelative(target: Date, lang: LanguageCode): string {
  try {
    return target.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return target.toISOString();
  }
}

export default function Reminder() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    analysisId?: string;
    deadlineKey?: string;
    deadlineIso?: string;
    description?: string;
  }>();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [deadlineDate, setDeadlineDate] = useState<Date | null>(null);
  const [picked, setPicked] = useState<Date | null>(null);
  const [showPicker, setShowPicker] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getStoredLanguage().then((l) => setLang(l ?? 'en'));
    const d = isoToDate(params.deadlineIso);
    setDeadlineDate(d);
  }, [params.deadlineIso]);

  const choose = (preset: Preset) => {
    if (preset === 'custom') {
      // Default custom to deadline-1day at 9am, or now+1 day if no deadline
      const base = deadlineDate ?? new Date();
      const seed = new Date(base);
      seed.setDate(seed.getDate() - 1);
      seed.setHours(9, 0, 0, 0);
      setPicked(seed.getTime() > Date.now() ? seed : new Date(Date.now() + 60 * 60 * 1000));
      setShowPicker(true);
      return;
    }
    const target = presetDate(preset, deadlineDate);
    if (!target) return;
    if (target.getTime() <= Date.now()) {
      // Fallback: schedule 5 min from now if preset would be in the past.
      const now = new Date(Date.now() + 5 * 60 * 1000);
      setPicked(now);
      Alert.alert(t(lang, 'past_deadline'));
      return;
    }
    setPicked(target);
  };

  const onConfirm = async () => {
    if (!picked || !params.analysisId || !params.deadlineKey) return;
    if (picked.getTime() <= Date.now()) {
      Alert.alert(t(lang, 'past_deadline'));
      return;
    }
    setBusy(true);
    try {
      const desc = params.description || '';
      const rec = await scheduleReminder({
        analysisId: params.analysisId,
        deadlineKey: params.deadlineKey,
        remindAt: picked,
        title: t(lang, 'notif_title'),
        body: desc || t(lang, 'notif_body'),
        description: desc,
      });
      if (!rec) {
        Alert.alert(t(lang, 'permission_needed'));
        return;
      }
      router.back();
    } catch (e: any) {
      Alert.alert(t(lang, 'error_generic'), e?.message || '');
    } finally {
      setBusy(false);
    }
  };

  const presets: { id: Preset; label: string }[] = [
    { id: '7d', label: t(lang, 'preset_7d') },
    { id: '3d', label: t(lang, 'preset_3d') },
    { id: '1d', label: t(lang, 'preset_1d') },
    { id: 'dayof', label: t(lang, 'preset_dayof') },
    { id: 'custom', label: t(lang, 'preset_custom') },
  ];

  return (
    <SafeAreaView style={styles.safe} testID="reminder-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="reminder-close" hitSlop={12}>
          <X color={colors.textPrimary} size={24} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'remind_me')}</Text>
        <View style={{ width: 24 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.iconBig}>
          <Bell color={colors.primary} size={28} strokeWidth={2.4} />
        </View>
        <Text style={styles.title}>{t(lang, 'pick_when_remind')}</Text>
        {params.description ? (
          <Text style={styles.deadlineDesc} numberOfLines={3}>
            {params.description}
          </Text>
        ) : null}
        {deadlineDate ? (
          <View style={styles.deadlineChip}>
            <Text style={styles.deadlineChipText}>
              {deadlineDate.toLocaleDateString()}
            </Text>
          </View>
        ) : null}

        <View style={{ gap: spacing.sm, marginTop: spacing.md }}>
          {presets.map((p) => {
            const target = p.id === 'custom' ? picked : presetDate(p.id, deadlineDate);
            const disabled =
              p.id !== 'custom' &&
              (!target || target.getTime() <= Date.now());
            const isActive = picked && target && Math.abs(target.getTime() - picked.getTime()) < 1000;
            return (
              <Pressable
                key={p.id}
                onPress={() => choose(p.id)}
                disabled={disabled}
                style={[
                  styles.preset,
                  isActive && styles.presetActive,
                  disabled && { opacity: 0.4 },
                ]}
                testID={`reminder-preset-${p.id}`}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.presetLabel}>{p.label}</Text>
                  {target ? (
                    <Text style={styles.presetSub}>{formatRelative(target, lang)}</Text>
                  ) : null}
                </View>
                {isActive ? (
                  <View style={styles.tick}>
                    <Check color={colors.white} size={16} strokeWidth={3} />
                  </View>
                ) : (
                  <ChevronRight color={colors.textMuted} size={20} strokeWidth={2.4} />
                )}
              </Pressable>
            );
          })}
        </View>

        {showPicker ? (
          <View style={styles.pickerWrap}>
            <DateTimePicker
              value={picked ?? new Date(Date.now() + 60 * 60 * 1000)}
              mode={Platform.OS === 'ios' ? 'datetime' : 'date'}
              display={Platform.OS === 'ios' ? 'inline' : 'default'}
              minimumDate={new Date(Date.now() + 60 * 1000)}
              onChange={(_, d) => {
                if (Platform.OS !== 'ios') setShowPicker(false);
                if (d) setPicked(d);
              }}
            />
          </View>
        ) : null}
      </ScrollView>
      <View style={styles.footer}>
        <Button
          label={t(lang, 'continue')}
          onPress={onConfirm}
          loading={busy}
          disabled={!picked}
          icon={<Bell color={colors.white} size={18} strokeWidth={2.5} />}
          testID="reminder-confirm"
        />
      </View>
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
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  iconBig: {
    width: 64,
    height: 64,
    borderRadius: radius.xxl,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
  },
  deadlineDesc: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  deadlineChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
  },
  deadlineChipText: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
  },
  preset: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    width: '100%',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderWidth: 2,
    borderColor: colors.borderLight,
    minHeight: 64,
  },
  presetActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  presetLabel: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  presetSub: {
    marginTop: 2,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  tick: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pickerWrap: {
    width: '100%',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
    marginTop: spacing.sm,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
});
