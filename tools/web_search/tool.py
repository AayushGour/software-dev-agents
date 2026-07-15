"""SearXNG web search — shared core used by CLI, MCP server, and local registry.

Requires a running SearXNG with JSON output enabled. In SearXNG settings.yml:
  search:
    formats: [html, json]
Set SEARXNG_URL if not on the default below.
"""

import os
import json
import urllib.parse
import urllib.request
import urllib.error

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8081")


def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Search via local SearXNG. Returns [{title, url, snippet}, ...]."""
    params = urllib.parse.urlencode({"q": query, "format": "json"})
    url = f"{SEARXNG_URL}/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-harness/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError(
                f"SearXNG at {SEARXNG_URL} returned 403 for format=json. "
                "Enable JSON output in settings.yml:\n"
                "  search:\n    formats: [html, json]\n"
                "then restart SearXNG."
            ) from e
        raise
    return [
        {
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "snippet": it.get("content", ""),
        }
        for it in data.get("results", [])[:num_results]
    ]
