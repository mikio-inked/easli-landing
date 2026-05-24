"""easli — European country packs.

Per-country knowledge bundles used by the analyser & reply prompts since
Phase 6 of the backend refactor. Each pack carries the authoritative names,
document-type vocabulary, scam patterns and metadata for one country so
Mistral can:
  1. Anchor `detected_country_code` with high confidence from the sender.
  2. Pick the right `category` for country-specific doc types
     (e.g. "Mahnbescheid" → court, "Avis d'imposition" → tax).
  3. Flag country-specific scam patterns.

Keys are ISO 3166-1 alpha-2. Languages are ISO-639-1.
ADD a country here whenever we expand into a new market — a single dict
is enough to keep the analyser, reply, and translate prompts consistent.

This file is data-only — zero Python logic. Phases 6c (analyser country
detection), 6e (regional scam), and 6f (document-type anchors) will
import and inject these into the relevant prompts.
"""

from __future__ import annotations

from typing import TypedDict


class CountryAuthorities(TypedDict, total=False):
    tax: list[str]
    health_insurance: list[str]
    social: list[str]
    court: list[str]
    municipality: list[str]
    education: list[str]
    employment: list[str]
    pension: list[str]


class CountryPack(TypedDict, total=False):
    name: str                       # English country name
    language_codes: list[str]       # ISO-639-1 codes spoken officially
    currency: str                   # ISO 4217
    iban_prefix: str                # 2-letter IBAN country code
    authorities: CountryAuthorities
    specific_doc_types: list[str]   # vocabulary anchors for category detection
    scam_patterns: list[str]        # regional phishing/scam descriptions
    polite_form_pronoun: str        # how to address the recipient formally


