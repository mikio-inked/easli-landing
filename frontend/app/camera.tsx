// Document scanner camera — live framing overlay inspired by iOS Notes
// scanner. Renders the camera fullscreen, four corner brackets define the
// document area, with shutter, flash, and library buttons.
//
// Note: real edge auto-detection requires a custom dev build (e.g.
// react-native-document-scanner-plugin). This screen gives the same visual
// guidance and works inside Expo Go.

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  Platform,
  Pressable,
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
  Image as ImageIcon,
  X,
  Zap,
  ZapOff,
} from 'lucide-react-native';
import { Button } from '../src/ui';
import { setPendingAnalysis, getLanguage as getStoredLanguage } from '../src/store';
import { LanguageCode, t } from '../src/i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

type FlashMode = 'off' | 'on' | 'auto';

export default function CameraScreen() {
  const router = useRouter();
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<FlashMode>('off');
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
    // Request permission lazily on first mount.
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
      setPendingAnalysis({ base64: b64, mimeType: 'image/jpeg' });
      router.replace('/analyzing');
    } catch (e: any) {
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
      });
      if (res.canceled || !res.assets?.[0]?.base64) {
        setBusy(false);
        return;
      }
      const a = res.assets[0];
      const mime = (a.mimeType || 'image/jpeg').toLowerCase();
      setPendingAnalysis({ base64: a.base64!, mimeType: mime });
      router.replace('/analyzing');
    } catch {
      setBusy(false);
    }
  };

  const cycleFlash = () => {
    setFlash((f) => (f === 'off' ? 'on' : f === 'on' ? 'auto' : 'off'));
  };

  // Web preview: CameraView is not supported on react-native-web; fall back
  // to library picker UI. This must be checked BEFORE the permission gate
  // because expo-camera permissions are not implemented on web and would
  // otherwise force users into the permission-denied UI.
  if (Platform.OS === 'web') {
    // CameraView on web is limited; fall back to library picker UI.
    return (
      <SafeAreaView style={styles.permissionWrap}>
        <View style={styles.permissionInner}>
          <Text style={styles.permTitle}>{t(lang, 'scan_document')}</Text>
          <Text style={styles.permBody}>
            The live camera scanner runs on iPhone via Expo Go. On the web preview please pick an image from your library.
          </Text>
          <Button
            label={t(lang, 'pick_from_library')}
            onPress={handleLibrary}
            loading={busy}
            testID="camera-pick-library-web"
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
            onPress={() => router.back()}
            style={styles.iconChip}
            testID="camera-close"
            hitSlop={10}
          >
            <X color={colors.white} size={22} strokeWidth={2.6} />
          </Pressable>
          <Animated.View style={[styles.tipChip, { opacity: tipFade }]}>
            <Text style={styles.tipText}>{t(lang, 'tip_full_page')}</Text>
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

        {/* Bottom bar */}
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

          <View style={styles.sideBtn} />
        </View>
      </SafeAreaView>
    </View>
  );
}

const FRAME_PADDING_H = 24;
// Document framing aspect (portrait A4-ish). 0.707 = 1 / sqrt(2).
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
