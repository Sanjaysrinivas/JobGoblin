from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import include_discovered_routers
from app.core.config import get_settings
from app.core.ratelimit import limiter, rate_limit_exceeded_handler
from app.core.startup import seed_admin

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Idempotently seed the first admin from env, if configured.
    seed_admin()
    yield


app = FastAPI(title="JobGoblin API", version="0.1.0", lifespan=lifespan)

# Rate limiting for brute-forceable auth endpoints. The decorators on the auth
# routes read this limiter from app.state; a 429 is rendered via our handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Authlib's OAuth flow stashes the CSRF state / OIDC nonce in a server-managed
# session (a separate signed cookie from our JWT session). Scoped to the Google
# OAuth callback path; short-lived.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="jg_oauth_state",
    max_age=600,
    same_site="lax",
    https_only=settings.app_env != "development",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
    """Emit the consistent error envelope ``{detail, code}``.

    Routes raise ``HTTPException(detail={"detail": msg, "code": code})``; this
    handler flattens that into the body. Plain-string details fall back to
    ``{"detail": msg}`` so other endpoints keep working unchanged.
    """
    detail = exc.detail
    if isinstance(detail, dict):
        body = detail
    else:
        body = {"detail": detail}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


# In production the frontend and backend share one origin (behind Caddy), so no
# CORS is needed. In development the frontend (:3000) and backend (:8000) differ,
# so allow the frontend origin with credentials for cookie-based auth.
if settings.app_env == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

include_discovered_routers(app, prefix="/api")
