# web_search (SearXNG)

Web search via a **local, self-hosted SearXNG**, auto-managed in Docker. `tool.py` is
the search core; `ensure_searxng.py` manages the backend container; the MCP server wraps
both. Design: `docs/superpowers/specs/2026-07-28-searxng-autospawn-design.md`.

## Two tools, one contract
- **`ensure_searxng`** — health-checks the backend; if it's down, starts the
  `searxng/searxng` container (JSON enabled, limiter off → no redis). Idempotent and
  cheap when already up. **Call it before `web_search`.**
- **`web_search`** — search only. **Raises** if SearXNG isn't reachable; it does not
  start it. The raise message names the fix, so a skipped `ensure_searxng` self-corrects.

The MCP server's `instructions` tell the agent to call `ensure_searxng` first, and — if
the backend can't start (`no-docker` / `daemon-down` / `port-busy` / `failed`) — to ask
the user before falling back to the native WebSearch tool (external, not the private one).

## Config
`SEARXNG_URL` — default `http://localhost:8081`. The managed container's config lives in
`searxng/settings.template.yml` (committed); `searxng/settings.yml` is generated on first
run with a real `secret_key` and is **gitignored**.

## Lifecycle
```
first search → ensure_searxng: down → docker run (pulls image 1st time) → up → web_search
later        → ensure_searxng: up (fast) → web_search
session end  → SessionEnd hook → ensure_searxng.py --stop → docker stop
next session → ensure_searxng: down → docker start (image cached) → up
```
Teardown hook: `claude-code/.claude/settings.json` (SessionEnd → `--stop`).

## CLI (manual ops / hook)
```bash
python3 tools/web_search/ensure_searxng.py --start    # ensure up (spawn if needed)
python3 tools/web_search/ensure_searxng.py --status   # up | down (no spawn)
python3 tools/web_search/ensure_searxng.py --stop      # docker stop harness-searxng
python3 tools/web_search/cli.py "query"                # search, no MCP (backend must be up)
```

## Claude Code
Registered in `claude-code/.mcp.json` and launched as
`uv run --with "mcp<2" python .../mcp_server.py` — `uv` provides the interpreter **and**
`mcp` (pinned `<2`, since `mcp` 2.0 moved `mcp.server.fastmcp`), so it works even when the
system `python`/`mcp` are missing. Needs `uv` + Docker. Agents call
`mcp__web-search__ensure_searxng` then `mcp__web-search__web_search`.

## Requires
- **Docker** (daemon running) — for auto-spawn. Without it, `ensure_searxng` reports
  `no-docker`/`daemon-down` and the agent asks before using native WebSearch.
- **Port 8081 free** — if another SearXNG without JSON already holds it, `ensure_searxng`
  returns `port-busy`; enable `search.formats: [html, json]` on that instance or free the port.

## Tests
```bash
PYTHONPATH=tools/web_search python3 -m unittest test_ensure_searxng -v   # unit (no Docker)
```

## Smoke test
```bash
python3 tools/web_search/ensure_searxng.py --start && python3 tools/web_search/cli.py "claude opus 4.8" 3
```
Returns `[{title, url, snippet}]` (CLI prints numbered).
