"""Google OAuth (OpenID Connect) client built on Authlib.

Two responsibilities, kept deliberately small so the route layer stays thin and
tests can stub them without any network:

- ``build_authorization_url`` — the Google consent URL to redirect the browser to.
- ``fetch_verified_identity`` — exchange the callback code and return the
  Google-verified ``(email, sub)``.

The OAuth client is created lazily and only when Google credentials are
configured; ``is_configured`` lets routes return a clean 503 otherwise so the
app boots fine with empty creds.
"""

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request

from app.core.config import get_settings

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"

_oauth: OAuth | None = None


def is_configured() -> bool:
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def _client():
    """Return the registered Authlib Google client, building the registry once."""
    global _oauth
    s = get_settings()
    if _oauth is None:
        _oauth = OAuth()
        _oauth.register(
            name="google",
            client_id=s.google_client_id,
            client_secret=s.google_client_secret,
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs={"scope": "openid email profile"},
        )
    return _oauth.create_client("google")


def callback_redirect_uri() -> str:
    """The absolute redirect_uri Google calls back to."""
    base = get_settings().oauth_redirect_base_url.rstrip("/")
    return f"{base}/api/auth/google/callback"


async def build_authorization_redirect(request: Request):
    """Return a RedirectResponse to Google's consent screen (stores state in session)."""
    return await _client().authorize_redirect(request, callback_redirect_uri())


def build_authorization_url(state: str) -> str:
    """Pure-URL variant (used when no Starlette session is available / in tests)."""
    client = _client()
    metadata = client.load_server_metadata()
    endpoint = metadata["authorization_endpoint"]
    url, _ = client.create_authorization_url(
        endpoint, redirect_uri=callback_redirect_uri(), state=state
    )
    return url


async def fetch_verified_identity(request: Request) -> tuple[str, str]:
    """Exchange the authorization code and return the verified ``(email, sub)``.

    Raises if the token/userinfo is missing or the email is unverified. Tests
    monkeypatch this function to avoid any network call.
    """
    client = _client()
    token = await client.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await client.userinfo(token=token)
    email = userinfo.get("email")
    sub = userinfo.get("sub")
    email_verified = userinfo.get("email_verified", True)
    if not email or not sub or not email_verified:
        raise ValueError("Google did not return a verified email/sub")
    return email, sub
