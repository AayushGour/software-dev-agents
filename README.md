# AI Dev Org Harness

A lean software team as tight agent prompts — **10 roles, 2 modes**, two runtimes. Plan the work, then build it. Short prompts, direct action, few handoffs.

Plan mode gathers requirements and designs; agile dev mode builds; `reviewer` gives an independent code + integration review and `tester` validates against acceptance criteria — either can reject work back to the owner. No feature ships unreviewed or untested.

| Folder | Runtime | Use |
|---|---|---|
| `claude-code/` | Claude Code subagents (`.claude/agents/*.md`, Task tool) | run with Claude Code |
| `local/`       | llama.cpp + Hermes (file dispatcher `run.py`, `hermes_tools`) | run a small local model |
| `tools/`       | custom tools (MCP servers / HTTP APIs) shared by both runtimes | extend agent capabilities |

Both share: files-as-memory (no external DB), grep-as-code-graph, one-line logs, skippable ceremony for small tasks.

## Setup

One script installs the team into any project — cross-platform (Windows/Linux/macOS), only needs Python 3:

```bash
python3 setup-team.py <path-to-your-project>
```

`claude-code/.claude/` already mirrors the exact layout an installed project uses, so setup is a straight copy:

- `.claude/agents/*.md` — the 10 agent prompts
- `.claude/instructions.md` — shared rules every agent reads first
- `.claude/coding-standards.md` · `.claude/project-context.md` · `.claude/task-board.md` · `.claude/design.md` — working docs (start as templates)
- `.mcp.json` at the project root (tool paths rewritten to absolute)
- this `README.md` at the project root

Safe to re-run — skips files that already exist; pass `--force` to overwrite.

### Optional: a `setup-team` command (run it from anywhere)
So you can type `setup-team <path-to-project>` in any folder instead of `cd`-ing to the harness first. The script resolves the target relative to your current directory, so the alias works from anywhere. Replace `/ABSOLUTE/PATH/TO/harness` with this repo's path (`pwd` here on macOS/Linux, `(Get-Location).Path` in PowerShell).

