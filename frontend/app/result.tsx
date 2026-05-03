// Result screen 2.0 — Risk Hero + Action Pyramid + Detail Accordions.
// Goal: scannable for elderly / non-native speakers. The most important
// safety + action info is visible without scrolling; details collapse
// behind tap-to-expand cards so the screen never feels overwhelming.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  Easing,
  LayoutAnimation,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  UIManager,
  View,
} from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Clipboard from 'expo-clipboard';
import * as Linking from 'expo-linking';
import { Share } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  BellRing,
  Building2,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  Eye,
  FileText,
  Globe,
  HelpCircle,
  Info,
  ListTodo,
  MessageCircle,
  Reply,
  Share2,
  ShieldAlert,
  Trash2,
  X,
  XCircle,
} from 'lucide-react-native';
import { Badge, Button, SectionTitle } from '../src/ui';
import {
  ensureDeviceId,
  getLastResult,
  setLastResult,
  getLanguage as getStoredLanguage,
} from '../src/store';
import { AnalysisRecord, deleteAnalysis, getAnalysis, translateAnalysis } from '../src/api';
import { LanguageCode, categoryLabel, t } from '../src/i18n';
import { shareAnalysisAsPdf, shareAnalysisAsText } from '../src/share';
import {
  cancelAllForAnalysis,
  cancelReminder,
  getReminders,
  ReminderRecord,
} from '../src/notifications';
import { deleteOriginal, hasOriginal } from '../src/originals';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from '../src/theme';
import { ReadAloudButton } from '../src/components/ReadAloudButton';
import { ScamWarningModal } from '../src/components/ScamWarningModal';
import { ReplyAssistant } from '../src/replyAssistant';
import {
  EXPLANATION_LANGUAGES,
  countryCodeToFlag,
  formatLanguageLabel,
  getAnyLanguage,
} from '../src/languages';

// Enable LayoutAnimation on Android (iOS supports it natively).
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

function riskMeta(level: 'green' | 'yellow' | 'red', lang: LanguageCode) {
  if (level === 'green') {
    return {
      label: t(lang, 'risk_green'),
      icon: <Info color={colors.green.text} size={26} strokeWidth={2.4} />,
      palette: colors.green,
    };
  }
  if (level === 'yellow') {
    return {
      label: t(lang, 'risk_yellow'),
      icon: <AlertTriangle color={colors.yellow.text} size={26} strokeWidth={2.4} />,
      palette: colors.yellow,
    };
  }
  return {
    label: t(lang, 'risk_red'),
    icon: <ShieldAlert color={colors.red.text} size={26} strokeWidth={2.4} />,
    palette: colors.red,
  };
}

function deadlineKeyFor(idx: number, d: { date: string; description: string }): string {
  return `${idx}|${(d.date || '').trim()}|${(d.description || '').slice(0, 40).trim()}`;
}

function tryParseDeadlineDate(raw: string): Date | null {
  if (!raw) return null;
  const s = raw.trim();
  // ISO first
  const iso = new Date(s);
  if (!isNaN(iso.getTime()) && /\d{4}/.test(s)) return iso;
  // German DD.MM.YYYY
  const dm = s.match(/^(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{2,4})$/);
  if (dm) {
    const day = parseInt(dm[1], 10);
    const mon = parseInt(dm[2], 10) - 1;
    let yr = parseInt(dm[3], 10);
    if (yr < 100) yr += 2000;
    const d = new Date(yr, mon, day, 9, 0, 0, 0);
    if (!isNaN(d.getTime())) return d;
  }
  return null;
}

// Days from now to the given date. Returns 0 for today, negative for past.
function daysUntil(d: Date): number {
  const now = new Date();
  const a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const b = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((a.getTime() - b.getTime()) / 86400000);
}

// Build a calm, language-aware "in N days / tomorrow / overdue" label.
function formatRelativeDays(days: number, lang: LanguageCode): string {
  if (days === 0) return t(lang, 'today_label');
  if (days === 1) return t(lang, 'in_one_day');
  if (days > 0) return t(lang, 'in_n_days').replace('{n}', String(days));
  return t(lang, 'days_overdue').replace('{n}', String(Math.abs(days)));
}

// Pick the SINGLE most-important thing to surface in the Main Action card.
// Heuristic:
//   1) The soonest non-past deadline (with parseable date) wins.
//   2) Else the first high-urgency required action.
//   3) Else the first required action.
//   4) Else null → don't render the card.
type MainAction =
  | {
      kind: 'deadline';
      date: Date;
      raw: string;
      description: string;
      days: number;
      requiresResponse: boolean;
    }
  | { kind: 'action'; action: string; reason?: string; urgency?: string }
  | null;

const REPLY_TOKENS = [
  // EN
  'reply', 'respond', 'response', 'answer', 'submit', 'confirm', 'object',
  'objection', 'contact', 'send back', 'return',
  // DE
  'antwort', 'rückantwort', 'rückmeld', 'antworten', 'einreich', 'bestätig',
  'widerspruch', 'einspruch', 'kontakt', 'zurücksend', 'rücksend',
  // ES
  'respond', 'contest', 'envia', 'confirm',
  // RU
  'отвеч', 'ответ', 'подтверд', 'возраж',
  // TR
  'yanıtla', 'cevap', 'itiraz', 'onayla',
  // VI
  'trả lời', 'phản hồi', 'xác nhận', 'phản đối',
  // ZH
  '回复', '回答', '确认', '反对',
];

function tokenSearch(haystack: string, needles: string[]): boolean {
  const h = haystack.toLowerCase();
  return needles.some((n) => h.includes(n));
}

function replyRequired(r: any): boolean {
  const fields = [
    ...(r.required_actions || []).map((a: any) => `${a.action || ''} ${a.reason || ''}`),
    r.simple_explanation_translated || '',
    r.summary_translated || '',
  ];
  if (tokenSearch(fields.join(' '), REPLY_TOKENS)) return true;
  // If there's a reply draft and a deadline, we treat that as "reply needed".
  if ((r as any).reply_draft && (r.deadlines || []).length > 0) return true;
  if (r.german_reply_draft && (r.deadlines || []).length > 0) return true;
  return false;
}

function pickMainAction(r: any): MainAction {
  const deadlines = (r.deadlines || []) as Array<{ date: string; description: string }>;
  // 1) soonest non-past deadline
  const dated = deadlines
    .map((d) => ({ d, parsed: tryParseDeadlineDate(d.date || '') }))
    .filter((x) => !!x.parsed && x.parsed!.getTime() >= Date.now() - 86400000) // include today
    .sort((a, b) => a.parsed!.getTime() - b.parsed!.getTime());
  if (dated.length > 0) {
    const top = dated[0];
    return {
      kind: 'deadline',
      date: top.parsed!,
      raw: top.d.date,
      description: top.d.description || '',
      days: daysUntil(top.parsed!),
      requiresResponse: replyRequired(r),
    };
  }
  // 2) highest urgency action
  const acts = (r.required_actions || []) as Array<{
    action: string;
    urgency?: string;
    reason?: string;
  }>;
  const high = acts.find((a) => a.urgency === 'high');
  if (high) {
    return { kind: 'action', action: high.action, reason: high.reason, urgency: 'high' };
  }
  if (acts.length > 0) {
    const a = acts[0];
    return { kind: 'action', action: a.action, reason: a.reason, urgency: a.urgency };
  }
  return null;
}

