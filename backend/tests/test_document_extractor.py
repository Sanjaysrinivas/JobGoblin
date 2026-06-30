"""Tests for plain-text extraction from PDF and DOCX (design.md §8)."""

import pytest

from app.services.document_extractor import UnsupportedDocumentError, extract_text
from tests.sample_docs import (
    DOCX_CONTENT_TYPE,
    PDF_CONTENT_TYPE,
    make_docx_bytes,
    make_pdf_bytes,
)


def test_extract_pdf_text():
    data = make_pdf_bytes("Hello PDF\nSecond line")
    text = extract_text(data, PDF_CONTENT_TYPE)
    assert "Hello PDF" in text
    assert "Second line" in text


def test_extract_docx_text():
    data = make_docx_bytes("Hello DOCX\nAnother line")
    text = extract_text(data, DOCX_CONTENT_TYPE)
    assert "Hello DOCX" in text
    assert "Another line" in text


def test_unsupported_content_type_raises():
    with pytest.raises(UnsupportedDocumentError):
        extract_text(b"plain", "text/plain")
