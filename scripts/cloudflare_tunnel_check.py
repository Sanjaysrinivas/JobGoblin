"""Operator check for Cloudflare Tunnel bring-up.

The script verifies local Caddy health and Compose tunnel configuration. It only
starts cloudflared when --start is supplied.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PUBLIC_HEALTH_RETRIES = 6
DEFAULT_RETRY_INTERVAL = 5
TUNNEL_RUNNING_TIMEOUT = 60


class HealthCheckError(Exception):
    """Raised when an HTTP health check request fails."""


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


def get_json_once(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HealthCheckError(f"{url} returned {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise HealthCheckError(f"could not reach {url}: {exc.reason}") from exc


def get_json(url: str, timeout: int) -> str:
    try:
        return get_json_once(url, timeout)
    except HealthCheckError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


def get_json_with_retries(url: str, timeout: int, *, attempts: int, interval: int) -> str:
    last_error: HealthCheckError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return get_json_once(url, timeout)
        except HealthCheckError as exc:
            last_error = exc
            if attempt == attempts:
                break
            print(
                f"Public tunnel health check failed ({attempt}/{attempts}): {exc}. "
                f"Retrying in {interval}s..."
            )
            time.sleep(interval)

    raise SystemExit(
        f"ERROR: public tunnel health check did not pass after {attempts} attempts: {last_error}"
    )


def cloudflared_running() -> bool:
    result = run(
        [
            "docker",
            "compose",
            "--profile",
            "tunnel",
            "ps",
            "--status",
            "running",
            "--services",
            "cloudflared",
        ]
    )
    require_ok(result, "failed to inspect running cloudflared service")
    return "cloudflared" in {line.strip() for line in result.stdout.splitlines() if line.strip()}


def wait_for_cloudflared_running(
    *, timeout: int = TUNNEL_RUNNING_TIMEOUT, interval: int = DEFAULT_RETRY_INTERVAL
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cloudflared_running():
            return
        print(f"cloudflared is not running yet; retrying in {interval}s...")
        time.sleep(interval)
    raise SystemExit(f"ERROR: cloudflared did not become running within {timeout}s.")


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
        "--public-retries",
        type=int,
        default=DEFAULT_PUBLIC_HEALTH_RETRIES,
        help="Number of public tunnel health attempts before failing.",
    )
    parser.add_argument(
        "--retry-interval",
        type=int,
        default=DEFAULT_RETRY_INTERVAL,
        help="Seconds to wait between tunnel readiness checks.",
    )
    parser.add_argument(
        "--tail", type=int, default=80, help="Number of cloudflared log lines to inspect."
    )
    args = parser.parse_args()
    if args.public_retries < 1:
        raise SystemExit("ERROR: --public-retries must be at least 1.")
    if args.retry_interval < 0:
        raise SystemExit("ERROR: --retry-interval must be zero or greater.")

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
        wait_for_cloudflared_running(interval=args.retry_interval)
    else:
        if not token:
            print("WARN: CLOUDFLARED_TUNNEL_TOKEN is empty; checking existing cloudflared state only.")
        if not cloudflared_running():
            raise SystemExit(
                "ERROR: cloudflared service is not running. Start the tunnel or rerun with --start."
            )

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
        print(
            get_json_with_retries(
                public_health,
                args.timeout,
                attempts=args.public_retries,
                interval=args.retry_interval,
            ).strip()
        )

    print("OK: Cloudflare tunnel check completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
