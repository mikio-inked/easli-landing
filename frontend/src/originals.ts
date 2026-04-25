// On-device storage for original documents (opt-in).
// Files are written to FileSystem.documentDirectory (sandboxed per app) which
// iOS automatically encrypts via Data Protection when the device is locked.
// We do NOT send originals to the backend. Only the analysis result lives on
// the server.
//
// Note: expo-file-system/legacy is not implemented on react-native-web. All
// public functions are guarded so they no-op on web (and on any other env
// where the FS APIs throw).

import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';

const IS_WEB = Platform.OS === 'web';
const DIR = (FileSystem.documentDirectory ?? '') + 'klarpost/originals/';

async function ensureDir() {
  if (IS_WEB) return;
  try {
    const info = await FileSystem.getInfoAsync(DIR);
    if (!info.exists) {
      await FileSystem.makeDirectoryAsync(DIR, { intermediates: true });
    }
  } catch {
    // ignore — best-effort directory creation
  }
}

function safeMimeExt(mime: string): string {
  const m = mime.toLowerCase();
  if (m.includes('pdf')) return 'pdf';
  if (m.includes('png')) return 'png';
  if (m.includes('webp')) return 'webp';
  if (m.includes('heic') || m.includes('heif')) return 'heic';
  return 'jpg';
}

export interface OriginalMeta {
  mimeType: string;
  ext: string;
}

export async function saveOriginal(
  analysisId: string,
  base64: string,
  mimeType: string
): Promise<void> {
  if (IS_WEB) return;
  try {
    await ensureDir();
    const ext = safeMimeExt(mimeType);
    const path = `${DIR}${analysisId}.${ext}`;
    await FileSystem.writeAsStringAsync(path, base64, {
      encoding: 'base64' as any,
    });
    await FileSystem.writeAsStringAsync(`${DIR}${analysisId}.json`, JSON.stringify({ mimeType, ext }));
  } catch {
    // Non-fatal: server-side analysis result is what matters.
  }
}

export async function loadOriginal(
  analysisId: string
): Promise<{ base64: string; mimeType: string } | null> {
  if (IS_WEB) return null;
  try {
    const meta = await readMeta(analysisId);
    if (!meta) return null;
    const path = `${DIR}${analysisId}.${meta.ext}`;
    const info = await FileSystem.getInfoAsync(path);
    if (!info.exists) return null;
    const base64 = await FileSystem.readAsStringAsync(path, { encoding: 'base64' as any });
    return { base64, mimeType: meta.mimeType };
  } catch {
    return null;
  }
}

async function readMeta(analysisId: string): Promise<OriginalMeta | null> {
  if (IS_WEB) return null;
  try {
    const metaPath = `${DIR}${analysisId}.json`;
    const info = await FileSystem.getInfoAsync(metaPath);
    if (!info.exists) return null;
    const raw = await FileSystem.readAsStringAsync(metaPath);
    return JSON.parse(raw) as OriginalMeta;
  } catch {
    return null;
  }
}

export async function hasOriginal(analysisId: string): Promise<boolean> {
  if (IS_WEB) return false;
  const meta = await readMeta(analysisId);
  return !!meta;
}

export async function deleteOriginal(analysisId: string): Promise<void> {
  if (IS_WEB) return;
  try {
    const meta = await readMeta(analysisId);
    if (meta) {
      await FileSystem.deleteAsync(`${DIR}${analysisId}.${meta.ext}`, { idempotent: true });
      await FileSystem.deleteAsync(`${DIR}${analysisId}.json`, { idempotent: true });
    }
  } catch {
    // ignore
  }
}

export async function deleteAllOriginals(): Promise<void> {
  if (IS_WEB) return;
  try {
    const info = await FileSystem.getInfoAsync(DIR);
    if (!info.exists) return;
    await FileSystem.deleteAsync(DIR, { idempotent: true });
  } catch {
    // ignore
  }
}
