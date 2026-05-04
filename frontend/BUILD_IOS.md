# 📱 easli — iOS Build Guide (eigener Expo-Account)

Dieser Guide beschreibt, wie du iOS Builds **direkt über deinen eigenen Expo-Account** machst,
ohne den Emergent-Cloud-Build-Wrapper (der ein 12-Min-Timeout hatte).

---

## 🎯 Warum dieser Workflow?

- **Backend** (FastAPI + MongoDB) → bleibt auf **Emergent Deployment**
- **iOS App Build** (IPA für TestFlight / App Store) → läuft **lokal via `eas build`** in deinem Expo-Account
- **Vorteil:** kein Wrapper-Timeout mehr; selbst wenn die EAS-Queue 30 Min dauert, geht der Build durch

---

## 💡 Wichtig: Funktioniert auch von Windows!

Der eigentliche iOS-Build läuft in der **EAS Cloud** auf Apple-Servern.
Du brauchst **keinen Mac** — Windows + Node.js reichen vollständig aus.
Apple-spezifische Schritte (Provisioning, Signing) übernimmt EAS automatisch.

---

## ✅ Voraussetzungen (einmalig einrichten)

### 1. Tools installieren

#### 🍏 macOS / Linux

```bash
# Node.js (≥ 18)
node --version

# EAS CLI installieren
npm install -g eas-cli

# Expo CLI (optional, aber praktisch)
npm install -g expo
```

#### 🪟 Windows (PowerShell)

```powershell
# 1. Node.js installieren von https://nodejs.org/ (LTS-Version)
node --version

# 2. EAS CLI installieren
npm install -g eas-cli

# 3. Expo CLI (optional)
npm install -g expo

# 4. PowerShell erlauben, lokale Scripts auszuführen (NUR EINMAL):
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

> 💡 **Tipp für Windows-User:** Statt der normalen `cmd`-Konsole nimm **PowerShell** oder
> **Windows Terminal** (gibt's gratis im Microsoft Store). Damit funktionieren die Befehle wie
> auf Mac/Linux, und das `build-ios.ps1` Script läuft sauber.

### 2. Repo lokal auschecken

Wenn du noch keine lokale Kopie hast: über GitHub klonen oder das Projekt aus Emergent exportieren
und in einen Ordner legen.

```bash
cd /pfad/zu/deinem/easli-projekt/frontend
yarn install         # oder: npm install
```

### 3. Mit deinem Expo-Account einloggen

```bash
eas login
# → Email/Passwort von deinem Expo.dev Account eingeben
```

### 4. Projekt mit deinem Account verknüpfen (NUR EINMAL)

```bash
cd frontend
eas init
```

Was passiert:
- EAS fragt: „Create a new project for @dein-username/easli?" → **Ja**
- Es wird automatisch ein Eintrag in `app.json` hinzugefügt:

```json
"extra": {
  "eas": {
    "projectId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

**WICHTIG:** Diese Änderung an `app.json` musst du committen und ins Emergent-Projekt zurückbringen
(z.B. via `git pull` im Emergent Dashboard oder die Datei manuell kopieren), damit Emergent denselben
Projekt-Identifier kennt.

### 5. Apple Developer Account verknüpfen

Beim ersten Build wirst du gefragt:
- Apple ID + App-spezifisches Passwort eingeben (oder via 2FA)
- EAS legt automatisch Provisioning Profile + Distribution Certificate an
- **Bundle Identifier:** `com.easli.app` muss in deinem Apple Developer Account verfügbar sein

---

## 🚀 Build & Submit Workflow

### Option A: Per Script (empfohlen)

#### 🍏 macOS / Linux

```bash
cd frontend
./scripts/build-ios.sh production
```

#### 🪟 Windows (PowerShell)

```powershell
cd frontend
.\scripts\build-ios.ps1 production
```

Das Script:
- Prüft, ob du eingeloggt bist
- Triggert `eas build --platform ios --profile production`
- Zeigt dir den Build-Link auf expo.dev
- Bietet dir an, direkt zu TestFlight zu submitten

### Option B: Manuell (Schritt für Schritt)

```bash
cd frontend

# 1. Production Build starten
eas build --platform ios --profile production

# → Wartezeit: 15–25 Min (Free Tier) oder 5–10 Min (Paid)
# → Du bekommst eine URL wie https://expo.dev/accounts/.../builds/xxx

# 2. Wenn der Build fertig ist: zu TestFlight submitten
eas submit --platform ios --latest

# → Wartezeit: 5–15 Min bis zur TestFlight Verarbeitung durch Apple
```

### Option C: Preview Build (für interne Tests, ohne TestFlight)

```bash
eas build --platform ios --profile preview
# → Erzeugt ein Ad-hoc IPA, das du via QR-Code/Link auf registrierte Devices laden kannst
```

---

## 🔄 Nach jedem Code-Change

```bash
# 1. Code änderungen lokal pullen / pushen
git pull   # falls du im Emergent geändert hast
# oder
git push   # falls du lokal geändert hast → ins Emergent Repo

# 2. Build starten
./scripts/build-ios.sh production

# 3. Submitten
eas submit --platform ios --latest
```

`autoIncrement: true` in `eas.json` zählt die `buildNumber` automatisch hoch — du brauchst nichts manuell zu pflegen.

---

## ⚠️ Häufige Probleme & Lösungen

### „Project not found" / „Invalid projectId"
→ `app.json` enthält eine `projectId`, die zu einem anderen Account gehört.
**Fix:** Lösche das `extra.eas` Objekt aus `app.json` und führe `eas init` neu aus.

### „Bundle Identifier already in use"
→ `com.easli.app` ist bereits in einem anderen Apple Developer Account registriert.
**Fix:** Entweder den anderen Account aufräumen, ODER in `app.json` eine andere Bundle ID setzen
(z.B. `com.easli.ios`) und in App Store Connect neu registrieren.

### Build läuft 30+ Min in der Queue
→ Free-Tier-Queue ist voll.
**Fix:** EAS Paid Plan ($19/mo) für Priority Queue, ODER zu einer anderen Tageszeit erneut versuchen.

### „Credentials not found"
→ Apple Developer Account nicht verknüpft.
**Fix:** `eas credentials` ausführen und durch das interaktive Menü navigieren.

---

## 📊 Build-Profile Übersicht (`eas.json`)

| Profil | iOS Resource | Use Case |
|---|---|---|
| `development` | `m-medium` | Lokales Debugging mit Dev-Client |
| `preview` | `m-medium` | Ad-hoc IPA für Tester |
| `production` | `m-large` | TestFlight + App Store (schneller Build dank `m-large`) |

---

## 🔐 Geheimnisse / Environment Variables

EAS injiziert keine `EXPO_PUBLIC_*` Variablen aus `.env`-Dateien automatisch in den Native Build —
sie müssen in `app.json` (`extra`) oder als EAS Secrets liegen.

Aktuell verwendet die App nur `EXPO_PUBLIC_BACKEND_URL`, das via Metro-Bundler in den JS-Code
eingebacken wird. Stelle sicher, dass die `.env` Datei im `frontend/` Ordner korrekt ist,
bevor du `eas build` ausführst.

```bash
# Wert prüfen
cat frontend/.env
# sollte zeigen: EXPO_PUBLIC_BACKEND_URL=https://...
```

---

## 🆘 Notfall-Hilfe

- Expo Forum: https://forums.expo.dev
- EAS Status: https://status.expo.dev
- Emergent Support: support@emergent.sh

---

_Stand: April 2026 | easli MVP | Expo SDK 54_
