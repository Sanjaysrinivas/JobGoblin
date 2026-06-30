"""Plain-text extraction from uploaded resumes (design.md §8).

PDF -> ``pdfplumber`` (layout-aware); DOCX -> ``python-docx``. Dispatch is by
content type; anything else raises ``UnsupportedDocumentError``.
"""

import io

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

SUPPORTED_CONTENT_TYPES = {PDF_CONTENT_TYPE, *DOCX_CONTENT_TYPES}


class UnsupportedDocumentError(ValueError):
    """Raised when a content type cannot be extracted (not PDF/DOCX)."""


def _extract_pdf(data: bytes) -> str:
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _extract_docx(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs).strip()


def extract_text(data: bytes, content_type: str) -> str:
    """Extract plain text from ``data`` based on ``content_type``."""
    if content_type == PDF_CONTENT_TYPE:
        return _extract_pdf(data)
    if content_type in DOCX_CONTENT_TYPES:
        return _extract_docx(data)
    raise UnsupportedDocumentError(
        f"Unsupported document type: {content_type!r}. Upload a PDF or DOCX."
    )
