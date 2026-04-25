// History list — shows all stored analyses for this device.

import { useCallback, useState } from 'react';
import {
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, ClipboardList, Trash2 } from 'lucide-react-native';
import { Badge } from '../src/ui';
import { ensureDeviceId, getLanguage as getStoredLanguage, setLastResult } from '../src/store';
import { AnalysisListItem, deleteAnalysis, listAnalyses } from '../src/api';
import { LanguageCode, t } from '../src/i18n';
import { cancelAllForAnalysis } from '../src/notifications';
import { deleteOriginal } from '../src/originals';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

function formatDate(iso: string, lang: LanguageCode): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();
  if (isToday) return t(lang, 'today');
  if (isYesterday) return t(lang, 'yesterday');
  return d.toLocaleDateString();
}

export default function HistoryScreen() {
  const router = useRouter();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [lang, setLang] = useState<LanguageCode>('en');
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const l = (await getStoredLanguage()) ?? 'en';
    setLang(l);
    const id = await ensureDeviceId();
    try {
      const data = await listAnalyses(id);
      setItems(data);
    } catch {
      setItems([]);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const onDelete = (it: AnalysisListItem) => {
    Alert.alert(t(lang, 'confirm_delete_one'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          const id = await ensureDeviceId();
          try {
            await deleteAnalysis(it.id, id);
            await cancelAllForAnalysis(it.id);
            await deleteOriginal(it.id);
            setItems((prev) => prev.filter((x) => x.id !== it.id));
          } catch (e: any) {
            Alert.alert(t(lang, 'error_generic'), e?.message || '');
          }
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={styles.safe} testID="history-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="history-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'history_title')}</Text>
        <View style={{ width: 26 }} />
      </View>
      <FlatList
        data={items}
        keyExtractor={(it) => it.id}
        contentContainerStyle={[styles.content, items.length === 0 && { flexGrow: 1 }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <View style={styles.empty} testID="history-empty">
            <ClipboardList color={colors.textMuted} size={28} strokeWidth={2.2} />
            <Text style={styles.emptyText}>{t(lang, 'no_history')}</Text>
          </View>
        }
        renderItem={({ item }) => {
          const variant = item.risk_level;
          const label =
            variant === 'green' ? t(lang, 'risk_green') : variant === 'yellow' ? t(lang, 'risk_yellow') : t(lang, 'risk_red');
          return (
            <Pressable
              onPress={() => {
                setLastResult(null);
                router.push(`/result?id=${encodeURIComponent(item.id)}`);
              }}
              style={styles.item}
              testID={`history-item-${item.id}`}
            >
              <View style={{ flex: 1, gap: 6 }}>
                <View style={styles.itemHeader}>
                  <Text style={styles.itemTitle} numberOfLines={1}>
                    {item.document_type || item.sender || t(lang, 'document_type')}
                  </Text>
                  <Text style={styles.itemDate}>{formatDate(item.created_at, lang)}</Text>
                </View>
                <Text style={styles.itemSummary} numberOfLines={2}>
                  {item.summary_translated || item.sender || ''}
                </Text>
                <View style={{ marginTop: 4 }}>
                  <Badge label={label} variant={variant} />
                </View>
              </View>
              <Pressable
                onPress={() => onDelete(item)}
                hitSlop={10}
                style={styles.itemDelete}
                testID={`history-delete-${item.id}`}
              >
                <Trash2 color={colors.textSecondary} size={20} strokeWidth={2.2} />
              </Pressable>
            </Pressable>
          );
        }}
      />
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
    gap: spacing.sm,
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  emptyText: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  itemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  itemTitle: {
    flex: 1,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  itemDate: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
  },
  itemSummary: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  itemDelete: {
    width: 32,
    height: 32,
    borderRadius: radius.full,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
