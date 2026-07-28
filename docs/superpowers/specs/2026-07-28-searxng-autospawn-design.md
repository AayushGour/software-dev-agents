# SearXNG auto-spawn — design

**Date:** 2026-07-28
**Status:** Approved (design), pending implementation plan
**Component:** `tools/web_search/`, `claude-code/.mcp.json`, `claude-code/.claude/settings.json`

## Problem

The `web-search` MCP server queries a SearXNG instance at `SEARXNG_URL` (default
`http://localhost:8081`). SearXNG is a **separate process nobody starts** — if the
user hasn't launched it, every agent `web_search` call fails. The tool assumes an
externally-running backend, so web search silently doesn't work on a fresh machine.

Goal: the harness brings SearXNG up **on demand**, with the model deciding when,
and cleans it up at session end.

## Decisions (settled)

| Question | Decision |
|---|---|
| How SearXNG runs | **Docker** — official `searxng/searxng` image, one container |
| When it spawns | **Lazy** — only when a search is actually needed |
| Who decides to spawn | **The model** — it calls an `ensure_searxng` MCP tool; that invocation *is* the consent. No flag file, no skill. |
| Separation of concerns | `web_search` does **only** search (raises if backend down); `ensure_searxng` does **only** health-check + spawn |
| Ordering | MCP server `instructions` + tool docstring tell the model to call `ensure_searxng` before `web_search`; the raise self-heals if it's skipped |
| Docker absent | `ensure_searxng` reports it; model **asks the user first** (states the tradeoff briefly) before falling back to the native `WebSearch` tool |
| Teardown | **SessionEnd hook** → `docker stop` (deterministic, not model-dependent) |
| Redis/valkey | **Not needed** — SearXNG limiter disabled in mounted config |
| Agent impact | **None** — `mcp__web-search__web_search` name/signature unchanged |

## Architecture

Two MCP tools with a contract, one deterministic mechanism script, one teardown hook.

```
model turn:
  ensure_searxng()  ──► health-check :8081
                        up?      → return "up"
                        down?    → docker run/start + poll ready → "spawned" | error-status
  web_search(q)     ──► query SearXNG   (RAISES if down — never spawns)

session end:
  SessionEnd hook   ──► ensure_searxng.py --stop  → docker stop harness-searxng
```

### The contract (why two tools)

- `ensure_searxng` is the **only** place that spawns. Idempotent and cheap when the
  backend is already up (a single local HTTP GET), so "always call it first" is free.
- `web_search` is **pure**: it searches, and if the backend is unreachable it raises
  `RuntimeError("SearXNG not up — call ensure_searxng first")`. It contains no
  lifecycle logic.
- The model is instructed (server `instructions` + `web_search` docstring) to call
  `ensure_searxng` before its first `web_search`. If it forgets, `web_search`'s raise
  names the fix, so the model self-corrects on the next turn. **Ordering is
  self-healing, not hope-based.**
- The model choosing to call `ensure_searxng` is the consent gate — the decision to
  start a Docker container lives in the model layer, not buried inside the search tool.
- **Docker-absent is also a model-mediated decision, not an automatic fallback.** When
  `ensure_searxng` returns `no-docker` / `daemon-down` / `failed`, the model must tell
  the user SearXNG can't start and ask before switching to the native `WebSearch` tool,
  stating the consequence in one line: native WebSearch is an external (Anthropic-hosted)
  search, not the self-hosted/private SearXNG — queries leave the local machine and the
  result set differs. Fall back only on the user's OK.

## Components

### 1. `tools/web_search/ensure_searxng.py` (new — the mechanism)

Deterministic. No model needed; callable from the MCP tool, the CLI, and the hook.

```python
def ensure() -> str:
    """Return one of: 'up' | 'spawned' | 'no-docker' | 'daemon-down' | 'failed:<msg>'."""
    if _healthy(SEARXNG_URL):          # HTTP GET, verify it's actually SearXNG
        return "up"
    if not shutil.which("docker"):
        return "no-docker"
    if not _docker_daemon_up():        # `docker info` succeeds
        return "daemon-down"
    _write_settings_if_absent()        # generate settings.yml from template + secret
    _run_or_start_container()          # `docker start` if it exists, else `docker run`
    if _wait_healthy(SEARXNG_URL, timeout=25):
        return "spawned"
    return "failed:container did not become healthy in 25s"

def stop() -> None:                    # `docker stop harness-searxng` (ignore if absent)
```

- **Container:** `docker run -d --name harness-searxng -p 8081:8080 -v <cfg>:/etc/searxng searxng/searxng`
  where `<cfg>` = `tools/web_search/searxng/` (absolute path).
- **Reuse:** if a `harness-searxng` container already exists (stopped), `docker start` it
  rather than `docker run` (avoids name collision, faster).
- **Health check** (`_healthy`): GET `{url}/healthz` (SearXNG returns 200 "OK"); verify
  the response looks like SearXNG so a *different* service occupying :8081 isn't mistaken
  for it. Fall back to GET `{url}/` if `/healthz` is unavailable.
- **CLI:** `python ensure_searxng.py [--status | --start | --stop]` — `--start` = `ensure()`,
  `--status` prints without spawning, `--stop` = `stop()`. Used by the hook and for manual ops.
- **First-run image pull** (~1–2 min) happens inside the first `docker run`; the poll
  timeout covers the post-pull startup. (Optional: a longer timeout on a detected first pull.)

### 2. `tools/web_search/searxng/settings.template.yml` (new — committed) + generated `settings.yml` (gitignored)

