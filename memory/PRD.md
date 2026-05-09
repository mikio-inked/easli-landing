# easli — Product Requirements Document (v1.0)

## Vision
**easli** helps people across Europe understand official, administrative,
and everyday paperwork in their own language. Designed for migrants, expats,
seniors, and anyone who struggles with bureaucratic letters in any
European language.

**Tagline:** *„Beherrsche deinen Papierkram. In jeder Sprache. In ganz Europa."*  
*(EN: "Master your paperwork. In any language. Across Europe.")*

**Brand:**
- Name: `easli` (always lowercase)
- Bundle-ID: `com.easli.app` (iOS + Android)
- Domain: `easli.app` (landing) · `api.easli.app` (backend)
- Apple App-ID: `6765859779` · Apple Team-ID: `PGL9WMXPG7`
- Owner: Martin Tran (`m.tran@icloud.com`, GitHub `mikio-inked`)

## Stack
- **Frontend**: React Native + Expo SDK 54, Expo Router (file-based), TypeScript
- **Backend**: FastAPI + Motor (async MongoDB Atlas), hosted on Railway
- **AI**: **Mistral AI 🇫🇷** (`mistral-large-2512` for OCR + analysis + chat,
  `mistral-ocr-latest` for fast OCR pre-stage). Native `mistralai==1.9.11` SDK.
  Model IDs are pinned via env vars (`MISTRAL_VISION_MODEL` /
  `MISTRAL_ANALYSIS_MODEL` / `MISTRAL_CHAT_MODEL`) so swapping is trivial.
  EU-hosted, no training on API data.
- **Storage**: MongoDB Atlas. Original images / PDFs are NEVER persisted.
  Analyses auto-delete after 90 days via TTL index.
