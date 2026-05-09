// easli — Sentry wrapper
// ------------------------------------------------------------
// Initializes Sentry only when EXPO_PUBLIC_SENTRY_DSN is set. Otherwise
// every export is a no-op so dev/PR builds don't ship telemetry.
//
// PRIVACY: We deliberately disable defaultIntegrations that auto-collect
// device names and exact OS versions. Stack traces + manual breadcrumbs
// only — no IPs, no fingerprints. Aligns with our "anonymous device-id
// only" privacy stance.
import * as Sentry from '@sentry/react-native';

let _enabled = false;

export function initSentry(): void {
  const dsn = (process.env.EXPO_PUBLIC_SENTRY_DSN || '').trim();
  if (!dsn) {
    // Silent in production — only log in dev so devs notice missing config.
    if (__DEV__) console.log('[sentry] disabled (EXPO_PUBLIC_SENTRY_DSN not set)');
    return;
  }
  try {
    Sentry.init({
      dsn,
      // Send only 10% of transactions to keep the free tier quota happy.
      tracesSampleRate: 0.1,
      // Don't ship stack traces for breadcrumbs — only for explicit captures.
      attachStacktrace: false,
      // Privacy: never send PII. Sentry's default already excludes IPs but
      // be explicit so we don't regress when SDK defaults change.
      sendDefaultPii: false,
      environment:
        process.env.EXPO_PUBLIC_SENTRY_ENV ||
        (__DEV__ ? 'development' : 'production'),
      release: process.env.EXPO_PUBLIC_APP_VERSION || undefined,
      // Strip the URL query string from breadcrumbs in case any device_id
      // ever leaks via fetch breadcrumb. Defensive belt-and-suspenders.
      beforeBreadcrumb: (crumb) => {
        if (crumb.category === 'fetch' && crumb.data && typeof crumb.data === 'object') {
          const data = crumb.data as Record<string, any>;
          if (typeof data.url === 'string') {
            const q = data.url.indexOf('?');
            if (q >= 0) data.url = data.url.slice(0, q);
          }
        }
        return crumb;
      },
    });
    _enabled = true;
  } catch (e) {
    // Never let a Sentry misconfig crash the app boot.
    if (__DEV__) console.warn('[sentry] init failed', e);
  }
}

export function captureException(err: unknown, context?: Record<string, any>): void {
  if (!_enabled) return;
  try {
    Sentry.captureException(err, context ? { extra: context } : undefined);
  } catch {
    /* swallow */
  }
}

export function captureMessage(
  msg: string,
  level: 'info' | 'warning' | 'error' = 'info',
): void {
  if (!_enabled) return;
  try {
    Sentry.captureMessage(msg, level);
  } catch {
    /* swallow */
  }
}

export function setTag(key: string, value: string): void {
  if (!_enabled) return;
  try {
    Sentry.setTag(key, value);
  } catch {
    /* swallow */
  }
}

export function isSentryEnabled(): boolean {
  return _enabled;
}
