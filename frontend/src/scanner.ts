// Native (iOS / Android) wrapper around react-native-document-scanner-plugin.
//
// On iOS this hands off to Apple VisionKit (VNDocumentCameraViewController) —
// the same scanner used by Notes / Files — with automatic edge detection,
// auto-capture, perspective correction and multi-page stacking.
// On Android the plugin uses Google ML Kit Document Scanner with the same
// feature set.
//
// Metro picks this file for ios/android; the parallel `scanner.web.ts` file
// is loaded for web bundles and just returns 'unavailable' so the UI can
// fall back to the manual flow.

import DocumentScanner, {
  ResponseType,
  ScanDocumentResponseStatus,
} from 'react-native-document-scanner-plugin';

export interface ScannedPage {
  base64: string;
  mimeType: 'image/jpeg' | 'image/png';
}

export interface ScanResult {
  status: 'success' | 'cancel' | 'unavailable' | 'error';
  pages: ScannedPage[];
}

export function isNativeScannerAvailable(): boolean {
  return true;
}

export interface ScanOptions {
  /** Maximum number of pages allowed in this single scan session. */
  maxPages?: number;
  /** JPEG quality 0–100, default 80 (good OCR quality, tighter payload). */
  quality?: number;
}

export async function scanDocument(opts: ScanOptions = {}): Promise<ScanResult> {
  try {
    const res = await DocumentScanner.scanDocument({
      croppedImageQuality: opts.quality ?? 80,
      maxNumDocuments: opts.maxPages ?? 10,
      // Base64 directly avoids the file→read→base64 round-trip and lets us
      // garbage-collect the temp files immediately after the scanner call.
      responseType: ResponseType.Base64,
    });

    if (res.status !== ScanDocumentResponseStatus.Success) {
      return { status: 'cancel', pages: [] };
    }
    const images = res.scannedImages ?? [];
    if (images.length === 0) {
      return { status: 'cancel', pages: [] };
    }
    return {
      status: 'success',
      pages: images.map((b64) => ({
        base64: b64,
        mimeType: 'image/jpeg' as const,
      })),
    };
  } catch {
    // Privacy: don't leak the error object — it could carry the document
    // path or buffer reference. We surface only a generic 'error' status.
    return { status: 'error', pages: [] };
  }
}
