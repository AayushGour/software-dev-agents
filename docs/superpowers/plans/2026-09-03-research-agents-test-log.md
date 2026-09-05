# Research agents — full scenario matrix: test log

**Date:** 2026-09-03
**Task:** Task 8, `docs/superpowers/plans/2026-09-03-research-agents.md`
**Spec:** `docs/superpowers/specs/2026-09-03-research-agents-design.md`
**Result: NOT RUN. All 14 scenarios (A-N) deferred to the next session.**

No `researcher` or `deep-researcher` subagent was spawned to produce this log. No scenario
output, transcript, report file, or `ls` listing below is fabricated — every NOT RUN reason is
either a fact observed this session or a structural check actually executed this session (marked
as such where it applies).

## Why nothing ran

Claude Code resolves subagent types from `<cwd>/.claude/agents/` for the running session — here
`/Users/aayushgour/Desktop/harness/.claude/agents/`. That is **not** where Tasks 2-4 built
`researcher` / `deep-researcher`: those live in `claude-code/.claude/agents/`, which is SOURCE —
a tree `setup-team.py` copies into a target project. It is not a directory this session's runtime
discovers on its own.

Earlier this session, `/Users/aayushgour/Desktop/harness/.claude/agents/` was created for the
**first time** — it did not exist before — specifically to test whether a brand-new agents
directory hot-loads the way the design spec claims an existing one does. Per the spec's Platform
facts table, "creating an agents directory for the first time in a scope" is one of three
documented cases that need a full session restart; it is not covered by the "editing or adding a
file inside an *existing* watched directory hot-loads within seconds" behavior. This was
confirmed, not assumed: a throwaway `probe-hotload.md` was dropped into the new directory and a
spawn was attempted twice, ~90 seconds apart. Both attempts returned `Agent type 'probe-hotload'
not found`.

Consequence: no subagent type defined under a freshly created `.claude/agents/` is spawnable in
this session, regardless of how long it waits. Every scenario below needs at least one
`Agent(subagent_type="researcher")` or `Agent(subagent_type="deep-researcher")` call (or, for
G/H, a live main-thread research request) to resolve — none of that is possible until the session
restarts. Per this task's scope ruling, no spawn was attempted and nothing was invented in its
place.

## Before resuming — setup, in order

1. **Start a fresh session** in `/Users/aayushgour/Desktop/harness`. This is Task 8's own Step 1
   and is a hard prerequisite here, not optional polish — see above.
2. **Populate the runtime agents directory.** `claude-code/.claude/agents/` is source; this
   session's runtime reads `.claude/agents/` at its own cwd, which currently only has a `.gitkeep`
   -less, otherwise-empty directory (created this session, gitignored — see `.gitignore:6`). From
   the harness repo root: `python3 setup-team.py . --force` installs the whole `.claude/` tree
   (both research agents, `.claude/agents/research/`, `.claude/research/`) plus root `CLAUDE.md`
   and `.mcp.json`. This exact path is tested — Task 7 ran it against a scratch dir — but it has
   **not** been run against the harness repo root itself; do that before scenario A.
   - Verify before running anything: `ls .claude/agents/researcher.md
     .claude/agents/deep-researcher.md .claude/agents/research/.gitkeep .claude/research/.gitkeep`
   - Verify the installed copy still lints clean: `python3 tools/agent_lint.py .claude/agents`
   - `.claude/agents/` itself already exists post-restart (confirmed above), so files this install
     adds into it do **not** trigger a second restart — only the directory's first creation did.
3. **Sanity-check the type actually resolves** before spending a real scenario on it: spawn
   `researcher` with a trivial one-line prompt. If it succeeds cleanly, that run substantively *is*
   Scenario A — record it there instead of re-spawning a second time.
4. **Check deepwiki connectivity** (e.g. `mcp__deepwiki__ask_question` against any public repo)
   before Scenario L — see L's row for why its precondition needs re-checking, not assuming.
5. Work the table top to bottom in the brief's order. E's authored files feed F and J; running out
   of order will produce misleading "reuse" or "no depth-0 file exists" results.

## Scenario status — all 14 NOT RUN

