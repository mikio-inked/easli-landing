// API client for the easli backend.

import { LanguageCode } from './i18n';
import { captureException } from './sentry';

const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export interface Deadline {
  date: string;
  description: string;
  confidence: 'low' | 'medium' | 'high';
}

export interface RequiredAction {
  action: string;
  urgency: 'low' | 'medium' | 'high';
  reason: string;
}

export type Category =
  | 'tax'
  | 'insurance'
  | 'rent'
  | 'bank'
  | 'health'
  | 'government'
  | 'court'
  | 'utilities'
  | 'telecom'
  | 'work'
  | 'education'
  | 'other';

export interface ReplyOption {
  id: 'inquiry' | 'extension' | 'confirm' | 'objection' | 'submit_documents' | 'cancel' | string;
  label: string;
  reason?: string;
  recommended?: boolean;
}

export interface ExtractedEntities {
  email?: string;
  subject?: string;
  reference_number?: string;
  contact_person?: string;
  organization?: string;
}

export interface AnalysisResult {
  source_language: string;
  /** ISO-639-1 code of the detected source language ('de', 'en', 'fr', ...).
   * Empty string on legacy records. Populated since Phase-3. */
  source_language_code?: string;
  target_language: string;
  document_type: string;
  sender: string;
  summary_translated: string;
  simple_explanation_translated: string;
  key_points: string[];
  deadlines: Deadline[];
  required_actions: RequiredAction[];
  risk_level: 'green' | 'yellow' | 'red';
  risk_reason: string;
  /** Polite reply draft, in the SAME language as the source document.
   * Preferred field since Phase-3 (multi-source-language). */
  reply_draft?: string;
  /** Legacy alias, kept for backward compat with older records. Mirrors
   * `reply_draft` when both are populated. Readers should prefer
   * `reply_draft ?? german_reply_draft`. */
  german_reply_draft: string;
  reply_draft_explanation_translated: string;
  questions_to_ask: string[];
  uncertainties: string[];
  disclaimer: string;
  category: Category;
  scam_warning: boolean;
  scam_reason: string;
  /** Reply Assistant (Phase R5). Optional on legacy records. */
  extracted_entities?: ExtractedEntities;
  reply_options?: ReplyOption[];
}

export interface AnalysisRecord {
  id: string;
  device_id: string;
  target_language: string;
  target_language_label: string;
  mime_type: string;
  created_at: string;
  result: AnalysisResult;
  /** Map of LanguageCode → localized AnalysisResult. Populated on demand by
   *  POST /api/analyses/{id}/translate. Factual fields (sender, dates, risk,
   *  category, scam_warning, german_reply_draft) are preserved byte-identical. */
  translations?: Record<string, AnalysisResult>;
}

export interface AnalysisListItem {
  id: string;
  created_at: string;
  target_language: string;
  target_language_label: string;
  document_type: string;
  sender: string;
  risk_level: 'green' | 'yellow' | 'red';
  summary_translated: string;
  category: Category;
  scam_warning: boolean;
  /** ISO 3166-1 alpha-2 jurisdiction detected by the analyser. Empty string
   *  when the document did not contain a confident country signal. Added in
   *  Phase 6 (EU country packs). Legacy records pre-Phase 6 will return ''. */
  detected_country_code?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  off_topic: boolean;
  created_at: string;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const msg = (body && body.detail) || (typeof body === 'string' ? body : `HTTP ${res.status}`);
    const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    // Report 5xx and unexpected 4xx (excluding the user-facing 401/402/403
    // which are part of normal flow, and 429 which is rate-limit feedback).
    // We strip the URL via the Sentry beforeBreadcrumb hook already; this
    // adds the HTTP status as a tag for fast triage in the dashboard.
    if (res.status >= 500 || (res.status >= 400 && ![401, 402, 403, 404, 422, 429].includes(res.status))) {
      captureException(err, { httpStatus: res.status, url: res.url.split('?')[0] });
    }
    throw err;
  }
  return body as T;
}

export interface AnalyzePage {
  file_base64: string;
  mime_type: string;
}

// Re-export the typed errors from `usage.ts` so existing callers can keep
// importing everything from `api.ts`.
export {
  PaymentRequiredError,
  RateLimitError,
  TestLimitReachedError,
  UnsupportedDocumentLanguageError,
  type UsageState,
} from './usage';

import {
  PaymentRequiredError,
  RateLimitError,
  TestLimitReachedError,
  UnsupportedDocumentLanguageError,
  type UsageState,
} from './usage';

/** Hard ceiling for /api/analyze. Long enough that big-picture multipage
 *  scans still succeed, short enough that a stuck connection eventually
 *  gives the user a clean error instead of an indefinite spinner. */
const ANALYZE_TIMEOUT_MS = 120_000;

