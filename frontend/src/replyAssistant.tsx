// Reply Assistant — Phase R5 production component.
//
// Renders inside the Result screen's "Reply" tab. Lifecycle:
//
//   1. Show a list of intent cards (reply_options from the analysis).
//      The recommended option is highlighted with a "Recommended" badge.
//
//   2. When the user picks an intent, we POST /generate-reply and show
//      a skeleton-loader card. On success the response renders into an
//      editable <TextInput> so the user can fine-tune wording.
//
//   3. The composer block surfaces the entities the model extracted
//      (recipient email, subject, contact_person, reference number,
//      organization). When the email is missing we render a fallback
//      input field so the user can type one.
//
//   4. Three actions: "Open in mail" (mailto: via expo-linking, primary,
//      iOS/Android native), "Copy" (clipboard), "Share" (RN Share API).
//
// Multi-language: the entire UI uses the user's chosen target language
// for chrome (labels, buttons), but the generated reply itself stays in
// the SOURCE document's language (so it can be sent to the sender).

import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking as RNLinking,
  Platform,
  Pressable,
  Share,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import {
  Check,
  ChevronRight,
  Copy,
  Mail,
  RefreshCw,
  Share2,
  Sparkles,
} from 'lucide-react-native';
import {
  AnalysisRecord,
  ExtractedEntities,
  ReplyOption,
  generateReply,
} from './api';
import { LanguageCode, t } from './i18n';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from './theme';

interface Props {
  record: AnalysisRecord;
  /** UI language (NOT the source-language of the reply). */
  uiLang: LanguageCode;
  /** Currently displayed result (already language-switched if applicable). */
  options: ReplyOption[];
  entities: ExtractedEntities;
  /** Initial fallback reply (the static `reply_draft` from analysis). When
   *  the user hasn't picked an intent yet, we don't show this — they need
   *  to actively pick. */
  legacyReplyDraft?: string;
  /** Source-document language label, shown to the user as a small hint
   *  ("Reply in English") so they understand why the draft isn't in
   *  their UI language. */
  sourceLanguageLabel?: string;
  deviceId: string;
}

interface DraftState {
  intentId: string;
  text: string;
  loading: boolean;
}

