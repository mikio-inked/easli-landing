# easli — Google Play Store Launch Checklist

**Ziel:** App "easli" im Google Play Store veröffentlichen.
**Wichtig:** Google erzwingt seit Nov 2023 eine **14-Tage-Closed-Testing-Phase** mit
mindestens **12 aktiven Testern** BEVOR du in Production gehen kannst. Also sofort
starten, parallel zu TestFlight auf iOS.

---

## Phase 1 — Google Play Console Account (einmalig)

- [ ] **Google Play Developer Account erstellen** (falls noch nicht)
  https://play.google.com/console → "Get started"
  - Einmalige Gebühr: **25 USD**
  - Konto-Typ: **Organization** (nicht Personal, wegen Impressumspflicht EU)
  - Identitätsverifikation dauert 1-3 Tage
- [ ] **Payment Profile** hinzufügen (für bezahlte Apps / In-App-Käufe später)
- [ ] **Declarations ausfüllen**: Policy-Fragen zur App-Kategorie beantworten

---

## Phase 2 — App anlegen im Play Console

- [ ] **Create app** → Name: `easli`, Sprache: Deutsch, App oder Spiel: App,
      Gratis oder kostenpflichtig: **Gratis** (später IAP via RevenueCat)
- [ ] **Declarations**: Developer Program Policies + US Export Laws bestätigen
- [ ] **App-Zugriff** setzen: "All functionality available without restrictions"
      (oder Test-Credentials hinterlegen, falls Login nötig — bei easli nicht nötig)
- [ ] **Anzeigen**: "App contains ads" = **Nein** (easli hat keine Werbung)
- [ ] **Inhaltsfreigabe (Content Rating)** Fragebogen ausfüllen
      - Kategorie: Utility / Productivity
      - Erwartetes Rating: **PEGI 3 / Everyone**
- [ ] **Zielgruppe**: Erwachsene (18+) — Papierkram-App
- [ ] **Nachrichten-App?** Nein
- [ ] **COVID-19 Tracing App?** Nein
- [ ] **Data Safety Form** ausfüllen (wichtig!):
  - [ ] Sammelt App Daten? → **Ja** (anonyme Device-ID, Dokumenttexte während Analyse)
  - [ ] Werden Daten geteilt mit Dritten? → **Ja, mit Mistral AI (EU)** zur KI-Analyse
  - [ ] Daten verschlüsselt übertragen? → **Ja**
  - [ ] Nutzer können Daten löschen? → **Ja** (Settings → "Alle Daten löschen")
  - Kategorien angeben:
    - Device or other IDs → Anonymous Device ID (für Quota-Tracking)
    - Photos → Originale nicht gespeichert, nur zur Analyse übermittelt
    - Files and docs → Gleiche Handhabung
- [ ] **Government App?** Nein
- [ ] **Financial features?** Nein

---

## Phase 3 — Store Listing (Haupt-Listing in Deutsch + 10 Lokalisierungen)

Dateien liegen in `/app/scripts/store_screenshots/out_android/`

**Haupt-Sprache: Deutsch (DE-DE)**
- [ ] **Name der App (max 30):** `easli — Briefe verstehen`
- [ ] **Kurzbeschreibung (max 80):** `Fotografiere Briefe, easli erklärt sie dir in deiner Sprache.`
- [ ] **Vollständige Beschreibung (max 4000):** siehe `play-listing-de.md` (folgt)
- [ ] **App-Symbol** 512×512 → `/app/frontend/assets/images/play-store-icon.png`
- [ ] **Feature-Grafik** 1024×500 → `out_android/android-phone-de/feature-graphic-de.png`
- [ ] **Phone Screenshots (min 2, max 8):** Alle 5 aus `out_android/android-phone-de/`
- [ ] **Kategorie:** Produktivität (Primary), Tools (Secondary)
- [ ] **Tags:** Finanzen, Übersetzer, OCR, KI, Brief, Papierkram
- [ ] **E-Mail-Kontakt** (Pflicht): Deine Support-Email
- [ ] **Website** (optional): easli.app oder Landing-Page
- [ ] **Datenschutzerklärung URL** (Pflicht!): Muss erreichbar sein

**Zusätzliche Lokalisierungen (im Play Console unter "Store listings"):**
- [ ] Englisch (en-US) — Assets: `out_android/android-phone-en/`
- [ ] Französisch (fr-FR) — `out_android/android-phone-fr/`
- [ ] Italienisch (it-IT) — `out_android/android-phone-it/`
- [ ] Spanisch (es-ES) — `out_android/android-phone-es/`
- [ ] Polnisch (pl-PL) — `out_android/android-phone-pl/`
- [ ] Arabisch (ar) — `out_android/android-phone-ar/`
- [ ] Türkisch (tr-TR) — `out_android/android-phone-tr/`
- [ ] Russisch (ru-RU) — `out_android/android-phone-ru/`
- [ ] Vietnamesisch (vi-VN) — `out_android/android-phone-vi/`
- [ ] Chinesisch, vereinfacht (zh-CN) — `out_android/android-phone-zh/`

---

## Phase 4 — Internal Testing (< 1 Tag Setup)

Keine Wartezeit, keine Review. Zum schnellen QA mit dir selbst / Freunden.

- [ ] **Im Play Console → Testing → Internal testing → Create new release**
- [ ] AAB-Build hochladen (aus EAS):
  ```bash
  cd /pfad/zu/easli/frontend
  ./scripts/build-android.sh production   # erzeugt AAB via EAS
  # Dann entweder:
  # a) AAB aus expo.dev manuell downloaden und in Console hochladen
  # b) eas submit --platform android --latest (falls Service Account JSON eingerichtet)
  ```
