// App-wide font scaling for accessibility / elderly-friendly mode.
//
// Strategy: monkey-patch React Native's built-in Text component so every
// `<Text>` in the tree receives a scaled `fontSize` (and `lineHeight`) without
// requiring every individual screen to be refactored. The patch is installed
// ONCE at module load time — before the first <Text> is rendered — and reads
// a module-level `_scale` variable that is kept in sync with AsyncStorage.
//
// Why monkey-patching and not a theme context?
// KlarPost already has 20+ screens with hard-coded fontSize values from the
// theme token set. Threading a hook through every screen would be noisy and
// slow to roll out, and we want one toggle to instantly upscale everything
// (headings, buttons, list items, modals). The override respects any fontSize
// authors have set locally — it simply multiplies by the current scale.

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import { StyleSheet, Text as RNText, TextInput as RNTextInput } from 'react-native';

const KEY_LARGE_FONT = 'klarpost.largeFont';
const LARGE_SCALE = 1.18; // +18% — comfortable bump without breaking layouts

// Module-level state kept in sync with AsyncStorage. Read synchronously inside
// the patched render function so toggling takes effect on next re-render.
let _scale = 1;
let _installed = false;
const listeners = new Set<() => void>();

function scaleStyle(style: unknown): unknown {
  if (_scale === 1 || style == null) return style;
  const flat = StyleSheet.flatten(style as never) as Record<string, unknown> | null;
  if (!flat) return style;
  const next: Record<string, unknown> = { ...flat };
  if (typeof flat.fontSize === 'number') next.fontSize = (flat.fontSize as number) * _scale;
  if (typeof flat.lineHeight === 'number') next.lineHeight = (flat.lineHeight as number) * _scale;
  return next;
}

/**
 * Install the Text / TextInput render override exactly once. Safe to call
 * from the module top-level of `_layout.tsx`.
 */
export function installLargeFontPatch(): void {
  if (_installed) return;
  _installed = true;
  try {
    const anyText = RNText as unknown as { render?: (...args: unknown[]) => unknown };
    const origTextRender = anyText.render;
    if (typeof origTextRender === 'function') {
      anyText.render = function patchedTextRender(this: unknown, props: { style?: unknown }, ref: unknown) {
        if (_scale === 1) {
          return (origTextRender as (p: unknown, r: unknown) => unknown).call(this, props, ref);
        }
        const nextProps = { ...props, style: scaleStyle(props?.style) };
        return (origTextRender as (p: unknown, r: unknown) => unknown).call(this, nextProps, ref);
      } as never;
    }
    const anyInput = RNTextInput as unknown as { render?: (...args: unknown[]) => unknown };
    const origInputRender = anyInput.render;
    if (typeof origInputRender === 'function') {
      anyInput.render = function patchedInputRender(this: unknown, props: { style?: unknown }, ref: unknown) {
        if (_scale === 1) {
          return (origInputRender as (p: unknown, r: unknown) => unknown).call(this, props, ref);
        }
        const nextProps = { ...props, style: scaleStyle(props?.style) };
        return (origInputRender as (p: unknown, r: unknown) => unknown).call(this, nextProps, ref);
      } as never;
    }
  } catch {
    // If RN internals ever change, fail soft — the app just won't scale.
  }
}

/** Loads the persisted large-font flag into the module-level `_scale`. */
export async function loadLargeFontMode(): Promise<boolean> {
  try {
    const v = await AsyncStorage.getItem(KEY_LARGE_FONT);
    const enabled = v === '1';
    _scale = enabled ? LARGE_SCALE : 1;
    return enabled;
  } catch {
    _scale = 1;
    return false;
  }
}

/** Persists the flag and immediately updates the in-memory scale. */
export async function setLargeFontMode(enabled: boolean): Promise<void> {
  if (enabled) {
    await AsyncStorage.setItem(KEY_LARGE_FONT, '1');
  } else {
    await AsyncStorage.removeItem(KEY_LARGE_FONT);
  }
  _scale = enabled ? LARGE_SCALE : 1;
  listeners.forEach((fn) => {
    try {
      fn();
    } catch {
      // ignore listener failures
    }
  });
}

/** Reads the current flag without touching storage (for quick checks). */
export function isLargeFontModeSync(): boolean {
  return _scale > 1;
}

/**
 * Hook returning `[enabled, setEnabled, loaded]`. Subscribes to module-wide
 * updates so every consumer re-renders when the toggle flips.
 */
export function useLargeFontMode(): [boolean, (enabled: boolean) => Promise<void>, boolean] {
  const [enabled, setEnabled] = useState<boolean>(_scale > 1);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let mounted = true;
    loadLargeFontMode().then((e) => {
      if (mounted) {
        setEnabled(e);
        setLoaded(true);
      }
    });
    const onChange = () => {
      if (mounted) setEnabled(_scale > 1);
    };
    listeners.add(onChange);
    return () => {
      mounted = false;
      listeners.delete(onChange);
    };
  }, []);

  const update = async (e: boolean) => {
    await setLargeFontMode(e);
    setEnabled(e);
  };
  return [enabled, update, loaded];
}
