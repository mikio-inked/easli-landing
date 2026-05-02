// Font loader for the easli rebrand. Loads the Inter family at app boot
// and exposes a hook so the root layout can defer rendering until the
// fonts are ready (prevents a flash of fallback text).
//
// The fallback path is graceful: if the font network fetch fails (rare —
// expo-google-fonts caches aggressively), we still render the app with the
// platform default. Users who never load the font once will see the
// system sans-serif until they get back online.

import { useFonts as useInterFonts } from 'expo-font';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
  Inter_800ExtraBold,
} from '@expo-google-fonts/inter';

/** Returns true once fonts are loaded (or font-load failed — we don't
 *  block the UI on a network failure). */
export function useEasliFonts(): boolean {
  const [loaded, error] = useInterFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    Inter_800ExtraBold,
  });
  // Treat both success AND error as "ready" so a network glitch doesn't
  // freeze the splash screen forever.
  return loaded || !!error;
}
