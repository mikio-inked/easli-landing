// Native calendar integration — adds a deadline as an iOS Calendar event
// with a 1-day-before alarm. Permissions are requested on demand.

import * as Calendar from 'expo-calendar';
import { Alert, Platform } from 'react-native';
import { LanguageCode, t } from './i18n';

/** Add a deadline to the user's default calendar. Returns true on success. */
export async function addDeadlineToCalendar(args: {
  title: string;
  date: Date;
  notes?: string;
  lang: LanguageCode;
}): Promise<boolean> {
  const { title, date, notes, lang } = args;
  try {
    // 1) Request permissions. iOS prompts the first time; subsequent
    //    runs are silent. Android shows a system dialog.
    const perm = await Calendar.requestCalendarPermissionsAsync();
    if (perm.status !== 'granted') {
      Alert.alert(t(lang, 'app_lock_title'), t(lang, 'error_generic'));
      return false;
    }

    // 2) Find a writable calendar to add to. On iOS we look for the
    //    default-internal source; on Android we just take the first
    //    user-owned writable one.
    const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
    let target = calendars.find((c) => c.allowsModifications && c.source?.name);
    if (!target) target = calendars.find((c) => c.allowsModifications);
    if (!target) return false;

    // 3) Calendar event spans 1 hour. The deadline itself is the start.
    //    Alarm goes off 24h earlier so the user can still react.
    const startDate = new Date(date);
    startDate.setHours(9, 0, 0, 0); // a sensible morning time
    const endDate = new Date(startDate.getTime() + 60 * 60 * 1000);

    await Calendar.createEventAsync(target.id, {
      title: `easli: ${title}`,
      startDate,
      endDate,
      notes: notes || '',
      alarms: [
        { relativeOffset: -24 * 60 }, // 1 day before
        { relativeOffset: -60 }, // 1 hour before
      ],
      timeZone: undefined, // use device default
    });
    return true;
  } catch {
    return false;
  }
}