export async function analyzeDocument(params: {
  device_id: string;
  target_language: LanguageCode;
  pages: AnalyzePage[];
  /** Idempotency key generated by the client at the moment the user taps
   *  "Analyze". Same key sent twice → backend will not double-consume. */
  idempotency_key?: string;
}): Promise<AnalysisRecord & { usage?: UsageState }> {
  // AbortController + setTimeout gives us a deterministic upper bound on
  // the request. Without this, iOS URLSession defaults to 60 s — which is
  // too tight for multi-page scans on slow networks. RN's Web/iOS/Android
  // all support AbortController in modern builds.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);

  let res: Response;
  // Diagnostic (Phase EU-1 support): If BASE_URL is empty at runtime the
  // fetch polyfill throws "Invalid URL: /api/analyze" which is confusing
  // on real devices. Surface a precise, debuggable error instead that
  // exposes the resolved URL and the raw env var value.
  const targetUrl = `${BASE_URL}/api/analyze`;
  if (!BASE_URL || !targetUrl.startsWith('http')) {
    throw new Error(
      `Backend URL not configured. BASE_URL="${BASE_URL}" ENV="${(process.env.EXPO_PUBLIC_BACKEND_URL as string) || ''}". Rebuild or push OTA with EXPO_PUBLIC_BACKEND_URL set.`,
    );
  }
  try {
    res = await fetch(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: controller.signal,
    });
  } catch (e: any) {
    if (e?.name === 'AbortError') {
      throw new Error(
        'The upload took too long. Please check your connection and try again.',
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }

  // Special-case the entitlement-gate responses BEFORE the generic error
  // handler so callers can route the user to the paywall / test-limit
  // banner instead of showing a raw error toast.
  if (res.status === 402 || res.status === 429) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // ignore — fall through to a generic error
    }
    // Branch 1 — entitlement gate (backend includes `usage` in the body).
    if (body?.usage) {
      const message: string = body.message || '';
      if (res.status === 402 || body.error === 'payment_required') {
        throw new PaymentRequiredError(message, body.usage as UsageState);
      }
      throw new TestLimitReachedError(
        message || 'Dein Testkontingent ist erreicht. Danke fürs Testen von easli.',
        body.usage as UsageState,
      );
    }
    // Branch 2 — Mistral rate-limit propagated through (no `usage` field).
    // The backend has already retried twice with backoff before sending
    // this. Surface a typed RateLimitError so the analyzing screen can
    // show "Server is busy, try again in N seconds" instead of the
    // generic "AI analysis failed" toast.
    if (res.status === 429) {
      const headerVal = res.headers.get('retry-after') || res.headers.get('Retry-After');
      const retryAfter = parseInt(headerVal || '8', 10);
      throw new RateLimitError(
        (body && body.detail) || 'AI is busy. Please try again in a moment.',
        Number.isFinite(retryAfter) ? retryAfter : 8,
      );
    }
  }

  // Language gate — the backend returns 422 with a typed error envelope
  // when the document is clearly non-German. We surface a dedicated typed
  // error so the analyzing screen can show a calm explanation screen
  // instead of the generic "AI analysis failed" toast, and so the caller
  // can be 100% sure NO usage was consumed. Keeping this BEFORE jsonOrThrow
  // is critical — otherwise the generic handler strips the structured body.
  if (res.status === 422) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // fall through to generic error below
    }
    if (body && body.error === 'unsupported_document_language') {
      throw new UnsupportedDocumentLanguageError(
        body.message || 'Dieses Dokument scheint nicht auf Deutsch zu sein.',
        body.detected_language_code ?? null,
        body.confidence || 'high',
      );
    }
  }

  return jsonOrThrow<AnalysisRecord & { usage?: UsageState }>(res);
}

export async function listAnalyses(deviceId: string): Promise<AnalysisListItem[]> {
  const res = await fetch(`${BASE_URL}/api/analyses?device_id=${encodeURIComponent(deviceId)}`);
  return jsonOrThrow<AnalysisListItem[]>(res);
}

export async function getAnalysis(id: string, deviceId: string): Promise<AnalysisRecord> {
  const res = await fetch(`${BASE_URL}/api/analyses/${encodeURIComponent(id)}?device_id=${encodeURIComponent(deviceId)}`);
  return jsonOrThrow<AnalysisRecord>(res);
}