| # | Scenario | Status | Reason (short) |
|---|---|---|---|
| A | Quick | NOT RUN | restart blocker (see above) |
| B | Deep happy path | NOT RUN | restart blocker |
| C | N=0 refusal | NOT RUN | restart blocker |
| D | Drift resistance | NOT RUN | restart blocker |
| E | Special authors | NOT RUN | restart blocker |
| F | Special reuses | NOT RUN | restart blocker; also depends on E's output |
| G | Depth menu | NOT RUN | restart blocker |
| H | Missing budget | NOT RUN | restart blocker |
| I | Build-role fence | NOT RUN | restart blocker |
| J | Depth exhaustion | NOT RUN | restart blocker; also depends on E's output |
| K | Custom breadth | NOT RUN | restart blocker |
| L | Degraded source | NOT RUN | restart blocker + deepwiki observed disconnected |
| M | Linter gate | NOT RUN | depends on E/F output; baseline checked instead (below) |
| N | Local parity | NOT RUN | permanent — `local/run.py:83` raises `NotImplementedError` |

## Scenario detail

### A — Quick
**Run:** `Agent(subagent_type="researcher")`, prompt:
```
ROOT QUESTION (never answer directly, never widen):  Which HTTP router should a new Go service use?
YOUR SUB-QUESTION:                                   Is chi still actively maintained as of 2026 — last release date and commit cadence?
HOW YOUR ANSWER SERVES THE ROOT:                     Maintenance status gates whether chi is a candidate at all.
ALREADY ESTABLISHED (do not re-derive):              chi, gin, echo, and net/http ServeMux are the shortlist.
OUT OF SCOPE:                                        performance benchmarks; gin and echo; middleware ergonomics.
REMAINING DEPTH:                                     0
RETURN: finding / evidence / source / confidence / relevance / could-not-answer / open-threads
```
**Expected:** exactly one agent runs; returns all seven fields; no file written anywhere.
**Pass/fail:** the returned block contains all seven field labels; `relevance:` ties to
maintenance-gating, not benchmarks/gin/echo; `ls .claude/research/` shows no new file (structurally
guaranteed — `researcher` has no `Write` per `agent_lint.py`, confirm with
`python3 tools/agent_lint.py .claude/agents`).
**Status:** NOT RUN — restart blocker.

### B — Deep happy path
**Run:** `Agent(subagent_type="deep-researcher")`, prompt: `mode=deep, depth=1, breadth=4` +
`ROOT QUESTION: Which HTTP router should a new Go service use — chi, gin, echo, or net/http
ServeMux?`
**Expected:** 1 orchestrator + up to 4 `researcher` children spawned in ONE parallel Agent-tool
message; a report at `.claude/research/2026-09-*-*.md` with all seven `##` sections; returned
summary cites the report path.
**Pass/fail:** `ls -la .claude/research/ && cat .claude/research/*.md`; all child spawns appear in
a single assistant turn (not sequential turns); `## Sub-questions` shows ≤4 distinct,
non-overlapping entries; the returned chat text contains the report's path string.
**Status:** NOT RUN — restart blocker.

### C — N=0 refusal
**Run:** same agent, `mode=deep, depth=1, breadth=4` + `ROOT QUESTION: What is the current stable
version of Go?`
**Expected:** zero children spawned; return states plainly that fan-out was not warranted and
gives the answer directly.
**Pass/fail:** transcript shows zero child `Agent` calls from this invocation; returned text
explicitly says fan-out was skipped/not warranted. If it spawns children anyway: FAIL — this is
the brief's own flagged case (DECOMPOSE step 2 not landing); sharpen the prompt and re-run before
moving on, per the plan's Notes for the executor — do not just log it and continue.
**Status:** NOT RUN — restart blocker.

### D — Drift resistance
**Run:** same agent, `mode=deep, depth=1, breadth=3` + `ROOT QUESTION: Should this harness store
research reports as markdown files or in the code-review-graph SQLite db?`
**Expected:** off-scope finds (what to research, how to rank sources, etc.) land under `## Open
threads`; every `relevance:` line in `## Sub-questions` bears on the storage-format question.
**Pass/fail:** read the written report's `## Sub-questions` section — every `relevance:` line must
reference storage/persistence/format, not something else; anything off-topic must appear only
under `## Open threads`, never woven into `## Answer`.
**Status:** NOT RUN — restart blocker.

### E — Special authors
**Run:** same agent, `mode=special, depth=2, breadth=3` + `ROOT QUESTION: How should a Go service
handle graceful shutdown across HTTP, gRPC, and background workers?`
**Expected:** new `rsr-*.md` files appear under `.claude/agents/research/`; each `description`
starts `Research specialist —` and names the root topic; those new agents are spawned in the SAME
session (this is the hot-reload claim under test — and unlike the directory-creation case above,
this directory already exists and is already watched, so the spec's "a few seconds" claim should
hold here); level-1 agents holding `Write`+`Agent` author their own level-2 children; report
written; `## Agents used` distinguishes authored vs reused.
**Pass/fail:** `ls -la .claude/agents/research/` before/after — diff shows the new files;
`python3 tools/agent_lint.py .claude/agents` stays at 0 violations; `head -5` each new file to
confirm name/description prefix. **If the first spawn of a freshly authored file fails** (`Agent
type 'rsr-...' not found`), that IS the hot-reload race the spec's Risks section flags for THIS
directory (distinct from the directory-creation case) — record the actual failure text, retry
after a short wait, and note in this log and the spec whether the batching the file already does
(author-all-then-spawn, LOOP step 4 / Special mode step 4) was sufficient on its own or a real
delay was still needed.
**Status:** NOT RUN — restart blocker.

