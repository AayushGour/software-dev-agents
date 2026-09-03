# Research agents — generic, deep, and special research — design

**Date:** 2026-09-03
**Status:** Approved (design), pending implementation
**Component:** `claude-code/.claude/agents/researcher.md`, `claude-code/.claude/agents/deep-researcher.md`, `claude-code/.claude/researcher-template.md`, `claude-code/.claude/agents/research/`, `claude-code/CLAUDE.md`, `local/agents/*`, `local/instructions.md`, `setup-team.py`

## Problem

The team has research *tools* (`mcp__web-search__web_search`, `mcp__deepwiki__*`) but no research
*role*. Today every agent researches inline, in its own context, with no budget and no artifact:
the architect burns its planning context on a library comparison, three agents re-derive the same
fact in three sessions, and nothing is written down. `CLAUDE.md:127` is the whole current policy —
"agents with the tools use web_search … agents without them ask their spawner".

Goal: a research capability that (a) runs in its own context so findings, not raw pages, reach the
caller, (b) scales from one cheap lookup to a fanned-out investigation, (c) leaves a citable report,
and (d) cannot quietly cost 40 agents when nobody asked for it.

## Decisions (settled)

| Question | Decision |
|---|---|
| Roles | **Two.** `researcher` (leaf, one question, cheap) and `deep-researcher` (orchestrator, fans out, writes the report). |
| Modes | **Three, chosen per invocation.** `quick` = one `researcher`, no fan-out. `deep` = fan-out with *generic* stock `researcher` children, specialised by prompt only. `special` = fan-out with *tailored authored* agent files. |
| Depth | **Always asked, never assumed.** Main thread shows a menu (Quick / Deep / Special / Custom) before any research spawn. |
| Who authors in special mode | **Every level authors its own children.** A level-1 tailored agent decomposes its own sub-question, authors its own children, spawns them. True recursion. |
| Authored-agent lifetime | **Persist.** They are reusable assets. Reuse-before-author is the growth brake. |
| Output | **Report file + summary to caller.** `.claude/research/YYYY-MM-DD-<topic>.md`; short synthesis returned to whoever spawned it. `quick` mode returns chat only. |
| Wiring | **`CLAUDE.md` only** — the shared rulebook every agent reads first. No per-agent frontmatter edits to the 10 core roles. |
| Trees | **Both.** `claude-code/` (real spawning) and `local/` (task-board fan-out). |
| Containment | **Written rule, not an allowlist** — the platform ignores `Agent(...)` type lists inside subagent definitions (see Platform facts). |

## Architecture

```
QUICK                  DEEP                              SPECIAL
researcher             deep-researcher (generic)         deep-researcher (generic)
   │                     ├─ researcher  ×b                 ├─ rsr-<domain>  ×b   (authored here)
   └─ answer             │    (stock agent, prompt-        │     └─ rsr-<sub> ×b (authored by the
                         │     specialised, leaf)          │           level-1 agent)
                         └─ synthesize → report            └─ synthesize → report
```

Both fan-out modes: generic root, report written, summary returned. The only difference is **what
the children are** — stock agents differentiated by prompt (`deep`) vs authored agent files with
their own `description`/`tools`/`model` that persist and get reused (`special`).

**Budget arithmetic.** `breadth` = sub-questions per node = children spawned. `depth` = levels of
children below the orchestrator. Agents = `1 + b + b² + …` to `depth` terms. This is a **ceiling** —
if recon yields two real sub-questions, two children spawn, not `b`.

| Mode | depth | breadth | agents |
|---|---|---|---|
| quick | — | — | 1 |
| deep | 1 | 4 | `1 + 4` = **5** |
| deep (custom, depth 2) | 2 | 4 | `1 + 4 + 16` = **21**, children are `deep-researcher` |
| special | 2 | 4 | `1 + 4 + 16` = **21** |
| custom | caller | caller | caller does the math; menu shows it |

## The depth menu (main-thread gate)

**Subagents cannot call `AskUserQuestion`** — it is removed from the subagent toolset. So the menu
*must* fire in the main thread, before the spawn. When any agent requests research, or the user asks
for it, the main thread presents:

- **Quick — 1 agent, no fan-out.** One `researcher` answers directly from web + repo. Chat summary,
  no report. For: which lib, does X support Y, what version.
- **Deep — up to 5 (1 + 4).** depth 1, breadth 4. Stock generic children, parallel, synthesized.
  Writes a report.
