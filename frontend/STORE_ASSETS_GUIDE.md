# easli — Store Assets Guide

Practical workflow to produce App Store + Google Play screenshots and
preview videos for the **full release**. Designed to be done on macOS in
60–90 minutes from nothing to ready-to-upload assets in DE + EN.

---

## 1. Required dimensions (Apple)

| Device class | Resolution | Required? |
|---|---|---|
| **6.9" iPhone 15/16 Pro Max** | 1290×2796 | **Required** for new submissions |
| **5.5" iPhone 8 Plus** | 1242×2208 | **Required** until Apple drops it (still in 2026) |
| 6.5" iPhone 11 Pro Max | 1242×2688 | Optional, fallback from 6.9" if not provided |
| iPad 13" | 2064×2752 | Optional unless you want iPad listing |

**Plan for v1**: Submit only **6.9" + 5.5"**. iPad later.

| Google Play | Resolution | Count |
|---|---|---|
| Phone screenshots | min 1080×1920 | 4–8 |
| Feature graphic | 1024×500 | 1 (required) |
| 7" tablet screenshots | min 1024×600 | optional |
| 10" tablet screenshots | min 1280×800 | optional |

---

## 2. Suggested 8-screen storytelling sequence

Same sequence works for both stores. Each screenshot tells one beat of the user's pain → relief journey.

| # | App Screen | DE Headline | EN Headline |
|---|---|---|---|
| 1 | Home / scan launch | „Brief? Foto. Fertig." | "Letter? Snap. Done." |
| 2 | Camera with detected page | „Ein Foto, alle Seiten" | "One snap, every page" |
| 3 | Result – Summary tab | „Klar erklärt — in deiner Sprache" | "Plain language — in yours" |
| 4 | Result – Deadlines tab | „Frist verpasst? Nicht mit easli." | "Never miss a deadline again" |
| 5 | Reply – Intent picker | „Antwort? In zwei Sekunden." | "Reply? In two seconds." |
| 6 | Reply – Draft + explainer | „Du weißt, was du sendest." | "You know what you're sending." |
| 7 | Settings – 25 languages | „25 Sprachen. 100 % du." | "25 languages. 100% you." |
| 8 | Privacy / disclaimer screen | „Anonym. EU-gehostet. Kein Training." | "Anonymous. EU-hosted. No AI training." |

Keep headlines **short** (3–6 words) and **concrete**. Avoid "innovative", "powerful", "amazing".

---

## 3. Capture the raw screenshots — macOS workflow

### Option A — iOS Simulator (recommended, free)

1. Open Xcode → Window → Devices & Simulators → boot **iPhone 15 Pro Max** (1290×2796 logical).
2. Install the easli `.ipa` from the `production-apk`-equivalent build, or open via Expo Go pointing to `https://api.easli.app`.
3. For each scene #1–#8, drive the app to that screen on the simulator.
4. Capture:
   ```bash
   xcrun simctl io booted screenshot ~/easli-screens/01-home.png
   ```
5. Repeat for all 8 scenes → DE locale → EN locale (switch the app language between captures).
6. For the 5.5" set: boot **iPhone 8 Plus** (1242×2208) and repeat. (You can take only English here — Apple will fall back to it for older devices.)

### Option B — Real iPhone (highest fidelity)

1. Connect your iPhone via cable.
2. Open QuickTime → File → New Movie Recording → choose iPhone as source.
3. Use **Cmd-Shift-4** (selection screenshot) → drag over the QuickTime preview frame.
4. Apple Store accepts these as long as they're 1290×2796. If yours is 1179×2556 (Pro non-Max), still acceptable.

