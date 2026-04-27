// Lightweight global app store for KlarPost.
// Persists language + device id to AsyncStorage; keeps a transient pending
// analysis payload (base64) in memory only — original documents are NEVER
// persisted by default.

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import type { AnalysisRecord } from './api';
import { LanguageCode } from './i18n';

const KEY_LANG = 'klarpost.language';
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

export async function setLanguage(code: LanguageCode): Promise<void> {
  await AsyncStorage.setItem(KEY_LANG, code);
}

export async function getLanguage(): Promise<LanguageCode | null> {
  const v = await AsyncStorage.getItem(KEY_LANG);
  return (v as LanguageCode | null) ?? null;
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
  await AsyncStorage.multiRemove([KEY_LANG, KEY_DEVICE, KEY_ONBOARDED, KEY_CONSENT]);
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
