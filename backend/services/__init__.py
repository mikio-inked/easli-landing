"""easli — `services` package.

Each module here owns one cross-cutting concern of the easli backend:

  services/image_service.py        — PDF→PNG conversion, vision-friendly
                                     image compression (Pillow).
  services/ocr_service.py          — Mistral OCR fan-out for multi-page scans.
  services/ai_service.py           — Mistral chat/analyse/translate calls
                                     + retry policy + language gate.
  services/entitlement_service.py  — usage / quota / paywall decision logic.

Design rules:
  • Each service is INDEPENDENTLY importable. No service is allowed to
    import from `routers/*`; routers import services, never the other way.
  • Services may import from `core/*`, `models/*`, `utils/*`, and each
    other (cautiously).
  • Services NEVER touch FastAPI's `Request` object — they take plain
    Python arguments and raise `HTTPException` only where the existing
    contract demanded it (preserved for byte-identical refactor).
"""
