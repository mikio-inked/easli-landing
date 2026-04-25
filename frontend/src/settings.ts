// Lightweight user-settings store (persistent flags).

import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY_SAVE_ORIGINALS = 'klarpost.saveOriginals';

export async function getSaveOriginals(): Promise<boolean> {
  const v = await AsyncStorage.getItem(KEY_SAVE_ORIGINALS);
  return v === '1';
}

export async function setSaveOriginals(value: boolean): Promise<void> {
  await AsyncStorage.setItem(KEY_SAVE_ORIGINALS, value ? '1' : '0');
}
