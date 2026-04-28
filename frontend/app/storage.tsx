// Settings → "View saved originals" → /storage
//
// Diagnostic detail screen for the on-device originals layer. Three jobs:
//   1. Show real numbers (count, total size, per-file list) so the user can
//      verify "save originals" is actually working — not a black box.
//   2. Run a self-test (write/read/delete a tiny file) on demand to give an
//      instant green/red signal even when the user has zero originals saved.
//   3. Surface the last few storage errors that previously got silently
//      swallowed in catch-blocks. Useful for support cases.
//
// Strings on this screen are intentionally English-only — it sits two levels
// deep in Settings and is primarily a diagnostic tool. Top-level UX (Toast
// banner + Settings card) IS localised, so end users never need to read
// English unless they're deep-debugging.

import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  FileText,
  HardDrive,
  PlayCircle,
  Trash2,
} from 'lucide-react-native';
import { Button } from '../src/ui';
import {
  StorageError,
  StorageStats,
  StoredOriginalMeta,
  clearStorageErrors,
  deleteAllOriginals,
  deleteOriginal,
  formatBytes,
  getStorageErrors,
  getStorageStats,
  listStoredOriginals,
  runStorageSelfTest,
} from '../src/originals';
import { LanguageCode, t } from '../src/i18n';
import { getLanguage } from '../src/store';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

interface SelfTestResult {
  ok: boolean;
  error?: string;
  details?: string;
  ranAt: number;
}

