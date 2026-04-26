// Web stub for the native document scanner. Metro automatically picks this
// file for web bundles via the .web.ts naming convention, so the actual
// react-native-document-scanner-plugin module — which calls
// TurboModuleRegistry.getEnforcing('DocumentScanner') at import time — is
// never pulled into the web bundle.

export interface ScannedPage {
  base64: string;
  mimeType: 'image/jpeg' | 'image/png';
}

export interface ScanResult {
  status: 'success' | 'cancel' | 'unavailable' | 'error';
  pages: ScannedPage[];
}

export function isNativeScannerAvailable(): boolean {
  return false;
}

export interface ScanOptions {
  maxPages?: number;
  quality?: number;
}

export async function scanDocument(_opts: ScanOptions = {}): Promise<ScanResult> {
  return { status: 'unavailable', pages: [] };
}
