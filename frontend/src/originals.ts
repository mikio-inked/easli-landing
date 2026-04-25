// On-device storage for original documents (opt-in).
// Files are written to FileSystem.documentDirectory (sandboxed per app) which
// iOS automatically encrypts via Data Protection when the device is locked.
// We do NOT send originals to the backend. Only the analysis result lives on
// the server.

import * as FileSystem from 'expo-file-system/legacy';

const DIR = (FileSystem.documentDirectory ?? '') + 'klarpost/originals/';

async function ensureDir() {
  const info = await FileSystem.getInfoAsync(DIR);
  if (!info.exists) {
    await FileSystem.makeDirectoryAsync(DIR, { intermediates: true });
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
  await ensureDir();
  const ext = safeMimeExt(mimeType);
  const path = `${DIR}${analysisId}.${ext}`;
  await FileSystem.writeAsStringAsync(path, base64, {
    encoding: 'base64' as any,
  });
  // Store mime alongside as a tiny .json manifest so we can reconstruct later.
  await FileSystem.writeAsStringAsync(`${DIR}${analysisId}.json`, JSON.stringify({ mimeType, ext }));
}

export async function loadOriginal(
  analysisId: string
): Promise<{ base64: string; mimeType: string } | null> {
  const meta = await readMeta(analysisId);
  if (!meta) return null;
  const path = `${DIR}${analysisId}.${meta.ext}`;
  const info = await FileSystem.getInfoAsync(path);
  if (!info.exists) return null;
  const base64 = await FileSystem.readAsStringAsync(path, { encoding: 'base64' as any });
  return { base64, mimeType: meta.mimeType };
}

async function readMeta(analysisId: string): Promise<OriginalMeta | null> {
  const metaPath = `${DIR}${analysisId}.json`;
  const info = await FileSystem.getInfoAsync(metaPath);
  if (!info.exists) return null;
  try {
    const raw = await FileSystem.readAsStringAsync(metaPath);
    return JSON.parse(raw) as OriginalMeta;
  } catch {
    return null;
  }
}

export async function hasOriginal(analysisId: string): Promise<boolean> {
  const meta = await readMeta(analysisId);
  return !!meta;
}

export async function deleteOriginal(analysisId: string): Promise<void> {
  const meta = await readMeta(analysisId);
  if (meta) {
    await FileSystem.deleteAsync(`${DIR}${analysisId}.${meta.ext}`, { idempotent: true });
    await FileSystem.deleteAsync(`${DIR}${analysisId}.json`, { idempotent: true });
  }
}

export async function deleteAllOriginals(): Promise<void> {
  const info = await FileSystem.getInfoAsync(DIR);
  if (!info.exists) return;
  await FileSystem.deleteAsync(DIR, { idempotent: true });
}
