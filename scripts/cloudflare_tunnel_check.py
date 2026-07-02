"""Operator check for Cloudflare Tunnel bring-up.

The script verifies local Caddy health and Compose tunnel configuration. It only
starts cloudflared when --start is supplied.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def run(command: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    print(f"$ {' '.join(command)}")
    result = subprocess.run(
        command,
        cwd=repo_root(),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result


def require_ok(result: subprocess.CompletedProcess[str], message: str) -> None:
    if result.returncode != 0:
        raise SystemExit(f"ERROR: {message}")


def get_json(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"ERROR: {url} returned {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"ERROR: could not reach {url}: {exc.reason}") from exc


def main() -> int:
    dotenv = read_dotenv(repo_root() / ".env")
    token = os.getenv("CLOUDFLARED_TUNNEL_TOKEN") or dotenv.get("CLOUDFLARED_TUNNEL_TOKEN", "")

    parser = argparse.ArgumentParser(description="Verify Cloudflare Tunnel runtime wiring.")
    parser.add_argument(
        "--start", action="store_true", help="Start cloudflared through the Compose tunnel profile."
    )
    parser.add_argument("--local-health", default="http://localhost:8080/api/health")
    parser.add_argument("--public-url", default=os.getenv("CLOUDFLARED_PUBLIC_URL", ""))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--tail", type=int, default=80, help="Number of cloudflared log lines to inspect."
    )
    args = parser.parse_args()

    require_ok(
        run(["docker", "compose", "config", "--quiet"]), "docker compose config validation failed"
    )

    print(f"Checking local origin health: {args.local_health}")
    print(get_json(args.local_health, args.timeout).strip())

    if args.start:
        if not token:
            raise SystemExit(
                "ERROR: CLOUDFLARED_TUNNEL_TOKEN is empty; refusing to start cloudflared."
            )
        require_ok(
            run(
                ["docker", "compose", "--profile", "tunnel", "up", "-d", "cloudflared"], timeout=180
            ),
            "failed to start cloudflared",
        )
    elif not token:
        print("WARN: CLOUDFLARED_TUNNEL_TOKEN is empty. Skipping tunnel start verification.")

    ps = run(["docker", "compose", "--profile", "tunnel", "ps", "cloudflared"])
    require_ok(ps, "failed to inspect cloudflared service")

    logs = run(
        ["docker", "compose", "--profile", "tunnel", "logs", f"--tail={args.tail}", "cloudflared"]
    )
    require_ok(logs, "failed to read cloudflared logs")
    log_text = f"{logs.stdout}\n{logs.stderr}".lower()
    if args.start and "error" in log_text and "no such service" not in log_text:
        raise SystemExit("ERROR: cloudflared logs contain 'error'; inspect the output above.")

    if args.public_url:
        public_health = args.public_url.rstrip("/") + "/api/health"
        print(f"Checking public tunnel health: {public_health}")
        print(get_json(public_health, args.timeout).strip())

    print("OK: Cloudflare tunnel check completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