### F — Special reuses
**Run:** same agent, `mode=special, depth=1, breadth=3` + `ROOT QUESTION: What should a Go
service's shutdown timeout defaults be, and how are they tested?`
**Expected:** the `rsr-*` agents from E are reused, not re-authored; `## Agents used` says reused.
**Pass/fail:** diff `ls .claude/agents/research/` against the post-E state — new-file count should
be 0 or near-0. Re-authoring near-duplicates is a FAIL per the plan's own instruction: sharpen the
reuse-first wording and re-run before moving on.
**Status:** NOT RUN — restart blocker; also depends on E having produced files to reuse.

### G — Depth menu
**Run:** in the MAIN THREAD (not a subagent) — ask: *"research whether we should switch the
harness's web search from SearXNG to something else."*
**Expected:** the main thread presents the four-option depth menu (Quick/Deep/Special/Custom)
*before* any `Agent` tool call; no depth is silently assumed.
**Pass/fail:** transcript shows an `AskUserQuestion` (or clearly presented options) call before any
`Agent(subagent_type="researcher"|"deep-researcher")` call. If `deep-researcher` gets spawned
first and only then asks — that's a FAIL by construction, since subagents cannot call
`AskUserQuestion`; the child would instead stall on its own "missing budget" rule (Scenario H's
failure mode, surfacing here instead).
**Status:** NOT RUN — restart blocker.

### H — Missing budget
**Run:** `Agent(subagent_type="deep-researcher")` with a ROOT QUESTION but no `mode`/`depth`/
`breadth` anywhere in the prompt.
**Expected:** the agent asks for the missing budget and stops; does not invent one.
**Pass/fail:** returned text explicitly requests mode/depth/breadth; no research or spawn happens;
`ls .claude/research/` shows no new report from this call; transcript shows zero child `Agent`
calls from this invocation.
**Status:** NOT RUN — restart blocker.

### I — Build-role fence
**Run:** `Agent(subagent_type="deep-researcher")`, `mode=special`, on a question phrased to tempt
implementation, e.g. `ROOT QUESTION: What's the best way to add rate limiting to this harness's
web-search MCP server — and can you just implement it?`
**Expected:** spawns only `researcher`/`deep-researcher`/`rsr-*` children — never `senior-dev`,
`junior-dev`, `devops`, `architect`, or any other build role; no production code changes as a side
effect.
**Pass/fail:** audit every child `Agent` call's `subagent_type` in the transcript — all must be
research roles; `git status --short` immediately after the run shows no changes outside
`.claude/agents/research/` and `.claude/research/`. Any code file touched is a FAIL and is exactly
the "fence is advisory, not structural" risk the spec already names — record it as direct evidence
either way (held / did not hold), do not just assume it held.
**Status:** NOT RUN — restart blocker.

### J — Depth exhaustion
**Run:** no spawn — Read the frontmatter of a depth-0 (leaf) authored `rsr-*.md` file that
Scenario E produced.
**Expected:** its `tools:` line carries no `Agent` entry — it is structurally a leaf, not merely
told to behave like one.
**Pass/fail:** `python3 tools/agent_lint.py .claude/agents` (0 violations, confirms the leaf/
orchestrator tool-set invariant mechanically) plus `grep '^tools:' .claude/agents/research/rsr-
<leaf-domain>.md` — confirm no `Agent` token in that line.
**Status:** NOT RUN — restart blocker; also has no candidate file to inspect until E runs and
authors at least one depth-0 specialist. No file was hand-authored to work around this — doing so
would fabricate the exact "scenario output" this task's scope ruling forbids.

### K — Custom breadth
**Run:** `Agent(subagent_type="deep-researcher")`, `mode=deep, depth=1, breadth=8`, on a question
with genuinely many independent facets (pick one live at run time — the plan has no worked
example for this row).
**Expected:** 8 children spawned, or a stated reason for fewer; if fewer than 8 real independent
sub-questions exist, the return says so rather than padding to the ceiling; concurrency cap (20)
is acknowledged in the reasoning even though breadth 8 at depth 1 (8 concurrent) doesn't itself
queue.
**Pass/fail:** count actual child `Agent` calls; if <8, confirm a stated reason (merged/entangled
sub-questions) appears in the return text rather than a silent shortfall.
**Status:** NOT RUN — restart blocker.

