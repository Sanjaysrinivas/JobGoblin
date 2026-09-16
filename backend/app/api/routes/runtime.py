"""Authenticated, non-secret runtime configuration for honest UI status."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models import User

router = APIRouter(prefix="/runtime", tags=["runtime"])


class RuntimeConfigurationOut(BaseModel):
    ai_provider: str
    ai_model: str
    local_ai: bool
    discovery_provider: str


@router.get("/configuration", response_model=RuntimeConfigurationOut)
def runtime_configuration(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> RuntimeConfigurationOut:
    settings = get_settings()
    provider = settings.ai_provider.casefold()
    model = settings.ollama_model if provider == "ollama" else provider
    return RuntimeConfigurationOut(
        ai_provider=provider,
        ai_model=model,
        local_ai=provider == "ollama",
        discovery_provider=settings.job_discovery_provider,
    )
