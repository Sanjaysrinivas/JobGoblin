"""Dry-run report of E2E leftovers in a workspace, plus exact-ID deletion.

Lists jobs, resumes, applications, contacts, cover letters, and outreach that
match known E2E naming patterns. Deletion is never performed by pattern: pass
explicit `--delete <kind>:<id>` values after reviewing the dry-run output.

Usage:
    python scripts/e2e_artifact_report.py            # dry-run report
    python scripts/e2e_artifact_report.py --delete job:<uuid> ...

Environment: BASE_URL (default http://localhost:8080), E2E_ADMIN_EMAIL,
E2E_ADMIN_PASSWORD (defaults match the local compose stack).
"""

import argparse
import http.cookiejar
import json
import os
import re
import sys
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@jobgoblin.local")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "goblin-demo-pass-123")

# Known E2E naming patterns (docs/pr-45-detailed-remediation.md section 7.4).
PATTERNS = [
    re.compile(r"^E2E Resume "),
    re.compile(r"^e2e-resume-"),
    re.compile(r"^E2E Co "),
    re.compile(r"^Platform Engineer (mu|[a-z0-9]{6,}-)"),
    re.compile(r"^Remediation Engineer "),
    re.compile(r"^Remediation Co "),
    re.compile(r"^Resume [AB] letters-"),
    re.compile(r"^Stage Resume stages-"),
    re.compile(r"^Taylor Recruiter "),
    re.compile(r"^example\.com/(e2e-role|remediation)-"),
]

KINDS = {
    "job": ("/api/jobs", ["title", "company_name", "source_url"]),
    "resume": ("/api/resumes", ["title", "original_filename"]),
    "application": ("/api/applications", ["status", "notes"]),
    "contact": ("/api/contacts", ["name", "company", "email"]),
    "cover-letter": ("/api/cover-letters", ["tone", "status"]),
    "outreach": ("/api/outreach", ["content"]),
}


class Client:
    """Cookie-session API client: login once, reuse the jg_session cookie."""

    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, str]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE_URL + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        with self.opener.open(req) as resp:
            return resp.status, resp.read().decode()

    def login(self) -> None:
        self.request("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})


def _matches(*values: object) -> bool:
    return any(
        isinstance(value, str) and pattern.search(value)
        for value in values
        for pattern in PATTERNS
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete",
        action="append",
        default=[],
        metavar="KIND:ID",
        help="Delete exactly this resource, e.g. job:<uuid>. Repeatable.",
    )
    args = parser.parse_args()

    client = Client()
    client.login()

    if args.delete:
        for target in args.delete:
            kind, _, resource_id = target.partition(":")
            if kind not in KINDS:
                print(f"unknown kind in {target!r}; expected one of {list(KINDS)}")
                return 2
            path = KINDS[kind][0]
            status, _ = client.request("DELETE", f"{path}/{resource_id}")
            print(f"deleted {target}: HTTP {status}")
        return 0

    found_any = False
    for kind, (path, fields) in KINDS.items():
        _, text = client.request("GET", path)
        rows = json.loads(text)
        hits = [row for row in rows if _matches(*[row.get(f) for f in fields])]
        if not hits:
            continue
        found_any = True
        print(f"\n{kind}: {len(hits)} candidate E2E artifact(s)")
        for row in hits:
            summary = " | ".join(f"{f}={row.get(f)!r}" for f in fields if row.get(f))
            print(f"  {kind}:{row['id']}  {summary}")
    if not found_any:
        print("No E2E-named artifacts found.")
    else:
        print(
            "\nDry run only. Review each row, then delete explicitly, e.g.\n"
            "  python scripts/e2e_artifact_report.py --delete job:<uuid>"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
