"""easli — legacy module entry point (5-line shim).

After Phase 5 of the backend refactor, the entire backend lives in
`main.py` + `core/` + `models/` + `routers/` + `services/` + `utils/`.
This file exists ONLY because the container's supervisord.conf is a
read-only file that still launches the backend with `uvicorn server:app`.

If you ever own the supervisord.conf and can change it to
`uvicorn main:app`, delete this file outright.

Procfile and railway.json have already been moved to `main:app`.
"""

from main import app  # noqa: F401 — re-exported for `uvicorn server:app`

__all__ = ["app"]
