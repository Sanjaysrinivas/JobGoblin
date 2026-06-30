from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env.

    Production MUST override the security-sensitive defaults below.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = "dev-secret-change-me"

    # Database
    database_url: str = "postgresql+psycopg://jobgoblin:jobgoblin@db:5432/jobgoblin"

    # AI provider
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_fast_model: str = "llama3.2:3b"

    # Storage / uploads
    file_storage_path: str = "/data/uploads"
    max_upload_mb: int = 10

    # Seed admin (single-user/invite-only bootstrap)
    admin_email: str = ""
    admin_password: str = ""

    # CORS (dev only; production is same-origin behind Caddy)
    frontend_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
