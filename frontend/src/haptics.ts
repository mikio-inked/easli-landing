// Centralised haptic feedback helper.
//
// Why a central module: we want a consistent "feel" across the app and an
// easy place to turn haptics off (e.g. user preference, accessibility, or
// when running unit tests). All UI code should import from here, never call
// Haptics directly.
//
// Haptic levels used in easli:
//   • tap()        — micro feedback for normal taps on important buttons
//   • selection()  — list-item / segmented-control changes
//   • success()    — finished analysis, finished purchase, restored receipt
//   • warning()    — soft validation error (e.g. quota reached, deletes)
//   • error()      — hard failure (network, payment failed, scan failed)
//
// All functions are fire-and-forget: errors from Haptics (e.g. on the web
// preview where haptics is a no-op) are swallowed so they never crash a
// callsite.

import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';

// Web does not support haptics at all — short-circuit so we don't pay the
// import + try/catch cost on every call. iOS + Android both work natively.
const HAPTICS_AVAILABLE = Platform.OS === 'ios' || Platform.OS === 'android';

let enabled = true;

/** Globally enable/disable haptics (e.g. user preference toggle in Settings). */
export function setHapticsEnabled(value: boolean) {
  enabled = value;
}

export function areHapticsEnabled() {
  return enabled && HAPTICS_AVAILABLE;
}

function safe<T>(fn: () => Promise<T>): void {
  if (!enabled || !HAPTICS_AVAILABLE) return;
  // Don't await — fire and forget. iOS sometimes errors briefly during
  // app foreground/background transitions; we don't want a haptic to
  // bubble up as an unhandled promise rejection in Sentry.
  fn().catch(() => {});
}

/** Soft single tap — use for the most common interactive buttons. */
export function tap() {
  safe(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
}

/** A slightly heavier tap — use for primary CTAs like "Scan letter". */
export function press() {
  safe(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
}

/** Used when the user changes a selected value (segmented control, language). */
export function selection() {
  safe(() => Haptics.selectionAsync());
}

/** Positive notification: analysis ready, purchase successful, restore done. */
export function success() {
  safe(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
}

/** Soft negative: quota reached, item deleted, scan aborted. */
export function warning() {
  safe(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning));
}

/** Hard negative: network/payment failure, anything the user must retry. */
export function error() {
  safe(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error));
}
