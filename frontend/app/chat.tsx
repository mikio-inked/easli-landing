// Document-scoped chat screen.
// Lets the user ask questions about ONE specific analyzed document. The
// backend system prompt strictly limits the bot to this document's content
// and refuses unrelated requests.

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft,
  Eraser,
  Info,
  Send,
  ShieldAlert,
  Sparkles,
} from 'lucide-react-native';
import {
  ChatMessage,
  clearChatMessages,
  getAnalysis,
  listChatMessages,
  sendChatMessage,
} from '../src/api';
import { ensureDeviceId, getLanguage as getStoredLanguage } from '../src/store';
import { LanguageCode, t } from '../src/i18n';
import { colors, fontSize, fontWeight, radius, spacing } from '../src/theme';

interface DisplayMessage extends ChatMessage {
  pending?: boolean;
}

export default function ChatScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [lang, setLang] = useState<LanguageCode>('en');
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [docTitle, setDocTitle] = useState<string>('');
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const listRef = useRef<FlatList<DisplayMessage> | null>(null);

  const scrollToEnd = useCallback(() => {
    setTimeout(() => listRef.current?.scrollToEnd?.({ animated: true }), 50);
  }, []);

  useEffect(() => {
    (async () => {
      const l = (await getStoredLanguage()) ?? 'en';
      setLang(l);
      if (!id) {
        setLoading(false);
        return;
      }
      try {
        const did = await ensureDeviceId();
        const [rec, msgs] = await Promise.all([
          getAnalysis(id, did),
          listChatMessages(id, did),
        ]);
        setDocTitle(rec.result.document_type || rec.result.sender || '');
        setMessages(msgs);
        scrollToEnd();
      } catch (e: any) {
        Alert.alert(t(lang, 'error_generic'), e?.message || '');
      } finally {
        setLoading(false);
      }
    })();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const send = async (text: string) => {
    if (!id) return;
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setInput('');
    setSending(true);
    const did = await ensureDeviceId();

    // Optimistic user bubble + thinking placeholder.
    const optimisticUser: DisplayMessage = {
      role: 'user',
      content: trimmed,
      off_topic: false,
      created_at: new Date().toISOString(),
    };
    const thinking: DisplayMessage = {
      role: 'assistant',
      content: t(lang, 'chat_thinking'),
      off_topic: false,
      created_at: new Date().toISOString(),
      pending: true,
    };
    setMessages((prev) => [...prev, optimisticUser, thinking]);
    scrollToEnd();

    try {
      const reply = await sendChatMessage(id, did, trimmed);
      setMessages((prev) => {
        const next = prev.filter((m) => !m.pending);
        return [...next, reply];
      });
    } catch (e: any) {
      setMessages((prev) => prev.filter((m) => !m.pending && m !== optimisticUser));
      Alert.alert(t(lang, 'error_generic'), e?.message || '');
    } finally {
      setSending(false);
      scrollToEnd();
    }
  };

  const onClear = () => {
    if (!id || messages.length === 0) return;
    Alert.alert(t(lang, 'chat_clear_confirm'), '', [
      { text: t(lang, 'cancel'), style: 'cancel' },
      {
        text: t(lang, 'delete'),
        style: 'destructive',
        onPress: async () => {
          try {
            const did = await ensureDeviceId();
            await clearChatMessages(id, did);
            setMessages([]);
          } catch (e: any) {
            Alert.alert(t(lang, 'error_generic'), e?.message || '');
          }
        },
      },
    ]);
  };

  const starters: string[] = [
    t(lang, 'chat_starter_1'),
    t(lang, 'chat_starter_2'),
    t(lang, 'chat_starter_3'),
    t(lang, 'chat_starter_4'),
  ];

  const isEmpty = !loading && messages.length === 0;

  return (
    <SafeAreaView style={styles.safe} testID="chat-screen">
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} testID="chat-back" hitSlop={12}>
          <ArrowLeft color={colors.textPrimary} size={26} strokeWidth={2.4} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>{t(lang, 'ask_question')}</Text>
          {docTitle ? (
            <Text style={styles.headerSub} numberOfLines={1}>
              {docTitle}
            </Text>
          ) : null}
        </View>
        <Pressable
          onPress={onClear}
          disabled={messages.length === 0}
          hitSlop={12}
          testID="chat-clear"
          style={messages.length === 0 ? { opacity: 0.3 } : null}
        >
          <Eraser color={colors.textSecondary} size={22} strokeWidth={2.2} />
        </Pressable>
      </View>

      <View style={styles.scopeBanner} testID="chat-scope-banner">
        <Info color={colors.primary} size={14} strokeWidth={2.5} />
        <Text style={styles.scopeText}>{t(lang, 'chat_scope_note')}</Text>
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 12 : 0}
      >
        {isEmpty ? (
          <View style={styles.emptyWrap} testID="chat-empty">
            <View style={styles.emptyIcon}>
              <Sparkles color={colors.primary} size={26} strokeWidth={2.4} />
            </View>
            <Text style={styles.emptyTitle}>{t(lang, 'chat_empty_title')}</Text>
            <Text style={styles.emptySub}>{t(lang, 'chat_empty_sub')}</Text>
            <View style={{ gap: spacing.sm, width: '100%', marginTop: spacing.md }}>
              {starters.map((s, i) => (
                <Pressable
                  key={i}
                  onPress={() => send(s)}
                  disabled={sending}
                  style={({ pressed }) => [
                    styles.starter,
                    pressed && { opacity: 0.85 },
                    sending && { opacity: 0.5 },
                  ]}
                  testID={`chat-starter-${i}`}
                >
                  <Text style={styles.starterText}>{s}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(_, i) => String(i)}
            contentContainerStyle={styles.list}
            renderItem={({ item }) => <Bubble msg={item} />}
            onContentSizeChange={scrollToEnd}
          />
        )}

        <View style={styles.composerWrap}>
          <View style={styles.composer}>
            <TextInput
              value={input}
              onChangeText={setInput}
              placeholder={t(lang, 'chat_placeholder')}
              placeholderTextColor={colors.textMuted}
              style={styles.input}
              multiline
              editable={!sending}
              testID="chat-input"
              returnKeyType="send"
              blurOnSubmit={false}
              onSubmitEditing={() => send(input)}
            />
            <Pressable
              onPress={() => send(input)}
              disabled={!input.trim() || sending}
              style={[
                styles.sendBtn,
                (!input.trim() || sending) && { opacity: 0.4 },
              ]}
              testID="chat-send"
            >
              <Send color={colors.white} size={20} strokeWidth={2.5} />
            </Pressable>
          </View>
          <Text style={styles.disclaimer}>{t(lang, 'disclaimer_short')}</Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Bubble({ msg }: { msg: DisplayMessage }) {
  const isUser = msg.role === 'user';
  const isOffTopic = msg.off_topic && !isUser;
  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowBot]}>
      <View
        style={[
          styles.bubble,
          isUser ? styles.bubbleUser : styles.bubbleBot,
          isOffTopic && styles.bubbleOffTopic,
          msg.pending && { opacity: 0.7 },
        ]}
      >
        {isOffTopic ? (
          <View style={styles.offTopicChip}>
            <ShieldAlert color={colors.yellow.text} size={12} strokeWidth={2.5} />
          </View>
        ) : null}
        <Text
          style={[
            styles.bubbleText,
            isUser ? styles.bubbleTextUser : styles.bubbleTextBot,
          ]}
        >
          {msg.content}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
    backgroundColor: colors.surface,
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.textPrimary,
  },
  headerSub: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },
  scopeBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    backgroundColor: colors.primarySoft,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  scopeText: {
    flex: 1,
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  list: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  row: { flexDirection: 'row', marginBottom: 6 },
  rowUser: { justifyContent: 'flex-end' },
  rowBot: { justifyContent: 'flex-start' },
  bubble: {
    maxWidth: '82%',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 18,
  },
  bubbleUser: {
    backgroundColor: colors.primary,
    borderBottomRightRadius: 4,
  },
  bubbleBot: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    borderBottomLeftRadius: 4,
  },
  bubbleOffTopic: {
    backgroundColor: colors.yellow.bg,
    borderColor: colors.yellow.border,
  },
  bubbleText: {
    fontSize: fontSize.base,
    lineHeight: 22,
  },
  bubbleTextUser: {
    color: colors.white,
  },
  bubbleTextBot: {
    color: colors.textPrimary,
  },
  offTopicChip: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.yellow.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  emptyWrap: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: 16,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  emptyTitle: {
    fontSize: fontSize['2xl'],
    fontWeight: fontWeight.extrabold,
    color: colors.textPrimary,
  },
  emptySub: {
    fontSize: fontSize.base,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  starter: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  starterText: {
    fontSize: fontSize.base,
    color: colors.textPrimary,
    fontWeight: fontWeight.medium,
  },
  composerWrap: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    gap: 6,
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    backgroundColor: colors.background,
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  input: {
    flex: 1,
    minHeight: 36,
    maxHeight: 140,
    fontSize: fontSize.base,
    color: colors.textPrimary,
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disclaimer: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: spacing.md,
  },
});
