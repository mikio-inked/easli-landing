// Local notification scheduling for deadline reminders.
// Uses expo-notifications. We store a small map per analysis in AsyncStorage:
//   klarpost.reminders.{analysisId} -> [{ deadlineKey, notificationId, remindAtIso, description }]

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

export interface ReminderRecord {
  deadlineKey: string;
  notificationId: string;
  remindAtIso: string;
  description: string;
}

const KEY = (analysisId: string) => `klarpost.reminders.${analysisId}`;

let configured = false;
function configureOnce() {
  if (configured) return;
  configured = true;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

export async function ensureChannel(): Promise<void> {
  configureOnce();
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('deadlines', {
      name: 'Deadlines',
      importance: Notifications.AndroidImportance.HIGH,
    });
  }
}

export async function requestPermission(): Promise<boolean> {
  configureOnce();
  const current = await Notifications.getPermissionsAsync();
  if (current.granted || current.status === 'granted') return true;
  const next = await Notifications.requestPermissionsAsync({
    ios: { allowAlert: true, allowBadge: false, allowSound: true },
  });
  return next.granted || next.status === 'granted';
}

export async function getReminders(analysisId: string): Promise<ReminderRecord[]> {
  const raw = await AsyncStorage.getItem(KEY(analysisId));
  if (!raw) return [];
  try {
    return JSON.parse(raw) as ReminderRecord[];
  } catch {
    return [];
  }
}

async function setReminders(analysisId: string, list: ReminderRecord[]): Promise<void> {
  if (list.length === 0) {
    await AsyncStorage.removeItem(KEY(analysisId));
  } else {
    await AsyncStorage.setItem(KEY(analysisId), JSON.stringify(list));
  }
}

export async function scheduleReminder(params: {
  analysisId: string;
  deadlineKey: string;
  remindAt: Date;
  title: string;
  body: string;
  description: string;
}): Promise<ReminderRecord | null> {
  configureOnce();
  await ensureChannel();
  const granted = await requestPermission();
  if (!granted) return null;

  // Cancel any existing reminder for the same deadline first.
  const existing = await getReminders(params.analysisId);
  const same = existing.find((r) => r.deadlineKey === params.deadlineKey);
  if (same) {
    try {
      await Notifications.cancelScheduledNotificationAsync(same.notificationId);
    } catch {
      // ignore
    }
  }

  const seconds = Math.max(1, Math.floor((params.remindAt.getTime() - Date.now()) / 1000));
  const notificationId = await Notifications.scheduleNotificationAsync({
    content: {
      title: params.title,
      body: params.body,
      data: { analysisId: params.analysisId, deadlineKey: params.deadlineKey },
      sound: true,
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds,
      repeats: false,
      channelId: Platform.OS === 'android' ? 'deadlines' : undefined,
    } as Notifications.TimeIntervalTriggerInput,
  });

  const record: ReminderRecord = {
    deadlineKey: params.deadlineKey,
    notificationId,
    remindAtIso: params.remindAt.toISOString(),
    description: params.description,
  };
  const filtered = existing.filter((r) => r.deadlineKey !== params.deadlineKey);
  filtered.push(record);
  await setReminders(params.analysisId, filtered);
  return record;
}

export async function cancelReminder(analysisId: string, deadlineKey: string): Promise<void> {
  const list = await getReminders(analysisId);
  const target = list.find((r) => r.deadlineKey === deadlineKey);
  if (!target) return;
  try {
    await Notifications.cancelScheduledNotificationAsync(target.notificationId);
  } catch {
    // ignore
  }
  await setReminders(
    analysisId,
    list.filter((r) => r.deadlineKey !== deadlineKey)
  );
}

export async function cancelAllForAnalysis(analysisId: string): Promise<void> {
  const list = await getReminders(analysisId);
  for (const r of list) {
    try {
      await Notifications.cancelScheduledNotificationAsync(r.notificationId);
    } catch {
      // ignore
    }
  }
  await AsyncStorage.removeItem(KEY(analysisId));
}

export async function cancelAllReminders(): Promise<void> {
  try {
    await Notifications.cancelAllScheduledNotificationsAsync();
  } catch {
    // ignore
  }
  const keys = await AsyncStorage.getAllKeys();
  const reminderKeys = keys.filter((k) => k.startsWith('klarpost.reminders.'));
  if (reminderKeys.length) await AsyncStorage.multiRemove(reminderKeys);
}
