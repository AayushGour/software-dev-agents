# code-review-graph as the team's code brain — design

**Date:** 2026-07-28
**Status:** Approved (design), pending implementation
**Component:** `tools/code_review_graph/`, `claude-code/.mcp.json`, `claude-code/.claude/settings.json`, `claude-code/.claude/instructions.md`, `claude-code/.claude/agents/*.md`, `setup-team.py`

## Problem

Agents "analyze the code" by Grep/Glob/Read — re-reading large swaths of the codebase
every task, burning tokens and still missing structural facts (who calls this, what
breaks if I change it, which tests cover it). There's no shared structural memory.

Goal: give the team a **code brain** — a persistent, per-project knowledge graph of the
codebase that agents query for precise structural context instead of blind file reads —
auto-installed and auto-built for **every** project the harness runs in.

## Chosen tool: code-review-graph (CRG)

CRG parses source with Tree-sitter into an AST graph (functions, classes, calls, imports,
inheritance, tests) stored in a local SQLite db `.code-review-graph/graph.db`, and exposes
it as its **own MCP server** (`code-review-graph serve`) with 30+ tools. Local, no API
keys, no external DB. Median ~82× token reduction vs whole-corpus reads. (NotebookLM-style
tools — open-notebook, notebooklm-py — were rejected: document/text RAG, not code-structure
aware; wrong shape for a code brain. See conversation.)

## Decisions (settled)

| Question | Decision |
|---|---|
| Install | **uvx** — `.mcp.json` runs `uvx code-review-graph serve`; uv fetches + caches, no pre-install. Hook bootstraps `uv` via pip if missing. |
| Graph build | **Hook + lazy** — SessionStart hook builds/updates the graph (background); agents also call `build_or_update_graph_tool` on demand. |
| Agent wiring | **Deep** — instructions.md + architect/senior-dev/junior-dev/reviewer/tester query the graph FIRST (impact-radius before edits, review-context before review, architecture-overview when planning). |
| Embeddings | **Local embeddings ON** — `code-review-graph[embeddings]` (sentence-transformers, runs locally, no API key, no code off-machine). Enables `semantic_search_nodes_tool` (search code by meaning). Build runs an `embed` step. |
| Storage | per-project `.code-review-graph/` — gitignored (self-managed by the ensure script). |
| Deployment | central `tools/` (as today); `.mcp.json` uvx entry needs no path rewrite; **settings.json hook paths rewritten to absolute by setup-team**. |

## Architecture

```
Claude Code spawns (cwd = project root):
  mcp__code-review-graph__*   ← uvx code-review-graph serve   (queries the graph)

SessionStart hook (cwd = project root):
  ensure_graph.py  → ensure uv present → build graph if absent, else incremental update
                     (detached/background — never blocks session start) + gitignore .code-review-graph/

Agents (deep wiring):
  architect      → get_architecture_overview_tool before designing
  senior/junior  → get_impact_radius_tool + query_graph_tool before editing
  reviewer       → get_review_context_tool + detect_changes_tool
  tester         → query_graph_tool (TESTED_BY) + detect_changes_tool
  all            → build_or_update_graph_tool if the graph looks stale/missing (lazy)
```

Server key in `.mcp.json` is `code-review-graph`, so tools appear as
`mcp__code-review-graph__<tool>`.

## Components

### 1. `claude-code/.mcp.json` — add the CRG server (new entry)

```json
"code-review-graph": {
  "command": "uvx",
  "args": ["--from", "code-review-graph[embeddings]", "code-review-graph", "serve"]
}
```

- `--from code-review-graph[embeddings]` makes uvx install the package **with the local
  embeddings extra** (sentence-transformers) and run the `code-review-graph` console script.
- uvx runs with cwd = project root → graphs *that* project, writes `.code-review-graph/`
  there. A bare command (no `../tools/` path) → **setup-team needs no rewrite** for this entry.
- Verify the console-script name at implementation; if it differs, adjust the trailing
  `code-review-graph serve` accordingly (the `--from` extras spec stays).

