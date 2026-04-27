import { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { colors } from '../src/theme';
import { ensureDeviceId } from '../src/store';
import { initBilling } from '../src/billing';
import {
  installLargeFontPatch,
  loadLargeFontMode,
  useLargeFontMode,
} from '../src/largeFontMode';

// Install the Text/TextInput render override at module import time, BEFORE
// any <Text> can render. Loading the persisted flag is async; until it
// resolves, _scale stays at 1, so the first paint is never zoomed — the bump
// (if any) simply appears on the next re-render. This matches the behaviour
// RN users already expect from accessibility scaling.
installLargeFontPatch();

export default function RootLayout() {
  const [fontReady, setFontReady] = useState(false);
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
        if (!cancelled) setFontReady(true);
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

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.background }}>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        <Stack
          // Only re-key on the initial font-flag load — NOT on every toggle,
          // because remounting the navigator would reset transient screen
          // state (e.g. the user's language pick on the onboarding screen).
          // Toggling large-font mode re-renders the currently-visible screen
          // through the hook subscription, and the patched <Text> render
          // function picks up the new scale on the very next paint.
          key={fontReady ? 'r' : 'b'}
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
