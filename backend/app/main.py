from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, health
from app.core.config import get_settings
from app.core.startup import seed_admin

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Idempotently seed the first admin from env, if configured.
    seed_admin()
    yield


app = FastAPI(title="JobGoblin API", version="0.1.0", lifespan=lifespan)


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

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