- **Special — up to 21 (1 + 4 + 16).** depth 2, breadth 4. Authors tailored `rsr-<domain>.md` per
  sub-question; each child may author + spawn one level deeper. Authored agents persist. Writes a
  report.
- **Custom.** Caller sets mode, depth, breadth, and scope fences in free text. The menu states the
  arithmetic and the **concurrency cap of 20** (breadth 6 at depth 2 = 36 concurrent → queues).

Never guess the depth. A research request without a chosen depth is not actionable.

**How a request reaches the main thread.** The main thread presents the menu, but a research need
rarely originates there — it surfaces three, four levels deep inside whatever a subagent is doing.
The propagation is: **a spawned agent that needs research returns the request to its own
spawner rather than guessing a depth**, stating what it needs researched and why. The spawner
either already has the answer (reuse before research) or itself has no menu access and bubbles the
request upward the same way — return, don't guess. This repeats until the request reaches the main
thread, which is the only place in the whole call stack where `AskUserQuestion` actually works.
The main thread then presents the menu and spawns fresh with the chosen mode/depth/breadth baked
into the prompt; it does not resume the agent that originated the request mid-stack.

## The deep-researcher loop

```
in:  root question + mode + depth + breadth + any caller fences

1 RECON       cheap pass by the orchestrator itself: web_search + repo grep.
              Goal is not the answer — it is the SHAPE of the question. What
              sub-domains exist, what is already settled, what is contested.

2 DECOMPOSE   split into N independent sub-questions, N <= breadth.
              Independent = no sub-question needs another's answer first.
              Overlapping or dependent → merge, or sequence inside one child.
              If recon already answered it → N = 0, skip to 5 and say so.
              Deep research on a shallow question is waste; report that, don't spend.

3 STAFF       mode=deep    → children are stock `researcher`, specialised by prompt.
                             `researcher` has no `Agent` tool, so it is always a leaf —
                             `deep` is therefore depth-1 by construction. A custom
                             `deep, depth 2` spawns `deep-researcher` children instead,
                             which then spawn stock researchers at level 2.
              mode=special → per sub-question:
                               glob .claude/agents/research/ — an existing rsr-* fits? reuse it.
                               genuine domain gap? author .claude/agents/research/rsr-<domain>.md
                               from .claude/researcher-template.md.
              Gap = an ongoing domain (protocol, framework, subsystem), not this one
              question. Same bar as the architect's team-formation rule (CLAUDE.md).
              remaining depth >= 1 → authored file gets `Agent` + `Write` in tools.
              remaining depth = 0  → authored file is a leaf: no `Agent`, no `Write`.

              Building an orchestrator variant (remaining depth >= 1) means pasting more than
              LOOP steps 2-5. Those four steps alone (DECOMPOSE/STAFF/SPAWN/SYNTHESIZE) leave the
              pasted STAFF step's `mode=special` branch pointing at a `## Special mode` section
              the file never received, and drop `## Fences` entirely — losing the no-build-role
              rule and the concurrency cap, with nothing downstream to re-state them. Building an
              orchestrator variant means ALL of: add `Write, Agent` to `tools:`; paste LOOP steps
              2-5; ALSO paste `## Fences` verbatim; ALSO paste `## Special mode` itself; and
              REPLACE — not supplement — the leaf template's `## Method`, seven-field `RETURN`,
              `NEVER:`, and `DONE:` with orchestrator-appropriate text mirroring deep-researcher's
              own closing `CONSULT:` / `NEVER:` / `DONE:`. An orchestrator's contract with its
              caller is a synthesis plus a report path; leaving the leaf's seven-field block in
              place states two incompatible return contracts in one file. Match
              `claude-code/.claude/researcher-template.md`'s authoring footer, which is the
              delivered source of truth for this list.

4 SPAWN       author ALL children for the level first, THEN spawn them in ONE message
              (parallel). Authoring-then-immediately-spawning one at a time races the
              file watcher; batching gives it slack.

5 SYNTHESIZE  conflicts are NAMED, not averaged. Unanswered stays unanswered.
              Write .claude/research/YYYY-MM-DD-<topic>.md — question, answer, evidence,
              sources, confidence, conflicts, open threads, agents used.
              Return a short summary + the report path to the caller.
