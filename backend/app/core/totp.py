"""TOTP authenticator-app helpers (pyotp + segno).

Generates per-user secrets, the ``otpauth://`` provisioning URI an authenticator
app scans, a self-contained QR code (base64 PNG data URI, no external assets),
and verifies submitted codes with a small clock-skew window.

Never log secrets or codes from here.
"""

import base64
import io

import pyotp
import segno


def generate_secret() -> str:
    """Return a fresh random base32 TOTP secret."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, *, account_name: str, issuer: str) -> str:
    """Build the ``otpauth://`` URI for an authenticator app to enroll."""
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)


def qr_data_uri(provisioning_uri: str) -> str:
    """Render the provisioning URI as a base64 PNG ``data:`` URI (self-contained)."""
    qr = segno.make(provisioning_uri, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=5, border=2)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_code(secret: str | None, code: str) -> bool:
    """Validate a 6-digit code against the secret. Never raises.

    ``valid_window=1`` tolerates one 30s step of clock drift either side.
    """
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception:
        return False
