// Lightweight global app store for easli.
// Persists language + device id to AsyncStorage; keeps a transient pending
// analysis payload (base64) in memory only — original documents are NEVER
// persisted by default.

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import type { AnalysisRecord } from './api';
import { LanguageCode } from './i18n';
import { toUIStringCode } from './i18n';

// ---- Storage keys --------------------------------------------------------
//
// Historical: KEY_LANG held a single "language" which was used for both UI
// chrome and AI explanation. Since Phase 4 (EU-1) we split this into three
// independently-stored preferences:
//
//   KEY_LANG              — the user's Explanation-Language pick (25 options).
//                           Existing users' saved value migrates 1:1 into
//                           this role; no data loss.
//   KEY_APP_LANG_OVERRIDE — optional UI-chrome override (7 options). If
//                           set, takes precedence for `t()` calls; if
//                           not set, UI chrome falls back from
//                           explanation-lang via `toUIStringCode`.
//   KEY_REPLY_LANG_MODE   — 'auto' (default) | 'fixed'
//   KEY_REPLY_LANG_FIXED  — the fixed reply-language code (only when
//                           mode='fixed'). Matches the 32-language
//                           REPLY_LANGUAGES registry.
const KEY_LANG = 'klarpost.language';
const KEY_APP_LANG_OVERRIDE = 'klarpost.app_lang_override';
const KEY_REPLY_LANG_MODE = 'klarpost.reply_lang_mode';
const KEY_REPLY_LANG_FIXED = 'klarpost.reply_lang_fixed';
const KEY_DEVICE = 'klarpost.deviceId';
const KEY_ONBOARDED = 'klarpost.onboarded';
const KEY_CONSENT = 'klarpost.consent_v1';

function uuid(): string {
  // RFC4122-ish, fine for an anonymous device id.
  const hex = (n: number) => Math.floor(Math.random() * 0xffff).toString(16).padStart(4, '0');
  return `${hex(0)}${hex(0)}-${hex(0)}-${(0x4000 | (Math.random() * 0x0fff)).toString(16)}-${(0x8000 | (Math.random() * 0x3fff)).toString(16)}-${hex(0)}${hex(0)}${hex(0)}`;
}

export async function ensureDeviceId(): Promise<string> {
  let id = await AsyncStorage.getItem(KEY_DEVICE);
  if (!id) {
    id = uuid();
    await AsyncStorage.setItem(KEY_DEVICE, id);
  }
  return id;
}

export async function getDeviceId(): Promise<string | null> {
  return AsyncStorage.getItem(KEY_DEVICE);
}

// -------------------------------------------------------------------------
//  LANGUAGE PREFS — 3-part model (Phase 4 / EU-1)
// -------------------------------------------------------------------------

/** Raw Explanation-Language read — the language the AI writes analyses in.
 *  Used by analyzing/chat/translate API calls. */
export async function getExplanationLang(): Promise<LanguageCode | null> {
  const v = await AsyncStorage.getItem(KEY_LANG);
  return (v as LanguageCode | null) ?? null;
}

export async function setExplanationLang(code: LanguageCode): Promise<void> {
  await AsyncStorage.setItem(KEY_LANG, code);
}

/** Optional UI-chrome override. When null, the resolved app-lang falls back
 *  to the closest UI-translated bundle derived from the explanation pref. */
export async function getAppLangOverride(): Promise<LanguageCode | null> {
  const v = await AsyncStorage.getItem(KEY_APP_LANG_OVERRIDE);
  return (v as LanguageCode | null) ?? null;
}

export async function setAppLangOverride(code: LanguageCode | null): Promise<void> {
  if (code == null) {
    await AsyncStorage.removeItem(KEY_APP_LANG_OVERRIDE);
  } else {
    await AsyncStorage.setItem(KEY_APP_LANG_OVERRIDE, code);
  }
}

/** Resolved App-Language — what every UI-chrome `t()` call should use.
 *  - If the user set an explicit override → that.
 *  - Otherwise → fall back via `toUIStringCode(explanationLang)` so screens
 *    render in whichever of the 7 UI-translated bundles matches best. */
