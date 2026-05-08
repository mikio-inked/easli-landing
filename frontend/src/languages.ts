// /src/languages.ts ─ Phase EU-1: European multilingual paperwork support
//
// Three SEPARATE language registries:
//
//   1. SOURCE_LANGUAGES       — languages a user-uploaded document can be in.
//                               Used for detection display ("Document detected: Greek")
//                               and for the manual "Reply language" override.
//
//   2. EXPLANATION_LANGUAGES  — languages the user can choose to RECEIVE
//                               the explanation, summary, and chat answers.
//                               Mistral AI generates output in these languages.
//
//   3. REPLY_LANGUAGES        — languages a reply draft can be written in.
//                               Same set as SOURCE_LANGUAGES (you reply in the
//                               sender's language). Default reply language ==
//                               detected document language.
//
// IMPORTANT — this is a metadata registry. The existing UI i18n strings
// (`/src/i18n.ts`) still drive the app's chrome (button labels, error text).
// Adding a new ExplanationLanguage here does NOT require translating the
// whole app — it just tells Mistral which language to write the analysis in.
//
// Privacy: language codes are sent to the backend as ISO-639-1 / ISO-639-3
// strings only. No third-party language detection SDK; Mistral handles it.

export type LanguageEntry = {
  /** ISO-639-1 (or BCP-47 with script tag where ambiguous, e.g. 'zh-Hans') */
  code: string;
  /** Native language name as it would appear in that language */
  nativeName: string;
  /** English name for cross-language display & analytics */
  englishName: string;
  /** Regional indicator emoji or country flag (UI only). May be empty for
      pan-regional languages like Arabic. */
  flag: string;
};

// ─────────────────────────────────────────────────────────────────────────
//  A. SOURCE LANGUAGES — uploaded documents may be in any of these
// ─────────────────────────────────────────────────────────────────────────
export const SOURCE_LANGUAGES: LanguageEntry[] = [
  { code: 'de',  nativeName: 'Deutsch',     englishName: 'German',      flag: '🇩🇪' },
  { code: 'en',  nativeName: 'English',     englishName: 'English',     flag: '🇬🇧' },
  { code: 'fr',  nativeName: 'Français',    englishName: 'French',      flag: '🇫🇷' },
  { code: 'es',  nativeName: 'Español',     englishName: 'Spanish',     flag: '🇪🇸' },
  { code: 'it',  nativeName: 'Italiano',    englishName: 'Italian',     flag: '🇮🇹' },
  { code: 'pt',  nativeName: 'Português',   englishName: 'Portuguese',  flag: '🇵🇹' },
  { code: 'nl',  nativeName: 'Nederlands',  englishName: 'Dutch',       flag: '🇳🇱' },
  { code: 'pl',  nativeName: 'Polski',      englishName: 'Polish',      flag: '🇵🇱' },
  { code: 'ro',  nativeName: 'Română',      englishName: 'Romanian',    flag: '🇷🇴' },
  { code: 'cs',  nativeName: 'Čeština',     englishName: 'Czech',       flag: '🇨🇿' },
  { code: 'hu',  nativeName: 'Magyar',      englishName: 'Hungarian',   flag: '🇭🇺' },
  { code: 'el',  nativeName: 'Ελληνικά',    englishName: 'Greek',       flag: '🇬🇷' },
  { code: 'bg',  nativeName: 'Български',   englishName: 'Bulgarian',   flag: '🇧🇬' },
  { code: 'hr',  nativeName: 'Hrvatski',    englishName: 'Croatian',    flag: '🇭🇷' },
  { code: 'sk',  nativeName: 'Slovenčina',  englishName: 'Slovak',      flag: '🇸🇰' },
  { code: 'sl',  nativeName: 'Slovenščina', englishName: 'Slovenian',   flag: '🇸🇮' },
  { code: 'lt',  nativeName: 'Lietuvių',    englishName: 'Lithuanian',  flag: '🇱🇹' },
  { code: 'lv',  nativeName: 'Latviešu',    englishName: 'Latvian',     flag: '🇱🇻' },
  { code: 'et',  nativeName: 'Eesti',       englishName: 'Estonian',    flag: '🇪🇪' },
  { code: 'sv',  nativeName: 'Svenska',     englishName: 'Swedish',     flag: '🇸🇪' },
  { code: 'da',  nativeName: 'Dansk',       englishName: 'Danish',      flag: '🇩🇰' },
  { code: 'fi',  nativeName: 'Suomi',       englishName: 'Finnish',     flag: '🇫🇮' },
  { code: 'ga',  nativeName: 'Gaeilge',     englishName: 'Irish',       flag: '🇮🇪' },
  { code: 'mt',  nativeName: 'Malti',       englishName: 'Maltese',     flag: '🇲🇹' },
  { code: 'no',  nativeName: 'Norsk',       englishName: 'Norwegian',   flag: '🇳🇴' },
  { code: 'is',  nativeName: 'Íslenska',    englishName: 'Icelandic',   flag: '🇮🇸' },
  { code: 'sr',  nativeName: 'Српски',      englishName: 'Serbian',     flag: '🇷🇸' },
  { code: 'sq',  nativeName: 'Shqip',       englishName: 'Albanian',    flag: '🇦🇱' },
  { code: 'bs',  nativeName: 'Bosanski',    englishName: 'Bosnian',     flag: '🇧🇦' },
  { code: 'uk',  nativeName: 'Українська',  englishName: 'Ukrainian',   flag: '🇺🇦' },
  { code: 'ru',  nativeName: 'Русский',     englishName: 'Russian',     flag: '🇷🇺' },
  { code: 'tr',  nativeName: 'Türkçe',      englishName: 'Turkish',     flag: '🇹🇷' },
  { code: 'ar',  nativeName: 'العربية',     englishName: 'Arabic',      flag: '🇸🇦' },
];

