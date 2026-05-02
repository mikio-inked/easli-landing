// App-wide font scaling for accessibility / elderly-friendly mode.
//
// Three-layer patch strategy so this works in **every** RN environment:
//
//   1. `react/jsx-runtime` `.jsx` and `.jsxs`  — caught by the new JSX
//      transform (the default in RN 0.71+ / Expo SDK 50+ release builds with
//      Hermes). Every `<Text>` becomes a `_jsx(Text, props)` call at compile
//      time, so this is the most reliable interception point in production.
//   2. `React.createElement`                    — caught by code that still
//      uses the legacy JSX transform (rare today, but Expo Go dev bundles
//      and some third-party libs sometimes do).
//   3. `Text.render` / `TextInput.render` slot  — last-resort fallback for
//      odd RN builds where the forwardRef render slot is the only writable
//      surface. This was our original approach and it works in Expo Go,
//      but Hermes-optimised TestFlight builds can render via a memoised
//      path that ignores it — hence the higher-level patches above.
//
// All three are idempotent and installed at module-import time
// (`installLargeFontPatch()` is called from `app/_layout.tsx` top-level
// before the first <Text> is rendered).

import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useState } from 'react';
import { StyleSheet, Text as RNText, TextInput as RNTextInput } from 'react-native';

const KEY_LARGE_FONT = 'klarpost.largeFont';
const LARGE_SCALE = 1.18; // +18% — comfortable bump without breaking layouts

let _scale = 1;
let _installed = false;
const listeners = new Set<() => void>();

// ---- Inter font auto-application -----------------------------------------
// Map fontWeight string/number → Inter family name. We piggy-back on the
// largeFontMode patch (which already intercepts every <Text>'s style) so
// callers don't need to set fontFamily everywhere — they just keep using
// fontWeight: '700' / '600' / etc. and the right Inter is picked.
//
// When `fontFamily` is already set on the style, we DON'T override it —
// that lets brand components (logo) opt into a specific weight directly.
function interFamilyFor(weight: unknown): string {
  if (typeof weight === 'number') {
    if (weight >= 800) return 'Inter_800ExtraBold';
    if (weight >= 700) return 'Inter_700Bold';
    if (weight >= 600) return 'Inter_600SemiBold';
    if (weight >= 500) return 'Inter_500Medium';
    return 'Inter_400Regular';
  }
  if (typeof weight === 'string') {
    if (weight === 'bold' || weight === '700') return 'Inter_700Bold';
    if (weight === '800' || weight === '900') return 'Inter_800ExtraBold';
    if (weight === '600') return 'Inter_600SemiBold';
    if (weight === '500') return 'Inter_500Medium';
    return 'Inter_400Regular';
  }
  return 'Inter_400Regular';
}

function scaleStyle(style: unknown): unknown {
  if (style == null) return style;
  const flat = StyleSheet.flatten(style as never) as Record<string, unknown> | null;
  if (!flat) return style;
  const next: Record<string, unknown> = { ...flat };
  // Apply font scaling for accessibility / large-font-mode.
  if (_scale !== 1) {
    if (typeof flat.fontSize === 'number') {
      next.fontSize = Math.round((flat.fontSize as number) * _scale);
    }
    if (typeof flat.lineHeight === 'number') {
      next.lineHeight = Math.round((flat.lineHeight as number) * _scale);
    }
  }
  // Auto-apply Inter family unless the caller explicitly set fontFamily.
  // This is what makes the easli rebrand "just work" across all 23 screens
  // without touching each <Text> individually.
  if (typeof flat.fontFamily !== 'string' || !flat.fontFamily) {
    next.fontFamily = interFamilyFor(flat.fontWeight);
  }
  return next;
}

// Cheap identity check that survives module-instance differences. RN ships
// Text as a forwardRef. Comparing by `displayName === 'Text'` would match
// authored components called Text too — instead we match the canonical
// imports we captured at module load.
const TEXT_TYPES = new Set<unknown>([RNText, RNTextInput]);

function maybeScalePropsFor(type: unknown, props: unknown): unknown {
  // We always want to apply Inter font (even at scale === 1), so we don't
  // early-return on the scale check any more. The early-out is now only
  // for non-Text types and missing style.
  if (!TEXT_TYPES.has(type)) return props;
  if (props == null || typeof props !== 'object') return props;
  const p = props as { style?: unknown };
  if (p.style == null) {
    // No style set yet — inject a minimal one so Inter still applies.
    return { ...p, style: { fontFamily: 'Inter_400Regular' } };
  }
  return { ...p, style: scaleStyle(p.style) };
}