export async function deleteAnalysis(id: string, deviceId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/analyses/${encodeURIComponent(id)}?device_id=${encodeURIComponent(deviceId)}`, {
    method: 'DELETE',
  });
  await jsonOrThrow(res);
}

export async function deleteAllAnalyses(deviceId: string): Promise<void> {
  // DSGVO Art. 17 — calls the explicit /api/history/{device_id} endpoint
  // which wipes both analyses AND chat messages in one shot.
  const res = await fetch(
    `${BASE_URL}/api/history/${encodeURIComponent(deviceId)}`,
    { method: 'DELETE' }
  );
  await jsonOrThrow(res);
}

export interface ExportPayload {
  app: string;
  device_id: string;
  exported_at: string;
  data_residency: string;
  count: number;
  analyses: AnalysisRecord[];
}

export async function exportMyData(deviceId: string): Promise<ExportPayload> {
  const res = await fetch(`${BASE_URL}/api/export?device_id=${encodeURIComponent(deviceId)}`);
  return jsonOrThrow<ExportPayload>(res);
}

export async function listChatMessages(analysisId: string, deviceId: string): Promise<ChatMessage[]> {
  const res = await fetch(
    `${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/messages?device_id=${encodeURIComponent(deviceId)}`
  );
  return jsonOrThrow<ChatMessage[]>(res);
}

export async function sendChatMessage(
  analysisId: string,
  deviceId: string,
  message: string,
  targetLanguage?: LanguageCode,
): Promise<ChatMessage> {
  const body: Record<string, unknown> = { device_id: deviceId, message };
  if (targetLanguage) body.target_language = targetLanguage;
  const res = await fetch(`${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return jsonOrThrow<ChatMessage>(res);
}

/**
 * Re-localise an existing analysis into a different language without
 * rescanning. Server uses the stored structured analysis — no new OCR /
 * Vision call, no original-image access. Cached per (analysis, language)
 * so repeat switches are instant.
 *
 * Throws a generic Error with a friendly message on any non-2xx. Errors
 * typically mean the user should try again in a moment — they do NOT
 * indicate the original analysis is lost (server always keeps the primary
 * result intact).
 */
export async function translateAnalysis(
  analysisId: string,
  deviceId: string,
  targetLanguage: LanguageCode,
): Promise<AnalysisRecord & { usage?: UsageState }> {
  const res = await fetch(
    `${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/translate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: deviceId,
        target_language: targetLanguage,
      }),
    },
  );
  return jsonOrThrow<AnalysisRecord & { usage?: UsageState }>(res);
}

export async function clearChatMessages(analysisId: string, deviceId: string): Promise<void> {
  const res = await fetch(
    `${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/messages?device_id=${encodeURIComponent(deviceId)}`,
    { method: 'DELETE' }
  );
  await jsonOrThrow(res);
}

/**
 * Generate a tailored reply draft for a single intent. Returns the reply
 * body in the SOURCE document's language so the user can paste it
 * straight into a mailto: composer.
 *
 * Phase R5 (Reply Assistant). Backend endpoint:
 *   POST /api/analyses/{id}/generate-reply
 *     body: { device_id, intent, custom_instruction? }
 *     200: { reply_text, intent }
 *     400: invalid intent
 *     404: analysis not found
 *     502: Mistral failure
 */
export async function generateReply(
  analysisId: string,
  deviceId: string,
  intent: string,
  customInstruction?: string,
  /** Phase EU-1: optional explicit reply language (ISO-639-1, e.g. "de",
   *  "fr", "nl"). When omitted, backend falls back to the analysis's
   *  `suggested_reply_language_code`, then to `source_language_code`. */
  replyLanguageCode?: string,
): Promise<{
  reply_text: string;
  intent: string;
  reply_language_code?: string;
  /** Phase R6: a 2-4 sentence explanation in the user's Explanation-
   *  Language of what this reply says, so users scanning a letter in a
   *  language they don't fully master know what they're about to send. */
  reply_explanation?: string;
}> {
  const body: Record<string, unknown> = {
    device_id: deviceId,
    intent,
    custom_instruction: customInstruction || '',
  };
  if (replyLanguageCode && replyLanguageCode.trim()) {
    body.reply_language_code = replyLanguageCode.trim();
  }
  const res = await fetch(
    `${BASE_URL}/api/analyses/${encodeURIComponent(analysisId)}/generate-reply`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  return jsonOrThrow<{
    reply_text: string;
    intent: string;
    reply_language_code?: string;
    reply_explanation?: string;
  }>(res);
}


// ============================================================
// Redemption codes (hidden Friends & Family flow)
// ============================================================
export interface RedeemResult {
  ok: boolean;
  tier?: 'lifetime' | 'plus_year' | 'plus_month' | string;
  message: string;
  plus_active: boolean;
  plus_lifetime: boolean;
  plus_period_end?: string | null;
}

/** Public endpoint — redeem a Friends & Family code.
 *
 *  The backend validates capacity / expiry / active flag and, on success,
 *  flips the device's `usage_records` doc to `plus_active=true` (plus
 *  `plus_lifetime=true` for lifetime tier). Re-running with the same
 *  device_id is idempotent (returns ok=true with message "Already redeemed").
 *
 *  Caller MUST refresh the local Usage hook afterwards so the paywall
 *  badge updates without a full app restart. */
export async function redeemCode(
  deviceId: string,
  code: string,
): Promise<RedeemResult> {
  const res = await fetch(`${BASE_URL}/api/redeem`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_id: deviceId,
      code: (code || '').trim(),
    }),
  });
  // The backend returns 200 with { ok: false, message } for "code not found"
  // type errors — the throw path in jsonOrThrow only fires on 4xx/5xx.
  return jsonOrThrow<RedeemResult>(res);
}
