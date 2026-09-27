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
  reloaded     was up on a stale settings.yml; re-rendered it and restarted
  no-docker    docker CLI not found
  daemon-down  docker installed but the daemon isn't running
  port-busy    something holds the port but isn't JSON-capable SearXNG (free it / enable JSON)
  failed:<m>   spawn attempted but the container didn't become healthy in time
"""

import os
import re
import sys
import json
import time
import shutil
import hashlib
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
_STAMP_PREFIX = "# template-sha256: "

# Statuses that mean "the backend is serving" — callers gate on these rather than
# re-listing the strings, so adding a status can't silently leave a caller reporting a
# healthy backend as unavailable.
HEALTHY = ("up", "spawned", "reloaded")

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


def _json_ok(timeout: int = 9) -> bool:
    """True if SEARXNG_URL answers a format=json search — what web_search actually needs.

    Pinned to a single engine on purpose. mcp_server calls ensure() before EVERY
    web_search, so an unrestricted probe fanned this query out to the whole general
    pool and doubled the scrape traffic each search put on the engines — a direct
    contributor to the 429/CAPTCHA suspensions that degrade result quality. Only
    three things are being checked here (the socket answers, format=json is not 403'd,
    the body parses as JSON), and one cheap engine proves all three; an empty result
    set is still a pass. wikipedia is enabled in SearXNG's shipped defaults and is not
    rate-limited, so it costs the scraped engines nothing.

    2026-09-06: bumped from 5s to 9s. settings.yml raised outgoing.request_timeout to
    6.0s, so a legitimate response could take over 5s and this probe was timing out on
    genuinely-healthy-but-slow responses; urllib raised a timeout Exception (caught
    below, returns False) and ensure() then misdiagnosed the backend as "port-busy" via
    _listening() succeeding on a fast root-path probe. The single-engine probe above
    makes that far less likely, but keep the headroom: a container that is still
    booting is slow to answer anything.
    """
    q = urllib.parse.urlencode({"q": "healthcheck", "format": "json", "engines": "wikipedia"})
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


def _sync_settings() -> bool:
    """Render settings.yml from the template, preserving any secret already generated.

    Returns True if settings.yml was created or rewritten — i.e. a running container is
    now serving a stale config and needs restarting — and False if it was already
    current.

    settings.yml is gitignored (it holds the generated secret), so installing or
    updating the harness only ever ships settings.template.yml. The previous
    write-if-absent behaviour meant an existing install stayed pinned forever to
    whichever template it first ran with, and template fixes (engine pool, timeouts)
    silently never reached it. Stamping the rendered file with the template's digest
    makes that drift detectable on every ensure().

    Best-effort: on any filesystem error this reports "no change" rather than raising,
    so a config refresh can never take down an otherwise working backend. A first-run
    failure still surfaces, as the container then comes up without JSON enabled and
    ensure() returns "failed:".
    """
    try:
        stamp = f"{_STAMP_PREFIX}{hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()}\n"
        secret = None
        if SETTINGS.exists():
            current = SETTINGS.read_text()
            if current.endswith(stamp):
                return False
            m = re.search(r'secret_key:\s*"([^"]+)"', current)
            if m and m.group(1) != "__SECRET_KEY__":
                secret = m.group(1)
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        rendered = TEMPLATE.read_text().replace("__SECRET_KEY__", secret or secrets.token_hex(32))
        SETTINGS.write_text(f"{rendered}\n{stamp}")
        return True
    except OSError:
        return False


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


def _restart_container() -> bool:
    """Restart the harness container so a re-rendered settings.yml takes effect."""
    docker = _docker_bin()
    if not docker or not _container_exists():
        return False
    try:
        return subprocess.run(
            [docker, "restart", CONTAINER], capture_output=True, timeout=60
        ).returncode == 0
    except Exception:
        return False


def _wait_json(timeout: int = 45) -> bool:
    # Per-attempt timeout matches _json_ok's default (9s, see its docstring) — a
    # shorter per-attempt timeout here could make every single poll attempt time out
    # (rather than genuinely fail) whenever a fanned-out engine legitimately takes
    # close to outgoing.request_timeout, starving _wait_json of a real answer.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _json_ok(timeout=9):
            return True
        time.sleep(1.5)
    return False


def ensure() -> str:
    """Guarantee a JSON-capable SearXNG at SEARXNG_URL. See module docstring for statuses."""
    drifted = _sync_settings()
    if _json_ok():
        if not drifted:
            return "up"
        # Up, but on the settings.yml we just replaced. Restart so the current engine
        # pool and timeouts apply. If the restart can't be attempted (no docker, or the
        # container isn't ours), keep serving the stale config rather than failing.
        if not _restart_container():
            return "up"
        return "reloaded" if _wait_json() else "failed:container did not return after a config reload"
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
