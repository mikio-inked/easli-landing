# easli — Paywall Setup Walkthrough (RevenueCat + Apple + Google)

**Ziel:** Kostenpflichtige IAP in iOS + Android scharf schalten.

**Geschätzter Zeitaufwand:** 75-90 Min verteilt auf:
- 5 Min: RevenueCat-Konto
- 30 Min: Apple App Store Connect (IAP-Produkte)
- 30 Min: Google Play Console (IAP-Produkte)
- 15 Min: RevenueCat Dashboard (Produkte verknüpfen + Keys holen)
- 5 Min: Schlüssel an mich zurückschicken, ich wire es zusammen

---

## Die 3 Produkte (für alle Plattformen)

| Product ID | Typ | Preis | RC-Entitlement |
|---|---|---|---|
| `easli_single_letter` | Einmalig (non-consumable)* | 1,49 € | `plus` |
| `easli_plus_monthly` | Monats-Abo | 4,99 € | `plus` |
| `easli_plus_yearly` | Jahres-Abo | 39,99 € | `plus` |

\* **Hinweis zum Single-Letter:** Apple behandelt "Einmal-Kauf für einen Brief" als **Consumable** (verbrauchbar), NICHT als Non-Consumable. RevenueCat unterstützt Consumables, aber sie werden anders getrackt. Lesen wir gleich unten.

---

## Schritt 1 — RevenueCat Account (5 Min)

1. Gehe zu **https://app.revenuecat.com/signup**
2. Registriere dich mit deiner Support-Email-Adresse
3. Bestätige Email-Link
4. Nach Login: **"New Project"** → Name: `easli` → weiter
5. Beim Platform-Setup wähle beide: **iOS + Android**
6. Bundle-ID eintragen: `com.easli.app` (beide Plattformen)
7. RC generiert jetzt **2 API-Keys** (iOS + Android Public Key) — siehe Schritt 4

---

## Schritt 2 — Apple App Store Connect IAP anlegen (30 Min)

**Login:** https://appstoreconnect.apple.com → App "easli" → Tab **"Monetarisierung"** → **"Abonnements" + "In-App-Käufe"**

### 2a) Abo-Gruppe anlegen (für monatlich + jährlich)

1. **"Abonnements"** → **"+"** neben "Abonnement-Gruppen"
2. Referenzname: `easli Plus` (intern, nicht sichtbar)
3. Anzeigename: `easli Plus` — **für alle 11 Sprachen** einzeln eintragen:
   - DE: `easli Plus`
   - EN: `easli Plus`
   - FR-IT-ES-PL-AR-TR-RU-VI-ZH: alle `easli Plus` (Markenname bleibt)
4. Speichern

### 2b) Monats-Abo anlegen (innerhalb der Gruppe)

1. **"Abonnement erstellen"** innerhalb `easli Plus`
2. Referenzname: `easli Plus Monthly`
3. **Produkt-ID: `easli_plus_monthly`** ⚠️ EXAKT SO SCHREIBEN (kein Tippfehler!)
4. Abrechnungs-Zeitraum: **1 Monat**
5. Preis: wähle die Preisstufe **DE € 4,99 / Monat** (Tier 5)
6. **Lokalisierung** für alle 11 Sprachen:
   - Anzeigename: `easli Plus` (alle Sprachen)
   - Beschreibung (jeweils eine Zeile, z.B.):
     - DE: `Unbegrenzt Briefe analysieren + alle Pro-Funktionen`
     - EN: `Unlimited letter analyses + all pro features`
     - FR: `Analyses illimitées de courrier + toutes fonctions pro`
     - IT: `Analisi illimitate + tutte le funzioni pro`
     - ES: `Análisis ilimitados + todas las funciones pro`
     - PL: `Nieograniczone analizy + wszystkie funkcje pro`
     - AR: `تحليلات غير محدودة + جميع ميزات برو`
     - TR: `Sınırsız analiz + tüm pro özellikler`
     - RU: `Безлимит анализов + все функции pro`
     - VI: `Phân tích không giới hạn + mọi tính năng pro`
     - ZH: `无限分析 + 所有专业功能`
7. **Review-Informationen**:
   - Screenshot des Paywall-Screens hochladen (aus TestFlight aufgenommen)
   - Review-Notizen: `Paywall test with sandbox account. No real payment required for review.`
8. Speichern → **Status "Bereit zur Einreichung"** sollte erscheinen

### 2c) Jahres-Abo (gleiche Gruppe)

