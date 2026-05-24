"""easli — formal salutations and sign-offs per reply language.

Used by the reply-generation prompt to enforce consistent, language-
appropriate openers and closers. Each entry carries:

  formal_unknown : opener when the recipient name is not known
                   (e.g. "Sehr geehrte Damen und Herren,").
  formal_named   : opener when a `contact_person` from
                   `extracted_entities` is known. Use the `{nachname}`
                   placeholder; the analyser substitutes the actual
                   last name at runtime.
  sign_off       : standard polite closing (one line, NO trailing
                   comma in some languages — see entries).
  sign_off_formal: optional more formal closing used for authorities /
                   legal correspondence. Falls back to `sign_off` when
                   not present.

Key = ISO-639-1 code (BCP-47 for Simplified Chinese). Fallback is `en`.

Phase 6a defines the data; Phase 6d injects them into the reply prompt.
"""

from __future__ import annotations

from typing import TypedDict


class Salutation(TypedDict, total=False):
    formal_unknown: str
    formal_named: str
    sign_off: str
    sign_off_formal: str


REPLY_SALUTATIONS: dict[str, Salutation] = {
    # ---- DACH ----
    "de": {
        "formal_unknown": "Sehr geehrte Damen und Herren,",
        "formal_named": "Sehr geehrte/r Frau/Herr {nachname},",
        "sign_off": "Mit freundlichen Grüßen",
        "sign_off_formal": "Mit freundlichen Grüßen",
    },

    # ---- Romance ----
    "fr": {
        "formal_unknown": "Madame, Monsieur,",
        "formal_named": "Madame {nachname}, / Monsieur {nachname},",
        "sign_off": "Cordialement,",
        "sign_off_formal": (
            "Je vous prie d'agréer, Madame, Monsieur, "
            "l'expression de mes salutations distinguées."
        ),
    },
    "es": {
        "formal_unknown": "Estimados señores:",
        "formal_named": "Estimado/a Sr./Sra. {nachname}:",
        "sign_off": "Atentamente,",
        "sign_off_formal": "Le saluda atentamente,",
    },
    "it": {
        "formal_unknown": "Spettabile,",
        "formal_named": "Egregio/a Sig./Sig.ra {nachname},",
        "sign_off": "Cordiali saluti,",
        "sign_off_formal": "Distinti saluti,",
    },
    "pt": {
        "formal_unknown": "Exmos. Senhores,",
        "formal_named": "Exmo./a Sr./Sra. {nachname},",
        "sign_off": "Com os melhores cumprimentos,",
    },
    "ro": {
        "formal_unknown": "Stimate Doamne, Stimați Domni,",
        "formal_named": "Stimată/Stimate {nachname},",
        "sign_off": "Cu stimă,",
    },

    # ---- Benelux ----
    "nl": {
        "formal_unknown": "Geachte heer/mevrouw,",
        "formal_named": "Geachte heer/mevrouw {nachname},",
        "sign_off": "Met vriendelijke groet,",
        "sign_off_formal": "Hoogachtend,",
    },

    # ---- English ----
    "en": {
        "formal_unknown": "Dear Sir or Madam,",
        "formal_named": "Dear Mr./Ms. {nachname},",
        "sign_off": "Kind regards,",
        "sign_off_formal": "Yours faithfully,",
    },

    # ---- CEE / Slavic ----
    "pl": {
        "formal_unknown": "Szanowni Państwo,",
        "formal_named": "Szanowny Panie {nachname}, / Szanowna Pani {nachname},",
        "sign_off": "Z poważaniem,",
    },
    "cs": {
        "formal_unknown": "Vážení,",
        "formal_named": "Vážený pane {nachname}, / Vážená paní {nachname},",
        "sign_off": "S pozdravem,",
    },
    "sk": {
        "formal_unknown": "Vážení,",
        "formal_named": "Vážený pane {nachname}, / Vážená pani {nachname},",
        "sign_off": "S pozdravom,",
    },
    "sl": {
        "formal_unknown": "Spoštovani,",
        "formal_named": "Spoštovani gospod/gospa {nachname},",
        "sign_off": "Lep pozdrav,",
    },
    "hr": {
        "formal_unknown": "Poštovani,",
        "formal_named": "Poštovani gospodine/gospođo {nachname},",
        "sign_off": "S poštovanjem,",
    },
    "sr": {
        "formal_unknown": "Поштовани,",
        "sign_off": "С поштовањем,",
    },
    "bg": {
        "formal_unknown": "Уважаеми дами и господа,",
        "sign_off": "С уважение,",
    },
    "uk": {
        "formal_unknown": "Шановні панове,",
        "sign_off": "З повагою,",
    },
    "ru": {
        "formal_unknown": "Уважаемые дамы и господа,",
        "sign_off": "С уважением,",
    },

    # ---- Baltic ----
    "lt": {
        "formal_unknown": "Gerbiamieji,",
        "sign_off": "Pagarbiai,",
    },
    "lv": {
        "formal_unknown": "Godātie kungi un dāmas,",
        "sign_off": "Ar cieņu,",
    },
    "et": {
        "formal_unknown": "Lugupeetud,",
        "sign_off": "Lugupidamisega,",
    },

    # ---- Nordic ----
    "sv": {
        "formal_unknown": "Hej,",  # Swedish dropped formal address decades ago
        "formal_named": "Hej {nachname},",
        "sign_off": "Vänliga hälsningar,",
    },
    "da": {
        "formal_unknown": "Kære,",
        "sign_off": "Venlig hilsen,",
    },
    "no": {
        "formal_unknown": "Hei,",
        "sign_off": "Vennlig hilsen,",
    },
    "fi": {
        "formal_unknown": "Hyvä vastaanottaja,",
        "sign_off": "Ystävällisin terveisin,",
    },
    "is": {
        "formal_unknown": "Kæri viðtakandi,",
        "sign_off": "Með kveðju,",
    },

    # ---- Greek ----
    "el": {
        "formal_unknown": "Αξιότιμοι κύριοι,",
        "sign_off": "Με εκτίμηση,",
    },

    # ---- Hungarian ----
    "hu": {
        "formal_unknown": "Tisztelt Hölgyem/Uram!",
        "sign_off": "Üdvözlettel,",
    },

    # ---- Turkish / Arabic / Hindi / Chinese / Vietnamese ----
    "tr": {
        "formal_unknown": "Sayın Yetkili,",
        "formal_named": "Sayın {nachname} Bey/Hanım,",
        "sign_off": "Saygılarımla,",
    },
    "ar": {
        "formal_unknown": "إلى السيدة/السيد المحترم/ة،",
        "sign_off": "مع فائق الاحترام،",
    },
    "hi": {
        "formal_unknown": "माननीय महोदय/महोदया,",
        "sign_off": "सस्नेह,",
    },
    "zh-hans": {
        "formal_unknown": "尊敬的先生/女士：",
        "sign_off": "此致敬礼",
    },
    "vi": {
        "formal_unknown": "Kính gửi Quý Ông/Bà,",
        "sign_off": "Trân trọng,",
    },
}


DEFAULT_FALLBACK_SALUTATION: Salutation = REPLY_SALUTATIONS["en"]


def salutation_for(lang_code: str) -> Salutation:
    """Return the salutation pack for `lang_code`, falling back to English.

    Lookup is case-insensitive and tolerates a stray BCP-47 region tag
    (e.g. 'de-AT' -> 'de'). Returns the English fallback rather than None
    so call sites never have to guard against missing entries.
    """
    if not lang_code:
        return DEFAULT_FALLBACK_SALUTATION
    key = lang_code.strip().lower()
    if key in REPLY_SALUTATIONS:
        return REPLY_SALUTATIONS[key]
    base = key.split("-", 1)[0]
    return REPLY_SALUTATIONS.get(base, DEFAULT_FALLBACK_SALUTATION)
