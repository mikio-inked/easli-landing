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
// Covers every language present in EXPLANATION_LANGUAGES (37 codes) plus
// some aliases. For unknown codes the resolver below falls back to passing
// the raw language tag (e.g. "sk") which iOS/Android still try to honour
// before defaulting to system language.
const TTS_LOCALES: Partial<Record<LanguageCode | string, string>> = {
  // UI-supported (11)
  en: 'en-US',
  de: 'de-DE',
  de_simple: 'de-DE',
  es: 'es-ES',
  fr: 'fr-FR',
  it: 'it-IT',
  pl: 'pl-PL',
  ru: 'ru-RU',
  tr: 'tr-TR',
  vi: 'vi-VN',
  zh: 'zh-CN',
  'zh-Hans': 'zh-CN',
  'zh-Hant': 'zh-TW',
  ar: 'ar-SA',
  // Western European
  pt: 'pt-PT',
  nl: 'nl-NL',
  ga: 'ga-IE',
  mt: 'mt-MT',
  // Nordic
  sv: 'sv-SE',
  da: 'da-DK',
  no: 'nb-NO',  // Bokmål — most common Norwegian on iOS
  nb: 'nb-NO',
  nn: 'nn-NO',
  fi: 'fi-FI',
  is: 'is-IS',
  // Baltic
  et: 'et-EE',
  lv: 'lv-LV',
  lt: 'lt-LT',
  // Central / Eastern European
  ro: 'ro-RO',
  cs: 'cs-CZ',
  sk: 'sk-SK',
  sl: 'sl-SI',
  hu: 'hu-HU',
  hr: 'hr-HR',
  sr: 'sr-RS',
  bs: 'bs-BA',
  sq: 'sq-AL',
  bg: 'bg-BG',
  el: 'el-GR',
  uk: 'uk-UA',
  // Middle East / Asian
  fa: 'fa-IR',
  ur: 'ur-PK',
  hi: 'hi-IN',
};

/** Resolve a TTS locale string for a given language code.
 *  Falls back to the bare language tag (system TTS will then try its closest
 *  match), and finally to en-US as a last-ditch default. */
function resolveTtsLocale(code: string | null | undefined): string {
  if (!code) return 'en-US';
  const direct = TTS_LOCALES[code as LanguageCode];
  if (direct) return direct;
  // strip region/variant suffixes ("zh-CN" → "zh") for the lookup
  const base = code.split(/[-_]/)[0];
  const baseHit = TTS_LOCALES[base as LanguageCode];
  if (baseHit) return baseHit;
  // Last resort: hand the raw code to the engine. iOS/Android usually pick
  // a sane default if the language is installed; otherwise they no-op.
  return base || 'en-US';
}

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
        language: resolveTtsLocale(lang),
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
      accessibilityRole="button"
      accessibilityLabel={t(lang, 'read_aloud_a11y')}
      accessibilityState={{ busy: speaking }}
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