1. Erneut **"Abonnement erstellen"** in `easli Plus`
2. Referenzname: `easli Plus Yearly`
3. **Produkt-ID: `easli_plus_yearly`**
4. Abrechnungs-Zeitraum: **1 Jahr**
5. Preis: Preisstufe **DE € 39,99 / Jahr** (Tier 40)
6. Lokalisierungen wie bei 2b, ansonsten identisch
7. Speichern

### 2d) Einzel-Brief (Consumable IAP — andere Liste!)

1. Zurück zum Haupt-Monetarisierungs-Tab → **"In-App-Käufe" (NICHT Abonnements!)**
2. **"+"** → Typ: **"Verbrauchsmaterial"** (Consumable)
3. Referenzname: `easli Single Letter`
4. **Produkt-ID: `easli_single_letter`**
5. Preis: Tier 2 (**€ 1,49**)
6. Lokalisierung (alle 11 Sprachen):
   - Anzeigename: DE `Einzelner Brief`, EN `Single Letter`, FR `Une lettre`, IT `Una lettera`, ES `Una carta`, PL `Jeden list`, AR `رسالة واحدة`, TR `Tek mektup`, RU `Одно письмо`, VI `Một lá thư`, ZH `单封信件`
   - Beschreibung: DE `Analyse eines einzelnen Briefes ohne Abo` — analog in anderen Sprachen
7. Screenshot + Review-Notizen wie oben
8. Speichern

### 2e) App-Kapazität aktivieren

Automatisch aktiv wenn du IAP anlegst. Prüfe in **Xcode** (falls du das Projekt lokal öffnest): Signing & Capabilities → In-App Purchase muss mit grünem Haken erscheinen. Bei EAS-Builds ist das automatisch drin.

### 2f) Sandbox-Tester anlegen

1. App Store Connect → **"Benutzer und Zugang"** → **"Sandbox-Tester"**
2. **"+"** → beliebige Fake-Email (z.B. `easli-test+1@icloud.com` — muss NICHT real existieren)
3. Passwort + Geburtsdatum
4. Speichern — diesen Account benutzt du später auf dem iPhone zum Testen ohne echte Belastung

---

## Schritt 3 — Google Play Console IAP anlegen (30 Min)

**Login:** https://play.google.com/console → easli → **Monetarisieren** → **Produkte**

### 3a) Einzel-Brief (Managed Product)

1. **"In-App-Produkte"** → **"Produkt erstellen"**
2. **Produkt-ID: `easli_single_letter`**
3. Name: `Einzelner Brief` (DE default) — Übersetzungen via "Übersetzungen hinzufügen" für die anderen 10 Sprachen
4. Preis: € 1,49 (manuell pro Land oder "Alle Länder EUR 1,49")
5. Status: **"Aktiv"** → Speichern

### 3b) Abo-Basis `easli Plus`

1. **"Abonnements"** → **"Abonnement erstellen"**
2. **Produkt-ID: `easli_plus`** (Basis-Gruppe)
3. Name: `easli Plus`
4. **"Basis-Abos hinzufügen"**:
   - **Monthly**:
     - Basis-Plan-ID: `easli_plus_monthly` (ID = vollständiger Produkt-Identifier bei RC-Mapping!)
     - Abrechnung: monatlich, automatisch erneuerbar
     - Preis: € 4,99/Monat
   - **Yearly**:
     - Basis-Plan-ID: `easli_plus_yearly`
     - Abrechnung: jährlich
     - Preis: € 39,99/Jahr
5. Alle Pläne aktivieren + speichern

> ⚠️ **Unterschied zu Apple:** Google benutzt ein Abo-Objekt mit mehreren Basis-Plänen. Das Mapping zu RC ist `<subscription_id>:<base_plan_id>`.

### 3c) License-Testing-Account

1. Play Console → **Einstellungen** → **License-Testing**
2. Deine Test-Gmail-Adresse eintragen (z.B. deine eigene, die auf dem Android-Testgerät angemeldet ist)
3. Speichern — die kann jetzt Sandbox-Käufe machen ohne Belastung

---

## Schritt 4 — RevenueCat Dashboard verknüpfen (15 Min)

Zurück in **https://app.revenuecat.com** → Projekt `easli`.

### 4a) App-Credentials setzen

**Project Settings → Apps**

- **iOS:** App Store Connect Shared Secret eintragen
  - Hol's dir: App Store Connect → App easli → App-Informationen → "App-Spezifisches gemeinsames Geheimnis"
