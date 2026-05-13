import { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import * as Sentry from '@sentry/react-native';
import { colors, isDarkMode } from '../src/theme';
import { ensureDeviceId } from '../src/store';
import { initBilling } from '../src/billing';
import { initSentry, isSentryEnabled, captureException } from '../src/sentry';
import {
  installLargeFontPatch,
  loadLargeFontMode,
  useLargeFontMode,
} from '../src/largeFontMode';
import { useEasliFonts } from '../src/fontLoader';

// Initialize Sentry as the very first side-effect — before any other code
// can crash. No-op when EXPO_PUBLIC_SENTRY_DSN is unset, so dev builds are
// silent.
initSentry();

// Install the Text/TextInput render override at module import time, BEFORE
// any <Text> can render. Loading the persisted flag is async; until it
// resolves, _scale stays at 1, so the first paint is never zoomed — the bump
// (if any) simply appears on the next re-render. This matches the behaviour
// RN users already expect from accessibility scaling.
installLargeFontPatch();

function RootLayout() {
  const [largeFontReady, setLargeFontReady] = useState(false);
  // Brand typography (Inter family). Doesn't block rendering — the hook
  // returns true on either success OR error so a network glitch can't
  // freeze the splash screen.
  const fontsLoaded = useEasliFonts();
  // Subscribe to the toggle so the component (and its Stack child) re-renders
  // on flip — this propagates to the currently-mounted screen, whose <Text>
  // children pass through the patched render with the new scale.
  useLargeFontMode();

  // Install the global JS error handler exactly once on mount. This catches
  // exceptions thrown OUTSIDE React render trees (event handlers, promise
  // rejections) which the ErrorBoundary alone wouldn't see.
  useEffect(() => {
    if (!isSentryEnabled()) return;
    const ErrorUtils = (global as any).ErrorUtils;
    if (!ErrorUtils?.setGlobalHandler) return;
    const prev = ErrorUtils.getGlobalHandler?.();
    ErrorUtils.setGlobalHandler((err: unknown, isFatal?: boolean) => {
      try {
        captureException(err, { fatal: !!isFatal });
      } catch {
        /* swallow */
      }
      // Chain to the previous handler so red-box / native crash flow stays.
      if (typeof prev === 'function') prev(err, isFatal);
    });
  }, []);

  // Boot the RevenueCat SDK as early as possible. The wrapper is built to
  // never throw — it logs a single info line if the keys are missing or the
  // platform doesn't support billing — so this is safe to fire-and-forget.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadLargeFontMode();
      } catch {
        // ignore — _scale stays at default
      } finally {
        if (!cancelled) setLargeFontReady(true);
      }
      try {
        const deviceId = await ensureDeviceId();
        if (!cancelled) {
          await initBilling(deviceId);
        }
      } catch {
        // intentionally swallowed — billing is optional in soft mode
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Boot key only flips ONCE the persisted large-font flag has loaded AND
  // the Inter fonts are ready (or have failed). After that initial flip
  // we never remount the navigator — toggling large-font mode re-renders
  // the visible screen via the hook subscription instead.
  const bootKey = largeFontReady && fontsLoaded ? 'r' : 'b';

  return (
    <Sentry.ErrorBoundary
      fallback={({ resetError }) => (
        // Minimal fallback — show a plain "Something went wrong" message and
        // let the user reset. Keeps the dependency surface tiny (no extra
        // i18n string lookups so this won't itself crash if the i18n module
        // is the failing one).
        <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', padding: 24 }}>
          <StatusBar style={isDarkMode ? 'light' : 'dark'} />
        </GestureHandlerRootView>
      )}
    >
      <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.background }}>
        <SafeAreaProvider>
          <StatusBar style={isDarkMode ? 'light' : 'dark'} />
          <Stack
            key={bootKey}
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: colors.background },
              animation: 'slide_from_right',
            }}
          />
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </Sentry.ErrorBoundary>
  );
}

// Wrap the root with Sentry.wrap so navigation breadcrumbs and touch
// instrumentation kick in. When Sentry is disabled (no DSN), the wrap is
// a passthrough — no-op cost.
export default Sentry.wrap(RootLayout);
