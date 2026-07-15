# How the org works (local / llama.cpp + Hermes) — read once

Small model. Be literal. Do the one task. Stop when done.
7 roles, 2 modes, files for memory.

## Two modes
PLAN MODE (no code): business-analyst gets requirements + clarifies → architect designs + splits into tasks.
DEV MODE (build): architect delegates → senior-dev / junior-dev / devops build → tester checks → done.
Start plan mode. Then dev mode. Tiny change = skip plan, just do it.

## Tools (hermes_tools)
- read_file, write_file, append_file (logs — never overwrite)
- grep(pattern, path) = your code search
- list_dir, run(cmd) = shell/tests

Custom tools (tools/registry.py, if loaded):
- web_search(query) = web results (SearXNG). For research + fact-check.
- deepwiki_ask(repo, question) = docs for a public GitHub repo ("owner/name").

## Files (source of truth, not chat)
```
project-context.md   what/why + design + decisions   (BA + architect)
coding-standards.md  stack, rules, how to run tests   (architect)
task-board.md        tasks + owner + status
logs/<agent>.md      1 line per task (append)
src/...              code
```

## Task line
`- T7 owner=senior-dev title="build /auth" deps=T3 status=todo`
status: todo | wip | review | test | done | blocked

## Delegate = add a sub-task
No direct calls. To delegate: senior-dev appends a row owner=junior-dev status=todo, sets own task blocked deps=<sub-id>. Dispatcher runs junior next. Junior done → senior unblocks + reviews.

## Handoff = set status
built → status=test (dispatcher runs tester). test pass → done. fail/reject → status=todo + note, back to owner.

## Common rules
- Unsure? clarify or write the assumption in project-context.md. Don't invent.
- grep before build — reuse, no duplicates. Follow coding-standards.md.
- Devs write unit tests. run them.
- Log 1 line per task. Big decision → append to project-context.md.
- Never: duplicate code, skip tests, invent requirements, overwrite a log.