**macOS / Linux — zsh** (default on modern macOS), append to `~/.zshrc`:
```bash
echo 'alias setup-team="python3 /ABSOLUTE/PATH/TO/harness/setup-team.py"' >> ~/.zshrc
source ~/.zshrc
```
**Linux — bash**, same but `~/.bashrc`:
```bash
echo 'alias setup-team="python3 /ABSOLUTE/PATH/TO/harness/setup-team.py"' >> ~/.bashrc
source ~/.bashrc
```
**Windows — PowerShell**, add a function to your profile (aliases can't carry a fixed argument, so use a function that forwards `@args`):
```powershell
Add-Content $PROFILE 'function setup-team { python "C:\ABSOLUTE\PATH\TO\harness\setup-team.py" @args }'
. $PROFILE
```
Then from any project folder:
```bash
setup-team <path-to-your-project>
```

**Then start a new Claude Code session inside that project folder** — subagents are discovered at session start, not hot-reloaded mid-conversation. Describe the work; the main thread routes to the right agent, or call one via the `Task` tool.

## Roster (10)
| Agent | Role |
|---|---|
| business-analyst | requirements, clarify, research/fact-check |
| project-manager  | intake/triage, track, status, coordinate, project record |
| architect        | design, standards, split into tasks, delegate, technical record |
| product-engineer | feasibility, prioritize by impact, spikes to de-risk, shape work |
| ux-designer      | flows, wireframes, design system, accessibility (Nielsen + WCAG) |
| senior-dev       | hard tasks, quality check, review junior, debug, severity read |
| junior-dev       | smaller build/edit tasks, debug |
| devops           | CI/CD, deploy, networking, cloud |
| reviewer         | independent code + integration review (Google eng-practices), can reject |
| tester           | unit/integration/API/blackbox, automated scripts, can reject |

## Two modes
- **Plan mode** — `business-analyst` gathers + clarifies requirements → `architect` designs, sets standards, splits into tasks, pulling in `ux-designer` (UI) and `product-engineer` (feasibility/spikes). No code.
- **Agile dev mode** — `architect` delegates → `senior-dev` / `junior-dev` / `devops` build → `reviewer` reviews code + integration → `tester` validates → done. `project-manager` tracks + documents throughout.

Start in plan mode; switch to dev mode once the plan + tasks exist. Small/obvious change → skip plan mode, just do it.

## Incoming requests — intake + triage
Every new bug/change goes to **project-manager** first (the front door).
1. PM logs it and sets **priority** (P0 critical → P3 low — urgency/when to fix).
2. PM routes by type (asks senior-dev for the **severity/complexity** read only on borderline cases):
   - new / unclear requirement → **business-analyst**
   - clear small fix → **senior-dev** → does it, or delegates to **junior-dev**
   - complex / architectural / cross-cutting → **architect** → pulls **ux-designer** + **product-engineer** to plan → task split
3. Then the normal build flow: build → **reviewer** → **tester** → done.

Priority = business urgency (PM owns). Severity = technical impact/complexity (senior-dev owns). Different axes — don't conflate them.

## Source of truth = files (not chat)
```
.claude/project-context.md    what we're building, why, constraints, design, decisions   (BA seeds; architect + PM keep current)
.claude/coding-standards.md   stack, conventions, how to run tests                        (architect)
.claude/task-board.md         tasks + owner + priority + status                           (architect creates; PM keeps honest; each updates own)
.claude/design.md             flows, states, components, accessibility AC                 (ux-designer; UI projects only)
.claude/logs/<agent>.md       one log file per agent, that agent appends only             (each agent, own file only)
```
"Analyze the code" = Grep / Glob / Read. Reuse before you write — no duplicates.

**Logging — one file per agent (no shared file, no lock):** each agent writes **only** its own `.claude/logs/<agent>.md`. Because no two agents ever write the same file, parallel agents never collide. One line per task at handoff/done: `- <date> [T<id>] one-line summary`. To see who-did-what, read/concat `.claude/logs/*.md` (PM does this for status reports).

**Who documents:** architect owns the *technical* record; project-manager owns the *project* record. User-facing docs split three ways: **architect** → overview + setup; **senior-dev** → API/usage reference for what they built; **tester** → verified how-to. One voice, no overlap.

## Design principles (why the prompts are short)
- Few agents, sharp prompts, direct action — coordination tax is what kills agent orgs.
- Shared rules live in one `instructions.md`, not repeated per agent.
- Memory = plain files; "analyze the codebase" = grep/glob/read.
- Log one line per task, not 15 fields per action.
- senior-dev + reviewer review; tester can reject. Neither ceremony runs on a typo.
- Prod-grade baseline is non-negotiable: DRY, no magic strings (constants module), env config read from one place, lint clean before handoff. See `coding-standards.md`'s Non-negotiables.

## Custom tools
`tools/` holds capabilities beyond files+shell (web search, APIs, MCP). One core impl per tool, wired to Claude Code (MCP in `claude-code/.mcp.json`) and local (`tools/registry.py`). Included: `web_search/` → SearXNG (local, `SEARXNG_URL`), `deepwiki/` → public-repo docs+Q&A (remote MCP). Needs `pip install mcp`. See `tools/README.md`.

## Quick start
- Install the team into a project: `python3 setup-team.py <path>` (see [Setup](#setup))
- Local (llama.cpp/Hermes) details: see `local/README.md`
- Add a tool: see `tools/README.md`

## Superseded
`CLAUDE_MASTER_PROMPT.md` is the original generator spec (kept for reference). The earlier generated output lives in `old/` — superseded by `claude-code/` and `local/`. It relied on nonexistent tools (GBrain, Code Review Graph, `claude memory add`), had two drifted rosters, and ~170-line boilerplate prompts. Safe to delete once you've confirmed the new folders.
