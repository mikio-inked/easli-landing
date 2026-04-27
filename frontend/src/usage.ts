// Usage / paywall config API client + small React hooks.
//
// All functions hit the FastAPI backend introduced in Phase 1
// (/app/backend/server.py).
//
// Privacy: this module only talks about counters and product IDs — never
// document content. The hooks expose cached state so screens can render
// meters without hammering the backend.

import { useCallback, useEffect, useState } from 'react';

const BASE_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL || process.env.EXPO_PACKAGER_PROXY_URL || '';

export type PaywallMode = 'disabled' | 'soft' | 'hard';

export interface UsageState {
  device_id: string;
  paywall_mode: PaywallMode;
  free_analyses_used: number;
  free_analyses_total: number;
  soft_extra_used: number;
  soft_extra_total: number;
  single_letter_credits: number;
  plus_active: boolean;
  plus_period_end: string | null;
  plus_monthly_used: number;
  plus_monthly_total: number;
  total_chat_questions_used: number;
  total_chat_questions_total: number;
  per_document_chat_questions: Record<string, number>;
}

export interface PaywallConfig {
  paywall_mode: PaywallMode;
  free_analyses: number;
  soft_test_extra_analyses: number;
  max_pages_per_document: number;
  max_chat_questions_per_document: number;
  max_total_chat_questions_per_tester: number;
  plus_monthly_analyses: number;
  products: {
    single_letter: string;
    plus_monthly: string;
    plus_yearly: string;
  };
  entitlements: { plus: string };
}

export class PaymentRequiredError extends Error {
  usage: UsageState;
  constructor(message: string, usage: UsageState) {
    super(message);
    this.name = 'PaymentRequiredError';
    this.usage = usage;
  }
}

export class TestLimitReachedError extends Error {
  usage: UsageState;
  scope?: 'per_document' | 'total';
  constructor(message: string, usage: UsageState, scope?: 'per_document' | 'total') {
    super(message);
    this.name = 'TestLimitReachedError';
    this.usage = usage;
    this.scope = scope;
  }
}

/**
 * Thrown when Mistral rate-limits us (HTTP 429 from /api/analyze or
 * /api/analyses/{id}/chat). The route handler in server.py already retries
 * twice with backoff before surfacing this — by the time the client sees
 * it the AI provider really is busy. We expose `retryAfterSeconds` so the
 * UI can show a friendly "try again in N seconds" message instead of the
 * generic "AI analysis failed" toast.
 */
export class RateLimitError extends Error {
  retryAfterSeconds: number;
  constructor(message: string, retryAfterSeconds: number) {
    super(message);
    this.name = 'RateLimitError';
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/**
 * Thrown by analyzeDocument() when the backend's language gate decides
 * the document is clearly NOT primarily German and rejects before running
 * any full analysis. NO quota is consumed when this is thrown — the caller
 * can show a calm explanation screen and send the user back to scan/upload
 * without any usage bookkeeping.
 *
 * `detectedLanguageCode` is a best-effort ISO-639-1 code (e.g. 'en', 'fr',
 * 'tr') or null if the model couldn't name the language. `confidence` is
 * always 'high' when this error fires — the backend uses 'low' / 'unknown'
 * to fall through to normal analysis with an uncertainty note instead.
 */
export class UnsupportedDocumentLanguageError extends Error {
  detectedLanguageCode: string | null;
  confidence: 'low' | 'medium' | 'high';
  constructor(
    message: string,
    detectedLanguageCode: string | null,
    confidence: 'low' | 'medium' | 'high' = 'high',
  ) {
    super(message);
    this.name = 'UnsupportedDocumentLanguageError';
    this.detectedLanguageCode = detectedLanguageCode;
    this.confidence = confidence;
  }
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    const detail =
      (body && (body.detail || body.message || body.error)) ||
      `HTTP ${res.status}`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return (await res.json()) as T;
}

export async function getUsage(deviceId: string): Promise<UsageState> {
  if (!deviceId) throw new Error('device_id is required');
  // Always go to network — the entitlement gate must reflect the latest
  // server-side state (e.g. just after a webhook credit was applied).
  const res = await fetch(`${BASE_URL}/api/usage/${encodeURIComponent(deviceId)}`, {
    cache: 'no-store',
    headers: { 'Cache-Control': 'no-cache' },
  });
  return jsonOrThrow<UsageState>(res);
}

export async function getPaywallConfig(): Promise<PaywallConfig> {
  const res = await fetch(`${BASE_URL}/api/paywall/config`, {
    cache: 'no-store',
  });
  return jsonOrThrow<PaywallConfig>(res);
}

// ---- React hooks -----------------------------------------------------

export function useUsage(deviceId: string | null | undefined) {
  const [usage, setUsage] = useState<UsageState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!deviceId) return;
    setLoading(true);
    setError(null);
    try {
      const next = await getUsage(deviceId);
      setUsage(next);
    } catch (e: any) {
      setError(e?.message || 'Failed to load usage');
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { usage, loading, error, refresh, setUsage };
}

export function usePaywallConfig() {
  const [config, setConfig] = useState<PaywallConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    getPaywallConfig()
      .then((c) => {
        if (mounted) setConfig(c);
      })
      .catch((e: any) => {
        if (mounted) setError(e?.message || 'Failed to load config');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return { config, loading, error };
}

// ---- Helper: derive a remaining count (free + soft) for the current mode

export function getRemainingAnalyses(usage: UsageState | null): {
  free: number;
  soft: number;
  combined: number;
  exhausted: boolean;
} {
  if (!usage) return { free: 0, soft: 0, combined: 0, exhausted: true };
  const free = Math.max(0, usage.free_analyses_total - usage.free_analyses_used);
  const soft =
    usage.paywall_mode === 'soft'
      ? Math.max(0, usage.soft_extra_total - usage.soft_extra_used)
      : 0;
  const combined = free + soft + usage.single_letter_credits +
    (usage.plus_active
      ? Math.max(0, usage.plus_monthly_total - usage.plus_monthly_used)
      : 0);
  return {
    free,
    soft,
    combined,
    exhausted: combined === 0,
  };
}
