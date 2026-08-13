"""End-to-end runtime smoke test for JobGoblin's operator path.

This script creates smoke-test records in the configured local environment. It
does not delete or mutate existing user records.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from typing import Any

DEFAULT_API_BASE = "http://localhost:8080/api"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_ERROR_BODY = 500


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
                return decode_json_response(method, url, response.read())
        except urllib.error.HTTPError as exc:
            detail = truncate_text(exc.read().decode("utf-8", errors="replace"))
            raise SystemExit(f"ERROR: {method} {url} returned {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"ERROR: could not reach {url}: {exc.reason}") from exc


def truncate_text(text: str, *, limit: int = MAX_ERROR_BODY) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        return "<empty>"
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def format_value(value: Any) -> str:
    if value is None:
        return "<empty>"
    try:
        return truncate_text(json.dumps(value, sort_keys=True, default=str))
    except TypeError:
        return truncate_text(str(value))


def decode_json_response(method: str, url: str, raw: bytes) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"ERROR: {method} {url} returned invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {truncate_text(text)}"
        ) from exc


def require_object(body: Any, label: str) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise SystemExit(
            f"ERROR: {label} response must be a JSON object; "
            f"got {type(body).__name__}: {format_value(body)}"
        )
    return body


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
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as docx:
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
    return buffer.getvalue()


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


def require_field(body: Any, field: str, label: str) -> Any:
    response = require_object(body, label)
    value = response.get(field)
    if value in (None, "", []):
        raise SystemExit(
            f"ERROR: {label} response did not include a usable {field!r}: "
            f"{format_value(response)}"
        )
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
    require_object(client.request("GET", "/health"), "health")

    print("Logging in...")
    login = require_object(
        client.request(
            "POST", "/auth/login", payload={"email": args.email, "password": args.password}
        ),
        "login",
    )
    if login.get("mfa_required"):
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
    resume = require_object(
        client.request(
            "POST",
            "/resumes/upload",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        ),
        "resume upload",
    )
    resume_id = require_field(resume, "id", "resume upload")
    if not resume.get("parsed_json"):
        print("Inline parse was empty; requesting explicit re-parse...")
        resume = require_object(
            client.request("POST", f"/resumes/{resume_id}/parse"), "resume parse"
        )
    require_field(resume, "parsed_json", "resume parse")

    print("Creating smoke job...")
    job = require_object(
        client.request(
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
        ),
        "job create",
    )
    job_id = require_field(job, "id", "job create")

    print("Running resume-to-job analysis...")
    analysis = require_object(
        client.request(
            "POST",
            "/analysis/resume-job",
            payload={"resume_id": resume_id, "job_id": job_id},
        ),
        "analysis",
    )
    require_field(analysis, "overall_score", "analysis")
    require_field(analysis, "explanation", "analysis")

    print("Generating cover letter...")
    cover_letter = require_object(
        client.request(
            "POST",
            "/cover-letters",
            payload={"resume_id": resume_id, "job_id": job_id, "tone": "professional"},
        ),
        "cover letter",
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
