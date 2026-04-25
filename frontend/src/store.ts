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

export async function resetAll(): Promise<void> {
  await AsyncStorage.multiRemove([KEY_LANG, KEY_DEVICE, KEY_ONBOARDED]);
}

// ---- Transient pending-analysis store (memory only) ----

export interface PendingAnalysis {
  base64: string;
  mimeType: string;
}

let pending: PendingAnalysis | null = null;

export function setPendingAnalysis(p: PendingAnalysis | null) {
  pending = p;
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
