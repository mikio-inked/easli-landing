// Scan: tips screen + camera launcher. Uses expo-image-picker.launchCameraAsync
// which prompts for permission and returns a base64 image.

import { useEffect, useState } from 'react';
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as ImagePicker from 'expo-image-picker';
import { ArrowLeft, Camera, Image as ImageIcon, Lightbulb, Maximize2, Square } from 'lucide-react-native';
import { Button } from '../src/ui';
import { setPendingAnalysis, getLanguage as getStoredLanguage } from '../src/store';
import { LanguageCode, t } from '../src/i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

export default function ScanScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getStoredLanguage().then((l) => setLang(l ?? 'en'));
  }, []);

  const openCamera = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) {
        Alert.alert(t(lang, 'error_generic'), 'Camera permission is required.');
        return;
      }
      const res = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        quality: 0.7,
        base64: true,
        allowsEditing: false,
      });
      if (res.canceled || !res.assets || res.assets.length === 0) return;
      const a = res.assets[0];
      if (!a.base64) {
        Alert.alert(t(lang, 'error_generic'), t(lang, 'error_no_image'));
        return;
      }
      const mime = (a.mimeType || 'image/jpeg').toLowerCase();
      setPendingAnalysis({ base64: a.base64, mimeType: mime });
      router.replace('/analyzing');
    } catch (e: any) {
      Alert.alert(t(lang, 'error_generic'), e?.message || '');
    } finally {
      setBusy(false);
    }
  };

  const openLibrary = async () => {
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
      if (!a.base64) {
        Alert.alert(t(lang, 'error_generic'), t(lang, 'error_no_image'));
        return;
      }
      const mime = (a.mimeType || 'image/jpeg').toLowerCase();
      setPendingAnalysis({ base64: a.base64, mimeType: mime });
      router.replace('/analyzing');
    } catch (e: any) {
      Alert.alert(t(lang, 'error_generic'), e?.message || '');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} testID="scan-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="scan-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'scan_document')}</Text>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.frameWrap}>
          <View style={styles.frame}>
            <Image
              source={{ uri: 'https://static.prod-images.emergentagent.com/jobs/1f0c6f21-2efe-4a5b-950e-770baf187f4d/images/0b5b9d6fb4e6a1a07ee423bf490d131ccfc6cfc7932ed41c51e126f29e0135cb.png' }}
              style={styles.frameImage}
              resizeMode="contain"
            />
          </View>
        </View>
        <Text style={styles.title}>{t(lang, 'tips_title')}</Text>
        <View style={styles.tipsList}>
          <Tip icon={<Lightbulb color={colors.primary} size={20} strokeWidth={2.4} />} text={t(lang, 'tip_lighting')} />
          <Tip icon={<Square color={colors.primary} size={20} strokeWidth={2.4} />} text={t(lang, 'tip_flat')} />
          <Tip icon={<Maximize2 color={colors.primary} size={20} strokeWidth={2.4} />} text={t(lang, 'tip_full_page')} />
          <Tip icon={<Camera color={colors.primary} size={20} strokeWidth={2.4} />} text={t(lang, 'tip_no_blur')} />
        </View>
      </ScrollView>
      <View style={styles.footer}>
        <Button
          label={t(lang, 'open_camera')}
          onPress={openCamera}
          loading={busy}
          icon={<Camera color={colors.white} size={20} strokeWidth={2.5} />}
          testID="scan-open-camera"
        />
        <Button
          label={t(lang, 'pick_from_library')}
          onPress={openLibrary}
          variant="secondary"
          icon={<ImageIcon color={colors.primary} size={20} strokeWidth={2.5} />}
          testID="scan-pick-library"
        />
      </View>
    </SafeAreaView>
  );
}

function Tip({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <View style={styles.tipRow}>
      <View style={styles.tipIcon}>{icon}</View>
      <Text style={styles.tipText}>{text}</Text>
    </View>
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
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.lg,
  },
  frameWrap: {
    width: '100%',
    alignItems: 'center',
  },
  frame: {
    width: '100%',
    height: 220,
    borderRadius: radius.xxl,
    backgroundColor: colors.primarySoft,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  frameImage: { width: '100%', height: '100%' },
  title: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
  },
  tipsList: { gap: spacing.sm },
  tipRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  tipIcon: {
    width: 36,
    height: 36,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tipText: {
    flex: 1,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    paddingTop: spacing.sm,
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    backgroundColor: colors.background,
  },
});
