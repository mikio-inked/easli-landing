// Analyzing screen — runs the API call while showing a calm step-by-step
// progress display. On success navigates to /result; on failure shows a
// retry/back path.

import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AlertCircle, Check, Clock, FileSearch, Languages, ScanText } from 'lucide-react-native';
import { Button } from '../src/ui';
import {
  ensureDeviceId,
  takePendingAnalysis,
  setLastResult,
  getLanguage as getStoredLanguage,
} from '../src/store';
import { analyzeDocument } from '../src/api';
import { LanguageCode, t } from '../src/i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

type Status = 'running' | 'error';

export default function Analyzing() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState<Status>('running');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const startedRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    (async () => {
      const l = (await getStoredLanguage()) ?? 'en';
      setLang(l);
      const pending = takePendingAnalysis();
      if (!pending) {
        setStatus('error');
        setErrorMsg(t(l, 'error_no_image'));
        return;
      }
      const deviceId = await ensureDeviceId();

      // Slowly advance the visual step indicator while the API call is in
      // flight. Caps at the second-to-last step until the network finishes.
      intervalRef.current = setInterval(() => {
        setStep((s) => Math.min(s + 1, 2));
      }, 1300);

      try {
        const record = await analyzeDocument({
          device_id: deviceId,
          target_language: l,
          file_base64: pending.base64,
          mime_type: pending.mimeType,
        });
        if (intervalRef.current) clearInterval(intervalRef.current);
        setStep(3);
        setLastResult(record);
        // Small pause so the user sees the final tick before navigating.
        setTimeout(() => router.replace(`/result?id=${encodeURIComponent(record.id)}`), 350);
      } catch (e: any) {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setStatus('error');
        setErrorMsg(e?.message || t(l, 'error_generic'));
      }
    })();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [router]);

  if (status === 'error') {
    return (
      <SafeAreaView style={styles.safe} testID="analyzing-error">
        <View style={styles.centerWrap}>
          <View style={styles.errorIcon}>
            <AlertCircle color={colors.red.text} size={36} strokeWidth={2.4} />
          </View>
          <Text style={styles.errorTitle}>{t(lang, 'error_generic')}</Text>
          <Text style={styles.errorBody}>{errorMsg}</Text>
        </View>
        <View style={styles.footer}>
          <Button label={t(lang, 'retry')} onPress={() => router.back()} testID="analyzing-retry" />
          <Button
            label={t(lang, 'back')}
            onPress={() => router.replace('/home')}
            variant="ghost"
            testID="analyzing-back-home"
          />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} testID="analyzing-screen">
      <View style={styles.headerWrap}>
        <Text style={styles.title}>{t(lang, 'analyzing_title')}</Text>
        <View style={styles.spinnerCircle}>
          <ActivityIndicator color={colors.primary} size="large" />
        </View>
      </View>
      <View style={styles.steps}>
        <Step
          icon={<FileSearch color={colors.primary} size={20} strokeWidth={2.4} />}
          label={t(lang, 'analyzing_step_reading')}
          state={step >= 0 ? (step > 0 ? 'done' : 'active') : 'pending'}
        />
        <Step
          icon={<ScanText color={colors.primary} size={20} strokeWidth={2.4} />}
          label={t(lang, 'analyzing_step_extracting')}
          state={step >= 1 ? (step > 1 ? 'done' : 'active') : 'pending'}
        />
        <Step
          icon={<Languages color={colors.primary} size={20} strokeWidth={2.4} />}
          label={t(lang, 'analyzing_step_translating')}
          state={step >= 2 ? (step > 2 ? 'done' : 'active') : 'pending'}
        />
        <Step
          icon={<Clock color={colors.primary} size={20} strokeWidth={2.4} />}
          label={t(lang, 'analyzing_step_checking')}
          state={step >= 3 ? 'done' : 'pending'}
        />
      </View>
    </SafeAreaView>
  );
}

function Step({
  icon,
  label,
  state,
}: {
  icon: React.ReactNode;
  label: string;
  state: 'pending' | 'active' | 'done';
}) {
  return (
    <View style={[styles.stepRow, state === 'pending' && { opacity: 0.55 }]}>
      <View
        style={[
          styles.stepIcon,
          state === 'done' && { backgroundColor: colors.green.bg, borderColor: colors.green.border },
        ]}
      >
        {state === 'done' ? <Check color={colors.green.text} size={20} strokeWidth={3} /> : icon}
      </View>
      <Text style={styles.stepLabel}>{label}</Text>
      {state === 'active' ? <ActivityIndicator color={colors.primary} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing.lg },
  headerWrap: {
    alignItems: 'center',
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
    gap: spacing.lg,
  },
  spinnerCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    textAlign: 'center',
    paddingHorizontal: spacing.md,
  },
  steps: { gap: spacing.sm, marginTop: spacing.md },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    minHeight: 64,
  },
  stepIcon: {
    width: 36,
    height: 36,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  stepLabel: {
    flex: 1,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium,
  },
  centerWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  errorIcon: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: colors.red.bg,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.red.border,
  },
  errorTitle: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  errorBody: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  footer: {
    paddingBottom: spacing.lg,
    paddingTop: spacing.sm,
    gap: spacing.sm,
  },
});
