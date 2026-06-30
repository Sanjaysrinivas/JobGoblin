"""ATS-friendly PDF export of a parsed resume profile (design.md §8).

Uses ``fpdf2`` (pure Python — no system libraries) to emit a clean, single-column
document: plain headings, no graphics, no columns. Optimised for ATS parsers
rather than visual flair.
"""

from typing import Any

# Core-14 fonts are Latin-1 only; replace common non-Latin-1 glyphs so user text
# never crashes the renderer with an encoding error.
_REPLACEMENTS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "•": "-", "…": "...",
}


def _ascii(text: Any) -> str:
    s = "" if text is None else str(text)
    for bad, good in _REPLACEMENTS.items():
        s = s.replace(bad, good)
    return s.encode("latin-1", "replace").decode("latin-1")


def render_resume_pdf(title: str, profile: dict | None) -> bytes:
    """Render ``profile`` (a ParsedResume dict) to ATS-plain PDF bytes."""
    from fpdf import FPDF

    profile = profile or {}
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    epw = pdf.w - pdf.l_margin - pdf.r_margin

    def heading(text: str) -> None:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, _ascii(text), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10.5)

    def body(text: str, *, bullet: bool = False) -> None:
        prefix = "- " if bullet else ""
        pdf.multi_cell(epw, 5.5, _ascii(prefix + text))

    # Name / title.
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, _ascii(title or "Resume"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10.5)

    if profile.get("summary"):
        heading("Summary")
        body(profile["summary"])

    skills = profile.get("skills") or []
    if skills:
        heading("Skills")
        body(", ".join(_ascii(s) for s in skills))

    experience = profile.get("experience") or []
    if experience:
        heading("Experience")
        for item in experience:
            role = _ascii(item.get("role", ""))
            company = _ascii(item.get("company", ""))
            dates = " - ".join(
                d for d in (item.get("start"), item.get("end")) if d
            )
            pdf.set_font("Helvetica", "B", 10.5)
            header = " at ".join(p for p in (role, company) if p)
            if dates:
                header = f"{header} ({_ascii(dates)})" if header else _ascii(dates)
            pdf.multi_cell(epw, 5.5, header)
            pdf.set_font("Helvetica", size=10.5)
            for hl in item.get("highlights") or []:
                body(hl, bullet=True)
            pdf.ln(1)

    education = profile.get("education") or []
    if education:
        heading("Education")
        for item in education:
            parts = [
                item.get("credential", ""),
                item.get("institution", ""),
                item.get("year", ""),
            ]
            body(", ".join(_ascii(p) for p in parts if p))

    projects = profile.get("projects") or []
    if projects:
        heading("Projects")
        for proj in projects:
            body(_ascii(proj), bullet=True)

    certifications = profile.get("certifications") or []
    if certifications:
        heading("Certifications")
        for cert in certifications:
            body(_ascii(cert), bullet=True)

    return bytes(pdf.output())