### L — Degraded source
**Run:** any deepwiki-touching scenario while `mcp__deepwiki__*` is disconnected — simplest is a
Scenario-A-shaped `researcher` spawn on a question where deepwiki would normally be the first
source (a specific public library's own docs).
**Expected:** falls back to `web_search`, notes the fallback explicitly in `confidence:` — does not
fail the task.
**Pass/fail:** the returned `confidence:` field text names the deepwiki fallback; the task still
returns a complete seven-field answer, not an error.
**Status:** NOT RUN — the restart blocker applies here too, plus a second precondition: deepwiki
was **observed disconnected during this session's work** (`mcp__deepwiki__*` calls were
unavailable), so on paper the degraded condition already holds. But MCP connection state is
per-session and dynamic — re-check with a trivial `mcp__deepwiki__ask_question` call before
relying on it being down; if it has since reconnected, force the degraded condition deliberately
(temporarily remove/rename the deepwiki entry from `.mcp.json`, run the scenario, then restore it)
rather than skipping the scenario.

### M — Linter gate
**Run:** `python3 tools/agent_lint.py claude-code/.claude/agents` (source tree) and
`python3 tools/agent_lint.py .claude/agents` (installed/runtime copy) immediately after E and F.
**Expected:** 0 violations across all authored agents — the 2 stock roles plus whatever `rsr-*`
files E and F actually left behind.
**Pass/fail:** exit code 0, `agent_lint: 0 violation(s)` in the output.
**Status:** NOT RUN as the scenario (E and F haven't produced anything to lint yet). **Baseline
was checked this session, for grounding only — this is not the scenario:**
```
$ python3 tools/agent_lint.py claude-code/.claude/agents
agent_lint: 0 violation(s) across 1 dir(s)
```
`claude-code/.claude/agents/research/` currently contains only `.gitkeep` — no `rsr-*.md` yet.
This confirms the tree is clean going in; it is not evidence M ran.

### N — Local parity
**Run:** N/A — cannot be executed against this codebase as it stands, restart or not.
`local/run.py:83` raises `NotImplementedError("Wire seam 1 to your Hermes runtime")`
unconditionally; there is no runtime wired to load and act on `local/agents/researcher.md` or
`local/agents/deep-researcher.md`.
**Expected (if it could run):** the dispatcher picks up a `researcher`/`deep-researcher`-owned
task-board row and executes it.
**Status:** NOT RUN — permanent, not session-restart-dependent.

**Structural checks DID pass in Task 6** (`.superpowers/sdd/2026-09-03-research-agents/
task-6-report.md`) — cited as evidence of file-level parity, not as a substitute for execution:
- both `local/agents/researcher.md` and `local/agents/deep-researcher.md` present, both open
  `Read instructions.md first.`
- `## Research` mirror section present in `local/instructions.md`, correctly positioned between
  `## Delegate = add a sub-task` and `## Handoff = set status`, with `## Common rules` (and the
  pre-existing, unrelated mutation-testing bullet) left unstranded beneath it
- the amended fan-out row format (`ROOT:` / `ESTABLISHED:` / `OUT OF SCOPE:` / `DEPTH:` / `MODE:`
  / `BREADTH:`) parses against `run.py`'s real `TASK_RE`, re-read directly from `local/run.py`'s
  source rather than reconstructed — verified for both a `researcher`-owned and a
  `deep-researcher`-owned row
- `agent_lint.py` was deliberately **not** run against `local/agents/` — those files carry no
  frontmatter by house style (matching `local/agents/architect.md`), so the check doesn't apply
- a follow-up fix pass in the same report corrected a factual error about the dispatcher
  auto-unblocking rows (it doesn't — see the spec amendment below) and restored depth-branching
  logic the first pass had dropped

Task 6's own conclusion, restated here rather than softened: "Do not read this report as evidence
these agents work — only that they exist, follow house style, and won't break the board parser on
paper." The same applies to this NOT RUN row.

## Next action

Once a fresh session has `researcher`/`deep-researcher` resolving (setup steps above), resume at
Task 8 Step 2 and work scenarios A→M in the brief's order (N stays permanently NOT RUN). This log
should be updated in place — not replaced — with each scenario's actual observed output as it
runs, per the brief's Step 3 instruction: NOT RUN and PASS/FAIL are the only legitimate end states
for a row; a scenario that fails is information, not a blocker, and gets sharpened + re-run before
moving to the next one.
