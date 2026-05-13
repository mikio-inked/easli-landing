// "Please rate easli" prompt logic.
//
// We use `expo-store-review` so the OS-native rating sheet pops up
// (max 3x per year per Apple). Our job is just to ask the OS at the
// right moment — not too early, not too often, and never block the
// user's flow.
//
// Heuristic:
//   • Only fires after the user has had ≥ 3 successful analyses.
//   • Only fires once per app version (so we don't spam updaters).
//   • Only fires on a SUCCESS moment (after seeing a Result screen),
//     never on errors.
//   • Skips entirely if the OS says reviews aren't available.

import * as StoreReview from 'expo-store-review';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const KEY_ANALYSES_COUNT = '@easli.rate.analysesCount';
const KEY_ASKED_VERSION = '@easli.rate.askedForVersion';
const KEY_DECLINED_AT = '@easli.rate.declinedAt';

// Don't ask before this number of completed analyses.
const MIN_ANALYSES = 3;
// Don't ask more often than this (ms).
const COOLDOWN_MS = 1000 * 60 * 60 * 24 * 30; // 30 days

/** Call once per successful analysis. Idempotent + fire-and-forget. */
export async function recordSuccessfulAnalysis(): Promise<void> {
  try {
    const raw = await AsyncStorage.getItem(KEY_ANALYSES_COUNT);
    const next = Math.min(9999, (Number(raw) || 0) + 1);
    await AsyncStorage.setItem(KEY_ANALYSES_COUNT, String(next));
  } catch {
    // ignore
  }
}

/**
 * Try to open the OS rating prompt. Safe to call from any UI thread.
 * Returns true if we actually showed the prompt, false if we skipped.
 */
export async function maybePromptRating(): Promise<boolean> {
  try {
    // 1) Has the OS got the capability? (Some devices, e.g. enterprise-
    //    managed ones, disable it.)
    const available = await StoreReview.hasAction();
    if (!available) return false;

    // 2) Did we already ask for *this* app version?
    const version = Constants.expoConfig?.version || '0.0.0';
    const askedFor = await AsyncStorage.getItem(KEY_ASKED_VERSION);
    if (askedFor === version) return false;

    // 3) Has the user just been asked recently for a previous version?
    const declinedAtRaw = await AsyncStorage.getItem(KEY_DECLINED_AT);
    if (declinedAtRaw) {
      const declinedAt = Number(declinedAtRaw);
      if (Number.isFinite(declinedAt) && Date.now() - declinedAt < COOLDOWN_MS) {
        return false;
      }
    }

    // 4) Does the user have enough successful analyses?
    const countRaw = await AsyncStorage.getItem(KEY_ANALYSES_COUNT);
    const count = Number(countRaw) || 0;
    if (count < MIN_ANALYSES) return false;

    // All gates passed — open the OS sheet. We can't tell whether the user
    // actually rated or dismissed, so we mark "asked for this version" and
    // also stamp "declinedAt" so we won't bother them again for a month
    // even if they update to a newer version that opts back in.
    await StoreReview.requestReview();
    await AsyncStorage.setItem(KEY_ASKED_VERSION, version);
    await AsyncStorage.setItem(KEY_DECLINED_AT, String(Date.now()));
    return true;
  } catch {
    return false;
  }
}