### 2. `tools/code_review_graph/ensure_graph.py` (new — install + build)

Deterministic, cwd-independent for *its own* location; operates the graph on the **current
working directory** (the project). Mirrors `ensure_searxng.py` in spirit.

```python
def ensure_uv() -> bool:
    """True if uvx is available; try `python3 -m pip install --user uv` once if not."""

def graph_gitignored():
    """Append `.code-review-graph/` to the project's .gitignore if not already ignored."""

CRG = ["uvx", "--from", "code-review-graph[embeddings]", "code-review-graph"]

def build_or_update():
    """If ./.code-review-graph/graph.db is absent → `CRG build`, else `CRG update`;
    then `CRG embed` to (re)compute vector embeddings for semantic search. Launched
    DETACHED as one background chain (Popen, no wait) so the SessionStart hook returns
    immediately; stdout/err → .code-review-graph/ensure.log."""

def main():  # CLI: --build (default) | --status
    if not ensure_uv(): print("uv unavailable — install uv to enable the code brain"); return 0
    graph_gitignored(); build_or_update(); print("code brain: build/update kicked off"); return 0
```

- **Non-blocking:** the actual `build`/`update` runs as a detached child; the hook doesn't
  wait (first-ever uvx fetch + build can take ~30–60s — must not stall session start).
- **Correctness net:** the "lazy" path (agents calling `build_or_update_graph_tool`) covers
  the window where the background build is still running or uv was missing.

### 3. `claude-code/.claude/settings.json` — add SessionStart hook

