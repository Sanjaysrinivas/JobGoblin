"""Operator check for the local Ollama runtime.

The script is intentionally non-destructive. By default it verifies Docker
Compose configuration, confirms the Ollama service is running, and checks model
presence. Pass --pull to download missing models and --start to start Ollama.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_FAST_MODEL = "llama3.2:3b"


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


def running_services() -> set[str]:
    result = run(["docker", "compose", "ps", "--status", "running", "--services"])
    require_ok(result, "docker compose ps failed")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def model_names() -> set[str]:
    result = run(["docker", "compose", "exec", "-T", "ollama", "ollama", "list"])
    require_ok(result, "could not list Ollama models; is the ollama service healthy?")
    names: set[str] = set()
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            names.add(parts[0])
    return names


def ensure_model(model: str, *, pull: bool) -> None:
    names = model_names()
    if model not in names:
        if not pull:
            raise SystemExit(
                f"ERROR: Ollama model {model!r} is missing. "
                "Run this script again with --pull to download it."
            )
        result = run(
            ["docker", "compose", "exec", "-T", "ollama", "ollama", "pull", model], timeout=3600
        )
        require_ok(result, f"failed to pull Ollama model {model}")

    result = run(["docker", "compose", "exec", "-T", "ollama", "ollama", "show", model])
    require_ok(result, f"failed to inspect Ollama model {model}")


def generate_probe(model: str) -> None:
    result = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "ollama",
            "ollama",
            "run",
            model,
            "Reply with exactly: ok",
        ],
        timeout=180,
    )
    require_ok(result, f"generation probe failed for {model}")
    if "ok" not in result.stdout.lower():
        raise SystemExit("ERROR: generation probe completed but did not contain 'ok'")


def main() -> int:
    dotenv = read_dotenv(repo_root() / ".env")
    parser = argparse.ArgumentParser(description="Verify JobGoblin's Ollama runtime.")
    parser.add_argument(
        "--model", default=os.getenv("OLLAMA_MODEL") or dotenv.get("OLLAMA_MODEL") or DEFAULT_MODEL
    )
    parser.add_argument(
        "--fast-model",
        default=os.getenv("OLLAMA_FAST_MODEL")
        or dotenv.get("OLLAMA_FAST_MODEL")
        or DEFAULT_FAST_MODEL,
        help="Fast/secondary model to verify. Pass an empty string to skip.",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the ollama Compose service if it is not running.",
    )
    parser.add_argument(
        "--pull", action="store_true", help="Pull missing models before verification."
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Run a tiny generation probe after model verification.",
    )
    args = parser.parse_args()

    require_ok(
        run(["docker", "compose", "config", "--quiet"]), "docker compose config validation failed"
    )

    services = running_services()
    if "ollama" not in services:
        if not args.start:
            raise SystemExit("ERROR: ollama is not running. Start the stack or rerun with --start.")
        require_ok(
            run(["docker", "compose", "up", "-d", "ollama"]), "failed to start ollama service"
        )

    ensure_model(args.model, pull=args.pull)
    if args.fast_model:
        ensure_model(args.fast_model, pull=args.pull)
    if args.generate:
        generate_probe(args.model)

    print("OK: Ollama runtime check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