function hasImportantUncertainty(r: any): boolean {
  // "Important" = anything that mentions money, dates, payment, sender,
  // legal/medical/tax. We're generous here so the user errs on the side of
  // double-checking. If there are no uncertainties at all, this returns
  // false and the section stays hidden.
  const un = (r.uncertainties || []) as string[];
  if (un.length === 0) return false;
  const importantHints = [
    // EN
    'date', 'amount', 'pay', 'paid', 'iban', 'sender', 'identity',
    'legal', 'medical', 'tax',
    // DE
    'datum', 'betrag', 'zahl', 'absender', 'recht', 'medizin', 'steuer',
    // ES
    'fecha', 'monto', 'pago', 'remitente',
    // RU
    'дата', 'сумм', 'плат', 'отправит',
    // TR
    'tarih', 'tutar', 'ödem', 'gönder',
    // VI
    'ngày', 'số tiền', 'thanh toán', 'người gửi',
    // ZH
    '日期', '金额', '付款', '发件人',
  ];
  return un.some((u) => tokenSearch(u, importantHints));
}

export default function ResultScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [record, setRecord] = useState<AnalysisRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [reminders, setReminders] = useState<ReminderRecord[]>([]);
  const [originalSaved, setOriginalSaved] = useState(false);
  // Save-banner state — populated from `klarpost.lastSaveBanner` AsyncStorage
  // key written by analyzing.tsx after the optional original save attempt.
  // We read+clear once on mount so the banner appears immediately after
  // navigation but NOT when the user later returns to the same record from
  // history. Auto-dismissed after 4s.
  const [saveBanner, setSaveBanner] = useState<'ok' | 'fail' | null>(null);
  // Per-section open state. Default values are computed lazily from the
  // analysis result via `defaultOpenSections(record)` below — that lets us
  // smartly auto-open Reply Draft only when a reply is required, etc.
  // After the user toggles, their explicit choice wins (stored as bool).
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});
  // Device id for backend calls. Loaded once on mount; the ReplyAssistant
  // and other tab content rely on it.
  const [deviceId, setDeviceId] = useState<string>('');
  // Phase R3: result-screen redesign — segmented "tab" navigation. The
  // user sees ONE tab's content at a time so the page no longer scrolls
  // forever. Tabs that have no content are simply not rendered, so the
  // pill-bar always reflects what's actually available for THIS document.
  // Default tab is 'overview' (calm summary + any scam warning).
  const [activeTab, setActiveTab] = useState<
    'overview' | 'actions' | 'deadlines' | 'reply' | 'details'
  >('overview');
  // ---- "Change language" feature state ----
  // `displayLang` is which language version of the analysis the user is
  // CURRENTLY looking at. It defaults to the analysis's primary language,
  // but can diverge after the user taps the language switcher.
  // NOTE: this is separate from `lang` (the UI chrome language — button
  // labels, headings) because a user who reads the app in German but wants
  // the Telekom letter explained in English should get English content
  // with German chrome.
  const [displayLang, setDisplayLang] = useState<LanguageCode | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);

  const toggleSection = useCallback((key: string, currentlyOpen: boolean) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    // Pass the *visible* current state so we honour smart defaults: when
    // a section is open via fallback (no explicit user choice), tapping it
    // must move to closed (false), not flip from undefined to true.
    setOpenSections((prev) => ({ ...prev, [key]: !currentlyOpen }));
  }, []);

  const refreshReminders = useCallback(async (recordId: string) => {
    const list = await getReminders(recordId);
    setReminders(list);
  }, []);

  useEffect(() => {
    (async () => {
      const l = (await getStoredLanguage()) ?? 'en';
      setLang(l);

      // Pop the "Saved on this device" banner — written by analyzing.tsx —
      // exactly once per analysis. Banner survives a screen re-mount only if
      // we haven't read it yet, so consuming it here gives feedback right
      // after the new analysis arrives, but never on later visits to history.
      try {
        const raw = await AsyncStorage.getItem('klarpost.lastSaveBanner');
        if (raw) {
          const data = JSON.parse(raw) as { id?: string; ok?: boolean; at?: number };
          await AsyncStorage.removeItem('klarpost.lastSaveBanner');
          // Only show if banner is recent (<60s) AND matches the analysis we
          // are about to display — guards against stale entries surviving
          // app crashes or background-kills.
          const fresh = typeof data.at === 'number' && Date.now() - data.at < 60_000;
          if (fresh && (id ? data.id === id : true)) {
            setSaveBanner(data.ok ? 'ok' : 'fail');
            setTimeout(() => setSaveBanner(null), 4000);
          }
        }
      } catch {
        // banner is best-effort; never block result rendering on it
      }

      const cached = getLastResult();
      if (cached && (!id || cached.id === id)) {
        // Ensure device_id is always available — even on the in-memory
        // cache fast-path. Previously this was only set in the backend-
        // fetch branch below, which left deviceId='' for fresh scans
        // coming from analyzing.tsx. That broke /generate-reply and
        // any other POST that includes device_id in the body (404
        // "Analysis not found" because Mongo filter {device_id: ""}
        // never matched).
        setDeviceId(await ensureDeviceId());
        setRecord(cached);
        setLoading(false);
        await refreshReminders(cached.id);
        setOriginalSaved(await hasOriginal(cached.id));
        return;
      }
      if (!id) {
        setLoading(false);
        return;
      }
      try {
        const did = await ensureDeviceId();
        setDeviceId(did);
        const r = await getAnalysis(id, did);
        setLastResult(r);
        setRecord(r);
        await refreshReminders(r.id);
        setOriginalSaved(await hasOriginal(r.id));
      } catch {
        setRecord(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [id, refreshReminders]);

  // When returning from the reminder modal, refresh the reminders list.
  useFocusEffect(
    useCallback(() => {
      if (record?.id) {
        refreshReminders(record.id);
      }
    }, [record?.id, refreshReminders])
  );

  // ---- "Change language" derived state & handler. Must be declared
  // before any conditional return so React's rules of hooks stay satisfied
  // across the loading / null-record / render paths. We gate every deref
  // on `record` being present; when it's null the memoized values are
  // harmless no-ops.
  const primaryCode = (record?.target_language ?? 'en') as LanguageCode;
  const availableLangs = useMemo<Set<LanguageCode>>(() => {
    const s = new Set<LanguageCode>([primaryCode]);
    if (record?.translations) {
      for (const k of Object.keys(record.translations)) {
        s.add(k as LanguageCode);
      }
    }
    return s;
  }, [record?.translations, primaryCode]);

  const onPickLanguage = useCallback(async (targetCode: LanguageCode) => {
    if (!record) return;
    setTranslateError(null);
    const effective = displayLang ?? primaryCode;

    // Already the active view — just close.
    if (targetCode === effective) {
      setSheetOpen(false);
      return;
    }

    // Cached (either primary or already translated) → instant switch.
    if (availableLangs.has(targetCode)) {
      setDisplayLang(targetCode);
      setSheetOpen(false);
      return;
    }

    // Miss — call backend, show loading, update record + switch on success.
    setTranslating(true);
    setSheetOpen(false);
    try {
      const did = await ensureDeviceId();
      const updated = await translateAnalysis(record.id, did, targetCode);
      const newRecord: AnalysisRecord = {
        ...record,
        translations: {
          ...(record.translations || {}),
          ...(updated.translations || {}),
        },
      };
      setRecord(newRecord);
      setLastResult(newRecord);
      setDisplayLang(targetCode);
    } catch (_e) {
      // Privacy: don't echo raw server error. Show the friendly i18n string.
      setTranslateError(t(lang, 'translation_error'));
    } finally {
      setTranslating(false);
    }
  }, [record, displayLang, primaryCode, availableLangs, lang]);

  const onOpenSheet = useCallback(() => {
    setTranslateError(null);
    setSheetOpen(true);
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator color={colors.primary} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  if (!record) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.loadingWrap}>
          <Text style={styles.errorText}>{t(lang, 'error_generic')}</Text>
          <Button label={t(lang, 'back')} onPress={() => router.replace('/home')} />
        </View>
      </SafeAreaView>
    );
  }

  // Resolve which language version to show. Default to the record's
  // primary language if the user hasn't switched yet.
  const effectiveDisplayLang: LanguageCode = displayLang ?? primaryCode;
  const r = (
    effectiveDisplayLang === primaryCode
      ? record.result
      : record.translations?.[effectiveDisplayLang] ?? record.result
  );
  const risk = riskMeta(r.risk_level, lang);
  // Phase-3 (multi-source-language): prefer `reply_draft` (any source
  // language), fall back to legacy `german_reply_draft` for older records.
  const replyDraftText = (r as any).reply_draft || r.german_reply_draft || '';

  const copyReply = async () => {
    if (!replyDraftText) return;
    try {
      await Clipboard.setStringAsync(replyDraftText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  const onDelete = () => {
    Alert.alert(t(lang, 'confirm_delete_one'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          const did = await ensureDeviceId();
          try {
            await deleteAnalysis(record.id, did);
            await cancelAllForAnalysis(record.id);
            await deleteOriginal(record.id);
            setLastResult(null);
            router.replace('/home');
          } catch (e: any) {
            Alert.alert(t(lang, 'error_generic'), e?.message || '');
          }
        },
      },
    ]);
  };

  const onShare = () => {
    Alert.alert(
      t(lang, 'share'),
      undefined,
      [
        { text: t(lang, 'share_as_pdf'), onPress: () => shareAnalysisAsPdf(record, lang) },
        { text: t(lang, 'share_as_text'), onPress: () => shareAnalysisAsText(record, lang) },
        { text: t(lang, 'cancel'), style: 'cancel' },
      ],
      { cancelable: true },
    );
  };


  // ---- Per-analysis derived state ----
  const heroPalette = risk.palette;
  const hasActions = (r.required_actions?.length ?? 0) > 0;
  const hasDeadlines = (r.deadlines?.length ?? 0) > 0;
  const hasScam = !!r.scam_warning;
  const hasReplyDraft = !!replyDraftText;
  const hasQuestions = (r.questions_to_ask?.length ?? 0) > 0;
  const hasUncertainties = (r.uncertainties?.length ?? 0) > 0;
  const hasKeyPoints = (r.key_points?.length ?? 0) > 0;
  const hasSenderText = !!(r.sender && r.sender.trim());
  // Phase EU-1: Resolve language metadata once. Falls back gracefully for
  // legacy records (no source_language_code, no detected_country_code) so
  // old history items still render.
  const langCtx = (() => {
    const rr = r as any;
    const srcCode = (rr.source_language_code || '').toLowerCase();
    const replyCode = (rr.suggested_reply_language_code || srcCode || '').toLowerCase();
    const targetCode = (record?.target_language || '').toLowerCase();
    const countryCode = (rr.detected_country_code || '').toUpperCase();
    const countryName = rr.detected_country_name || '';
    return {
      srcCode,
      srcLabel:
        formatLanguageLabel(srcCode) ||
        (rr.source_language && rr.source_language.trim()) ||
        '',
      srcFlag: getAnyLanguage(srcCode)?.flag || '',
      replyCode,
      replyLabel: formatLanguageLabel(replyCode) || '',
      replyFlag: getAnyLanguage(replyCode)?.flag || '',
      targetCode,
      targetLabel: formatLanguageLabel(targetCode) || '',
      targetFlag: getAnyLanguage(targetCode)?.flag || '',
      countryCode,
      countryName,
      countryFlag: countryCodeToFlag(countryCode),
      jurisdictionConfidence: (rr.jurisdiction_confidence || '') as
        | '' | 'low' | 'medium' | 'high',
      replyEqualsSrc: replyCode === srcCode && !!srcCode,
      explainEqualsSrc: targetCode === srcCode && !!srcCode,
    };
  })();
  const sourceLangLabel = langCtx.srcLabel;
  const hasSourceLang = !!sourceLangLabel;
  // Tab definitions for Phase R3. We only render a pill for tabs that have
  // content (e.g. the Reply pill is hidden when the document doesn't need
  // a reply). The Overview tab is always present.
  type TabKey = 'overview' | 'actions' | 'deadlines' | 'reply' | 'details';
  const availableTabs: { key: TabKey; label: string; count?: number }[] = [
    { key: 'overview', label: t(lang, 'tab_overview') },
    ...(hasActions
      ? [{ key: 'actions' as TabKey, label: t(lang, 'tab_actions'), count: r.required_actions!.length }]
      : []),
    ...(hasDeadlines
      ? [{ key: 'deadlines' as TabKey, label: t(lang, 'deadlines'), count: r.deadlines!.length }]
      : []),
    ...(hasReplyDraft || (r.reply_options && r.reply_options.length > 0)
      ? [{ key: 'reply' as TabKey, label: t(lang, 'tab_reply') }]
      : []),
    { key: 'details' as TabKey, label: t(lang, 'tab_details') },
  ];
  // If the active tab is no longer available (e.g. after a language switch
  // that wiped the reply_draft), fall back gracefully.
  const safeActiveTab: TabKey =
    availableTabs.some((t) => t.key === activeTab) ? activeTab : 'overview';
  const mainAct = pickMainAction(r);
  const replyNeeded = replyRequired(r);
  const importantUncertainty = hasImportantUncertainty(r);

  // First non-past deadline (used by the sticky-bar "Add reminder" button)
  const firstFutureDeadline = (() => {
    const idx = (r.deadlines || []).findIndex((d) => {
      const p = tryParseDeadlineDate(d.date || '');
      return p && p.getTime() >= Date.now() - 86400000;
    });
    if (idx < 0) return null;
    const d = r.deadlines![idx];
    const parsed = tryParseDeadlineDate(d.date || '');
    return parsed ? { idx, d, parsed } : null;
  })();

  // Smart accordion defaults — calm, scannable, no overwhelming open list.
  // User toggles override these via openSections[id].
  const isOpen = (id: string, fallback: boolean): boolean =>
    openSections[id] === undefined ? fallback : openSections[id];

  // Sticky action: jump to reminder picker for the soonest deadline.
  const onStickyRemind = () => {
    if (!firstFutureDeadline) return;
    router.push({
      pathname: '/reminder',
      params: {
        analysisId: record.id,
        deadlineKey: deadlineKeyFor(firstFutureDeadline.idx, firstFutureDeadline.d),
        deadlineIso: firstFutureDeadline.parsed.toISOString(),
        description: firstFutureDeadline.d.description || '',
      },
    });
  };

  return (
    <SafeAreaView style={styles.safe} testID="result-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.replace('/home')} testID="result-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {r.document_type || t(lang, 'other_document')}
        </Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          {originalSaved ? (
            <Pressable
              onPress={() => router.push(`/original?id=${encodeURIComponent(record.id)}`)}
              testID="result-view-original"
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel={t(lang, 'view_original')}
            >
              <Eye color={colors.primary} size={22} strokeWidth={2.4} />
            </Pressable>
          ) : null}
          <Pressable
            onPress={onDelete}
            testID="result-delete"
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={t(lang, 'delete')}
          >
            <Trash2 color={colors.textSecondary} size={22} strokeWidth={2.2} />
          </Pressable>
        </View>
      </View>

      {/* Change-language control. Visible right under the header so users who
          picked the wrong language during scan can fix it without going back
          to the main menu. Shows the current DISPLAY language (which may
          differ from the analysis's primary language once the user switches).
          Tap → bottom sheet with all 7 supported languages.
          NOTE: Pressable extends full width for an easy tap target; we use
          a pill inside for visual containment. */}
      <Pressable
        onPress={onOpenSheet}
        style={styles.langSwitchRow}
        testID="change-language-button"
        accessibilityRole="button"
        accessibilityLabel={t(lang, 'change_language')}
        hitSlop={6}
      >
        <View style={styles.langSwitchPill}>
          <Globe size={16} color={colors.primary} strokeWidth={2.2} />
          <Text style={styles.langSwitchCurrent} numberOfLines={1}>
            {formatLanguageLabel(effectiveDisplayLang, effectiveDisplayLang)}
          </Text>
          <Text style={styles.langSwitchHint}>· {t(lang, 'change_language')}</Text>
          <ChevronDown size={14} color={colors.textSecondary} strokeWidth={2.2} />
        </View>
      </Pressable>

      {/* Language-picker modal. Full-screen translucent overlay with a
          centred card so it looks consistent on iOS & Android without
          a native bottom-sheet lib. Each item shows native label AND a
          tiny "⚡ cached" marker when the translation is already stored
          locally — that way power users can tell which switches will
          be instant vs. which trigger a round-trip. */}
      <Modal
        visible={sheetOpen}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setSheetOpen(false)}
      >
        <Pressable
          style={styles.modalBackdrop}
          onPress={() => setSheetOpen(false)}
          accessible={false}
        >
          {/* Inner Pressable swallows taps so tapping the card doesn't close. */}
          <Pressable style={styles.modalCard} onPress={() => {}}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {t(lang, 'translation_sheet_title')}
              </Text>
              <Pressable
                onPress={() => setSheetOpen(false)}
                hitSlop={10}
                accessibilityRole="button"
                accessibilityLabel={t(lang, 'back')}
              >
                <X size={22} color={colors.textSecondary} strokeWidth={2.2} />
              </Pressable>
            </View>
            <ScrollView
              style={{ maxHeight: 480, marginTop: spacing.xs }}
              showsVerticalScrollIndicator
              contentContainerStyle={{ paddingBottom: spacing.xs }}
            >
              {EXPLANATION_LANGUAGES.map(opt => {
                const isActive = opt.code.toLowerCase() === (effectiveDisplayLang || '').toLowerCase();
                const isCached = availableLangs.has(opt.code as LanguageCode);
                return (
                  <Pressable
                    key={opt.code}
                    onPress={() => onPickLanguage(opt.code as LanguageCode)}
                    style={({ pressed }) => [
                      styles.modalRow,
                      pressed && { backgroundColor: colors.borderLight },
                      isActive && { backgroundColor: colors.primarySoft },
                    ]}
                    testID={`lang-option-${opt.code}`}
                    accessibilityRole="button"
                    accessibilityState={{ selected: isActive }}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={styles.modalRowTitle} numberOfLines={1}>
                        {opt.flag} {opt.nativeName}
                      </Text>
                      {opt.englishName && opt.englishName !== opt.nativeName ? (
                        <Text style={styles.modalRowSub} numberOfLines={1}>
                          {opt.englishName}
                        </Text>
                      ) : null}
                    </View>
                    {isActive ? (
                      <Check size={20} color={colors.primary} strokeWidth={2.6} />
                    ) : isCached ? (
                      <Text style={styles.modalRowCached}>⚡</Text>
                    ) : null}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>

      {/* Translating overlay — shown while the backend generates a new
          localisation. Non-dismissable to prevent the user firing multiple
          concurrent requests. The backend call typically takes 3-20s. */}
      {translating ? (
        <View style={styles.translatingOverlay} pointerEvents="auto">
          <View style={styles.translatingCard}>
            <ActivityIndicator color={colors.primary} size="large" />
            <Text style={styles.translatingText}>
              {t(lang, 'translating_subtitle')}
            </Text>
          </View>
        </View>
      ) : null}

      {/* Inline translate-error pill — non-blocking. Lives below the
          language-switch row so users see it next to the control that
          triggered it. Auto-dismisses on next successful switch. */}
      {translateError ? (
        <View style={styles.translateErrorBanner}>
          <AlertTriangle size={16} color="#B91C1C" strokeWidth={2.4} />
          <Text style={styles.translateErrorText}>{translateError}</Text>
        </View>
      ) : null}

      {/* Auto-pop scam-warning modal — visible once per analysis the first time
          the user lands here. Tone is calm, not panic-inducing. */}
      <ScamWarningModal
        analysisId={hasScam ? record.id : null}
        reason={hasScam ? (r.scam_reason || t(lang, 'scam_warning_body')) : ''}
        lang={lang}
      />

      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Save-status banner — shown for ~4 seconds after a fresh analysis
            when the user has the "Save originals" toggle on. Gives instant
            visible confirmation that local storage actually worked (or
            failed). Auto-clears via setTimeout in the load effect. */}
        {saveBanner ? (
          <View
            style={[
              styles.saveBanner,
              saveBanner === 'ok' ? styles.saveBannerOk : styles.saveBannerFail,
            ]}
            testID={`save-banner-${saveBanner}`}
          >
            {saveBanner === 'ok' ? (
              <CheckCircle2 color={colors.green.text} size={18} strokeWidth={2.4} />
            ) : (
              <AlertTriangle color={colors.red.text} size={18} strokeWidth={2.4} />
            )}
            <Text
              style={[
                styles.saveBannerText,
                saveBanner === 'ok' ? styles.saveBannerTextOk : styles.saveBannerTextFail,
              ]}
            >
              {t(lang, saveBanner === 'ok' ? 'saved_to_device' : 'saved_to_device_failed')}
            </Text>
          </View>
        ) : null}

        {/* ============================================================
            0. LANGUAGE CONTEXT STRIP (Phase EU-1)
            Shows: source language + country (if detected) + explanation
            language + reply language. Only renders when at least the
            source language is known. Calm, single-line, scrollable on
            very narrow screens.
            ============================================================ */}
        {hasSourceLang ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.langStripRow}
            testID="result-lang-strip"
          >
            <View style={styles.langChip} testID="result-lang-chip-source">
              <Text style={styles.langChipKicker} numberOfLines={1}>
                {t(lang, 'source_language_detected')}
              </Text>
              <Text style={styles.langChipValue} numberOfLines={1}>
                {langCtx.srcFlag ? langCtx.srcFlag + ' ' : ''}
                {langCtx.srcLabel}
                {langCtx.countryFlag && langCtx.countryName
                  ? '  ·  ' + langCtx.countryFlag + ' ' + langCtx.countryName
                  : langCtx.countryFlag
                  ? '  ·  ' + langCtx.countryFlag
                  : ''}
              </Text>
            </View>
            {/* Explanation language only when different from source */}
            {!langCtx.explainEqualsSrc && langCtx.targetLabel ? (
              <View style={styles.langChip} testID="result-lang-chip-target">
                <Text style={styles.langChipKicker} numberOfLines={1}>
                  {t(lang, 'lang_explained_in')}
                </Text>
                <Text style={styles.langChipValue} numberOfLines={1}>
                  {langCtx.targetFlag ? langCtx.targetFlag + ' ' : ''}
                  {langCtx.targetLabel}
                </Text>
              </View>
            ) : null}
            {/* Reply language only when different from source — when same we
                imply "reply in the sender's language" via the strip layout */}
            {!langCtx.replyEqualsSrc && langCtx.replyLabel ? (
              <View style={styles.langChip} testID="result-lang-chip-reply">
                <Text style={styles.langChipKicker} numberOfLines={1}>
                  {t(lang, 'lang_reply_in')}
                </Text>
                <Text style={styles.langChipValue} numberOfLines={1}>
                  {langCtx.replyFlag ? langCtx.replyFlag + ' ' : ''}
                  {langCtx.replyLabel}
                </Text>
              </View>
            ) : null}
            {/* Soft "country unclear" hint only when we have source lang but
                no jurisdiction. Stays calm, never alarms. */}
            {!langCtx.countryCode && !langCtx.explainEqualsSrc ? (
              <View
                style={[styles.langChip, styles.langChipMuted]}
                testID="result-lang-chip-country-unclear"
              >
                <Text style={styles.langChipKicker} numberOfLines={1}>
                  {t(lang, 'lang_country_label')}
                </Text>
                <Text style={styles.langChipValueMuted} numberOfLines={1}>
                  {t(lang, 'lang_country_unclear')}
                </Text>
              </View>
            ) : null}
          </ScrollView>
        ) : null}

        {/* ============================================================
            1. RISK HERO
            ============================================================ */}
        <View
          style={[
            styles.heroCard,
            { backgroundColor: heroPalette.bg, borderColor: heroPalette.border },
          ]}
          testID={`risk-card-${r.risk_level}`}
        >
          <View style={styles.heroTopRow}>
            <View style={[styles.heroIconWrap, { backgroundColor: 'rgba(255,255,255,0.85)' }]}>
              {risk.icon}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.heroKicker, { color: heroPalette.text }]}>
                {t(lang, 'risk_level')}
              </Text>
              <Text style={[styles.heroTitle, { color: heroPalette.text }]} numberOfLines={3}>
                {risk.label}
              </Text>
            </View>
          </View>
          <Text style={[styles.heroBody, { color: heroPalette.text }]}>
            {r.risk_reason || t(lang, 'urgency_unknown')}
          </Text>
          <View style={styles.heroChipsRow}>
            {r.category ? (
              <View style={styles.heroChip} testID="result-category-pill">
                <Text style={[styles.heroChipText, { color: heroPalette.text }]}>
                  {categoryLabel(lang, r.category)}
                </Text>
              </View>
            ) : (
              <View style={styles.heroChip}>
                <Text style={[styles.heroChipText, { color: heroPalette.text }]}>
                  {t(lang, 'other_document')}
                </Text>
              </View>
            )}
            <View style={styles.heroChip}>
              <Building2 color={heroPalette.text} size={12} strokeWidth={2.5} />
              <Text
                style={[styles.heroChipText, { color: heroPalette.text }]}
                numberOfLines={1}
              >
                {hasSenderText ? r.sender : t(lang, 'sender_unknown')}
              </Text>
            </View>
          </View>
          {/* Calm reassurance line — keeps the emotional message warm */}
          <Text style={[styles.heroReassurance, { color: heroPalette.text }]}>
            {t(lang, 'not_alone')}
          </Text>
        </View>

        {/* ============================================================
            1b. SAFETY DISCLAIMER (Phase EU-1)
            Only renders for high-risk legal/court/immigration/debt
            documents where Mistral added a calm professional-help hint.
            Soft amber tint, never alarming.
            ============================================================ */}
        {((r as any).safety_disclaimer || '').trim() ? (
          <View
            style={styles.safetyDisclaimerCard}
            testID="result-safety-disclaimer"
          >
            <ShieldAlert
              color={colors.yellow.text}
              size={18}
              strokeWidth={2.2}
            />
            <Text style={styles.safetyDisclaimerText}>
              {(r as any).safety_disclaimer}
            </Text>
          </View>
        ) : null}

        {/* ============================================================
            2. MAIN ACTION CARD — single most-important thing
            ============================================================ */}
        {mainAct ? (
          <View style={styles.mainActionCard} testID="main-action-card">
            <View style={styles.mainActionHeader}>
              <View style={styles.mainActionIcon}>
                {mainAct.kind === 'deadline' ? (
                  <CalendarClock color={colors.white} size={20} strokeWidth={2.6} />
                ) : (
                  <ListTodo color={colors.white} size={20} strokeWidth={2.6} />
                )}
              </View>
              <Text style={styles.mainActionKicker}>{t(lang, 'main_action_title')}</Text>
            </View>
            {mainAct.kind === 'deadline' ? (
              <>
                <Text style={styles.mainActionTitle} numberOfLines={3}>
                  {mainAct.requiresResponse ? t(lang, 'respond_by') : t(lang, 'act_by')}{' '}
                  {mainAct.raw}
                </Text>
                <View style={styles.mainActionMetaRow}>
                  <View style={styles.mainActionDaysPill}>
                    <Text style={styles.mainActionDaysText}>
                      {formatRelativeDays(mainAct.days, lang)}
                    </Text>
                  </View>
                  {mainAct.description ? (
                    <Text style={styles.mainActionMeta} numberOfLines={3}>
                      {mainAct.description}
                    </Text>
                  ) : null}
                </View>
                <Text style={styles.mainActionVerify}>{t(lang, 'verify_in_original')}</Text>
              </>
            ) : (
              <>
                <Text style={styles.mainActionTitle} numberOfLines={3}>
                  {mainAct.action}
                </Text>
                {mainAct.reason ? (
                  <Text style={styles.mainActionMeta}>{mainAct.reason}</Text>
                ) : null}
              </>
            )}
          </View>
        ) : null}

        {/* ============================================================
            PILLS / TABS — Phase R3 redesign
            Single horizontal bar that filters which sections render below.
            ============================================================ */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.pillsRow}
          testID="result-tabs"
        >
          {availableTabs.map((tabDef) => {
            const isActive = tabDef.key === safeActiveTab;
            return (
              <Pressable
                key={tabDef.key}
                onPress={() => setActiveTab(tabDef.key)}
                style={({ pressed }) => [
                  styles.pill,
                  isActive && styles.pillActive,
                  pressed && !isActive && { opacity: 0.7 },
                ]}
                testID={`result-tab-${tabDef.key}`}
                accessibilityRole="tab"
                accessibilityState={{ selected: isActive }}
              >
                <Text style={[styles.pillText, isActive && styles.pillTextActive]}>
                  {tabDef.label}
                </Text>
                {typeof tabDef.count === 'number' && tabDef.count > 0 ? (
                  <View style={[styles.pillBadge, isActive && styles.pillBadgeActive]}>
                    <Text
                      style={[styles.pillBadgeText, isActive && styles.pillBadgeTextActive]}
                    >
                      {tabDef.count}
                    </Text>
                  </View>
                ) : null}
              </Pressable>
            );
          })}
        </ScrollView>

        {/* ============================================================
            3. SCAM WARNING (always visible — security overrides tabs)
            ============================================================ */}
        {hasScam ? (
          <View style={styles.scamCard} testID="scam-warning-card">
            <View style={styles.scamRow}>
              <View style={styles.scamIcon}>
                <ShieldAlert color={colors.red.text} size={26} strokeWidth={2.4} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.scamTitle}>{t(lang, 'scam_warning_title')}</Text>
                <Text style={styles.scamBody}>
                  {r.scam_reason || t(lang, 'scam_warning_body')}
                </Text>
                <Text style={[styles.scamBody, { marginTop: 8, fontWeight: fontWeight.bold }]}>
                  {t(lang, 'scam_caution_body')}
                </Text>
              </View>
            </View>
          </View>
        ) : null}

        {/* === Section 4: SUMMARY — Overview tab === */}
        {safeActiveTab === 'overview' && (r.simple_explanation_translated || r.summary_translated) ? (
          <Accordion
            id="summary"
            title={t(lang, 'what_this_means')}
            icon={<Info color={colors.primary} size={18} strokeWidth={2.5} />}
            open={isOpen('summary', true)}
            onToggle={toggleSection}
            testID="summary-card"
          >
            {r.simple_explanation_translated ? (
              <View style={{ marginBottom: spacing.sm }}>
                <ReadAloudButton
                  text={r.simple_explanation_translated}
                  lang={lang}
                  testID="read-aloud-explanation"
                />
              </View>
            ) : null}
            <Text style={styles.body}>
              {r.simple_explanation_translated || r.summary_translated}
            </Text>
          </Accordion>
        ) : null}

        {/* === Section 5: ACTIONS — Actions tab === */}
        {safeActiveTab === 'actions' && hasActions ? (
          <Accordion
            id="actions"
            title={t(lang, 'what_to_do_next')}
            icon={<ListTodo color={colors.primary} size={18} strokeWidth={2.5} />}
            open={isOpen('actions', true)}
            onToggle={toggleSection}
            testID="actions-card"
          >
            <View style={{ gap: spacing.sm }}>
              {r.required_actions!.map((a, i) => (
                <View key={i} style={styles.actionItem}>
                  <View
                    style={[
                      styles.actionUrgency,
                      a.urgency === 'high' && { backgroundColor: colors.red.solid },
                      a.urgency === 'medium' && { backgroundColor: colors.yellow.solid },
                      a.urgency === 'low' && { backgroundColor: colors.green.solid },
                    ]}
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.actionTitle}>{a.action}</Text>
                    {a.reason ? <Text style={styles.actionReason}>{a.reason}</Text> : null}
                  </View>
                </View>
              ))}
            </View>
          </Accordion>
        ) : null}

        {/* === Section 6: DEADLINES — Deadlines tab === */}
        {safeActiveTab === 'deadlines' && hasDeadlines ? (
          <View style={styles.pyramidCard} testID="deadlines-card">
            <SectionRow
              icon={<CalendarClock color={colors.primary} size={18} strokeWidth={2.5} />}
              title={t(lang, 'deadlines')}
            />
            <View style={{ gap: spacing.sm }}>
              {r.deadlines!.map((d, i) => {
                const key = deadlineKeyFor(i, d);
                const existing = reminders.find((rm) => rm.deadlineKey === key);
                const parsed = tryParseDeadlineDate(d.date);
                const isPast = parsed ? parsed.getTime() < Date.now() : false;
                const days = parsed ? daysUntil(parsed) : null;
                const onToggleReminder = () => {
                  if (existing) {
                    Alert.alert(t(lang, 'cancel_reminder'), '', [
                      { text: t(lang, 'cancel'), style: 'cancel' },
                      {
                        text: t(lang, 'delete'),
                        style: 'destructive',
                        onPress: async () => {
                          await cancelReminder(record.id, key);
                          await refreshReminders(record.id);
                        },
                      },
                    ]);
                    return;
                  }
                  if (isPast) {
                    Alert.alert(t(lang, 'past_deadline'));
                    return;
                  }
                  router.push({
                    pathname: '/reminder',
                    params: {
                      analysisId: record.id,
                      deadlineKey: key,
                      deadlineIso: parsed ? parsed.toISOString() : '',
                      description: d.description || '',
                    },
                  });
                };
                return (
                  <View key={i} style={styles.deadlineItem}>
                    <View style={styles.deadlineDateChip}>
                      <Text style={styles.deadlineDate}>{d.date || '—'}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.deadlineDesc}>{d.description}</Text>
                      <View
                        style={{
                          flexDirection: 'row',
                          alignItems: 'center',
                          gap: 8,
                          marginTop: 6,
                          flexWrap: 'wrap',
                        }}
                      >
                        {days !== null ? (
                          <View
                            style={[
                              styles.daysPill,
                              days < 0 && { backgroundColor: colors.red.bg },
                            ]}
                          >
                            <Text
                              style={[
                                styles.daysPillText,
                                days < 0 && { color: colors.red.text },
                              ]}
                            >
                              {formatRelativeDays(days, lang)}
                            </Text>
                          </View>
                        ) : null}
                        <Pressable
                          onPress={onToggleReminder}
                          style={[
                            styles.reminderBtn,
                            existing && {
                              backgroundColor: colors.green.bg,
                              borderColor: colors.green.border,
                            },
                          ]}
                          testID={`reminder-toggle-${i}`}
                          accessibilityRole="button"
                          accessibilityLabel={
                            existing ? t(lang, 'reminder_set') : t(lang, 'remind_me')
                          }
                        >
                          {existing ? (
                            <BellRing color={colors.green.text} size={14} strokeWidth={2.5} />
                          ) : (
                            <Bell color={colors.primary} size={14} strokeWidth={2.5} />
                          )}
                          <Text
                            style={[
                              styles.reminderBtnLabel,
                              existing && { color: colors.green.text },
                            ]}
                          >
                            {existing ? t(lang, 'reminder_set') : t(lang, 'remind_me')}
                          </Text>
                          {existing ? (
                            <XCircle color={colors.green.text} size={14} strokeWidth={2.4} />
                          ) : null}
                        </Pressable>
                      </View>
                    </View>
                  </View>
                );
              })}
            </View>
            <Text style={styles.verifyNote}>{t(lang, 'verify_in_original')}</Text>
          </View>
        ) : null}

        {/* ============================================================
            7. REPLY DRAFT — auto-open ONLY if a reply is needed AND not scam
            ============================================================ */}
        {/* === Section 7: REPLY ASSISTANT (Phase R5) === */}
        {safeActiveTab === 'reply' && (hasReplyDraft || (r.reply_options && r.reply_options.length > 0)) ? (
          <View style={styles.replyTabWrapper} testID="reply-card">
            {hasScam ? (
              <View style={styles.scamInlineCaution}>
                <ShieldAlert color={colors.red.text} size={16} strokeWidth={2.5} />
                <Text style={styles.scamInlineCautionText}>
                  {t(lang, 'scam_contact_caution')}
                </Text>
              </View>
            ) : null}
            <ReplyAssistant
              record={record}
              uiLang={lang}
              options={r.reply_options || []}
              entities={r.extracted_entities || {}}
              legacyReplyDraft={replyDraftText}
              sourceLanguageLabel={sourceLangLabel}
              suggestedReplyLanguageCode={langCtx.replyCode}
              deviceId={deviceId}
            />
          </View>
        ) : null}

        {/* === Section 8: QUESTIONS — Details tab === */}
        {safeActiveTab === 'details' && hasQuestions ? (
          <Accordion
            id="questions"
            title={t(lang, 'questions_to_ask')}
            icon={<HelpCircle color={colors.primary} size={18} strokeWidth={2.5} />}
            open={isOpen('questions', false)}
            onToggle={toggleSection}
            testID="questions-card"
          >
            <View style={{ gap: 8 }}>
              {r.questions_to_ask!.map((q, i) => (
                <View key={i} style={styles.bullet}>
                  <View style={[styles.bulletDot, { backgroundColor: colors.primary }]} />
                  <Text style={styles.bulletText}>{q}</Text>
                </View>
              ))}
            </View>
          </Accordion>
        ) : null}

        {/* === Section 9: DETAILS — Details tab === */}
        {safeActiveTab === 'details' && (hasKeyPoints || hasSenderText || r.document_type) ? (
          <Accordion
            id="details"
            title={t(lang, 'key_points_title')}
            icon={<FileText color={colors.primary} size={18} strokeWidth={2.5} />}
            open={isOpen('details', false)}
            onToggle={toggleSection}
            testID="details-card"
          >
            <View style={styles.kvRow}>
              <Text style={styles.kvKey}>{t(lang, 'sender')}</Text>
              <Text style={styles.kvValue} numberOfLines={2}>
                {hasSenderText ? r.sender : t(lang, 'sender_unknown')}
              </Text>
            </View>
            <View style={styles.kvRow}>
              <Text style={styles.kvKey}>{t(lang, 'document_type')}</Text>
              <Text style={styles.kvValue} numberOfLines={2}>
                {r.document_type || t(lang, 'other_document')}
              </Text>
            </View>
            {hasSourceLang ? (
              <View style={styles.kvRow}>
                <Text style={styles.kvKey}>{t(lang, 'source_language_detected')}</Text>
                <Text style={styles.kvValue} numberOfLines={1}>
                  {sourceLangLabel}
                </Text>
              </View>
            ) : null}
            {hasKeyPoints ? (
              <View style={{ gap: 8, marginTop: spacing.sm }}>
                {r.key_points!.map((kp, i) => (
                  <View key={i} style={styles.bullet}>
                    <View style={styles.bulletDot} />
                    <Text style={styles.bulletText}>{kp}</Text>
                  </View>
                ))}
              </View>
            ) : null}
          </Accordion>
        ) : null}

        {/* === Section 10: UNCERTAINTIES — Details tab === */}
        {safeActiveTab === 'details' && hasUncertainties ? (
          <Accordion
            id="uncertainties"
            title={t(lang, 'double_check')}
            icon={<AlertTriangle color={colors.yellow.text} size={18} strokeWidth={2.5} />}
            open={isOpen('uncertainties', hasScam || importantUncertainty)}
            onToggle={toggleSection}
            testID="uncertainties-card"
          >
            <View style={{ gap: 8 }}>
              {r.uncertainties!.map((u, i) => (
                <View key={i} style={styles.bullet}>
                  <View style={[styles.bulletDot, { backgroundColor: colors.yellow.solid }]} />
                  <Text style={styles.bulletText}>{u}</Text>
                </View>
              ))}
            </View>
          </Accordion>
        ) : null}

        {/* ============================================================
            DISCLAIMER
            ============================================================ */}
        <View style={styles.disclaimer} testID="disclaimer-card">
          <FileText color={colors.textSecondary} size={16} strokeWidth={2.4} />
          <Text style={styles.disclaimerText}>{r.disclaimer}</Text>
        </View>

        {/* Spacer for sticky bar */}
        <View style={{ height: spacing.xl + 56 }} />
      </ScrollView>

      {/* ============================================================
          STICKY ACTION BAR — Ask KlarPost (primary), Share, Reminder
          ============================================================ */}
      <View style={styles.stickyBar} testID="sticky-action-bar">
        <Pressable
          onPress={onShare}
          style={styles.stickyIconBtn}
          accessibilityRole="button"
          accessibilityLabel={t(lang, 'share')}
          testID="sticky-share"
        >
          <Share2 color={colors.primary} size={20} strokeWidth={2.5} />
        </Pressable>
        {firstFutureDeadline ? (
          <Pressable
            onPress={onStickyRemind}
            style={styles.stickyIconBtn}
            accessibilityRole="button"
            accessibilityLabel={t(lang, 'remind_me')}
            testID="sticky-reminder"
          >
            <Bell color={colors.primary} size={20} strokeWidth={2.5} />
          </Pressable>
        ) : null}
        <Pressable
          onPress={() =>
            router.push(
              `/chat?id=${encodeURIComponent(record.id)}&lang=${encodeURIComponent(effectiveDisplayLang)}`,
            )
          }
          style={styles.stickyAskBtn}
          accessibilityRole="button"
          accessibilityLabel={t(lang, 'ask_question')}
          testID="sticky-ask"
        >
          <MessageCircle color={colors.white} size={18} strokeWidth={2.6} />
          <Text style={styles.stickyAskLabel}>{t(lang, 'ask_question')}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}