- [ ] **Release-Notizen** auf Deutsch: "Erste Version. Feedback willkommen!"
- [ ] **Tester-Liste anlegen**: E-Mail-Adressen (min 1, aber bis zu 100)
- [ ] **Opt-in-Link** teilen → Tester müssen den Link klicken und annehmen
- [ ] Rollout → auf "Managed publishing" falls du manuell freigeben willst

**Ergebnis:** Du + Freunde können die App sofort auf Android testen.

---

## Phase 5 — Closed Testing (PFLICHT: 14 Tage + 12 Tester) 🔴

Das ist der kritische Pfad für deinen Play-Store-Launch.

- [ ] **Testing → Closed testing → Create new release**
- [ ] Track-Namen: "Open Beta" oder "Closed Alpha"
- [ ] Tester-Liste (sehr wichtig!): **mindestens 12 E-Mail-Adressen**
  - Tipp: Erstelle eine Google-Gruppe namens `easli-testers@googlegroups.com`
    und füge alle Tester zur Gruppe hinzu — viel einfacher zu verwalten
- [ ] AAB hochladen (gleicher Build wie Internal)
- [ ] Rollout → "Submit for review" (1-7 Tage Google Review beim ersten Mal)
- [ ] **Tester einladen** und bitten, die App zu installieren
- [ ] **Dashboard beobachten**: unter "Testing → Closed testing → Testers" siehst du:
  - "Active testers last 14 days" muss ≥ 12 sein
  - Uhr tickt erst wenn alle Tester opted-in sind + App installiert haben
- [ ] **14 Tage warten** ab dem Zeitpunkt, an dem du 12 aktive Tester erreichst
- [ ] Nach 14 Tagen: "Apply for production access" Button erscheint
- [ ] Produktion-Access beantragen → Google Review ca. 1-3 Tage

---

## Phase 6 — Production Release

- [ ] **Production → Create new release**
- [ ] Gleichen AAB nochmal hochladen (oder neueren Build, falls du Closed-Testing-Bugs gefixt hast)
- [ ] **Country/Region Availability**:
  - EU (alle Länder) + Schweiz + UK + Norwegen
  - Optional: Weltweit — aber easli ist EU-fokussiert, lieber eingrenzen
- [ ] **Rollout percentage**: Start mit **10%** (staged rollout), dann nach 2-3 Tagen auf 100%
- [ ] **Submit for review** → Google Review 2-7 Tage

---

## Parallele Tasks (während der 14-Tage-Wartezeit)

- [ ] **Privacy Policy URL** erstellen (auf easli.app oder GitHub Pages)
  Pflichtinhalte:
  - Welche Daten werden gesammelt (anonyme Device-ID, Dokumenttexte temporär)
  - An welchen Dritten werden Daten geteilt (Mistral AI, Paris)
  - Wie können Nutzer Daten löschen (Settings → Alle Daten löschen)
  - Kontakt für Datenschutzanfragen
- [ ] **Terms of Service URL** erstellen
- [ ] **Play Integrity API** aktivieren (empfohlen, schützt vor App-Piraterie)
- [ ] **Service Account für EAS Submit** einrichten:
  1. Play Console → Setup → API access → Create service account
  2. In der GCP Console das Service Account erstellen
  3. JSON Key herunterladen → in `/app/frontend/secrets/google-play-service-account.json`
  4. Im Play Console dem Service Account die Rolle "Release Manager" geben
  5. Danach: `eas submit --platform android --latest` funktioniert automatisch

---

## Empfohlene Timeline

```
Tag 0 (heute):     Play Console einrichten, Internal Testing Release hochladen
Tag 1:             Closed Testing erstellen, 12+ Tester einladen
Tag 2:             Google Review für Closed Testing abgeschlossen (1-3 Tage)
Tag 3-16:          Bugs fixen, Feedback einarbeiten. Uhr läuft.
Tag 17:            Production-Access beantragen
Tag 18-20:         Google Review für Production
Tag 21:            🚀 LIVE IM PLAY STORE
```

**Wichtig:** Starte Phase 2-4 SOFORT, damit die 14-Tage-Uhr parallel zum
iOS-TestFlight-Release tickt. Sonst verlierst du 2 Wochen.

---

## Build & Submit Befehle (auf deinem Mac)

```bash
cd ~/dein-easli-projekt/frontend

# 1. AAB für Play Store bauen
./scripts/build-android.sh production

# 2a. Manuell: AAB von https://expo.dev runterladen und ins Play Console hochladen
#     (wenn du noch kein Service Account JSON hast)

# 2b. Automatisch: direkt zu Play Console uploaden
eas submit --platform android --latest
# Voraussetzung: ./secrets/google-play-service-account.json existiert
```

---

## Permissions-Übersicht (aus `app.json`)

Diese Permissions fragt die App ab — im Play Console unter "App content → Sensitive permissions":

| Permission | Zweck für Nutzer |
|---|---|
| `CAMERA` | Briefe scannen |
| `READ_EXTERNAL_STORAGE` | Vorhandene Fotos/PDFs aus Galerie öffnen |
| `READ_MEDIA_IMAGES` | Android 13+ fine-grained Foto-Zugriff |
| `POST_NOTIFICATIONS` | Fristen-Erinnerungen |

Keine davon ist "sensitive" nach Google-Definition. Keine extra Deklaration nötig.
