import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.models import Job, Resume, User, WorkMode


def test_create_and_retrieve_user(session):
    user = User(email="a@b.com", password_hash="x", display_name="A")
    session.add(user)
    session.commit()
    session.refresh(user)

    got = session.get(User, user.id)
    assert got is not None
    assert got.email == "a@b.com"
    assert got.is_admin is False
    assert got.created_at is not None


def test_duplicate_email_rejected(session):
    session.add(User(email="dup@b.com", password_hash="x", display_name="A"))
    session.commit()

    session.add(User(email="dup@b.com", password_hash="y", display_name="B"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_user_cascades_resumes(session):
    user = User(email="c@b.com", password_hash="x", display_name="C")
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id

    session.add(
        Resume(
            user_id=user_id,
            title="R",
            original_filename="r.pdf",
            file_key="k",
            content_type="application/pdf",
            file_size=10,
        )
    )
    session.commit()

    session.delete(user)
    session.commit()

    remaining = session.exec(select(Resume).where(Resume.user_id == user_id)).all()
    assert remaining == []


def test_timestamps_are_timezone_aware(session):
    user = User(email="tz@b.com", password_hash="x", display_name="TZ")
    session.add(user)
    session.commit()

    # Force a reload from the DB so we see what Postgres actually returns.
    session.expire_all()
    got = session.get(User, user.id)
    assert got.created_at.tzinfo is not None


def test_job_enum_defaults(session):
    user = User(email="d@b.com", password_hash="x", display_name="D")
    session.add(user)
    session.commit()
    session.refresh(user)

    job = Job(user_id=user.id, company_name="Acme", title="Engineer", description="jd")
    session.add(job)
    session.commit()
    session.refresh(job)

    assert job.work_mode == WorkMode.unknown
    assert job.source.value == "other"
