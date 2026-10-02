# Running on the local org (llama.cpp + Hermes) — what differs from the rulebook

Small model. Be literal. Do the one task. Stop when done.
The team rulebook above and your role prompt were written for Claude Code. Where they
name a tool or mechanism this runtime lacks, use the substitute below.

## Tools
| Rulebook / role prompt says | Use here |
|---|---|
| Read · Write · Edit | `read_file` · `write_file` · `append_file` (logs — never overwrite) |
| Grep · Glob | `grep(pattern, path)` · `list_dir` |
| Bash | `run(cmd)` |
| `mcp__web-search__*` · `mcp__deepwiki__*` | `web_search(query)` · `deepwiki_ask(repo, question)` (if loaded) |
| `mcp__graphify__*` (code brain) | not available — `grep` instead |
| Task / Agent (spawn a subagent) | not available — delegate by board row (below) |
| AskUserQuestion / the depth menu | no user in the loop — write the assumption in project-context.md |

## Delegate = add a board row
No spawning. To delegate, append a row to `.claude/task-board.md` owned by the other
agent with `status:todo`, and set your own row `status:blocked deps:<sub-id>`. The
dispatcher runs the child next. Fan-out (deep-researcher) works the same way and runs
one row at a time — sequential, not parallel. Budget (mode + depth + breadth) goes in
the task title.

`blocked` rows are invisible to the dispatcher: it only reconsiders todo/review/test,
never blocked, even once every dep is done. So the CHILD unblocks the parent: when you
finish, check the parent's deps; if every one is done, set the parent row back to
`status:todo` yourself. Nothing does this automatically.

## Handoff = set status
Built → `status:review` (dispatcher runs reviewer) → `status:test` (runs tester).
Pass → `status:done  evidence:<ref>`. Reject → `status:todo` + note, back to the owner.

## No hooks run here
Board-lint, the code-brain refresh and every other hook are Claude Code only. You must
hold the evidence rule yourself: never write `status:done` without an `evidence:` ref
that exists.
