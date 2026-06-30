"""TOTP authenticator-app helpers (pyotp + segno).

Generates per-user secrets, the ``otpauth://`` provisioning URI an authenticator
app scans, a self-contained QR code (base64 PNG data URI, no external assets),
and verifies submitted codes with a small clock-skew window.

Never log secrets or codes from here.
"""

import base64
import io
import time

import pyotp
import segno

# A TOTP step is 30 seconds; we accept one step of drift either side.
_PERIOD = 30
_DRIFT_STEPS = 1


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

    Tolerates one 30s step of clock drift either side. Use
    :func:`match_timestep` instead when you need replay protection.
    """
    return match_timestep(secret, code) is not None


def match_timestep(
    secret: str | None, code: str, *, last_timestep: int | None = None
) -> int | None:
    """Return the Unix timestep the code matches, or ``None`` if it doesn't.

    The timestep is ``unix_time // 30``. We scan the current step plus one step
    of drift either side. When ``last_timestep`` is given, any matching step that
    is ``<= last_timestep`` is rejected — this prevents replaying a code (or an
    older still-valid one) after it has already been consumed. Never raises.
    """
    if not secret or not code:
        return None
    code = code.strip()
    try:
        totp_obj = pyotp.TOTP(secret)
        now = int(time.time())
        current_step = now // _PERIOD
        # Check newest steps first so a fresh code maps to its own step.
        for offset in range(_DRIFT_STEPS, -_DRIFT_STEPS - 1, -1):
            step = current_step + offset
            for_time = step * _PERIOD
            if totp_obj.verify(code, for_time=for_time, valid_window=0):
                if last_timestep is not None and step <= last_timestep:
                    return None
                return step
        return None
    except Exception:
        return None
