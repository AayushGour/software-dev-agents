# Custom tools

Give the org capabilities beyond files + shell — web search, API calls, MCP servers.
Each tool has ONE core implementation, exposed to both runtimes:

- **Claude Code** → MCP server (registered in `../claude-code/.mcp.json`). Agents call it as `mcp__<server>__<tool>`.
- **Local (Hermes)** → a python callable listed in `registry.py`. `../local/run.py` loads it and hands it to the agent next to `hermes_tools`.

## Layout
```
tools/
  registry.py           # local runtime: name -> callable map
  <tool>/
    tool.py             # core impl (plain python function) — the single source
    cli.py              # optional: call via Bash (works in Claude Code today, no MCP needed)
    mcp_server.py       # optional: FastMCP stdio server for Claude Code
    README.md
```

## Add a tool
1. `mkdir tools/<name>`, write `tool.py` with a plain function.
2. Local: import it in `registry.py`, add to `TOOLS`.
3. Claude Code: either
   - wrap in `mcp_server.py` (FastMCP) + add to `claude-code/.mcp.json`, OR
   - add a `cli.py` and let agents call it with the `Bash` tool (zero MCP setup).
4. Grant it to the agents that need it (`tools:` frontmatter for Claude Code MCP tools).

## Wrapping an existing MCP server or HTTP API
- Third-party MCP server: add it straight to `claude-code/.mcp.json`; for local, write a thin `tool.py` that shells/HTTP-calls it and register in `registry.py`.
- Plain HTTP endpoint: `tool.py` = a `urllib`/`requests` call. Same two hookups.

## Config
Tools read config from env vars (e.g. `SEARXNG_URL`). Set them in `.mcp.json` `env` for Claude Code, and in your shell/dispatcher for local.

## Included tools
- `web_search/` — SearXNG (`SEARXNG_URL`, default `http://localhost:8081`). Local server.
- `deepwiki/` — docs + Q&A for public GitHub repos. Hosted remote MCP (`mcp.deepwiki.com`); local wrapper needs `pip install mcp`.