Mounted at `/etc/searxng/settings.yml`. On first run `ensure_searxng.py` copies the
template to `settings.yml`, injecting a random `secret_key` (`secrets.token_hex(32)`).

```yaml
server:
  secret_key: "<generated on first run>"
  limiter: false            # no redis/valkey required
  public_instance: false
search:
  formats: [html, json]     # REQUIRED — tool.py queries format=json
general:
  debug: false
```

### 3. `tools/web_search/mcp_server.py` (modified — expose both tools + instructions)

```python
mcp = FastMCP(
    "web-search",
    instructions=(
        "Before your first web_search this session, call ensure_searxng to guarantee "
        "the local SearXNG backend is running. Call it again if web_search raises a "
        "'not up' error. If ensure_searxng reports Docker is unavailable "
        "(no-docker / daemon-down / failed), do NOT silently fall back: tell the user "
        "SearXNG can't start, note briefly that the native WebSearch is an external "
        "(Anthropic-hosted) search — not the self-hosted/private SearXNG, so queries "
        "leave the local machine and results differ — and ask whether to use it. Only "
        "fall back to WebSearch if the user agrees."
    ),
)

@mcp.tool()
def ensure_searxng() -> str:
    """Ensure the local SearXNG backend is running; spawn its Docker container if down.
    CALL THIS BEFORE web_search. Returns a status line: up | spawned | no-docker |
    daemon-down | failed. On no-docker/daemon-down/failed, ASK THE USER before falling
    back to the native WebSearch tool (note it's external, not the private SearXNG)."""
    return _ensure()   # from ensure_searxng.py

@mcp.tool()
def web_search(query: str, num_results: int = 5) -> str:
    """Search the web via the local SearXNG backend. Call ensure_searxng FIRST — this
    tool raises if SearXNG is not running (it does not start it)."""
    ...
```

- Server `instructions` is surfaced to the agent by Claude Code (same mechanism as the
  deepwiki server-instructions block). The clause is **also** in `web_search`'s docstring
  so Task-spawned subagents — which carry the tool schema but may not get the
  server-instructions block — still see the ordering rule.

### 4. `tools/web_search/tool.py` (modified — search-only, raise on down)

`web_search()` keeps its current query logic but **raises** instead of returning empty
when the backend is unreachable:

```python
except urllib.error.URLError:  # connection refused / DNS / timeout → backend down
    raise RuntimeError(
        f"SearXNG not reachable at {SEARXNG_URL} — call ensure_searxng first "
        "(or use the native WebSearch tool)."
    )
```

The existing 403-means-JSON-disabled branch stays. No spawn logic here.

### 5. `claude-code/.claude/settings.json` (new — teardown hook)

```json
{
  "hooks": {
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "python tools/web_search/ensure_searxng.py --stop" } ] }
    ]
  }
}
```

Deterministic teardown — fires on session close regardless of what the model did.

### 6. `.gitignore` (modified)

Add `tools/web_search/searxng/settings.yml` (contains the generated secret).

### 7. Docs (modified)

`tools/web_search/README.md` + `tools/README.md`: document the two-tool contract,
the ordering rule, Docker requirement, and teardown.

## Error handling / edge cases

| Case | Behavior |
|---|---|
| Backend already up | `ensure_searxng` → "up" immediately (one GET); `web_search` works |
| Docker not installed | `ensure_searxng` → "no-docker"; model asks the user (states the tradeoff) before falling back to native WebSearch |
| Docker installed, daemon stopped | `ensure_searxng` → "daemon-down" (message: start Docker Desktop); model asks the user before falling back to native WebSearch |
| Stopped `harness-searxng` container exists | `docker start` it, not `run` — no name collision |
| :8081 occupied by a non-SearXNG service | health check verifies identity → treats as down → spawn on a name that maps :8081 (documented limitation: user must free the port) |
| First-ever run (image not pulled) | pull happens in first `docker run`; poll timeout accounts for startup |
| Model calls `web_search` without `ensure_searxng` | `web_search` raises with the fix in the message → model self-corrects |
| Container fails to become healthy | `ensure_searxng` → "failed:<msg>"; model reports + asks the user before falling back to WebSearch |

## Testing

- **Unit (no Docker):** `ensure()` returns `no-docker` when `shutil.which("docker")` is
  mocked absent; `daemon-down` when `docker info` mocked failing; health-check identity
  logic; `web_search` raises the expected message on `URLError`; status strings exact.
- **Integration (Docker present):** cold call → `ensure()` spawns, `_wait_healthy` passes,
  `web_search` returns results; second `ensure()` → "up" fast; `--stop` stops the container;
  re-`ensure()` after stop → `docker start` path.
- **Contract:** with backend down, `web_search` raises (does not spawn); `ensure_searxng`
  is the only spawner.

## Out of scope / future

- **Generic per-tool spawn pattern.** `ensure_searxng.py` is structured (health → check
  deps → run/start → poll) so a later generic `ensure_tool(manifest)` — image, port,
  health path per tool — can subsume it. Not built now (YAGNI); one tool, one script today.
- **Local (Hermes) runtime.** `tools/registry.py` exposes `web_search` as a plain callable;
  wiring `ensure` into that runtime is a follow-up (the hook + MCP tool are Claude-Code-side).

## Files touched

- `tools/web_search/ensure_searxng.py` — new
- `tools/web_search/searxng/settings.template.yml` — new
- `tools/web_search/mcp_server.py` — modified (2 tools + instructions)
- `tools/web_search/tool.py` — modified (raise on down)
- `claude-code/.claude/settings.json` — new (SessionEnd hook)
- `.gitignore` — modified (generated settings.yml)
- `tools/web_search/README.md`, `tools/README.md` — modified (docs)