COUNTRY_PACKS: dict[str, CountryPack] = {
    # ---------------------------------------------------------------- DACH
    "DE": {
        "name": "Germany",
        "language_codes": ["de"],
        "currency": "EUR",
        "iban_prefix": "DE",
        "polite_form_pronoun": "Sie",
        "authorities": {
            "tax": [
                "Finanzamt", "Bundeszentralamt für Steuern", "BZSt",
                "Hauptzollamt",
            ],
            "health_insurance": [
                "AOK", "TK", "Techniker Krankenkasse", "Barmer", "DAK",
                "IKK", "BKK", "Krankenkasse", "GKV", "PKV",
            ],
            "social": [
                "Bundesagentur für Arbeit", "Agentur für Arbeit", "Jobcenter",
                "Familienkasse", "Sozialamt",
            ],
            "pension": [
                "Deutsche Rentenversicherung", "DRV", "Versorgungsamt",
            ],
            "court": [
                "Amtsgericht", "Landgericht", "Oberlandesgericht",
                "Verwaltungsgericht", "Sozialgericht", "Arbeitsgericht",
                "Finanzgericht", "Mahngericht", "Gerichtsvollzieher",
            ],
            "municipality": [
                "Bürgeramt", "Einwohnermeldeamt", "Standesamt", "Ordnungsamt",
                "Stadtverwaltung", "Bezirksamt",
            ],
            "education": [
                "BAföG", "Studierendenwerk", "Schulamt",
            ],
        },
        "specific_doc_types": [
            "Mahnung", "Zahlungserinnerung", "Mahnbescheid",
            "Vollstreckungsbescheid", "Pfändungs- und Überweisungsbeschluss",
            "Steuerbescheid", "Einkommensteuerbescheid", "Umsatzsteuerbescheid",
            "Bußgeldbescheid", "Verwarngeld",
            "Kostenbescheid", "Gebührenbescheid", "Beitragsbescheid",
            "Kündigung", "Abmahnung",
        ],
        "scam_patterns": [
            "Anruf angeblich vom Bundeszentralamt für Steuern (BZSt) mit "
            "Festnahme-Drohung bei ausstehender Steuerzahlung.",
            "SMS angeblich von DHL/Hermes/DPD mit Phishing-Link für "
            "angebliche Zollgebühr oder Paket-Umleitung.",
            "Schockanruf 'Mama/Papa, ich hatte einen Unfall, brauche Geld' "
            "via WhatsApp oder Telefon.",
        ],
    },

    "AT": {
        "name": "Austria",
        "language_codes": ["de"],
        "currency": "EUR",
        "iban_prefix": "AT",
        "polite_form_pronoun": "Sie",
        "authorities": {
            "tax": ["Finanzamt Österreich", "BMF"],
            "social": ["AMS", "ÖGK", "PVA", "AK"],
            "municipality": ["Magistrat", "Gemeindeamt"],
        },
        "specific_doc_types": [
            "Mahnung", "Mahnklage", "Zahlungsbefehl",
            "Einkommensteuerbescheid", "Strafverfügung",
        ],
        "scam_patterns": [
            "Anruf angeblich von BMF / Finanzpolizei mit Festnahme-Drohung.",
        ],
    },

    "CH": {
        "name": "Switzerland",
        "language_codes": ["de", "fr", "it", "rm"],
        "currency": "CHF",
        "iban_prefix": "CH",
        "polite_form_pronoun": "Sie / Vous / Lei",
        "authorities": {
            "tax": ["Eidg. Steuerverwaltung", "ESTV", "Kantonales Steueramt"],
            "social": ["AHV", "IV", "Ausgleichskasse", "SUVA"],
            "municipality": ["Einwohnerkontrolle", "Gemeinde"],
        },
        "specific_doc_types": [
            "Mahnung", "Betreibung", "Zahlungsbefehl", "Veranlagungsverfügung",
        ],
        "scam_patterns": [
            "Schockanruf angeblich von Polizei/Staatsanwaltschaft mit "
            "Aufforderung, Bargeld oder Schmuck zu übergeben.",
        ],
    },

    # ----------------------------------------------------------- BENELUX
    "NL": {
        "name": "Netherlands",
        "language_codes": ["nl"],
        "currency": "EUR",
        "iban_prefix": "NL",
        "polite_form_pronoun": "u",
        "authorities": {
            "tax": ["Belastingdienst"],
            "social": ["UWV", "SVB", "DUO"],
            "health_insurance": ["CZ", "VGZ", "Zilveren Kruis", "Menzis"],
            "municipality": ["Gemeente"],
            "court": ["Rechtbank", "Gerechtshof"],
        },
        "specific_doc_types": [
            "Aanmaning", "Dwangbevel", "Aanslag", "Boete", "Beschikking",
        ],
        "scam_patterns": [
            "SMS / e-mail van 'Belastingdienst' met phishing-link voor "
            "vermeende teruggave of openstaande aanslag.",
        ],
    },

    "BE": {
        "name": "Belgium",
        "language_codes": ["nl", "fr", "de"],
        "currency": "EUR",
        "iban_prefix": "BE",
        "polite_form_pronoun": "u / vous",
        "authorities": {
            "tax": ["FOD Financiën", "SPF Finances"],
            "social": ["RVA", "ONEM", "RIZIV", "INAMI", "Mutualité"],
            "municipality": ["Gemeente", "Commune"],
        },
        "specific_doc_types": [
            "Aanmaning", "Mise en demeure", "Aanslag", "Avertissement-extrait",
        ],
        "scam_patterns": [],
    },

    "LU": {
        "name": "Luxembourg",
        "language_codes": ["fr", "de", "lb"],
        "currency": "EUR",
        "iban_prefix": "LU",
        "authorities": {
            "tax": ["Administration des Contributions Directes", "ACD"],
            "social": ["CNS", "CCSS", "ADEM"],
        },
        "specific_doc_types": [],
        "scam_patterns": [],
    },

    # ---------------------------------------------------------- ROMANCE
    "FR": {
        "name": "France",
        "language_codes": ["fr"],
        "currency": "EUR",
        "iban_prefix": "FR",
        "polite_form_pronoun": "vous",
        "authorities": {
            "tax": [
                "Trésor Public", "DGFiP",
                "Direction Générale des Finances Publiques",
                "Service des Impôts",
            ],
            "health_insurance": [
                "CPAM", "Assurance Maladie", "Ameli", "MGEN", "Mutuelle",
            ],
            "social": [
                "URSSAF", "CAF", "Pôle Emploi", "France Travail",
                "MSA", "Sécurité Sociale",
            ],
            "pension": ["CNAV", "CARSAT", "AGIRC-ARRCO"],
            "court": [
                "Tribunal", "Tribunal Judiciaire", "Tribunal Administratif",
                "Cour d'Appel", "Huissier de Justice",
            ],
            "municipality": ["Mairie", "Préfecture", "Sous-Préfecture"],
            "education": ["CROUS", "Académie", "Rectorat"],
        },
        "specific_doc_types": [
            "Avis d'imposition", "Avis d'échéance",
            "Mise en demeure", "Commandement de payer",
            "Avis à tiers détenteur", "Saisie sur compte",
            "Procès-verbal", "Contravention",
        ],
        "scam_patterns": [
            "SMS angeblich von Ameli mit Aufforderung, Carte-Vitale-Daten zu aktualisieren — Phishing.",
            "Fake-Bußgeldbescheid (Antai) via SMS oder E-Mail mit Druckaufbau.",
            "Anruf 'votre numéro de sécurité sociale est utilisé frauduleusement' — Phishing.",
        ],
    },

    "ES": {
        "name": "Spain",
        "language_codes": ["es", "ca", "gl", "eu"],
        "currency": "EUR",
        "iban_prefix": "ES",
        "polite_form_pronoun": "usted",
        "authorities": {
            "tax": ["AEAT", "Hacienda", "Agencia Tributaria"],
            "health_insurance": ["Seguridad Social", "INSS", "Sanidad Pública"],
            "social": [
                "SEPE", "INSS", "TGSS",
                "Tesorería General de la Seguridad Social",
            ],
            "court": [
                "Juzgado", "Juzgado de Primera Instancia",
                "Audiencia Provincial", "Tribunal Supremo",
            ],
            "municipality": ["Ayuntamiento", "Padrón"],
        },
        "specific_doc_types": [
            "Notificación de embargo", "Providencia de apremio",
            "Liquidación provisional", "Acta de inspección",
            "Requerimiento", "Multa de tráfico",
        ],
        "scam_patterns": [
            "SMS angeblich von Correos / Endesa mit Aufforderung, kleine "
            "Gebühr zu zahlen — Phishing.",
            "Anruf angeblich von AEAT mit Druck zur sofortigen Zahlung — Betrug.",
        ],
    },

    "IT": {
        "name": "Italy",
        "language_codes": ["it"],
        "currency": "EUR",
        "iban_prefix": "IT",
        "polite_form_pronoun": "Lei",
        "authorities": {
            "tax": [
                "Agenzia delle Entrate", "Equitalia",
                "Agenzia Entrate-Riscossione", "ADER",
            ],
            "health_insurance": ["ASL", "ASST", "SSN"],
            "social": ["INPS", "INAIL", "Centro per l'Impiego"],
            "court": [
                "Tribunale", "Giudice di Pace", "Corte d'Appello",
                "Ufficiale Giudiziario",
            ],
            "municipality": ["Comune", "Anagrafe"],
        },
        "specific_doc_types": [
            "Cartella esattoriale", "Ingiunzione di pagamento",
            "Avviso di accertamento", "Decreto ingiuntivo",
            "Verbale", "Multa",
        ],
        "scam_patterns": [
            "WhatsApp / SMS impersonating INPS asking for IBAN — Phishing.",
            "Telefonata 'sua nipote ha avuto un incidente' — Schockanruf.",
        ],
    },

    "PT": {
        "name": "Portugal",
        "language_codes": ["pt"],
        "currency": "EUR",
        "iban_prefix": "PT",
        "polite_form_pronoun": "o senhor / a senhora",
        "authorities": {
            "tax": ["Autoridade Tributária", "AT", "Finanças"],
            "social": ["Segurança Social", "IEFP"],
        },
        "specific_doc_types": [
            "Citação", "Notificação", "Coima",
        ],
        "scam_patterns": [],
    },

    # ------------------------------------------------------------ CEE / Nordic
    "PL": {
        "name": "Poland",
        "language_codes": ["pl"],
        "currency": "PLN",
        "iban_prefix": "PL",
        "polite_form_pronoun": "Pan / Pani",
        "authorities": {
            "tax": ["Urząd Skarbowy", "Krajowa Administracja Skarbowa", "KAS"],
            "social": ["ZUS", "NFZ", "Urząd Pracy"],
            "municipality": ["Urząd Miasta", "Urząd Gminy"],
        },
        "specific_doc_types": [
            "Wezwanie", "Nakaz zapłaty", "Decyzja", "Mandat",
        ],
        "scam_patterns": [],
    },

    "CZ": {
        "name": "Czech Republic",
        "language_codes": ["cs"],
        "currency": "CZK",
        "iban_prefix": "CZ",
        "authorities": {
            "tax": ["Finanční úřad", "GFŘ"],
            "social": ["ČSSZ", "Úřad práce"],
        },
        "specific_doc_types": ["Vyměření", "Platëbní výměr", "Pokuta"],
        "scam_patterns": [],
    },

    "SE": {
        "name": "Sweden",
        "language_codes": ["sv"],
        "currency": "SEK",
        "iban_prefix": "SE",
        "polite_form_pronoun": "du",  # Sweden famously dropped the formal
        "authorities": {
            "tax": ["Skatteverket"],
            "social": ["Försäkringskassan", "Arbetsförmedlingen", "CSN"],
            "municipality": ["Kommun"],
        },
        "specific_doc_types": ["Krav", "Beslut", "Bötesföreläggande"],
        "scam_patterns": [],
    },

    "DK": {
        "name": "Denmark",
        "language_codes": ["da"],
        "currency": "DKK",
        "iban_prefix": "DK",
        "authorities": {
            "tax": ["SKAT", "Skattestyrelsen"],
            "social": ["Udbetaling Danmark"],
        },
        "specific_doc_types": ["Rykker", "Inkasso", "Påkrav"],
        "scam_patterns": [],
    },

    "FI": {
        "name": "Finland",
        "language_codes": ["fi", "sv"],
        "currency": "EUR",
        "iban_prefix": "FI",
        "authorities": {
            "tax": ["Verohallinto"],
            "social": ["Kela", "TE-toimisto"],
        },
        "specific_doc_types": ["Maksumuistutus", "Perintäkirje", "Sakko"],
        "scam_patterns": [],
    },

    # ---- Reserved placeholders — fill in when expansion warrants. ----
    "NO": {"name": "Norway", "language_codes": ["no"], "currency": "NOK", "iban_prefix": "NO", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
    "GR": {"name": "Greece", "language_codes": ["el"], "currency": "EUR", "iban_prefix": "GR", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
    "IE": {"name": "Ireland", "language_codes": ["en", "ga"], "currency": "EUR", "iban_prefix": "IE", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
    "GB": {"name": "United Kingdom", "language_codes": ["en"], "currency": "GBP", "iban_prefix": "GB", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
    "HU": {"name": "Hungary", "language_codes": ["hu"], "currency": "HUF", "iban_prefix": "HU", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
    "RO": {"name": "Romania", "language_codes": ["ro"], "currency": "RON", "iban_prefix": "RO", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
    "BG": {"name": "Bulgaria", "language_codes": ["bg"], "currency": "BGN", "iban_prefix": "BG", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
    "HR": {"name": "Croatia", "language_codes": ["hr"], "currency": "EUR", "iban_prefix": "HR", "authorities": {}, "specific_doc_types": [], "scam_patterns": []},
}


# ---------------------------------------------------------------------------
# Convenience lookup helpers
# ---------------------------------------------------------------------------
def country_pack(code: str) -> CountryPack | None:
    """Return the pack for an ISO-3166-1 alpha-2 code, or None if unknown."""
    if not code:
        return None
    return COUNTRY_PACKS.get(code.strip().upper())


def country_pack_by_language(lang_code: str) -> list[CountryPack]:
    """Return every pack whose `language_codes` includes the given
    ISO-639-1 code. Useful as a fallback when sender-name detection failed
    but the document's primary language is known.

    Multiple packs may match (e.g. 'de' → [DE, AT, CH], 'fr' → [FR, BE, CH, LU]).
    """
    lc = (lang_code or "").strip().lower()
    if not lc:
        return []
    return [p for p in COUNTRY_PACKS.values() if lc in p.get("language_codes", [])]
