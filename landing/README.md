# easli landing page

Static 4-page site for `https://easli.app`. Plain HTML + CSS, no JavaScript, total bundle size ~25 KB. Hostable anywhere — IONOS Webhosting, GitHub Pages, Vercel, Netlify, Cloudflare Pages.

## Files

```
landing/
├── index.html      ← Marketing landing (https://easli.app/)
├── privacy.html    ← Datenschutzerklärung (https://easli.app/privacy)
├── imprint.html    ← Impressum (https://easli.app/imprint)
├── support.html    ← Support / FAQ (https://easli.app/support)
├── style.css       ← Shared stylesheet (5 KB)
└── README.md       ← This file
```

## App Store URLs you can use after deploy

- **Marketing URL**: `https://easli.app/`
- **Privacy Policy URL**: `https://easli.app/privacy.html`
- **Support URL**: `https://easli.app/support.html`

> Note: pretty URLs (`/privacy` instead of `/privacy.html`) only work on hosts that auto-resolve the `.html`. IONOS does this by default; GitHub Pages and Netlify too. Vercel needs a small `vercel.json` rewrite (see below).

## Deployment options

### Option 1 — IONOS Webhosting (recommended; you're already there)

1. IONOS Login → **Hosting** → dein Webhosting-Tarif (oder bei einem reinen Domainvertrag den Punkt **Webspace bestellen** — bei IONOS ist Hosting bei der Domain-Registrierung oft schon dabei).
2. **Verzeichnis öffnen** → entweder via **Webdav-URL** im Finder oder **SFTP** (siehe IONOS-Anleitung „SFTP-Zugang einrichten").
3. Lade alle 5 Dateien (`*.html` + `style.css`) ins Wurzelverzeichnis (`/` oder `htdocs/` je nach Tarif).
4. Domain-Zuordnung in IONOS: **Domains & SSL** → easli.app → **Ziel** → auf das Webhosting-Verzeichnis verweisen.
5. SSL-Zertifikat (Let's Encrypt) wird automatisch ausgestellt — kann 1-5 Min dauern.

**Test:** `curl -sI https://easli.app/` → HTTP 200.

### Option 2 — GitHub Pages (kostenlos, kein Hosting nötig)

1. Neues Repo `easli-landing` auf GitHub anlegen (public oder privat).
2. Push diese 5 Dateien ins Wurzelverzeichnis.
3. Repo → **Settings** → **Pages** → Source: **main / (root)** → Save.
4. Custom Domain konfigurieren → `easli.app` → Save. GitHub Pages legt automatisch eine `CNAME`-Datei an.
5. Bei IONOS: **A-Records** für die Apex-Domain `easli.app` setzen auf:
   - `185.199.108.153`
   - `185.199.109.153`
   - `185.199.110.153`
   - `185.199.111.153`
6. SSL aktivieren in GitHub Pages → Enforce HTTPS.

Dauert insgesamt 10-15 Min. Empfehlenswert wenn du IONOS-Webhosting nicht bezahlt hast.

### Option 3 — Vercel (kostenlos, schnellste Bereitstellung)

```bash
cd landing
npm install -g vercel
vercel deploy --prod
# Folge dem Wizard: Login, Project-Name = easli-landing, Build = none, Output = ./
```

Anschließend in Vercel → Settings → Domains → `easli.app` hinzufügen → die zwei DNS-Anweisungen (A-Record + AAAA-Record) bei IONOS setzen.

Für pretty URLs (`/privacy` ohne `.html`) ein `vercel.json` neben den HTMLs mit:

```json
{
  "cleanUrls": true,
  "trailingSlash": false
}
```

## Apex vs. www

- IONOS: Setze `www.easli.app` als 301-Redirect auf `easli.app` (im DNS-Manager → "Subdomain weiterleiten").
- GitHub Pages: Trage in der `CNAME`-Datei nur `easli.app` ein (ohne www).
- Vercel: setzt das automatisch.

## Was noch fehlt (TODO nach Deploy)

- ~~`og.png` — Open-Graph-Bild 1200×630 für Link-Previews~~ ✅ vorhanden
- ~~`apple-touch-icon.png` — 180×180 für iOS-Home-Screen-Bookmarks~~ ✅ vorhanden
- App Store + Google Play Buttons aktivieren — sobald die App live ist, in `index.html` die `class="btn-store disabled"` entfernen und `href="#"` durch echte Store-URLs ersetzen.
- Optional: Cookie-Banner — du brauchst keinen, weil keine Cookies / kein Tracking. Aber falls du z. B. später Plausible Analytics einbaust, dann ja.

## Marketing-Assets neu generieren

`og.png` und `apple-touch-icon.png` werden aus `_make_assets.py` erzeugt. Falls du die Texte/Farben ändern willst:

```bash
cd landing
python3 _make_assets.py
# überschreibt og.png und apple-touch-icon.png mit dem neuen Branding
```

Beide Dateien sind in HTML eingebunden via:
- `<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">`
- `<meta property="og:image" content="https://easli.app/og.png">`

## Updaten

Wenn du Texte ändern willst — direkt in den HTML-Dateien editieren und neu hochladen. Kein Build-Schritt.
