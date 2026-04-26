// RevenueCat wrapper with graceful fallback.
//
// Design goals:
//   1. The app MUST NOT crash if the RevenueCat SDK keys are missing or if
//      the SDK itself fails to load (e.g. on the web preview build).
//   2. When billing is unavailable, every public function in this module
//      returns a sensible fallback ("not available") so callers can render
//      the friendly German "Zahlungen nicht verfügbar" UI.
//   3. Initialization is idempotent and uses the existing anonymous
//      device_id as the RevenueCat `appUserID`.
//   4. We never log the RevenueCat key, the customer info object, or any
//      raw purchase identifiers beyond the product_id we already display.

import { Platform } from 'react-native';

// Pick the platform-specific public key. Empty string when the .env hasn't
// been wired up yet (TestFlight / APK testing).
const RC_PUBLIC_KEY = (Platform.select<string>({
  ios: process.env.EXPO_PUBLIC_REVENUECAT_IOS_PUBLIC_KEY,
  android: process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_PUBLIC_KEY,
  default: '',
}) || '').trim();

// Stable product / entitlement IDs. These mirror what the Apple App Store
// Connect, Google Play Console, and RevenueCat dashboards must define.
// Keeping them centralised here means the paywall screen never has magic
// strings.
export const PRODUCT_IDS = {
  singleLetter: 'klarpost_single_letter',
  plusMonthly: 'klarpost_plus_monthly',
  plusYearly: 'klarpost_plus_yearly',
} as const;

export const PLUS_ENTITLEMENT_ID = 'plus';

export class PaymentsUnavailableError extends Error {
  constructor(message: string = 'Payments unavailable in this build') {
    super(message);
    this.name = 'PaymentsUnavailableError';
  }
}

export class PurchaseCancelledError extends Error {
  constructor() {
    super('Purchase cancelled');
    this.name = 'PurchaseCancelledError';
  }
}

// ---- module-private state ----
let _initialized = false;
let _available = false;
let _initPromise: Promise<boolean> | null = null;
let _Purchases: any | null = null; // lazy-loaded ESM default export

/** Public flag — call from screens to decide whether to render real
 *  purchase buttons or the "not available in test build" placeholder. */
export function isBillingAvailable(): boolean {
  return _available;
}

/** Lazy-load the SDK so a missing native module on web doesn't crash the
 *  app at boot time. */
async function _loadSdk(): Promise<any | null> {
  if (_Purchases) return _Purchases;
  try {
    const mod = await import('react-native-purchases');
    _Purchases = mod.default ?? mod;
    return _Purchases;
  } catch (e) {
    // Native module not available (web preview, EAS without prebuild, ...).
    // We swallow the error and stay in "not available" mode.
    return null;
  }
}

/** Initialize RevenueCat once for this app instance.
 *
 *  Returns true if the SDK is configured and ready for purchases, false
 *  otherwise. Safe to call repeatedly — concurrent callers share the same
 *  init promise.
 */
export async function initBilling(deviceId: string): Promise<boolean> {
  if (_initialized) return _available;
  if (_initPromise) return _initPromise;

  _initPromise = (async () => {
    _initialized = true;

    if (!RC_PUBLIC_KEY) {
      // Empty key — keep in fallback mode. Don't call console.log with the
      // env var name to avoid grepping the log for keys.
      console.info('[billing] disabled — no RevenueCat public key configured');
      return false;
    }
    if (Platform.OS === 'web') {
      // The web preview build is NOT a billable surface; degrade silently.
      console.info('[billing] disabled — web platform');
      return false;
    }

    const Purchases = await _loadSdk();
    if (!Purchases) {
      console.info('[billing] disabled — SDK module unavailable');
      return false;
    }

    try {
      // WARN-level by default so the SDK doesn't spam the console.
      if (Purchases.LOG_LEVEL?.WARN !== undefined) {
        Purchases.setLogLevel(Purchases.LOG_LEVEL.WARN);
      }
      await Purchases.configure({ apiKey: RC_PUBLIC_KEY, appUserID: deviceId });
      _available = true;
      return true;
    } catch (e) {
      // Network failure / Play Billing missing on APK / etc. Stay in
      // graceful-fallback mode so the rest of the app keeps working.
      console.info('[billing] disabled — configure failed');
      return false;
    }
  })();

  return _initPromise;
}

/** RevenueCat offerings for the current app/user.
 *
 *  Returns the "current" offering object as-is from the SDK, or null if
 *  billing is not available. Callers should still render their hard-coded
 *  fallback prices when this returns null.
 */
export async function getCurrentOffering(): Promise<any | null> {
  if (!_available || !_Purchases) return null;
  try {
    const offerings = await _Purchases.getOfferings();
    return offerings?.current ?? null;
  } catch {
    return null;
  }
}

/** Map our internal product IDs to packages inside the RevenueCat offering. */
export function findPackageForProductId(offering: any, productId: string): any | null {
  if (!offering) return null;
  const candidates: any[] = [
    ...(offering.availablePackages || []),
    offering.lifetime,
    offering.annual,
    offering.sixMonth,
    offering.threeMonth,
    offering.twoMonth,
    offering.monthly,
    offering.weekly,
    offering.custom,
  ];
  for (const pkg of candidates) {
    if (!pkg) continue;
    const pid = pkg?.product?.identifier || pkg?.productIdentifier;
    if (pid && pid === productId) return pkg;
  }
  return null;
}

export interface PurchaseResult {
  customerInfo: any;
  productIdentifier: string;
}

/** Run a real RevenueCat purchase. Throws PaymentsUnavailableError when
 *  billing is not configured, PurchaseCancelledError when the user backs out,
 *  and a generic Error for everything else. */
export async function purchasePackage(pkg: any): Promise<PurchaseResult> {
  if (!_available || !_Purchases) {
    throw new PaymentsUnavailableError();
  }
  try {
    const res = await _Purchases.purchasePackage(pkg);
    return {
      customerInfo: res.customerInfo,
      productIdentifier: res.productIdentifier,
    };
  } catch (e: any) {
    if (e?.userCancelled) {
      throw new PurchaseCancelledError();
    }
    throw e;
  }
}

/** Restore previous purchases. Returns the freshly-fetched customer info,
 *  or throws PaymentsUnavailableError when billing is disabled. */
export async function restorePurchases(): Promise<any> {
  if (!_available || !_Purchases) {
    throw new PaymentsUnavailableError();
  }
  return await _Purchases.restorePurchases();
}

/** Check whether the user currently has the `plus` entitlement active. */
export async function hasActivePlus(): Promise<boolean> {
  if (!_available || !_Purchases) return false;
  try {
    const info = await _Purchases.getCustomerInfo();
    return !!info?.entitlements?.active?.[PLUS_ENTITLEMENT_ID];
  } catch {
    return false;
  }
}

/** Update the RevenueCat user id. Used when the device_id is regenerated. */
export async function setBillingUserId(deviceId: string): Promise<void> {
  if (!_available || !_Purchases) return;
  try {
    await _Purchases.logIn(deviceId);
  } catch {
    /* swallow */
  }
}
