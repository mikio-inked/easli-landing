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
  TextInput,
  View,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, ClipboardList, HardDrive, Search, ShieldAlert, Trash2, X } from 'lucide-react-native';
import { Badge } from '../src/ui';
import { ensureDeviceId, getLanguage as getStoredLanguage, setLastResult } from '../src/store';
import { AnalysisListItem, deleteAnalysis, listAnalyses } from '../src/api';
import { countryCodeToFlag } from '../src/languages';
import {
  CATEGORY_EMOJI,
  CATEGORY_ORDER,
  CategoryCode,
  LanguageCode,
  categoryLabel,
  t,
} from '../src/i18n';
import { cancelAllForAnalysis } from '../src/notifications';
import { deleteOriginal, getStoredOriginalIds } from '../src/originals';
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
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [lang, setLang] = useState<LanguageCode>('en');
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<CategoryCode | null>(null);
  const [query, setQuery] = useState('');
  // High-risk-only toggle. Cheap to compute (we already have risk_level on
  // every item from the backend), so it's just an additional filter pass.
  const [highRiskOnly, setHighRiskOnly] = useState(false);

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
    // Refresh "saved on this device" badge set in parallel — single
    // directory listing keeps the cost flat regardless of history size.
    try {
      const s = await getStoredOriginalIds();
      setSavedIds(s);
    } catch {
      setSavedIds(new Set());
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
    const q = query.trim().toLowerCase();
    return items.filter((it) => {
      // 1) Category chip filter
      if (filter && safeCategory(it.category) !== filter) return false;
      // 2) High-risk-only toggle
      if (highRiskOnly && it.risk_level !== 'red') return false;
      // 3) Full-text search across sender, document type, summary and
      //    target_language_label. Lowercased once for cheap repeated
      //    .includes() — fine for a list of ≤ 1k items.
      if (q) {
        const hay = [
          it.sender,
          it.document_type,
          it.summary_translated,
          it.target_language_label,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, filter, query, highRiskOnly]);

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

      {/* Search bar — instant client-side filter across sender, document
          type, summary and target language. Stays hidden until the user
          has at least 2 letters in history to avoid clutter for new users. */}
      {items.length >= 2 ? (
        <View style={styles.searchWrap}>
          <Search color={colors.textMuted} size={18} strokeWidth={2.4} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder={t(lang, 'history_search_placeholder')}
            placeholderTextColor={colors.textMuted}
            style={styles.searchInput}
            autoCorrect={false}
            autoCapitalize="none"
            returnKeyType="search"
            clearButtonMode="while-editing"
            testID="history-search-input"
          />
          {query.length > 0 ? (
            <Pressable
              onPress={() => setQuery('')}
              hitSlop={10}
              testID="history-search-clear"
            >
              <X color={colors.textMuted} size={18} strokeWidth={2.4} />
            </Pressable>
          ) : null}
        </View>
      ) : null}

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
            active={filter === null && !highRiskOnly}
            onPress={() => {
              setFilter(null);
              setHighRiskOnly(false);
            }}
            testID="history-filter-all"
          />
          {/* High-risk pill — surfaces the most urgent letters in a single
              tap. Only render the chip if there IS at least one red item,
              otherwise the chip would always be empty. */}
          {items.some((it) => it.risk_level === 'red') ? (
            <FilterChip
              label={`🔴 ${t(lang, 'filter_high_risk')}`}
              count={items.filter((it) => it.risk_level === 'red').length}
              active={highRiskOnly}
              onPress={() => {
                setHighRiskOnly((v) => !v);
                setFilter(null);
              }}
              testID="history-filter-high-risk"
            />
          ) : null}
          {visibleCategories.map((c) => (
            <FilterChip
              key={c}
              label={`${CATEGORY_EMOJI[c]} ${categoryLabel(lang, c)}`}
              count={items.filter((it) => safeCategory(it.category) === c).length}
              active={filter === c}
              onPress={() => {
                setFilter(c);
                setHighRiskOnly(false);
              }}
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
                  {savedIds.has(item.id) ? (
                    <View
                      style={styles.savedDot}
                      testID={`history-saved-${item.id}`}
                      accessibilityLabel={t(lang, 'saved_to_device')}
                    >
                      <HardDrive color={colors.primary} size={11} strokeWidth={2.6} />
                    </View>
                  ) : null}
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
                  {/* Phase 6 EU: country chip — flag + ISO code. Mirrors the
                      result-screen jurisdiction badge but compact for list
                      density. Hidden when detected_country_code is empty so
                      legacy/pre-Phase-6 records don't show a muted stub. */}
                  {item.detected_country_code ? (
                    <View
                      style={styles.countryChip}
                      testID={`history-country-${item.detected_country_code}`}
                      accessibilityLabel={`Country ${item.detected_country_code}`}
                    >
                      <Text style={styles.countryChipFlag}>
                        {countryCodeToFlag(item.detected_country_code)}
                      </Text>
                      <Text style={styles.countryChipCode}>
                        {item.detected_country_code}
                      </Text>
                    </View>
                  ) : null}
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
  searchWrap: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minHeight: 44,
  },
  searchInput: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.textPrimary,
    paddingVertical: 0,
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
  // Tiny chip indicating this analysis has its original document saved on
  // device (toggle in Settings). Reassures the user that local storage
  // really did persist their letter.
  savedDot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
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
  // Phase 6 EU: country chip in list row — flag + ISO code. Compact pill
  // designed to match `categoryChip` density. Uses primary border to mirror
  // the result-screen jurisdiction badge so the design language stays
  // consistent across screens.
  countryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.primaryBorder ?? colors.border,
  },
  countryChipFlag: {
    fontSize: 13,
    lineHeight: 16,
  },
  countryChipCode: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.textPrimary,
    letterSpacing: 0.4,
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
