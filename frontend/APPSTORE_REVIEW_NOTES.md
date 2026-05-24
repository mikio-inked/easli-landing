# easli — App Store Connect / Play Console Review Notes

> **Audience:** Apple App Reviewer · Play Console Reviewer · internal QA.  
> **Bundle:** `com.easli.app`  ·  **Version:** see `app.json` → `expo.version`.  
> **Reviewer contact:** review@easli.app (24 h response time, business days).  
> **Last updated:** 2026-05-24.

This file is what we paste into App Store Connect → App Review → *Notes*
AND into Play Console → App content → *App access*. It gives the
reviewer everything needed to evaluate easli in under 5 minutes.

---

## 1. Demo account / sign-in requirements

**There is no sign-in.** easli uses an anonymous, randomly-generated
device ID stored in the iOS keychain / Android keystore. The reviewer
does NOT need a demo account; on first launch the app is fully usable
immediately.

For RevenueCat paywall verification we provide a sandbox tester account
in section §5 below.

---

## 2. What easli does (one paragraph for context)

easli is a document-only OCR-and-explain assistant for European
paperwork. You photograph an official letter (tax notice, bill, court
letter …) and easli returns a plain-language summary in the language
you chose, a category, a risk level, the deadlines, the required
actions and a ready-to-send reply draft — in the SENDER’s language.
There is no free-form chat, no image generation, no avatars, no social
feed, no companion AI. The full moderation pipeline is documented in
`SUBMISSION_GUIDELINE_2_1.md`.

---

## 3. 5-minute walkthrough for the reviewer

### Step 1 — Onboarding

1. Launch easli for the first time.
2. The language picker appears. Pick **“English”** (or any other).
3. Tap **“Continue”**.
4. Tap **“Allow notifications”** when asked (optional, used only for
   deadline reminders the user opts in for).

### Step 2 — Scan a sample document (no camera needed)

1. On the Home screen tap **“Upload from gallery”**.
2. Pick any official letter you have, OR use one of the bundled sample
   PDFs under **Settings → Help → Try sample documents**. Three
   pre-installed fixtures:
   - `sample_de_finanzamt.pdf` (German tax notice)
   - `sample_fr_dgfip.pdf` (French tax notice)
   - `sample_it_cartella.pdf` (Italian debt-collection letter)
3. Wait 20–25 s. The analysis screen opens.

### Step 3 — Validate the result screen

- **Country chip** — first row, leftmost: shows the detected country
  (🇩🇪 Germany / 🇫🇷 France / 🇮🇹 Italy) with a green confidence dot.
- **Source language chip** — next to it, shows the detected document
  language.
- **Risk hero** — a green / yellow / red card with a one-sentence why.
- **4 tabs** — Overview, Actions, Reply, Details. Tap each.

### Step 4 — Validate the Reply tab (linguistic correctness)

1. Tap **“Reply”**.
2. The recommended intent (“Ask for clarification”) is highlighted; tap
   **“Generate reply”**.
3. After ~5 s, the reply text appears.
4. For the German fixture, the reply MUST start with “Sehr geehrte…”
   and end with “Mit freundlichen Grüßen” (Phase 6d invariant).
5. The accompanying short “Explanation” text appears in your chosen UI
   language (e.g. English).

### Step 5 — Validate the “Report” flow (Guideline 1.2 compliance)

1. Scroll to the bottom of any result screen.
2. Tap the small **“Report this analysis”** link.
3. The modal opens. Pick a reason (e.g. “Wrong or incomplete analysis”).
4. (Optional) type a short comment.
5. Tap **“Send report”**.
6. A green toast confirms reception. The modal closes. The flow is
   anonymous — no PII is sent; the document content is NOT included.

### Step 6 — Validate DSGVO controls

1. Open **Settings**.
2. Tap **“Export my data”** → a JSON file with every analysis is
   produced (Art. 15 DSGVO).
3. Tap **“Delete all my data”** → confirm → all analyses are purged
   within ~1 s (Art. 17 DSGVO).

---

## 4. Paywall location & how to reset quota for testing

### Where the paywall lives

- The user has **3 free analyses**. The 4th attempt opens the paywall
  sheet automatically.
- The paywall is also reachable from **Settings → Upgrade to Plus**.
- The paywall is presented via **RevenueCat’s Paywall** widget, with
  weekly + monthly options.
- On Apple, the products are: `easli_plus_weekly`, `easli_plus_monthly`.
  On Google Play: `easli_plus_weekly`, `easli_plus_monthly` (same IDs).

### How to reset quota for a fresh test

*Internal dev-tools endpoint is enabled in TestFlight / Internal-Track
builds:*

