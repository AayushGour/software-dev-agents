# Local org — llama.cpp + Hermes

The same team as `claude-code/`, driven by a small local model through a Hermes
tool-calling agent. **No copies of its own:** agents, rulebook and working-doc templates
all come from the canonical `claude-code/` tree via `installer/source.py`. Only what is
genuinely different about this runtime lives here.

## How it runs
No subagent Task tool here. `run.py` reads `.claude/task-board.md`, picks the next
actionable task, and builds the system prompt from the canonical agent body + the
canonical rulebook (`claude-code/AGENTS.md`) + `runtime.md` (tool substitutions,
board-row delegation, no hooks). It runs the Hermes agent with `hermes_tools`. Agents
coordinate through files. Install the working docs with `setup-team.py` (they land in
`<project>/.claude/`), wire the two seams in `run.py` to your llama.cpp/Hermes setup,
then from the harness root: `python3 -m local.run <project_dir>`.

Dispatch: `todo` → the task owner, `review` → reviewer, `test` → tester.

## Files
```
local/
  runtime.md        what differs from the rulebook on this runtime
  run.py            dispatcher
  hermes_agent.py   llama.cpp + Hermes tool-calling loop
  hermes_tools.py   filesystem + shell tools, sandboxed to the project
  test_run.py       python3 -m unittest local.test_run
```

## Tools
`tools/registry.py` gives agents `web_search` (SearXNG) + `deepwiki_ask` (public-repo
docs). `run.py` loads them next to `hermes_tools`. deepwiki needs `pip install mcp`.
