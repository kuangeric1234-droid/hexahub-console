from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.api.middleware import RequestIDMiddleware
from backend.api.router import api_router
from backend.config import settings

log = structlog.get_logger()

__version__ = "0.2.0"


# ── Rate limiter ───────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.services.scheduler import scheduler, publish_due_posts
    scheduler.add_job(publish_due_posts, "interval", minutes=1, id="publish_scheduler", replace_existing=True)
    scheduler.start()
    log.info("startup", version=__version__, debug=settings.DEBUG)
    yield
    scheduler.shutdown(wait=False)
    log.info("shutdown")


# ── App ────────────────────────────────────────────────────────────────────────

docs_url  = "/docs"  if settings.DOCS_ENABLED else None
redoc_url = "/redoc" if settings.DOCS_ENABLED else None

app = FastAPI(
    title="Hexa Hub Marketing API",
    version=__version__,
    description=(
        "AI-powered multi-platform marketing content operations. "
        "Authenticate via `POST /api/v1/auth/token` (password) or "
        "`POST /api/v1/auth/login` (OAuth2 form), then use the returned "
        "`access_token` as `Authorization: Bearer <token>`."
    ),
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth",        "description": "Authentication and user management"},
        {"name": "campaigns",   "description": "Campaign lifecycle and AI workflow"},
        {"name": "posts",       "description": "Individual post CRUD and approval"},
        {"name": "approvals",   "description": "Approval queue and history"},
        {"name": "compliance",  "description": "Real-time 违禁词 compliance checking"},
        {"name": "ad-creative", "description": "Ad creative generation (A/B variants)"},
        {"name": "assets",      "description": "Media library with S3/MinIO storage"},
        {"name": "brand",       "description": "Brand context and marketing skills"},
        {"name": "logs",        "description": "Agent execution logs (admin only)"},
        {"name": "webhooks",    "description": "External system callbacks (shared secret)"},
        {"name": "tools",       "description": "Repurpose and utility endpoints"},
        {"name": "meta",        "description": "Health check"},
    ],
)

# ── Middleware (order matters: outermost executes last on response) ─────────────

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiter ───────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(api_router)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": __version__}
