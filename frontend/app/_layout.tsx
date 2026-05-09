import { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { colors } from '../src/theme';
import { ensureDeviceId } from '../src/store';
import { initBilling } from '../src/billing';
import { initSentry } from '../src/sentry';
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

export default function RootLayout() {
  const [largeFontReady, setLargeFontReady] = useState(false);
  // Brand typography (Inter family). Doesn't block rendering — the hook
  // returns true on either success OR error so a network glitch can't
  // freeze the splash screen.
  const fontsLoaded = useEasliFonts();
  // Subscribe to the toggle so the component (and its Stack child) re-renders
  // on flip — this propagates to the currently-mounted screen, whose <Text>
  // children pass through the patched render with the new scale.
  useLargeFontMode();

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
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.background }}>
      <SafeAreaProvider>
        <StatusBar style="dark" />
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
  );
}
