// Pure logic helpers for the Result screen.
// Extracted from app/result.tsx during Phase C modularisation. No JSX,
// no React state — safe to import from any TS file. Keep this file
// dependency-light: only LanguageCode + i18n.t() are pulled in.

import { LanguageCode, t } from '../i18n';

export function deadlineKeyFor(idx: number, d: { date: string; description: string }): string {
  return `${idx}|${(d.date || '').trim()}|${(d.description || '').slice(0, 40).trim()}`;
}

export function tryParseDeadlineDate(raw: string): Date | null {
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
export function daysUntil(d: Date): number {
  const now = new Date();
  const a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const b = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((a.getTime() - b.getTime()) / 86400000);
}

// Build a calm, language-aware "in N days / tomorrow / overdue" label.
export function formatRelativeDays(days: number, lang: LanguageCode): string {
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
export type MainAction =
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

export const REPLY_TOKENS = [
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

export function tokenSearch(haystack: string, needles: string[]): boolean {
  const h = haystack.toLowerCase();
  return needles.some((n) => h.includes(n));
}

export function replyRequired(r: any): boolean {
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

export function pickMainAction(r: any): MainAction {
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

export function hasImportantUncertainty(r: any): boolean {
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
