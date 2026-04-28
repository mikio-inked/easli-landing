// Analyzing screen — runs the API call while showing a calm step-by-step
// progress display. On success navigates to /result; on failure shows a
// retry/back path.

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
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
import { analyzeDocument, PaymentRequiredError, RateLimitError, TestLimitReachedError, UnsupportedDocumentLanguageError } from '../src/api';
import { LanguageCode, t } from '../src/i18n';
import { saveOriginal } from '../src/originals';
import { getSaveOriginals } from '../src/settings';
import { compressPagesForUpload } from '../src/imageCompression';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

type Status = 'running' | 'error' | 'lang_rejected';

/**
 * Everything we need to *re-fire* an /api/analyze call without going back to
 * /scan. Cached after the (potentially expensive) compression pass so retries
 * don't redo it. idempotencyKey stays the same so the server can dedupe if
 * the previous attempt was actually accepted but the response was lost.
 */
type AnalysisCtx = {
  deviceId: string;
  pages: { base64: string; mimeType: string }[];
  idempotencyKey: string;
  lang: LanguageCode;
};

export default function Analyzing() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState<Status>('running');
  const [errorMsg, setErrorMsg] = useState<string>('');
  // Live countdown shown on the retry button while we politely wait for
  // Mistral's rate-limit window to reset. 0 = button is enabled.
  const [retryCountdown, setRetryCountdown] = useState<number>(0);
  // True when the failure is something we can re-fire from this screen
  // (rate-limit, network, generic). False for terminal states (paywall,
  // missing image) where retry doesn't make sense.
  const [retryable, setRetryable] = useState<boolean>(false);
  const startedRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Cached analysis input — populated after the first successful compression
  // pass so that the retry button can re-fire the API call without going
  // back to /scan and forcing the user to re-take photos.
  const ctxRef = useRef<AnalysisCtx | null>(null);

  /**
   * Drives one /api/analyze call and routes the user accordingly.
   * Used both by the initial run and by the retry button. Caller is
   * responsible for populating ctxRef before calling this.
   */
  const runAnalysis = useCallback(async (ctx: AnalysisCtx) => {
    setStatus('running');
    setStep(0);
    setErrorMsg('');
    setRetryable(false);

    // Slowly advance the visual step indicator while the API call is in
    // flight. Caps at the second-to-last step until the network finishes.
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      setStep((s) => Math.min(s + 1, 2));
    }, 1300);

    try {
      const record = await analyzeDocument({
        device_id: ctx.deviceId,
        target_language: ctx.lang,
        pages: ctx.pages.map((p) => ({ file_base64: p.base64, mime_type: p.mimeType })),
        idempotency_key: ctx.idempotencyKey,
      });
      if (intervalRef.current) clearInterval(intervalRef.current);
      setStep(3);
      setLastResult(record);
      // Optional on-device storage of the original document — opt-in only.
      // For multi-page captures we store only the first page (preview only).
      // We capture success/failure here so the result screen can show a
      // visible banner ("Saved on this device" / "Could not save") instead
      // of silently swallowing errors. The banner state lives in
      // AsyncStorage under a single key that result.tsx consumes once on
      // mount and immediately clears.
      try {
        if ((await getSaveOriginals()) && ctx.pages.length > 0) {
          const first = ctx.pages[0];
          const ok = await saveOriginal(record.id, first.base64, first.mimeType);
          await AsyncStorage.setItem(
            'klarpost.lastSaveBanner',
            JSON.stringify({ id: record.id, ok, at: Date.now() }),
          );
        }
      } catch {
        // saveOriginal already logs; AsyncStorage write itself shouldn't crash.
      }
      // Small pause so the user sees the final tick before navigating.
      setTimeout(() => router.replace(`/result?id=${encodeURIComponent(record.id)}`), 350);
    } catch (e: any) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      // Backend entitlement gates — these are terminal, retry doesn't help.
      if (e instanceof TestLimitReachedError) {
        router.replace('/paywall?reason=test_limit_reached');
        return;
      }
      if (e instanceof PaymentRequiredError) {
        router.replace('/paywall?reason=payment_required');
        return;
      }
      // Language gate — document is clearly non-German. Zero quota was
      // consumed server-side. Show a calm dedicated screen instead of the
      // generic error toast. No retry button — the document itself is the
      // wrong input, so the only sensible action is "scan another document".
      if (e instanceof UnsupportedDocumentLanguageError) {
        setStatus('lang_rejected');
        // Body is the localized string from the backend, or the i18n fallback
        // if the server didn't provide one.
        setErrorMsg(e.message || t(ctx.lang, 'lang_gate_reject_body'));
        setRetryable(false);
        return;
      }
      // Mistral rate-limited us. Show the truthful Retry-After window the
      // server gave us, start a live countdown on the retry button, and
      // keep the analysis context cached so the user can re-fire from this
      // screen instead of going back to /scan.
      if (e instanceof RateLimitError) {
        const seconds = Math.max(1, Math.min(120, e.retryAfterSeconds || 8));
        setStatus('error');
        setErrorMsg(
          t(ctx.lang, 'error_rate_limited').replace('{n}', String(seconds)),
        );
        setRetryable(true);
        setRetryCountdown(seconds);
        return;
      }
      // Any other error (network, 502, parse, etc.). The user can re-fire
      // immediately — no countdown needed.
      setStatus('error');
      setErrorMsg(e?.message || t(ctx.lang, 'error_generic'));
      setRetryable(true);
    }
  }, [router]);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    (async () => {
      const l = (await getStoredLanguage()) ?? 'en';
      setLang(l);
      const pending = takePendingAnalysis();
      if (!pending || pending.pages.length === 0) {
        setStatus('error');
        setErrorMsg(t(l, 'error_no_image'));
        // No pages cached — only path forward is to go back and re-scan.
        setRetryable(false);
        return;
      }
      const deviceId = await ensureDeviceId();

      // Compress every page to vision-friendly size BEFORE the upload.
      // This is where we save the most bandwidth + battery: a 4-page
      // VisionKit scan can be 25-40 MB raw → typically becomes ~400 KB.
      // compressPagesForUpload() always returns a list of the same length
      // (falls back to the original page on any failure) so this is safe
      // to drop in front of the API call.
      const compressed = await compressPagesForUpload(pending.pages);

      // Cache so the retry button can re-fire without recompressing or
      // re-asking for permissions.
      ctxRef.current = {
        deviceId,
        pages: compressed,
        idempotencyKey: pending.idempotencyKey,
        lang: l,
      };

      await runAnalysis(ctxRef.current);
    })();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [runAnalysis]);

  // Live countdown for the retry button. Re-fires every second while > 0,
  // self-terminates at 0. We use setTimeout (not setInterval) so each tick
  // only schedules the next one — no cleanup-leak risk if React unmounts
  // mid-tick.
  useEffect(() => {
    if (retryCountdown <= 0) return;
    const timer = setTimeout(() => {
      setRetryCountdown((c) => Math.max(0, c - 1));
    }, 1000);
    return () => clearTimeout(timer);
  }, [retryCountdown]);

  /**
   * Retry button handler. If we have a cached analysis context, re-fire the
   * same /api/analyze call (server is idempotent on idempotency_key).
   * Otherwise fall back to going back to /scan so the user can reshoot.
   *
   * Note: the button is no longer disabled during the countdown — tapping
   * during a wait window is now permitted (we cancel the countdown and try
   * immediately). The countdown is purely advisory: the next attempt may
   * still 429 if the user jumps the gun, but we've found that users
   * confused by a non-responsive button is a worse outcome than letting
   * them retry early. The auto-fire-when-countdown-hits-0 path below also
   * frees the user from having to tap at all.
   */
  const onRetry = useCallback(() => {
    if (ctxRef.current) {
      runAnalysis(ctxRef.current);
      return;
    }
    router.back();
  }, [runAnalysis, router]);

  if (status === 'lang_rejected') {
    // Dedicated screen for the language gate. Calm, no red alert icon,
    // no retry button — the document itself is the wrong input. Only
    // action is "scan another document" which takes the user back to the
    // capture flow.
    return (
      <SafeAreaView style={styles.safe} testID="analyzing-lang-rejected">
        <View style={styles.centerWrap}>
          <View style={[styles.errorIcon, { backgroundColor: colors.primarySoft }]}>
            <FileSearch color={colors.primary} size={36} strokeWidth={2.4} />
          </View>
          <Text style={styles.errorTitle}>{t(lang, 'lang_gate_reject_title')}</Text>
          <Text style={styles.errorBody}>
            {errorMsg || t(lang, 'lang_gate_reject_body')}
          </Text>
          <Text style={[styles.errorBody, { marginTop: spacing.md, fontSize: fontSize.sm, color: colors.textSecondary }]}>
            {t(lang, 'lang_gate_reject_hint')}
          </Text>
        </View>
        <View style={styles.footer}>
          <Button
            label={t(lang, 'lang_gate_reject_cta')}
            onPress={() => router.replace('/scan')}
            testID="analyzing-lang-rejected-cta"
          />
          <Button
            label={t(lang, 'back')}
            onPress={() => router.replace('/home')}
            variant="ghost"
            testID="analyzing-lang-rejected-home"
          />
        </View>
      </SafeAreaView>
    );
  }

  if (status === 'error') {
    // Countdown is purely informational — the button is always tappable so
    // the user can re-fire immediately if they want. The "(Ns)" suffix tells
    // them how long Mistral asked us to wait, so an early tap may 429 again,
    // but that's their call.
    const retryLabel = retryCountdown > 0
      ? `${t(lang, 'retry')} (${retryCountdown}s)`
      : t(lang, 'retry');
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
          <Button
            label={retryLabel}
            onPress={onRetry}
            disabled={!retryable}
            testID="analyzing-retry"
          />
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
