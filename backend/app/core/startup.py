"""Application startup tasks (run from the FastAPI lifespan)."""

from sqlmodel import Session, select

from app.core import security
from app.core.config import get_settings
from app.core.database import engine
from app.models import User


def seed_admin(session: Session | None = None) -> User | None:
    """Create the seed admin from ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD`` if set.

    Idempotent and safe to call on every boot: does nothing when the env vars
    are empty, or when an admin (or a user with that email) already exists.
    Returns the created admin, or ``None`` if nothing was created.
    """
    settings = get_settings()
    email = settings.admin_email.strip().lower()
    password = settings.admin_password
    if not email or not password:
        return None

    owns_session = session is None
    session = session or Session(engine)
    try:
        # Already have any admin? leave it alone.
        if session.exec(select(User).where(User.is_admin.is_(True))).first() is not None:
            return None
        # Email already taken (non-admin)? don't clobber it.
        if session.exec(select(User).where(User.email == email)).first() is not None:
            return None

        admin = User(
            email=email,
            password_hash=security.hash_password(password),
            display_name="Admin",
            is_admin=True,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        return admin
    finally:
        if owns_session:
            session.close()
