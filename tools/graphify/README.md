# graphify (the code brain)

A persistent, per-project **knowledge graph of the codebase** — the team's structural
memory. Built by [graphify](https://github.com/Graphify-Labs/graphify) (PyPI `graphifyy`;
tree-sitter AST → `graphify-out/graph.json`), exposed as its own MCP server so agents query
structure instead of re-reading files. Code extraction is local only — no LLM, no API key.
Rationale and history: `decisions.md`.

## How it's wired
- **MCP server** (`claude-code/.mcp.json`): `uvx --from 'graphifyy[mcp]<0.10' graphify-mcp`. Runs
  at the project cwd → serves `graphify-out/graph.json`. Tools appear as `mcp__graphify__*`.
  Starts fine before the graph exists, and reloads `graph.json` whenever it changes.
- **SessionStart hook** (`claude-code/.claude/settings.json`) → `ensure_graph.py`: bootstraps
  `uv` if missing, then runs `graphify update .` **detached/background** (full build if no
  graph yet, incremental otherwise), so it never blocks session start. Also gitignores
  `graphify-out/`.
- **PostToolUse hook** → `refresh_graph.py`: after a source edit, re-runs the above,
  debounced to once per 120s.

## Requires
- **`uv`** (provides `uvx`). Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
  The hook pip-installs `uv` as a fallback; if that fails it logs a message and the MCP
  server stays down until `uv` exists.

## MCP tools
`query_graph` (keyword/question BFS/DFS) · `get_node` · `get_neighbors` · `shortest_path` ·
`god_nodes` · `graph_stats` · `get_community` · `list_prs` / `get_pr_impact` / `triage_prs`
(need `gh`; not granted to agents).

## Agents use it as a brain
- **architect** → `god_nodes`, `graph_stats`, `get_community`, `query_graph`, `shortest_path`
- **senior-dev** → `get_neighbors`, `get_node`, `query_graph`, `shortest_path` + `graphify affected` (Bash)
- **junior-dev** → `get_neighbors`, `query_graph`
- **reviewer** → `get_neighbors`, `get_node`, `query_graph` + `graphify affected` (Bash)
- **tester** → `query_graph`, `get_neighbors`

## Manual CLI
```bash
python3 tools/graphify/ensure_graph.py --build              # bootstrap + update (background)
python3 tools/graphify/ensure_graph.py --status             # up | absent
uvx --from 'graphifyy[mcp]<0.10' graphify update .               # build/refresh in the foreground
uvx --from 'graphifyy[mcp]<0.10' graphify affected "<symbol>"    # blast radius
uvx --from 'graphifyy[mcp]<0.10' graphify query "<question>"     # same as the query_graph tool
open graphify-out/graph.html                                # interactive visualisation
```

## Tests
```bash
PYTHONPATH=tools/graphify python3 -m unittest test_ensure_graph -v
```
