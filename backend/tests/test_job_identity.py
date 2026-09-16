"""Coordination tests for the job-identity service (plan item F9)."""

import threading
import uuid

import pytest
from sqlmodel import Session, select

from app.models import Job, User
from app.services.job_identity import (
    JobIdentityConflict,
    find_duplicate_job,
    job_dedupe_key,
    persist_job,
)


@pytest.fixture
def user(session) -> User:
    u = User(email="identity@example.com", password_hash="x", display_name="Id")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _job(user_id: uuid.UUID, dedupe_key: str, title: str) -> Job:
    return Job(
        user_id=user_id,
        company_name="Acme",
        title=title,
        dedupe_key=dedupe_key,
        description="Coordination test job.",
    )


def test_find_duplicate_job_scopes_to_user(session, user):
    key = job_dedupe_key("https://example.com/one", "Acme", "Eng", "Remote")
    other = User(email="other-identity@example.com", password_hash="x", display_name="O")
    session.add(other)
    session.commit()

    session.add(_job(user.id, key, "Mine"))
    session.add(_job(other.id, key, "Theirs"))
    session.commit()

    mine = find_duplicate_job(session, user, key)
    assert mine is not None
    assert mine.user_id == user.id
    assert find_duplicate_job(session, user, key, exclude_id=mine.id) is None
    assert find_duplicate_job(session, user, "missing-key") is None


def test_persist_job_translates_uniqueness_violation(session, user):
    key = job_dedupe_key("https://example.com/two", "Acme", "Eng", "Remote")
    session.add(_job(user.id, key, "First"))
    session.commit()

    with pytest.raises(JobIdentityConflict):
        persist_job(session, _job(user.id, key, "Second"))


def test_persist_job_leaves_commit_to_its_caller(engine, user):
    key = job_dedupe_key("https://example.com/staged", "Acme", "Eng", "Remote")
    with Session(engine) as writer:
        persist_job(writer, _job(user.id, key, "Staged"))
        with Session(engine) as reader:
            assert reader.exec(select(Job).where(Job.dedupe_key == key)).first() is None
        writer.commit()

    with Session(engine) as reader:
        assert reader.exec(select(Job).where(Job.dedupe_key == key)).first() is not None


def test_concurrent_identity_writes_leave_one_job(engine, session, user):
    """Two connections race the same identity: exactly one job survives and
    the loser gets JobIdentityConflict instead of a leaked IntegrityError."""
    key = job_dedupe_key("https://example.com/race", "Acme", "Eng", "Remote")
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def service_writer(name: str) -> None:
        with Session(engine) as own:
            barrier.wait(timeout=30)
            try:
                persist_job(own, _job(user.id, key, f"Racer {name}"))
                own.commit()
                outcomes.append(f"ok-{name}")
            except JobIdentityConflict:
                outcomes.append(f"conflict-{name}")
            except Exception as exc:  # noqa: BLE001 - leaking any other error fails the test
                outcomes.append(f"leak-{type(exc).__name__}")

    threads = [
        threading.Thread(target=service_writer, args=("a",)),
        threading.Thread(target=service_writer, args=("b",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(outcomes) == 2, outcomes
    assert sum(o.startswith("ok-") for o in outcomes) == 1, outcomes
    assert sum(o.startswith("conflict-") for o in outcomes) == 1, outcomes
    assert not any(o.startswith("leak-") for o in outcomes), outcomes
    session.expire_all()
    survivors = session.exec(
        select(Job).where(Job.user_id == user.id, Job.dedupe_key == key)
    ).all()
    assert len(survivors) == 1
