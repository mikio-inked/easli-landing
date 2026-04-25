// Document scanner camera — live framing overlay inspired by iOS Notes
// scanner with multi-page capture. Renders the camera fullscreen with four
// corner brackets defining the document area, a horizontal thumbnail strip
// of pages already captured, a shutter button, flash toggle, and a
// "Done · N" CTA that appears once the first page is captured.
//
// Note: real edge auto-detection requires a custom dev build (e.g.
// react-native-document-scanner-plugin). This screen gives the same visual
// guidance and works inside Expo Go.

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  Easing,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  Check,
  Image as ImageIcon,
  X,
  Zap,
  ZapOff,
} from 'lucide-react-native';
import { Button } from '../src/ui';
import {
  PendingPage,
  getLanguage as getStoredLanguage,
  setPendingAnalysis,
} from '../src/store';
import { LanguageCode, t } from '../src/i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

type FlashMode = 'off' | 'on' | 'auto';

interface CapturedPage extends PendingPage {
  uri: string;
}

export default function CameraScreen() {
  const router = useRouter();
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<FlashMode>('off');
  const [pages, setPages] = useState<CapturedPage[]>([]);
  const flashAnim = useRef(new Animated.Value(0)).current;
  const tipFade = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    getStoredLanguage().then((l) => setLang(l ?? 'en'));
  }, []);

  // Auto-fade the helper tip after 5 seconds so the user is not over-coached.
  useEffect(() => {
    const timer = setTimeout(() => {
      Animated.timing(tipFade, {
        toValue: 0.45,
        duration: 600,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }).start();
    }, 5000);
    return () => clearTimeout(timer);
  }, [tipFade]);

  useEffect(() => {
    if (permission && !permission.granted && permission.canAskAgain) {
      requestPermission();
    }
  }, [permission, requestPermission]);

  const flashScreen = useCallback(() => {
    flashAnim.setValue(0);
    Animated.sequence([
      Animated.timing(flashAnim, {
        toValue: 1,
        duration: 80,
        useNativeDriver: true,
      }),
      Animated.timing(flashAnim, {
        toValue: 0,
        duration: 240,
        useNativeDriver: true,
      }),
    ]).start();
  }, [flashAnim]);

  const handleCapture = async () => {
    if (busy || !ready || !cameraRef.current) return;
    setBusy(true);
    flashScreen();
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.7,
        skipProcessing: false,
        exif: false,
        base64: false,
      });
      if (!photo?.uri) {
        setBusy(false);
        return;
      }
      const b64 = await FileSystem.readAsStringAsync(photo.uri, {
        encoding: 'base64' as any,
      });
      setPages((prev) => [
        ...prev,
        { base64: b64, mimeType: 'image/jpeg', uri: photo.uri },
      ]);
    } catch {
      // ignore — surface via the busy spinner reset
    } finally {
      setBusy(false);
    }
  };

  const handleLibrary = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        setBusy(false);
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 0.7,
        base64: true,
        allowsEditing: false,
        allowsMultipleSelection: true,
      });
      if (res.canceled || !res.assets?.length) {
        setBusy(false);
        return;
      }
      const newPages: CapturedPage[] = [];
      for (const a of res.assets) {
        if (!a.base64) continue;
        const mime = (a.mimeType || 'image/jpeg').toLowerCase();
        newPages.push({ base64: a.base64, mimeType: mime, uri: a.uri });
      }
      if (newPages.length === 0) {
        setBusy(false);
        return;
      }
      setPages((prev) => [...prev, ...newPages]);
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = (idx: number) => {
    setPages((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleDone = () => {
    if (pages.length === 0) return;
    setPendingAnalysis({
      pages: pages.map((p) => ({ base64: p.base64, mimeType: p.mimeType })),
    });
    router.replace('/analyzing');
  };

  const handleClose = () => {
    if (pages.length === 0) {
      router.back();
      return;
    }
    Alert.alert(t(lang, 'cancel'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: () => router.back(),
      },
    ]);
  };

  const cycleFlash = () => {
    setFlash((f) => (f === 'off' ? 'on' : f === 'on' ? 'auto' : 'off'));
  };

  // Permission states
  if (Platform.OS === 'web') {
    return (
      <SafeAreaView style={styles.permissionWrap}>
        <View style={styles.permissionInner}>
          <Text style={styles.permTitle}>{t(lang, 'scan_document')}</Text>
          <Text style={styles.permBody}>
            The live multi-page scanner runs on iPhone via Expo Go. On the web preview please pick one or more images from your library.
          </Text>
          <Button
            label={t(lang, 'pick_from_library')}
            onPress={handleLibrary}
            loading={busy}
            testID="camera-pick-library-web"
          />
          {pages.length > 0 ? (
            <Button
              label={`${t(lang, 'done')} · ${pages.length}`}
              onPress={handleDone}
              testID="camera-web-done"
              icon={<Check color={colors.white} size={18} strokeWidth={2.5} />}
            />
          ) : null}
          <Pressable onPress={() => router.back()} style={styles.permCancel}>
            <Text style={styles.permCancelLabel}>{t(lang, 'cancel')}</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  if (!permission) {
    return (
      <View style={styles.permissionWrap}>
        <ActivityIndicator color={colors.white} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.permissionWrap}>
        <View style={styles.permissionInner}>
          <Text style={styles.permTitle}>{t(lang, 'open_camera')}</Text>
          <Text style={styles.permBody}>
            {t(lang, 'tip_lighting')} · {t(lang, 'tip_flat')} · {t(lang, 'tip_full_page')}
          </Text>
          <Button
            label={t(lang, 'open_camera')}
            onPress={requestPermission}
            testID="camera-grant"
          />
          <Pressable onPress={() => router.back()} style={styles.permCancel}>
            <Text style={styles.permCancelLabel}>{t(lang, 'cancel')}</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const FlashIcon = flash === 'off' ? ZapOff : Zap;
  const flashLabel = flash === 'off' ? 'Off' : flash === 'on' ? 'On' : 'Auto';
  const tipText = pages.length === 0
    ? t(lang, 'tip_full_page')
    : t(lang, 'multi_page_hint');
  const pageCount = pages.length;

  return (
    <View style={styles.root} testID="camera-screen">
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFillObject}
        facing="back"
        flash={flash}
        autofocus="on"
        onCameraReady={() => setReady(true)}
        animateShutter={false}
      />

      {/* Corner-bracket framing overlay */}
      <View pointerEvents="none" style={styles.frameWrap}>
        <View style={styles.frame}>
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
        </View>
      </View>

      {/* Capture flash */}
      <Animated.View
        pointerEvents="none"
        style={[StyleSheet.absoluteFillObject, { backgroundColor: '#fff', opacity: flashAnim }]}
      />

      <SafeAreaView style={styles.safeOverlay} pointerEvents="box-none">
        {/* Top bar */}
        <View style={styles.topBar} pointerEvents="box-none">
          <Pressable
            onPress={handleClose}
            style={styles.iconChip}
            testID="camera-close"
            hitSlop={10}
          >
            <X color={colors.white} size={22} strokeWidth={2.6} />
          </Pressable>
          <Animated.View style={[styles.tipChip, { opacity: tipFade }]}>
            <Text style={styles.tipText}>{tipText}</Text>
          </Animated.View>
          <Pressable
            onPress={cycleFlash}
            style={styles.iconChip}
            testID="camera-flash"
            hitSlop={10}
          >
            <FlashIcon
              color={flash === 'off' ? colors.white : colors.yellow.solid}
              size={22}
              strokeWidth={2.6}
            />
            <Text style={styles.flashLabel}>{flashLabel}</Text>
          </Pressable>
        </View>

        {/* Bottom area: thumbnail strip + bar */}
        <View pointerEvents="box-none">
          {pageCount > 0 ? (
            <View style={styles.thumbStripWrap} testID="camera-thumb-strip">
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.thumbStripContent}
              >
                {pages.map((p, i) => (
                  <View key={p.uri + i} style={styles.thumbItem}>
                    <Image source={{ uri: p.uri }} style={styles.thumbImg} />
                    <View style={styles.thumbNumber}>
                      <Text style={styles.thumbNumberText}>{i + 1}</Text>
                    </View>
                    <Pressable
                      onPress={() => handleRemove(i)}
                      hitSlop={8}
                      style={styles.thumbRemove}
                      testID={`camera-thumb-remove-${i}`}
                    >
                      <X color={colors.white} size={12} strokeWidth={3} />
                    </Pressable>
                  </View>
                ))}
              </ScrollView>
            </View>
          ) : null}

          <View style={styles.bottomBar} pointerEvents="box-none">
            <Pressable
              onPress={handleLibrary}
              disabled={busy}
              style={[styles.sideBtn, busy && { opacity: 0.4 }]}
              testID="camera-library"
              hitSlop={8}
            >
              <ImageIcon color={colors.white} size={22} strokeWidth={2.4} />
            </Pressable>

            <Pressable
              onPress={handleCapture}
              disabled={busy || !ready}
              style={[styles.shutterOuter, (busy || !ready) && { opacity: 0.5 }]}
              testID="camera-shutter"
              hitSlop={6}
            >
              <View style={styles.shutterRing}>
                <View style={styles.shutterInner}>
                  {busy ? <ActivityIndicator color={colors.white} /> : null}
                </View>
              </View>
            </Pressable>

            {pageCount > 0 ? (
              <Pressable
                onPress={handleDone}
                style={styles.doneBtn}
                testID="camera-done"
                hitSlop={6}
              >
                <Check color={colors.white} size={18} strokeWidth={2.6} />
                <Text style={styles.doneLabel}>
                  {t(lang, 'done')} · {pageCount}
                </Text>
              </Pressable>
            ) : (
              <View style={styles.sideBtn} />
            )}
          </View>
        </View>
      </SafeAreaView>
    </View>
  );
}

const FRAME_PADDING_H = 24;
const FRAME_ASPECT = 0.707;

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  safeOverlay: { flex: 1, justifyContent: 'space-between' },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    gap: spacing.sm,
  },
  iconChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: radius.full,
    backgroundColor: 'rgba(0,0,0,0.5)',
    minWidth: 44,
    justifyContent: 'center',
  },
  flashLabel: {
    color: colors.white,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    letterSpacing: 0.4,
  },
  tipChip: {
    flex: 1,
    marginHorizontal: spacing.sm,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: radius.full,
    backgroundColor: 'rgba(0,0,0,0.55)',
    alignItems: 'center',
  },
  tipText: {
    color: colors.white,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    textAlign: 'center',
  },
  frameWrap: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: FRAME_PADDING_H,
  },
  frame: {
    width: '100%',
    aspectRatio: FRAME_ASPECT,
    maxHeight: '70%',
    position: 'relative',
  },
  corner: {
    position: 'absolute',
    width: 36,
    height: 36,
    borderColor: '#FFFFFF',
  },
  cornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: 4,
    borderLeftWidth: 4,
    borderTopLeftRadius: 12,
  },
  cornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: 4,
    borderRightWidth: 4,
    borderTopRightRadius: 12,
  },
  cornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
    borderBottomLeftRadius: 12,
  },
  cornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
    borderBottomRightRadius: 12,
  },
  thumbStripWrap: {
    paddingVertical: spacing.sm,
    backgroundColor: 'rgba(0,0,0,0.55)',
  },
  thumbStripContent: {
    paddingHorizontal: spacing.md,
    gap: 10,
    alignItems: 'center',
  },
  thumbItem: {
    width: 56,
    height: 72,
    borderRadius: radius.sm,
    backgroundColor: '#222',
    overflow: 'visible',
    borderWidth: 2,
    borderColor: '#FFFFFF',
    position: 'relative',
  },
  thumbImg: {
    width: '100%',
    height: '100%',
    borderRadius: 4,
  },
  thumbNumber: {
    position: 'absolute',
    left: 2,
    top: 2,
    minWidth: 20,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 10,
    backgroundColor: 'rgba(0,0,0,0.7)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbNumberText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: fontWeight.bold,
  },
  thumbRemove: {
    position: 'absolute',
    right: -8,
    top: -8,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.red.solid,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  bottomBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    paddingTop: spacing.sm,
  },
  sideBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: 'rgba(0,0,0,0.4)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  doneBtn: {
    minWidth: 96,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
    gap: 6,
  },
  doneLabel: {
    color: colors.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    letterSpacing: 0.2,
  },
  shutterOuter: {
    width: 84,
    height: 84,
    borderRadius: 42,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.18)',
  },
  shutterRing: {
    width: 76,
    height: 76,
    borderRadius: 38,
    borderWidth: 4,
    borderColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutterInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  permissionWrap: {
    flex: 1,
    backgroundColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
  },
  permissionInner: {
    width: '100%',
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  permTitle: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.white,
    textAlign: 'center',
  },
  permBody: {
    fontSize: fontSize.base,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.sm,
  },
  permCancel: { paddingVertical: 12, alignItems: 'center' },
  permCancelLabel: {
    color: colors.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.semibold,
  },
});