- **Payments**: RevenueCat (`react-native-purchases` v10) wrapping Apple
  StoreKit + Google Play Billing. iOS public SDK key is hard-coded in
  `eas.json` (publicly safe by RC's design). Android key still pending.
- **Auth**: Anonymous device-id only (AsyncStorage). No email, no login.
- **TTS**: System voices via `expo-speech`. Quality ranking (Premium >
  Enhanced > Default). 40 BCP-47 locales mapped. One-time iOS hint pointing
  at *Settings → Accessibility → Spoken Content → Voices* if no premium
  voice is installed.
- **Notifications**: `expo-notifications`. Local reminders for deadlines.
  Android needs `POST_NOTIFICATIONS` (declared in `app.json`).

## Languages

### UI-Chrome (11 hand-translated languages)
`de`, `de_simple`, `en`, `es`, `fr`, `it`, `pl`, `ar`, `tr`, `ru`, `vi`, `zh`

`UI_STRING_CODES` in `frontend/src/i18n.ts` is the source of truth.
Falls back to English if a code isn't in this set.

### Explanation Languages (25 — what the AI writes analyses in)
DE/EN/ES/VI/TR/RU/ZH (UI-translated) + FR/IT/PT/NL/PL/RO/CS/HU/EL/BG/HR/SR/SQ/UK/AR/FA/UR/HI.

`EXPLANATION_LANGUAGES` in `backend/server.py` is the source of truth.
Frontend mirrors this in `frontend/src/languages.ts`. **Both must stay in
sync** — adding a code requires changes in both files.

### Reply Languages (32 — for generated reply drafts)
Same set as Explanation + auto-detect (defaults to source-document language).

## Source Languages
**Detected automatically.** No fixed source — letters can be in any European
language and the AI auto-detects it via `source_language_code`. This is the
key Phase EU-1 win over the old "always German source" model.

## Screens (Expo Router file structure)
```
app/
├── index.tsx           # Entry → onboarding or home
├── onboarding.tsx      # 3-step intro + consent
├── language.tsx        # 11 UI / 25 explanation language picker
├── home.tsx            # Two CTAs (Scan / Upload), recent analyses
├── scan.tsx            # Native scanner launcher
├── camera.tsx          # In-app camera fallback
├── upload.tsx          # PDF / image picker
├── analyzing.tsx       # Sequential progress states
├── result.tsx          # Risk hero + action pyramid + accordion details
├── chat.tsx            # Free-form Q&A about a document
├── reply-language.tsx  # Pick reply-draft language (auto / fixed)
├── history.tsx         # All past analyses with category filter
├── reminder.tsx        # Set deadline notification
├── original.tsx        # View saved original image (opt-in)
├── storage.tsx         # Manage stored originals
├── paywall.tsx         # RevenueCat offerings + purchase
├── privacy.tsx         # In-app privacy summary
└── legal/              # Imprint, contact, full privacy policy
```

## Backend API (all routes prefixed `/api`)

| Method | Path | Purpose |
|---|---|---|
| GET    | `/api/`                                           | Health |
| GET    | `/api/languages`                                  | List 7 legacy + 25 explanation languages |
| GET    | `/api/paywall/config`                             | Paywall mode + product IDs |
| GET    | `/api/usage/{device_id}`                          | Public usage view |
| POST   | `/api/analyze`                                    | OCR + analyze a base64 image / multi-page PDF |
| POST   | `/api/analyses/{id}/translate`                    | Re-render an analysis in a new explanation lang |
| POST   | `/api/analyses/{id}/generate-reply`               | Intent-based reply draft |
| POST   | `/api/analyses/{id}/chat`                         | Document Q&A |
| GET    | `/api/analyses/{id}/messages`                     | List chat messages |
| DELETE | `/api/analyses/{id}/messages`                     | Clear chat |
| GET    | `/api/analyses?device_id=`                        | List analyses |
| GET    | `/api/analyses/{id}?device_id=`                   | Get one analysis |
| DELETE | `/api/analyses/{id}?device_id=`                   | Delete one |
| DELETE | `/api/analyses?device_id=`                        | Delete all (legacy) |
| DELETE | `/api/history/{device_id}`                        | Delete all + chat (current) |
| GET    | `/api/export?device_id=`                          | DSGVO Art. 15 — full data export |
| POST   | `/api/revenuecat/webhook`                         | Server-side IAP reconciliation (opt-in auth) |
| POST   | `/api/dev/usage/reset` *(dev-only)*               | Reset usage record |
| POST   | `/api/dev/usage/simulate` *(dev-only)*            | Simulate paywall scenarios |

**Pending (Q1 2026):**
- `POST /api/redeem` — redemption codes (Friends & Family lifetime).
- `POST /api/admin/login` + admin endpoints — code generation, user management.

## Paywall

**Modes** (`PAYWALL_MODE` env var): `disabled` | `soft` | `hard`.
- `disabled`: no limits, no paywall.
- `soft` (current): 3 free analyses + 10 extra for testers, then upsell.
- `hard` (post-launch): 3 free, then mandatory paywall.

**Products** (RevenueCat IDs identical across stores):
| Product ID | Type | Price (€) | Entitlement |
|---|---|---|---|
| `easli_single_letter` | Consumable | 1.49 | `plus` (one-shot) |
| `easli_plus_monthly`  | Subscription | 4.99 | `plus` |
| `easli_plus_yearly`   | Subscription | 39.99 | `plus` |

**Soft caps for Plus:**
- 20 analyses/month (`PLUS_MONTHLY_ANALYSES`)
- 5 chat questions per document
- 20 total chat questions per testing window

## Privacy & DSGVO
- Original images / PDFs decoded → sent to Mistral → discarded. Never stored.
- Only the structured analysis result + `device_id` + `language` + `timestamp`
  are persisted. TTL index deletes them after 90 days (`ANALYSIS_TTL_DAYS`).
- DSGVO endpoints: `/export` (Art. 15) + `/history` DELETE (Art. 17), wired
  to Settings → "Daten exportieren" / "Alle Daten löschen".
- All API keys live in backend `.env` only. **Never in client / git.**
- Mistral API: EU-hosted (Paris), no training on customer data (per their
  default API policy).
- No tracking, no analytics SDK, no advertising IDs. iOS Privacy Manifest
  declares `NSPrivacyTracking: false` and proper API-usage reasons.

## Safety prompts
The system prompt explicitly forbids the model from:
- Diagnosing medical conditions or recommending treatment
- Telling the user whether they must or must not pay
- Providing legal/tax/financial/medical advice
- Inventing missing data (deadlines, country, sender)

It must:
- Mark uncertainties clearly in `uncertainties[]`
- Recommend contacting the sender or a qualified advisor for serious matters
- Flag scams/phishing only when ≥1 strong red flag is present (`scam_warning`)
- Populate `safety_disclaimer` for HIGH-risk docs (court / debt / immigration / eviction / termination)
- Always include a closing `disclaimer`

## Risk levels
- `green`: informational only
- `yellow`: may need action
- `red`: deadline / payment / legal / urgent

## Categories (12)
`tax`, `insurance`, `rent`, `bank`, `health`, `government`, `court`,
`utilities`, `telecom`, `work`, `education`, `other`

## Roadmap

### Done (v1.0)
- Multi-source-language detection (Phase EU-1)
- 11 UI / 25 explanation languages
- Reply Assistant with intent picker (Phase R5)
- Document chat (`/api/analyses/{id}/chat`)
- Reminders for deadlines
- TestFlight live, App Store assets ready
- Privacy Manifest, EU-hosted AI, full DSGVO surface
- Landing page (DE/EN/FR/ES/IT/PL) + 55 store screenshots

### In progress (Q1 2026)
- Admin panel (web at `api.easli.app/admin`)
- Redemption codes (Friends & Family lifetime)
- RevenueCat Apple wire-up + sandbox test
- Sentry error tracking
- Rate limiting on `/api/analyze` (slowapi)

### Backlog
- Calendar integration (`expo-calendar`) for deadlines
- Drag-to-reorder pages in scanner preview
- OpenAI / Azure-OpenAI TTS as Pro feature (DSGVO trade-off TBD)
- Landing page → 11 languages parity
- Modular split of `server.py` (3.3k LoC) and `result.tsx` (2.2k LoC)
- Mistral API key rotation (P1 security)
- GitHub Actions CI/CD
