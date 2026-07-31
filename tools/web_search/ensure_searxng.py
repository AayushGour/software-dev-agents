"""Ensure a local SearXNG backend is running for the web_search tool.

Health-checks SEARXNG_URL; if it's not answering JSON, spawns the official
searxng/searxng Docker container with a config that (a) enables JSON output —
required by tool.py — and (b) disables the limiter, so no redis/valkey is needed.
Idempotent and cheap when the backend is already up. Also the teardown entrypoint
for the SessionEnd hook.

The MCP `ensure_searxng` tool calls ensure(); the SessionEnd hook calls this as a
CLI (`--stop`). See docs/superpowers/specs/2026-07-28-searxng-autospawn-design.md.

ensure() statuses:
  up           backend reachable and JSON-capable — ready for web_search
  spawned      was down; container started and is now JSON-healthy
  no-docker    docker CLI not found
  daemon-down  docker installed but the daemon isn't running
  port-busy    something holds the port but isn't JSON-capable SearXNG (free it / enable JSON)
  failed:<m>   spawn attempted but the container didn't become healthy in time
"""

import os
import sys
import json
import time
import shutil
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8081")
CONTAINER = "harness-searxng"
IMAGE = "searxng/searxng"

_HERE = Path(__file__).resolve().parent
CFG_DIR = _HERE / "searxng"
TEMPLATE = CFG_DIR / "settings.template.yml"
SETTINGS = CFG_DIR / "settings.yml"
_PORT = urllib.parse.urlparse(SEARXNG_URL).port or 8081
_UA = {"User-Agent": "ai-harness/1.0"}

# Claude Code launched from a GUI can hand the MCP server a stripped PATH that omits
# docker. Fall back to the usual install locations before giving up.
_DOCKER_CANDIDATES = (
    "/usr/local/bin/docker",
    "/opt/homebrew/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
    "/Applications/OrbStack.app/Contents/MacOS/xbin/docker",
)


def _docker_bin():
    """Resolve the docker executable: PATH first, then common install dirs. None if absent.
    (os.path.exists follows symlinks, so a dangling symlink is skipped, not returned.)"""
    found = shutil.which("docker")
    if found:
        return found
    for p in _DOCKER_CANDIDATES:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p
    return None


def _json_ok(timeout: int = 5) -> bool:
    """True if SEARXNG_URL answers a format=json search — what web_search actually needs."""
    q = urllib.parse.urlencode({"q": "healthcheck", "format": "json"})
    req = urllib.request.Request(f"{SEARXNG_URL}/search?{q}", headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            json.load(r)
        return True
    except Exception:
        return False


def _listening(timeout: int = 2) -> bool:
    """True if anything answers HTTP on SEARXNG_URL at all (even a 403)."""
    try:
        urllib.request.urlopen(urllib.request.Request(SEARXNG_URL, headers=_UA), timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # it answered with a status code → something is there
    except Exception:
        return False


def _docker_daemon_up() -> bool:
    docker = _docker_bin()
    if not docker:
        return False
    try:
        return subprocess.run([docker, "info"], capture_output=True, timeout=15).returncode == 0
    except Exception:
        return False


def _container_exists() -> bool:
    docker = _docker_bin()
    if not docker:
        return False
    try:
        out = subprocess.run(
            [docker, "ps", "-aq", "-f", f"name=^{CONTAINER}$"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        return bool(out)
    except Exception:
        return False


def _write_settings_if_absent() -> None:
    """Materialize settings.yml from the template on first run, injecting a real secret."""
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    if SETTINGS.exists():
        return
    SETTINGS.write_text(TEMPLATE.read_text().replace("__SECRET_KEY__", secrets.token_hex(32)))


def _start_container() -> None:
    """Start the harness container — reuse a stopped one, else create it."""
    docker = _docker_bin()
    if _container_exists():
        subprocess.run([docker, "start", CONTAINER], capture_output=True, timeout=30)
    else:
        subprocess.run(
            [docker, "run", "-d", "--name", CONTAINER,
             "-p", f"{_PORT}:8080", "-v", f"{CFG_DIR}:/etc/searxng", IMAGE],
            capture_output=True, timeout=60,
        )


def _wait_json(timeout: int = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _json_ok(timeout=3):
            return True
        time.sleep(1.5)
    return False


def ensure() -> str:
    """Guarantee a JSON-capable SearXNG at SEARXNG_URL. See module docstring for statuses."""
    if _json_ok():
        return "up"
    if _listening():
        return (
            f"port-busy: something on {SEARXNG_URL} answered but is not a JSON-capable "
            "SearXNG. Enable `search.formats: [html, json]` on it and restart, or free "
            "the port so the harness can manage its own container."
        )
    if not _docker_bin():
        return "no-docker"
    if not _docker_daemon_up():
        return "daemon-down"
    _write_settings_if_absent()
    _start_container()
    return "spawned" if _wait_json() else "failed:container did not become JSON-healthy in time"


def stop() -> None:
    docker = _docker_bin()
    if docker:
        subprocess.run([docker, "stop", CONTAINER], capture_output=True, timeout=30)


def _main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "--start"
    if arg == "--stop":
        stop()
        print("stopped")
        return 0
    if arg == "--status":
        print("up" if _json_ok() else "down")
        return 0
    if arg == "--start":
        print(ensure())
        return 0
    print(f"unknown arg: {arg} (use --start | --stop | --status)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
