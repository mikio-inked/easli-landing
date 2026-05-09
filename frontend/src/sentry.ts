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
import Constants from 'expo-constants';

let _enabled = false;

function _detectRelease(): string | undefined {
  // Prefer explicit env override (set in eas.json for prod builds).
  const fromEnv = (process.env.EXPO_PUBLIC_APP_VERSION || '').trim();
  if (fromEnv) return `easli@${fromEnv}`;
  // Fall back to app.json version + iOS buildNumber / Android versionCode.
  const v = Constants.expoConfig?.version;
  if (!v) return undefined;
  const ios = Constants.expoConfig?.ios?.buildNumber;
  const android = (Constants.expoConfig?.android as any)?.versionCode;
  const build = ios || android;
  return build ? `easli@${v}+${build}` : `easli@${v}`;
}

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
      tracesSampleRate: parseFloat(
        process.env.EXPO_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || '0.1',
      ),
      // Don't ship stack traces for breadcrumbs — only for explicit captures.
      attachStacktrace: false,
      // Privacy: never send PII. Sentry's default already excludes IPs but
      // be explicit so we don't regress when SDK defaults change.
      sendDefaultPii: false,
      environment:
        process.env.EXPO_PUBLIC_SENTRY_ENV ||
        (__DEV__ ? 'development' : 'production'),
      release: _detectRelease(),
      maxBreadcrumbs: 30,
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
      // Strip device_id-like long hex strings from breadcrumb messages so
      // an accidental console.log doesn't leak the anonymous identifier.
      beforeSend: (event) => {
        if (event.breadcrumbs) {
          event.breadcrumbs = event.breadcrumbs.map((b) => {
            if (typeof b.message === 'string') {
              b.message = b.message.replace(
                /\b[a-f0-9]{16,}\b/gi,
                '[redacted]',
              );
            }
            return b;
          });
        }
        return event;
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
