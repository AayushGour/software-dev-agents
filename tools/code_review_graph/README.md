# code_review_graph (the code brain)

A persistent, per-project **knowledge graph of the codebase** — the team's structural
memory. Built by [code-review-graph](https://github.com/tirth8205/code-review-graph)
(Tree-sitter AST → local SQLite `.code-review-graph/graph.db`), exposed as its own MCP
server so agents query structure instead of re-reading files (~82× fewer tokens).
Design: `docs/superpowers/specs/2026-07-28-code-review-graph-brain-design.md`.

## How it's wired
- **MCP server** (`claude-code/.mcp.json`): `uvx --from code-review-graph[embeddings]
  code-review-graph serve`. Runs at the project cwd → graphs that project. Tools appear as
  `mcp__code-review-graph__*`. No pre-install — `uvx` fetches + caches on first run.
- **SessionStart hook** (`claude-code/.claude/settings.json`) → `ensure_graph.py`: bootstraps
  `uv` if missing, builds the graph if absent (else incremental `update`), then `embed`s —
  all **detached/background**, so it never blocks session start. Also gitignores
  `.code-review-graph/`.
- **Lazy net:** agents call `mcp__code-review-graph__build_or_update_graph_tool` if the graph
  looks missing/stale mid-session.

## Requires
- **`uv`** (provides `uvx`). Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
  The hook pip-installs `uv` as a fallback; if that fails it logs a message and the MCP
  server stays down until `uv` exists.
- First-ever run pulls the package **with embeddings** (torch, heavy) + a MiniLM model
  (~90 MB) in the background.

## Agents use it as a brain (deep-wired)
- **architect** → `get_architecture_overview_tool`, `semantic_search_nodes_tool`
- **senior/junior-dev** → `get_impact_radius_tool`, `query_graph_tool` before edits
- **reviewer** → `get_review_context_tool`, `detect_changes_tool`, `semantic_search_nodes_tool`
- **tester** → `query_graph_tool` (tests covering a node), `detect_changes_tool`

## Manual CLI
```bash
python3 tools/code_review_graph/ensure_graph.py --build     # bootstrap + build (background)
python3 tools/code_review_graph/ensure_graph.py --status    # up | absent
uvx --from code-review-graph[embeddings] code-review-graph status       # graph stats
uvx --from code-review-graph[embeddings] code-review-graph impact <path> # blast radius
uvx --from code-review-graph[embeddings] code-review-graph visualize     # interactive HTML
```

## Tests
```bash
PYTHONPATH=tools/code_review_graph python3 -m unittest test_ensure_graph -v
```