```

**Termination.** Three independent stops, first one wins:
1. Depth exhausted — structural: the leaf's frontmatter has no `Agent` tool.
2. `N = 0` at decompose — nothing left worth splitting.
3. `breadth` cap per level.

Platform hard-caps depth at 3 layers below the main conversation regardless of what the caller asks.

## Drift control

The failure mode of recursive research is a level-2 agent answering a fascinating question nobody
asked. Four fences, all structural:

**1. Every spawn carries the root question verbatim.** Not a paraphrase. Child prompt shape:

```
ROOT QUESTION (never answer directly, never widen):  <verbatim>
YOUR SUB-QUESTION:                                   <one question>
HOW YOUR ANSWER SERVES THE ROOT:                     <one line, written by the parent>
ALREADY ESTABLISHED (do not re-derive):              <recon findings>
OUT OF SCOPE:                                        <siblings' sub-questions + explicit exclusions>
REMAINING DEPTH:                                     <n>
```

The last line depends on what the child is — a single `RETURN:` requesting the seven fields is
wrong for an orchestrator child: it has no budget to work with and its contract is a synthesis,
not seven fields. Two variants, matching the delivered `claude-code/.claude/agents/deep-researcher.md`:

- **Leaf child** (`researcher`, or an `rsr-*` at remaining depth 0) — holds no `Agent`, cannot fan
  out:
  `RETURN: finding / evidence / source / confidence / relevance / could-not-answer / open-threads`
- **Orchestrator child** (`deep-researcher`, or an `rsr-*` with remaining depth ≥ 1) — it fans out
  again, so it needs its own budget or it will stop and ask you for one:
  `MODE: <mode>   BREADTH: <breadth>`
  `RETURN: a short synthesis + the path of the report you wrote`

`OUT OF SCOPE` listing the siblings is what stops four children converging on the same tangent.

**2. Narrowing-only.** A child may split its sub-question further. It may not add a sub-question
outside its own. Something important but off-scope is **reported as an open thread**, never chased.
The orchestrator decides whether an open thread becomes a new branch. Widening is a root-only
privilege.

**3. `relevance:` is a required return field.** Every child states how its finding bears on the root
question. A child that cannot fill that line honestly has drifted and says so. The orchestrator drops
or demotes those findings at synthesis rather than blending them in.

**4. Authored agents are scoped at birth.** In special mode the tailored file's `description` and
`DO:` are written *against the root question*, not the domain in general —
`"Research specialist — <root topic>: <domain> aspects"`, not `"gRPC expert"`. The fence lives in the
file, so it survives into the grandchildren that agent spawns.

## Roster hygiene

Name collisions are **silent** (`"loads only one of them, chosen by filesystem read order"`), so
naming is load-bearing, not cosmetic.

- **Name pattern** `rsr-<domain>` — reserved prefix; cannot collide with the 10 core roles or future
  architect-authored specialists.
- **Description** must start `Research specialist —` so the main thread's router never mistakes one
  for a build role.
- **Location** `.claude/agents/research/` — subdirectories are scanned recursively and the path does
  not affect identity.
- **Reuse before authoring** — glob the directory and reuse a match. This is the growth brake; there
  is no prune job in v1.
- `setup-team.py` ships `.claude/agents/research/.gitkeep` so the directory pre-exists — creating an
  agents directory for the first time in a scope is one of the three cases that needs a restart.

## Agent definitions

**`claude-code/.claude/agents/researcher.md`** — the leaf.

```
name: researcher
description: Research specialist — answers ONE self-contained question from the web, public
             repo docs, and this codebase. Use for a single lookup, or as the child of
             deep-researcher. Does not fan out and does not write files.
tools: Read, Grep, Glob, mcp__web-search__web_search, mcp__web-search__ensure_searxng,
       mcp__deepwiki__ask_question, mcp__deepwiki__read_wiki_contents
model: sonnet
```

`tools` is declared explicitly and deliberately: **omitting it inherits every subagent tool**, which
would silently hand the leaf `Write` and `Agent` and stop it being a leaf.

**`claude-code/.claude/agents/deep-researcher.md`** — the orchestrator.

```
name: deep-researcher
description: Research specialist — orchestrates a fanned-out investigation. Recon, decompose,
             spawn researchers (deep) or author + spawn tailored rsr-* specialists (special),
             synthesize, write a report. Caller MUST supply mode + depth + breadth.
tools: Read, Grep, Glob, Write, Agent, mcp__web-search__web_search,
       mcp__web-search__ensure_searxng, mcp__deepwiki__ask_question,
       mcp__deepwiki__read_wiki_contents
