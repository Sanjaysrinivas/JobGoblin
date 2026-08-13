"""Tests for ATS-friendly PDF export (design.md §8)."""

from app.services.pdf_export import render_resume_pdf


def _profile() -> dict:
    return {
        "summary": "Senior engineer with 8 years building web platforms.",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "experience": [
            {
                "company": "Acme",
                "role": "Staff Engineer",
                "start": "2020",
                "end": "Present",
                "highlights": ["Led migration to FastAPI", "Cut latency 40%"],
            }
        ],
        "education": [
            {"institution": "State University", "credential": "BSc CS", "year": "2015"}
        ],
        "projects": ["JobGoblin"],
        "certifications": ["AWS SAA"],
    }


def test_render_returns_pdf_bytes():
    data = render_resume_pdf("Jane Doe", _profile())
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"
    assert len(data) > 500


def test_render_handles_empty_profile():
    data = render_resume_pdf("Untitled", {})
    assert data[:4] == b"%PDF"


def test_render_handles_none_profile():
    data = render_resume_pdf("Untitled", None)
    assert data[:4] == b"%PDF"


def test_render_coerces_string_lists_without_crashing():
    # The model may return a lone string where a list is expected; rendering must
    # not iterate it char-by-char or crash.
    profile = {
        "summary": "ok",
        "skills": "Python",  # string, not list
        "experience": [
            {"company": "Acme", "role": "Eng", "highlights": "Did things"}
        ],
        "projects": "Solo project",
        "certifications": "AWS",
    }
    data = render_resume_pdf("Coerce", profile)
    assert data[:4] == b"%PDF"
    assert len(data) > 500


def test_render_handles_non_dict_experience_items():
    profile = {"experience": ["just a string entry"], "education": ["plain edu"]}
    data = render_resume_pdf("Odd", profile)
    assert data[:4] == b"%PDF"
