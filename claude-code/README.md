# Claude Code org — lean dev team

10 subagents, 2 modes. Plan the work, then build it. Short prompts, direct action, few handoffs.

## Install
From the harness root:
```bash
python3 setup-team.py <your-project>
```
Installs agents, `.claude/instructions.md`, `.mcp.json` (tool paths made absolute), templates, and a per-agent `.claude/logs/` dir in one shot — cross-platform, re-runnable (`--force` to overwrite). See root `README.md` for details.

Claude Code auto-discovers `.claude/agents/*.md`. Describe the work — the main thread routes to the right agent, or call one via the `Task` tool.

## Two modes
- **Plan mode** — `business-analyst` gathers + clarifies requirements → `architect` designs, sets standards, splits into tasks, pulling in `ux-designer` (UI) and `product-engineer` (feasibility/spikes). No code.
- **Agile dev mode** — `architect` delegates → `senior-dev` / `junior-dev` / `devops` build → `reviewer` reviews code + integration → `tester` validates → done. `project-manager` tracks + documents throughout.

Small/obvious change → skip plan mode, just do it.

## Incoming requests
Every bug/change goes to `project-manager` first: sets **priority** (P0–P3), routes — unclear requirement → `business-analyst`; small fix → `senior-dev` (does it or delegates to `junior-dev`); complex → `architect` (pulls `ux-designer` + `product-engineer` to plan). Then build → `reviewer` → `tester`. Priority (PM) and severity (senior-dev) are separate axes.

## Roster
| Agent | Role |
|---|---|
| business-analyst | requirements, clarify, research/fact-check |
| project-manager | intake/triage, track, status, coordinate, project record |
| architect | design, standards, split into tasks, delegate, technical record |
| product-engineer | feasibility, prioritize by impact, spikes to de-risk, shape work |
| ux-designer | flows, wireframes, design system, accessibility (Nielsen + WCAG) |
| senior-dev | hard tasks, quality check, review junior, debug, severity read |
| junior-dev | smaller build/edit tasks, debug |
| devops | CI/CD, deploy, networking, cloud |
| reviewer | independent code + integration review (Google eng-practices), can reject |
| tester | unit/integration/API/blackbox, automated scripts, can reject |

## Source of truth = files (not chat)
`.claude/project-context.md` (what/why + design + decisions) · `.claude/coding-standards.md` · `.claude/task-board.md` · `.claude/design.md` (UI projects) · `.claude/logs/<agent>.md` (one file per agent — that agent appends only, so parallel agents never collide and no lock is needed). architect owns the technical record, PM owns the project record. User-facing docs split three ways: architect (overview/setup) · senior-dev (API/usage reference) · tester (verified how-to). "Analyze the code" = Grep/Glob/Read. See `.claude/instructions.md`.

## Tools
`web-search` (SearXNG) + `deepwiki` (public-repo docs) via `.mcp.json`. Needs `pip install mcp`. See `../tools/`.
