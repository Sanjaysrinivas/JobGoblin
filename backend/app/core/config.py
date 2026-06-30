from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / .env.

    Production MUST override the security-sensitive defaults below.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = "dev-secret-change-me"

    # Auth / session cookie
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    session_cookie_name: str = "jg_session"
    # Carries the short-lived MFA-pending token between primary auth and the
    # second-factor challenge. Distinct from the session cookie so the two
    # states never collide.
    mfa_cookie_name: str = "jg_mfa"

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

    # Google OAuth (login/signup). Empty by default so the app boots without
    # Google configured; the Google endpoints return 503 until creds are set.
    google_client_id: str = ""
    google_client_secret: str = ""
    # Base URL the OAuth callback is reachable at (used to build redirect_uri).
    oauth_redirect_base_url: str = "http://localhost:8080"

    # Email allowlist (private tool). Comma-separated; empty disables the
    # allowlist gate. Parsed/normalised via the ``allowed_email_set`` property.
    allowed_emails: str = ""

    # TOTP MFA: short-lived token lifetime for the intermediate "mfa_pending"
    # state between primary auth and the second-factor challenge.
    mfa_pending_token_expire_minutes: int = 5
    # Issuer name shown in the authenticator app (the otpauth:// label).
    totp_issuer: str = "JobGoblin"

    @property
    def allowed_email_set(self) -> set[str]:
        """The allowlist as a set of lowercased, stripped emails (may be empty)."""
        return {
            e.strip().lower()
            for e in self.allowed_emails.split(",")
            if e.strip()
        }

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> "Settings":
        """Refuse to boot in production with insecure default secrets/credentials."""
        if self.app_env == "production":
            if self.app_secret_key == "dev-secret-change-me":
                raise ValueError(
                    "APP_SECRET_KEY must be overridden with a secure value in production."
                )
            if "jobgoblin:jobgoblin" in self.database_url:
                raise ValueError(
                    "DATABASE_URL must not use the default credentials in production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
