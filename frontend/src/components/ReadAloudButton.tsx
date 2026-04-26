// ReadAloudButton — text-to-speech with expo-speech.
//
// Toggles between play and stop. Locale-aware: passes the current
// app language so the system TTS picks an appropriate voice.
// Graceful fallback: on web Speech.speak still works via the Web Speech
// API; on platforms where it's not available the button simply no-ops
// (we don't crash).

import { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Speech from 'expo-speech';
import { Pause, Play, Volume2 } from 'lucide-react-native';
import { LanguageCode, t } from '../i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../theme';

// Map our app LanguageCode → BCP-47 locales the system TTS understands.
const TTS_LOCALES: Record<LanguageCode, string> = {
  en: 'en-US',
  de_simple: 'de-DE',
  es: 'es-ES',
  ru: 'ru-RU',
  tr: 'tr-TR',
  vi: 'vi-VN',
  zh: 'zh-CN',
};

export function ReadAloudButton({
  text,
  lang,
  testID,
}: {
  text: string;
  lang: LanguageCode;
  testID?: string;
}) {
  const [speaking, setSpeaking] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      // Stop any in-flight utterance when this card unmounts so the user
      // doesn't hear a stale read-out after navigating away.
      try {
        Speech.stop();
      } catch {
        /* noop */
      }
      cleanupRef.current?.();
    };
  }, []);

  const start = async () => {
    if (!text || !text.trim()) return;
    try {
      const isAlready = await Speech.isSpeakingAsync();
      if (isAlready) {
        await Speech.stop();
      }
      setSpeaking(true);
      Speech.speak(text, {
        language: TTS_LOCALES[lang] || 'en-US',
        rate: 0.95,
        pitch: 1.0,
        onDone: () => setSpeaking(false),
        onStopped: () => setSpeaking(false),
        onError: () => setSpeaking(false),
      });
    } catch {
      setSpeaking(false);
    }
  };

  const stop = async () => {
    try {
      await Speech.stop();
    } catch {
      /* noop */
    }
    setSpeaking(false);
  };

  return (
    <Pressable
      onPress={speaking ? stop : start}
      style={({ pressed }) => [styles.btn, pressed && { opacity: 0.7 }]}
      hitSlop={6}
      testID={testID || 'read-aloud-btn'}
    >
      <View style={styles.icon}>
        {speaking ? (
          <Pause color={colors.primary} size={16} strokeWidth={2.6} />
        ) : (
          <Volume2 color={colors.primary} size={16} strokeWidth={2.6} />
        )}
      </View>
      <Text style={styles.label}>
        {speaking ? t(lang, 'read_aloud_stop') : t(lang, 'read_aloud_play')}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.full,
    backgroundColor: colors.primarySoft,
    alignSelf: 'flex-start',
  },
  icon: {
    width: 22,
    height: 22,
    borderRadius: radius.full,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.bold,
    color: colors.primary,
  },
});