```
POST  https://easli.app/api/dev/usage/reset?device_id={YOUR_DEVICE_ID}
```

The device ID is displayed at the bottom of **Settings → About**
(“Device ID: ab12…”). Copy it, paste into the URL, hit it from a browser
— the response is `{"ok":true,"reset":true}`. The paywall re-arms
immediately.

If the reviewer cannot make the HTTP call, they can simply reinstall
the app — a fresh install gets a fresh device-ID and fresh 3 free
analyses.

---

## 5. RevenueCat sandbox tester accounts

### Apple sandbox (App Store)

| Field | Value |
|---|---|
| Sandbox e-mail | `easli-review+ios@example.com` |
| Password | (provided in App Store Connect review submission text — NEVER stored in source). |
| Region | DE |
| Tier to test | Plus Monthly (`easli_plus_monthly`) |

**Sandbox-test path:**

1. Sign out of the App Store → Sign in with the sandbox tester account.
2. In easli, exhaust 3 free analyses → paywall appears.
3. Tap “Plus Monthly” → confirm in the Apple sheet.
4. Sandbox renewals take 3 min instead of 30 days — wait 3 min to test
   auto-renewal.
5. Verify the badge in Settings shows “Plus active until …”.

### Google Play sandbox

| Field | Value |
|---|---|
| License tester e-mail | `easli-review+android@example.com` (already added to Play Console license testers). |
| Tier to test | Plus Monthly. |

With license-tester e-mail signed in on the device, the purchase flow
opens in **test-card mode** automatically — the reviewer can pick “Test
card, always approves” and the entitlement activates with no actual
charge.

---

## 6. Supported countries / regions

easli targets the **European Union** as the primary market with full
linguistic + jurisdiction support for:

| Country | Language | Jurisdiction anchors (analyser) |
|---|---|---|
| Germany (DE) | de | Finanzamt, Bundeszentralamt für Steuern, Krankenkasse, Amtsgericht, Bürgeramt |
| Austria (AT) | de | BMF, FA, ÖGK, BG, BH |
| Switzerland (CH) | de | Steuerverwaltung, Betreibungsamt |
| Netherlands (NL) | nl | Belastingdienst, UWV, CJIB |
| Belgium (BE) | nl/fr | Belastingdienst / Service public fédéral Finances |
| Luxembourg (LU) | de/fr | Administration des contributions directes |
| France (FR) | fr | DGFiP, CAF, CPAM, URSSAF, ANTAI |
| Spain (ES) | es | AEAT, INSS, Tesorería |
| Italy (IT) | it | Agenzia delle Entrate, INPS, Agenzia delle Entrate Riscossione |
| Portugal (PT) | pt | Autoridade Tributária |
| Poland (PL) | pl | Urząd Skarbowy, ZUS |
| Czechia (CZ) | cs | Finanční úřad |
| Sweden (SE) | sv | Skatteverket, Kronofogden |
| Denmark (DK) | da | Skattestyrelsen, SKAT |
| Finland (FI) | fi | Verohallinto |

Documents from outside this list are still analysed, but the country
chip falls back to “Not clear from this letter” (verified anti-
hallucination behaviour — see analyser prompt in `core/prompts/analyze.py`).

The app UI is localised in **11 languages**; the analysis summary is
localised in **25 languages**.

---

## 7. Common reviewer questions & quick answers

**Q. Where is the data stored?**  
A. MongoDB Atlas in EU-Frankfurt (DSGVO Art. 28 contract). Photos are
NEVER stored — only the OCR’d text + structured JSON. 90-day TTL
auto-delete via index on `created_at`.

**Q. Is this app a tax / legal advice app?**  
A. No. The disclaimer on every analysis says easli provides general
information only and does not give legal, tax, financial or medical
advice. The user is always referred to the sender or a qualified
professional.

**Q. Could the AI produce hate speech / political opinion / unsafe
output?**  
A. Structurally no. The model is forced via `response_format=json_object`
to fit a strict Pydantic schema where every text field has a constrained
purpose (summary, deadline, required action). The system prompt
explicitly forbids opinions and off-topic content. See
`SUBMISSION_GUIDELINE_2_1.md` §3 for the full moderation contract.

**Q. Does easli use the user’s scanned letters to train the AI?**  
A. No. Mistral AI is contractually bound NOT to train on customer
prompts (DPA Art. 28). easli additionally does not store images at all.

**Q. What if a user uploads a non-document (e.g. a meme)?**  
A. OCR returns empty / unreadable text; the analyser bails out with
HTTP 422 “No readable text was found. Please retry with a clearer
photo.” No analysis is produced.

---

## 8. Contact

For escalations the operator answers in German + English at
**review@easli.app** within 24 hours on business days.
