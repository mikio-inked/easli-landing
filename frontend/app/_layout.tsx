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
  // user flips the toggle. We then bump the Stack's `key` so React fully
  // remounts the navigator — this guarantees every screen's <Text> is freshly
  // rendered through the patched render fn with the new scale, even on
  // platforms where some Text instances aggressively memoise their styles.
  const [largeFont] = useLargeFontMode();

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
          // Re-key on (a) initial font-flag load and (b) every toggle so the
          // entire navigator remounts and every <Text> goes through the
          // patched render with the new scale. The slight mount/unmount cost
          // is negligible compared to the accessibility win.
          key={`${fontReady ? 'r' : 'b'}-${largeFont ? 'lg' : 'sm'}`}
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