Extends the existing file (already holds the SearXNG SessionEnd hook):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "python3 ../tools/code_review_graph/ensure_graph.py --build" } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "python3 ../tools/web_search/ensure_searxng.py --stop" } ] }
    ]
  }
}
```

Relative `../tools/...` is correct for in-harness dogfooding (cwd = claude-code/); setup-team
rewrites it to absolute on deploy (see §6).

### 4. `claude-code/.claude/instructions.md` — the code brain

- New short section **"The code brain (code-review-graph)"**: a persistent graph of the
  codebase, queried via `mcp__code-review-graph__*`, auto-built each session. Agents consult
  it for structure/impact/callers/tests **before** Grep/Read, then read only the files it
  points to. When the name isn't known, `semantic_search_nodes_tool` finds code by meaning.
  If the graph looks missing/stale, call `build_or_update_graph_tool`.
- Amend the existing line `"Analyze the code" = Grep / Glob / Read.` →
  `"Analyze the code" = query the code brain (mcp__code-review-graph__*) first for structure/impact, then Grep/Glob/Read the specific files it points to. Reuse before you write.`

### 5. `claude-code/.claude/agents/*.md` — deep wiring (5 agents)

For each, (a) add the needed MCP tools to `tools:` frontmatter, (b) add one LOOP/method line
telling it to query the graph first. Grant only what each role uses:

| Agent | Tools granted (`mcp__code-review-graph__…`) | Behavior added |
|---|---|---|
| architect | `get_architecture_overview_tool`, `query_graph_tool`, `semantic_search_nodes_tool`, `build_or_update_graph_tool` | Read the architecture overview before designing; semantic-search to locate related subsystems by intent |
| senior-dev | `get_impact_radius_tool`, `query_graph_tool`, `get_review_context_tool`, `semantic_search_nodes_tool`, `build_or_update_graph_tool` | Check impact-radius + callers before editing shared code; semantic-search to find where a concept lives |
| junior-dev | `get_impact_radius_tool`, `query_graph_tool` | Check callers/impact of the one thing before editing |
| reviewer | `get_review_context_tool`, `detect_changes_tool`, `get_impact_radius_tool`, `semantic_search_nodes_tool` | Pull review-context + risk-scored change impact; semantic-search for duplicate/similar code by meaning |
| tester | `query_graph_tool`, `detect_changes_tool` | Find tests covering changed nodes; prioritize regression by risk |

(business-analyst / product-engineer / ux-designer / devops / project-manager unchanged —
no code-structure need, keeps their tool surface minimal.)

### 6. `setup-team.py` — rewrite hook tool-paths to absolute (deployment fix)

`install_dotclaude` copies `settings.json` verbatim, so its `../tools/...` hook commands
break in a deployed project (cwd = project, not claude-code/). Add a post-copy step that
rewrites `../tools/` → absolute `TOOLS_DIR` inside every hook `command` string in
`<target>/.claude/settings.json` — mirroring what `install_mcp` already does for `.mcp.json`.
This fixes **both** the new CRG SessionStart hook and the existing SearXNG SessionEnd hook
for deployed projects. Also update the closing hint to note the code brain needs `uv`.

### 7. `.gitignore` — add `.code-review-graph/`

For the harness repo (in case the brain is built here while dogfooding). Deployed projects
get their own entry appended by `ensure_graph.py`'s `graph_gitignored()`.

### 8. Docs

- `tools/code_review_graph/README.md` (new) — what it is, uvx requirement, the hook, the
  MCP tools agents use, manual CLI (`--build`, `code-review-graph status/visualize`).
- `tools/README.md` — add code_review_graph to "Included tools".

## Edge cases

| Case | Behavior |
|---|---|
| `uv` not installed | ensure_graph tries `pip install --user uv` once; if still absent, logs an actionable message and returns 0 (no crash). MCP `uvx` entry will fail to start until uv exists — documented. |
| First-ever uvx run | downloads + caches CRG **with embeddings** — pulls torch (heavy, hundreds of MB–~2 GB) + downloads the MiniLM model (~90 MB) on first `embed`; all detached/background so session start isn't blocked; agents fall back to the lazy build tool meanwhile |
| Graph missing when an agent queries | agent calls `build_or_update_graph_tool` (lazy net) |
| Large repo first build | ~10s/500 files, background; incremental updates <2s |
| Deployed project (setup-team) | hook paths rewritten to absolute; uvx entry unchanged; graph builds in the project |
| Non-git / unsupported files | CRG skips gitignored + unparseable files; honors `.code-review-graphignore` |

## Testing

- **Unit (no uv/network):** `ensure_graph` — `graph_gitignored()` appends once / is idempotent;
  `build_or_update()` picks build vs update by graph.db presence (mock Popen, assert argv);
  `ensure_uv()` returns False cleanly when uv + pip both absent (mocked).
- **setup-team:** deploy to a temp dir; assert `<target>/.claude/settings.json` hook commands
  are absolute and point at the harness `tools/`; `.mcp.json` has the `code-review-graph` entry.
- **Integration (uv present):** run `ensure_graph.py --build` in a small temp repo → assert
  `.code-review-graph/graph.db` appears, `code-review-graph status` reports nodes, and the
  `embed` step populated embeddings; confirm `uvx --from code-review-graph[embeddings]
  code-review-graph serve` starts and lists `mcp__code-review-graph__*` tools **including
  `semantic_search_nodes_tool`**.
- **Agent frontmatter:** each wired agent's `tools:` parses and includes the granted MCP tools.

## Out of scope / future

- **`watch`/daemon** continuous updates — hook+lazy is enough; revisit if staleness bites.
- **Local (Hermes) runtime** wiring — this spec is Claude-Code-side (MCP + hook).
- **Research/document brain** (open-notebook) — separate capability, only if a doc-ingestion
  need appears.

## Files touched

- `tools/code_review_graph/ensure_graph.py` — new
- `tools/code_review_graph/README.md` — new
- `tools/code_review_graph/test_ensure_graph.py` — new (unit)
- `claude-code/.mcp.json` — modified (CRG server entry)
- `claude-code/.claude/settings.json` — modified (SessionStart hook)
- `claude-code/.claude/instructions.md` — modified (code-brain section + analyze line)
- `claude-code/.claude/agents/{architect,senior-dev,junior-dev,reviewer,tester}.md` — modified
- `setup-team.py` — modified (rewrite settings.json hook paths; hint text)
- `.gitignore` — modified (`.code-review-graph/`)
- `tools/README.md` — modified
