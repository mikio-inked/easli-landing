// On-device storage for original documents (opt-in).
// Files are written to FileSystem.documentDirectory (sandboxed per app) which
// iOS automatically encrypts via Data Protection when the device is locked.
// We do NOT send originals to the backend. Only the analysis result lives on
// the server.
//
// Note: expo-file-system/legacy is not implemented on react-native-web. All
// public functions are guarded so they no-op on web (and on any other env
// where the FS APIs throw).
//
// Diagnostics layer (see also `src/storageDiag.ts`): every save/load/delete
// records a brief breadcrumb so the Settings → Storage card can show a real
// count, total size, and the last error to the user — turning the "did this
// even work?" question into a visible answer.

import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';

const IS_WEB = Platform.OS === 'web';
const DIR = (FileSystem.documentDirectory ?? '') + 'klarpost/originals/';

const ERROR_LOG_KEY = 'klarpost.storageErrors.v1';
const MAX_ERRORS = 10;

export interface StoredOriginalMeta {
  /** Analysis ID this original belongs to. */
  id: string;
  mimeType: string;
  ext: string;
  /** Absolute size in bytes (file system reported). */
  sizeBytes: number;
  /** ISO timestamp when file was last modified, or empty if unknown. */
  modifiedAtIso: string;
}

export interface StorageStats {
  count: number;
  totalBytes: number;
  /** Direct path to the storage directory (for diagnostics). */
  dir: string;
  /** True if writing to disk is supported on this platform/runtime. */
  available: boolean;
}

