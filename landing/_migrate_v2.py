#!/usr/bin/env python3
"""easli 2.0 landing migration

Phase 1: Patches applied to ALL locale index.html files (existing + new)
  - iOS App Store button enabled with real URL
  - Play Store button stays disabled ("Coming soon")
  - "Frankfurt" → "Paris (Mistral AI, France)" factual fix
  - Hreflang block expanded to all 11 locales + x-default
  - Lang-switch nav expanded to all 11 locales
  - Hero/final-CTA eyebrow updated to "Live on App Store · Android coming soon"

Phase 2: Generate 5 new locales (tr, ru, vi, zh-Hans, nl) from en/index.html
  - Per-locale title/desc/h1/etc. translations
  - Localised lang/og:url/canonical/hreflang current-page
"""
import re
import shutil
from pathlib import Path

BASE = Path("/app/landing")
APPSTORE_URL = "https://apps.apple.com/app/easli-understand-letters/id6765859779"

# ---------------------------------------------------------------------------
# All 11 locales — display label for the lang-switch nav
# ---------------------------------------------------------------------------
LOCALES = [
    ("de", "/",          "Deutsch",  "DE"),
    ("en", "/en/",       "English",  "EN"),
    ("fr", "/fr/",       "Français", "FR"),
    ("es", "/es/",       "Español",  "ES"),
    ("it", "/it/",       "Italiano", "IT"),
    ("pl", "/pl/",       "Polski",   "PL"),
    ("nl", "/nl/",       "Nederlands","NL"),
    ("tr", "/tr/",       "Türkçe",   "TR"),
    ("ru", "/ru/",       "Русский",  "RU"),
    ("zh-Hans", "/zh/",  "中文",      "中文"),
    ("vi", "/vi/",       "Tiếng Việt","VI"),
]

# ---------------------------------------------------------------------------
# Phase-1 universal translation tables (per-locale phrasing)
# Only what changes between locales for L1+L2 patches.
# ---------------------------------------------------------------------------
APPSTORE_LABEL = {  # <small>{prefix}</small><strong>App Store</strong>
    "de": ("Laden im", "Bald bei", "Im App Store laden", "Bald bei Google Play, in Kürze verfügbar"),
    "en": ("Download on the", "Coming soon to", "Download on the App Store", "Coming soon to Google Play"),
    "fr": ("Télécharger dans l'", "Bientôt sur", "Télécharger dans l'App Store", "Bientôt sur Google Play"),
    "es": ("Descargar en", "Próximamente en", "Descargar en App Store", "Próximamente en Google Play"),
    "it": ("Scarica su", "Presto su", "Scarica su App Store", "Presto su Google Play"),
    "pl": ("Pobierz w", "Wkrótce w", "Pobierz w App Store", "Wkrótce w Google Play"),
    "nl": ("Download in de", "Binnenkort in", "Download in de App Store", "Binnenkort in Google Play"),
    "tr": ("İndir:", "Yakında:", "App Store'dan indir", "Yakında Google Play'de"),
    "ru": ("Скачать в", "Скоро в", "Скачать в App Store", "Скоро в Google Play"),
    "zh-Hans": ("下载", "即将上线", "在 App Store 下载", "即将上线 Google Play"),
    "vi": ("Tải về trên", "Sắp ra mắt trên", "Tải về trên App Store", "Sắp ra mắt trên Google Play"),
}

EYEBROW_LIVE = {
    "de": "Jetzt im App Store · Android folgt",
    "en": "Live on App Store · Android coming soon",
    "fr": "Disponible sur l'App Store · Android bientôt",
    "es": "Ya en App Store · Android pronto",
    "it": "Disponibile su App Store · Android in arrivo",
    "pl": "Już w App Store · Android wkrótce",
    "nl": "Nu in de App Store · Android binnenkort",
    "tr": "App Store'da yayında · Android yakında",
    "ru": "Уже в App Store · Android скоро",
    "zh-Hans": "现已上线 App Store · Android 即将推出",
    "vi": "Đã có trên App Store · Android sắp ra mắt",
}

# "Servers in Frankfurt" → "Servers in Paris (Mistral AI, France)"
SERVER_LOCATION = {
    "de": "Unsere Server stehen in Paris (Mistral AI, Frankreich). Deine Daten verlassen die EU nicht.",
    "en": "Our servers sit in Paris (Mistral AI, France). Your data stays inside the EU.",
    "fr": "Nos serveurs sont à Paris (Mistral AI, France). Vos données ne quittent pas l'UE.",
    "es": "Nuestros servidores están en París (Mistral AI, Francia). Tus datos no salen de la UE.",
    "it": "I nostri server sono a Parigi (Mistral AI, Francia). I tuoi dati non lasciano l'UE.",
    "pl": "Nasze serwery znajdują się w Paryżu (Mistral AI, Francja). Twoje dane nie opuszczają UE.",
    "nl": "Onze servers staan in Parijs (Mistral AI, Frankrijk). Je gegevens verlaten de EU niet.",
    "tr": "Sunucularımız Paris'te (Mistral AI, Fransa). Verileriniz AB sınırları dışına çıkmaz.",
    "ru": "Наши серверы находятся в Париже (Mistral AI, Франция). Ваши данные не покидают ЕС.",
    "zh-Hans": "我们的服务器位于巴黎(Mistral AI,法国)。您的数据不离开欧盟。",
    "vi": "Máy chủ của chúng tôi đặt tại Paris (Mistral AI, Pháp). Dữ liệu của bạn không rời khỏi EU.",
}

# ---------------------------------------------------------------------------
# Phase-2 full body translations for the 5 NEW locales
# Built from en/index.html as canonical source.
# Each value is the localized replacement of the EN source string.
# ---------------------------------------------------------------------------