// ---- Layer 1: react/jsx-runtime --------------------------------------------
function patchJsxRuntime(): boolean {
  // Both runtimes (prod + dev) need patching; either may be present at runtime
  // depending on whether Babel emitted the dev or prod transform.
  const targets: { name: string; mod: Record<string, unknown> | null }[] = [];
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const prod = require('react/jsx-runtime') as Record<string, unknown>;
    targets.push({ name: 'jsx-runtime', mod: prod });
  } catch {
    // ignore — runtime not present
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const dev = require('react/jsx-dev-runtime') as Record<string, unknown>;
    targets.push({ name: 'jsx-dev-runtime', mod: dev });
  } catch {
    // ignore
  }

  let patchedAny = false;
  for (const { mod } of targets) {
    if (!mod) continue;
    for (const fnName of ['jsx', 'jsxs', 'jsxDEV']) {
      const orig = mod[fnName];
      if (typeof orig !== 'function') continue;
      const wrapped = function patchedJsx(this: unknown, type: unknown, props: unknown, ...rest: unknown[]) {
        const nextProps = maybeScalePropsFor(type, props);
        return (orig as (...a: unknown[]) => unknown).call(this, type, nextProps, ...rest);
      };
      try {
        mod[fnName] = wrapped;
        if (mod[fnName] === wrapped) {
          patchedAny = true;
          continue;
        }
      } catch {
        // try defineProperty
      }
      try {
        Object.defineProperty(mod, fnName, {
          configurable: true,
          enumerable: true,
          writable: true,
          value: wrapped,
        });
        if (mod[fnName] === wrapped) patchedAny = true;
      } catch {
        // give up on this fn
      }
    }
  }
  return patchedAny;
}

// ---- Layer 2: React.createElement ------------------------------------------
function patchCreateElement(): boolean {
  const anyReact = React as unknown as { createElement: (...args: unknown[]) => unknown };
  const orig = anyReact.createElement;
  if (typeof orig !== 'function') return false;
  const wrapped = function patchedCreateElement(this: unknown, type: unknown, props: unknown, ...children: unknown[]) {
    const nextProps = maybeScalePropsFor(type, props);
    return (orig as (...a: unknown[]) => unknown).call(this, type, nextProps, ...children);
  };
  try {
    anyReact.createElement = wrapped as never;
    if (anyReact.createElement === wrapped) return true;
  } catch {
    // fall through
  }
  try {
    Object.defineProperty(React, 'createElement', {
      configurable: true,
      enumerable: true,
      writable: true,
      value: wrapped,
    });
    return (React as unknown as { createElement: unknown }).createElement === wrapped;
  } catch {
    return false;
  }
}

// ---- Layer 3: forwardRef render slot (legacy fallback) ---------------------
function tryReplaceRender(comp: unknown): boolean {
  if (!comp || typeof comp !== 'object') return false;
  const target = comp as { render?: (...args: unknown[]) => unknown };
  const orig = target.render;
  if (typeof orig !== 'function') return false;
  const wrapper = function patchedRender(this: unknown, props: { style?: unknown }, ref: unknown) {
    if (_scale === 1) return (orig as (p: unknown, r: unknown) => unknown).call(this, props, ref);
    const nextProps = { ...props, style: scaleStyle(props?.style) };
    return (orig as (p: unknown, r: unknown) => unknown).call(this, nextProps, ref);
  };
  try {
    target.render = wrapper as never;
    if (target.render === wrapper) return true;
  } catch {
    // fall through
  }
  try {
    Object.defineProperty(target, 'render', {
      configurable: true,
      enumerable: true,
      writable: true,
      value: wrapper,
    });
    return target.render === wrapper;
  } catch {
    return false;
  }
}

/**
 * Install the JSX-runtime + createElement + render-slot overrides exactly
 * once. Safe to call from the module top-level of `_layout.tsx`.
 */
export function installLargeFontPatch(): void {
  if (_installed) return;
  _installed = true;
  let jsxOk = false;
  let createOk = false;
  let textOk = false;
  let inputOk = false;
  try {
    jsxOk = patchJsxRuntime();
  } catch {
    // ignore
  }
  try {
    createOk = patchCreateElement();
  } catch {
    // ignore
  }
  try {
    textOk = tryReplaceRender(RNText);
    inputOk = tryReplaceRender(RNTextInput);
  } catch {
    // ignore
  }
  if (__DEV__) {
    // eslint-disable-next-line no-console
    console.log(
      `[largeFontMode] patch installed jsx=${jsxOk} createElement=${createOk} text=${textOk} textInput=${inputOk}`,
    );
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