// ─────────────────────────────────────────────────────────────────────────
//  B. EXPLANATION LANGUAGES — the analysis can be written in any of these.
//
//  This is the user's "I want my paperwork explained in ___" choice.
//  A subset of source languages plus several non-European immigrant
//  community languages (Persian, Urdu, Hindi, Chinese, Vietnamese).
// ─────────────────────────────────────────────────────────────────────────
export const EXPLANATION_LANGUAGES: LanguageEntry[] = [
  { code: 'en',      nativeName: 'English',     englishName: 'English',                flag: '🇬🇧' },
  { code: 'de',      nativeName: 'Deutsch',     englishName: 'German',                 flag: '🇩🇪' },
  { code: 'fr',      nativeName: 'Français',    englishName: 'French',                 flag: '🇫🇷' },
  { code: 'es',      nativeName: 'Español',     englishName: 'Spanish',                flag: '🇪🇸' },
  { code: 'it',      nativeName: 'Italiano',    englishName: 'Italian',                flag: '🇮🇹' },
  { code: 'pt',      nativeName: 'Português',   englishName: 'Portuguese',             flag: '🇵🇹' },
  { code: 'nl',      nativeName: 'Nederlands',  englishName: 'Dutch',                  flag: '🇳🇱' },
  { code: 'pl',      nativeName: 'Polski',      englishName: 'Polish',                 flag: '🇵🇱' },
  { code: 'ro',      nativeName: 'Română',      englishName: 'Romanian',               flag: '🇷🇴' },
  { code: 'cs',      nativeName: 'Čeština',     englishName: 'Czech',                  flag: '🇨🇿' },
  { code: 'hu',      nativeName: 'Magyar',      englishName: 'Hungarian',              flag: '🇭🇺' },
  { code: 'el',      nativeName: 'Ελληνικά',    englishName: 'Greek',                  flag: '🇬🇷' },
  { code: 'bg',      nativeName: 'Български',   englishName: 'Bulgarian',              flag: '🇧🇬' },
  { code: 'hr',      nativeName: 'Hrvatski',    englishName: 'Croatian',               flag: '🇭🇷' },
  { code: 'sr',      nativeName: 'Српски',      englishName: 'Serbian',                flag: '🇷🇸' },
  { code: 'sq',      nativeName: 'Shqip',       englishName: 'Albanian',               flag: '🇦🇱' },
  { code: 'uk',      nativeName: 'Українська',  englishName: 'Ukrainian',              flag: '🇺🇦' },
  { code: 'ru',      nativeName: 'Русский',     englishName: 'Russian',                flag: '🇷🇺' },
  { code: 'tr',      nativeName: 'Türkçe',      englishName: 'Turkish',                flag: '🇹🇷' },
  { code: 'ar',      nativeName: 'العربية',     englishName: 'Arabic',                 flag: '🇸🇦' },
  { code: 'fa',      nativeName: 'فارسی',       englishName: 'Persian (Farsi)',        flag: '🇮🇷' },
  { code: 'ur',      nativeName: 'اردو',        englishName: 'Urdu',                   flag: '🇵🇰' },
  { code: 'hi',      nativeName: 'हिन्दी',       englishName: 'Hindi',                  flag: '🇮🇳' },
  { code: 'zh-Hans', nativeName: '简体中文',     englishName: 'Chinese (Simplified)',   flag: '🇨🇳' },
  { code: 'vi',      nativeName: 'Tiếng Việt',  englishName: 'Vietnamese',             flag: '🇻🇳' },
];

