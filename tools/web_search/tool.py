"""SearXNG web search — shared core used by CLI, MCP server, and local registry.

Search only: this raises if SearXNG isn't reachable — it never starts it. The MCP
`ensure_searxng` tool (ensure_searxng.py) is responsible for bringing the backend up
before this is called. Requires a running SearXNG with JSON output enabled. In
SearXNG settings.yml:
  search:
    formats: [html, json]
Set SEARXNG_URL if not on the default below.
"""

import os
import json
import time
import threading
import urllib.parse
import urllib.request
import urllib.error
from collections import OrderedDict

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8081")

# --- Burst control -----------------------------------------------------------
# SearXNG reaches the upstream engines by scraping their public endpoints from one
# egress IP. The research fan-out spawns several agents that search at the same
# moment, so a handful of agent-level queries become a burst of near-simultaneous
# scrapes against the same few engines; they answer 429/CAPTCHA and suspend
# themselves for 180-3600s. What the user sees is not an error — the surviving
# engines keep answering, just badly — so the symptom is "results quietly got worse
# after a few searches". See the engine-pool notes in searxng/settings.template.yml.
#
# Three cheap mitigations, all env-tunable:
#   concurrency cap  no more than N scrape fan-outs in flight at once
#   pacing           at least MIN_INTERVAL between two request starts
#   cache            repeats inside CACHE_TTL cost the engines nothing
#
# Scope: this state is per-process, so it throttles everything sharing one MCP server
# (the case that actually bursts — all of a session's agents). Separate cli.py
# invocations each get their own budget.
MAX_CONCURRENCY = int(os.environ.get("WEB_SEARCH_MAX_CONCURRENCY", "2"))
MIN_INTERVAL = float(os.environ.get("WEB_SEARCH_MIN_INTERVAL", "0.5"))
CACHE_TTL = float(os.environ.get("WEB_SEARCH_CACHE_TTL", "900"))
CACHE_MAX_ENTRIES = 256

_slots = threading.BoundedSemaphore(max(1, MAX_CONCURRENCY))
_pace_lock = threading.Lock()
_next_start = 0.0
_cache_lock = threading.Lock()
_cache: "OrderedDict[str, tuple[float, list[dict]]]" = OrderedDict()


def _pace() -> None:
    """Block until this caller is allowed to start a request.

    Sleeps outside the lock so waiting callers don't serialize on each other; the
    loop re-checks because the slot it was waiting for may have been taken meanwhile.
    """
    global _next_start
    while True:
        with _pace_lock:
            now = time.monotonic()
            if now >= _next_start:
                _next_start = now + MIN_INTERVAL
                return
            wait = _next_start - now
        time.sleep(wait)


def _cache_get(query: str):
    """Cached full result list for `query`, or None on miss/expiry."""
    if CACHE_TTL <= 0:
        return None
    with _cache_lock:
        entry = _cache.get(query)
        if entry is None:
            return None
        stamp, results = entry
        if time.monotonic() - stamp > CACHE_TTL:
            del _cache[query]
            return None
        _cache.move_to_end(query)
        return results


def _cache_put(query: str, results: list[dict]) -> None:
    if CACHE_TTL <= 0:
        return
    with _cache_lock:
        _cache[query] = (time.monotonic(), results)
        _cache.move_to_end(query)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)


def _fetch(query: str) -> list[dict]:
    """One live SearXNG query. Returns every result it gave us, normalized."""
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
    except urllib.error.URLError as e:
        # Connection refused / DNS / timeout → the backend is down.
        raise RuntimeError(
            f"SearXNG not reachable at {SEARXNG_URL} — call ensure_searxng first "
            f"(or ask the user about using the native WebSearch tool). Cause: {e.reason}"
        ) from e
    return [
        {
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "snippet": it.get("content", ""),
        }
        for it in data.get("results", [])
    ]


def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Search via local SearXNG. Returns [{title, url, snippet}, ...].

    Throttled and cached — see the burst-control notes above. The cache holds the full
    result list per query, not the truncated one, so a later call asking for more
    results than an earlier one is still served correctly.
    """
    results = _cache_get(query)
    if results is None:
        with _slots:
            # A caller we queued behind may have just fetched this same query.
            results = _cache_get(query)
            if results is None:
                _pace()
                results = _fetch(query)
                _cache_put(query, results)
    # Copy out: callers must not be able to mutate what's left in the cache.
    return [dict(r) for r in results[:num_results]]