model: opus
```

Bare `Agent`, not `Agent(researcher)` — the type list is ignored in a subagent definition, so the
constraint "spawn only `researcher` or `rsr-*`, never a build role" is written into the body.

**`claude-code/.claude/researcher-template.md`** — sibling of the existing `agent-template.md`, same
house style. What an orchestrator copies and edits when authoring a specialist. Carries the drift
fences and the depth-dependent `tools` line as instructions in an HTML comment footer.

## CLAUDE.md block

One block, because every agent reads this file first — no per-agent edits. Extends/replaces the
research clause at `CLAUDE.md:127`.

```
## Research
Outside knowledge or unfamiliar-domain digging goes to research, not inline.
Agents: researcher (one question, cheap) | deep-researcher (fan-out, writes a report).

MAIN THREAD ONLY — the depth menu.
Subagents cannot call AskUserQuestion. When any agent asks for research, or the user
does, the MAIN THREAD presents the depth menu (Quick / Deep / Special / Custom) and
spawns with mode + depth + breadth baked into the prompt. Never guess the depth.

Fences at every level:
- carry the ROOT QUESTION verbatim into every child prompt
- children narrow, never widen — off-scope finds are reported as open threads, not chased
- every child returns `relevance:`; unfillable relevance = drift, and it says so
- research agents spawn only researcher or rsr-* — never a build role
- reports: .claude/research/YYYY-MM-DD-<topic>.md
- authored specialists: .claude/agents/research/rsr-<domain>.md, description starts
  "Research specialist —", glob and reuse before authoring a new one
