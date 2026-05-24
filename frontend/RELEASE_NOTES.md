# easli 2.0 — Release Notes

**Version**: 2.0 (Marketing) / 1.0.1 (`app.json`)
**Codename**: EU-Upgrade
**Release Date**: TBD (Submission-Ready)
**Platforms**: iOS (App Store) · Android (Google Play)

---

## 🇪🇺 EU-First Paperwork Assistant

easli 2.0 ist ein vollständiges Upgrade vom deutschen MVP (KlarPost) zum europaweiten Paperwork-Assistant für 11 UI-Sprachen und 25 Erklärsprachen.

---

## ✨ Highlights

### 1. Automatische Länder-Erkennung (Multi-Country EU)
- Briefe werden automatisch einem EU-Land zugeordnet (DE, AT, CH, FR, IT, ES, NL, BE, PL, PT, SE, DK, FI, IE, GR, CZ, HU, …).
- Sichtbar im Result-Screen als **Country-Chip** (Flagge + ISO-Code) mit Confidence-Dot (🟢 high / 🟡 medium / 🔴 low).
- Country-Chip auch in der History-Liste — sofort erkennbar, ohne den Brief erneut zu öffnen.

### 2. Länderspezifische Salutations & Sign-offs
- **Reply-Generator** rendert opener + sign-off deterministisch aus einer Salutation-Library pro Sprache:
  - 🇩🇪 `Sehr geehrte Frau Schulz,` … `Mit freundlichen Grüßen`
  - 🇫🇷 `Madame Schulz,` … `Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.`
  - 🇬🇧 `Dear Ms. Schulz,` … `Yours faithfully,`
  - 🇮🇹 `Gentile Sig.ra Schulz,` … `Distinti saluti,`
- Honorific-Stripping (Frau/Herr/Madame/Sig./Dhr.) + Last-Name-Extraktion automatisch.
- Keine `[Your Name]` Platzhalter mehr.

### 3. Document-Type Anchors (Regional)
- Per-Country Anker für Dokument-Typen verbessern die Kategorisierung:
  - 🇩🇪 `Mahnung`, `Steuerbescheid`, `Bußgeldbescheid`, `Mahnbescheid`
  - 🇫🇷 `Avis d'imposition`, `Mise en demeure`
  - 🇮🇹 `Cartella esattoriale`, `Avviso di accertamento`
  - 🇪🇸 `Notificación de Hacienda`
- Anker setzen `category` UND `detected_country_code` bei einem einzigen literalen Treffer.

### 4. Regional Scam-Detection
- Länderspezifische Scam-Patterns (gegated auf high-confidence country detection):
  - Gefälschte `Bundespolizei`-Briefe mit gmail-Absender + iTunes/BTC-Forderung → `risk=red`, `scam_warning=true`.
  - Phishing-Muster auf französischen `Impôts.gouv`-Imitationen mit ausländischer IBAN.
- Kalibrierte `scam_reason` ohne Panik-Sprache.

### 5. In-App Report-Flow (App Store Guideline 1.2)
- Neuer `Report this analysis` Button auf jeder Analyse-Detail-Seite.
- Modal mit 4 Gründen (Spam, Falsche Erkennung, Beleidigend, Sonstiges) + Freitext.
- Haptic Feedback (`selection` → `success`) — App Store Review Guideline 1.2 erfüllt.
- Backend persistiert in `reports` Collection.

### 6. RevenueCat Paywall
- Native Paywall via RevenueCat, hardened entitlement evaluation.
- Webhook-Idempotency via Event-Ring-Buffer (kein Double-Crediting).
- `INITIAL_PURCHASE`, `RENEWAL`, `EXPIRATION`, `NON_RENEWING_PURCHASE` → korrekt gemapped.
- Single-Letter-Credits Pack.

### 7. App Lock (iOS/Android)
- Face ID / Touch ID / Geräte-Passcode Lock im Settings-Screen.
- App Re-Lock bei Background → Foreground Wechsel.
- DSGVO-konform: nur lokales SecureStore-Flag, kein Tracking.

### 8. Dark Mode
- Vollständiges Dark Theme über alle Screens (Home, Result, History, Settings, Privacy, Inbox).
- System-Theme-Detection + manueller Override im Settings-Screen.

### 9. Kalender-Integration
- Fristen aus Briefen lassen sich mit einem Tap als Kalender-Event speichern.
- Native iOS/Android Calendar Permission Flow nach `<handle_permissions_contract>`.

### 10. Email-Forwarding Inbox (Beta)
- Eigener `@inbox.easli.app` Alias (DNS-Setup via Mailgun pending User-Action).
- Briefe per Mail-Forward direkt in die App.

