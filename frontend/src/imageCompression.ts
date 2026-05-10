// Image compression helper used right before /api/analyze.
//
// Why this exists:
//   The native VisionKit / ML Kit document scanner ships pages at the
//   capture-device's full resolution (e.g. 3000 x 4000 px ≈ 5-8 MB JPEG per
//   page). Uploading 4 such pages over LTE is 25-40 MB of body and routinely
//   pushes the request past iOS URLSession's default 60 s timeout. We've seen
//   real users hit "AI analysis failed" toasts because the upload itself
//   never reached our backend.
//
//   The fix is to downscale every page to vision-friendly dimensions before
//   the network hop. Mistral Vision happily reads German letters at 1600 px
//   width (more than enough for OCR), so we can shrink 5-8 MB down to
//   ~80-200 KB per page with no perceptible quality loss for the user.
//
// PRIVACY: this module never logs the base64 string, the file URI, or any
// content derived from the page. Only sizes (input vs output bytes) are
// logged via console.log so dev tooling shows the win, but those lines do
// not contain any document content.
//
// Web compatibility: expo-image-manipulator works on web via canvas, so the
// same code runs in the Expo preview AND on iOS / Android. Pages from the
// existing /camera (manual capture) and /upload (library picker) flows pass
// through here too — we treat all paths uniformly.

import { manipulateAsync, SaveFormat } from 'expo-image-manipulator';
import type { PendingPage } from './store';

/** Above this base64 size we always re-encode. ~600 KB binary ≈ 800 KB b64. */
const COMPRESS_THRESHOLD_BYTES = 600 * 1024;

/** Mistral Vision is happy at this resolution; matches the backend post-OCR
 *  cap so we don't double-process. */
const MAX_VISION_WIDTH_PX = 1600;
const JPEG_QUALITY = 0.7;

/** Quick base64 → binary-bytes estimate. Avoids decoding the whole string. */
function estimateBinaryBytes(b64: string): number {
  return Math.floor((b64.length * 3) / 4);
}

/**
 * Compress one page if it's large enough to be worth it. Always returns
 * a PendingPage — even on failure we fall back to the original payload so
 * the upload path is never *blocked* by compression.
 */
export async function compressPageForUpload(
  page: PendingPage,
  pageIndex: number,
): Promise<PendingPage> {
  const sizeBefore = estimateBinaryBytes(page.base64);
  if (sizeBefore <= COMPRESS_THRESHOLD_BYTES) {
    // Already small — skip. Library-picked images and small scans land here.
    return page;
  }

  try {
    // ImageManipulator accepts a base64 data URI directly on iOS / Android /
    // web — no temp file needed.
    const dataUri = `data:${page.mimeType};base64,${page.base64}`;
    const result = await manipulateAsync(
      dataUri,
      [{ resize: { width: MAX_VISION_WIDTH_PX } }],
      {
        compress: JPEG_QUALITY,
        format: SaveFormat.JPEG,
        base64: true,
      },
    );

    if (!result.base64) {
      // Defensive: shouldn't happen because we asked for base64.
      if (__DEV__) {
        // eslint-disable-next-line no-console
        console.log(
          `[compress] page=${pageIndex} no_base64_in_result — passing original through`,
        );
      }
      return page;
    }

    const sizeAfter = estimateBinaryBytes(result.base64);
    // Privacy: log only sizes, NEVER the base64 itself.
    if (__DEV__) {
      // eslint-disable-next-line no-console
      console.log(
        `[compress] page=${pageIndex} before=${sizeBefore}B after=${sizeAfter}B ratio=${(sizeAfter / sizeBefore).toFixed(2)}`,
      );
    }

    return {
      base64: result.base64,
      mimeType: 'image/jpeg',
    };
  } catch (e: any) {
    // Privacy: log only the error type, not the exception payload (which on
    // some platforms can include the file URI).
    console.log(
      `[compress] page=${pageIndex} failed type=${e?.name ?? 'Unknown'} — passing original through`,
    );
    return page;
  }
}

/**
 * Compress all pages in parallel. Order is preserved.
 */
export async function compressPagesForUpload(
  pages: PendingPage[],
): Promise<PendingPage[]> {
  if (pages.length === 0) return pages;
  return Promise.all(pages.map((p, i) => compressPageForUpload(p, i)));
}