export interface StorageError {
  at: string; // ISO
  op: 'save' | 'load' | 'delete' | 'list' | 'self-test';
  analysisId?: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function ensureDir() {
  if (IS_WEB) return;
  try {
    const info = await FileSystem.getInfoAsync(DIR);
    if (!info.exists) {
      await FileSystem.makeDirectoryAsync(DIR, { intermediates: true });
    }
  } catch (e) {
    await logError('save', undefined, errToMessage(e));
    throw e;
  }
}

function safeMimeExt(mime: string): string {
  const m = (mime ?? '').toLowerCase();
  if (m.includes('pdf')) return 'pdf';
  if (m.includes('png')) return 'png';
  if (m.includes('webp')) return 'webp';
  if (m.includes('heic') || m.includes('heif')) return 'heic';
  return 'jpg';
}

function errToMessage(e: unknown): string {
  if (e instanceof Error) return e.message || String(e);
  if (typeof e === 'string') return e;
  try {
    return JSON.stringify(e);
  } catch {
    return 'Unknown error';
  }
}

// ---------------------------------------------------------------------------
// Error log (visible in Settings → Storage diagnostics card)
// ---------------------------------------------------------------------------

async function logError(
  op: StorageError['op'],
  analysisId: string | undefined,
  message: string,
): Promise<void> {
  try {
    const raw = await AsyncStorage.getItem(ERROR_LOG_KEY);
    const list: StorageError[] = raw ? (JSON.parse(raw) as StorageError[]) : [];
    list.unshift({ at: new Date().toISOString(), op, analysisId, message });
    while (list.length > MAX_ERRORS) list.pop();
    await AsyncStorage.setItem(ERROR_LOG_KEY, JSON.stringify(list));
  } catch {
    // logging failures are intentionally swallowed
  }
}

export async function getStorageErrors(): Promise<StorageError[]> {
  try {
    const raw = await AsyncStorage.getItem(ERROR_LOG_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as StorageError[];
  } catch {
    return [];
  }
}

export async function clearStorageErrors(): Promise<void> {
  try {
    await AsyncStorage.removeItem(ERROR_LOG_KEY);
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// Save / load / delete
// ---------------------------------------------------------------------------

/**
 * Save an original document for `analysisId`. Returns `true` on success.
 * Errors are recorded in the diagnostic log and surfaced via the return
 * value so callers (e.g. analyzing.tsx) can show a banner to the user
 * instead of silently swallowing the failure.
 */
export async function saveOriginal(
  analysisId: string,
  base64: string,
  mimeType: string,
): Promise<boolean> {
  if (IS_WEB) return false;
  try {
    await ensureDir();
    const ext = safeMimeExt(mimeType);
    const path = `${DIR}${analysisId}.${ext}`;
    await FileSystem.writeAsStringAsync(path, base64, {
      encoding: 'base64' as never,
    });
    await FileSystem.writeAsStringAsync(
      `${DIR}${analysisId}.json`,
      JSON.stringify({ mimeType, ext }),
    );
    return true;
  } catch (e) {
    await logError('save', analysisId, errToMessage(e));
    return false;
  }
}

export async function loadOriginal(
  analysisId: string,
): Promise<{ base64: string; mimeType: string } | null> {
  if (IS_WEB) return null;
  try {
    const meta = await readMeta(analysisId);
    if (!meta) return null;
    const path = `${DIR}${analysisId}.${meta.ext}`;
    const info = await FileSystem.getInfoAsync(path);
    if (!info.exists) return null;
    const base64 = await FileSystem.readAsStringAsync(path, {
      encoding: 'base64' as never,
    });
    return { base64, mimeType: meta.mimeType };
  } catch (e) {
    await logError('load', analysisId, errToMessage(e));
    return null;
  }
}

async function readMeta(
  analysisId: string,
): Promise<{ mimeType: string; ext: string } | null> {
  if (IS_WEB) return null;
  try {
    const metaPath = `${DIR}${analysisId}.json`;
    const info = await FileSystem.getInfoAsync(metaPath);
    if (!info.exists) return null;
    const raw = await FileSystem.readAsStringAsync(metaPath);
    return JSON.parse(raw) as { mimeType: string; ext: string };
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
      await FileSystem.deleteAsync(`${DIR}${analysisId}.${meta.ext}`, {
        idempotent: true,
      });
      await FileSystem.deleteAsync(`${DIR}${analysisId}.json`, {
        idempotent: true,
      });
    }
  } catch (e) {
    await logError('delete', analysisId, errToMessage(e));
  }
}

export async function deleteAllOriginals(): Promise<void> {
  if (IS_WEB) return;
  try {
    const info = await FileSystem.getInfoAsync(DIR);
    if (!info.exists) return;
    await FileSystem.deleteAsync(DIR, { idempotent: true });
  } catch (e) {
    await logError('delete', undefined, errToMessage(e));
  }
}

// ---------------------------------------------------------------------------
// Diagnostics — used by Settings storage card and history indicator
// ---------------------------------------------------------------------------

/**
 * Returns lightweight stats (count + total bytes) about every saved original.
 * Designed to be called from a Settings screen.
 */
export async function getStorageStats(): Promise<StorageStats> {
  const baseDir = DIR;
  if (IS_WEB) {
    return { count: 0, totalBytes: 0, dir: baseDir, available: false };
  }
  try {
    const info = await FileSystem.getInfoAsync(baseDir);
    if (!info.exists) {
      return { count: 0, totalBytes: 0, dir: baseDir, available: true };
    }
    const files = await FileSystem.readDirectoryAsync(baseDir);
    // We count only the .json sidecars (one per saved original) so the
    // count reflects "how many originals are stored", not files-on-disk.
    const sidecars = files.filter((f) => f.endsWith('.json'));
    let totalBytes = 0;
    for (const name of files) {
      try {
        const f = await FileSystem.getInfoAsync(baseDir + name, { size: true });
        if (f.exists && typeof (f as { size?: number }).size === 'number') {
          totalBytes += (f as { size: number }).size;
        }
      } catch {
        // skip — best-effort stat
      }
    }
    return {
      count: sidecars.length,
      totalBytes,
      dir: baseDir,
      available: true,
    };
  } catch (e) {
    await logError('list', undefined, errToMessage(e));
    return { count: 0, totalBytes: 0, dir: baseDir, available: true };
  }
}

/**
 * Returns the list of all originals on disk with size + mtime. Used by the
 * Settings storage detail screen.
 */
export async function listStoredOriginals(): Promise<StoredOriginalMeta[]> {
  if (IS_WEB) return [];
  try {
    const info = await FileSystem.getInfoAsync(DIR);
    if (!info.exists) return [];
    const files = await FileSystem.readDirectoryAsync(DIR);
    const sidecars = files.filter((f) => f.endsWith('.json'));
    const out: StoredOriginalMeta[] = [];
    for (const sidecar of sidecars) {
      const id = sidecar.replace(/\.json$/, '');
      const meta = await readMeta(id);
      if (!meta) continue;
      const fullPath = `${DIR}${id}.${meta.ext}`;
      let sizeBytes = 0;
      let modifiedAtIso = '';
      try {
        const f = await FileSystem.getInfoAsync(fullPath, { size: true });
        if (f.exists) {
          const fi = f as { size?: number; modificationTime?: number };
          sizeBytes = typeof fi.size === 'number' ? fi.size : 0;
          if (typeof fi.modificationTime === 'number') {
            // expo-file-system returns Unix seconds (float).
            modifiedAtIso = new Date(fi.modificationTime * 1000).toISOString();
          }
        }
      } catch {
        // ignore — keep zeros
      }
      out.push({ id, mimeType: meta.mimeType, ext: meta.ext, sizeBytes, modifiedAtIso });
    }
    // Newest first
    out.sort((a, b) => (a.modifiedAtIso < b.modifiedAtIso ? 1 : -1));
    return out;
  } catch (e) {
    await logError('list', undefined, errToMessage(e));
    return [];
  }
}

/**
 * Returns the set of analysis IDs that have a saved original. Used by the
 * history list to render a "saved offline" indicator without doing N file
 * stat calls per item.
 */
export async function getStoredOriginalIds(): Promise<Set<string>> {
  if (IS_WEB) return new Set();
  try {
    const info = await FileSystem.getInfoAsync(DIR);
    if (!info.exists) return new Set();
    const files = await FileSystem.readDirectoryAsync(DIR);
    const ids = new Set<string>();
    for (const f of files) {
      if (f.endsWith('.json')) ids.add(f.replace(/\.json$/, ''));
    }
    return ids;
  } catch {
    return new Set();
  }
}

/**
 * Performs a round-trip self test: write a tiny test file, read it back,
 * verify content, delete it. Used by the Settings → Storage diagnostic
 * "Run test" button to give the user instant confidence the storage layer
 * is working on their device.
 */
export async function runStorageSelfTest(): Promise<{ ok: boolean; error?: string; details?: string }> {
  if (IS_WEB) {
    return { ok: false, error: 'Web platform: local storage is not supported' };
  }
  const testId = `__selftest_${Date.now()}`;
  const testPath = `${DIR}${testId}.txt`;
  try {
    await ensureDir();
    const payload = `klarpost-selftest-${testId}`;
    await FileSystem.writeAsStringAsync(testPath, payload);
    const info = await FileSystem.getInfoAsync(testPath, { size: true });
    if (!info.exists) {
      return { ok: false, error: 'File was written but not found on disk' };
    }
    const readBack = await FileSystem.readAsStringAsync(testPath);
    if (readBack !== payload) {
      return { ok: false, error: 'Read content did not match what was written' };
    }
    await FileSystem.deleteAsync(testPath, { idempotent: true });
    return {
      ok: true,
      details: `Wrote ${(info as { size?: number }).size ?? payload.length} bytes, read+verified, deleted.`,
    };
  } catch (e) {
    const msg = errToMessage(e);
    await logError('self-test', undefined, msg);
    // Best-effort cleanup if the read/delete failed mid-way.
    try {
      await FileSystem.deleteAsync(testPath, { idempotent: true });
    } catch {
      // ignore
    }
    return { ok: false, error: msg };
  }
}

/** Pretty-print bytes for diagnostics UI ("3.2 MB" etc). */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let idx = 0;
  let val = bytes;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[idx]}`;
}
