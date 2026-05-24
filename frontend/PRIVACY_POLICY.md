# Datenschutzerklärung — easli

> **Stand:** 24. Mai 2026  
> **Version:** 1.0  
> **Gültig für:** easli iOS, easli Android (Bundle `com.easli.app`)  
> **Sprache:** Deutsch (verbindliche Fassung). Eine englische Übersetzung
> wird auf Anfrage bereitgestellt.

Diese Datenschutzerklärung beschreibt, **welche Daten easli verarbeitet, zu
welchem Zweck, wie lange wir sie speichern und welche Rechte du hast.** Sie
erfüllt die Informationspflichten nach Art. 13 DSGVO und richtet sich an
alle Nutzerinnen und Nutzer der easli­-App.

easli ist bewusst **konto-frei**, **werbe-frei** und **tracking-frei**
gebaut. Du brauchst weder E-Mail-Adresse noch Name, um die App zu nutzen.

---

## Inhalt

1. [Verantwortliche Stelle](#1-verantwortliche-stelle)
2. [Welche Daten wir verarbeiten](#2-welche-daten-wir-verarbeiten)
3. [Zweck und Rechtsgrundlage](#3-zweck-und-rechtsgrundlage)
4. [Speicherdauer](#4-speicherdauer)
5. [Auftragsverarbeiter — wer sieht deine Daten?](#5-auftragsverarbeiter--wer-sieht-deine-daten)
6. [Keine KI-Trainings­daten](#6-keine-ki-trainingsdaten)
7. [Internationale Datenüber­mittlung](#7-internationale-datenubermittlung)
8. [Deine Rechte](#8-deine-rechte)
9. [Wie du deine Rechte ausübst](#9-wie-du-deine-rechte-ausubst)
10. [Cookies und Tracking](#10-cookies-und-tracking)
11. [Datensicherheit](#11-datensicherheit)
12. [Beschwerde bei einer Aufsichts­behörde](#12-beschwerde-bei-einer-aufsichtsbehorde)
13. [Änderungen dieser Datenschutz­erklärung](#13-anderungen-dieser-datenschutzerklarung)
14. [Kontakt](#14-kontakt)

---

## 1. Verantwortliche Stelle

Verantwortlich im Sinne von Art. 4 Nr. 7 DSGVO ist:

```
<<Vor- und Nachname / Firma>>
<<Straße und Hausnummer>>
<<PLZ Ort>>
<<Land>>

E-Mail: privacy@easli.app
Web:    https://easli.app
```

Für Datenschutz-Fragen erreichst du uns unter **privacy@easli.app**.
Wir antworten innerhalb von 30 Tagen, in der Regel deutlich schneller.

> *Hinweis:* Sobald die rechtliche Anschrift final ist, ersetzen wir die
> oben stehenden Platzhalter. Die App selbst sammelt keine derartigen
> Daten von dir.

---

## 2. Welche Daten wir verarbeiten

### 2.1 Was passiert mit deinen fotografierten Briefen?

Wenn du ein Dokument scannst oder ein PDF hochlädst, durchläuft es folgenden
Weg:

1. **Foto/PDF** wird einmalig per HTTPS (TLS 1.2+) an unseren Server in der
   EU übermittelt.
2. Unser Server reicht das Bild an **Mistral AI (Paris, Frankreich)** zur
   OCR-Extraktion weiter — eine reine Texterkennung.
3. Der OCR-Text wird zur Analyse erneut an Mistral AI gesendet.
4. **Das Originalbild wird NICHT gespeichert.** Es existiert nur im
   Arbeitsspeicher unseres Servers während der Verarbeitung (typisch
   20–30 Sekunden) und wird danach gelöscht.
5. Persistent gespeichert wird ausschließlich der **OCR-Text** und das
   **strukturierte Analyse-Ergebnis** (Zusammenfassung, Fristen, Antwort­
   entwurf etc.).

### 2.2 Übersicht aller verarbeiteten Datenkategorien

| Kategorie | Inhalt | Quelle | Persistiert? |
|---|---|---|---|
| **Dokumentbild** | Foto/PDF deines Briefes | Du → App | ❌ Nein |
| **OCR-Text** | Extrahierter Text aus dem Dokument | OCR-Engine | ✅ 90 Tage |
| **Analyse-Ergebnis** | Zusammenfassung, Fristen, Antwort­entwurf, Kategorie, Risiko-Stufe | Mistral AI | ✅ 90 Tage |
| **Chat-Nachrichten** | Deine Fragen zu einer Analyse + KI-Antworten | Du → App | ✅ 90 Tage |
| **Anonyme Geräte-ID** | Zufällige UUIDv4, ausschließlich lokal im iOS-Keychain bzw. Android-Keystore gespeichert; auf unseren Servern nur zur Verknüpfung mit deinen Analysen | App | ✅ 90 Tage |
| **Nutzungs-Zähler** | Anzahl analysierter Dokumente pro Monat (für die Gratis-Quota) | App | ✅ unbegrenzt; Wert wird monatlich zurück­gesetzt |
| **Abonnement-Status** | Aktive Plus-Mitgliedschaft (ja/nein, Gültigkeits­datum) via RevenueCat | RevenueCat → Server | ✅ bis 30 Tage nach Ablauf |
| **User-Reports** | Dein Bericht, wenn du eine Analyse über den Report-Button meldest (Grund + optionaler Kommentar bis 500 Zeichen) | Du → App | ✅ 90 Tage |
| **Crash-Logs** | Stack-Traces bei Abstürzen, mit content-scrubbing | App → Sentry | ✅ 90 Tage (Sentry) |
| **Server-Logs** | Metadaten-Logs (HTTP-Methode, Pfad, Status, Dauer, IP) | Server | ✅ 14 Tage |

### 2.3 Was wir **nicht** verarbeiten

- **Keine E-Mail-Adresse.** Es gibt keinen Account.
- **Keine Telefonnummer.**
- **Keine Werbe-ID** (IDFA, Google Advertising ID).
- **Keine Geo­daten.**
- **Keine Kontakte, keine bestehenden Kalender­einträge, keine Fotos** außerhalb derjenigen, die du aktiv in die App importierst.
- **Keine Browserverlauf-Daten, kein Tracking über Apps hinweg.**

---

## 3. Zweck und Rechtsgrundlage

| Verarbeitung | Zweck | Rechtsgrundlage |
|---|---|---|
| Dokumentanalyse (OCR + KI) | Erbringung der Kernleistung, die du in der App anforderst | Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung) |
| Speicherung der Analyse-Ergebnisse | Damit du später erneut auf deine Briefe zugreifen kannst | Art. 6 Abs. 1 lit. b DSGVO |
| Chat zur Analyse | Beantwortung deiner Rück­fragen zum Dokument | Art. 6 Abs. 1 lit. b DSGVO |
| Anonyme Geräte-ID | Eindeutige, account-freie Zuordnung deiner Analysen zum Gerät | Art. 6 Abs. 1 lit. b DSGVO |
| Abrechnung der kosten­pflichtigen Plus-Funktion | Vertragsabwicklung mit Apple/Google + RevenueCat | Art. 6 Abs. 1 lit. b DSGVO |
| Crash-Logs (Sentry) | Stabilität der App, Fehler­diagnose | Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse) |
| Server-Metadaten-Logs | IT-Sicherheit, Missbrauchs­erkennung, Rate-Limit-Schutz | Art. 6 Abs. 1 lit. f DSGVO |
| User-Reports | Verbesserung der App, Sicherheits­meldungen prüfen | Art. 6 Abs. 1 lit. f DSGVO |

---

## 4. Speicherdauer

Wir speichern Daten **so kurz wie möglich** und löschen automatisch nach
festen Fristen (Art. 5 Abs. 1 lit. e DSGVO):

| Datenkategorie | Speicherdauer | Mechanismus |
|---|---|---|
| Dokumentbilder | **0 Sekunden persistent** (nur im RAM während der Verarbeitung) | direkter Löschvorgang nach Antwort |
| OCR-Text + Analyse-Ergebnis | **90 Tage** ab Erstellung | MongoDB TTL-Index `analyses.created_at` |
| Chat-Nachrichten zur Analyse | **90 Tage** (an die Eltern-Analyse gebunden) | MongoDB TTL-Index |
| User-Reports | **90 Tage** ab Einsendung | MongoDB TTL-Index `reports.created_at` |
| Anonyme Geräte-ID auf dem Server | gleicher Lebenszyklus wie die zugehörigen Analysen | mit Analyse mitgelöscht |
| Anonyme Geräte-ID auf deinem Gerät | bis du die App deinstallierst | iOS Keychain / Android Keystore |
| Abonnement-Status | bis **30 Tage nach Ablauf** des Abonnements | RevenueCat + Server |
| Crash-Logs (Sentry) | **90 Tage** | Sentry-Retention |
| Server-Metadaten-Logs | **14 Tage** | Hosting-Provider Standard |

Du kannst alle deine Daten **jederzeit selbst löschen** — siehe Abschnitt 9.

---

## 5. Auftragsverarbeiter — wer sieht deine Daten?

Wir setzen ausschließlich Auftragsverarbeiter ein, die unter einer
schriftlichen Vereinbarung nach Art. 28 DSGVO arbeiten.

| Dienst | Anbieter | Sitz / Server­standort | Verarbeitete Daten | Vertrags­grundlage |
|---|---|---|---|---|
| **OCR + KI-Analyse + Chat + Antwort-Generierung** | Mistral AI | Paris, Frankreich — ausschließlich EU-Server | Dokument-Bild (flüchtig) + OCR-Text + Analyse + Chat-Verlauf | Art. 28 DSGVO, EU-DPA |
| **Datenbank** | MongoDB Atlas (MongoDB Inc.) | Frankfurt am Main (eu-central-1) | OCR-Texte, Analyse-Ergebnisse, Chat, Reports, anonyme Geräte-ID | Art. 28 DSGVO, SCC + EU-DPA |
| **Crash-Reporting** | Sentry GmbH (Functional Software) | EU-Region (Frankfurt) | Stack-Traces, Geräte-Modell, OS-Version — content-scrubbed | Art. 28 DSGVO |
| **CDN / DNS / DDoS-Schutz** | Cloudflare Inc. | Globale Edge-Knoten mit EU-Priorisierung | IP-Adresse, HTTP-Header (flüchtig) | Art. 28 DSGVO, SCC |
| **Abonnement-Verwaltung** | RevenueCat Inc. | USA | Anonyme Geräte-ID + Apple/Google Kauf-Token + Entitlement-Status (**keine** Inhalte) | Art. 28 DSGVO, SCC + Daten­mini­mie­rung |
| **Zahlungs­abwicklung** | Apple Inc. / Google LLC | USA | Reiner Kauf-Token — wir sehen weder Karten- noch Konto­daten | Art. 6 Abs. 1 lit. b DSGVO |
| **Hosting / Tunnel** | <<dein Hosting-Anbieter, z. B. Railway EU>> | Frankfurt | s. MongoDB | Art. 28 DSGVO |

Eine aktuelle Liste der Sub-Auftrags­verarbeiter inkl. der jeweiligen DPAs
stellen wir auf Anfrage bereit (**privacy@easli.app**).

---

## 6. Keine KI-Trainings­daten

**Deine Dokumente und Chat-Nachrichten werden NICHT verwendet, um
KI-Modelle zu trainieren.** Mistral AI bietet hierfür eine vertraglich
zugesicherte Opt-Out-Garantie für ihre kommerzielle API, die wir nutzen.
Konkret bedeutet das:

- Prompts (deine Dokumente + Fragen) werden **nicht** ins Trainings-Korpus
  von Mistral aufgenommen.
- Mistral bewahrt Prompts maximal **30 Tage** zur Missbrauchs­erkennung auf
  und löscht sie danach automatisch.
- easli selbst nutzt deine Daten **niemals** für eigenes Training, eigene
  Statistiken oder Marketing-Zwecke.

Die Anti-Training-Klausel ist Teil unseres Auftragsverarbeitungs-Vertrags
mit Mistral AI und ein Kernbaustein unseres Datenschutz-Versprechens.

---

## 7. Internationale Datenüber­mittlung

Die Kern-Verarbeitung deiner Daten erfolgt **ausschließlich in der
Europäischen Union** (Server in Paris und Frankfurt). Nur drei
Umstände können einen kurzen Daten-Transit außerhalb der EU bedeuten:

1. **RevenueCat (USA)** — erhält ausschließlich deinen Apple/Google Kauf-
   Token + die anonyme Geräte-ID. Inhalte deiner Briefe werden niemals
   an RevenueCat übermittelt. Grundlage: Standard-Vertrags­klauseln (SCC)
   nach Beschluss (EU) 2021/914.
2. **Cloudflare** — Edge-Knoten weltweit zur DDoS-Abwehr; die Daten werden
   nur flüchtig durchgeleitet (Header + Payload, keine Speicherung). EU-
   Knoten haben Vorrang. Grundlage: SCC.
3. **Apple / Google Payment-Server** — Zahlungs­abwicklung unter dem
   jeweiligen App-Store-Vertrag, den du beim Kauf eingehst.

Deine fotografierten Briefe selbst verlassen **die EU nicht**.

---

## 8. Deine Rechte

Nach der DSGVO hast du folgende Rechte gegenüber uns:

| Recht | Artikel | Was du tun kannst |
|---|---|---|
| **Auskunft** | Art. 15 DSGVO | Eine Kopie aller deiner Daten anfordern (siehe §9.1) |
| **Berichtigung** | Art. 16 DSGVO | Falsche Analysen melden und neu scannen |
| **Löschung** | Art. 17 DSGVO | Alle deine Daten innerhalb von Sekunden löschen (§9.2) |
| **Einschränkung** | Art. 18 DSGVO | Verarbeitung vorübergehend stoppen lassen — schreib uns |
| **Datenüber­tragbarkeit** | Art. 20 DSGVO | Deine Daten in maschinen­lesbarem JSON-Format exportieren (§9.1) |
| **Widerspruch** | Art. 21 DSGVO | Verarbeitung auf Basis berechtigten Interesses widersprechen — schreib uns |
| **Beschwerde** | Art. 77 DSGVO | Aufsichts­behörde einschalten (siehe §12) |

Alle Rechte sind **kostenlos und ohne Begründung** wahrnehmbar.

---

## 9. Wie du deine Rechte ausübst

### 9.1 Daten exportieren (Art. 15 + Art. 20 DSGVO)

Direkt in der App:
```
Einstellungen → Meine Daten exportieren
```
Die App ruft dann `GET /api/export?device_id=...` auf unserem Server auf
und stellt dir eine **JSON-Datei** mit allen deinen Analysen, Chats und
Reports zur Verfügung — zum Teilen, Speichern, Drucken.

### 9.2 Alle Daten löschen (Art. 17 DSGVO)

Direkt in der App:
```
Einstellungen → Alle meine Daten löschen → Bestätigen
```
Innerhalb von ca. **1 Sekunde** entfernen wir:

- jede gespeicherte Analyse,
- jede Chat-Nachricht,
- jeden User-Report,
- den Nutzungs-Zähler.

Technisch passiert: `DELETE /api/history/{device_id}`. Der Vorgang ist
endgültig — wir bewahren keine Sicherungs­kopien deiner Daten auf.

Möchtest du auch die lokal auf deinem Gerät gespeicherte anonyme
Geräte-ID entfernen? Deinstalliere einfach die App — iOS und Android
löschen automatisch alle Keychain- bzw. Keystore-Einträge.

### 9.3 Auskunft und alle anderen Anliegen per E-Mail

Für jede Anfrage nach Art. 15–21 DSGVO, die nicht per In-App-Knopf
abgedeckt ist, schreib uns formlos an:

```
privacy@easli.app
```

Gib idealerweise deine anonyme Geräte-ID an — du findest sie in der
App unter **Einstellungen → Über easli**. Ohne diese ID können wir deine
Daten nicht identifizieren, da wir keine sonstigen Identifikatoren
führen.

Antwortfrist: **30 Tage** nach Eingang (Art. 12 Abs. 3 DSGVO).

---

## 10. Cookies und Tracking

easli ist eine native mobile App und **setzt keine Cookies**. Wir
verwenden auch **kein App- oder Cross-App-Tracking**:

- Apple Privacy Manifest: `NSPrivacyTracking = false`.
- Es ist **kein** Facebook Pixel, Google Analytics, AppsFlyer, Branch,
  Adjust oder vergleichbares Tracking-SDK eingebunden.
- Es ist **keine** Werbe-ID (IDFA / Google Advertising ID) abgefragt.
- Es gibt **keine** Marketing-E-Mails. Wir haben deine Adresse gar nicht.

Die Website `https://easli.app` selbst setzt höchstens technisch
notwendige Cookies (Session, CSRF-Schutz) und kein Tracking.

---

## 11. Datensicherheit

Wir treffen technische und organisatorische Maßnahmen nach Art. 32 DSGVO:

- **Verschlüsselung in der Über­tragung:** sämtliche Verbindungen (App
  ↔ Server, Server ↔ Mistral, Server ↔ MongoDB) laufen über TLS 1.2
  oder höher.
- **Verschlüsselung at-rest:** MongoDB Atlas verschlüsselt alle gespei­
  cherten Daten auf der Festplatte mit AES-256.
- **Zugriffsbeschränkung:** auf die Datenbank haben nur der Operator
  (§1) und ein eng definierter Kreis von Auftragsverarbeitern Zugriff.
  Jeder Zugriff wird protokolliert.
- **Privacy-Logging:** Server-Logs enthalten **niemals** Inhalte deiner
  Dokumente oder Chats — ausschließlich Metadaten (HTTP-Methode, Pfad,
  Status, Dauer, Zeichen­zähler). Dies wird durch automatisierte Privacy-
  Tests im CI überprüft.
- **Rate-Limiting + Missbrauchs­erkennung** zum Schutz vor automatisierten
  Angriffen.

---

## 12. Beschwerde bei einer Aufsichts­behörde

Du hast nach Art. 77 DSGVO das Recht, dich bei einer Datenschutz-Aufsichts-
behörde zu beschweren — typischerweise der Behörde deines gewöhnlichen
Aufenthalts­orts.

**Deutschland (zuständig für easli):**
```
<<Zuständige Landesdaten­schutz­behörde des Sitzlandes des Operators>>
Kontakt: https://www.bfdi.bund.de/DE/Service/Anschriften/anschriften-node.html
```

Für Nutzer in anderen EU-Ländern findest du die zuständige Behörde unter:
[edpb.europa.eu/about-edpb/about-edpb/members_de](https://edpb.europa.eu/about-edpb/about-edpb/members_de).

---

## 13. Änderungen dieser Datenschutz­erklärung

Wir aktualisieren diese Erklärung, wenn sich die App, ihre Funktionen oder
unsere Auftrags­verarbeiter ändern. Die jeweils aktuelle Fassung findest
du jederzeit unter [easli.app/privacy](https://easli.app/privacy) sowie
in der App unter **Einstellungen → Datenschutz**.

Wesentliche Änderungen — etwa neue Auftrags­verarbeiter oder neue Datenkate-
gorien — kommunizieren wir aktiv über einen Hinweis in der App.

**Versions­historie**:

| Version | Stand | Änderung |
|---|---|---|
| 1.0 | 2026-05-24 | Erstveröffentlichung anlässlich des EU-weiten Launches (15 unterstützte Länder, Phase 6). |

---

## 14. Kontakt

- Datenschutz-Fragen: **privacy@easli.app**
- App-Review-Anfragen (Apple/Google): **review@easli.app**
- Allgemeines / Support: **hello@easli.app**

Wir antworten in **Deutsch, Englisch und Französisch**. Für andere
Sprachen brauchen wir eventuell etwas länger.

---

*easli ist ein Produkt von <<Operator-Name / Firma>>. Diese Datenschutz-
erklärung wurde mit größter Sorgfalt erstellt; eine juristische Prüfung
vor Live-Schaltung wird empfohlen, sobald der Operator-Sitz feststeht.*
