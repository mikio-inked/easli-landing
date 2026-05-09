"""easli — Admin & Redemption-Code Module.

This module ships the Admin Web UI ("/admin") plus all admin/redemption
endpoints. Kept in a SEPARATE file from server.py to avoid bloating the
already-3300-line monolith.

Architecture:
  • Single-admin model — exactly ONE admin login, password set on first run
    (initial-setup flow at /api/admin/setup-status + /api/admin/setup).
  • Sessions: JWT (HS256). Token TTL 24h. Secret auto-generated on first
    setup and persisted in `admin_config`.
  • Redemption codes: stored in `redemption_codes` collection. Each code
    has a tier ("lifetime" | "plus_year" | "plus_month"), max_uses, used_by
    list, optional expires_at. Idempotent — same device redeeming twice
    just returns OK without double-applying.
  • Public endpoint `/api/redeem` lets the in-app hidden flow consume
    a code and flips the user's `usage_records` doc to `plus_active=true`
    (and `plus_lifetime=true` for lifetime codes).

Privacy: never logs passwords, JWT secret, or full code values. Only
prefix + last 4 chars of any code-related log line.
"""

# Note: NO `from __future__ import annotations` here — it would turn our
# Pydantic models into forward references that Body(...) defaults can't
# resolve, breaking FastAPI's request-body inspection.

import secrets
import string
import os
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Literal

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Header, Depends, Request, Body
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# ---- Constants ----------------------------------------------------------
ADMIN_CONFIG_ID = "admin"
JWT_ALGO = "HS256"
JWT_TTL_HOURS = 24
ADMIN_HTML_PATH = Path(__file__).parent / "admin.html"

# Tier definitions — what a code unlocks when redeemed.
TIER_LIFETIME = "lifetime"
TIER_PLUS_YEAR = "plus_year"
TIER_PLUS_MONTH = "plus_month"
ALLOWED_TIERS = {TIER_LIFETIME, TIER_PLUS_YEAR, TIER_PLUS_MONTH}

# ---- Models -------------------------------------------------------------


class SetupStatusResponse(BaseModel):
    setup_completed: bool


class SetupRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str
    expires_at: str


class CreateCodeRequest(BaseModel):
    tier: Literal["lifetime", "plus_year", "plus_month"] = "lifetime"
    max_uses: int = Field(default=1, ge=1, le=10000)
    note: Optional[str] = ""
    expires_at: Optional[str] = None  # ISO date, optional
    custom_code: Optional[str] = None  # if set, use this exact code instead of random


class CodeRecord(BaseModel):
    code: str
    tier: str
    max_uses: int
    uses: int
    used_by: List[str] = []
    note: Optional[str] = ""
    expires_at: Optional[str] = None
    created_at: str
    active: bool = True


class RedeemRequest(BaseModel):
    device_id: str
    code: str


class RedeemResponse(BaseModel):
    ok: bool
    tier: Optional[str] = None
    message: str = ""
    plus_active: bool = False
    plus_lifetime: bool = False
    plus_period_end: Optional[str] = None


class GrantLifetimeRequest(BaseModel):
    device_id: str
    note: Optional[str] = ""


class DashboardStats(BaseModel):
    total_users: int
    active_today: int
    active_week: int
    total_analyses: int
    analyses_today: int
    analyses_week: int
    plus_users_active: int
    lifetime_users: int
    top_languages: List[dict]
    top_countries: List[dict]


# ---- Helpers ------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_code(prefix: str = "EASLI") -> str:
    """Random 12-char human-friendly code: EASLI-XXXX-XXXX (no ambig chars).

    Avoids 0/O/1/I/L for readability when typing on iPhone.
    """
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    body = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{prefix}-{body[:4]}-{body[4:]}"


def _normalize_code(raw: str) -> str:
    """Uppercase + strip whitespace + dashes preserved."""
    if not raw:
        return ""
    return "".join(raw.upper().split())


def _mask_code(code: str) -> str:
    """For logs: EASLI-XXXX-AB12 → EASLI-***-AB12."""
    if not code or len(code) < 4:
        return "***"
    return f"{code[:6]}***{code[-4:]}"


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---- Admin Router Factory ----------------------------------------------


