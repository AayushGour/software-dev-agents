# AI Dev Org Harness

A lean software team as tight agent prompts — **7 roles, 2 modes**, two runtimes.

Plan mode gathers requirements and designs; agile dev mode builds, and a dedicated `tester` agent validates against acceptance criteria and can reject work back to the owner. No feature ships untested.

| Folder | Runtime | Use |
|---|---|---|
| `claude-code/` | Claude Code subagents (`.claude/agents/*.md`, Task tool) | run with Claude Code |
| `local/`       | llama.cpp + Hermes (file dispatcher `run.py`, `hermes_tools`) | run a small local model |
| `tools/`       | custom tools (MCP servers / HTTP APIs) shared by both runtimes | extend agent capabilities |

Both share: files-as-memory (no external DB), grep-as-code-graph, 1-line logs, skippable ceremony for small tasks.

## Setup

One script installs the team into any project — cross-platform (Windows/Linux/macOS), only needs Python 3:

```bash
python3 setup-team.py <path-to-your-project>
```

Copies the agent prompts into `.claude/agents/`, `.claude/instructions.md`, the `.claude/project-context.md` / `.claude/coding-standards.md` / `.claude/task-board.md` / `.claude/design.md` templates, and seeds one `.claude/logs/<agent>.md` per agent (each agent appends only its own — no lock needed). `.mcp.json` lands at the project root (with tool paths rewritten to absolute). Safe to re-run — skips files that already exist, pass `--force` to overwrite.

**Then start a new Claude Code session inside that project folder** — subagents are discovered at session start, not hot-reloaded mid-conversation.

## Roster (7)
business-analyst · project-manager · architect · senior-dev · junior-dev · devops · tester

## Two modes
- **Plan mode** — business-analyst gathers + clarifies requirements → architect designs, sets standards, splits into tasks. No code.
- **Agile dev mode** — architect delegates → senior-dev / junior-dev / devops build → tester validates → done. project-manager tracks throughout.

Small/obvious change → skip plan mode, just do it.

## Shared files (source of truth, not chat)
`project-context.md` (what/why + design + decisions) · `coding-standards.md` · `task-board.md` · `logs.md` (shared).

## Design principles (why the prompts are short)
- Few agents, sharp prompts, direct action — coordination tax is what kills agent orgs.
- Shared rules live in one `instructions.md`, not repeated per agent.
- Memory = plain files; "analyze the codebase" = grep/glob/read.
- Log one line per task, not 15 fields per action.
- senior-dev reviews; tester can reject. Neither ceremony runs on a typo.
- Prod-grade baseline is non-negotiable: DRY, no magic strings (constants module), env config
  read from one place, lint clean before handoff. See `coding-standards.md`'s Non-negotiables.

## Custom tools
`tools/` holds capabilities beyond files+shell (web search, APIs, MCP). One core impl per tool,
wired to Claude Code (MCP in `claude-code/.mcp.json`) and local (`tools/registry.py`).
Included: `web_search/` → SearXNG (local, `SEARXNG_URL`), `deepwiki/` → public-repo docs+Q&A (remote MCP). See `tools/README.md`.

## Quick start
- Install the team into a project: `python3 setup-team.py <path>` (see [Setup](#setup))
- Claude Code details: see `claude-code/README.md`
- Local (llama.cpp/Hermes) details: see `local/README.md`
- Add a tool: see `tools/README.md`

## Superseded
`CLAUDE_MASTER_PROMPT.md` is the original generator spec (kept for reference).
The earlier generated output lives in `old/` (`old/agents/`, `old/organization/`,
`old/CLAUDE_ORGANIZATION.md`) — superseded by `claude-code/` and `local/`. It relied on
nonexistent tools (GBrain, Code Review Graph, `claude memory add`), had two drifted rosters,
and ~170-line boilerplate prompts. Safe to delete once you've confirmed the new folders.