export default function StorageScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [items, setItems] = useState<StoredOriginalMeta[]>([]);
  const [errors, setErrors] = useState<StorageError[]>([]);
  const [loading, setLoading] = useState(true);
  const [selfTestRunning, setSelfTestRunning] = useState(false);
  const [selfTest, setSelfTest] = useState<SelfTestResult | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [s, list, errs] = await Promise.all([
        getStorageStats(),
        listStoredOriginals(),
        getStorageErrors(),
      ]);
      setStats(s);
      setItems(list);
      setErrors(errs);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const l = (await getLanguage()) ?? 'en';
      setLang(l);
      await refresh();
    })();
  }, [refresh]);

  const onRunSelfTest = async () => {
    setSelfTestRunning(true);
    try {
      const r = await runStorageSelfTest();
      setSelfTest({ ...r, ranAt: Date.now() });
      await refresh();
    } finally {
      setSelfTestRunning(false);
    }
  };

  const onDeleteOne = (id: string) => {
    Alert.alert(t(lang, 'delete'), t(lang, 'confirm_delete_one'), [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          await deleteOriginal(id);
          await refresh();
        },
      },
    ]);
  };

  const onDeleteAll = () => {
    if (!stats || stats.count === 0) return;
    Alert.alert(t(lang, 'delete'), t(lang, 'confirm_delete_all'), [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          await deleteAllOriginals();
          await refresh();
        },
      },
    ]);
  };

  const onClearErrors = async () => {
    await clearStorageErrors();
    await refresh();
  };

  return (
    <SafeAreaView style={styles.safe} testID="storage-screen">
      <View style={styles.topBar}>
        <View
          style={styles.backBtn}
          onTouchEnd={() => router.back()}
          accessibilityRole="button"
          testID="storage-back"
        >
          <ChevronLeft color={colors.textSecondary} size={22} strokeWidth={2.4} />
        </View>
        <Text style={styles.title}>{t(lang, 'local_storage_title')}</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {/* ---- Stats card ---- */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.iconWrap, { backgroundColor: colors.primarySoft }]}>
              <HardDrive color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>Storage</Text>
              {loading ? (
                <Text style={styles.cardSub}>Loading…</Text>
              ) : stats?.available ? (
                <Text style={styles.cardSub}>
                  {stats.count} original{stats.count === 1 ? '' : 's'} ·{' '}
                  {formatBytes(stats.totalBytes)}
                </Text>
              ) : (
                <Text style={[styles.cardSub, { color: colors.red.text }]}>
                  Local storage is not available on this platform
                </Text>
              )}
            </View>
          </View>
          {stats?.dir ? (
            <Text style={styles.path} numberOfLines={2}>
              {stats.dir}
            </Text>
          ) : null}
        </View>

        {/* ---- Self-test card ---- */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.iconWrap, { backgroundColor: colors.primarySoft }]}>
              <PlayCircle color={colors.primary} size={20} strokeWidth={2.4} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{t(lang, 'storage_run_test')}</Text>
              <Text style={styles.cardSub}>
                Writes a 1-byte test file, reads it back, then deletes it.
              </Text>
            </View>
          </View>

          {selfTest ? (
            <View
              style={[
                styles.testResult,
                selfTest.ok ? styles.testResultOk : styles.testResultFail,
              ]}
            >
              {selfTest.ok ? (
                <CheckCircle2 color={colors.green.text} size={18} strokeWidth={2.4} />
              ) : (
                <AlertTriangle color={colors.red.text} size={18} strokeWidth={2.4} />
              )}
              <Text
                style={[
                  styles.testResultText,
                  { color: selfTest.ok ? colors.green.text : colors.red.text },
                ]}
              >
                {selfTest.ok
                  ? `Local storage works on this device${
                      selfTest.details ? ` — ${selfTest.details}` : ''
                    }`
                  : `Test failed: ${selfTest.error ?? 'unknown error'}`}
              </Text>
            </View>
          ) : null}

          <Button
            label={selfTestRunning ? 'Testing…' : 'Run test'}
            onPress={onRunSelfTest}
            disabled={selfTestRunning}
            variant="secondary"
            testID="storage-run-test"
          />
        </View>

        {/* ---- Originals list ---- */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Saved originals</Text>
          {items.length === 0 ? (
            <Text style={styles.empty}>
              {stats?.available
                ? 'No originals saved yet. Turn on "Save originals locally" in Settings and analyse a document.'
                : 'Local storage is unavailable here.'}
            </Text>
          ) : (
            <View style={{ gap: spacing.xs }}>
              {items.map((item) => (
                <View key={item.id} style={styles.itemRow}>
                  <View
                    style={[styles.iconWrap, { backgroundColor: colors.borderLight, width: 32, height: 32 }]}
                  >
                    <FileText color={colors.textSecondary} size={16} strokeWidth={2.4} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemTitle} numberOfLines={1}>
                      {item.id.slice(0, 8)}…{item.ext.toUpperCase()}
                    </Text>
                    <Text style={styles.itemSub}>
                      {formatBytes(item.sizeBytes)}
                      {item.modifiedAtIso
                        ? ` · ${new Date(item.modifiedAtIso).toLocaleDateString()}`
                        : ''}
                    </Text>
                  </View>
                  <View
                    style={styles.itemDelete}
                    onTouchEnd={() => onDeleteOne(item.id)}
                    accessibilityRole="button"
                    testID={`storage-delete-${item.id}`}
                  >
                    <Trash2 color={colors.red.text} size={16} strokeWidth={2.4} />
                  </View>
                </View>
              ))}
              <View style={{ height: spacing.xs }} />
              <Button
                label={`Delete all (${items.length})`}
                onPress={onDeleteAll}
                variant="danger"
                icon={<Trash2 color={colors.white} size={18} strokeWidth={2.4} />}
                testID="storage-delete-all"
              />
            </View>
          )}
        </View>

        {/* ---- Recent errors ---- */}
        {errors.length > 0 ? (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <View style={[styles.iconWrap, { backgroundColor: colors.red.bg }]}>
                <AlertTriangle color={colors.red.text} size={20} strokeWidth={2.4} />
              </View>
              <Text style={styles.cardTitle}>Recent errors</Text>
            </View>
            {errors.map((e, idx) => (
              <View key={idx} style={styles.errorRow}>
                <Text style={styles.errorOp}>{e.op.toUpperCase()}</Text>
                <Text style={styles.errorMessage}>{e.message}</Text>
                <Text style={styles.errorAt}>{new Date(e.at).toLocaleString()}</Text>
              </View>
            ))}
            <Button label="Clear errors" onPress={onClearErrors} variant="secondary" />
          </View>
        ) : null}

        {loading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  topBar: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: radius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    flex: 1,
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
  },
  scroll: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },

  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  cardSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  path: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontFamily: 'monospace',
    marginTop: spacing.xs,
  },
  sectionTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  empty: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    paddingVertical: spacing.sm,
    lineHeight: 20,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  itemTitle: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  itemSub: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 2,
  },
  itemDelete: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.full,
  },
  testResult: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  testResultOk: {
    backgroundColor: colors.green.bg,
    borderColor: colors.green.border,
  },
  testResultFail: {
    backgroundColor: colors.red.bg,
    borderColor: colors.red.border,
  },
  testResultText: {
    flex: 1,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  errorRow: {
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  errorOp: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    color: colors.red.text,
  },
  errorMessage: {
    fontSize: fontSize.sm,
    color: colors.textPrimary,
    marginTop: 2,
  },
  errorAt: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 2,
  },
  loadingWrap: { paddingVertical: spacing.lg, alignItems: 'center' },
});