def make_admin_router(db: AsyncIOMotorDatabase, limiter=None) -> APIRouter:
    """Build the /api/admin + /api/redeem routes wired to the given DB.

    Kept as a factory because server.py owns the Mongo client; we accept the
    db handle here and avoid re-creating one. Returns a single router that
    server.py can include with `app.include_router(...)`.

    `limiter` (slowapi.Limiter, optional) — if provided, applies per-route
    rate limits to /api/redeem and /api/admin/login. None = limits disabled.
    """

    router = APIRouter()

    # Lightweight wrapper so calling code stays clean even when no limiter
    # is configured (e.g. unit tests). Preserves the inner function's
    # signature with functools.wraps so FastAPI's body-inspection still
    # detects Pydantic models as JSON bodies (otherwise they'd be parsed
    # as query params and 422 would fire).
    import functools

    def _maybe_limit(rule: str):
        def _decorator(fn):
            if limiter is None:
                return fn
            wrapped = limiter.limit(rule)(fn)
            return functools.wraps(fn)(wrapped)
        return _decorator

    # ---- Setup state cache (read once on startup, refreshed on writes) --
    # We keep a tiny in-memory mirror so the JWT secret doesn't hit the DB
    # on every authenticated request.
    state: dict = {"jwt_secret": None, "loaded": False}

    async def _load_state() -> None:
        cfg = await db.admin_config.find_one({"_id": ADMIN_CONFIG_ID})
        if cfg:
            state["jwt_secret"] = cfg.get("jwt_secret")
        state["loaded"] = True

    async def _ensure_state() -> dict:
        if not state["loaded"]:
            await _load_state()
        return state

    # ---- JWT helpers ----------------------------------------------------

    def _issue_token(jwt_secret: str) -> TokenResponse:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=JWT_TTL_HOURS)
        payload = {
            "sub": "admin",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, jwt_secret, algorithm=JWT_ALGO)
        return TokenResponse(token=token, expires_at=exp.isoformat())

    async def require_admin(authorization: Optional[str] = Header(None)) -> str:
        """Dependency: validate Bearer JWT, return 'admin' or raise 401."""
        await _ensure_state()
        secret = state.get("jwt_secret")
        if not secret:
            raise HTTPException(status_code=401, detail="Admin not configured")
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGO])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        if payload.get("sub") != "admin":
            raise HTTPException(status_code=401, detail="Invalid subject")
        return "admin"

    # =====================================================================
    # 1. Static UI — /admin (and /admin/)
    # =====================================================================

    @router.get("/admin", response_class=HTMLResponse)
    @router.get("/admin/", response_class=HTMLResponse)
    @router.get("/api/admin/ui", response_class=HTMLResponse)
    async def admin_html() -> FileResponse:
        if not ADMIN_HTML_PATH.exists():
            raise HTTPException(status_code=404, detail="Admin UI missing")
        return FileResponse(str(ADMIN_HTML_PATH), media_type="text/html")

    # =====================================================================
    # 2. Setup + Login (no auth required for these)
    # =====================================================================

    @router.get("/api/admin/setup-status", response_model=SetupStatusResponse)
    async def setup_status() -> SetupStatusResponse:
        cfg = await db.admin_config.find_one(
            {"_id": ADMIN_CONFIG_ID}, {"setup_completed": 1}
        )
        return SetupStatusResponse(
            setup_completed=bool(cfg and cfg.get("setup_completed"))
        )

    @router.post("/api/admin/setup", response_model=TokenResponse)
    async def setup(req: SetupRequest) -> TokenResponse:
        """First-time admin password setup. Idempotent — once setup is
        completed this endpoint returns 409 forever.
        """
        existing = await db.admin_config.find_one({"_id": ADMIN_CONFIG_ID})
        if existing and existing.get("setup_completed"):
            raise HTTPException(status_code=409, detail="Admin already configured")

        password_hash = _hash_password(req.password)
        jwt_secret = secrets.token_urlsafe(48)

        await db.admin_config.update_one(
            {"_id": ADMIN_CONFIG_ID},
            {
                "$set": {
                    "password_hash": password_hash,
                    "jwt_secret": jwt_secret,
                    "setup_completed": True,
                    "created_at": _now_iso(),
                }
            },
            upsert=True,
        )
        # Refresh in-memory state.
        state["jwt_secret"] = jwt_secret
        state["loaded"] = True
        logger.info("admin_setup_completed")
        return _issue_token(jwt_secret)

    @router.post("/api/admin/login", response_model=TokenResponse)
    @_maybe_limit(os.environ.get("RATE_LIMIT_ADMIN_LOGIN", "20/hour"))
    async def login(
        request: Request,
        req: LoginRequest = Body(...),
    ) -> TokenResponse:
        cfg = await db.admin_config.find_one({"_id": ADMIN_CONFIG_ID})
        if not cfg or not cfg.get("setup_completed"):
            raise HTTPException(status_code=409, detail="Admin not configured")

        # ---- Brute-force lockout ----
        # After 5 consecutive failed logins, lock the account for 15 minutes.
        # The counter resets on success. Stored in MongoDB so a server
        # restart can't bypass it.
        now_ts = datetime.now(timezone.utc)
        failed = int(cfg.get("failed_login_attempts") or 0)
        lockout_until_str = cfg.get("lockout_until")
        if lockout_until_str:
            try:
                lockout_until = datetime.fromisoformat(
                    lockout_until_str.replace("Z", "+00:00")
                )
                if lockout_until > now_ts:
                    remaining_min = int(
                        (lockout_until - now_ts).total_seconds() / 60
                    ) + 1
                    logger.warning("admin_login_locked_out remaining_min=%s", remaining_min)
                    raise HTTPException(
                        status_code=429,
                        detail=f"Too many failed attempts. Try again in {remaining_min} min.",
                    )
            except (ValueError, TypeError):
                pass

        if not _verify_password(req.password, cfg.get("password_hash") or ""):
            new_failed = failed + 1
            update: dict = {"failed_login_attempts": new_failed}
            if new_failed >= 5:
                lockout_end = now_ts + timedelta(minutes=15)
                update["lockout_until"] = lockout_end.isoformat()
                update["failed_login_attempts"] = 0  # reset counter on lockout
                logger.warning("admin_login_lockout_triggered")
            await db.admin_config.update_one(
                {"_id": ADMIN_CONFIG_ID}, {"$set": update}
            )
            logger.warning("admin_login_failed attempt=%s", new_failed)
            raise HTTPException(status_code=401, detail="Invalid password")

        jwt_secret = cfg.get("jwt_secret") or ""
        if not jwt_secret:
            jwt_secret = secrets.token_urlsafe(48)
            await db.admin_config.update_one(
                {"_id": ADMIN_CONFIG_ID}, {"$set": {"jwt_secret": jwt_secret}}
            )
        state["jwt_secret"] = jwt_secret
        state["loaded"] = True
        # Reset lockout state on successful login.
        await db.admin_config.update_one(
            {"_id": ADMIN_CONFIG_ID},
            {
                "$set": {
                    "last_login_at": _now_iso(),
                    "failed_login_attempts": 0,
                    "lockout_until": None,
                }
            },
        )
        logger.info("admin_login_ok")
        return _issue_token(jwt_secret)

    # =====================================================================
    # 3. Dashboard / Stats (authenticated)
    # =====================================================================

    @router.get("/api/admin/dashboard", response_model=DashboardStats)
    async def dashboard(_: str = Depends(require_admin)) -> DashboardStats:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        total_users = await db.usage_records.count_documents({})
        active_today = await db.usage_records.count_documents(
            {"updated_at": {"$gte": today_start.isoformat()}}
        )
        active_week = await db.usage_records.count_documents(
            {"updated_at": {"$gte": week_start.isoformat()}}
        )
        total_analyses = await db.analyses.count_documents({})
        analyses_today = await db.analyses.count_documents(
            {"created_at": {"$gte": today_start.isoformat()}}
        )
        analyses_week = await db.analyses.count_documents(
            {"created_at": {"$gte": week_start.isoformat()}}
        )
        plus_users_active = await db.usage_records.count_documents({"plus_active": True})
        lifetime_users = await db.usage_records.count_documents({"plus_lifetime": True})

        # Top languages
        top_lang_cursor = db.analyses.aggregate(
            [
                {"$match": {"target_language": {"$exists": True, "$ne": ""}}},
                {"$group": {"_id": "$target_language", "n": {"$sum": 1}}},
                {"$sort": {"n": -1}},
                {"$limit": 5},
            ]
        )
        top_languages = [
            {"language": d["_id"], "count": d["n"]} async for d in top_lang_cursor
        ]

        # Top detected countries
        top_country_cursor = db.analyses.aggregate(
            [
                {"$match": {"detected_country_code": {"$exists": True, "$nin": ["", None]}}},
                {"$group": {"_id": "$detected_country_code", "n": {"$sum": 1}}},
                {"$sort": {"n": -1}},
                {"$limit": 5},
            ]
        )
        top_countries = [
            {"country": d["_id"], "count": d["n"]} async for d in top_country_cursor
        ]

        return DashboardStats(
            total_users=total_users,
            active_today=active_today,
            active_week=active_week,
            total_analyses=total_analyses,
            analyses_today=analyses_today,
            analyses_week=analyses_week,
            plus_users_active=plus_users_active,
            lifetime_users=lifetime_users,
            top_languages=top_languages,
            top_countries=top_countries,
        )

    # =====================================================================
    # 4. User Management
    # =====================================================================

    @router.get("/api/admin/users")
    async def list_users(
        q: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
        _: str = Depends(require_admin),
    ):
        limit = max(1, min(limit, 200))
        flt: dict = {}
        if q:
            flt["device_id"] = {"$regex": q.strip(), "$options": "i"}
        cursor = (
            db.usage_records.find(flt, {"_id": 0})
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
        )
        items = [doc async for doc in cursor]
        total = await db.usage_records.count_documents(flt)
        return {"total": total, "items": items}

    @router.get("/api/admin/users/{device_id}")
    async def get_user(device_id: str, _: str = Depends(require_admin)):
        usage = await db.usage_records.find_one({"device_id": device_id}, {"_id": 0})
        analyses_count = await db.analyses.count_documents({"device_id": device_id})
        last_analysis = await db.analyses.find_one(
            {"device_id": device_id},
            {"_id": 0, "id": 1, "created_at": 1, "document_type": 1, "category": 1},
            sort=[("created_at", -1)],
        )
        return {
            "usage": usage,
            "analyses_count": analyses_count,
            "last_analysis": last_analysis,
        }

    @router.post("/api/admin/users/grant-lifetime")
    async def grant_lifetime(
        req: GrantLifetimeRequest, _: str = Depends(require_admin)
    ):
        """Manually grant lifetime Plus to a device — bypasses RevenueCat."""
        if not req.device_id:
            raise HTTPException(status_code=400, detail="device_id required")
        now = _now_iso()
        await db.usage_records.update_one(
            {"device_id": req.device_id},
            {
                "$set": {
                    "plus_active": True,
                    "plus_lifetime": True,
                    "plus_current_period_end": None,  # null = no expiry
                    "plus_admin_grant_note": req.note or "",
                    "plus_admin_granted_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"device_id": req.device_id, "created_at": now},
            },
            upsert=True,
        )
        logger.info("admin_grant_lifetime device=%s", req.device_id)
        return {"ok": True}

    @router.post("/api/admin/users/revoke-lifetime")
    async def revoke_lifetime(
        req: GrantLifetimeRequest, _: str = Depends(require_admin)
    ):
        if not req.device_id:
            raise HTTPException(status_code=400, detail="device_id required")
        now = _now_iso()
        await db.usage_records.update_one(
            {"device_id": req.device_id},
            {
                "$set": {
                    "plus_active": False,
                    "plus_lifetime": False,
                    "plus_admin_revoke_note": req.note or "",
                    "plus_admin_revoked_at": now,
                    "updated_at": now,
                },
            },
        )
        logger.info("admin_revoke_lifetime device=%s", req.device_id)
        return {"ok": True}

    # =====================================================================
    # 5. Redemption Codes — Admin
    # =====================================================================

    @router.get("/api/admin/codes")
    async def list_codes(_: str = Depends(require_admin)):
        cursor = db.redemption_codes.find({}, {"_id": 0}).sort("created_at", -1).limit(500)
        items = [doc async for doc in cursor]
        return {"items": items, "total": len(items)}

    @router.post("/api/admin/codes")
    async def create_code(req: CreateCodeRequest, _: str = Depends(require_admin)):
        if req.tier not in ALLOWED_TIERS:
            raise HTTPException(status_code=400, detail="Invalid tier")
        # Custom code (e.g. "EASLI-MOM-2026") OR generated random.
        code = (
            _normalize_code(req.custom_code)
            if req.custom_code
            else _generate_code()
        )
        if not code or len(code) < 6:
            raise HTTPException(status_code=400, detail="Code too short")
        # Uniqueness check
        existing = await db.redemption_codes.find_one({"code": code})
        if existing:
            raise HTTPException(status_code=409, detail="Code already exists")
        record = {
            "code": code,
            "tier": req.tier,
            "max_uses": req.max_uses,
            "uses": 0,
            "used_by": [],
            "note": req.note or "",
            "expires_at": req.expires_at or None,
            "created_at": _now_iso(),
            "active": True,
        }
        await db.redemption_codes.insert_one(record)
        record.pop("_id", None)
        logger.info("admin_code_created tier=%s code=%s", req.tier, _mask_code(code))
        return record

    @router.delete("/api/admin/codes/{code}")
    async def deactivate_code(code: str, _: str = Depends(require_admin)):
        norm = _normalize_code(code)
        result = await db.redemption_codes.update_one(
            {"code": norm}, {"$set": {"active": False}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Code not found")
        logger.info("admin_code_deactivated code=%s", _mask_code(norm))
        return {"ok": True}

    @router.post("/api/admin/codes/{code}/reactivate")
    async def reactivate_code(code: str, _: str = Depends(require_admin)):
        norm = _normalize_code(code)
        result = await db.redemption_codes.update_one(
            {"code": norm}, {"$set": {"active": True}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Code not found")
        return {"ok": True}

    # =====================================================================
    # 6. Public Redemption — used by hidden in-app flow
    # =====================================================================

    @router.post("/api/redeem", response_model=RedeemResponse)
    @_maybe_limit(os.environ.get("RATE_LIMIT_REDEEM", "10/minute"))
    async def redeem_code(
        request: Request,
        req: RedeemRequest = Body(...),
    ):
        if not req.device_id or not req.code:
            raise HTTPException(status_code=400, detail="device_id and code required")
        norm = _normalize_code(req.code)
        rec = await db.redemption_codes.find_one({"code": norm})
        if not rec:
            return RedeemResponse(ok=False, message="Code not found")
        if not rec.get("active", True):
            return RedeemResponse(ok=False, message="Code is no longer active")
        # Expiry check
        exp = rec.get("expires_at")
        if exp:
            try:
                if datetime.fromisoformat(exp.replace("Z", "+00:00")) < datetime.now(
                    timezone.utc
                ):
                    return RedeemResponse(ok=False, message="Code expired")
            except (ValueError, AttributeError):
                pass
        # Already used by THIS device — idempotent success
        used_by = rec.get("used_by") or []
        if req.device_id in used_by:
            tier = rec.get("tier")
            return RedeemResponse(
                ok=True,
                tier=tier,
                message="Already redeemed",
                plus_active=True,
                plus_lifetime=(tier == TIER_LIFETIME),
            )
        # Capacity check
        if rec.get("uses", 0) >= rec.get("max_uses", 1):
            return RedeemResponse(ok=False, message="Code limit reached")

        tier = rec.get("tier") or TIER_LIFETIME
        now = _now_iso()
        period_end_iso: Optional[str] = None
        update_fields: dict = {
            "plus_active": True,
            "updated_at": now,
        }
        if tier == TIER_LIFETIME:
            update_fields["plus_lifetime"] = True
            update_fields["plus_current_period_end"] = None
        elif tier == TIER_PLUS_YEAR:
            period_end = datetime.now(timezone.utc) + timedelta(days=365)
            period_end_iso = period_end.isoformat()
            update_fields["plus_current_period_end"] = period_end_iso
            update_fields["plus_current_period_start"] = now
        elif tier == TIER_PLUS_MONTH:
            period_end = datetime.now(timezone.utc) + timedelta(days=30)
            period_end_iso = period_end.isoformat()
            update_fields["plus_current_period_end"] = period_end_iso
            update_fields["plus_current_period_start"] = now

        # Mark code consumed (atomic) BEFORE touching usage so a crash
        # between the two writes doesn't double-grant.
        consumed = await db.redemption_codes.update_one(
            {
                "code": norm,
                "active": True,
                "uses": {"$lt": rec.get("max_uses", 1)},
                "used_by": {"$ne": req.device_id},
            },
            {
                "$inc": {"uses": 1},
                "$push": {"used_by": req.device_id},
                "$set": {"last_used_at": now},
            },
        )
        if consumed.matched_count == 0:
            # Race condition — someone else just consumed the last use.
            return RedeemResponse(ok=False, message="Code limit reached")

        await db.usage_records.update_one(
            {"device_id": req.device_id},
            {
                "$set": update_fields,
                "$setOnInsert": {"device_id": req.device_id, "created_at": now},
            },
            upsert=True,
        )
        logger.info(
            "redeem_ok device=%s code=%s tier=%s",
            req.device_id, _mask_code(norm), tier,
        )
        return RedeemResponse(
            ok=True,
            tier=tier,
            message="Code redeemed successfully",
            plus_active=True,
            plus_lifetime=(tier == TIER_LIFETIME),
            plus_period_end=period_end_iso,
        )

    return router