### Tip — keep dummy data clean
- Use the same demo letter for every screenshot of one locale — looks consistent.
- For the **Reply** screen (#5–#6), make sure the explainer box is visible.
- For **Settings 25 languages** (#7), scroll until at least 8–10 languages are visible.
- Hide the dev-tools row by **not** triggering 5 taps on settings header.
- Make sure the time in the status bar is **9:41 AM** for that quintessential Apple look. iOS Simulator does this automatically when you screenshot.

---

## 4. Add marketing overlays (decorated screenshots)

Apple's reviewers don't require this, but it converts ~30% better in browse-and-scroll. Use **one** of these:

### Free tools
- **Apple's own Screenshots Studio** (in App Store Connect → Media Manager → "Screenshot studio") — basic, but free.
- **Mockuuups Studio** (free tier, web) — drag PNG, drop, export.
- **Figma** + a community template like "App Store Screenshot Template" — fully customisable, free.

### Paid but fast (~$15/mo, cancel anytime)
- **AppLaunchpad** ([applaunchpad.com](https://theapplaunchpad.com)) — best for batch generation per locale. ~30 min for 8 screenshots × 7 locales.
- **AppMockUp Studio** ([app-mockup.com](https://app-mockup.com)) — slick templates, 1290×2796 export.
- **Screenshots.pro** — great for video-style preview frames.

### Recommended layout
Each marketing screenshot has 3 zones:
```
┌─────────────────────────┐
│  Headline (top 18%)     │  ← bold, brand colour, 60-80pt
│  Subline (top 8%)       │  ← optional secondary
├─────────────────────────┤
│                         │
│   App screenshot in     │
│   phone frame, centred  │
│                         │
└─────────────────────────┘
```

### Brand colours (hex codes from `/app/frontend/src/theme.ts`)
- **Primary**: `#1F6FEB` (calm blue)
- **Primary Dark**: `#0F4FB8`
- **Background gradient top**: `#F5F8FF`
- **Background gradient bottom**: `#FFFFFF`

Use Inter or SF Pro for the headline. Both are free.

---

## 5. App Preview Video (15–30 seconds, optional but high-impact)

Apple allows up to **3 preview videos** per locale. They auto-loop. Stats: listings with at least one preview see ~25% higher install rate.

### Storyboard (≈15 sec)
1. **0:00–0:02** — Hand holds a paper letter (use a real Finanzamt envelope as prop)
2. **0:02–0:05** — Tap easli, point camera at letter, multi-page capture
3. **0:05–0:08** — Result screen scrolling — summary, deadline highlighted
4. **0:08–0:12** — Tap Reply tab, pick "Frist verlängern", draft appears with explainer
5. **0:12–0:15** — Tap "In Mail öffnen", Mail.app opens with body filled
6. End frame: easli logo + "Paperwork. Made Simple." + "easli.app"

### Capture
On the iOS Simulator with iPhone 15 Pro Max booted:
```bash
xcrun simctl io booted recordVideo --codec h264 ~/easli-preview-de.mov
# (do the storyboard interaction)
# Cmd-C in terminal to stop recording
```

The output is `.mov`, ProRes, ~50MB for 15s — App Store accepts up to 500MB and re-encodes.

### Edit
- **iMovie** (free, macOS) — trim, add a 1-sec intro/outro with logo, bake captions if needed.
- **CapCut** (free, macOS) — better text animations, faster export.
- Export at **1080×1920 (portrait)**, H.264, 30fps. Apple accepts 4K but 1080p is faster to upload.

### Key rules
- **No** music with copyright (Apple rejects). Use built-in licensed beds in iMovie or silence.
- Captions in the video are OK and helpful — but text on screen MUST match the App Store locale.
- Don't show prices, payment dialogs, or anything misleading.

---

## 6. Asset deliverable folder structure

By the end of this you should have:
```
~/easli-store-assets/
├── ios/
│   ├── 6.9-de/ 8 PNGs  1290×2796
│   ├── 6.9-en/ 8 PNGs  1290×2796
│   ├── 5.5-en/ 8 PNGs  1242×2208
│   └── preview-de.mp4  15s 1080×1920
│   └── preview-en.mp4  15s 1080×1920
└── google-play/
    ├── phone-de/ 4 PNGs  ≥1080×1920
    ├── phone-en/ 4 PNGs  ≥1080×1920
    └── feature-graphic.png 1024×500
```

For locales beyond DE+EN (ES, VI, TR, RU, ZH), Apple shows the EN screenshots automatically as fallback. **You can skip them for the initial submission and add later** without resubmitting the binary — assets are uploaded via App Store Connect web UI any time.

---

## 7. Upload sequence (order matters)

### App Store Connect
1. **Create the version** (e.g. 1.0.0) → "Prepare for Submission".
2. Pick the build from EAS in the "Build" section.
3. **Localizations** → for each (DE, EN, ES, VI, TR, RU, ZH):
   - Paste Name, Subtitle, Description, Keywords, Promotional Text from `STORE_LISTING.md`.
   - Drag the 8 screenshots for the matching device size. Apple accepts drag-drop multi-file.
4. Upload Preview videos in the same screenshot block (DE + EN only initially).
5. **App Privacy** → fill in: "Identifiers" → "Device ID" → "Used for App Functionality", **NOT** linked to user, NOT for tracking.
6. **Pricing & Availability** → Free with In-App Purchases (RevenueCat already wired).
7. **Age Rating** → questionnaire → unrestricted, 4+.
8. **Submit for Review**.

### Google Play Console
1. **Production track** → Create new release.
2. Upload the `.aab` from EAS.
3. **Store listing** → for each locale: paste Short + Full description.
4. **Graphic Assets** → upload feature graphic, phone screenshots, app icon.
5. **Data safety** → "Personal info: None collected" → IDs: "Device or other IDs - Used for app functionality, NOT shared, NOT linked to user".
6. **App content** → privacy policy URL, ads = none, target audience 13+.
7. **Submit for review** — note Google Play requires a **14-day Closed Testing track** before you can publish to Production. Do this in parallel.

---

## 8. After submission — what to expect

### Apple
- **First review**: 24–48h typical. Sometimes 1h, sometimes 5 days.
- **Rejection reasons** to pre-empt:
  - **App Privacy Details mismatch** — make sure what you declare matches what the app actually does. easli's anonymous device ID + Mistral mention covers this.
  - **Subscription terms unclear in description** — easli Plus billing terms in the description text, plus a privacy URL link.
  - **Missing iCloud / sign-in option** — N/A for easli, no account required.
- **Phased Release** — turn on so 1% of users get the update first, ramp over 7 days. Disable to ship to 100% immediately.

### Google
- **Closed Testing 14 days mandatory** before production. Use this period to:
  - Get 12+ testers to install the APK.
  - Fix any crashes Crashlytics surfaces.
  - Tweak description based on tester feedback.
- **First Production review**: 1–7 days, sometimes longer for new apps.

---

## 9. Quick win — minimum viable submission

If you want to ship NOW with the least effort:

1. **DE + EN screenshots only** (8 each, raw simulator captures, no overlay).
2. **No App Preview videos** (skip).
3. **5.5" set** = same as 6.9" set scaled in Photoshop (Apple accepts this).
4. **All other locales** = inherit EN automatically.

Time required: ~90 minutes including upload.

This passes Apple review and gets you live. You can always come back, replace screenshots with overlay-decorated versions, add localised previews and videos — all without resubmitting the binary.

---

## 10. Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| "Image dimensions don't match" | iPhone 15 Pro Max simulator gives 1320×2868, App Store wants 1290×2796 | Use **iPhone 14 Pro Max** simulator instead, or scale down in Preview.app |
| "Status bar shows my real time" | Forgot to use simulator | Apple isn't strict; if it bothers you, use Apple's `simctl status_bar` command |
| "Apple Privacy questionnaire complains" | Anonymous device ID confusion | Declare it as "Device ID" → "App Functionality" only. NOT tracking, NOT linked. |
| "Screenshot has rounded corners doubled" | Screenshot tool added a frame on top of iOS 15+ system frame | Use raw `xcrun simctl io booted screenshot` — no frame |
| "Mailto preview shows old TO field" | Cached app | Quit + relaunch + re-screenshot |

---

**Generated for easli v1.0.0 full release. Last updated: May 2026.**
