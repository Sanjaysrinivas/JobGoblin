"""Equivalence fixtures: the job-identity migration's frozen logic must keep
producing the same keys as the runtime service (it cannot import app code)."""

import importlib.util
from pathlib import Path

import pytest

from app.services.job_identity import canonical_job_url, job_dedupe_key, normalized_phrase

_migration_path = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "a5b6c7d8e9f0_enforce_resume_and_job_identity.py"
)
_spec = importlib.util.spec_from_file_location("job_identity_migration", _migration_path)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)

URL_CASES = [
    "https://Example.com/Jobs/42/",
    "http://www.example.com/careers/senior-engineer",
    "https://example.com/jobs?utm_source=linkedin&ref=board",
    "https://example.com/jobs?gclid=abc&fbclid=def&q=python",
    "https://example.com:8443/jobs/42?b=2&a=1",
    "https://example.com/jobs/café-manager",
    "not a url at all",
    "",
]


@pytest.mark.parametrize("value", URL_CASES)
def test_canonical_url_matches_migration(value: str):
    assert canonical_job_url(value) == migration._canonical_url(value)


IDENTITY_CASES = [
    (
        "https://Example.com/Jobs/42/?utm_medium=social",
        "Acme GmbH",
        "Senior Platform Engineer",
        "Berlin, DE",
    ),
    (None, "Acme GmbH", "Senior Platform Engineer", "Berlin, DE"),
    (None, "ACME gmbh", "senior PLATFORM engineer", None),
    (None, "Café R&D", "Engineer (C++)", "Zürich"),
    ("https://example.com", "", "", ""),
]


@pytest.mark.parametrize(("source_url", "company", "title", "location"), IDENTITY_CASES)
def test_job_dedupe_key_matches_migration(source_url, company, title, location):
    assert job_dedupe_key(source_url, company, title, location) == migration._job_key(
        source_url, company, title, location
    )


def test_normalized_phrase_matches_migration():
    for value in ("Café R&D", "  spaced   out  ", "C++ / C# / .NET"):
        assert normalized_phrase(value) == migration._normalized(value)
