# easli — App Store Screenshots

**55 screenshots** for Apple App Store submission (5 scenes × 11 UI languages).

All images are **1290 × 2796 px** (6.7"/6.9" iPhone requirement — covers
iPhone 15 Pro Max, iPhone 16 Pro Max). Apple also accepts these as the
fallback for smaller devices.

## Folder structure

```
out/
├── ios-6.9-de/  # German
├── ios-6.9-en/  # English
├── ios-6.9-fr/  # French
├── ios-6.9-it/  # Italian
├── ios-6.9-es/  # Spanish
├── ios-6.9-pl/  # Polish
├── ios-6.9-ar/  # Arabic (RTL)
├── ios-6.9-tr/  # Turkish
├── ios-6.9-ru/  # Russian
├── ios-6.9-vi/  # Vietnamese
└── ios-6.9-zh/  # Chinese (Simplified)
```

Each folder contains 5 PNGs in the recommended App Store sequence:

| # | File | Message |
|---|------|---------|
| 1 | `01-language-picker-{lang}.png` | "11 languages. Zero stress." — USP: eleven-language support |
| 2 | `02-home-{lang}.png`            | "Letter? Snap. Done." — hero CTA + recent paperwork |
| 3 | `03-scan-{lang}.png`            | "One snap. Every page." — multi-page scanner |
| 4 | `04-result-{lang}.png`          | "Plain language. In yours." — AI summary + deadline |
| 5 | `05-reply-{lang}.png`           | "Reply? In two seconds." — AI-drafted reply |

## How to upload to App Store Connect

1. Open **App Store Connect → My Apps → easli → [version] → Prepare for Submission**.
2. Scroll to **Localizations** and pick each language (add a new localization
   if missing).
3. Under **App Previews and Screenshots** → **iPhone 6.9" Display**, drag the
   5 PNGs from the matching folder in order.
4. Apple accepts drag-drop multi-file.
5. Save. Repeat for each of the 11 languages.

## Regenerate

From `/app/scripts/store_screenshots/`:

```bash
# All 11 languages, all 5 scenes
python3 generate.py

# Only one language
python3 generate.py --only en

# Only selected scenes
python3 generate.py --scenes 1,4

# Combine
python3 generate.py --only de --scenes 1,2,3
```

Edit `strings.py` to tweak headlines, sublines, or the in-phone mock UI copy
for any language.

## Design notes

- Canvas: 1290 × 2796 (portrait, 9:19.5)
- Brand colour: `#1F6FEB` (easli blue)
- Background: subtle gradient `#EEF4FF → #F5F8FF → #FFFFFF`
- Device: iPhone 15 Pro Max silhouette with Dynamic Island and 9:41 status bar
- Fonts: Noto Sans (Latin/Cyrillic/Greek), Noto Naskh Arabic (AR), Noto Sans CJK (ZH)
- RTL: Arabic text is automatically reshaped + bidi-reordered before rendering
