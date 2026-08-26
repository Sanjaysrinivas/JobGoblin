"""Plain-text extraction from uploaded resumes (design.md §8).

PDF -> ``pdfplumber`` (layout-aware); DOCX -> ``python-docx``. Dispatch is by
content type. Unknown types raise ``UnsupportedDocumentError``; a corrupt or
malformed file of a supported type raises ``ExtractionError``.

Only ``.docx`` (Office Open XML) is supported — python-docx cannot read the
legacy ``.doc`` binary format, so we do not advertise it.
"""

import io

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

SUPPORTED_CONTENT_TYPES = {PDF_CONTENT_TYPE, *DOCX_CONTENT_TYPES}


class UnsupportedDocumentError(ValueError):
    """Raised when a content type cannot be extracted (not PDF/DOCX)."""


class ExtractionError(ValueError):
    """Raised when a supported file is corrupt/malformed and cannot be parsed."""


def _extract_pdf(data: bytes) -> str:
    import pdfplumber

    try:
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()
    except Exception as exc:  # pdfplumber/pdfminer raise a variety of errors
        raise ExtractionError("Could not read the PDF file.") from exc


def _extract_docx(data: bytes) -> str:
    from docx import Document
    from docx.table import Table

    try:
        document = Document(io.BytesIO(data))
        blocks: list[str] = []
        for item in document.iter_inner_content():
            if isinstance(item, Table):
                blocks.extend(
                    cell.text.strip()
                    for row in item.rows
                    for cell in row.cells
                    if cell.text.strip()
                )
            elif item.text.strip():
                blocks.append(item.text.strip())
        return "\n".join(blocks).strip()
    except Exception as exc:  # PackageNotFoundError, BadZipFile, etc.
        raise ExtractionError("Could not read the DOCX file.") from exc


def extract_text(data: bytes, content_type: str) -> str:
    """Extract plain text from ``data`` based on ``content_type``.

    Raises ``UnsupportedDocumentError`` for unknown content types and
    ``ExtractionError`` when a supported file is corrupt/unreadable.
    """
    if content_type == PDF_CONTENT_TYPE:
        return _extract_pdf(data)
    if content_type in DOCX_CONTENT_TYPES:
        return _extract_docx(data)
    raise UnsupportedDocumentError(
        f"Unsupported document type: {content_type!r}. Upload a PDF or DOCX."
    )
