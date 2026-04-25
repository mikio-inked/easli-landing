// Helpers to export the current analysis as a shareable PDF or plain text
// using Expo's native share sheet. Works on iOS, Android and (best-effort) web.

import { Alert, Platform } from 'react-native';
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';

import { AnalysisRecord } from './api';
import { LanguageCode, categoryLabel, t } from './i18n';

const RISK_EMOJI: Record<'green' | 'yellow' | 'red', string> = {
  green: '🟢',
  yellow: '🟡',
  red: '🔴',
};

function escapeHtml(value: string): string {
  return (value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDateOnly(iso: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString();
  } catch {
    return iso;
  }
}

function nonEmpty(arr: string[] | undefined | null): string[] {
  return (arr || []).map((v) => (v || '').trim()).filter(Boolean);
}

export function buildAnalysisText(record: AnalysisRecord, lang: LanguageCode): string {
  const r = record.result;
  const lines: string[] = [];

  lines.push('KlarPost');
  lines.push('────────────────────');
  lines.push(`${t(lang, 'category_label')}: ${categoryLabel(lang, r.category)}`);
  if (r.document_type) lines.push(`${t(lang, 'document_type')}: ${r.document_type}`);
  if (r.sender) lines.push(`${t(lang, 'sender')}: ${r.sender}`);
  lines.push(`${t(lang, 'risk_level')}: ${RISK_EMOJI[r.risk_level] || ''} ${r.risk_level}`);
  if (r.risk_reason) lines.push(`  ${r.risk_reason}`);
  lines.push('');

  if (r.scam_warning) {
    lines.push(`⚠️  ${t(lang, 'scam_warning_title')}`);
    if (r.scam_reason) lines.push(`  ${r.scam_reason}`);
    lines.push('');
  }

  if (r.summary_translated) {
    lines.push(`■ ${t(lang, 'summary')}`);
    lines.push(r.summary_translated);
    lines.push('');
  }
  if (r.simple_explanation_translated) {
    lines.push(`■ ${t(lang, 'what_this_means')}`);
    lines.push(r.simple_explanation_translated);
    lines.push('');
  }
  const points = nonEmpty(r.key_points);
  if (points.length) {
    lines.push(`■ ${t(lang, 'summary')}`);
    points.forEach((p) => lines.push(`  • ${p}`));
    lines.push('');
  }
  if (r.deadlines && r.deadlines.length) {
    lines.push(`■ ${t(lang, 'deadlines')}`);
    r.deadlines.forEach((d) => {
      const date = formatDateOnly(d.date);
      lines.push(`  • ${date} — ${d.description}`);
    });
    lines.push('');
  }
  if (r.required_actions && r.required_actions.length) {
    lines.push(`■ ${t(lang, 'what_to_do_next')}`);
    r.required_actions.forEach((a) => {
      lines.push(`  • ${a.action}${a.reason ? ` — ${a.reason}` : ''}`);
    });
    lines.push('');
  }
  if (r.german_reply_draft) {
    lines.push(`■ ${t(lang, 'reply_draft')} (Deutsch)`);
    lines.push(r.german_reply_draft);
    lines.push('');
  }
  if (r.reply_draft_explanation_translated) {
    lines.push(`■ ${t(lang, 'reply_explanation')}`);
    lines.push(r.reply_draft_explanation_translated);
    lines.push('');
  }
  const qs = nonEmpty(r.questions_to_ask);
  if (qs.length) {
    lines.push(`■ ${t(lang, 'questions_to_ask')}`);
    qs.forEach((q) => lines.push(`  • ${q}`));
    lines.push('');
  }
  if (r.disclaimer) {
    lines.push('────────────────────');
    lines.push(r.disclaimer);
  }
  return lines.join('\n');
}

function buildAnalysisHtml(record: AnalysisRecord, lang: LanguageCode): string {
  const r = record.result;
  const date = formatDateOnly(record.created_at);
  const cat = escapeHtml(categoryLabel(lang, r.category));

  const points = nonEmpty(r.key_points);
  const qs = nonEmpty(r.questions_to_ask);

  const scamBlock = r.scam_warning
    ? `<div class="alert alert-scam">
         <div class="alert-title">⚠️ ${escapeHtml(t(lang, 'scam_warning_title'))}</div>
         ${r.scam_reason ? `<div class="alert-body">${escapeHtml(r.scam_reason)}</div>` : ''}
       </div>`
    : '';

  const deadlineRows = (r.deadlines || [])
    .map(
      (d) => `<li><b>${escapeHtml(formatDateOnly(d.date))}</b> — ${escapeHtml(d.description)}</li>`,
    )
    .join('');

  const actionsRows = (r.required_actions || [])
    .map(
      (a) =>
        `<li><b>${escapeHtml(a.action)}</b>${a.reason ? ` — ${escapeHtml(a.reason)}` : ''}</li>`,
    )
    .join('');

  return `<!doctype html><html><head><meta charset="utf-8"><title>KlarPost</title>
<style>
  @page { margin: 28mm 18mm; }
  * { box-sizing: border-box; }
  body { font: 12pt/1.5 -apple-system, "SF Pro Text", "Helvetica Neue", Arial, sans-serif; color: #0F172A; }
  h1 { font-size: 22pt; margin: 0 0 4pt; color: #1D4ED8; }
  h2 { font-size: 13pt; margin: 18pt 0 6pt; color: #1D4ED8; padding-bottom: 4pt; border-bottom: 1pt solid #E2E8F0; }
  .meta { color: #475569; font-size: 10pt; margin-bottom: 12pt; }
  .meta b { color: #0F172A; }
  .pill { display: inline-block; padding: 2pt 8pt; border-radius: 999pt; background: #EFF6FF; color: #1D4ED8; font-size: 9pt; margin-right: 4pt; }
  .risk-green { background: #DCFCE7; color: #166534; }
  .risk-yellow { background: #FEF9C3; color: #854D0E; }
  .risk-red { background: #FEE2E2; color: #991B1B; }
  .alert { padding: 10pt 12pt; border-radius: 8pt; margin: 12pt 0; }
  .alert-scam { background: #FEF2F2; border: 1pt solid #FCA5A5; color: #7F1D1D; }
  .alert-title { font-weight: 700; margin-bottom: 4pt; }
  .reply { background: #F8FAFC; padding: 10pt 12pt; border-left: 3pt solid #2563EB; white-space: pre-wrap; }
  ul { margin: 0 0 0 16pt; padding: 0; }
  li { margin-bottom: 4pt; }
  .disclaimer { color: #64748B; font-size: 9pt; margin-top: 24pt; padding-top: 8pt; border-top: 1pt dashed #CBD5E1; }
  .footer { color: #94A3B8; font-size: 8pt; margin-top: 12pt; }
</style></head><body>
  <h1>KlarPost</h1>
  <div class="meta">
    <span class="pill">${cat}</span>
    <span class="pill risk-${r.risk_level}">${RISK_EMOJI[r.risk_level] || ''} ${escapeHtml(r.risk_level)}</span>
    ${date ? `<span class="pill">${escapeHtml(date)}</span>` : ''}
  </div>
  <div class="meta">
    ${r.document_type ? `<div><b>${escapeHtml(t(lang, 'document_type'))}:</b> ${escapeHtml(r.document_type)}</div>` : ''}
    ${r.sender ? `<div><b>${escapeHtml(t(lang, 'sender'))}:</b> ${escapeHtml(r.sender)}</div>` : ''}
    ${r.risk_reason ? `<div><b>${escapeHtml(t(lang, 'risk_level'))}:</b> ${escapeHtml(r.risk_reason)}</div>` : ''}
  </div>

  ${scamBlock}

  ${
    r.summary_translated
      ? `<h2>${escapeHtml(t(lang, 'summary'))}</h2><div>${escapeHtml(r.summary_translated)}</div>`
      : ''
  }
  ${
    r.simple_explanation_translated
      ? `<h2>${escapeHtml(t(lang, 'what_this_means'))}</h2><div>${escapeHtml(r.simple_explanation_translated)}</div>`
      : ''
  }
  ${points.length ? `<h2>${escapeHtml(t(lang, 'summary'))}</h2><ul>${points.map((p) => `<li>${escapeHtml(p)}</li>`).join('')}</ul>` : ''}
  ${deadlineRows ? `<h2>${escapeHtml(t(lang, 'deadlines'))}</h2><ul>${deadlineRows}</ul>` : ''}
  ${actionsRows ? `<h2>${escapeHtml(t(lang, 'what_to_do_next'))}</h2><ul>${actionsRows}</ul>` : ''}
  ${
    r.german_reply_draft
      ? `<h2>${escapeHtml(t(lang, 'reply_draft'))} (Deutsch)</h2><div class="reply">${escapeHtml(r.german_reply_draft)}</div>`
      : ''
  }
  ${
    r.reply_draft_explanation_translated
      ? `<h2>${escapeHtml(t(lang, 'reply_explanation'))}</h2><div>${escapeHtml(r.reply_draft_explanation_translated)}</div>`
      : ''
  }
  ${qs.length ? `<h2>${escapeHtml(t(lang, 'questions_to_ask'))}</h2><ul>${qs.map((q) => `<li>${escapeHtml(q)}</li>`).join('')}</ul>` : ''}

  ${r.disclaimer ? `<div class="disclaimer">${escapeHtml(r.disclaimer)}</div>` : ''}
  <div class="footer">Generated by KlarPost • ${escapeHtml(record.target_language_label || record.target_language)}</div>
</body></html>`;
}

export async function shareAnalysisAsText(
  record: AnalysisRecord,
  lang: LanguageCode,
): Promise<void> {
  const text = buildAnalysisText(record, lang);
  if (Platform.OS === 'web') {
    try {
      const navAny: any = (globalThis as any).navigator;
      if (navAny?.share) {
        await navAny.share({ title: 'KlarPost', text });
        return;
      }
      if (navAny?.clipboard?.writeText) {
        await navAny.clipboard.writeText(text);
        Alert.alert('KlarPost', 'Copied to clipboard.');
        return;
      }
    } catch (e) {
      // fall through
    }
    Alert.alert('KlarPost', text);
    return;
  }
  // Native: share the text via expo-sharing using a tmp .txt file.
  try {
    const FileSystem = await import('expo-file-system');
    // expo-file-system v18 deprecates documentDirectory in favor of cacheDirectory for tmp.
    const dir = (FileSystem as any).cacheDirectory || (FileSystem as any).documentDirectory;
    const path = `${dir}klarpost-${Date.now()}.txt`;
    await (FileSystem as any).writeAsStringAsync(path, text, {
      encoding: (FileSystem as any).EncodingType?.UTF8 ?? 'utf8',
    });
    if (await Sharing.isAvailableAsync()) {
      await Sharing.shareAsync(path, {
        mimeType: 'text/plain',
        dialogTitle: 'KlarPost',
        UTI: 'public.plain-text',
      });
    } else {
      Alert.alert('KlarPost', text);
    }
  } catch (e) {
    Alert.alert('KlarPost', t(lang, 'share_failed'));
  }
}

export async function shareAnalysisAsPdf(
  record: AnalysisRecord,
  lang: LanguageCode,
): Promise<void> {
  const html = buildAnalysisHtml(record, lang);
  try {
    const { uri } = await Print.printToFileAsync({ html });
    if (await Sharing.isAvailableAsync()) {
      await Sharing.shareAsync(uri, {
        mimeType: 'application/pdf',
        dialogTitle: 'KlarPost',
        UTI: 'com.adobe.pdf',
      });
    } else if (Platform.OS === 'web') {
      // Best-effort: open the rendered PDF in a new tab.
      const w: any = (globalThis as any).window;
      if (w?.open) w.open(uri, '_blank');
    } else {
      Alert.alert('KlarPost', t(lang, 'share_failed'));
    }
  } catch (e) {
    Alert.alert('KlarPost', t(lang, 'share_failed'));
  }
}
