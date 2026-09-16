"""Operator check for Cloudflare Tunnel bring-up.

The script verifies local Caddy health and Compose tunnel configuration. It only
starts cloudflared when --start is supplied.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PUBLIC_HEALTH_RETRIES = 6
DEFAULT_RETRY_INTERVAL = 5
TUNNEL_RUNNING_TIMEOUT = 60
QUICK_TUNNEL_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


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


def cloudflared_logs(tail: int) -> subprocess.CompletedProcess[str]:
    return run(["docker", "compose", "--profile", "tunnel", "logs", f"--tail={tail}", "cloudflared"])


def find_quick_tunnel_url(log_text: str) -> str:
    matches = QUICK_TUNNEL_URL_PATTERN.findall(log_text)
    return matches[-1] if matches else ""


def wait_for_quick_tunnel_url(*, tail: int, timeout: int, interval: int) -> tuple[str, str]:
    deadline = time.monotonic() + timeout
    last_text = ""
    while time.monotonic() < deadline:
        logs = cloudflared_logs(tail)
        require_ok(logs, "failed to read cloudflared logs")
        last_text = f"{logs.stdout}\n{logs.stderr}"
        public_url = find_quick_tunnel_url(last_text)
        if public_url:
            return public_url, last_text
        print(f"quick tunnel URL is not in logs yet; retrying in {interval}s...")
        time.sleep(interval)
    return "", last_text


def main() -> int:
    dotenv = read_dotenv(repo_root() / ".env")

    parser = argparse.ArgumentParser(description="Verify Cloudflare Tunnel runtime wiring.")
    parser.add_argument(
        "--start", action="store_true", help="Start cloudflared through the Compose tunnel profile."
    )
    parser.add_argument("--local-health", default="http://localhost:8080/api/health")
    parser.add_argument(
        "--public-url",
        default=os.getenv("CLOUDFLARED_PUBLIC_URL") or dotenv.get("CLOUDFLARED_PUBLIC_URL", ""),
    )
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
        require_ok(
            run(
                ["docker", "compose", "--profile", "tunnel", "up", "-d", "cloudflared"], timeout=180
            ),
            "failed to start cloudflared",
        )
        wait_for_cloudflared_running(interval=args.retry_interval)
    else:
        if not cloudflared_running():
            raise SystemExit(
                "ERROR: cloudflared service is not running. Start the tunnel or rerun with --start."
            )

    quick_url, log_text = wait_for_quick_tunnel_url(
        tail=args.tail,
        timeout=args.timeout,
        interval=args.retry_interval,
    )
    if args.start and "error" in log_text.lower() and "no such service" not in log_text.lower():
        raise SystemExit("ERROR: cloudflared logs contain 'error'; inspect the output above.")

    public_url = args.public_url or quick_url
    if public_url:
        print(f"Shareable tunnel URL: {public_url}")
        public_health = public_url.rstrip("/") + "/api/health"
        print(f"Checking public tunnel health: {public_health}")
        print(
            get_json_with_retries(
                public_health,
                args.timeout,
                attempts=args.public_retries,
                interval=args.retry_interval,
            ).strip()
        )
    else:
        print("WARN: no trycloudflare.com URL found in cloudflared logs.")

    print("OK: Cloudflare tunnel check completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
