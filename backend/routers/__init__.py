"""easli — `routers` package.

Each module here groups a related set of HTTP endpoints under a thin
`APIRouter` with `prefix="/api"` and a descriptive `tags=[...]` entry so
they render cleanly in OpenAPI / Swagger UI.

Phase 3 of the backend refactor splits the historic monolithic
`server.api_router` into purpose-specific routers:

  routers/scan.py     — POST /analyze + analysis CRUD + history erasure +
                        root + /languages
  routers/usage.py    — /usage, /paywall/config, /export, dev tools
  routers/chat.py     — chat + messages              (Phase 3b)
  routers/reply.py    — /generate-reply, /translate  (Phase 3b)
  routers/webhook.py  — /revenuecat/webhook          (Phase 3b)

Route bodies are intentionally still "fat" (call helpers in server.py).
Phase 4 will move the business logic out into `services/*` and the route
bodies will shrink to dependency-wiring + thin service calls.
"""
