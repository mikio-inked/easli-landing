// Result screen — renders the structured analysis as stacked cards.

import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Clipboard from 'expo-clipboard';
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  BellRing,
  Building2,
  CalendarClock,
  CheckCircle2,
  Copy,
  Eye,
  FileText,
  HelpCircle,
  Info,
  ListTodo,
  MessageCircle,
  Reply,
  RotateCcw,
  Share2,
  ShieldAlert,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react-native';
import { Badge, Button, Card, SectionTitle } from '../src/ui';
import {
  ensureDeviceId,
  getLastResult,
  setLastResult,
  getLanguage as getStoredLanguage,
} from '../src/store';
import { AnalysisRecord, deleteAnalysis, getAnalysis } from '../src/api';
import { LanguageCode, categoryLabel, t } from '../src/i18n';
import { shareAnalysisAsPdf, shareAnalysisAsText } from '../src/share';
import {
  cancelAllForAnalysis,
  cancelReminder,
  getReminders,
  ReminderRecord,
} from '../src/notifications';
import { deleteOriginal, hasOriginal } from '../src/originals';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

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

export default function ResultScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [record, setRecord] = useState<AnalysisRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [reminders, setReminders] = useState<ReminderRecord[]>([]);
  const [originalSaved, setOriginalSaved] = useState(false);

  const refreshReminders = useCallback(async (recordId: string) => {
    const list = await getReminders(recordId);
    setReminders(list);
  }, []);

  useEffect(() => {
    (async () => {
      const l = (await getStoredLanguage()) ?? 'en';
      setLang(l);
      const cached = getLastResult();
      if (cached && (!id || cached.id === id)) {
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

  const r = record.result;
  const risk = riskMeta(r.risk_level, lang);

  const copyReply = async () => {
    if (!r.german_reply_draft) return;
    try {
      await Clipboard.setStringAsync(r.german_reply_draft);
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


  return (
    <SafeAreaView style={styles.safe} testID="result-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.replace('/home')} testID="result-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {r.document_type || t(lang, 'document_type')}
        </Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          {originalSaved ? (
            <Pressable
              onPress={() => router.push(`/original?id=${encodeURIComponent(record.id)}`)}
              testID="result-view-original"
              hitSlop={12}
            >
              <Eye color={colors.primary} size={22} strokeWidth={2.4} />
            </Pressable>
          ) : null}
          <Pressable onPress={onShare} testID="result-share" hitSlop={12}>
            <Share2 color={colors.primary} size={22} strokeWidth={2.4} />
          </Pressable>
          <Pressable onPress={onDelete} testID="result-delete" hitSlop={12}>
            <Trash2 color={colors.textSecondary} size={22} strokeWidth={2.2} />
          </Pressable>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Scam warning — surfaces the highest-priority safety signal first */}
        {r.scam_warning ? (
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
              </View>
            </View>
          </View>
        ) : null}

        {/* Category pill (compact, glanceable) */}
        {r.category ? (
          <View style={styles.categoryPill} testID="result-category-pill">
            <Text style={styles.categoryPillText}>
              {t(lang, 'category_label')}: {categoryLabel(lang, r.category)}
            </Text>
          </View>
        ) : null}

        {/* Risk level */}
        <View
          style={[
            styles.riskCard,
            { backgroundColor: risk.palette.bg, borderColor: risk.palette.border },
          ]}
          testID={`risk-card-${r.risk_level}`}
        >
          <View style={styles.riskTop}>
            <View style={[styles.riskIcon, { backgroundColor: 'rgba(255,255,255,0.6)' }]}>
              {risk.icon}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.riskKicker, { color: risk.palette.text }]}>
                {t(lang, 'risk_level')}
              </Text>
              <Text style={[styles.riskTitle, { color: risk.palette.text }]}>
                {risk.label}
              </Text>
            </View>
          </View>
          {r.risk_reason ? (
            <Text style={[styles.riskBody, { color: risk.palette.text }]}>{r.risk_reason}</Text>
          ) : null}
        </View>

        {/* Summary */}
        {r.summary_translated ? (
          <Card testID="summary-card">
            <SectionRow icon={<Sparkles color={colors.primary} size={18} strokeWidth={2.5} />} title={t(lang, 'summary')} />
            <Text style={styles.body}>{r.summary_translated}</Text>
          </Card>
        ) : null}

        {/* What this means */}
        {r.simple_explanation_translated ? (
          <Card testID="explanation-card">
            <SectionRow icon={<Info color={colors.primary} size={18} strokeWidth={2.5} />} title={t(lang, 'what_this_means')} />
            <Text style={styles.body}>{r.simple_explanation_translated}</Text>
            {r.key_points && r.key_points.length > 0 ? (
              <View style={{ gap: 8, marginTop: spacing.sm }}>
                {r.key_points.map((kp, i) => (
                  <View key={i} style={styles.bullet}>
                    <View style={styles.bulletDot} />
                    <Text style={styles.bulletText}>{kp}</Text>
                  </View>
                ))}
              </View>
            ) : null}
          </Card>
        ) : null}

        {/* What to do next */}
        {r.required_actions && r.required_actions.length > 0 ? (
          <Card testID="actions-card">
            <SectionRow icon={<ListTodo color={colors.primary} size={18} strokeWidth={2.5} />} title={t(lang, 'what_to_do_next')} />
            <View style={{ gap: spacing.sm }}>
              {r.required_actions.map((a, i) => (
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
          </Card>
        ) : null}

        {/* Deadlines */}
        <Card testID="deadlines-card">
          <SectionRow icon={<CalendarClock color={colors.primary} size={18} strokeWidth={2.5} />} title={t(lang, 'deadlines')} />
          {r.deadlines && r.deadlines.length > 0 ? (
            <View style={{ gap: spacing.sm }}>
              {r.deadlines.map((d, i) => {
                const key = deadlineKeyFor(i, d);
                const existing = reminders.find((rm) => rm.deadlineKey === key);
                const parsed = tryParseDeadlineDate(d.date);
                const isPast = parsed ? parsed.getTime() < Date.now() : false;
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
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                        {d.confidence ? (
                          <Badge
                            label={d.confidence}
                            variant={
                              d.confidence === 'high' ? 'green' : d.confidence === 'medium' ? 'yellow' : 'neutral'
                            }
                          />
                        ) : null}
                        <Pressable
                          onPress={onToggleReminder}
                          style={[
                            styles.reminderBtn,
                            existing && { backgroundColor: colors.green.bg, borderColor: colors.green.border },
                          ]}
                          testID={`reminder-toggle-${i}`}
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
          ) : (
            <Text style={[styles.body, { color: colors.textSecondary }]}>{t(lang, 'no_deadlines')}</Text>
          )}
        </Card>

        {/* Sender + Doc type */}
        <Card testID="sender-card">
          <SectionRow icon={<Building2 color={colors.primary} size={18} strokeWidth={2.5} />} title={t(lang, 'sender')} />
          <View style={styles.kvRow}>
            <Text style={styles.kvKey}>{t(lang, 'sender')}</Text>
            <Text style={styles.kvValue}>{r.sender || '—'}</Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={styles.kvKey}>{t(lang, 'document_type')}</Text>
            <Text style={styles.kvValue}>{r.document_type || '—'}</Text>
          </View>
        </Card>

        {/* German reply draft */}
        {r.german_reply_draft ? (
          <Card testID="reply-card">
            <SectionRow icon={<Reply color={colors.primary} size={18} strokeWidth={2.5} />} title={t(lang, 'reply_draft')} />
            <View style={styles.replyBox}>
              <Text style={styles.replyText}>{r.german_reply_draft}</Text>
            </View>
            <Pressable onPress={copyReply} style={styles.copyBtn} testID="reply-copy">
              {copied ? (
                <CheckCircle2 color={colors.green.text} size={18} strokeWidth={2.5} />
              ) : (
                <Copy color={colors.primary} size={18} strokeWidth={2.5} />
              )}
              <Text style={styles.copyLabel}>
                {copied ? t(lang, 'copied') : t(lang, 'copy')}
              </Text>
            </Pressable>
            {r.reply_draft_explanation_translated ? (
              <View style={{ marginTop: spacing.sm }}>
                <Text style={styles.subSectionTitle}>{t(lang, 'reply_explanation')}</Text>
                <Text style={[styles.body, { marginTop: 6 }]}>
                  {r.reply_draft_explanation_translated}
                </Text>
              </View>
            ) : null}
          </Card>
        ) : null}

        {/* Questions to ask */}
        {r.questions_to_ask && r.questions_to_ask.length > 0 ? (
          <Card testID="questions-card">
            <SectionRow icon={<HelpCircle color={colors.primary} size={18} strokeWidth={2.5} />} title={t(lang, 'questions_to_ask')} />
            <View style={{ gap: 8 }}>
              {r.questions_to_ask.map((q, i) => (
                <View key={i} style={styles.bullet}>
                  <View style={[styles.bulletDot, { backgroundColor: colors.primary }]} />
                  <Text style={styles.bulletText}>{q}</Text>
                </View>
              ))}
            </View>
          </Card>
        ) : null}

        {/* Uncertainties */}
        {r.uncertainties && r.uncertainties.length > 0 ? (
          <Card testID="uncertainties-card">
            <SectionRow icon={<AlertTriangle color={colors.yellow.text} size={18} strokeWidth={2.5} />} title={t(lang, 'uncertainties')} />
            <View style={{ gap: 8 }}>
              {r.uncertainties.map((u, i) => (
                <View key={i} style={styles.bullet}>
                  <View style={[styles.bulletDot, { backgroundColor: colors.yellow.solid }]} />
                  <Text style={styles.bulletText}>{u}</Text>
                </View>
              ))}
            </View>
          </Card>
        ) : null}

        {/* Disclaimer */}
        <View style={styles.disclaimer} testID="disclaimer-card">
          <FileText color={colors.textSecondary} size={16} strokeWidth={2.4} />
          <Text style={styles.disclaimerText}>{r.disclaimer}</Text>
        </View>

        <Button
          label={t(lang, 'ask_question')}
          onPress={() => router.push(`/chat?id=${encodeURIComponent(record.id)}`)}
          icon={<MessageCircle color={colors.white} size={18} strokeWidth={2.5} />}
          testID="result-ask-question"
        />
        <Button
          label={t(lang, 'analyze_again')}
          onPress={() => router.replace('/home')}
          variant="secondary"
          icon={<RotateCcw color={colors.primary} size={18} strokeWidth={2.5} />}
          testID="result-analyze-again"
        />
        <View style={{ height: spacing.lg }} />
      </ScrollView>
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
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.md, paddingHorizontal: spacing.lg },
  errorText: { fontSize: fontSize.base, color: colors.textSecondary, textAlign: 'center' },
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
  categoryPill: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: colors.primarySoft,
  },
  categoryPillText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    letterSpacing: 0.3,
  },

  riskCard: {
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    gap: spacing.md,
  },
  riskTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  riskIcon: {
    width: 56,
    height: 56,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  riskKicker: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    opacity: 0.8,
  },
  riskTitle: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    letterSpacing: -0.4,
    marginTop: 2,
  },
  riskBody: {
    fontSize: fontSize.base,
    lineHeight: 22,
    fontWeight: fontWeight.medium,
  },
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
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    backgroundColor: colors.background,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  deadlineDateChip: {
    backgroundColor: colors.primarySoft,
    borderRadius: radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 6,
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
});