export async function getAppLang(): Promise<LanguageCode> {
  const override = await getAppLangOverride();
  if (override) return override;
  const explanation = await getExplanationLang();
  return toUIStringCode(explanation ?? 'en') as LanguageCode;
}

// -------------------------------------------------------------------------
//  BACK-COMPAT shims — everything here is intentionally unchanged in
//  signature so the 14 existing screens keep working without a refactor.
//  `getLanguage`/`setLanguage` retain their original role: they map to
//  the Explanation-Language pref, which is what the API calls (analyze,
//  chat, translate) expect. UI chrome calls are handled separately via
//  `getAppLang()` / `useAppLang()`.
// -------------------------------------------------------------------------

export async function setLanguage(code: LanguageCode): Promise<void> {
  await setExplanationLang(code);
}

export async function getLanguage(): Promise<LanguageCode | null> {
  return getExplanationLang();
}

// -------------------------------------------------------------------------
//  REPLY-LANGUAGE MODE — "auto" (match detected sender lang, default) or
//  "fixed" (always reply in the user's pinned language).
// -------------------------------------------------------------------------

export type ReplyLangMode = 'auto' | 'fixed';

export async function getReplyLangMode(): Promise<ReplyLangMode> {
  const v = await AsyncStorage.getItem(KEY_REPLY_LANG_MODE);
  return v === 'fixed' ? 'fixed' : 'auto';
}

export async function setReplyLangMode(mode: ReplyLangMode): Promise<void> {
  await AsyncStorage.setItem(KEY_REPLY_LANG_MODE, mode);
}

export async function getReplyLangFixed(): Promise<string | null> {
  return AsyncStorage.getItem(KEY_REPLY_LANG_FIXED);
}

export async function setReplyLangFixed(code: string | null): Promise<void> {
  if (code == null) {
    await AsyncStorage.removeItem(KEY_REPLY_LANG_FIXED);
  } else {
    await AsyncStorage.setItem(KEY_REPLY_LANG_FIXED, code);
  }
}

export async function setOnboarded(): Promise<void> {
  await AsyncStorage.setItem(KEY_ONBOARDED, '1');
}

export async function isOnboarded(): Promise<boolean> {
  const v = await AsyncStorage.getItem(KEY_ONBOARDED);
  return v === '1';
}

// ---- Large-font accessibility mode ----
// Moved to /src/largeFontMode.ts — it owns the render-time scale used by a
// monkey-patched <Text> component so every screen picks up the bump without
// refactoring. Re-exported here for backward compatibility with callers that
// already import from `store`.
export {
  setLargeFontMode,
  isLargeFontModeSync as _isLargeFontSync,
  loadLargeFontMode as getLargeFontMode,
} from './largeFontMode';

// ---- DSGVO consent (active opt-in before first analyze) ----

export interface ConsentRecord {
  acceptedAt: string; // ISO timestamp
  version: 'v1';
}

export async function setConsent(): Promise<void> {
  const record: ConsentRecord = {
    acceptedAt: new Date().toISOString(),
    version: 'v1',
  };
  await AsyncStorage.setItem(KEY_CONSENT, JSON.stringify(record));
}

export async function getConsent(): Promise<ConsentRecord | null> {
  const raw = await AsyncStorage.getItem(KEY_CONSENT);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.acceptedAt === 'string') return parsed as ConsentRecord;
  } catch {
    // fallthrough
  }
  return null;
}

export async function hasConsent(): Promise<boolean> {
  return (await getConsent()) !== null;
}

export async function revokeConsent(): Promise<void> {
  await AsyncStorage.removeItem(KEY_CONSENT);
}

export async function resetAll(): Promise<void> {
  // IMPORTANT: we intentionally KEEP `KEY_DEVICE` here. The device_id is the
  // anchor of the paywall quota on the backend (`usage_records`). Wiping it
  // would let a user reset their free-quota by tapping "Konto löschen",
  // "Neu einrichten" or uninstalling/reinstalling the app.
  //
  // DSGVO Art. 17 is still satisfied because all personal data (analyses,
  // chat messages, original scans, reminders) have already been deleted
  // from the backend via DELETE /history/{device_id} before this call.
  // The bare UUID that remains is pseudonymous and by itself has no
  // personal data attached to it — a fresh `usage_records` entry is
  // created lazily on next use with the same zero-data state.
  await AsyncStorage.multiRemove([
    KEY_LANG,
    KEY_APP_LANG_OVERRIDE,
    KEY_REPLY_LANG_MODE,
    KEY_REPLY_LANG_FIXED,
    // KEY_DEVICE,  ← removed on purpose, see note above
    KEY_ONBOARDED,
    KEY_CONSENT,
  ]);
}