- **Android:** Google Play Service Account JSON hochladen
  - Hol's dir: Play Console → Einstellungen → API-Zugriff → Service Account mit Rolle "Release Manager" erstellen → JSON herunterladen

### 4b) Products in RC anlegen

**Products → "+ New"**

Drei Einträge:

| RC Product ID | iOS App Store ID | Android Play ID | Type |
|---|---|---|---|
| `easli_single_letter` | `easli_single_letter` | `easli_single_letter` | Non-subscription |
| `easli_plus_monthly` | `easli_plus_monthly` | `easli_plus:easli_plus_monthly` | Subscription (monthly) |
| `easli_plus_yearly` | `easli_plus_yearly` | `easli_plus:easli_plus_yearly` | Subscription (yearly) |

⚠️ Bei Google Android verwende das Format `<product_id>:<base_plan_id>` für Abos.

### 4c) Entitlement anlegen

**Entitlements → "+ New"** → ID: `plus` → Add all 3 products to it

### 4d) Offering anlegen (die eigentliche Paywall-Auswahl)

**Offerings → "+ New"**

- Identifier: `default`
- Packages:
  - Package 1: Identifier `$rc_monthly` → Product `easli_plus_monthly`
  - Package 2: Identifier `$rc_annual` → Product `easli_plus_yearly`
  - Package 3: Identifier `single` → Product `easli_single_letter`
- Als "Current" markieren

### 4e) Webhook konfigurieren

**Project Settings → Integrations → Webhooks → "+ Add"**

- URL: `https://api.easli.app/api/revenuecat/webhook`
- Authorization Header: erfinde dir ein Bearer-Secret (z.B. 64 random chars) — merken!
- Subscription Events: alle aktivieren
- Speichern

---

## Schritt 5 — Keys an mich schicken

Nach Abschluss brauche ich von dir **3 Werte** (copy-paste in den nächsten Chat):

```
RC_IOS_PUBLIC_KEY = appl_....
RC_ANDROID_PUBLIC_KEY = goog_....
RC_WEBHOOK_AUTH_HEADER = Bearer <dein-geheimes-secret>
```

Die ersten 2 findest du in RC: **Project Settings → API Keys → Public SDK Keys** (pro Plattform).

Der 3. ist das Secret das du dir in Schritt 4e ausgedacht hast.

---

## Schritt 6 — Ich setze alles zusammen (nachdem du mir die Keys gibst)

Ich mache:
1. EAS-Secrets anlegen: `eas secret:create EXPO_PUBLIC_REVENUECAT_IOS_PUBLIC_KEY` / `_ANDROID_PUBLIC_KEY`
2. Railway-Env setzen: `REVENUECAT_WEBHOOK_AUTH_HEADER=<secret>` + `PAYWALL_MODE=hard`
3. Neuer iOS-Build via EAS → Sandbox-Test
4. Wenn Sandbox-Kauf durchläuft + Webhook ankommt + `plus_active: true` im Usage steht → Submit for Review

---

## Was passiert NACH dem Submit

- Apple Review: 1-3 Tage
- Apple reviewt App + IAP-Produkte zusammen
- Bei Approve: Du kannst sofort live gehen
- Tipp: Erstmal `PAYWALL_MODE=soft` für den Launch — gibt Nutzern 10 Test-Analysen, dann hard paywall. Sanfter Übergang, bessere Retention.

---

## FAQ / typische Fallstricke

**Q: Kann ich die Produkt-IDs später umbenennen?**
A: Nein, nicht ohne alle bestehenden Käufe zu verlieren. Deswegen `easli_*` von Anfang an richtig setzen.

**Q: Was wenn ich die Preise später ändere?**
A: Apple + Google erlauben Preisänderungen. RC nimmt den Preis aus den Stores. Kein Code-Change nötig.

**Q: Muss ich die Paywall-Screenshots in allen 11 Sprachen für Apple-Review hochladen?**
A: Nein. Ein einziger Screenshot in deiner Hauptsprache (Deutsch) reicht. Apple prüft die Payment-Flow-Logik, nicht die Lokalisierung.

**Q: Wie prüfe ich nach Launch, ob Webhooks ankommen?**
A: Railway-Logs grep nach `rc_webhook event=`. Oder: RC Dashboard → Customers → einzelnen User aufrufen → Events-Tab zeigt alle Webhook-Deliveries mit Status.
