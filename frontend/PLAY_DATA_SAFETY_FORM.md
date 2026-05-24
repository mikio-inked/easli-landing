# easli — Google Play Console: Data Safety Form

> **Audience:** Operator filling out Play Console → App content → Data safety.  
> **Status:** Ready to paste — last reviewed 2026-05-24.  
> **DSGVO basis:** Art. 6(1)(b) (contract) + Art. 6(1)(f) (legitimate interest = anti-spam, integrity).

Google Play asks 4 macro-questions. Below are the verbatim answers, in
the exact order the form presents them, with the data-type checkboxes
you must tick. Where the form asks “Provide a link to your privacy
policy”, use **`https://easli.app/privacy`** (already configured in the
Store Listing).

---

## Q1. Does your app collect or share any of the required user data types?

**Answer:** Yes.

---

## Q2. Is all of the user data collected by your app encrypted in transit?

**Answer:** Yes.  
*Justification:* every backend call uses HTTPS (TLS 1.2+); the Mistral
API is called over HTTPS; MongoDB Atlas connection enforces TLS.

---

## Q3. Do you provide a way for users to request that their data be deleted?

**Answer:** Yes.  
*Where:* Settings → “Delete all my data” → calls `DELETE /api/history/{device_id}`, which purges every analysis + chat message tied to the anonymous device-ID within 1 s.

---

## Q4. Data collected and purpose

Tick the following categories. Everything else stays **un-ticked**.

### 4a. Personal info

| Data type | Collected | Shared | Optional | Processing purpose | Reason |
|---|---|---|---|---|---|
| Name | ❌ | ❌ | — | — | not collected |
| Email address | ❌ | ❌ | — | — | not collected |
| User IDs | ✅ | ❌ | yes (auto-gen) | App functionality | Anonymous UUIDv4 stored client-side in Android Keystore to scope the user’s analyses + paywall entitlement. No login, no account. |
| Address / Phone / Race / … | ❌ | ❌ | — | — | not collected |

### 4b. Financial info

| Data type | Collected | Shared | Optional | Processing purpose | Reason |
|---|---|---|---|---|---|
| Purchase history | ✅ | ❌ | required to track Plus entitlement | App functionality, Account management | RevenueCat receives the Google Play purchase token; easli only stores the resulting entitlement (`active`/`expired`) keyed to the device-ID. |
| Credit card / Other financial info | ❌ | ❌ | — | — | Google Play handles payment; easli never sees card data. |

### 4c. Photos and videos

| Data type | Collected | Shared | Optional | Processing purpose | Reason |
|---|---|---|---|---|---|
| Photos | ✅ | ✅ (with Mistral) | required (the document you scan) | App functionality | Photos are sent to Mistral OCR + Mistral Chat (EU servers). easli **never stores the photo** on its own servers; only the OCR’d text + structured analysis are persisted. |
| Videos | ❌ | ❌ | — | — | not collected |

### 4d. Audio files

All un-ticked.

### 4e. Files and docs

| Data type | Collected | Shared | Optional | Processing purpose | Reason |
|---|---|---|---|---|---|
| Files and docs | ✅ | ✅ (with Mistral) | required | App functionality | When the user picks a PDF the same rule as photos applies — only OCR’d text persists. |

### 4f. Calendar / Contacts

All un-ticked.  
*Note:* easli **adds** events to the calendar via `expo-calendar`, but does NOT READ existing calendar entries. The Play Form only asks about COLLECTION; write-only access is therefore reported as “not collected”.

### 4g. App activity

| Data type | Collected | Shared | Optional | Processing purpose | Reason |
|---|---|---|---|---|---|
| App interactions | ✅ | ❌ | optional (only telemetry) | Analytics, Crash diagnostics | We log API call types + latencies for capacity planning. NO message bodies, NO photos, NO PII (verified via Privacy Log Audit in CI). |
| In-app search history | ❌ | ❌ | — | — | not collected |
| Other user-generated content | ✅ | ❌ | optional (only if user files a report) | App functionality | The “Report this analysis” modal stores the user’s optional 500-char comment; auto-deleted after 90 days. |

### 4h. App info and performance

| Data type | Collected | Shared | Optional | Processing purpose | Reason |
|---|---|---|---|---|---|
| Crash logs | ✅ | ✅ (Sentry, EU region) | optional (off by default in dev) | Crash diagnostics | Stack-traces with content-scrubbing via `beforeSend`. |
| Diagnostics | ✅ | ❌ | optional | App diagnostics | Backend metadata logs (model id, char counts, latencies). |
| Other app performance data | ❌ | ❌ | — | — | not collected |

### 4i. Device or other IDs

| Data type | Collected | Shared | Optional | Processing purpose | Reason |
|---|---|---|---|---|---|
| Device or other IDs | ✅ | ❌ | required (the anonymous UUIDv4) | App functionality | Same UUIDv4 as 4a row 3. No IDFA, no Google Advertising ID, no IMEI. |

---

## Q5. Why is data “shared” with third parties?

The only category we share is the document image + OCR’d text, and the
only third party is **Mistral AI (Paris, FR)** under a written DPA.

- **Recipient:** Mistral AI — 30 rue Vaneau, 75007 Paris, France.
- **Purpose:** OCR + analysis + reply generation; processor under Art. 28 DSGVO.
- **Retention by Mistral:** per their public policy, prompts + completions are NOT used for training and are retained for 30 days for abuse detection only.
- **Location:** EU only.
- **Link to their DPA:** https://mistral.ai/terms#dpa

For crash reports the recipient is **Sentry** (EU region, sentry.io).
They are a processor, not an independent controller.

---

## Final note on the form

Google wants you to confirm “All data types are accurate” at the bottom
of the form — we ARE accurate; the above mirrors exactly what the code
does. If you ever add a new SDK, run the privacy CI script and update
this file in lock-step.
