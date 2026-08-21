"""MCP stdio server — exposes web search (via a local SearXNG) to Claude Code.

Two tools, with a contract:
  ensure_searxng  health-check the SearXNG backend, starting its Docker container
                  if it's down. CALL THIS BEFORE web_search.
  web_search      run a search. Self-healing: ensures the backend first (starts it if down).

Install once:  pip install mcp
Registered in claude-code/.mcp.json. Tools appear to agents as
  mcp__web-search__ensure_searxng  and  mcp__web-search__web_search
"""

from mcp.server.fastmcp import FastMCP
from tool import web_search as _search
from ensure_searxng import ensure as _ensure

mcp = FastMCP(
    "web-search",
    instructions=(
        "Web search is backed by a local, self-hosted SearXNG. web_search is "
        "self-healing: it health-checks the backend and starts its Docker container "
        "itself — just call it. ensure_searxng remains for an explicit check. If it "
        "reports the "
        "backend can't be started (no-docker / daemon-down / port-busy / failed), do "
        "NOT silently fall back: tell the user SearXNG can't start, note briefly that "
        "the native WebSearch tool is an external (Anthropic-hosted) search rather than "
        "the self-hosted/private SearXNG — so queries leave the local machine and the "
        "results differ — and ask whether to use it. Fall back to WebSearch only if the "
        "user agrees."
    ),
)


@mcp.tool()
def ensure_searxng() -> str:
    """Ensure the local SearXNG backend is running; start its Docker container if down.
    CALL THIS BEFORE web_search. Cheap when already up (one local request).

    Returns a status line:
      up           ready — go ahead and call web_search
      spawned      was down; container started and is healthy — call web_search
      no-docker    Docker CLI not found
      daemon-down  Docker installed but its daemon isn't running
      port-busy    something else holds the port but isn't JSON-capable SearXNG
      failed:...   tried to start it but it didn't become healthy

    On no-docker / daemon-down / port-busy / failed, ASK THE USER before falling back
    to the native WebSearch tool (note it's external, not the private SearXNG)."""
    return _ensure()


@mcp.tool()
def web_search(query: str, num_results: int = 5) -> str:
    """Search the web via the local SearXNG backend. Self-healing: health-checks the
    backend first and starts its Docker container if it's down (the SessionEnd hook
    stops it between sessions, so a cold start is the NORMAL case). If the backend
    can't be started (no-docker / daemon-down / port-busy / failed), returns that
    status instead of results — then do NOT silently fall back: ask the user before
    using the native (external) WebSearch tool."""
    status = _ensure()
    if not status.startswith(("up", "spawned")):
        return (
            f"SearXNG backend unavailable ({status}). Do not silently fall back: "
            "tell the user the self-hosted search can't start and ask whether to "
            "use the native WebSearch tool (external, Anthropic-hosted) instead."
        )
    results = _search(query, num_results)
    if not results:
        return "No results."
    return "\n\n".join(
        f"{i}. {r['title']}\n{r['url']}\n{r['snippet']}"
        for i, r in enumerate(results, 1)
    )


if __name__ == "__main__":
    mcp.run()