# Translations indexed by english source string.
# Keep terse and accurate; native-speaker review recommended before launch.
T = {
    # ===================== nl (Nederlands) =====================
    "nl": {
        "Finally understand what your letter means": "Eindelijk begrijpen wat er in je brief staat",
        "One photo is enough. easli explains any official letter in your language, shows you deadlines and helps you reply. 25+ languages. EU-hosted. GDPR-compliant.":
            "Eén foto is genoeg. easli legt elke officiële brief uit in jouw taal, toont deadlines en helpt je met een antwoord. 25+ talen. EU-gehost. AVG-conform.",
        "One photo is enough. easli explains any official letter in your language.":
            "Eén foto is genoeg. easli legt elke officiële brief uit in jouw taal.",
        "Skip to content": "Naar de inhoud",
        "easli home": "easli home",
        "How it works": "Zo werkt het",
        "Languages": "Talen",
        "Privacy": "Privacy",
        "Support": "Support",
        "Switch language": "Taal wisselen",
        "Master your paperwork.": "Krijg grip op je papierwerk.",
        "Any language. Across Europe.": "In elke taal. Door heel Europa.",
        "Rental contract in Madrid, electricity bill in Berlin, doctor's letter in Rome — easli explains any document in seconds, warns about scams, and drafts the right reply.":
            "Huurcontract in Madrid, energierekening in Berlijn, doktersbrief in Rome — easli legt elk document in seconden uit, waarschuwt voor oplichting en stelt het juiste antwoord op.",
        "No account needed": "Geen account nodig",
        "EU-hosted": "EU-gehost",
        "GDPR-compliant": "AVG-conform",
        "Federal Employment Agency · 12345": "Uitkeringsinstantie · 12345",
        "URGENT": "URGENT",
        "2 WEEKS": "2 WEKEN",
        "Request for cooperation": "Verzoek om medewerking",
        "Analysis": "Analyse",
        "● Important · Deadline": "● Belangrijk · Deadline",
        "Submit missing documents": "Ontbrekende documenten indienen",
        "Federal Employment Agency": "Uitkeringsinstantie",
        "Due in": "Te doen binnen",
        "14 days": "14 dagen",
        "Reply on time.": "Antwoord op tijd.",
        "Draft a reply": "Antwoord opstellen",
        "Sound familiar?": "Komt het je bekend voor?",
        "Three seconds after opening.": "Drie seconden na het openen.",
        "A letter lands on the table. And your head starts running the same loop.":
            "Een brief ligt op tafel. En je hoofd begint dezelfde lus.",
        "„Why is the authority writing to me?\"": "„Waarom schrijft de instantie mij?\"",
        "The tone sounds serious. The words are long. And you don't really get what it's about.":
            "De toon klinkt serieus. De woorden zijn lang. En je begrijpt eigenlijk niet waar het over gaat.",
        "„How much time do I have?\"": "„Hoeveel tijd heb ik?\"",
        "There's a deadline somewhere. Maybe important, maybe not. You can't quite tell.":
            "Er staat ergens een deadline. Misschien belangrijk, misschien niet. Je weet het niet zeker.",
        "„And what am I supposed to do?\"": "„En wat moet ik doen?\"",
        "Submit something? Write a reply? Wait it out? You just don't want to get it wrong.":
            "Iets indienen? Antwoord schrijven? Afwachten? Je wilt geen fout maken.",
        "Before · After": "Voor · Na",
        "From bureaucratic jargon": "Van ambtelijk jargon",
        "to one clear sentence": "naar één duidelijke zin",
        "easli doesn't just translate your letter. It explains what actually matters.":
            "easli vertaalt niet alleen je brief. Het legt uit wat echt belangrijk is.",
        "Original": "Origineel",
        "12 letter types · one tool": "12 brieftypen · één tool",
        "easli is": "easli is",
        "not just for the tax office": "niet alleen voor de Belastingdienst",
        "We cover everything that lands in your mailbox. Authorities, banks, landlords, insurers, doctors, courts — every letter, one clear answer.":
            "Wij dekken alles wat in je brievenbus belandt. Instanties, banken, verhuurders, verzekeraars, artsen, rechtbanken — elke brief, één duidelijk antwoord.",
        "Rent & Housing": "Huur & Wonen",
        "Leases, utility bills, dunning, evictions": "Huurcontracten, servicekosten, aanmaningen, ontruimingen",
        "Electricity, Gas, Water": "Elektriciteit, Gas, Water",
        "Utility statements, prepayments, plan switches": "Energierekeningen, voorschotten, contractwissels",
        "Banking & Taxes": "Bank & Belastingen",
        "Tax notices, statements, loans": "Belastingaanslagen, afschriften, leningen",
        "Telecom & Subscriptions": "Telecom & Abonnementen",
        "Mobile, internet, broadcasting fees": "Mobiel, internet, mediabijdrage",
        "Courts & Lawyers": "Rechtbank & Advocaat",
        "Payment orders, summons, attachments": "Dwangbevelen, dagvaardingen, beslagleggingen",
        "Government & Offices": "Overheid & Diensten",
        "Immigration, employment, fines": "IND, UWV, boetes",
        "Insurance": "Verzekeringen",
        "Health, liability, car, pension": "Zorg, aansprakelijkheid, auto, pensioen",
        "Work & Contracts": "Werk & Contracten",
        "Payslips, employer letters": "Loonstroken, werkgeversbrieven",
        "Healthcare": "Gezondheidszorg",
        "Doctor's letters, hospital bills, prescriptions": "Doktersbrieven, ziekenhuisrekeningen, recepten",
        "Education": "Onderwijs",
        "School, university, kindergarten, grants": "School, universiteit, kinderopvang, studiebeurs",
        "Parcels & Other": "Pakketten & Overig",
        "Deliveries, ads, personal mail": "Leveringen, reclame, persoonlijke post",
        "Scam Shield": "Oplichtingsbescherming",
        "We warn when IBANs or senders look off": "We waarschuwen bij verdachte IBANs of afzenders",
        "Done in two minutes.": "Klaar in twee minuten.",
        "No account. No setup. Open the app and point the camera.":
            "Geen account. Geen setup. Open de app en richt de camera.",
        "Take a photo": "Maak een foto",
        "Snap the letter with the camera or pick a PDF from your files. Multiple pages work too.":
            "Maak een foto van de brief of kies een PDF. Meerdere pagina's werken ook.",
        "Read the explanation": "Lees de uitleg",
        "You get the essence of the letter in your language. What it's about. How urgent. What to do next.":
            "Je krijgt de essentie van de brief in jouw taal. Waar het over gaat. Hoe urgent. Wat te doen.",
        "Send a reply": "Verstuur een antwoord",
        "Accept a draft reply, adjust it, copy it. The reply is automatically in the sender's language.":
            "Accepteer een conceptantwoord, pas het aan, kopieer het. Het antwoord is automatisch in de taal van de afzender.",
        "🌍 25+ languages": "🌍 25+ talen",
        "Your letter. In": "Je brief. In",
        "Read every letter in the language you actually think in. No matter where it comes from.":
            "Lees elke brief in de taal waarin je denkt. Waar hij ook vandaan komt.",
        "✍️ <b>Smart twist:</b> You read in your own language, but the reply draft is automatically written in the sender's language.":
            "✍️ <b>Slimme draai:</b> Je leest in je eigen taal, maar het conceptantwoord wordt automatisch in de taal van de afzender geschreven.",
        "🔒 Privacy is the starting point": "🔒 Privacy is het uitgangspunt",
        "Your letters stay your business.": "Jouw brieven blijven jouw zaak.",
        "Official mail is personal. We built easli so you never have to hand over more than you need to.":
            "Officiële post is persoonlijk. We hebben easli zo gebouwd dat je nooit meer hoeft te delen dan nodig is.",
        "No account. No email.": "Geen account. Geen e-mail.",
        "No name, no profile. easli works anonymously.": "Geen naam, geen profiel. easli werkt anoniem.",
        "Hosted in Europe.": "Gehost in Europa.",
        "We don't keep your letters.": "We bewaren je brieven niet.",
        "The photo isn't stored long-term. Only the plain-language explanation stays.":
            "De foto wordt niet langdurig bewaard. Alleen de uitleg in duidelijke taal blijft.",
        "Delete everything, any time.": "Verwijder alles, op elk moment.",
        "One tap in settings and your history is gone. For good.":
            "Eén tik in de instellingen en je geschiedenis is weg. Voorgoed.",
        "Read the full privacy policy →": "Lees het volledige privacybeleid →",
        "Who it's for": "Voor wie",
        "For anyone who needs clarity.": "Voor iedereen die duidelijkheid nodig heeft.",
        "easli is built for people who don't deal with official letters every day.":
            "easli is gebouwd voor mensen die niet elke dag met officiële post te maken hebben.",
        "New in Europe": "Nieuw in Europa",
        "The language isn't home yet. But the authorities already are.":
            "De taal is nog niet thuis. Maar de instanties wel al.",
        "Students": "Studenten",
        "Rent, tuition, insurance. A new letter every week.":
            "Huur, collegegeld, verzekering. Elke week een nieuwe brief.",
        "Families": "Gezinnen",
        "Multiple authorities, multiple deadlines. Someone has to keep track.":
            "Meerdere instanties, meerdere deadlines. Iemand moet het bijhouden.",
        "Older people": "Ouderen",
        "Small print, big impact. easli reads loud and explains softly.":
            "Kleine letters, grote impact. easli leest hardop en legt zacht uit.",
        "✨ Coming soon": "✨ Nu live",
        "Stop the uneasy feeling": "Stop het onbehagen",
        "at the mailbox.": "bij de brievenbus.",
        "easli launches shortly. Drop us a note and we'll let you know the moment it's live.":
            "easli is nu in de App Store. Android volgt binnenkort.",
        "Imprint": "Colofon",
        "Contact": "Contact",
        "Made in the EU": "Gemaakt in de EU",
        "Lampertheim, Germany": "Lampertheim, Duitsland",
    },

    # ===================== tr (Türkçe) =====================
    "tr": {
        "Finally understand what your letter means": "Mektubunda yazanı sonunda anla",
        "One photo is enough. easli explains any official letter in your language, shows you deadlines and helps you reply. 25+ languages. EU-hosted. GDPR-compliant.":
            "Bir fotoğraf yeter. easli, her resmi mektubu kendi dilinde açıklar, son tarihleri gösterir ve cevap yazmana yardım eder. 25+ dil. AB barındırma. GDPR uyumlu.",
        "One photo is enough. easli explains any official letter in your language.":
            "Bir fotoğraf yeter. easli, her resmi mektubu kendi dilinde açıklar.",
        "Skip to content": "İçeriğe geç",
        "easli home": "easli ana sayfa",
        "How it works": "Nasıl çalışır",
        "Languages": "Diller",
        "Privacy": "Gizlilik",
        "Support": "Destek",
        "Switch language": "Dil değiştir",
        "Master your paperwork.": "Evrak işlerine hakim ol.",
        "Any language. Across Europe.": "Her dilde. Avrupa'nın her yerinde.",
        "Rental contract in Madrid, electricity bill in Berlin, doctor's letter in Rome — easli explains any document in seconds, warns about scams, and drafts the right reply.":
            "Madrid'de kira sözleşmesi, Berlin'de elektrik faturası, Roma'da doktor mektubu — easli her belgeyi saniyeler içinde açıklar, dolandırıcılıklara karşı uyarır ve doğru cevabı hazırlar.",
        "No account needed": "Hesap gerekmez",
        "EU-hosted": "AB'de barındırılır",
        "GDPR-compliant": "GDPR uyumlu",
        "Federal Employment Agency · 12345": "İş Kurumu · 12345",
        "URGENT": "ACİL",
        "2 WEEKS": "2 HAFTA",
        "Request for cooperation": "İşbirliği talebi",
        "Analysis": "Analiz",
        "● Important · Deadline": "● Önemli · Son tarih",
        "Submit missing documents": "Eksik belgeleri ilet",
        "Federal Employment Agency": "İş Kurumu",
        "Due in": "Kalan süre:",
        "14 days": "14 gün",
        "Reply on time.": "Zamanında cevap ver.",
        "Draft a reply": "Cevap hazırla",
        "Sound familiar?": "Tanıdık geliyor mu?",
        "Three seconds after opening.": "Açıldıktan üç saniye sonra.",
        "A letter lands on the table. And your head starts running the same loop.":
            "Bir mektup masaya düşer. Ve kafan aynı döngüye girer.",
        "„Why is the authority writing to me?\"": "„Devlet bana neden yazıyor?\"",
        "The tone sounds serious. The words are long. And you don't really get what it's about.":
            "Ciddi bir ton. Uzun kelimeler. Konunun ne olduğunu tam anlamıyorsun.",
        "„How much time do I have?\"": "„Ne kadar zamanım var?\"",
        "There's a deadline somewhere. Maybe important, maybe not. You can't quite tell.":
            "Bir yerde son tarih var. Belki önemli, belki değil. Emin değilsin.",
        "„And what am I supposed to do?\"": "„Peki ben ne yapmalıyım?\"",
        "Submit something? Write a reply? Wait it out? You just don't want to get it wrong.":
            "Bir şey mi ileteyim? Cevap mı yazayım? Bekleyeyim mi? Sadece hata yapmak istemiyorsun.",
        "Before · After": "Önce · Sonra",
        "From bureaucratic jargon": "Bürokratik jargondan",
        "to one clear sentence": "tek bir net cümleye",
        "easli doesn't just translate your letter. It explains what actually matters.":
            "easli sadece mektubunu çevirmez. Asıl önemli olanı açıklar.",
        "Original": "Orijinal",
        "12 letter types · one tool": "12 mektup türü · tek araç",
        "easli is": "easli sadece",
        "not just for the tax office": "vergi dairesi için değil",
        "We cover everything that lands in your mailbox. Authorities, banks, landlords, insurers, doctors, courts — every letter, one clear answer.":
            "Posta kutuna düşen her şeyi kapsarız. Kurumlar, bankalar, ev sahipleri, sigortacılar, doktorlar, mahkemeler — her mektup, tek bir net cevap.",
        "Rent & Housing": "Kira & Konut",
        "Leases, utility bills, dunning, evictions": "Kira sözleşmeleri, faturalar, ihtarlar, tahliyeler",
        "Electricity, Gas, Water": "Elektrik, Gaz, Su",
        "Utility statements, prepayments, plan switches": "Fatura dökümleri, ön ödemeler, tarife değişiklikleri",
        "Banking & Taxes": "Banka & Vergi",
        "Tax notices, statements, loans": "Vergi tebligatları, ekstreler, krediler",
        "Telecom & Subscriptions": "Telekom & Abonelikler",
        "Mobile, internet, broadcasting fees": "Mobil, internet, yayın katkı payı",
        "Courts & Lawyers": "Mahkeme & Avukat",
        "Payment orders, summons, attachments": "Ödeme emirleri, celpler, hacizler",
        "Government & Offices": "Devlet & Daireler",
        "Immigration, employment, fines": "Göç idaresi, iş kurumu, cezalar",
        "Insurance": "Sigorta",
        "Health, liability, car, pension": "Sağlık, sorumluluk, araç, emeklilik",
        "Work & Contracts": "İş & Sözleşmeler",
        "Payslips, employer letters": "Maaş bordroları, işveren yazıları",
        "Healthcare": "Sağlık",
        "Doctor's letters, hospital bills, prescriptions": "Doktor yazıları, hastane faturaları, reçeteler",
        "Education": "Eğitim",
        "School, university, kindergarten, grants": "Okul, üniversite, anaokulu, burslar",
        "Parcels & Other": "Kargo & Diğer",
        "Deliveries, ads, personal mail": "Teslimatlar, reklamlar, özel posta",
        "Scam Shield": "Dolandırıcılık Kalkanı",
        "We warn when IBANs or senders look off": "Şüpheli IBAN veya gönderici durumunda uyarırız",
        "Done in two minutes.": "İki dakikada tamam.",
        "No account. No setup. Open the app and point the camera.":
            "Hesap yok. Kurulum yok. Uygulamayı aç ve kamerayı doğrult.",
        "Take a photo": "Fotoğraf çek",
        "Snap the letter with the camera or pick a PDF from your files. Multiple pages work too.":
            "Kamerayla mektubu çek veya dosyalardan PDF seç. Birden fazla sayfa da olur.",
        "Read the explanation": "Açıklamayı oku",
        "You get the essence of the letter in your language. What it's about. How urgent. What to do next.":
            "Mektubun özünü kendi dilinde alırsın. Ne hakkında. Ne kadar acil. Sıradaki adım ne.",
        "Send a reply": "Cevap gönder",
        "Accept a draft reply, adjust it, copy it. The reply is automatically in the sender's language.":
            "Bir taslak cevap kabul et, düzelt, kopyala. Cevap otomatik olarak göndericinin dilinde olur.",
        "🌍 25+ languages": "🌍 25+ dil",
        "Your letter. In": "Mektubun.",
        "Read every letter in the language you actually think in. No matter where it comes from.":
            "Her mektubu gerçekten düşündüğün dilde oku. Nereden geldiği önemli değil.",
        "✍️ <b>Smart twist:</b> You read in your own language, but the reply draft is automatically written in the sender's language.":
            "✍️ <b>Akıllı dokunuş:</b> Sen kendi dilinde okursun, ama cevap taslağı otomatik olarak göndericinin dilinde yazılır.",
        "🔒 Privacy is the starting point": "🔒 Gizlilik başlangıç noktasıdır",
        "Your letters stay your business.": "Mektupların sana ait kalır.",
        "Official mail is personal. We built easli so you never have to hand over more than you need to.":
            "Resmi posta kişiseldir. easli'yi, gerekenden fazlasını asla teslim etmek zorunda kalmayasın diye kurduk.",
        "No account. No email.": "Hesap yok. E-posta yok.",
        "No name, no profile. easli works anonymously.": "İsim yok, profil yok. easli anonim çalışır.",
        "Hosted in Europe.": "Avrupa'da barındırılır.",
        "We don't keep your letters.": "Mektuplarını saklamayız.",
        "The photo isn't stored long-term. Only the plain-language explanation stays.":
            "Fotoğraf uzun süre saklanmaz. Sadece sade dilde açıklama kalır.",
        "Delete everything, any time.": "Her şeyi, istediğin zaman sil.",
        "One tap in settings and your history is gone. For good.":
            "Ayarlarda bir dokunuş, geçmişin silinir. Tamamen.",
        "Read the full privacy policy →": "Tam gizlilik politikasını oku →",
        "Who it's for": "Kimin için",
        "For anyone who needs clarity.": "Netlik isteyen herkes için.",
        "easli is built for people who don't deal with official letters every day.":
            "easli, her gün resmi mektuplarla uğraşmayanlar için yapıldı.",
        "New in Europe": "Avrupa'da yeni",
        "The language isn't home yet. But the authorities already are.":
            "Dil henüz ev gibi değil. Ama kurumlar çoktan öyle.",
        "Students": "Öğrenciler",
        "Rent, tuition, insurance. A new letter every week.":
            "Kira, harç, sigorta. Her hafta yeni bir mektup.",
        "Families": "Aileler",
        "Multiple authorities, multiple deadlines. Someone has to keep track.":
            "Birden fazla kurum, birden fazla son tarih. Birinin takip etmesi lazım.",
        "Older people": "Yaşlılar",
        "Small print, big impact. easli reads loud and explains softly.":
            "Küçük yazı, büyük etki. easli yüksek sesle okur, yumuşakça açıklar.",
        "✨ Coming soon": "✨ Şimdi yayında",
        "Stop the uneasy feeling": "Posta kutusundaki",
        "at the mailbox.": "huzursuzluğa son ver.",
        "easli launches shortly. Drop us a note and we'll let you know the moment it's live.":
            "easli artık App Store'da. Android sürümü yakında geliyor.",
        "Imprint": "Künye",
        "Contact": "İletişim",
        "Made in the EU": "AB'de yapıldı",
        "Lampertheim, Germany": "Lampertheim, Almanya",
    },

    # ===================== ru (Русский) =====================
    "ru": {
        "Finally understand what your letter means": "Наконец-то поймите, что написано в письме",
        "One photo is enough. easli explains any official letter in your language, shows you deadlines and helps you reply. 25+ languages. EU-hosted. GDPR-compliant.":
            "Одной фотографии достаточно. easli объяснит любое официальное письмо на вашем языке, покажет сроки и поможет ответить. 25+ языков. Хостинг в ЕС. Соответствует GDPR.",
        "One photo is enough. easli explains any official letter in your language.":
            "Одной фотографии достаточно. easli объяснит любое письмо на вашем языке.",
        "Skip to content": "Перейти к содержимому",
        "easli home": "easli главная",
        "How it works": "Как это работает",
        "Languages": "Языки",
        "Privacy": "Конфиденциальность",
        "Support": "Поддержка",
        "Switch language": "Сменить язык",
        "Master your paperwork.": "Возьмите бумажную работу под контроль.",
        "Any language. Across Europe.": "На любом языке. По всей Европе.",
        "Rental contract in Madrid, electricity bill in Berlin, doctor's letter in Rome — easli explains any document in seconds, warns about scams, and drafts the right reply.":
            "Договор аренды в Мадриде, счёт за электричество в Берлине, письмо от врача в Риме — easli объясняет любой документ за секунды, предупреждает о мошенничестве и составляет правильный ответ.",
        "No account needed": "Без аккаунта",
        "EU-hosted": "Хостинг в ЕС",
        "GDPR-compliant": "Соответствует GDPR",
        "Federal Employment Agency · 12345": "Служба занятости · 12345",
        "URGENT": "СРОЧНО",
        "2 WEEKS": "2 НЕДЕЛИ",
        "Request for cooperation": "Запрос о содействии",
        "Analysis": "Анализ",
        "● Important · Deadline": "● Важно · Срок",
        "Submit missing documents": "Подать недостающие документы",
        "Federal Employment Agency": "Служба занятости",
        "Due in": "Срок:",
        "14 days": "14 дней",
        "Reply on time.": "Ответьте вовремя.",
        "Draft a reply": "Составить ответ",
        "Sound familiar?": "Знакомо?",
        "Three seconds after opening.": "Через три секунды после вскрытия.",
        "A letter lands on the table. And your head starts running the same loop.":
            "Письмо ложится на стол. И в голове запускается всё та же петля.",
        "„Why is the authority writing to me?\"": "„Почему ведомство пишет мне?\"",
        "The tone sounds serious. The words are long. And you don't really get what it's about.":
            "Тон серьёзный. Слова длинные. И вы толком не понимаете, о чём это.",
        "„How much time do I have?\"": "„Сколько у меня времени?\"",
        "There's a deadline somewhere. Maybe important, maybe not. You can't quite tell.":
            "Где-то указан срок. Может, важно, может, нет. Сложно сказать.",
        "„And what am I supposed to do?\"": "„И что я должен делать?\"",
        "Submit something? Write a reply? Wait it out? You just don't want to get it wrong.":
            "Что-то подать? Написать ответ? Подождать? Просто не хочется ошибиться.",
        "Before · After": "До · После",
        "From bureaucratic jargon": "От бюрократического жаргона",
        "to one clear sentence": "к одному ясному предложению",
        "easli doesn't just translate your letter. It explains what actually matters.":
            "easli не просто переводит письмо. Он объясняет, что действительно важно.",
        "Original": "Оригинал",
        "12 letter types · one tool": "12 типов писем · один инструмент",
        "easli is": "easli —",
        "not just for the tax office": "не только для налоговой",
        "We cover everything that lands in your mailbox. Authorities, banks, landlords, insurers, doctors, courts — every letter, one clear answer.":
            "Мы охватываем всё, что попадает в ваш почтовый ящик. Госорганы, банки, арендодатели, страховые, врачи, суды — каждое письмо, один ясный ответ.",
        "Rent & Housing": "Аренда и жильё",
        "Leases, utility bills, dunning, evictions": "Договоры аренды, ЖКХ, требования, выселения",
        "Electricity, Gas, Water": "Электричество, Газ, Вода",
        "Utility statements, prepayments, plan switches": "Счета, авансы, смена тарифа",
        "Banking & Taxes": "Банки и налоги",
        "Tax notices, statements, loans": "Налоговые уведомления, выписки, кредиты",
        "Telecom & Subscriptions": "Связь и подписки",
        "Mobile, internet, broadcasting fees": "Мобильная связь, интернет, абонплата",
        "Courts & Lawyers": "Суд и адвокаты",
        "Payment orders, summons, attachments": "Судебные приказы, повестки, аресты",
        "Government & Offices": "Госорганы и ведомства",
        "Immigration, employment, fines": "Миграционная служба, биржа труда, штрафы",
        "Insurance": "Страхование",
        "Health, liability, car, pension": "Здоровье, ответственность, авто, пенсия",
        "Work & Contracts": "Работа и договоры",
        "Payslips, employer letters": "Расчётные листы, письма работодателя",
        "Healthcare": "Здравоохранение",
        "Doctor's letters, hospital bills, prescriptions": "Письма врачей, счета больниц, рецепты",
        "Education": "Образование",
        "School, university, kindergarten, grants": "Школа, университет, детсад, стипендии",
        "Parcels & Other": "Посылки и прочее",
        "Deliveries, ads, personal mail": "Доставки, реклама, личная почта",
        "Scam Shield": "Защита от мошенников",
        "We warn when IBANs or senders look off": "Предупреждаем при подозрительных IBAN или отправителях",
        "Done in two minutes.": "Готово за две минуты.",
        "No account. No setup. Open the app and point the camera.":
            "Без аккаунта. Без настройки. Откройте приложение и наведите камеру.",
        "Take a photo": "Сделайте фото",
        "Snap the letter with the camera or pick a PDF from your files. Multiple pages work too.":
            "Сфотографируйте письмо или выберите PDF из файлов. Несколько страниц тоже работают.",
        "Read the explanation": "Прочитайте объяснение",
        "You get the essence of the letter in your language. What it's about. How urgent. What to do next.":
            "Вы получаете суть письма на своём языке. О чём оно. Насколько срочно. Что делать дальше.",
        "Send a reply": "Отправьте ответ",
        "Accept a draft reply, adjust it, copy it. The reply is automatically in the sender's language.":
            "Примите черновик, откорректируйте, скопируйте. Ответ автоматически на языке отправителя.",
        "🌍 25+ languages": "🌍 25+ языков",
        "Your letter. In": "Ваше письмо. На",
        "Read every letter in the language you actually think in. No matter where it comes from.":
            "Читайте каждое письмо на языке, на котором действительно думаете. Откуда бы оно ни пришло.",
        "✍️ <b>Smart twist:</b> You read in your own language, but the reply draft is automatically written in the sender's language.":
            "✍️ <b>Умный приём:</b> Вы читаете на своём языке, а черновик ответа автоматически пишется на языке отправителя.",
        "🔒 Privacy is the starting point": "🔒 Конфиденциальность — отправная точка",
        "Your letters stay your business.": "Ваши письма остаются вашим делом.",
        "Official mail is personal. We built easli so you never have to hand over more than you need to.":
            "Официальная почта — личное. easli создан так, чтобы вы никогда не передавали больше, чем нужно.",
        "No account. No email.": "Без аккаунта. Без email.",
        "No name, no profile. easli works anonymously.": "Без имени, без профиля. easli работает анонимно.",
        "Hosted in Europe.": "Размещён в Европе.",
        "We don't keep your letters.": "Мы не храним ваши письма.",
        "The photo isn't stored long-term. Only the plain-language explanation stays.":
            "Фото не хранится долго. Остаётся только объяснение простыми словами.",
        "Delete everything, any time.": "Удалите всё в любой момент.",
        "One tap in settings and your history is gone. For good.":
            "Один тап в настройках — и история исчезает. Навсегда.",
        "Read the full privacy policy →": "Читать полную политику конфиденциальности →",
        "Who it's for": "Для кого",
        "For anyone who needs clarity.": "Для всех, кому нужна ясность.",
        "easli is built for people who don't deal with official letters every day.":
            "easli создан для тех, кто не каждый день разбирается с официальными письмами.",
        "New in Europe": "Новые в Европе",
        "The language isn't home yet. But the authorities already are.":
            "Язык ещё не родной. А ведомства уже да.",
        "Students": "Студенты",
        "Rent, tuition, insurance. A new letter every week.":
            "Аренда, плата за обучение, страховка. Новое письмо каждую неделю.",
        "Families": "Семьи",
        "Multiple authorities, multiple deadlines. Someone has to keep track.":
            "Несколько ведомств, несколько сроков. Кто-то должен следить.",
        "Older people": "Пожилые",
        "Small print, big impact. easli reads loud and explains softly.":
            "Мелкий шрифт, большое влияние. easli читает громко и объясняет мягко.",
        "✨ Coming soon": "✨ Уже доступно",
        "Stop the uneasy feeling": "Покончите с тревогой",
        "at the mailbox.": "у почтового ящика.",
        "easli launches shortly. Drop us a note and we'll let you know the moment it's live.":
            "easli уже в App Store. Версия для Android скоро.",
        "Imprint": "Импрессум",
        "Contact": "Контакты",
        "Made in the EU": "Сделано в ЕС",
        "Lampertheim, Germany": "Лампертхайм, Германия",
    },

    # ===================== zh-Hans (简体中文) =====================
    "zh-Hans": {
        "Finally understand what your letter means": "终于看懂信里写的是什么",
        "One photo is enough. easli explains any official letter in your language, shows you deadlines and helps you reply. 25+ languages. EU-hosted. GDPR-compliant.":
            "一张照片就够了。easli 用您的语言解释任何官方信件,显示截止日期,并帮您撰写回复。25+ 种语言。欧盟托管。符合 GDPR。",
        "One photo is enough. easli explains any official letter in your language.":
            "一张照片就够了。easli 用您的语言解释任何官方信件。",
        "Skip to content": "跳到内容",
        "easli home": "easli 首页",
        "How it works": "工作原理",
        "Languages": "语言",
        "Privacy": "隐私",
        "Support": "支持",
        "Switch language": "切换语言",
        "Master your paperwork.": "掌握您的文书工作。",
        "Any language. Across Europe.": "任何语言。遍布欧洲。",
        "Rental contract in Madrid, electricity bill in Berlin, doctor's letter in Rome — easli explains any document in seconds, warns about scams, and drafts the right reply.":
            "马德里的租赁合同、柏林的电费账单、罗马的医生信件——easli 几秒内解释任何文件,警告诈骗,并草拟正确的回复。",
        "No account needed": "无需账户",
        "EU-hosted": "欧盟托管",
        "GDPR-compliant": "符合 GDPR",
        "Federal Employment Agency · 12345": "联邦就业局 · 12345",
        "URGENT": "紧急",
        "2 WEEKS": "2 周",
        "Request for cooperation": "协助请求",
        "Analysis": "分析",
        "● Important · Deadline": "● 重要 · 截止",
        "Submit missing documents": "提交缺失文件",
        "Federal Employment Agency": "联邦就业局",
        "Due in": "剩余",
        "14 days": "14 天",
        "Reply on time.": "及时回复。",
        "Draft a reply": "草拟回复",
        "Sound familiar?": "听起来熟悉?",
        "Three seconds after opening.": "拆开三秒后。",
        "A letter lands on the table. And your head starts running the same loop.":
            "一封信落在桌上。脑子里又开始转那个老圈子。",
        "„Why is the authority writing to me?\"": "「为什么当局给我写信?」",
        "The tone sounds serious. The words are long. And you don't really get what it's about.":
            "语气严肃。词句冗长。您并不真正明白是关于什么的。",
        "„How much time do I have?\"": "「我有多少时间?」",
        "There's a deadline somewhere. Maybe important, maybe not. You can't quite tell.":
            "某处有截止日期。也许重要,也许不。您说不准。",
        "„And what am I supposed to do?\"": "「那我该做什么?」",
        "Submit something? Write a reply? Wait it out? You just don't want to get it wrong.":
            "提交什么?写回复?等等看?您只是不想搞错。",
        "Before · After": "之前 · 之后",
        "From bureaucratic jargon": "从官僚术语",
        "to one clear sentence": "到一句清晰的话",
        "easli doesn't just translate your letter. It explains what actually matters.":
            "easli 不只是翻译您的信件。它解释真正重要的内容。",
        "Original": "原文",
        "12 letter types · one tool": "12 种信件类型 · 一个工具",
        "easli is": "easli",
        "not just for the tax office": "不只是用于税务局",
        "We cover everything that lands in your mailbox. Authorities, banks, landlords, insurers, doctors, courts — every letter, one clear answer.":
            "我们涵盖所有落入您信箱的东西。当局、银行、房东、保险公司、医生、法院——每封信,一个清晰答案。",
        "Rent & Housing": "租房与住房",
        "Leases, utility bills, dunning, evictions": "租约、水电账单、催款、驱逐",
        "Electricity, Gas, Water": "电、燃气、水",
        "Utility statements, prepayments, plan switches": "公用事业账单、预付款、套餐变更",
        "Banking & Taxes": "银行与税务",
        "Tax notices, statements, loans": "税务通知、对账单、贷款",
        "Telecom & Subscriptions": "电信与订阅",
        "Mobile, internet, broadcasting fees": "手机、网络、广播费",
        "Courts & Lawyers": "法院与律师",
        "Payment orders, summons, attachments": "支付令、传票、扣押",
        "Government & Offices": "政府与机关",
        "Immigration, employment, fines": "移民、就业、罚款",
        "Insurance": "保险",
        "Health, liability, car, pension": "健康、责任、汽车、养老",
        "Work & Contracts": "工作与合同",
        "Payslips, employer letters": "工资单、雇主信件",
        "Healthcare": "医疗",
        "Doctor's letters, hospital bills, prescriptions": "医生信件、医院账单、处方",
        "Education": "教育",
        "School, university, kindergarten, grants": "学校、大学、幼儿园、助学金",
        "Parcels & Other": "包裹与其他",
        "Deliveries, ads, personal mail": "投递、广告、私人邮件",
        "Scam Shield": "诈骗防护",
        "We warn when IBANs or senders look off": "当 IBAN 或发件人可疑时,我们会警告",
        "Done in two minutes.": "两分钟搞定。",
        "No account. No setup. Open the app and point the camera.":
            "无需账户。无需设置。打开应用,对准相机。",
        "Take a photo": "拍照",
        "Snap the letter with the camera or pick a PDF from your files. Multiple pages work too.":
            "用相机拍下信件,或从文件中选择 PDF。也支持多页。",
        "Read the explanation": "阅读说明",
        "You get the essence of the letter in your language. What it's about. How urgent. What to do next.":
            "您用自己的语言获得信件的核心。关于什么。多紧急。下一步做什么。",
        "Send a reply": "发送回复",
        "Accept a draft reply, adjust it, copy it. The reply is automatically in the sender's language.":
            "接受回复草稿,调整,复制。回复自动使用发件人的语言。",
        "🌍 25+ languages": "🌍 25+ 种语言",
        "Your letter. In": "您的信件。用",
        "Read every letter in the language you actually think in. No matter where it comes from.":
            "用您真正思考的语言阅读每封信。无论它来自哪里。",
        "✍️ <b>Smart twist:</b> You read in your own language, but the reply draft is automatically written in the sender's language.":
            "✍️ <b>智能巧思:</b> 您用自己的语言阅读,但回复草稿自动使用发件人的语言撰写。",
        "🔒 Privacy is the starting point": "🔒 隐私是出发点",
        "Your letters stay your business.": "您的信件依然是您的事。",
        "Official mail is personal. We built easli so you never have to hand over more than you need to.":
            "官方邮件是私人的。我们打造 easli,让您永远不必交出比需要更多的东西。",
        "No account. No email.": "无账户。无邮件。",
        "No name, no profile. easli works anonymously.": "无姓名,无资料。easli 匿名工作。",
        "Hosted in Europe.": "在欧洲托管。",
        "We don't keep your letters.": "我们不保留您的信件。",
        "The photo isn't stored long-term. Only the plain-language explanation stays.":
            "照片不长期存储。只保留通俗易懂的说明。",
        "Delete everything, any time.": "随时删除一切。",
        "One tap in settings and your history is gone. For good.":
            "在设置中轻按一下,您的历史就消失了。永远地。",
        "Read the full privacy policy →": "阅读完整隐私政策 →",
        "Who it's for": "适合谁",
        "For anyone who needs clarity.": "适合所有需要清晰的人。",
        "easli is built for people who don't deal with official letters every day.":
            "easli 为不每天处理官方信件的人而打造。",
        "New in Europe": "初到欧洲",
        "The language isn't home yet. But the authorities already are.":
            "语言还不熟。但当局已经在了。",
        "Students": "学生",
        "Rent, tuition, insurance. A new letter every week.":
            "房租、学费、保险。每周一封新信。",
        "Families": "家庭",
        "Multiple authorities, multiple deadlines. Someone has to keep track.":
            "多个机关,多个截止。总得有人跟进。",
        "Older people": "年长者",
        "Small print, big impact. easli reads loud and explains softly.":
            "小字体,大影响。easli 大声朗读,温柔解释。",
        "✨ Coming soon": "✨ 现已上线",
        "Stop the uneasy feeling": "告别信箱旁的",
        "at the mailbox.": "不安感。",
        "easli launches shortly. Drop us a note and we'll let you know the moment it's live.":
            "easli 现已在 App Store。Android 版本即将推出。",
        "Imprint": "版权信息",
        "Contact": "联系",
        "Made in the EU": "欧盟制造",
        "Lampertheim, Germany": "兰佩特海姆,德国",
    },

    # ===================== vi (Tiếng Việt) =====================
    "vi": {
        "Finally understand what your letter means": "Cuối cùng cũng hiểu thư của bạn nói gì",
        "One photo is enough. easli explains any official letter in your language, shows you deadlines and helps you reply. 25+ languages. EU-hosted. GDPR-compliant.":
            "Một bức ảnh là đủ. easli giải thích mọi thư hành chính bằng ngôn ngữ của bạn, cho biết hạn chót và giúp bạn trả lời. 25+ ngôn ngữ. Lưu trữ tại EU. Tuân thủ GDPR.",
        "One photo is enough. easli explains any official letter in your language.":
            "Một bức ảnh là đủ. easli giải thích mọi thư hành chính bằng ngôn ngữ của bạn.",
        "Skip to content": "Bỏ qua đến nội dung",
        "easli home": "easli trang chủ",
        "How it works": "Cách hoạt động",
        "Languages": "Ngôn ngữ",
        "Privacy": "Quyền riêng tư",
        "Support": "Hỗ trợ",
        "Switch language": "Đổi ngôn ngữ",
        "Master your paperwork.": "Làm chủ giấy tờ của bạn.",
        "Any language. Across Europe.": "Mọi ngôn ngữ. Khắp Châu Âu.",
        "Rental contract in Madrid, electricity bill in Berlin, doctor's letter in Rome — easli explains any document in seconds, warns about scams, and drafts the right reply.":
            "Hợp đồng thuê nhà ở Madrid, hóa đơn điện ở Berlin, thư bác sĩ ở Rome — easli giải thích mọi tài liệu trong vài giây, cảnh báo lừa đảo và soạn câu trả lời phù hợp.",
        "No account needed": "Không cần tài khoản",
        "EU-hosted": "Lưu trữ tại EU",
        "GDPR-compliant": "Tuân thủ GDPR",
        "Federal Employment Agency · 12345": "Sở Lao động · 12345",
        "URGENT": "KHẨN",
        "2 WEEKS": "2 TUẦN",
        "Request for cooperation": "Yêu cầu hợp tác",
        "Analysis": "Phân tích",
        "● Important · Deadline": "● Quan trọng · Hạn chót",
        "Submit missing documents": "Nộp giấy tờ còn thiếu",
        "Federal Employment Agency": "Sở Lao động",
        "Due in": "Còn",
        "14 days": "14 ngày",
        "Reply on time.": "Trả lời đúng hạn.",
        "Draft a reply": "Soạn câu trả lời",
        "Sound familiar?": "Nghe quen không?",
        "Three seconds after opening.": "Ba giây sau khi mở.",
        "A letter lands on the table. And your head starts running the same loop.":
            "Một bức thư rơi xuống bàn. Và đầu bạn lại chạy cùng một vòng lặp.",
        "„Why is the authority writing to me?\"": "„Tại sao cơ quan lại viết cho mình?\"",
        "The tone sounds serious. The words are long. And you don't really get what it's about.":
            "Giọng văn nghiêm túc. Từ ngữ dài dòng. Và bạn không thực sự hiểu nó nói về gì.",
        "„How much time do I have?\"": "„Mình còn bao nhiêu thời gian?\"",
        "There's a deadline somewhere. Maybe important, maybe not. You can't quite tell.":
            "Có một hạn chót ở đâu đó. Có thể quan trọng, có thể không. Khó nói được.",
        "„And what am I supposed to do?\"": "„Và mình phải làm gì?\"",
        "Submit something? Write a reply? Wait it out? You just don't want to get it wrong.":
            "Nộp gì đó? Viết trả lời? Chờ xem? Bạn chỉ không muốn làm sai.",
        "Before · After": "Trước · Sau",
        "From bureaucratic jargon": "Từ ngôn ngữ hành chính",
        "to one clear sentence": "thành một câu rõ ràng",
        "easli doesn't just translate your letter. It explains what actually matters.":
            "easli không chỉ dịch thư của bạn. Nó giải thích điều thực sự quan trọng.",
        "Original": "Bản gốc",
        "12 letter types · one tool": "12 loại thư · một công cụ",
        "easli is": "easli",
        "not just for the tax office": "không chỉ dành cho cơ quan thuế",
        "We cover everything that lands in your mailbox. Authorities, banks, landlords, insurers, doctors, courts — every letter, one clear answer.":
            "Chúng tôi bao quát mọi thứ rơi vào hộp thư của bạn. Cơ quan, ngân hàng, chủ nhà, bảo hiểm, bác sĩ, tòa án — mỗi thư, một câu trả lời rõ ràng.",
        "Rent & Housing": "Thuê nhà & Nhà ở",
        "Leases, utility bills, dunning, evictions": "Hợp đồng thuê, hóa đơn, đòi nợ, trục xuất",
        "Electricity, Gas, Water": "Điện, Gas, Nước",
        "Utility statements, prepayments, plan switches": "Hóa đơn, trả trước, đổi gói",
        "Banking & Taxes": "Ngân hàng & Thuế",
        "Tax notices, statements, loans": "Thông báo thuế, sao kê, khoản vay",
        "Telecom & Subscriptions": "Viễn thông & Đăng ký",
        "Mobile, internet, broadcasting fees": "Di động, internet, phí truyền hình",
        "Courts & Lawyers": "Tòa án & Luật sư",
        "Payment orders, summons, attachments": "Lệnh thanh toán, triệu tập, kê biên",
        "Government & Offices": "Chính phủ & Cơ quan",
        "Immigration, employment, fines": "Di trú, lao động, phạt",
        "Insurance": "Bảo hiểm",
        "Health, liability, car, pension": "Sức khỏe, trách nhiệm, xe, hưu trí",
        "Work & Contracts": "Công việc & Hợp đồng",
        "Payslips, employer letters": "Phiếu lương, thư của chủ lao động",
        "Healthcare": "Y tế",
        "Doctor's letters, hospital bills, prescriptions": "Thư bác sĩ, hóa đơn bệnh viện, đơn thuốc",
        "Education": "Giáo dục",
        "School, university, kindergarten, grants": "Trường học, đại học, mẫu giáo, học bổng",
        "Parcels & Other": "Bưu kiện & Khác",
        "Deliveries, ads, personal mail": "Giao hàng, quảng cáo, thư cá nhân",
        "Scam Shield": "Lá chắn lừa đảo",
        "We warn when IBANs or senders look off": "Chúng tôi cảnh báo khi IBAN hoặc người gửi đáng ngờ",
        "Done in two minutes.": "Xong trong hai phút.",
        "No account. No setup. Open the app and point the camera.":
            "Không tài khoản. Không cài đặt. Mở ứng dụng và hướng camera.",
        "Take a photo": "Chụp ảnh",
        "Snap the letter with the camera or pick a PDF from your files. Multiple pages work too.":
            "Chụp ảnh bức thư hoặc chọn PDF từ tệp. Nhiều trang cũng được.",
        "Read the explanation": "Đọc lời giải thích",
        "You get the essence of the letter in your language. What it's about. How urgent. What to do next.":
            "Bạn nhận được phần cốt lõi của thư bằng ngôn ngữ của mình. Về cái gì. Khẩn cấp ra sao. Làm gì tiếp.",
        "Send a reply": "Gửi trả lời",
        "Accept a draft reply, adjust it, copy it. The reply is automatically in the sender's language.":
            "Chấp nhận bản nháp, chỉnh sửa, sao chép. Câu trả lời tự động bằng ngôn ngữ của người gửi.",
        "🌍 25+ languages": "🌍 25+ ngôn ngữ",
        "Your letter. In": "Thư của bạn. Bằng",
        "Read every letter in the language you actually think in. No matter where it comes from.":
            "Đọc mọi bức thư bằng ngôn ngữ bạn thật sự suy nghĩ. Dù nó đến từ đâu.",
        "✍️ <b>Smart twist:</b> You read in your own language, but the reply draft is automatically written in the sender's language.":
            "✍️ <b>Điểm thông minh:</b> Bạn đọc bằng ngôn ngữ của mình, nhưng bản nháp trả lời tự động viết bằng ngôn ngữ của người gửi.",
        "🔒 Privacy is the starting point": "🔒 Quyền riêng tư là điểm khởi đầu",
        "Your letters stay your business.": "Thư của bạn vẫn là việc của bạn.",
        "Official mail is personal. We built easli so you never have to hand over more than you need to.":
            "Thư hành chính là chuyện cá nhân. Chúng tôi xây dựng easli để bạn không bao giờ phải giao nộp nhiều hơn mức cần thiết.",
        "No account. No email.": "Không tài khoản. Không email.",
        "No name, no profile. easli works anonymously.": "Không tên, không hồ sơ. easli hoạt động ẩn danh.",
        "Hosted in Europe.": "Lưu trữ tại Châu Âu.",
        "We don't keep your letters.": "Chúng tôi không giữ lại thư của bạn.",
        "The photo isn't stored long-term. Only the plain-language explanation stays.":
            "Ảnh không được lưu lâu dài. Chỉ lời giải thích đơn giản được giữ lại.",
        "Delete everything, any time.": "Xóa mọi thứ, bất cứ lúc nào.",
        "One tap in settings and your history is gone. For good.":
            "Một chạm trong cài đặt và lịch sử của bạn biến mất. Vĩnh viễn.",
        "Read the full privacy policy →": "Đọc chính sách bảo mật đầy đủ →",
        "Who it's for": "Dành cho ai",
        "For anyone who needs clarity.": "Cho bất kỳ ai cần sự rõ ràng.",
        "easli is built for people who don't deal with official letters every day.":
            "easli được xây dựng cho những người không xử lý thư hành chính mỗi ngày.",
        "New in Europe": "Mới đến Châu Âu",
        "The language isn't home yet. But the authorities already are.":
            "Ngôn ngữ chưa phải nhà. Nhưng các cơ quan đã rồi.",
        "Students": "Sinh viên",
        "Rent, tuition, insurance. A new letter every week.":
            "Tiền thuê, học phí, bảo hiểm. Một bức thư mới mỗi tuần.",
        "Families": "Gia đình",
        "Multiple authorities, multiple deadlines. Someone has to keep track.":
            "Nhiều cơ quan, nhiều hạn chót. Phải có ai đó theo dõi.",
        "Older people": "Người lớn tuổi",
        "Small print, big impact. easli reads loud and explains softly.":
            "Chữ nhỏ, tác động lớn. easli đọc to và giải thích nhẹ nhàng.",
        "✨ Coming soon": "✨ Đã ra mắt",
        "Stop the uneasy feeling": "Chấm dứt cảm giác bất an",
        "at the mailbox.": "tại hộp thư.",
        "easli launches shortly. Drop us a note and we'll let you know the moment it's live.":
            "easli đã có trên App Store. Phiên bản Android sắp ra mắt.",
        "Imprint": "Thông tin pháp lý",
        "Contact": "Liên hệ",
        "Made in the EU": "Sản xuất tại EU",
        "Lampertheim, Germany": "Lampertheim, Đức",
    },
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
LANG_HTML_ATTR = {"de": "de", "en": "en", "fr": "fr", "es": "es", "it": "it", "pl": "pl",
                  "nl": "nl", "tr": "tr", "ru": "ru", "zh-Hans": "zh-Hans", "vi": "vi"}


def build_hreflang_block(current_lang: str) -> str:
    """Build the canonical + hreflang link block for a locale."""
    lines = []
    cur_url = f"https://easli.app{dict((c,u) for c,u,_,_ in LOCALES)[current_lang]}"
    lines.append(f'  <link rel="canonical" href="{cur_url}">')
    for code, url, _, _ in LOCALES:
        lines.append(f'  <link rel="alternate" hreflang="{LANG_HTML_ATTR[code]}" href="https://easli.app{url}">')
    lines.append('  <link rel="alternate" hreflang="x-default" href="https://easli.app/en/">')
    return "\n".join(lines)


def build_lang_switch(current_lang: str) -> str:
    """Build the <nav class='lang-switch'> block with all 11 locales."""
    items = []
    for code, url, title, label in LOCALES:
        attr = ' aria-current="page"' if code == current_lang else ""
        items.append(f'        <a href="{url}"{attr} title="{title}">{label}</a>')
    return '      <nav class="lang-switch" aria-label="Switch language">\n' + "\n".join(items) + "\n      </nav>"


# ---------------------------------------------------------------------------
# PATCH a single locale file in place (L1+L2 patches)
# ---------------------------------------------------------------------------
def patch_locale(path: Path, lang: str):
    html = path.read_text()

    # ---- 1. App Store button: replace href + class + label + add target/rel
    app_dl_text, _coming_prefix, app_aria, _gp_aria = APPSTORE_LABEL[lang]

    # Hero App Store button
    html = re.sub(
        r'<a href="#" class="btn-store disabled" aria-label="[^"]*App Store[^"]*">\s*'
        r'(<svg[^<]*<path d="M17\.05.*?</svg>)\s*'
        r'<span><small>[^<]*</small><strong>App Store</strong></span>\s*</a>',
        f'<a href="{APPSTORE_URL}" class="btn-store" target="_blank" rel="noopener" aria-label="{app_aria}">\n              \\1\n              <span><small>{app_dl_text}</small><strong>App Store</strong></span>\n            </a>',
        html,
        flags=re.DOTALL,
    )

    # ---- 2. "Coming soon" eyebrow → live
    html = re.sub(
        r'<span class="eyebrow"><span class="dot"></span>[^<]*</span>',
        f'<span class="eyebrow"><span class="dot"></span> {EYEBROW_LIVE[lang]}</span>',
        html,
        count=1,  # only the hero one; the final-CTA section uses different markup
    )

    # ---- 3. Frankfurt → Paris fix in privacy point
    html = re.sub(
        r'<span>(Unsere Server stehen in Frankfurt\. Deine Daten verlassen die EU nicht\.|'
        r'Our servers sit in Frankfurt\. Your data stays inside the EU\.|'
        r'Nos serveurs sont [^<]*?Frankfort[^<]*?\.|'
        r'Nuestros servidores [^<]*?Fr[áa]ncfort[^<]*?\.|'
        r'I nostri server sono a Francoforte\. I tuoi dati non lasciano l\'UE\.|'
        r'Nasze serwery znajdują się we Frankfurcie\. Twoje dane nie opuszczają UE\.)</span>',
        f'<span>{SERVER_LOCATION[lang]}</span>',
        html,
    )
    # Also catch generic patterns just in case
    html = re.sub(r'Frankfurt(\s*\(Germany\))?\.', "Paris (Mistral AI, France).", html)
    html = re.sub(r'Frankfort\.', "Paris (Mistral AI, France).", html)
    html = re.sub(r'Francoforte\.', "Parigi (Mistral AI, Francia).", html)
    html = re.sub(r'Fráncfort\.', "París (Mistral AI, Francia).", html)
    html = re.sub(r'Frankfurcie\.', "Paryżu (Mistral AI, Francja).", html)

    # ---- 4. Replace hreflang block
    # Find canonical + all hreflang lines and replace
    hreflang_block = build_hreflang_block(lang)
    html = re.sub(
        r'  <link rel="canonical"[^>]*>\s*(?:  <link rel="alternate"[^>]*>\s*)+',
        hreflang_block + "\n",
        html,
    )

    # ---- 5. Replace lang-switch nav
    lang_switch = build_lang_switch(lang)
    html = re.sub(
        r'      <nav class="lang-switch"[^>]*>.*?</nav>',
        lang_switch,
        html,
        flags=re.DOTALL,
    )

    path.write_text(html)
    print(f"  patched: {path.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Generate a NEW locale file from en/index.html as canonical source
# ---------------------------------------------------------------------------
def generate_new_locale(lang: str):
    src = (BASE / "en" / "index.html").read_text()
    out_path = BASE / lang / "index.html"
    out_path.parent.mkdir(exist_ok=True)

    # 1. swap html lang attribute
    src = src.replace('<html lang="en">', f'<html lang="{LANG_HTML_ATTR[lang]}">', 1)

    # 2. swap og:url + brand link href
    cur_url_path = dict((c, u) for c, u, _, _ in LOCALES)[lang]
    src = src.replace('https://easli.app/en/', f'https://easli.app{cur_url_path}')
    src = src.replace('href="/en/"', f'href="{cur_url_path}"')

    # 3. apply string-by-string translations
    t = T[lang]
    for en_str, local_str in sorted(t.items(), key=lambda kv: -len(kv[0])):
        # Replace plain occurrences (case-sensitive, full string)
        src = src.replace(en_str, local_str)

    # 4. write file
    out_path.write_text(src)
    print(f"  generated: {out_path.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("easli 2.0 landing migration")
    print("=" * 70)

    # --- Phase 2: generate 5 new locales FIRST (before patching)
    print("\nPhase 2 — generate new locales:")
    for new_lang in ("nl", "tr", "ru", "zh-Hans", "vi"):
        generate_new_locale(new_lang)

    # --- Phase 1: patch all 11 locale files
    print("\nPhase 1 — patch all locale files (existing + new):")
    for code, url, _, _ in LOCALES:
        if code == "de":
            p = BASE / "index.html"
        else:
            subdir = url.strip("/")
            p = BASE / subdir / "index.html"
        if not p.exists():
            print(f"  !! missing: {p}")
            continue
        patch_locale(p, code)

    print("\n" + "=" * 70)
    print("Done. Verify with:")
    print("  ls /app/landing/{nl,tr,ru,zh-Hans,vi}/index.html")
    print("  grep -c 'apps.apple.com/app/easli' /app/landing/**/index.html")
    print("=" * 70)


if __name__ == "__main__":
    main()
