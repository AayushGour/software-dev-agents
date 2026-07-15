# web_search (SearXNG)

Web search via a local SearXNG instance. `tool.py` is the core; CLI + MCP wrap it.

## Config
`SEARXNG_URL` — default `http://localhost:8081`.

SearXNG must have JSON output on. In `settings.yml`:
```yaml
search:
  formats: [html, json]
```

## Claude Code
Registered in `claude-code/.mcp.json`. Needs `pip install mcp`. Agents call `mcp__web-search__web_search`.
No-MCP alternative: `python tools/web_search/cli.py "query"` via the Bash tool.

## Local (Hermes)
Exported by `tools/registry.py` as `web_search(query, num_results=5)`; `local/run.py` hands it to the agent.

## Smoke test
```bash
python tools/web_search/cli.py "claude opus 4.8" 3
```
Returns `[{title, url, snippet}]` (CLI prints numbered).