function SectionRow({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <View style={styles.sectionIcon}>{icon}</View>
      <SectionTitle>{title}</SectionTitle>
    </View>
  );
}

// Accordion: collapsible card. Header is fully tappable (44pt min target).
// Animated chevron rotates on toggle for clear affordance.
function Accordion({
  id,
  title,
  icon,
  open,
  onToggle,
  testID,
  children,
}: {
  id: string;
  title: string;
  icon: React.ReactNode;
  open: boolean;
  onToggle: (id: string, currentlyOpen: boolean) => void;
  testID?: string;
  children: React.ReactNode;
}) {
  const rotation = useRef(new Animated.Value(open ? 1 : 0)).current;

  useEffect(() => {
    Animated.timing(rotation, {
      toValue: open ? 1 : 0,
      duration: 220,
      easing: Easing.out(Easing.ease),
      useNativeDriver: true,
    }).start();
  }, [open, rotation]);

  const rotateInterpolate = rotation.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '180deg'],
  });

  return (
    <View style={styles.accordionCard} testID={testID}>
      <Pressable
        onPress={() => onToggle(id, open)}
        style={({ pressed }) => [styles.accordionHeader, pressed && { opacity: 0.7 }]}
        hitSlop={4}
        testID={testID ? `${testID}-header` : undefined}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={title}
      >
        <View style={styles.sectionIcon}>{icon}</View>
        <Text style={styles.accordionTitle} numberOfLines={2}>
          {title}
        </Text>
        <Animated.View style={{ transform: [{ rotate: rotateInterpolate }] }}>
          <ChevronDown color={colors.textSecondary} size={22} strokeWidth={2.4} />
        </Animated.View>
      </Pressable>
      {open ? <View style={styles.accordionBody}>{children}</View> : null}
    </View>
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
    gap: spacing.sm,
  },
  headerTitle: {
    flex: 1,
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },
  loadingWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  errorText: { fontSize: fontSize.base, color: colors.textSecondary, textAlign: 'center' },

  // ---- Save banner (shown briefly after analysis when "save originals" is on) ----
  saveBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  saveBannerOk: {
    backgroundColor: colors.green.bg,
    borderColor: colors.green.border,
  },
  saveBannerFail: {
    backgroundColor: colors.red.bg,
    borderColor: colors.red.border,
  },
  saveBannerText: {
    flex: 1,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  saveBannerTextOk: { color: colors.green.text },
  saveBannerTextFail: { color: colors.red.text },

  // ---- Risk Hero ----
  heroCard: {
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1.5,
    gap: spacing.md,
    ...shadows.card,
  },
  heroTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  heroIconWrap: {
    width: 64,
    height: 64,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroKicker: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    opacity: 0.85,
  },
  heroTitle: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.4,
    marginTop: 4,
    lineHeight: 30,
  },
  heroBody: {
    fontSize: fontSize.base,
    lineHeight: 23,
    fontWeight: fontWeight.medium,
  },
  heroChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  heroChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.7)',
    maxWidth: '100%',
  },
  heroChipText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    letterSpacing: 0.3,
  },
  heroReassurance: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    lineHeight: 20,
    opacity: 0.85,
    fontStyle: 'italic',
  },

  // ---- Phase EU-1: Language Context Strip ----
  langStripRow: {
    flexDirection: 'row',
    alignItems: 'stretch',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
  },
  langChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    minWidth: 110,
  },
  langChipMuted: {
    backgroundColor: colors.background,
    borderStyle: 'dashed',
  },
  langChipKicker: {
    fontSize: 10,
    fontWeight: fontWeight.medium,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 2,
  },
  langChipValue: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  langChipValueMuted: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.textSecondary,
    fontStyle: 'italic',
  },

  // ---- Phase EU-1: Safety disclaimer card (for high-risk legal docs) ----
  safetyDisclaimerCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.yellow.bg,
    borderWidth: 1,
    borderColor: colors.yellow.border,
  },
  safetyDisclaimerText: {
    flex: 1,
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.yellow.text,
    fontWeight: fontWeight.medium,
  },

  // ---- Main Action card (the single most-urgent thing) ----
  mainActionCard: {
    backgroundColor: colors.primary,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    gap: 10,
    ...shadows.card,
  },
  mainActionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  mainActionIcon: {
    width: 36,
    height: 36,
    borderRadius: radius.md,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  mainActionKicker: {
    color: colors.white,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    opacity: 0.9,
  },
  mainActionTitle: {
    color: colors.white,
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    lineHeight: 28,
    letterSpacing: -0.2,
  },
  mainActionMetaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 10,
  },
  mainActionDaysPill: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.full,
  },
  mainActionDaysText: {
    color: colors.white,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
  },
  mainActionMeta: {
    flex: 1,
    color: colors.white,
    fontSize: fontSize.sm,
    lineHeight: 20,
    opacity: 0.95,
  },
  mainActionVerify: {
    color: colors.white,
    fontSize: fontSize.xs,
    fontStyle: 'italic',
    opacity: 0.85,
    marginTop: 4,
  },

  // ---- Deadline countdown pill (inside deadlines card) ----
  daysPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
  },
  daysPillText: {
    color: colors.primary,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
  },
  verifyNote: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontStyle: 'italic',
    marginTop: spacing.xs,
  },

  // ---- Inline scam caution (inside Reply Draft when scam is present) ----
  scamInlineCaution: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: colors.red.bg,
    borderRadius: radius.md,
    padding: spacing.sm,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.red.border,
  },
  scamInlineCautionText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.red.text,
    fontWeight: fontWeight.semibold,
    lineHeight: 18,
  },

  // ---- Sticky Action Bar ----
  stickyBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    paddingBottom: spacing.lg,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    ...Platform.select({
      ios: {
        shadowColor: '#0F172A',
        shadowOffset: { width: 0, height: -4 },
        shadowOpacity: 0.06,
        shadowRadius: 12,
      },
      android: { elevation: 8 },
      default: {},
    }),
  },
  stickyIconBtn: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stickyAskBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    ...shadows.button,
  },
  stickyAskLabel: {
    color: colors.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    letterSpacing: 0.2,
  },

  // ---- Scam banner ----
  scamCard: {
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1.5,
    backgroundColor: colors.red.bg,
    borderColor: colors.red.border,
  },
  scamRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
  },
  scamIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.7)',
  },
  scamTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.red.text,
    marginBottom: 4,
  },
  scamBody: {
    fontSize: fontSize.sm,
    lineHeight: 20,
    color: colors.red.text,
  },

  // ---- Action Pyramid (always-visible cards) ----
  pyramidCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.md,
    ...shadows.card,
  },
  // Reply-tab wrapper (Phase R5). Holds the optional scam-caution banner
  // above the embedded ReplyAssistant component.
  replyTabWrapper: {
    gap: spacing.md,
  },

  // ---- Pills / Tabs (Phase R3) ----
  // Horizontal segmented control used to filter visible sections.
  pillsRow: {
    paddingVertical: spacing.sm,
    paddingHorizontal: 2,
    gap: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 36,
  },
  pillActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pillText: {
    fontSize: 14,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  pillTextActive: {
    color: colors.white,
  },
  pillBadge: {
    minWidth: 20,
    height: 20,
    paddingHorizontal: 6,
    borderRadius: 10,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pillBadgeActive: {
    backgroundColor: 'rgba(255,255,255,0.25)',
  },
  pillBadgeText: {
    fontSize: 11,
    fontWeight: fontWeight.bold,
    color: colors.primary,
    fontVariant: ['tabular-nums'],
  },
  pillBadgeTextActive: {
    color: colors.white,
  },

  // ---- Detail Accordions ----
  accordionCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    borderWidth: 1,
    borderColor: colors.borderLight,
    overflow: 'hidden',
    ...shadows.card,
  },
  accordionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    minHeight: 56, // ≥44pt touch target
  },
  accordionTitle: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    letterSpacing: -0.2,
  },
  accordionBody: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },

  // ---- Shared content styles ----
  body: {
    color: colors.textPrimary,
    fontSize: fontSize.lg,
    lineHeight: 26,
  },
  sectionIcon: {
    width: 30,
    height: 30,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bullet: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  bulletDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.textSecondary,
    marginTop: 10,
  },
  bulletText: {
    flex: 1,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  actionItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    backgroundColor: colors.background,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  actionUrgency: {
    width: 6,
    alignSelf: 'stretch',
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  actionTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  actionReason: {
    marginTop: 4,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  deadlineItem: {
    // Stack vertically: long date ranges like "2026-04-21 bis 2026-04-23"
    // would otherwise hog the row and squeeze the description into a 30 px
    // column where each glyph wrapped to its own line. Putting the date
    // chip above the description gives the body text the full card width.
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: spacing.xs,
    backgroundColor: colors.background,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  deadlineDateChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primarySoft,
    borderRadius: radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 6,
    maxWidth: '100%',
  },
  deadlineDate: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: fontWeight.bold,
  },
  deadlineDesc: {
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium,
    lineHeight: 22,
  },
  kvRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    paddingVertical: 6,
  },
  kvKey: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: fontWeight.semibold,
  },
  kvValue: {
    flex: 1,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium,
    textAlign: 'right',
  },
  replyBox: {
    backgroundColor: colors.background,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  replyText: {
    fontSize: fontSize.base,
    color: colors.textPrimary,
    lineHeight: 24,
  },
  copyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    alignSelf: 'flex-start',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
  },
  copyLabel: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
  },
  reminderBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.primarySoft,
  },
  reminderBtnLabel: {
    color: colors.primary,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
  },
  subSectionTitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: fontWeight.bold,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  disclaimer: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: colors.borderLight,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  disclaimerText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  // ---- Change-language control ----
  langSwitchRow: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
    alignItems: 'flex-start',
  },
  langSwitchPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: colors.borderLight,
    borderWidth: 1,
    borderColor: colors.border,
    maxWidth: '100%',
  },
  langSwitchCurrent: {
    fontSize: fontSize.sm,
    color: colors.textPrimary,
    fontWeight: fontWeight.semibold as any,
  },
  langSwitchHint: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  translateErrorBanner: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xs,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: '#FEF2F2',
    borderRadius: radius.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  translateErrorText: {
    color: '#991B1B',
    fontSize: fontSize.sm,
    flex: 1,
  },
  // ---- Language-picker modal ----
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
  },
  modalCard: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: spacing.lg,
    ...shadows.card,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  modalTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold as any,
    color: colors.textPrimary,
    flex: 1,
    marginRight: spacing.sm,
  },
  modalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: 14,
    borderRadius: radius.md,
    marginTop: 2,
    minHeight: 52,
  },
  modalRowTitle: {
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.semibold as any,
  },
  modalRowSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  modalRowCached: {
    fontSize: 16,
    color: colors.textSecondary,
    opacity: 0.6,
  },
  // ---- Translating overlay ----
  translatingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255,255,255,0.78)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 100,
  },
  translatingCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.xl,
    alignItems: 'center',
    ...shadows.card,
    gap: spacing.md,
    minWidth: 200,
  },
  translatingText: {
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium as any,
    textAlign: 'center',
  },
});
