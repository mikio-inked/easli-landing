# KlarPost — Product Requirements Document (MVP)

## Vision
KlarPost helps people in Germany understand important German documents by
translating and explaining them clearly in their selected language. Designed
for immigrants, expats, seniors, and family members supporting relatives with
German paperwork.

Tagline: **"Understand German letters before they become a problem."**

## Stack
- **Frontend**: React Native + Expo (SDK 54, Expo Router file-based routing), TypeScript
- **Backend**: FastAPI + Motor (async MongoDB)
- **AI**: **Mistral AI 🇫🇷 (EU-hosted, DSGVO-friendly)** — `pixtral-large-latest` for vision OCR + analysis, `mistral-large-latest` for the document-scoped chat. Native `mistralai==1.9.11` SDK. (Migrated from OpenAI GPT-5.2 / Emergent LLM key for full EU data residency.)
- **Storage**: MongoDB (analysis results only — never the original document)
- **Auth**: Anonymous device-id (AsyncStorage) — placeholder for full auth later

## Source language → Target languages
Source is always German. Target languages (with native script):
- 简体中文 (Chinese Simplified, `zh`)
- Tiếng Việt (Vietnamese, `vi`)
- Türkçe (Turkish, `tr`)
- Русский (Russian, `ru`)
- English (`en`)
- Español (Spanish, `es`)

## Screens
1. **Onboarding** — 3 paged steps with illustrations, privacy reassurance, disclaimer
2. **Language picker** — single-tap selection, native script
3. **Home** — two large CTAs (Scan / Upload), recent analyses, language chip, history & settings
4. **Scan** — tips + iPhone camera launcher (or library fallback)
5. **Upload** — PDF or image picker with file-type validation
6. **Analyzing** — calm, sequential progress states (Reading → Extracting → Translating → Checking deadlines)
7. **Result** — stacked cards: Risk level, Summary, What this means, What to do next, Deadlines, Sender, German reply draft, Reply explanation, Questions, Uncertainties, Disclaimer
8. **History** — list of stored analyses with delete swipes
9. **Settings** — change language, delete all analyses, delete account, privacy, disclaimer, support

## Backend API
All routes prefixed with `/api`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/` | Health check |
| GET | `/api/languages` | List supported target languages |
| POST | `/api/analyze` | Analyze a base64 image or PDF in target language |
| GET | `/api/analyses?device_id=` | List analyses for a device |
| GET | `/api/analyses/{id}?device_id=` | Get one analysis |
| DELETE | `/api/analyses/{id}?device_id=` | Delete one analysis |
| DELETE | `/api/analyses?device_id=` | Delete all analyses for a device |

### `POST /api/analyze` request
```json
{
  "device_id": "string",
  "target_language": "zh|vi|tr|ru|en|es",
  "file_base64": "base64 string",
  "mime_type": "image/jpeg|image/png|image/webp|image/heic|application/pdf"
}
```
PDFs are converted to a PNG image (first page) on the server using PyMuPDF
before sending to GPT-5.2.

### Response
Structured `AnalysisRecord` with the AI result conforming to the schema in the
problem statement (document_type, sender, summary_translated,
simple_explanation_translated, key_points, deadlines[], required_actions[],
risk_level, risk_reason, german_reply_draft,
reply_draft_explanation_translated, questions_to_ask, uncertainties,
disclaimer).

## Risk levels
- **green** — informational only
- **yellow** — may need action
- **red** — deadline / payment / legal / urgent

## Privacy & data handling
- Original images and PDFs are **never** persisted server-side. They are
  decoded, sent to the model, and discarded.
- Only the structured analysis result + metadata (device id, language,
  timestamp) is stored in MongoDB.
- Users can delete individual analyses, all analyses, or fully reset (delete
  account → wipes local AsyncStorage and remote data).
- API keys live in backend `.env` only (`EMERGENT_LLM_KEY`).

## Safety rules enforced in the prompt
The system prompt explicitly forbids the model from:
- Diagnosing medical conditions or recommending treatment
- Telling the user whether they must or must not pay
- Providing legal/tax/financial/medical advice
The model must:
- Mark uncertainties clearly
- Recommend contacting the sender or a qualified advisor for important matters
- Always include a closing disclaimer

## Future / non-MVP
- Full email/password or Emergent Google auth (architecture is ready)
- Payments (Stripe with Emergent test key) for premium analyses / multi-page docs
- Optional storage of original document (off by default)
- Push notifications for upcoming deadlines
- Multi-page PDF analysis (currently first page only)
