// Scan screen — primary entry point for capturing a document.
//
// On iOS / Android the user taps the big "Scan now" CTA which calls the
// native VisionKit / ML Kit Document Scanner via `src/scanner.ts`. The
// scanner itself handles auto edge-detection, perspective correction and
// multi-page capture — KlarPost just receives the cropped pages back.
//
// On web (and any platform where the native scanner is unavailable) the
// scanner stub returns 'unavailable' and we silently fall back to the
// existing manual flow:  expo-image-picker camera or library.
//
// After at least one page is captured we render a thumbnail grid so the
// user can review, delete, scan more or start the analysis. Pages live
// in component state and never leave the device until /analyzing fires
// the API call.
//
// PRIVACY: We never log image content, file paths or base64. The pages
// are passed via `setPendingAnalysis()` (in-memory only) and the original
// device-side temp files are released as soon as the scanner returns.

import { useEffect, useState } from 'react';
import {
  Alert,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as ImagePicker from 'expo-image-picker';
import {
  ArrowLeft,
  Camera,
  Image as ImageIcon,
  Info,
  Lightbulb,
  Maximize2,
  Plus,
  ScanLine,
  Square,
  Trash2,
} from 'lucide-react-native';
import { Button } from '../src/ui';
import {
  generateIdempotencyKey,
  setPendingAnalysis,
  getLanguage as getStoredLanguage,
  PendingPage,
} from '../src/store';
import { LanguageCode, t } from '../src/i18n';
import { colors, fontSize, fontWeight, radius, shadows, spacing } from '../src/theme';
import {
  isNativeScannerAvailable,
  scanDocument,
  ScannedPage,
} from '../src/scanner';

export default function ScanScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [busy, setBusy] = useState(false);
  // Pages collected so far in this session. Cleared the moment the user
  // taps "Start analysis" and we hand off to /analyzing.
  const [pages, setPages] = useState<PendingPage[]>([]);
  // Sticky banner shown on web / unsupported devices so the user understands
  // why the native auto-scan UI isn't there.
  const [fallbackBanner, setFallbackBanner] = useState(false);

  useEffect(() => {
    getStoredLanguage().then((l) => setLang(l ?? 'en'));
  }, []);

  // Convert ScannedPage[] (from the native plugin) to PendingPage[]. The two
  // shapes are compatible — this just normalises the type.
  const intoPendingPages = (scanned: ScannedPage[]): PendingPage[] =>
    scanned.map((p) => ({ base64: p.base64, mimeType: p.mimeType }));

  /** Hard cap: KlarPost analyses are limited to 5 pages per document. */
  const MAX_PAGES = 5;

  /** Launch the native iOS/Android document scanner and append its result.  */
  const launchNativeScan = async () => {
    if (busy) return;
    // Compute how many more pages we can accept in this session and pass
    // that to the plugin so its in-app counter reflects the real cap. If
    // we already have MAX_PAGES, block the call entirely.
    const remaining = MAX_PAGES - pages.length;
    if (remaining <= 0) {
      Alert.alert(
        t(lang, 'pages_count_other').replace('{n}', String(MAX_PAGES)),
        t(lang, 'error_generic'),
      );
      return;
    }
    setBusy(true);
    try {
      const result = await scanDocument({ maxPages: remaining, quality: 80 });

      switch (result.status) {
        case 'success':
          // Defensive trim — the plugin should already respect maxPages,
          // but never let one runaway response exceed the global cap.
          setPages((prev) => [
            ...prev,
            ...intoPendingPages(result.pages).slice(0, MAX_PAGES - prev.length),
          ]);
          break;
        case 'cancel':
          // User backed out — silent.
          break;
        case 'unavailable':
          // Should not reach here when isNativeScannerAvailable() is true,
          // but be defensive: surface the fallback message + reveal the
          // legacy buttons.
          setFallbackBanner(true);
          break;
        case 'error':
        default:
          Alert.alert(t(lang, 'error_generic'));
          break;
      }
    } finally {
      setBusy(false);
    }
  };

  /** Fallback: expo-image-picker camera (web + unsupported devices). */
  const openCamera = () => {
    if (busy) return;
    // /camera is the existing multi-shot manual camera screen. Pages
    // captured there flow into setPendingAnalysis on its own.
    router.push('/camera');
  };

  /** Fallback / convenience: pick a single image from the library. */
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
      // Library picks bypass our preview UI on purpose: a single picked
      // image is the simplest case, mirror the previous fast-path.
      setPendingAnalysis({
        pages: [{ base64: a.base64, mimeType: mime }],
        idempotencyKey: generateIdempotencyKey(),
      });
      router.replace('/analyzing');
    } catch (e: any) {
      Alert.alert(t(lang, 'error_generic'), e?.message || '');
    } finally {
      setBusy(false);
    }
  };

  /** Remove one page from the local preview list. */
  const deletePage = (idx: number) => {
    Alert.alert(t(lang, 'delete_page_confirm'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: () => setPages((prev) => prev.filter((_, i) => i !== idx)),
      },
    ]);
  };

  /** Hand pages off to /analyzing for upload + AI analysis. */
  const startAnalysis = () => {
    if (busy || pages.length === 0) return;
    setPendingAnalysis({
      pages,
      idempotencyKey: generateIdempotencyKey(),
    });
    // Clear local state immediately so backing onto this screen later
    // gives a fresh start and doesn't accidentally show an old letter.
    setPages([]);
    router.replace('/analyzing');
  };

  const nativeAvailable = isNativeScannerAvailable();
  const hasPages = pages.length > 0;

  // ---- Render ----
  return (
    <SafeAreaView style={styles.safe} testID="scan-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="scan-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <Text style={styles.headerTitle}>{t(lang, 'scan_document')}</Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Friendly banner when native scanner is unavailable on this build/platform */}
        {(!nativeAvailable || fallbackBanner) && !hasPages ? (
          <View style={styles.fallbackBanner} testID="scan-fallback-banner">
            <Info color={colors.primary} size={20} strokeWidth={2.5} />
            <Text style={styles.fallbackText}>{t(lang, 'scanner_unavailable_msg')}</Text>
          </View>
        ) : null}

        {/* ============ PAGE PREVIEW ============ */}
        {hasPages ? (
          <View style={styles.previewCard} testID="scan-preview-card">
            <Text style={styles.previewKicker}>
              {pages.length === 1
                ? t(lang, 'pages_count_one')
                : t(lang, 'pages_count_other').replace('{n}', String(pages.length))}
            </Text>
            <View style={styles.previewGrid}>
              {pages.map((p, i) => (
                <View key={i} style={styles.thumbWrap} testID={`scan-thumb-${i}`}>
                  <View style={styles.thumbIndex}>
                    <Text style={styles.thumbIndexText}>{i + 1}</Text>
                  </View>
                  <Image
                    source={{ uri: `data:${p.mimeType};base64,${p.base64}` }}
                    style={styles.thumbImage}
                    resizeMode="cover"
                  />
                  <Pressable
                    onPress={() => deletePage(i)}
                    style={styles.thumbDelete}
                    hitSlop={8}
                    accessibilityRole="button"
                    accessibilityLabel={t(lang, 'delete_page_confirm')}
                    testID={`scan-thumb-delete-${i}`}
                  >
                    <Trash2 color={colors.white} size={14} strokeWidth={2.6} />
                  </Pressable>
                </View>
              ))}
            </View>
          </View>
        ) : (
          // ============ INTRO STATE ============
          <>
            <View style={styles.frameWrap}>
              <View style={styles.frame}>
                {/* Document outline with a soft scan beam — clean, on-brand,
                    no external image. Replaces the previous remote 3D camera
                    clipart that didn't fit the easli design system. */}
                <View style={styles.frameDocOutline}>
                  <View style={styles.frameDocLine} />
                  <View style={[styles.frameDocLine, { width: '70%' }]} />
                  <View style={[styles.frameDocLine, { width: '85%' }]} />
                  <View style={[styles.frameDocLine, { width: '60%' }]} />
                  <View style={[styles.frameDocLine, { width: '78%' }]} />
                  <View style={styles.frameScanBeam} />
                </View>
                <View style={styles.frameCornerTL} />
                <View style={styles.frameCornerTR} />
                <View style={styles.frameCornerBL} />
                <View style={styles.frameCornerBR} />
                <View style={styles.frameIconBadge}>
                  <ScanLine color={colors.white} size={28} strokeWidth={2.6} />
                </View>
              </View>
            </View>

            {/* Calm intro tip — short and reassuring for elderly users */}
            <View style={styles.introTipCard}>
              <Lightbulb color={colors.primary} size={22} strokeWidth={2.4} />
              <Text style={styles.introTipText}>{t(lang, 'scanner_intro_tip')}</Text>
            </View>

            <Text style={styles.title}>{t(lang, 'tips_title')}</Text>
            <View style={styles.tipsList}>
              <Tip
                icon={<Lightbulb color={colors.primary} size={20} strokeWidth={2.4} />}
                text={t(lang, 'tip_lighting')}
              />
              <Tip
                icon={<Square color={colors.primary} size={20} strokeWidth={2.4} />}
                text={t(lang, 'tip_flat')}
              />
              <Tip
                icon={<Maximize2 color={colors.primary} size={20} strokeWidth={2.4} />}
                text={t(lang, 'tip_full_page')}
              />
              <Tip
                icon={<Camera color={colors.primary} size={20} strokeWidth={2.4} />}
                text={t(lang, 'tip_no_blur')}
              />
            </View>
          </>
        )}
      </ScrollView>

      {/* ============ FOOTER CTAs ============ */}
      <View style={styles.footer}>
        {hasPages ? (
          <>
            <Button
              label={t(lang, 'start_analysis')}
              onPress={startAnalysis}
              loading={busy}
              icon={<ScanLine color={colors.white} size={20} strokeWidth={2.5} />}
              testID="scan-start-analysis"
            />
            {/* On native we let the user keep scanning more pages until the
                5-page cap; on web fallback "scan another page" doesn't make
                sense — show the library / camera buttons instead. */}
            {nativeAvailable && !fallbackBanner && pages.length < MAX_PAGES ? (
              <Button
                label={t(lang, 'scan_another')}
                onPress={launchNativeScan}
                variant="secondary"
                icon={<Plus color={colors.primary} size={20} strokeWidth={2.5} />}
                testID="scan-another-page"
              />
            ) : !nativeAvailable || fallbackBanner ? (
              <Button
                label={t(lang, 'pick_from_library')}
                onPress={openLibrary}
                variant="secondary"
                icon={<ImageIcon color={colors.primary} size={20} strokeWidth={2.5} />}
                testID="scan-pick-library"
              />
            ) : null}
          </>
        ) : nativeAvailable && !fallbackBanner ? (
          <>
            {/* Native primary path — ONE clean CTA, then a tiny library link */}
            <Button
              label={t(lang, 'start_scan')}
              onPress={launchNativeScan}
              loading={busy}
              icon={<ScanLine color={colors.white} size={20} strokeWidth={2.5} />}
              testID="scan-native-start"
            />
            <Button
              label={t(lang, 'pick_from_library')}
              onPress={openLibrary}
              variant="secondary"
              icon={<ImageIcon color={colors.primary} size={20} strokeWidth={2.5} />}
              testID="scan-pick-library"
            />
          </>
        ) : (
          <>
            {/* Web fallback path — open manual camera or library */}
            <Button
              label={t(lang, 'open_camera')}
              onPress={openCamera}
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
          </>
        )}
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

