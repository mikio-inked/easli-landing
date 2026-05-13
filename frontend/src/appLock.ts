// Biometric app-lock helper.
//
// Combines persistence (AsyncStorage) with the native biometric API. The
// app-root layout reads `isLockEnabled()` on mount and, if true, displays
// a blocking lock-screen overlay that calls `unlock()` and only renders
// the real UI after a successful authentication.
//
// Privacy: we never store biometric templates ourselves — that's all
// handled by the OS Secure Enclave. We just store a boolean flag in
// AsyncStorage and ask the OS to authenticate using whatever biometry
// the device has enrolled (Face ID, Touch ID, optic, fingerprint…).

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as LocalAuthentication from 'expo-local-authentication';

const LOCK_KEY = '@easli.appLock.enabled';

/** Returns true if the user has turned on biometric lock in Settings. */
export async function isLockEnabled(): Promise<boolean> {
  try {
    const raw = await AsyncStorage.getItem(LOCK_KEY);
    return raw === '1';
  } catch {
    return false;
  }
}

/** Persist the user's lock-screen preference. */
export async function setLockEnabled(enabled: boolean): Promise<void> {
  try {
    await AsyncStorage.setItem(LOCK_KEY, enabled ? '1' : '0');
  } catch {
    // ignore — non-fatal
  }
}

/**
 * Returns true if the device CAN do biometric auth at all (sensor +
 * at least one enrolled fingerprint/face). Used to gate the Settings
 * toggle so we don't offer a lock the user could never undo.
 */
export async function isBiometricAvailable(): Promise<boolean> {
  try {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) return false;
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    return enrolled;
  } catch {
    return false;
  }
}

/** Names of the biometric techniques the OS supports, for prompts. */
export async function getBiometricTypes(): Promise<string[]> {
  try {
    const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
    const out: string[] = [];
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      out.push('Face ID');
    }
    if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      out.push('Touch ID');
    }
    if (types.includes(LocalAuthentication.AuthenticationType.IRIS)) {
      out.push('Iris');
    }
    return out;
  } catch {
    return [];
  }
}

/**
 * Prompt the OS for biometric authentication.
 * @param promptMessage Localised string shown above Face ID / Touch ID sheet
 * @returns true if the user successfully authenticated
 */
export async function authenticate(promptMessage: string): Promise<boolean> {
  try {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage,
      // We don't accept device-passcode fallback for the unlock-on-open
      // flow because the security model is "your biometrics, not your
      // 4-digit PIN". Users without enrolled biometry just won't see
      // the option in Settings.
      disableDeviceFallback: false,
      cancelLabel: undefined, // platform default
    });
    return !!result.success;
  } catch {
    return false;
  }
}
