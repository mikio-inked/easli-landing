// Original document viewer — shows the saved original (image only for MVP).
// PDFs are stored but viewing them in-app requires a PDF renderer; for now we
// only render image MIME types. (Future: react-native-pdf or expo-pdf.)

import { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, FileText } from 'lucide-react-native';
import { LanguageCode, t } from '../src/i18n';
import { getLanguage as getStoredLanguage } from '../src/store';
import { loadOriginal } from '../src/originals';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

export default function OriginalScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [data, setData] = useState<{ base64: string; mimeType: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLang((await getStoredLanguage()) ?? 'en');
      if (!id) {
        setLoading(false);
        return;
      }
      const d = await loadOriginal(id);
      setData(d);
      setLoading(false);
    })();
  }, [id]);

  const isImage = data && data.mimeType.startsWith('image/');

  return (
    <SafeAreaView style={styles.safe} testID="original-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="original-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'view_original')}</Text>
        <View style={{ width: 26 }} />
      </View>
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} size="large" />
        </View>
      ) : !data ? (
        <View style={styles.center}>
          <FileText color={colors.textMuted} size={28} strokeWidth={2.2} />
          <Text style={styles.empty}>{t(lang, 'no_explanation')}</Text>
        </View>
      ) : isImage ? (
        <View style={styles.imageWrap}>
          <Image
            source={{ uri: `data:${data.mimeType};base64,${data.base64}` }}
            style={styles.image}
            resizeMode="contain"
          />
        </View>
      ) : (
        <View style={styles.center}>
          <FileText color={colors.primary} size={48} strokeWidth={2.2} />
          <Text style={styles.title}>PDF</Text>
          <Text style={styles.empty}>{t(lang, 'pdf_view_unsupported')}</Text>
        </View>
      )}
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
  imageWrap: { flex: 1, padding: spacing.md, backgroundColor: colors.borderLight },
  image: { flex: 1, borderRadius: radius.md, backgroundColor: colors.white },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  empty: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});
