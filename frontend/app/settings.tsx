// Settings screen — change language, delete data, view privacy / disclaimer.

import { useCallback, useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft,
  ChevronRight,
  HardDrive,
  HelpCircle,
  Languages as LanguagesIcon,
  Lock,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from 'lucide-react-native';
import { Card } from '../src/ui';
import { deleteAllAnalyses } from '../src/api';
import {
  ensureDeviceId,
  getLanguage as getStoredLanguage,
  resetAll,
  setLastResult,
} from '../src/store';
import { LanguageCode, getLanguage as getLanguageMeta, t } from '../src/i18n';
import { cancelAllReminders } from '../src/notifications';
import { deleteAllOriginals } from '../src/originals';
import { getSaveOriginals, setSaveOriginals } from '../src/settings';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

export default function SettingsScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [saveOriginals, setSaveOriginalsState] = useState(false);

  useFocusEffect(
    useCallback(() => {
      getStoredLanguage().then((l) => setLang(l ?? 'en'));
      getSaveOriginals().then(setSaveOriginalsState);
    }, [])
  );

  const onToggleSaveOriginals = async (value: boolean) => {
    setSaveOriginalsState(value);
    await setSaveOriginals(value);
    if (!value) {
      // Turning OFF the toggle clears any locally saved originals.
      await deleteAllOriginals();
    }
  };

  const onDeleteAll = () => {
    Alert.alert(t(lang, 'confirm_delete_all'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          const id = await ensureDeviceId();
          try {
            await deleteAllAnalyses(id);
            await cancelAllReminders();
            await deleteAllOriginals();
            setLastResult(null);
            Alert.alert(t(lang, 'done'));
          } catch (e: any) {
            Alert.alert(t(lang, 'error_generic'), e?.message || '');
          }
        },
      },
    ]);
  };

  const onDeleteAccount = () => {
    Alert.alert(t(lang, 'confirm_delete_all'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          const id = await ensureDeviceId();
          try {
            await deleteAllAnalyses(id);
          } catch {
            // ignore
          }
          await cancelAllReminders();
          await deleteAllOriginals();
          await resetAll();
          setLastResult(null);
          router.replace('/onboarding');
        },
      },
    ]);
  };

  const langMeta = getLanguageMeta(lang);

  return (
    <SafeAreaView style={styles.safe} testID="settings-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="settings-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'settings_title')}</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Card>
          <View style={styles.row}>
            <View style={[styles.rowIcon, { backgroundColor: colors.primarySoft }]}>
              <HardDrive color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'save_originals')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'save_originals_sub')}</Text>
            </View>
            <Switch
              value={saveOriginals}
              onValueChange={onToggleSaveOriginals}
              trackColor={{ false: colors.border, true: colors.primary }}
              thumbColor={colors.white}
              testID="settings-save-originals-toggle"
            />
          </View>
        </Card>

        <Card>
          <Pressable
            onPress={() => router.push('/language')}
            style={styles.row}
            testID="settings-change-language"
          >
            <View style={styles.rowIcon}>
              <LanguagesIcon color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'change_language')}</Text>
              <Text style={styles.rowSub}>
                {langMeta.flag}  {langMeta.nativeName} · {langMeta.englishName}
              </Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        <Card>
          <Pressable
            onPress={onDeleteAll}
            style={styles.row}
            testID="settings-delete-all"
          >
            <View style={[styles.rowIcon, { backgroundColor: colors.red.bg }]}>
              <Trash2 color={colors.red.text} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'delete_all_data')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'privacy_short')}</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
          <View style={styles.divider} />
          <Pressable
            onPress={onDeleteAccount}
            style={styles.row}
            testID="settings-delete-account"
          >
            <View style={[styles.rowIcon, { backgroundColor: colors.red.bg }]}>
              <ShieldAlert color={colors.red.text} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'delete_account')}</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        <Card>
          <View style={styles.row}>
            <View style={[styles.rowIcon, { backgroundColor: colors.green.bg }]}>
              <ShieldCheck color={colors.green.text} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'privacy')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'privacy_short')}</Text>
            </View>
          </View>
          <View style={styles.divider} />
          <View style={styles.row}>
            <View style={styles.rowIcon}>
              <Lock color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'disclaimer_title')}</Text>
              <Text style={styles.rowSub}>{t(lang, 'disclaimer_long')}</Text>
            </View>
          </View>
        </Card>

        <Card>
          <Pressable
            onPress={() =>
              Alert.alert(t(lang, 'support'), 'support@klarpost.app')
            }
            style={styles.row}
            testID="settings-support"
          >
            <View style={styles.rowIcon}>
              <HelpCircle color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{t(lang, 'support')}</Text>
              <Text style={styles.rowSub}>support@klarpost.app</Text>
            </View>
            <ChevronRight color={colors.textMuted} size={22} strokeWidth={2.4} />
          </Pressable>
        </Card>

        <Text style={styles.version}>KlarPost · v1.0.0 (MVP)</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  rowIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  rowSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 20,
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderLight,
    marginVertical: 4,
  },
  version: {
    textAlign: 'center',
    color: colors.textMuted,
    fontSize: fontSize.xs,
    marginTop: spacing.lg,
  },
});