// ---- Quiet a TS warning about Platform on web bundles (unused but kept
// available for future per-platform tweaks). ----
void Platform;

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },
  fallbackBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: colors.primarySoft,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
  fallbackText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: fontWeight.medium,
    lineHeight: 20,
  },
  frameWrap: { alignItems: 'center', marginTop: spacing.sm },
  frame: {
    width: 220,
    height: 240,
    borderRadius: radius.lg,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    position: 'relative',
    ...shadows.card,
  },
  frameImage: { width: '100%', height: '100%' },
  frameDocOutline: {
    width: 130,
    height: 170,
    borderRadius: 10,
    backgroundColor: colors.white,
    borderWidth: 1.5,
    borderColor: colors.border,
    paddingHorizontal: 14,
    paddingTop: 22,
    overflow: 'hidden',
    position: 'relative',
  },
  frameDocLine: {
    height: 8,
    borderRadius: 3,
    backgroundColor: colors.primarySoft,
    marginBottom: 9,
    width: '92%',
  },
  frameScanBeam: {
    position: 'absolute',
    left: 8,
    right: 8,
    top: '52%',
    height: 3,
    backgroundColor: colors.primary,
    opacity: 0.85,
    borderRadius: 2,
  },
  frameCornerTL: {
    position: 'absolute',
    top: 16,
    left: 16,
    width: 22,
    height: 22,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderColor: colors.primary,
    borderTopLeftRadius: 6,
  },
  frameCornerTR: {
    position: 'absolute',
    top: 16,
    right: 16,
    width: 22,
    height: 22,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderColor: colors.primary,
    borderTopRightRadius: 6,
  },
  frameCornerBL: {
    position: 'absolute',
    bottom: 16,
    left: 16,
    width: 22,
    height: 22,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderColor: colors.primary,
    borderBottomLeftRadius: 6,
  },
  frameCornerBR: {
    position: 'absolute',
    bottom: 16,
    right: 16,
    width: 22,
    height: 22,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderColor: colors.primary,
    borderBottomRightRadius: 6,
  },
  frameIconBadge: {
    position: 'absolute',
    bottom: 14,
    right: 14,
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadows.card,
  },

  introTipCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: colors.green.bg,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.green.border,
  },
  introTipText: {
    flex: 1,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium,
    lineHeight: 22,
  },

  title: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    marginTop: spacing.md,
  },
  tipsList: { gap: spacing.sm },
  tipRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  tipIcon: {
    width: 36,
    height: 36,
    borderRadius: radius.sm,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tipText: {
    flex: 1,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    lineHeight: 22,
  },

  // ---- Preview ----
  previewCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.xxl,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
    gap: spacing.md,
    ...shadows.card,
  },
  previewKicker: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    color: colors.primary,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  previewGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  thumbWrap: {
    width: 100,
    height: 130,
    borderRadius: radius.md,
    overflow: 'hidden',
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.borderLight,
    position: 'relative',
  },
  thumbImage: { width: '100%', height: '100%' },
  thumbIndex: {
    position: 'absolute',
    top: 6,
    left: 6,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: 'rgba(15,23,42,0.7)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },
  thumbIndexText: {
    color: colors.white,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
  },
  thumbDelete: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.red.solid,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },

  // ---- Footer ----
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    backgroundColor: colors.surface,
  },
});
