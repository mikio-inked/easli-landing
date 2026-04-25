// Upload: choose a PDF or image. Reads the picked file as base64 then routes
// to /analyzing.

import { useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import {
  ArrowLeft,
  FileText,
  Image as ImageIcon,
  ShieldCheck,
} from 'lucide-react-native';
import { Button } from '../src/ui';
import { setPendingAnalysis, getLanguage as getStoredLanguage } from '../src/store';
import { LanguageCode, t } from '../src/i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

const ALLOWED_IMAGE = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];
const ALLOWED_PDF = ['application/pdf'];

function inferMimeFromName(name?: string | null): string | null {
  if (!name) return null;
  const lower = name.toLowerCase();
  if (lower.endsWith('.pdf')) return 'application/pdf';
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.webp')) return 'image/webp';
  if (lower.endsWith('.heic')) return 'image/heic';
  if (lower.endsWith('.heif')) return 'image/heif';
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
  return null;
}

export default function UploadScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getStoredLanguage().then((l) => setLang(l ?? 'en'));
  }, []);

  const pickPdf = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (res.canceled || !res.assets || res.assets.length === 0) return;
      const a = res.assets[0];
      const mime = (a.mimeType || inferMimeFromName(a.name)) || '';
      if (!ALLOWED_PDF.includes(mime)) {
        Alert.alert(t(lang, 'error_generic'), t(lang, 'error_unsupported_file'));
        return;
      }
      const b64 = await FileSystem.readAsStringAsync(a.uri, { encoding: 'base64' as any });
      setPendingAnalysis({ base64: b64, mimeType: 'application/pdf' });
      router.replace('/analyzing');
    } catch (e: any) {
      Alert.alert(t(lang, 'error_generic'), e?.message || '');
    } finally {
      setBusy(false);
    }
  };

  const pickImage = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert(t(lang, 'error_generic'), 'Photo library permission is required.');
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 0.7,
        base64: true,
        allowsEditing: false,
      });
      if (res.canceled || !res.assets || res.assets.length === 0) return;
      const a = res.assets[0];
      let mime = (a.mimeType || inferMimeFromName(a.fileName) || 'image/jpeg').toLowerCase();
      if (!ALLOWED_IMAGE.includes(mime)) {
        Alert.alert(t(lang, 'error_generic'), t(lang, 'error_unsupported_file'));
        return;
      }
      if (!a.base64) {
        Alert.alert(t(lang, 'error_generic'), t(lang, 'error_no_image'));
        return;
      }
      setPendingAnalysis({ base64: a.base64, mimeType: mime });
      router.replace('/analyzing');
    } catch (e: any) {
      Alert.alert(t(lang, 'error_generic'), e?.message || '');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} testID="upload-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="upload-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'upload_file')}</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <Pressable
          onPress={pickPdf}
          style={({ pressed }) => [styles.option, pressed && { opacity: 0.95 }]}
          testID="upload-pdf-btn"
        >
          <View style={[styles.optionIcon, { backgroundColor: colors.primarySoft }]}>
            <FileText color={colors.primary} size={28} strokeWidth={2.4} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.optionTitle}>{t(lang, 'pick_pdf')}</Text>
            <Text style={styles.optionSub}>PDF</Text>
          </View>
        </Pressable>

        <Pressable
          onPress={pickImage}
          style={({ pressed }) => [styles.option, pressed && { opacity: 0.95 }]}
          testID="upload-image-btn"
        >
          <View style={[styles.optionIcon, { backgroundColor: colors.primarySoft }]}>
            <ImageIcon color={colors.primary} size={28} strokeWidth={2.4} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.optionTitle}>{t(lang, 'pick_image')}</Text>
            <Text style={styles.optionSub}>JPG · PNG · WEBP · HEIC</Text>
          </View>
        </Pressable>

        <View style={styles.privacyCard}>
          <ShieldCheck color={colors.green.solid} size={20} strokeWidth={2.4} />
          <Text style={styles.privacyText}>{t(lang, 'privacy_short')}</Text>
        </View>
      </ScrollView>
      <View style={styles.footer}>
        <Button
          label={t(lang, 'cancel')}
          onPress={() => router.back()}
          variant="ghost"
          testID="upload-cancel"
        />
      </View>
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
  content: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, gap: spacing.md },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    borderRadius: radius.xxl,
    borderWidth: 2,
    borderColor: colors.border,
    minHeight: 96,
  },
  optionIcon: {
    width: 56,
    height: 56,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  optionSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 4,
  },
  privacyCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.green.bg,
    borderColor: colors.green.border,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.lg,
    marginTop: spacing.sm,
  },
  privacyText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.green.text,
    fontWeight: fontWeight.medium,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
});
