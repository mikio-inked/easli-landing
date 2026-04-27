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
  // Subscribing to the hook triggers a re-render of the whole Stack when the
  // user flips the toggle — that propagates the new scale to every mounted
  // screen in one frame.
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
          // Keying on fontReady ensures the first render uses the correct
          // scale — avoids a flash of un-zoomed text on cold starts.
          key={fontReady ? 'ready' : 'boot'}
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
