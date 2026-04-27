// App-wide font scaling for accessibility / elderly-friendly mode.
//
// Two-pronged strategy so this works on Expo Go, in production builds, and
// across Hermes / JSC / RN 0.81+:
//
//   1. Monkey-patch the `render` slot of the forwardRef'd <Text>/<TextInput>
//      from `react-native`. This catches every text node anywhere in the
//      tree and multiplies any explicit fontSize / lineHeight by the current
//      scale. The patch is idempotent and installed at module-import time
//      (before the first render in `_layout.tsx`).
//   2. Re-key the root Stack whenever the scale changes — see `_layout.tsx`.
//      That way even text components whose parents wouldn't naturally
//      re-render still pick up the new scale on the next paint.

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import { StyleSheet, Text as RNText, TextInput as RNTextInput } from 'react-native';

const KEY_LARGE_FONT = 'klarpost.largeFont';
const LARGE_SCALE = 1.18; // +18% — comfortable bump without breaking layouts

let _scale = 1;
let _installed = false;
const listeners = new Set<() => void>();

function scaleStyle(style: unknown): unknown {
  if (_scale === 1 || style == null) return style;
  const flat = StyleSheet.flatten(style as never) as Record<string, unknown> | null;
  if (!flat) return style;
  const next: Record<string, unknown> = { ...flat };
  if (typeof flat.fontSize === 'number') {
    // Round to a whole pixel — some RN releases ignore fractional fontSize.
    next.fontSize = Math.round((flat.fontSize as number) * _scale);
  }
  if (typeof flat.lineHeight === 'number') {
    next.lineHeight = Math.round((flat.lineHeight as number) * _scale);
  }
  return next;
}

function tryReplaceRender(comp: unknown, label: string): boolean {
  if (!comp || typeof comp !== 'object') return false;
  const target = comp as { render?: (...args: unknown[]) => unknown };
  const orig = target.render;
  if (typeof orig !== 'function') return false;
  const wrapper = function patchedRender(this: unknown, props: { style?: unknown }, ref: unknown) {
    if (_scale === 1) {
      return (orig as (p: unknown, r: unknown) => unknown).call(this, props, ref);
    }
    const nextProps = { ...props, style: scaleStyle(props?.style) };
    return (orig as (p: unknown, r: unknown) => unknown).call(this, nextProps, ref);
  };
  // Try direct assignment first (works on most RN builds).
  try {
    target.render = wrapper as never;
    if (target.render === wrapper) return true;
  } catch {
    // fallthrough to defineProperty
  }
  // Some RN builds make the property non-writable but configurable. defineProperty
  // sidesteps the silent-fail of strict-mode assignment.
  try {
    Object.defineProperty(target, 'render', {
      configurable: true,
      enumerable: true,
      writable: true,
      value: wrapper,
    });
    return target.render === wrapper;
  } catch (e) {
    if (__DEV__) {
      // eslint-disable-next-line no-console
      console.warn(`[largeFontMode] could not patch ${label}.render`, e);
    }
    return false;
  }
}

/**
 * Install the Text / TextInput render override exactly once. Safe to call
 * from the module top-level of `_layout.tsx`.
 */
export function installLargeFontPatch(): void {
  if (_installed) return;
  _installed = true;
  try {
    const t = tryReplaceRender(RNText, 'Text');
    const ti = tryReplaceRender(RNTextInput, 'TextInput');
    if (__DEV__) {
      // eslint-disable-next-line no-console
      console.log(`[largeFontMode] patch installed text=${t} textInput=${ti}`);
    }
  } catch {
    // Always fail soft — accessibility is best-effort.
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

/** Raw scale (1 or LARGE_SCALE). Useful for screens that prefer a hook
 *  over the implicit Text patch (e.g. for explicit lineHeight tuning). */
export function getFontScaleSync(): number {
  return _scale;
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
