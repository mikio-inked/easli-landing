# easli — Apple App Store Review Notes (Guideline 2.1 & 1.1 / KI-Apps)

> **Audience:** Apple App Review · App Store Connect Reviewer · QA  
> **Bundle ID:** `com.easli.app`  ·  **Version:** see `app.json` → `expo.version`  
> **Category:** Productivity (primary) / Utilities (secondary)  
> **Age rating:** 4+  
> **Last reviewed:** 2026-05-24

This document explains how easli satisfies App Store Review Guidelines
**1.1.6 (Inappropriate Content)**, **1.2 (User-Generated Content / UGC
for AI Apps)**, **2.1 (App Completeness)**, **4.5.4 (Mobile-Only AI)**
and **5.1.1 (Privacy / DSGVO)**. It is intended as a reviewer briefing
so the reviewer can validate the moderation pipeline end-to-end on a
fresh device in under 5 minutes.

---

## 1. What easli does (one paragraph)

easli is a **document-only OCR-and-explain assistant** for European
paperwork. The user takes a photo (or picks a PDF) of an **official
letter** — a tax notice, debt-collection letter, court summons, health-
insurance bill, rental letter, etc. — and easli returns:

- a plain-language summary in the user's chosen language (25 supported),
- a category (`tax`, `court`, `health`, …),
- a risk level (green/yellow/red),
- explicit deadlines and required actions,
- a ready-to-send reply draft in the SENDER's language.

There is **no free-form chat input** that reaches the AI on the home
screen. There is **no image-generation, no audio-generation, no avatar,
no deepfake, no companion / role-play feature, no social feed**. easli
only explains the documents the user has photographed.

---

## 2. Input moderation — "only documents reach the AI"

easli accepts three input types, and each is constrained:

| Input | Channel | Pre-AI filter |
|---|---|---|
| **Photo (camera)** | `expo-camera` | Single image, capped to 10 pages per document, max 30 MB per page. No video, no live stream. |
| **PDF / image (gallery)** | `expo-image-picker` | Same caps. Filename + MIME type validated server-side. |
| **Chat about a document** | only AFTER an analysis exists, scoped to ONE document | the system prompt explicitly forbids off-topic answers and the model returns `{"off_topic": true, "reply": ""}` for anything outside the loaded document. |

There is **no free-text "ask anything" entry point**, no general
chatbot, no image-search, no web-browsing tool, no voice-to-anything,
no e-mail composition unrelated to a scanned document.

OCR is performed by Mistral OCR (EU-hosted) before the document text is
passed to the analysis model. The OCR layer rejects non-text inputs
gracefully — see `services/ocr_service.py`.

---

## 3. Output moderation — "the model cannot produce harmful content"

The analyser, the chat and the reply-generator all run against
**Mistral Large** (mistral-large-2512), the EU-based commercial model.
The system prompts (`core/prompts/`) constrain the model on four axes:

### 3.1 Topic constraint

```
You are a German-paperwork assistant. […]
You ONLY analyse the document the user has photographed.
You NEVER write opinions about politics, religion, ethnicity, sexuality,
or public figures. You NEVER discuss other people, conspiracies, or
current events. You ONLY describe the document at hand.
```
*(See `core/prompts/analyze.py` for the full system prompt — 20 330 chars
as of Phase 6.)*

### 3.2 No-advice constraint

The prompt explicitly forbids giving legal, tax, financial or medical
**advice**. The output is always framed as "this is what the letter
says / asks of you", not "this is what you should do". A standard
safety disclaimer is appended to every analysis:

> *"easli provides general information only and does not give legal, tax,
> financial, or medical advice. Please verify with the sender or a
> qualified professional."*

### 3.3 Scam-detection constraint

The analyser FLAGS scam letters (`scam_warning: true`, with a calm
explanation) but never WRITES a scam. The reply-generator system prompt
(`core/prompts/reply.py`) explicitly forbids:

- generating phishing text,
- impersonating an authority,
- writing anything that could harm a third party,
- writing harassment, threats, or insults toward the sender.

### 3.4 Format constraint (JSON schema enforcement)

The model is forced via Mistral's `response_format={"type":"json_object"}`
to return ONLY a structured JSON object that matches our `AnalysisResult`
Pydantic schema. Any free-form text outside the schema fails Pydantic
validation and the request is rejected with a `502` before being shown
to the user — see `services/ai/analyze.py` and
`services/ai/normalizers.py`.

This is the **strongest** moderation: even if the model attempted to
emit harmful prose, it would have to be inside a JSON value that maps to
a constrained `Literal` field (e.g. `risk_level: "green" | "yellow" |
"red"`), so structurally it cannot produce e.g. an open-ended hate-
speech paragraph.

