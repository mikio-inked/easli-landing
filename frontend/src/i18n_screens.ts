// easli — Screen-specific i18n strings
// ---------------------------------------------------------------------------
// Lightweight bag of translations that aren't in the main STRINGS table to
// avoid bloating UIKey for one-off screen labels. Used by language.tsx and
// reply-language.tsx — both have a small number of UI strings outside the
// main flow.
//
// Pattern: 11 UI-language codes × N keys. Falls back to English ('en') when
// the requested language isn't in the table.
//
// Add to STRINGS in i18n.ts ONLY when a label is reused in 3+ screens. For
// one-shot labels this file is the right place.

import type { LanguageCode } from './i18n';

type ScreenLangSet = {
  [K in LanguageCode]?: Record<string, string>;
};

// All language codes have an entry; missing codes auto-fall back to 'en'.
const screenStrings: ScreenLangSet = {
  de_simple: {
    app_language_title: 'App-Sprache',
    app_language_subtitle: 'Sprache der Menüs, Buttons und Fehlermeldungen.',
    reply_language_title: 'Antwortsprache',
    reply_language_auto_label: 'Automatisch (Absender-Sprache)',
    reply_language_auto_sub:
      'Antworte in der Sprache des Briefes. Erkannt wird sie beim Scan.',
    reply_language_fixed_label: 'Immer in fester Sprache',
    reply_language_fixed_sub:
      'Antworte immer in der gewählten Sprache, unabhängig vom Absender.',
    reply_language_pick: 'Antwortsprache wählen',
  },
  en: {
    app_language_title: 'App language',
    app_language_subtitle: 'The language of menus, buttons and error messages.',
    reply_language_title: 'Reply language',
    reply_language_auto_label: 'Automatic (match sender)',
    reply_language_auto_sub:
      'Reply in the same language the letter is written in. Detected automatically.',
    reply_language_fixed_label: 'Always in a fixed language',
    reply_language_fixed_sub:
      'Always draft replies in your pinned language, regardless of the sender.',
    reply_language_pick: 'Pick reply language',
  },
  es: {
    app_language_title: 'Idioma de la app',
    app_language_subtitle: 'El idioma de los menús, botones y mensajes de error.',
    reply_language_title: 'Idioma de respuesta',
    reply_language_auto_label: 'Automático (idioma del remitente)',
    reply_language_auto_sub:
      'Responde en el mismo idioma del documento. Se detecta automáticamente.',
    reply_language_fixed_label: 'Siempre en un idioma fijo',
    reply_language_fixed_sub:
      'Redacta siempre las respuestas en el idioma elegido, sin importar el remitente.',
    reply_language_pick: 'Elegir idioma de respuesta',
  },
  fr: {
    app_language_title: "Langue de l'app",
    app_language_subtitle: 'La langue des menus, boutons et messages.',
    reply_language_title: 'Langue de réponse',
    reply_language_auto_label: "Automatique (langue de l'expéditeur)",
    reply_language_auto_sub:
      "Répondez dans la langue du courrier. Détectée automatiquement.",
    reply_language_fixed_label: 'Toujours dans une langue fixe',
    reply_language_fixed_sub:
      "Rédige toujours les réponses dans la langue choisie, peu importe l'expéditeur.",
    reply_language_pick: 'Choisir la langue de réponse',
  },
  it: {
    app_language_title: "Lingua dell'app",
    app_language_subtitle: 'La lingua di menu, pulsanti e messaggi di errore.',
    reply_language_title: 'Lingua di risposta',
    reply_language_auto_label: 'Automatica (lingua del mittente)',
    reply_language_auto_sub:
      'Rispondi nella lingua della lettera. Viene rilevata automaticamente.',
    reply_language_fixed_label: 'Sempre in una lingua fissa',
    reply_language_fixed_sub:
      'Scrivi sempre le risposte nella lingua scelta, indipendentemente dal mittente.',
    reply_language_pick: 'Scegli la lingua di risposta',
  },
  pl: {
    app_language_title: 'Język aplikacji',
    app_language_subtitle: 'Język menu, przycisków i komunikatów o błędach.',
    reply_language_title: 'Język odpowiedzi',
    reply_language_auto_label: 'Automatycznie (język nadawcy)',
    reply_language_auto_sub:
      'Odpowiadaj w języku listu. Wykrywany automatycznie podczas skanowania.',
    reply_language_fixed_label: 'Zawsze w stałym języku',
    reply_language_fixed_sub:
      'Pisz odpowiedzi zawsze w wybranym języku, niezależnie od nadawcy.',
    reply_language_pick: 'Wybierz język odpowiedzi',
  },
  ar: {
    app_language_title: 'لغة التطبيق',
    app_language_subtitle: 'لغة القوائم والأزرار ورسائل الخطأ.',
    reply_language_title: 'لغة الرد',
    reply_language_auto_label: 'تلقائي (لغة المرسل)',
    reply_language_auto_sub: 'الرد بنفس لغة الرسالة. يتم اكتشافها تلقائيًا.',
    reply_language_fixed_label: 'دائمًا بلغة ثابتة',
    reply_language_fixed_sub:
      'اكتب الردود دائمًا باللغة التي تختارها، بغض النظر عن المرسل.',
    reply_language_pick: 'اختر لغة الرد',
  },
  tr: {
    app_language_title: 'Uygulama dili',
    app_language_subtitle: 'Menülerin, düğmelerin ve hata mesajlarının dili.',
    reply_language_title: 'Yanıt dili',
    reply_language_auto_label: 'Otomatik (gönderen dili)',
    reply_language_auto_sub:
      'Yanıtı mektubun dilinde yaz. Tarama sırasında otomatik algılanır.',
    reply_language_fixed_label: 'Her zaman sabit bir dilde',
    reply_language_fixed_sub:
      'Yanıtları her zaman seçilen dilde yaz, gönderene bakma.',
    reply_language_pick: 'Yanıt dilini seç',
  },
  ru: {
    app_language_title: 'Язык приложения',
    app_language_subtitle: 'Язык меню, кнопок и сообщений об ошибках.',
    reply_language_title: 'Язык ответа',
    reply_language_auto_label: 'Автоматически (язык отправителя)',
    reply_language_auto_sub:
      'Отвечайте на языке письма. Определяется автоматически.',
    reply_language_fixed_label: 'Всегда на фиксированном языке',
    reply_language_fixed_sub:
      'Всегда писать ответы на выбранном языке, независимо от отправителя.',
    reply_language_pick: 'Выбрать язык ответа',
  },
  vi: {
    app_language_title: 'Ngôn ngữ ứng dụng',
    app_language_subtitle: 'Ngôn ngữ của menu, nút và thông báo lỗi.',
    reply_language_title: 'Ngôn ngữ trả lời',
    reply_language_auto_label: 'Tự động (ngôn ngữ người gửi)',
    reply_language_auto_sub:
      'Trả lời bằng ngôn ngữ của thư. Tự động phát hiện khi quét.',
    reply_language_fixed_label: 'Luôn dùng ngôn ngữ cố định',
    reply_language_fixed_sub:
      'Luôn soạn câu trả lời bằng ngôn ngữ đã chọn, bất kể người gửi.',
    reply_language_pick: 'Chọn ngôn ngữ trả lời',
  },
  zh: {
    app_language_title: '应用语言',
    app_language_subtitle: '菜单、按钮和错误消息的语言。',
    reply_language_title: '回复语言',
    reply_language_auto_label: '自动(匹配发件人)',
    reply_language_auto_sub: '使用信件的语言回复。扫描时自动检测。',
    reply_language_fixed_label: '始终使用固定语言',
    reply_language_fixed_sub: '始终用您选择的语言起草回复,无论发件人是谁。',
    reply_language_pick: '选择回复语言',
  },
};

export function ts(lang: LanguageCode | null | undefined, key: string): string {
  const code = (lang || 'en') as LanguageCode;
  return (
    screenStrings[code]?.[key] ??
    screenStrings.en?.[key] ??
    key /* last-resort: show the key so missing translations are obvious in QA */
  );
}
