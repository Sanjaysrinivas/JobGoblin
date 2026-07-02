"""End-to-end runtime smoke test for JobGoblin's operator path.

This script creates smoke-test records in the configured local environment. It
does not delete or mutate existing user records.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

DEFAULT_API_BASE = "http://localhost:8080/api"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ApiClient:
    def __init__(self, base_url: str, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        data = body
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"ERROR: {method} {url} returned {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"ERROR: could not reach {url}: {exc.reason}") from exc


def make_docx(resume_text: str) -> bytes:
    escaped = (
        resume_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "</w:t></w:r></w:p><w:p><w:r><w:t>")
    )
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{escaped}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
            docx.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
            )
            docx.writestr(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>
""",
            )
            docx.writestr("word/document.xml", document_xml)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def multipart_file(
    field_name: str, filename: str, content_type: str, data: bytes
) -> tuple[bytes, str]:
    boundary = f"jobgoblin-smoke-{uuid.uuid4().hex}"
    lines = [
        f"--{boundary}\r\n".encode(),
        (
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        ).encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        data,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(lines), boundary


def require_field(body: dict[str, Any], field: str, label: str) -> Any:
    value = body.get(field)
    if value in (None, "", []):
        raise SystemExit(f"ERROR: {label} response did not include a usable {field!r}: {body}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test parsing, analysis, and cover-letter generation."
    )
    parser.add_argument("--api-base", default=os.getenv("RUNTIME_SMOKE_BASE_URL", DEFAULT_API_BASE))
    parser.add_argument(
        "--email", default=os.getenv("RUNTIME_SMOKE_EMAIL") or os.getenv("ADMIN_EMAIL")
    )
    parser.add_argument(
        "--password", default=os.getenv("RUNTIME_SMOKE_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    )
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    if not args.email or not args.password:
        raise SystemExit(
            "ERROR: provide --email/--password or set RUNTIME_SMOKE_EMAIL and "
            "RUNTIME_SMOKE_PASSWORD. A non-MFA smoke admin is required."
        )

    client = ApiClient(args.api_base, args.timeout)

    print("Checking API health...")
    health = client.request("GET", "/health")
    if not isinstance(health, dict):
        raise SystemExit(f"ERROR: unexpected health response: {health}")

    print("Logging in...")
    login = client.request(
        "POST", "/auth/login", payload={"email": args.email, "password": args.password}
    )
    if isinstance(login, dict) and login.get("mfa_required"):
        raise SystemExit("ERROR: smoke user requires MFA. Use a non-MFA local smoke admin.")
    require_field(login, "email", "login")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    resume_text = """Jordan Runtime
Backend engineer with Python, FastAPI, PostgreSQL, Docker, and OAuth experience.
Built self-hosted AI tools with Ollama, Cloudflare Tunnel, CI, and runtime smoke checks.
"""

    print("Uploading and parsing smoke resume...")
    docx_data = make_docx(resume_text)
    body, boundary = multipart_file(
        "file", f"runtime-smoke-{stamp}.docx", DOCX_CONTENT_TYPE, docx_data
    )
    resume = client.request(
        "POST",
        "/resumes/upload",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resume_id = require_field(resume, "id", "resume upload")
    if not resume.get("parsed_json"):
        print("Inline parse was empty; requesting explicit re-parse...")
        resume = client.request("POST", f"/resumes/{resume_id}/parse")
    require_field(resume, "parsed_json", "resume parse")

    print("Creating smoke job...")
    job = client.request(
        "POST",
        "/jobs",
        payload={
            "company_name": "Runtime Smoke Co",
            "title": "Platform Engineer",
            "location": "Remote",
            "work_mode": "remote",
            "source": "other",
            "description": (
                "We need a Python and FastAPI platform engineer with PostgreSQL, Docker, "
                "OAuth, Cloudflare Tunnel, CI, and local AI runtime experience."
            ),
            "priority": "low",
        },
    )
    job_id = require_field(job, "id", "job create")

    print("Running resume-to-job analysis...")
    analysis = client.request(
        "POST",
        "/analysis/resume-job",
        payload={"resume_id": resume_id, "job_id": job_id},
    )
    require_field(analysis, "overall_score", "analysis")
    require_field(analysis, "explanation", "analysis")

    print("Generating cover letter...")
    cover_letter = client.request(
        "POST",
        "/cover-letters",
        payload={"resume_id": resume_id, "job_id": job_id, "tone": "professional"},
    )
    require_field(cover_letter, "content", "cover letter")

    print("OK: runtime smoke passed.")
    print(f"Resume ID: {resume_id}")
    print(f"Job ID: {job_id}")
    print(f"Analysis ID: {analysis.get('id')}")
    print(f"Cover letter ID: {cover_letter.get('id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
