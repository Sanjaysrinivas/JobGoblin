from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="JobGoblin API", version="0.1.0")

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
