"""easli — `core` package.

Core primitives the rest of the backend builds on. Keep this layer free of
FastAPI route handlers and free of business logic — only configuration,
cross-cutting infrastructure (clients, logging, Sentry), shared exceptions,
security primitives (rate limiter), and prompt templates live here.

Importing any sub-module is safe and idempotent — no Sentry side-effects fire
until `core.config` is imported, which is the canonical bootstrap moment.

Directory layout:
  core/
    __init__.py        — this file
    config.py          — env vars, DB client, Mistral client, Sentry init
    security.py        — rate limiter (slowapi), client IP helper, middleware
    prompts.py         — Mistral system prompts (analyser, chat, translate, reply)
    exceptions.py      — custom application exceptions (e.g. MistralRateLimited)

DSGVO note: every value loaded here that may end up in logs is metadata only
(env-var names, model identifiers, sizes). No document bodies, no API keys,
no user content ever flows through this layer's logs.
"""

# Intentionally empty — sub-modules are imported explicitly by their users
# to keep the dependency graph obvious.
