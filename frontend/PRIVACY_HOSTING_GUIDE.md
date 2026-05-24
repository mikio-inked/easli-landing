# Hosting der Privacy Policy — easli

> **Ziel:** `https://easli.app/privacy` als statische, schnell ausgelieferte
> Seite, die Apple- und Google-Reviewer ohne Umweg öffnen können.

Du hast `easli.app` bereits als Domäne. Drei Wege — sortiert nach
Geschwindigkeit “von nichts → live”:

---

## Variante A — Cloudflare Pages (empfohlen, 5 Minuten)

Voraussetzung: Dein DNS läuft über Cloudflare (was du ohnehin nutzt für
DDoS-Schutz). Cloudflare Pages ist gratis, EU-CDN per Default, kein
Build-Step nötig.

**Schritte:**

1. **Repo vorbereiten** — lege ein kleines Repo `easli-marketing` an (oder
   nutze einen `marketing/` Unterordner deines bestehenden GitHub-Repos):
   ```
   easli-marketing/
   ├─ public/
   │  ├─ index.html        ← deine Landing-Page (optional)
   │  └─ privacy.html      ← KOPIE von /app/frontend/privacy.html
   └─ README.md
   ```
   Kopiere `/app/frontend/privacy.html` nach `public/privacy.html`.

2. **Cloudflare Pages anlegen**
   - dash.cloudflare.com → *Workers & Pages* → *Create* → *Pages* →
     *Connect to Git* → dein Repo auswählen.
   - **Build settings:** *None / Static site*
   - **Build output directory:** `public`
   - *Save and Deploy* → nach ~30 Sekunden hast du eine
     `easli-marketing.pages.dev` Preview-URL.

3. **Custom Domain verknüpfen**
   - Im Pages-Projekt → *Custom domains* → *Set up a custom domain* →
     `easli.app` eintragen.
   - Cloudflare richtet die CNAMEs automatisch ein (du musst nichts manuell
     im DNS-Tab anpassen, weil die Domäne bei Cloudflare gehostet ist).
   - HTTPS-Zertifikat wird automatisch ausgestellt (3–5 Minuten).

4. **Verifizieren**
   ```
   curl -I https://easli.app/privacy
   → HTTP/2 200
   → content-type: text/html; charset=utf-8
   ```
   Im Browser: alle Tabellen, das TOC und das Dark-Mode-Styling müssen
   sauber rendern.

5. **Apple / Google Store eintragen**
   - App Store Connect → *App Privacy* → *Privacy Policy URL* →
     `https://easli.app/privacy`
   - Play Console → *Store presence* → *Main store listing* →
     *Privacy policy* → `https://easli.app/privacy`
   - In der App selbst (Settings → Über easli → Datenschutz) verlinkst
     du dieselbe URL.

**Vorteile:** EU-Edge-CDN, automatisches HTTPS, kein Server-Patching,
rollback per Git-Revert, gratis.

---

## Variante B — Vercel (ähnlich schnell)

Nur sinnvoll, wenn du Cloudflare-Pages nicht magst.

1. `npx vercel` im Ordner mit `privacy.html` als `index.html`-Äquivalent.
2. Im Vercel-Dashboard *Add Domain* → `easli.app`.
3. DNS-Einträge an Vercel übergeben — oder bei Cloudflare einen
   CNAME `easli.app → cname.vercel-dns.com` setzen.
4. Privacy-Policy-URL: `https://easli.app/privacy.html`
   (oder Rewrite-Regel auf `/privacy`).

**Nachteil:** US-First-Hosting per Default; du musst auf eine EU-Region
(z. B. `fra1`) achten, sonst geraten kleinste Performance-Anteile in die
USA.

---

## Variante C — GitHub Pages (langsamster, aber 0 Konfiguration)

1. Repo `easli/easli.github.io` anlegen.
2. `privacy.html` darin ablegen.
3. *Settings → Pages → Source: main branch* aktivieren.
4. Custom Domain: `easli.app` eintragen — GitHub gibt dir 2–3 CNAME-Werte,
   die du bei Cloudflare DNS eintragen musst.
5. Privacy-Policy-URL: `https://easli.app/privacy.html`

**Nachteil:** US-CDN (Fastly), keine EU-Priorisierung, längere First-Byte
Latenz für deutsche Nutzer.

---

## Vor dem Go-Live: kurze Pflicht-Checkliste

- [ ] Platzhalter `<<Vor- und Nachname / Firma>>`, `<<Straße und Hausnummer>>`,
      `<<PLZ Ort>>`, `<<Land>>` und `<<dein Hosting-Anbieter…>>` ersetzen
      — sowohl im **HTML** als auch im **Markdown**.
- [ ] Sicherstellen, dass die Mail-Adresse `privacy@easli.app` tatsächlich
      empfangsbereit ist (idealerweise mit 30-Tage-SLA in deinem
      Postfach).
- [ ] Falls du eine UG / GmbH / Ltd. gründest: das Impressum (separater
      Pflichtinhalt nach §5 TMG) ebenfalls hosten — z. B. unter
      `https://easli.app/impressum`. Diese Datei ist NICHT Teil dieses
      Pakets.
- [ ] Ein **letzter Lawyer-Review** wird empfohlen, sobald die finale
      Rechtsform feststeht. Die Vorlage ist sauber, ersetzt aber keine
      individuelle Rechtsberatung.
- [ ] Privacy-Policy-URL in `app.json` als `expo.privacyPolicyUrl` zu
      hinterlegen ist NICHT nötig (das Feld existiert nicht), aber füge
      sie zum In-App-Settings-Screen unter “Datenschutz” hinzu — der
      iOS-Reviewer schaut explizit dort nach.

---

## Wartung

- **Bei jeder Änderung der Auftragsverarbeiter, der Datenkategorien oder
  der Speicherdauer:** Markdown + HTML in lock-step aktualisieren, die
  Versionshistorie-Tabelle in §13 ergänzen, und einen kurzen In-App-
  Hinweis ausspielen.
- **Bei sprachlich größeren Änderungen** (z. B. neue EU-Sprachfassung): am
  besten ein zweites HTML `privacy.en.html` etc. anlegen und mit einem
  Sprach-Toggle im Header zwischen ihnen wechseln. Für v1 ist nur die
  deutsche Fassung verbindlich.