// ---- Transient pending-analysis store (memory only) ----

export interface PendingPage {
  base64: string;
  mimeType: string;
  uri?: string; // local file uri, used only for thumbnails on the camera screen
}

export interface PendingAnalysis {
  pages: PendingPage[];
  /** Stable idempotency key for the resulting /api/analyze call. Generated
   *  the moment the user finalises a capture so retries from the analyzing
   *  error screen reuse the same key and never double-consume usage. */
  idempotencyKey: string;
}

let pending: PendingAnalysis | null = null;

/** Public uuid helper — exposed so other modules (e.g. paywall) can mint
 *  idempotency keys without re-implementing the same logic. */
export function generateIdempotencyKey(): string {
  return uuid();
}

export function setPendingAnalysis(p: { pages: PendingPage[]; idempotencyKey?: string } | null) {
  if (!p) {
    pending = null;
    return;
  }
  pending = {
    pages: p.pages,
    idempotencyKey: p.idempotencyKey || uuid(),
  };
}

export function takePendingAnalysis(): PendingAnalysis | null {
  const p = pending;
  pending = null;
  return p;
}

// Result store for the result screen (avoids passing huge JSON via params)
let lastResult: AnalysisRecord | null = null;

export function setLastResult(r: AnalysisRecord | null) {
  lastResult = r;
}

export function getLastResult(): AnalysisRecord | null {
  return lastResult;
}

// ---- Hook for language so screens re-render on change ----

export function useLanguage(): [LanguageCode | null, (c: LanguageCode) => Promise<void>, boolean] {
  const [lang, setLangState] = useState<LanguageCode | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    getLanguage().then((v) => {
      setLangState(v);
      setLoaded(true);
    });
  }, []);
  const update = async (c: LanguageCode) => {
    await setLanguage(c);
    setLangState(c);
  };
  return [lang, update, loaded];
}

// ---- App-Language hook ---------------------------------------------------
//
// Returns the resolved UI-chrome language: either the user's explicit
// override, or the closest UI-translated fallback derived from the
// explanation language. Screens wanting to render app chrome should use
// this hook; screens firing AI API calls should still use `useLanguage()`
// (which returns the raw explanation pref).
export function useAppLang(): [LanguageCode, (c: LanguageCode | null) => Promise<void>, boolean] {
  const [lang, setLang] = useState<LanguageCode>('en');
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    getAppLang().then((v) => {
      setLang(v);
      setLoaded(true);
    });
  }, []);
  const update = async (c: LanguageCode | null) => {
    await setAppLangOverride(c);
    const resolved = await getAppLang();
    setLang(resolved);
  };
  return [lang, update, loaded];
}

// ---- Reply-Language preference hook --------------------------------------
export function useReplyLangPref(): [
  { mode: ReplyLangMode; fixed: string | null },
  (mode: ReplyLangMode, fixed?: string | null) => Promise<void>,
  boolean,
] {
  const [pref, setPref] = useState<{ mode: ReplyLangMode; fixed: string | null }>({
    mode: 'auto',
    fixed: null,
  });
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    (async () => {
      const [m, f] = await Promise.all([getReplyLangMode(), getReplyLangFixed()]);
      setPref({ mode: m, fixed: f });
      setLoaded(true);
    })();
  }, []);
  const update = async (mode: ReplyLangMode, fixed: string | null = null) => {
    await setReplyLangMode(mode);
    if (mode === 'fixed') {
      await setReplyLangFixed(fixed);
    } else {
      await setReplyLangFixed(null);
    }
    setPref({ mode, fixed: mode === 'fixed' ? fixed : null });
  };
  return [pref, update, loaded];
}
