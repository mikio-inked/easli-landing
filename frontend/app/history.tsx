// History list — shows all stored analyses for this device.
// Supports filtering by AI-detected category (Tax, Rent, Bank, …) and
// surfaces a small scam-warning badge when relevant.

import { useCallback, useMemo, useState } from 'react';
import {
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, ClipboardList, ShieldAlert, Trash2 } from 'lucide-react-native';
import { Badge } from '../src/ui';
import { ensureDeviceId, getLanguage as getStoredLanguage, setLastResult } from '../src/store';
import { AnalysisListItem, deleteAnalysis, listAnalyses } from '../src/api';
import {
  CATEGORY_EMOJI,
  CATEGORY_ORDER,
  CategoryCode,
  LanguageCode,
  categoryLabel,
  t,
} from '../src/i18n';
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

function safeCategory(code: string | undefined | null): CategoryCode {
  return (CATEGORY_ORDER.includes(code as CategoryCode) ? code : 'other') as CategoryCode;
}

export default function HistoryScreen() {
  const router = useRouter();
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [lang, setLang] = useState<LanguageCode>('en');
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<CategoryCode | null>(null);

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
    }, [load]),
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

  // Build the chip row from categories that actually appear in the user's
  // history (plus "All" first). Avoids overwhelming first-time users.
  const visibleCategories = useMemo<CategoryCode[]>(() => {
    const present = new Set<CategoryCode>();
    items.forEach((it) => present.add(safeCategory(it.category)));
    return CATEGORY_ORDER.filter((c) => present.has(c));
  }, [items]);

  const filtered = useMemo(() => {
    if (!filter) return items;
    return items.filter((it) => safeCategory(it.category) === filter);
  }, [items, filter]);

  // If the active filter no longer matches anything (e.g. last item deleted),
  // silently fall back to "All".
  if (filter && filtered.length === 0 && items.length > 0) {
    // Defer this to the render of the empty state — the user gets feedback.
  }

  return (
    <SafeAreaView style={styles.safe} testID="history-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="history-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'history_title')}</Text>
        <View style={{ width: 26 }} />
      </View>

      {visibleCategories.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipsRow}
          testID="history-filter-chips"
        >
          <FilterChip
            label={t(lang, 'filter_all')}
            count={items.length}
            active={filter === null}
            onPress={() => setFilter(null)}
            testID="history-filter-all"
          />
          {visibleCategories.map((c) => (
            <FilterChip
              key={c}
              label={`${CATEGORY_EMOJI[c]} ${categoryLabel(lang, c)}`}
              count={items.filter((it) => safeCategory(it.category) === c).length}
              active={filter === c}
              onPress={() => setFilter(c)}
              testID={`history-filter-${c}`}
            />
          ))}
        </ScrollView>
      ) : null}

      <FlatList
        data={filtered}
        keyExtractor={(it) => it.id}
        contentContainerStyle={[styles.content, filtered.length === 0 && { flexGrow: 1 }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <View style={styles.empty} testID="history-empty">
            <ClipboardList color={colors.textMuted} size={28} strokeWidth={2.2} />
            <Text style={styles.emptyText}>
              {items.length === 0
                ? t(lang, 'no_history')
                : t(lang, 'filter_no_results')}
            </Text>
          </View>
        }
        renderItem={({ item }) => {
          const variant = item.risk_level;
          const label =
            variant === 'green'
              ? t(lang, 'risk_green')
              : variant === 'yellow'
                ? t(lang, 'risk_yellow')
                : t(lang, 'risk_red');
          const cat = safeCategory(item.category);
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
                <View style={styles.itemMeta}>
                  <View style={styles.categoryChip}>
                    <Text style={styles.categoryChipText}>
                      {CATEGORY_EMOJI[cat]} {categoryLabel(lang, cat)}
                    </Text>
                  </View>
                  <Badge label={label} variant={variant} />
                  {item.scam_warning ? (
                    <View style={styles.scamChip} testID={`history-scam-${item.id}`}>
                      <ShieldAlert color={colors.red.text} size={12} strokeWidth={2.6} />
                      <Text style={styles.scamChipText} numberOfLines={1}>
                        {t(lang, 'scam_warning_title').split('—')[0].trim()}
                      </Text>
                    </View>
                  ) : null}
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

function FilterChip({
  label,
  count,
  active,
  onPress,
  testID,
}: {
  label: string;
  count: number;
  active: boolean;
  onPress: () => void;
  testID?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      testID={testID}
      style={[styles.chip, active && styles.chipActive]}
      hitSlop={6}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]} numberOfLines={1}>
        {label} <Text style={[styles.chipCount, active && styles.chipCountActive]}>({count})</Text>
      </Text>
    </Pressable>
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
  chipsRow: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: 8,
    alignItems: 'center',
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    minHeight: 36,
    justifyContent: 'center',
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
  },
  chipTextActive: {
    color: '#FFFFFF',
  },
  chipCount: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    fontWeight: fontWeight.semibold,
  },
  chipCountActive: {
    color: 'rgba(255,255,255,0.85)',
  },
  content: {
    padding: spacing.lg,
    paddingTop: spacing.sm,
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
  itemMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 4,
  },
  categoryChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: colors.primarySoft,
  },
  categoryChipText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
  },
  scamChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: colors.red.bg,
    borderWidth: 1,
    borderColor: colors.red.border,
  },
  scamChipText: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    color: colors.red.text,
    maxWidth: 120,
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
