"""Tests for the email allowlist helper (private-tool access gate)."""

from app.core import allowlist
from app.core.config import Settings


def test_empty_allowlist_admits_nobody():
    settings = Settings(allowed_emails="")
    assert allowlist.is_allowed("anyone@example.com", settings) is False


def test_allowlist_admits_listed_email_case_insensitive():
    settings = Settings(allowed_emails="Alice@Example.com, bob@example.com")
    assert allowlist.is_allowed("alice@example.com", settings) is True
    assert allowlist.is_allowed("ALICE@EXAMPLE.COM", settings) is True
    assert allowlist.is_allowed("  bob@example.com  ", settings) is True


def test_allowlist_rejects_unlisted_email():
    settings = Settings(allowed_emails="alice@example.com")
    assert allowlist.is_allowed("carol@example.com", settings) is False
