// ScamWarningModal — full-screen sheet shown when an analysis is flagged
// as potentially fraudulent. Auto-pops on first display so the user
// cannot scroll past a critical warning.

import { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AlertOctagon, Eye, ShieldCheck, X } from 'lucide-react-native';
import { LanguageCode, t } from '../i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../theme';

const STORAGE_PREFIX = 'klarpost.scamShown.';

interface Props {
  analysisId: string | null;
  reason: string;
  lang: LanguageCode;
}

export function ScamWarningModal({ analysisId, reason, lang }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!analysisId || !reason) return;
    let cancelled = false;
    (async () => {
      const seen = await AsyncStorage.getItem(STORAGE_PREFIX + analysisId);
      if (!cancelled && !seen) {
        // First time the user sees this analysis — auto-show.
        setVisible(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [analysisId, reason]);

  const handleClose = async () => {
    if (analysisId) {
      try {
        await AsyncStorage.setItem(STORAGE_PREFIX + analysisId, '1');
      } catch {
        /* noop — modal still closes */
      }
    }
    setVisible(false);
  };

  if (!analysisId || !reason) return null;

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={handleClose}
      testID="scam-modal"
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <View style={styles.iconWrap}>
              <AlertOctagon color={colors.red.text} size={28} strokeWidth={2.4} />
            </View>
            <Pressable onPress={handleClose} hitSlop={10} testID="scam-modal-close">
              <X color={colors.textPrimary} size={24} strokeWidth={2.4} />
            </Pressable>
          </View>

          <Text style={styles.title}>{t(lang, 'scam_modal_title')}</Text>
          <Text style={styles.subtitle}>{t(lang, 'scam_modal_subtitle')}</Text>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            <View style={styles.reasonCard}>
              <View style={styles.reasonIconWrap}>
                <Eye color={colors.red.text} size={18} strokeWidth={2.4} />
              </View>
              <Text style={styles.reasonText}>{reason}</Text>
            </View>

            <Text style={styles.tipHeader}>{t(lang, 'scam_modal_tips_title')}</Text>
            <View style={styles.tipsBlock}>
              <Tip text={t(lang, 'scam_modal_tip_1')} />
              <Tip text={t(lang, 'scam_modal_tip_2')} />
              <Tip text={t(lang, 'scam_modal_tip_3')} />
              <Tip text={t(lang, 'scam_modal_tip_4')} />
            </View>
          </ScrollView>

          <Pressable
            onPress={handleClose}
            style={({ pressed }) => [styles.cta, pressed && { opacity: 0.92 }]}
            testID="scam-modal-acknowledge"
          >
            <Text style={styles.ctaText}>{t(lang, 'scam_modal_acknowledge')}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function Tip({ text }: { text: string }) {
  return (
    <View style={styles.tipRow}>
      <View style={styles.tipDot}>
        <ShieldCheck color={colors.green.text} size={14} strokeWidth={2.6} />
      </View>
      <Text style={styles.tipText}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.background,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    padding: spacing.lg,
    maxHeight: '90%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: radius.full,
    backgroundColor: colors.red.bg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
    letterSpacing: -0.4,
  },
  subtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.base,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  body: {
    marginTop: spacing.md,
  },
  reasonCard: {
    flexDirection: 'row',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    backgroundColor: colors.red.bg,
    borderWidth: 1,
    borderColor: colors.red.border,
    marginBottom: spacing.lg,
  },
  reasonIconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.full,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  reasonText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.red.text,
    lineHeight: 21,
    fontWeight: fontWeight.semibold,
  },
  tipHeader: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  tipsBlock: {
    gap: 10,
    marginBottom: spacing.lg,
  },
  tipRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  tipDot: {
    width: 22,
    height: 22,
    borderRadius: radius.full,
    backgroundColor: colors.green.bg,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  tipText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 21,
  },
  cta: {
    marginTop: spacing.md,
    backgroundColor: colors.red.solid,
    paddingVertical: spacing.md,
    borderRadius: radius.lg,
    alignItems: 'center',
  },
  ctaText: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.extrabold,
    color: colors.white,
    letterSpacing: 0.2,
  },
});