---

## 4. User reporting — the "Report this analysis" button

In-line with Guideline 1.2's expectation that UGC apps offer a
low-friction reporting mechanism, **every result screen contains a
"Report" link** at the bottom of the scroll. Tapping it opens a modal
that lets the user pick one of five reasons:

1. *Wrong or incomplete analysis*
2. *Translation or language error*
3. *Offensive or harmful content*
4. *Missed a scam or dangerous letter*
5. *Something else*

The user may add an optional free-text comment (≤ 500 chars). On submit
the app sends an anonymous report (no document content, no PII) to
`POST /api/report`, which writes a record to the `reports` collection
with `{analysis_id, device_id, reason, comment, app_version, created_at,
status: "new"}`. The user sees a confirmation toast and the modal
closes.

Reports are rate-limited to **5 per device per day** so a malicious user
cannot spam the queue. The moderation queue is reviewed manually by the
operator (see internal Admin Panel at `/api/admin/reports?since=…`).

When a report is acted upon (analysis hidden from the user, model prompt
updated, or sender-name pattern blacklisted), the report status moves
`new → triaged → resolved`. We retain reports for **90 days** then
auto-delete via TTL — same retention as analyses.

Reviewer can validate this flow in step 4 of the **APPSTORE_REVIEW_NOTES.md**
demo script.

---

## 5. Why a 17+ rating is NOT required

Per Guideline 1.1.6, an AI app that **cannot** produce objectionable
content does NOT need a 17+ rating. easli meets all three of Apple's
criteria:

1. **Constrained input** — only photographed documents reach the AI;
   the user cannot type "draw me X" or "tell me about Y".
2. **Constrained output** — strict JSON-schema enforcement; no
   free-form prose channel exists.
3. **User reporting** — the in-app Report button described in §4 is
   available on every result.

easli targets the **4+** age rating. The German UI uses formal address
(Sie/Ihnen) and there is no profanity, no violence, no sexual content,
no gambling, no in-app purchases beyond the optional Plus subscription.

---

## 6. Privacy & DSGVO (Art. 13, 15, 17, 25)

| Requirement | easli's compliance |
|---|---|
| **No tracking** | `NSPrivacyTracking = false`, no Facebook/Google/AppsFlyer/Branch/AppsFlyer SDK, no SDK that collects IDFA. |
| **No login** | The app uses a randomly-generated anonymous device ID (UUIDv4) stored in `expo-secure-store`. No e-mail, no phone number, no name, no account. |
| **Data minimisation (Art. 5(1)(c))** | Document images are processed in-memory and **never** stored. Only the OCR'd text + the structured analysis result are persisted to MongoDB Atlas (EU-Frankfurt region). |
| **Storage limitation (Art. 5(1)(e))** | A MongoDB TTL index on `analyses.created_at` auto-deletes every analysis after **90 days**. See `main.py` → `ttl_index_ready`. |
| **Right of access (Art. 15)** | `GET /api/export?device_id=…` returns the full JSON dump of every analysis + every chat message linked to the device. The UI surfaces this via Settings → Export my data. |
| **Right to erasure (Art. 17)** | `DELETE /api/history/{device_id}` purges everything in MongoDB tied to the device. The UI surfaces this via Settings → Delete all my data. |
| **DPA (Art. 28)** | We have a Data-Processing Agreement with **Mistral AI** (Paris, FR) covering OCR + chat completions. Servers are in the EU only. |
| **Sub-processor list** | Mistral AI (EU), MongoDB Atlas (EU-Frankfurt), Sentry Errors (EU region — content scrubbed via `beforeSend`). |
| **Privacy Policy URL** | `https://easli.app/privacy` (linked from Settings + App Store listing). |

---

## 7. Demo for the reviewer

Full step-by-step in **`APPSTORE_REVIEW_NOTES.md`** (sister document).

Quick path:

1. Open the app → pick "English" on the language picker.
2. Tap "Upload" and pick the bundled sample PDF (a German Finanzamt
   letter). The analysis takes 20-25 s.
3. Verify the country chip shows "🇩🇪 Germany" with a green confidence
   dot.
4. Verify the reply tab generates a reply starting with
   "Sehr geehrte …" and ending with "Mit freundlichen Grüßen".
5. Scroll to the bottom of the result and tap the "Report this
   analysis" link → pick a reason → submit. A green toast confirms
   reception.
6. Open Settings → "Delete all my data" → confirm. All analyses are
   purged within ~1 s.

---

## 8. Contact

For any reviewer question: **review@easli.app**. We answer within 24 h
on business days.
