"""MCP stdio server — exposes web_search to Claude Code.

Install once:  pip install mcp
Registered in claude-code/.mcp.json. Tool appears to agents as
  mcp__web-search__web_search
"""

from mcp.server.fastmcp import FastMCP
from tool import web_search as _search

mcp = FastMCP("web-search")


@mcp.tool()
def web_search(query: str, num_results: int = 5) -> str:
    """Search the web via a local SearXNG instance. Returns ranked results as text."""
    results = _search(query, num_results)
    if not results:
        return "No results."
    return "\n\n".join(
        f"{i}. {r['title']}\n{r['url']}\n{r['snippet']}"
        for i, r in enumerate(results, 1)
    )


if __name__ == "__main__":
    mcp.run()