// ─────────────────────────────────────────────────────────────────────────
//  C. REPLY LANGUAGES — same as source. You reply in the sender's language.
// ─────────────────────────────────────────────────────────────────────────
export const REPLY_LANGUAGES: LanguageEntry[] = SOURCE_LANGUAGES;

// ─────────────────────────────────────────────────────────────────────────
//  Lookup helpers
// ─────────────────────────────────────────────────────────────────────────
const buildIndex = (entries: LanguageEntry[]): Record<string, LanguageEntry> => {
  const out: Record<string, LanguageEntry> = {};
  for (const e of entries) out[e.code.toLowerCase()] = e;
  return out;
};

const SOURCE_INDEX = buildIndex(SOURCE_LANGUAGES);
const EXPLANATION_INDEX = buildIndex(EXPLANATION_LANGUAGES);
// Fallback for codes from any registry — used to render arbitrary detected
// language codes (e.g. one of the 32 source languages) on the result screen.
const ANY_INDEX = { ...SOURCE_INDEX, ...EXPLANATION_INDEX };

export function getSourceLanguage(code?: string | null): LanguageEntry | undefined {
  if (!code) return undefined;
  return SOURCE_INDEX[code.toLowerCase()];
}

export function getExplanationLanguage(code?: string | null): LanguageEntry | undefined {
  if (!code) return undefined;
  return EXPLANATION_INDEX[code.toLowerCase()];
}

export function getAnyLanguage(code?: string | null): LanguageEntry | undefined {
  if (!code) return undefined;
  return ANY_INDEX[code.toLowerCase()];
}

/** Display "Deutsch (German)" or fall back to the raw code. Safe for any
 *  detected code from Mistral, including ones we don't know about. Also
 *  handles our legacy i18n code quirks (e.g. `de_simple` → `de`,
 *  `zh` → `zh-Hans`, `ar-*` → `ar`). */
export function formatLanguageLabel(code?: string | null, fallback = ''): string {
  if (!code) return fallback;
  const normalized = normalizeLanguageCode(code);
  const entry = getAnyLanguage(normalized);
  if (!entry) return normalized.toUpperCase();
  if (entry.nativeName.toLowerCase() === entry.englishName.toLowerCase()) {
    return entry.nativeName;
  }
  return `${entry.nativeName} (${entry.englishName})`;
}

/** Collapse app-internal language codes (`de_simple`, `zh`, `nb`, etc.) to
 *  the registry's canonical codes. Also handles common BCP-47 variants
 *  like `en-US` → `en`. Case-insensitive. */
export function normalizeLanguageCode(code: string): string {
  const c = code.toLowerCase().trim();
  // App-internal "Einfaches Deutsch" flag we no longer surface to users.
  if (c === 'de_simple' || c === 'de-simple') return 'de';
  // Chinese simplified/traditional common variants.
  if (c === 'zh' || c === 'zh-cn' || c === 'zh_cn' || c === 'zh_hans') return 'zh-Hans';
  if (c === 'zh-tw' || c === 'zh_tw' || c === 'zh_hant') return 'zh-Hans'; // we only ship Simplified
  // Norwegian bokmål/nynorsk → generic Norwegian.
  if (c === 'nb' || c === 'nn' || c === 'nb-no' || c === 'nn-no') return 'no';
  // Serbian Cyrillic/Latin → generic Serbian.
  if (c === 'sr-cyrl' || c === 'sr-latn' || c === 'sr_cyrl' || c === 'sr_latn') return 'sr';
  // BCP-47 country variants we don't need to distinguish (en-US, en-GB,
  // fr-FR, fr-CA, es-ES, es-MX, etc.) — take the primary subtag.
  const dash = c.indexOf('-');
  const underscore = c.indexOf('_');
  const cut = dash !== -1 ? dash : underscore;
  if (cut > 0 && c.length > 3 && c !== 'zh-hans') {
    return c.slice(0, cut);
  }
  return c;
}

/** Country code (ISO 3166-1 alpha-2) → flag emoji.
 *  Pure functional: works for any 2-letter code without a lookup table. */
export function countryCodeToFlag(code?: string | null): string {
  if (!code || code.length !== 2) return '';
  const upper = code.toUpperCase();
  const A = 0x41, REGIONAL_OFFSET = 0x1f1a5;
  return (
    String.fromCodePoint(upper.charCodeAt(0) + REGIONAL_OFFSET - A) +
    String.fromCodePoint(upper.charCodeAt(1) + REGIONAL_OFFSET - A)
  );
}