export function ReplyAssistant({
  record,
  uiLang,
  options,
  entities,
  sourceLanguageLabel,
  deviceId,
}: Props) {
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [recipientOverride, setRecipientOverride] = useState<string>('');
  const [copied, setCopied] = useState(false);

  // Sort options so the recommended one shows first.
  const sortedOptions = useMemo(() => {
    return [...options].sort((a, b) => Number(!!b.recommended) - Number(!!a.recommended));
  }, [options]);

  const recipient = (entities.email || recipientOverride || '').trim();
  const hasRecipient = !!recipient;

  const subject = useMemo(() => {
    const refPart = entities.reference_number ? ` (${entities.reference_number})` : '';
    if (entities.subject) return `${entities.subject}${refPart}`;
    if (entities.organization) return `${entities.organization}${refPart}`;
    return record.result.document_type || t(uiLang, 'reply_default_subject');
  }, [entities, record.result.document_type, uiLang]);

  const pickIntent = async (opt: ReplyOption) => {
    setDraft({ intentId: opt.id, text: '', loading: true });
    try {
      const { reply_text } = await generateReply(record.id, deviceId, opt.id);
      setDraft({ intentId: opt.id, text: reply_text, loading: false });
    } catch (err) {
      setDraft(null);
      Alert.alert(t(uiLang, 'reply_error_title'), String((err as Error)?.message || err));
    }
  };

  const onCopy = async () => {
    if (!draft?.text) return;
    try {
      await Clipboard.setStringAsync(draft.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  const onOpenMail = async () => {
    if (!draft?.text) return;
    const to = recipient;
    const greetingPrefix = entities.contact_person ? `${entities.contact_person},\n\n` : '';
    const bodyText = greetingPrefix + draft.text;
    const url =
      `mailto:${encodeURIComponent(to)}` +
      `?subject=${encodeURIComponent(subject)}` +
      `&body=${encodeURIComponent(bodyText)}`;
    try {
      await RNLinking.openURL(url);
    } catch {
      Alert.alert(t(uiLang, 'reply_no_mail_app'));
    }
  };

  const onShare = async () => {
    if (!draft?.text) return;
    try {
      await Share.share({
        message: draft.text,
        title: subject,
      });
    } catch {
      // ignore — user cancelled
    }
  };

  // ---------------- Render ----------------
  return (
    <View style={styles.container}>
      {/* Step 1: pick an intent */}
      <View style={styles.headerRow}>
        <Sparkles color={colors.primary} size={18} strokeWidth={2.4} />
        <Text style={styles.headerTitle}>{t(uiLang, 'reply_pick_intent')}</Text>
      </View>

      <View style={styles.intentList}>
        {sortedOptions.map((opt) => {
          const isActive = draft?.intentId === opt.id;
          return (
            <Pressable
              key={opt.id}
              onPress={() => pickIntent(opt)}
              disabled={draft?.loading && draft.intentId === opt.id}
              style={({ pressed }) => [
                styles.intentCard,
                isActive && styles.intentCardActive,
                pressed && !isActive && { opacity: 0.7 },
              ]}
              accessibilityRole="button"
              accessibilityLabel={opt.label}
              testID={`intent-${opt.id}`}
            >
              <View style={{ flex: 1 }}>
                <View style={styles.intentTitleRow}>
                  <Text style={[styles.intentLabel, isActive && styles.intentLabelActive]}>
                    {opt.label}
                  </Text>
                  {opt.recommended ? (
                    <View style={styles.recommendedBadge}>
                      <Text style={styles.recommendedText}>
                        {t(uiLang, 'reply_recommended')}
                      </Text>
                    </View>
                  ) : null}
                </View>
                {opt.reason ? (
                  <Text style={styles.intentReason} numberOfLines={2}>
                    {opt.reason}
                  </Text>
                ) : null}
              </View>
              {draft?.intentId === opt.id && draft.loading ? (
                <ActivityIndicator color={colors.primary} size="small" />
              ) : (
                <ChevronRight color={colors.textMuted} size={18} strokeWidth={2.4} />
              )}
            </Pressable>
          );
        })}
      </View>

      {/* Step 2: editable draft */}
      {draft && !draft.loading && draft.text ? (
        <View style={styles.composer}>
          <View style={styles.headerRow}>
            <Mail color={colors.primary} size={18} strokeWidth={2.4} />
            <Text style={styles.headerTitle}>{t(uiLang, 'reply_compose')}</Text>
            <Pressable
              onPress={() => {
                const opt = sortedOptions.find((o) => o.id === draft.intentId);
                if (opt) pickIntent(opt);
              }}
              hitSlop={10}
              style={({ pressed }) => [styles.regenerateBtn, pressed && { opacity: 0.7 }]}
              testID="reply-regenerate"
              accessibilityLabel={t(uiLang, 'reply_regenerate')}
            >
              <RefreshCw color={colors.textMuted} size={16} strokeWidth={2.4} />
            </Pressable>
          </View>

          {/* Meta block — recipient, subject, contact */}
          <View style={styles.metaBlock}>
            {hasRecipient ? (
              <MetaRow label={t(uiLang, 'reply_to')} value={recipient} />
            ) : (
              <View style={{ marginBottom: spacing.sm }}>
                <Text style={styles.metaLabel}>{t(uiLang, 'reply_to')}</Text>
                <TextInput
                  value={recipientOverride}
                  onChangeText={setRecipientOverride}
                  placeholder={t(uiLang, 'reply_email_missing')}
                  placeholderTextColor={colors.textMuted}
                  style={styles.recipientInput}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  testID="reply-recipient-input"
                />
              </View>
            )}
            <MetaRow label={t(uiLang, 'reply_subject')} value={subject} />
            {entities.contact_person ? (
              <MetaRow label={t(uiLang, 'reply_contact_person')} value={entities.contact_person} />
            ) : null}
          </View>

          {/* The reply body — editable */}
          <Text style={styles.metaLabel}>
            {t(uiLang, 'reply_body')}
            {sourceLanguageLabel ? `  ·  ${sourceLanguageLabel}` : ''}
          </Text>
          <TextInput
            value={draft.text}
            onChangeText={(v) => setDraft({ ...draft, text: v })}
            multiline
            style={styles.bodyInput}
            textAlignVertical="top"
            testID="reply-body-input"
          />

          {/* Actions row */}
          <View style={styles.actionsRow}>
            <Pressable
              onPress={onOpenMail}
              disabled={!hasRecipient || !draft.text}
              style={({ pressed }) => [
                styles.primaryBtn,
                (!hasRecipient || !draft.text) && styles.primaryBtnDisabled,
                pressed && hasRecipient && draft.text ? { opacity: 0.85 } : null,
              ]}
              testID="reply-open-mail"
            >
              <Mail color={colors.white} size={16} strokeWidth={2.6} />
              <Text style={styles.primaryBtnText}>{t(uiLang, 'reply_open_mail')}</Text>
            </Pressable>
            <Pressable
              onPress={onCopy}
              disabled={!draft.text}
              style={({ pressed }) => [styles.secondaryBtn, pressed && { opacity: 0.7 }]}
              testID="reply-copy"
            >
              {copied ? (
                <Check color={colors.green.text} size={16} strokeWidth={2.6} />
              ) : (
                <Copy color={colors.primary} size={16} strokeWidth={2.6} />
              )}
              <Text style={styles.secondaryBtnText}>
                {copied ? t(uiLang, 'copied') : t(uiLang, 'copy')}
              </Text>
            </Pressable>
            <Pressable
              onPress={onShare}
              disabled={!draft.text}
              style={({ pressed }) => [styles.secondaryBtn, pressed && { opacity: 0.7 }]}
              testID="reply-share"
            >
              <Share2 color={colors.primary} size={16} strokeWidth={2.6} />
              <Text style={styles.secondaryBtnText}>{t(uiLang, 'share')}</Text>
            </Pressable>
          </View>

          {!hasRecipient ? (
            <Text style={styles.warningHint}>{t(uiLang, 'reply_email_warning')}</Text>
          ) : null}
        </View>
      ) : draft?.loading ? (
        <View style={styles.skeletonCard}>
          <ActivityIndicator color={colors.primary} />
          <Text style={styles.skeletonText}>{t(uiLang, 'reply_generating')}</Text>
        </View>
      ) : null}
    </View>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <View style={{ marginBottom: spacing.xs }}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={styles.metaValue} numberOfLines={2}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.md },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: {
    flex: 1,
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  intentList: { gap: 8 },
  intentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: 14,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  intentCardActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  intentTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  intentLabel: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  intentLabelActive: { color: colors.primary },
  recommendedBadge: {
    backgroundColor: colors.primary,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.pill,
  },
  recommendedText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: fontWeight.bold,
    letterSpacing: 0.2,
  },
  intentReason: {
    marginTop: 4,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  composer: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.sm,
    ...shadows.card,
  },
  regenerateBtn: {
    padding: 6,
    borderRadius: radius.full,
    backgroundColor: colors.surfaceMuted,
  },
  metaBlock: {
    paddingTop: 4,
    paddingBottom: 4,
  },
  metaLabel: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 3,
  },
  metaValue: {
    fontSize: fontSize.sm,
    color: colors.textPrimary,
  },
  recipientInput: {
    fontSize: fontSize.sm,
    color: colors.textPrimary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: 10,
    paddingVertical: Platform.OS === 'ios' ? 10 : 6,
  },
  bodyInput: {
    minHeight: 180,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.sm,
    backgroundColor: colors.background,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
    marginTop: 4,
  },
  primaryBtn: {
    flexGrow: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    minHeight: 44,
    ...shadows.button,
  },
  primaryBtnDisabled: { opacity: 0.5 },
  primaryBtnText: {
    color: colors.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
  },
  secondaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    paddingHorizontal: 14,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    minHeight: 44,
  },
  secondaryBtnText: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
  },
  warningHint: {
    fontSize: fontSize.xs,
    color: colors.yellow.text,
    fontStyle: 'italic',
    marginTop: 4,
  },
  skeletonCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: spacing.md,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
  },
  skeletonText: { color: colors.textSecondary, fontSize: fontSize.sm },
});