### 11. Privacy-First Architektur (DSGVO Art. 15 + 17)
- **Datenresidenz**: 100 % EU (Mistral AI · Paris, Frankreich).
- **Keine Original-Bilder** in MongoDB.
- **TTL-Index**: 90-Tage automatische Löschung aller Analysen.
- **GET /api/export** (DSGVO Art. 15) — vollständiger JSON-Export per Knopfdruck.
- **DELETE /api/history/{device_id}** (DSGVO Art. 17) — vollständiges Löschen aller Daten.
- **Redacted Logs**: keine Sender, Beträge, IBANs, Personen in Backend-Logs.
- **Request-Validation-Error** Body-Stripping (keine Base64-Bild-Echoes in 422).

---

## 🌍 Sprachen

### UI-Sprachen (11)
🇩🇪 Deutsch · 🇩🇪 Einfaches Deutsch · 🇬🇧 English · 🇫🇷 Français · 🇮🇹 Italiano · 🇪🇸 Español · 🇵🇱 Polski · 🇹🇷 Türkçe · 🇷🇺 Русский · 🇻🇳 Tiếng Việt · 🇨🇳 中文

### Erklär-Sprachen (25)
Alle 11 UI-Sprachen + Niederländisch, Portugiesisch, Schwedisch, Dänisch, Finnisch, Tschechisch, Ungarisch, Griechisch, Rumänisch, Bulgarisch, Slowakisch, Kroatisch, Slowenisch, Arabisch, Hindi.

---

## 🏗 Technical / Architektur

### Backend-Refactor (Phasen 3 – 7)
- `server.py`: **2 800 → 107 Zeilen** (-96 %), reines App-Bootstrap.
- `core/prompts.py`: monolithisch → `core/prompts/` Sub-Package (analyze, reply, chat, translate, _country_packs, _salutations).
- `services/ai_service.py`: 744 Zeilen → `services/ai/` Sub-Package (client, analyze, translate, chat, language_gate, normalizers).
- Late-bound Mistral Client-Injection via `core.config.mistral_client`.
- 0 Regressionen über 25+ Test-Steps.

### AI / Modelle
- **Mistral Large 2512** (`mistral-large-2512`) für Analyse, Reply, Translation, Chat.
- **Mistral OCR API** für Vision-First Pipeline (jeder Brief → strukturiertes Markdown).
- Defensive `_coerce_literal()` Sanitisation für robuste Pydantic Validation.

### Marketing-Assets
- **121 Store-Screenshots** (iOS 6.7"/6.5"/5.5" + Android 16:9) für alle 11 UI-Sprachen.
- EU Country-Chip in jedem Screenshot.
- Store-Texte für alle 11 Sprachen in `STORE_LISTING_TEXTS.md`.

### Submission-Artefakte
- `SUBMISSION_GUIDELINE_2_1.md` — Apple Guideline 2.1 Antworten.
- `APPSTORE_REVIEW_NOTES.md` — Notes for Apple Reviewer.
- `PLAY_DATA_SAFETY_FORM.md` — Google Play Data Safety Form.
- `PRIVACY_POLICY.md` + `privacy.html` (easli-branded).
- `PRIVACY_HOSTING_GUIDE.md` — Hosting-Anleitung für Privacy URL.

---

## 🔒 Sicherheit & Compliance

- **DSGVO/GDPR**: Art. 15 (Auskunft) + Art. 17 (Löschung) endpoints live.
- **App Store Guideline 1.2** (User-Generated Content): Report-Flow + Moderation.
- **App Store Guideline 2.1** (App Completeness): Antworten dokumentiert.
- **iOS Privacy Manifest**: vollständig deklariert (DeviceID, Photos, UserContent + 4 API Categories).
- **Android Data Safety Form**: vollständig befüllt.

---

## ⚠️ Bekannte offene Punkte (User-Actions)

| # | Punkt | Owner | Status |
|---|-------|-------|--------|
| 1 | Mailgun DNS-Records (`mx`, `dkim`) für `@inbox.easli.app` setzen | User | ⏳ Pending |
| 2 | Mistral Dev-Key rotieren (Prod-Key in EAS Secrets ist sauber) | User | ⏳ Pending |
| 3 | RevenueCat Sandbox Test-Accounts in App Store Connect hinterlegen | User | ⏳ Pending |
| 4 | `privacy.html` auf `https://easli.app/privacy` hosten | User | ⏳ Pending |
| 5 | App Store Connect: Screenshots hochladen (iOS 6.7" + 6.5" + 5.5") | User | ⏳ Pending |
| 6 | Google Play Console: Screenshots + Data Safety Form ausfüllen | User | ⏳ Pending |

---

**Maintained by**: easli Team
**Architecture**: Senior Full-Stack Architect (Claude/Emergent) + Grok (xAI)
**Backend**: FastAPI · MongoDB Atlas · Mistral AI (Paris, FR)
**Frontend**: React Native · Expo Router · RevenueCat · Sentry