- concurrency cap is 20; breadth 6 at depth 2 queues
```

## Local tree

`local/README.md:6` — *"No subagent Task tool here"*. `local/run.py` dispatches one agent per
actionable task-board row. So the local fan-out primitive is the one already documented in
`local/instructions.md`: **delegate = add a sub-task**.

- `local/agents/researcher.md` — compressed leaf. `web_search` / `deepwiki_ask` / `grep`.
- `local/agents/deep-researcher.md` — compressed orchestrator. Fans out by appending
  `- T<id> owner=rsr-<domain> title="<sub-question>" status=todo` rows and setting itself
  `blocked deps=<ids>`. Dispatcher runs them; unblock → synthesize.
- `local/instructions.md` — mirror rule, ~5 lines.

Two honest limits, recorded rather than hidden: the local dispatcher runs **one agent at a time**, so
local fan-out is sequential across dispatcher passes; and there is **no user in the loop**, so the
depth menu does not exist locally — mode/depth/breadth ride in the task title.

## Platform facts (verified 2026-09-03, code.claude.com/docs/en/sub-agents)

These are the load-bearing constraints. Each corrected an earlier assumption in this design.

| Fact | Quote | Consequence |
|---|---|---|
| Nesting works | *"a subagent can spawn subagents of its own, up to three layers below the main conversation"* | The recursion is real. Depth capped at 3 regardless of caller. `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` tunes it; `1` disables. |
| `Task` renamed | *"In version 2.1.63, the Task tool was renamed to Agent."* Old name still an alias. | New files use `Agent`. Existing `Task` in `architect.md`/`CLAUDE.md` still works but is stale. |
| Allowlist is main-thread only | *"any type list inside the parentheses is ignored"* in a subagent definition | `Agent(researcher)` would silently be bare `Agent`. Containment is a written rule. |
| Omitted `tools` inherits all | *"Inherits every tool available to subagents if omitted."* | The leaf MUST declare `tools` or it stops being a leaf. |
| Hot-reload | *"When you add or edit a subagent file on disk, or ask Claude to write one for you, Claude Code detects the change within a few seconds … no restart needed."* | Author-then-spawn works. Batch per level to give the watcher slack. |
| New agents dir needs restart | one of three documented exceptions | Ship `.claude/agents/research/.gitkeep`. |
| Subdirs scanned recursively | *"identity comes only from the `name` frontmatter field"* | `.claude/agents/research/` is safe. |
| Collisions are silent | *"loads only one of them, chosen by filesystem read order"* | `rsr-` prefix is mandatory, not cosmetic. |
| No structured params | *"Claude composes a delegation message … the subagent works from there."* | mode/depth/breadth pass as natural language in the prompt. |
| Concurrency cap 20 | default concurrent subagent limit | breadth 4 at depth 2 = 16 concurrent, fits. breadth 6 = 36, queues. |
| `AskUserQuestion` removed from subagents | listed among tools removed | The depth menu must fire in the main thread. |

## Risks

- **Roster growth.** Persist + per-level authoring means a few big investigations can leave 30+
  `rsr-*` files. Reuse-first globbing slows it; nothing stops it. Accepted for v1; a `--clean` pass
  is future work.
- **Cost.** `special, depth 2, breadth 4` = up to 21 agents, orchestrators on opus. The menu states
  the count before spawning, which is the mitigation.
- **Hot-reload — measured, not predicted.** Two distinct cases, not one. (1) Editing or adding an
  agent file **inside an already-existing watched directory** — e.g. authoring `rsr-*` files
  during a `special`-mode run — hot-loads within seconds; this is the platform's own documented
  behavior and Task 8's Scenario E is the live test of it, still pending. (2) **Creating an agents
  directory for the first time in a scope does not hot-load at all** — this was probed directly:
  `/Users/aayushgour/Desktop/harness/.claude/agents/` was created fresh, a throwaway agent file
  dropped into it, and a spawn attempted twice, ~90 seconds apart. Both attempts returned `Agent
  type '<name>' not found`. This is why Task 8's whole scenario matrix is deferred to a fresh
  session rather than run immediately — case (2) is one of the platform's three documented
  restart-required exceptions, and no amount of waiting inside the same session clears it. Full
  detail: `docs/superpowers/plans/2026-09-03-research-agents-test-log.md`.
- **Fence is advisory.** With the allowlist unavailable, nothing structurally prevents a research
  agent spawning a build role — only the written rule. Detectable in the report's "agents used"
  section. Unmeasured — Scenario I (Task 8) is the live test of whether it holds under an actual
  attempt, still pending.
- **deepwiki MCP availability.** The server was observed disconnected during design, and again
  during Task 8's setup work. Agents listing `mcp__deepwiki__*` must degrade to `web_search`, not
  fail.
- **`local/` does not execute.** `local/run.py:83` raises `NotImplementedError("Wire seam 1 to your
  Hermes runtime")`. The local files are spec-parity, not running code.
- **Local dispatcher: `blocked` rows are never reconsidered, even once every dep is done.** This is
  **pre-existing** in `local/run.py` and affects the harness's whole documented delegation
  primitive, not just research. `next_task()` tests `t["status"] in ACTIONABLE`
  (`{"todo","review","test"}`) *before* it looks at `deps` — a `blocked` row fails that first test
  and is skipped outright, so its `deps` are never even read. Confirmed by simulation: a board with
  parent `status=blocked deps=T2` and child `T2 status=done` yields `next_task() == (None, None)`
  — nothing is ever picked up. `local/instructions.md:34` already documents the same
  block-then-wait pattern for ordinary (non-research) delegation, so this bug predates and is
  broader than the research work — it was not introduced here, only surfaced by it. Our own files
  now state the workaround explicitly: the child that clears the last open dependency must flip
  the parent row back to `status=todo` itself; nothing does this automatically
  (`local/agents/deep-researcher.md`, `local/agents/researcher.md`, `local/instructions.md`).
  `local/run.py` was deliberately **not** modified — fixing the dispatcher itself is out of this
  design's scope, and the workaround is enough to keep the documented rows honest.

## Out of scope / future

- Pruning or usage-tracking of `rsr-*` agents (`/research --clean`).
- A `/research` slash command. The main thread's menu is the entry point in v1.
- Caching or dedup of research reports across sessions.
- Wiring `local/run.py`'s two seams.
- Research feeding `project-context.md` decisions automatically — the caller does that.

## Files touched

- `claude-code/.claude/agents/researcher.md` — new
- `claude-code/.claude/agents/deep-researcher.md` — new
- `claude-code/.claude/researcher-template.md` — new
- `claude-code/.claude/agents/research/.gitkeep` — new
- `claude-code/CLAUDE.md` — modified (## Research block; `Task` → `Agent` in the delegation spec)
- `local/agents/researcher.md` — new
- `local/agents/deep-researcher.md` — new
- `local/instructions.md` — modified (research mirror rule)
- `local/README.md` — modified (roster line)
- `setup-team.py` — modified (seed `.claude/research/`; roster hint text)
- `decisions.md` — modified (decision entry)

## Verification

- Every new/modified agent file's frontmatter parses and lists only tools that exist.
- `researcher` has no `Write` and no `Agent`; `deep-researcher` has both.
- Spawn `deep-researcher` in `deep` mode on a real question: 1 + N children appear, a report lands in
  `.claude/research/`, and the returned summary cites it.
- Spawn in `special` mode: an `rsr-*.md` is authored in `.claude/agents/research/`, then spawned in
  the same session — this is the hot-reload claim under test.
- Re-run `special` on a related question: the existing `rsr-*` is **reused**, not re-authored.
- Drift check: read the report's per-child `relevance:` lines; every one bears on the root question.
- `setup-team.py --force` into a scratch dir produces `.claude/agents/research/` and both new agents.
