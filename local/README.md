# Local org — llama.cpp + Hermes

Same 7-role, 2-mode dev team as `claude-code/`, tuned for a small local model driven by a Hermes tool-calling agent. Prompts are shorter and more literal.

## How it runs
No subagent Task tool here. `run.py` reads `task-board.md`, picks the next actionable task, loads that agent's prompt + `instructions.md` + project context, runs the Hermes agent with `hermes_tools`. Agents coordinate through files. Wire the two seams in `run.py` to your llama.cpp/Hermes setup, then: `python run.py <project_dir>`.

## Two modes
- **Plan mode**: `business-analyst` (requirements + clarify) → `architect` (design, standards, split into tasks). No code.
- **Dev mode**: `architect` delegates → `senior-dev` / `junior-dev` / `devops` build → `tester` validates → done. `project-manager` tracks.

## Roster
business-analyst · project-manager · architect · senior-dev · junior-dev · devops · tester

## Files
```
local/
  instructions.md   shared rules (agents read first)
  run.py            dispatcher (review→senior-dev, test→tester)
  agents/*.md       7 agent prompts
  templates/        project-context.md · coding-standards.md · task-board.md
```

## Delegation + handoff (via files)
Delegate = senior-dev adds a `owner=junior-dev` sub-task row, blocks its own on it.
Handoff = set task `status`: built→`test`, pass→`done`, reject→`todo`+note.

## Tools
`tools/registry.py` gives agents `web_search` (SearXNG) + `deepwiki_ask` (public-repo docs). `run.py` loads them next to `hermes_tools`. deepwiki needs `pip install mcp`.
