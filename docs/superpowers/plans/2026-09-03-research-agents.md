# Research Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `researcher` (cheap leaf) and `deep-researcher` (fan-out orchestrator with `deep` and `special` modes) to both harness trees, wired through `CLAUDE.md`, and prove all modes work end to end.

**Architecture:** Two agent definitions per tree plus a template the orchestrator copies when authoring tailored `rsr-*` specialists. Containment and drift control are prompt rules, not platform walls — the platform ignores `Agent(type)` allowlists inside subagent definitions — so a stdlib linter (`tools/agent_lint.py`) enforces mechanically what it can: tool-set invariants, name uniqueness, and the `rsr-` naming contract. The depth menu lives in the main thread because subagents cannot call `AskUserQuestion`.

**Tech Stack:** Markdown agent definitions with YAML frontmatter; Python 3 stdlib (`unittest`, `re`, `pathlib`) for the linter; Claude Code subagent runtime for the live scenario tests.

**Spec:** `docs/superpowers/specs/2026-09-03-research-agents-design.md`

## Global Constraints

Copied verbatim from the spec. Every task's requirements implicitly include these.

- Agent files live in `.claude/agents/`, scanned **recursively**; identity comes only from the `name` frontmatter field.
- Authored specialists: `.claude/agents/research/rsr-<domain>.md`. `description` MUST start `Research specialist —`.
- Name collisions are **silent** — `"loads only one of them, chosen by filesystem read order"`. The `rsr-` prefix is mandatory.
- Omitting `tools` **inherits every subagent tool**. Every agent in this plan declares `tools` explicitly.
- `Agent(type1, type2)` allowlists are **ignored inside a subagent definition** — use bare `Agent`, enforce the fence in prose.
- Subagents cannot call `AskUserQuestion`. The depth menu fires in the **main thread only**.
- Nesting is capped at **3 layers below the main conversation**. Concurrency cap is **20**.
- Reports: `.claude/research/YYYY-MM-DD-<topic>.md`.
- Budget arithmetic: agents = `1 + b + b²` to `depth` terms. `deep` = depth 1 / breadth 4 = 5. `special` = depth 2 / breadth 4 = 21.
- Python: stdlib only, `unittest`, run as `python3 -m unittest`. Match `tools/board_lint.py` house style (module docstring, module-level constants, fails open).
- Commits: no `Co-Authored-By` trailer, no session trailer.

---

### Task 1: `tools/agent_lint.py` — frontmatter invariant linter

The one mechanically enforceable part of the design. Written first so every later task has a red/green gate.

**Files:**
- Create: `tools/agent_lint.py`
- Create: `tools/test_agent_lint.py`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `parse_frontmatter(text: str) -> dict | None` — returns `{key: value}` of the leading `---` block, or `None` if absent. Values stay raw strings.
  - `tools_of(fm: dict) -> list[str] | None` — split `tools:` on commas, stripped. `None` when the key is absent (meaning "inherits everything").
  - `lint_tree(agents_dir: Path) -> list[str]` — returns a list of human-readable violation strings; empty list means clean.
  - `main(argv) -> int` — CLI, exit 1 when violations exist.

- [ ] **Step 1: Write the failing tests**

```python
"""Unit tests for agent_lint — frontmatter invariants for .claude/agents/*.md.

Pure logic, no filesystem beyond tmp dirs. Run from the repo root:
    PYTHONPATH=tools python3 -m unittest test_agent_lint -v
"""

import tempfile
import unittest
from pathlib import Path

import agent_lint as al


def write(d: Path, rel: str, body: str) -> None:
    p = d / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


LEAF = """---
name: researcher
description: Research specialist — answers ONE question.
tools: Read, Grep, Glob
model: sonnet
---
body
"""


class ParseFrontmatter(unittest.TestCase):
    def test_parses_leading_block(self):
        fm = al.parse_frontmatter(LEAF)
        self.assertEqual(fm["name"], "researcher")
        self.assertEqual(fm["model"], "sonnet")

    def test_none_when_absent(self):
        self.assertIsNone(al.parse_frontmatter("# just a heading\n"))

    def test_tools_absent_is_none_not_empty(self):
        fm = al.parse_frontmatter("---\nname: x\ndescription: y\n---\n")
        self.assertIsNone(al.tools_of(fm))

    def test_tools_split_and_stripped(self):
        self.assertEqual(al.tools_of({"tools": "Read,  Grep , Glob"}),
                         ["Read", "Grep", "Glob"])


class LintTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_clean_tree_has_no_violations(self):
        write(self.d, "researcher.md", LEAF)
        self.assertEqual(al.lint_tree(self.d), [])

    def test_missing_tools_key_is_a_violation(self):
        write(self.d, "a.md", "---\nname: a\ndescription: d\n---\n")
        self.assertTrue(any("declare tools" in v for v in al.lint_tree(self.d)))

    def test_duplicate_names_across_subdirs_flagged(self):
        write(self.d, "researcher.md", LEAF)
        write(self.d, "research/copy.md", LEAF)
        self.assertTrue(any("duplicate name" in v for v in al.lint_tree(self.d)))

    def test_researcher_must_not_hold_write_or_agent(self):
        bad = LEAF.replace("tools: Read, Grep, Glob",
                           "tools: Read, Grep, Glob, Write, Agent")
        write(self.d, "researcher.md", bad)
        vs = al.lint_tree(self.d)
        self.assertTrue(any("researcher" in v and "Write" in v for v in vs))
        self.assertTrue(any("researcher" in v and "Agent" in v for v in vs))

    def test_research_subdir_requires_rsr_prefix(self):
        write(self.d, "research/grpc.md", LEAF.replace("name: researcher", "name: grpc"))
        self.assertTrue(any("rsr-" in v for v in al.lint_tree(self.d)))

    def test_rsr_agent_requires_description_prefix(self):
        body = LEAF.replace("name: researcher", "name: rsr-grpc") \
                   .replace("description: Research specialist — answers ONE question.",
                            "description: gRPC expert.")
        write(self.d, "research/rsr-grpc.md", body)
        self.assertTrue(any("Research specialist" in v for v in al.lint_tree(self.d)))

    def test_agent_type_allowlist_is_rejected(self):
        body = LEAF.replace("name: researcher", "name: deep-researcher") \
                   .replace("tools: Read, Grep, Glob", "tools: Read, Agent(researcher)")
        write(self.d, "deep-researcher.md", body)
        self.assertTrue(any("ignored inside a subagent" in v for v in al.lint_tree(self.d)))

    def test_task_alias_allowlist_also_rejected(self):
        body = LEAF.replace("name: researcher", "name: deep-researcher") \
                   .replace("tools: Read, Grep, Glob", "tools: Read, Write, Task(researcher)")
        write(self.d, "deep-researcher.md", body)
        self.assertTrue(any("ignored inside a subagent" in v for v in al.lint_tree(self.d)))

    def test_deep_researcher_needs_agent_and_write(self):
        body = LEAF.replace("name: researcher", "name: deep-researcher")
        write(self.d, "deep-researcher.md", body)
        vs = al.lint_tree(self.d)
        self.assertTrue(any("deep-researcher" in v and "Agent" in v for v in vs))
        self.assertTrue(any("deep-researcher" in v and "Write" in v for v in vs))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=tools python3 -m unittest test_agent_lint -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_lint'`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Frontmatter invariants for .claude/agents/*.md — the mechanical half of the
research-agent contract (docs/superpowers/specs/2026-09-03-research-agents-design.md).

Claude Code resolves name collisions by filesystem read order and silently loads
one file, and an omitted `tools:` key inherits every subagent tool. Both failures
are invisible at runtime, so they are checked here instead.

Enforced:
  1. every agent declares `tools:` explicitly (omitting it inherits everything)
  2. `name` is unique across the whole tree, subdirectories included
  3. `researcher` is a leaf — no Write, no Agent
  4. `deep-researcher` is an orchestrator — has both Write and Agent
  5. files under agents/research/ are named rsr-* and describe themselves as
     "Research specialist —"
  6. no Agent(type, ...) allowlists — the type list is ignored in a subagent
     definition, so writing one states a guarantee that does not hold

Usage:  python3 tools/agent_lint.py [agents_dir ...]
Exit 1 with one line per violation; exit 0 when clean."""
import re
import sys
from pathlib import Path

DEFAULT_DIRS = ("claude-code/.claude/agents",)
RESEARCH_SUBDIR = "research"
RSR_PREFIX = "rsr-"
DESC_PREFIX = "Research specialist —"
LEAF_FORBIDDEN = ("Write", "Agent")
ORCHESTRATOR_REQUIRED = ("Write", "Agent")

_FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_ALLOWLIST_RE = re.compile(r"\b(?:Agent|Task)\s*\(")   # Task is the pre-2.1.63 alias


def parse_frontmatter(text: str):
    """Leading --- block as {key: raw string value}, or None if there isn't one."""
    m = _FM_RE.match(text)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def tools_of(fm: dict):
    """Declared tools as a list. None means the key is absent — inherits everything."""
    raw = fm.get("tools")
    if raw is None:
        return None
    return [t.strip() for t in raw.split(",") if t.strip()]


def lint_tree(agents_dir: Path) -> list:
    violations = []
    seen = {}
    for path in sorted(agents_dir.rglob("*.md")):
        rel = path.relative_to(agents_dir).as_posix()
        fm = parse_frontmatter(path.read_text())
        if fm is None:
            violations.append(f"{rel}: no frontmatter block")
            continue
        name = fm.get("name", "")
        desc = fm.get("description", "")
        if not name:
            violations.append(f"{rel}: no name field")
            continue
        if name in seen:
            violations.append(f"{rel}: duplicate name '{name}' (also {seen[name]}) — "
                              "Claude Code loads only one, by filesystem read order")
        seen[name] = rel

        raw_tools = fm.get("tools")
        tools = tools_of(fm)
        if tools is None:
            violations.append(f"{rel}: must declare tools explicitly — "
                              "an omitted key inherits every subagent tool")
            continue
        if _ALLOWLIST_RE.search(raw_tools):
            violations.append(f"{rel}: Agent(...) allowlist is ignored inside a subagent "
                              "definition — use bare Agent and state the fence in the body")

        if name == "researcher":
            for forbidden in LEAF_FORBIDDEN:
                if any(t == forbidden or t.startswith(forbidden + "(") for t in tools):
                    violations.append(f"{rel}: researcher is a leaf and must not hold {forbidden}")
        if name == "deep-researcher":
            for required in ORCHESTRATOR_REQUIRED:
                if not any(t == required or t.startswith(required + "(") for t in tools):
                    violations.append(f"{rel}: deep-researcher orchestrates and needs {required}")

        if rel.split("/")[0] == RESEARCH_SUBDIR:
            if not name.startswith(RSR_PREFIX):
                violations.append(f"{rel}: agents under {RESEARCH_SUBDIR}/ must be named "
                                  f"{RSR_PREFIX}<domain>, got '{name}'")
            if not desc.startswith(DESC_PREFIX):
                violations.append(f"{rel}: description must start '{DESC_PREFIX}' so the "
                                  "router never mistakes it for a build role")
    return violations


def main(argv) -> int:
    dirs = argv[1:] or list(DEFAULT_DIRS)
    violations = []
    for d in dirs:
        p = Path(d)
        if p.is_dir():
            violations += [f"{d}/{v}" for v in lint_tree(p)]
    for v in violations:
        print(v, file=sys.stderr)
    print(f"agent_lint: {len(violations)} violation(s) across {len(dirs)} dir(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/aayushgour/Desktop/harness && PYTHONPATH=tools python3 -m unittest test_agent_lint -v`
Expected: PASS, 12 tests.

- [ ] **Step 5: Run it against the existing tree — it must be clean before we add anything**

Run: `cd /Users/aayushgour/Desktop/harness && python3 tools/agent_lint.py claude-code/.claude/agents`
Expected: `agent_lint: 0 violation(s) across 1 dir(s)`, exit 0.
Verified 2026-09-03: all 10 existing agents declare `tools:`, every `name` is unique, none sits
under `research/`, and none uses a parenthesised allowlist — so this run is clean before any new
file lands. If it is not, the linter is wrong; do NOT rewrite the existing agents to satisfy it.

- [ ] **Step 6: Document it in `tools/README.md`**

Add one row to the tools table, matching the existing rows' format:

```markdown
| `agent_lint.py` | Frontmatter invariants for `.claude/agents/*.md` — explicit `tools:`, unique names, leaf/orchestrator tool sets, `rsr-` naming. `python3 tools/agent_lint.py <agents_dir>` |
```

- [ ] **Step 7: Commit**

```bash
git add tools/agent_lint.py tools/test_agent_lint.py tools/README.md
git commit -m "feat: agent_lint — frontmatter invariants for .claude/agents

Name collisions and an omitted tools: key both fail silently at runtime
(one file loaded by filesystem read order; every subagent tool inherited),
so they are checked mechanically instead."
```

---

### Task 2: `researcher` — the leaf agent

**Files:**
- Create: `claude-code/.claude/agents/researcher.md`

**Interfaces:**
- Consumes: `tools/agent_lint.py` from Task 1.
- Produces: subagent type `researcher`. Every later task spawns it by that name. Returns free text in the fixed shape: `finding / evidence / source / confidence / relevance / could-not-answer / open-threads`.

- [ ] **Step 1: Write the failing check**

Run: `cd /Users/aayushgour/Desktop/harness && python3 tools/agent_lint.py claude-code/.claude/agents && test -f claude-code/.claude/agents/researcher.md`
Expected: linter passes (0 violations) but `test -f` FAILS — the file does not exist yet.

- [ ] **Step 2: Write the agent**

```markdown
---
name: researcher
description: Research specialist — answers ONE self-contained question from the web, public repo docs, and this codebase. Use for a single lookup ("which library", "does X support Y", "what changed in v3"), or as a child of deep-researcher. Does not fan out, does not write files.
tools: Read, Grep, Glob, mcp__web-search__web_search, mcp__web-search__ensure_searxng, mcp__deepwiki__ask_question, mcp__deepwiki__read_wiki_contents
model: sonnet
---
# Researcher  (leaf — one question, one answer)

Read CLAUDE.md (project root) first — including the **STRICT DONE gate**. You are NOT done until you satisfy it.

DO: answer the ONE question you were given. Nothing adjacent, nothing broader.

## Method
1. Read your prompt's `ALREADY ESTABLISHED` block. Do not re-derive any of it.
2. Search: `web_search` for current external fact; `deepwiki_ask` / `read_wiki_contents` for a public repo's docs; Grep/Glob/Read for how this codebase already does it. Use the cheapest source that settles the question.
3. Prefer primary sources — a project's own docs or source over a blog summarising them. Note the date of anything version-sensitive.
4. Stop when the question is answered. More searching after that is drift, not thoroughness.

## Return exactly this shape
```
finding:          <the answer, 1-5 sentences>
evidence:         <what actually supports it — versions, quotes, file:line>
source:           <URLs / repo paths, one per line>
confidence:       high | medium | low  + one clause on why
relevance:        <how this bears on the ROOT QUESTION in your prompt>
could-not-answer: <what you could not settle, or "nothing">
open-threads:     <off-scope things worth someone else's time, or "none">
```

**`relevance:` is not optional.** If you cannot honestly connect your finding to the ROOT QUESTION, you have drifted — say exactly that in the field instead of inventing a connection.

**OUT OF SCOPE is a wall.** Something interesting outside your sub-question goes in `open-threads:` and nowhere else. Do not chase it. Your spawner decides whether it becomes a branch.

If `web_search` fails, call `ensure_searxng` once and retry. If deepwiki is unreachable, fall back to `web_search` and say so in `confidence:` — never fail the task over one dead source.

CONSULT: nobody. You are a leaf — you have no Agent tool and cannot delegate.
NEVER: fan out, write files, answer the root question directly, widen your sub-question, pad with adjacent findings.
DONE: the seven fields above are filled, `relevance:` honestly.
```

- [ ] **Step 3: Verify the linter accepts it**

Run: `cd /Users/aayushgour/Desktop/harness && python3 tools/agent_lint.py claude-code/.claude/agents`
Expected: `agent_lint: 0 violation(s)`, exit 0. Specifically no "leaf must not hold Write/Agent" line.

- [ ] **Step 4: Verify it actually runs — SCENARIO A (quick mode)**

Wait a few seconds for the file watcher, then spawn it with the Agent tool:

- `subagent_type`: `researcher`
- prompt:
```
ROOT QUESTION (never answer directly, never widen):  Which HTTP router should a new Go service use?
YOUR SUB-QUESTION:                                   Is chi still actively maintained as of 2026 — last release date and commit cadence?
HOW YOUR ANSWER SERVES THE ROOT:                     Maintenance status gates whether chi is a candidate at all.
ALREADY ESTABLISHED (do not re-derive):              chi, gin, echo, and net/http ServeMux are the shortlist.
OUT OF SCOPE:                                        performance benchmarks; gin and echo; middleware ergonomics.
REMAINING DEPTH:                                     0
RETURN: finding / evidence / source / confidence / relevance / could-not-answer / open-threads
```

Expected: exactly ONE agent runs. Returns all seven fields. `relevance:` ties to maintenance-gating. Says nothing about gin, echo, or benchmarks. No file written anywhere.

- [ ] **Step 5: Record the result and commit**

Paste the agent's returned block into the commit body as evidence.

```bash
git add claude-code/.claude/agents/researcher.md
git commit -m "feat: researcher agent — leaf, one question, no fan-out

tools: declared explicitly; an omitted key would inherit Write and Agent
and stop it being a leaf. Returns a fixed seven-field shape so a spawner
can synthesize across children without reparsing prose."
```

---

### Task 3: `deep-researcher` — orchestrator, `deep` mode

Special mode is deliberately NOT in this task — it needs the template from Task 4, and a reviewer should be able to reject special mode while keeping deep mode.

**Files:**
- Create: `claude-code/.claude/agents/deep-researcher.md`
- Create: `claude-code/.claude/agents/research/.gitkeep`
- Create: `claude-code/.claude/research/.gitkeep`

**Interfaces:**
- Consumes: subagent type `researcher` (Task 2); `tools/agent_lint.py` (Task 1).
- Produces: subagent type `deep-researcher`. Caller MUST pass `mode` (`deep` | `special`), `depth`, `breadth`. Writes `.claude/research/YYYY-MM-DD-<topic>.md` and returns `summary + report path`.

- [ ] **Step 1: Create the two directories first**

The spec's restart caveat: *"Creating a new `agents` directory for the first time in a scope"* is one of three cases needing a restart. `.claude/agents/` already exists, so the `research/` subdirectory is covered by the recursive watch — but it must exist on disk before anything writes into it.

```bash
cd /Users/aayushgour/Desktop/harness
mkdir -p claude-code/.claude/agents/research claude-code/.claude/research
touch claude-code/.claude/agents/research/.gitkeep claude-code/.claude/research/.gitkeep
```

- [ ] **Step 2: Write the failing check**

Run: `cd /Users/aayushgour/Desktop/harness && test -f claude-code/.claude/agents/deep-researcher.md`
Expected: FAIL, exit 1.

- [ ] **Step 3: Write the agent**

```markdown
---
name: deep-researcher
description: Research specialist — orchestrates a fanned-out investigation. Recon, decompose into independent sub-questions, spawn researchers (deep mode) or author and spawn tailored rsr-* specialists (special mode), then synthesize into a report. The caller MUST supply mode, depth, and breadth — this agent never picks its own budget.
tools: Read, Grep, Glob, Write, Agent, mcp__web-search__web_search, mcp__web-search__ensure_searxng, mcp__deepwiki__ask_question, mcp__deepwiki__read_wiki_contents
model: opus
---
# Deep Researcher  (orchestrator — fan out, synthesize, report)

Read CLAUDE.md (project root) first — including the **STRICT DONE gate**. You are NOT done until you satisfy it.

DO: turn ONE root question into a researched, cited answer by fanning out — and stay inside the budget you were given.

**Your caller supplies `mode`, `depth`, `breadth`. If any is missing, ask for it and stop.** You never pick your own budget — the human chose it from a menu and the cost is theirs.

Budget arithmetic: agents = `1 + b + b²` to `depth` terms. `depth 1, breadth 4` = 5. `depth 2, breadth 4` = 21. These are ceilings, not quotas — spawning four children for a two-part question is waste, not thoroughness.

## LOOP
1. **RECON — yourself, cheaply.** `web_search` + Grep the repo. You are not looking for the answer; you are looking for the *shape* of the question: which sub-domains exist, what is already settled, what is genuinely contested.
2. **DECOMPOSE.** Split into N independent sub-questions, `N <= breadth`. Independent means no sub-question needs another's answer first — if two are entangled, merge them or sequence them inside one child. **If recon already answered the root question, N = 0: skip to step 5, report the answer, and say plainly that fan-out was not warranted.** Deep research on a shallow question is waste; refusing to spend is the correct outcome, not a failure.
3. **STAFF.** `mode=deep` → every child is the stock `researcher`, specialised only by its prompt. `researcher` has no Agent tool, so it is always a leaf and `deep` is depth-1 by construction; if the caller asked for `deep` at depth ≥ 2, spawn `deep-researcher` children instead and pass them `depth - 1`.
   `mode=special` → see "Special mode" below.
4. **SPAWN.** All children for a level in ONE message, in parallel. Each child prompt is exactly:
```
ROOT QUESTION (never answer directly, never widen):  <verbatim — do not paraphrase>
YOUR SUB-QUESTION:                                   <one question>
HOW YOUR ANSWER SERVES THE ROOT:                     <one line, you write it>
ALREADY ESTABLISHED (do not re-derive):              <your recon findings>
OUT OF SCOPE:                                        <every sibling's sub-question + explicit exclusions>
REMAINING DEPTH:                                     <depth - 1>
RETURN: finding / evidence / source / confidence / relevance / could-not-answer / open-threads
```
   Listing the siblings under OUT OF SCOPE is what stops four children converging on the same tangent. It is not optional.
5. **SYNTHESIZE.** **Name conflicts, do not average them** — "A says X, B says Y, they disagree on Z" beats a smoothed non-answer. Unanswered stays unanswered. Drop or demote any finding whose `relevance:` does not bear on the root question. Then Write `.claude/research/YYYY-MM-DD-<topic>.md`:
```markdown
# <root question>
**Date:** YYYY-MM-DD   **Mode:** <mode>   **Budget:** depth <d>, breadth <b>   **Agents used:** <n>

## Answer
## Evidence
## Sources
## Confidence
## Conflicts        (what disagreed, and why — never averaged away)
## Open threads     (off-scope finds, for a human to triage)
## Sub-questions    (each one, its child, and its relevance line)
```
   Return to your caller: a short synthesis plus the report path. Not the raw child outputs — that is what your context is for.

## Fences (every level, no exceptions)
- Carry the ROOT QUESTION **verbatim** into every child prompt.
- **Children narrow, never widen.** Off-scope finds are reported as `open-threads:`, never chased. Widening is yours alone, and only from an open thread you deliberately promote.
- Every child returns `relevance:`. Unfillable relevance = drift; such findings are demoted at synthesis.
- **Spawn only `researcher`, `deep-researcher`, or `rsr-*`. Never a build role** (senior-dev, junior-dev, devops, architect…). Research does not write production code. This is a prompt rule and nothing enforces it but you: `Agent(...)` type lists are ignored inside a subagent definition.
- Concurrency cap is 20. `breadth 6` at depth 2 is 36 concurrent and will queue — say so rather than silently stalling.

CONSULT: your caller, when mode/depth/breadth is missing or the root question is ambiguous enough that two readings would produce different research.
NEVER: pick your own budget, spawn a build role, average away a conflict, return raw child transcripts, chase an open thread mid-run.
DONE: report written to `.claude/research/`, summary + path returned, every sub-question accounted for in the report.
```

- [ ] **Step 4: Verify the linter accepts it**

Run: `cd /Users/aayushgour/Desktop/harness && python3 tools/agent_lint.py claude-code/.claude/agents`
Expected: `agent_lint: 0 violation(s)`. Confirms `deep-researcher` holds both `Write` and `Agent`, and that no `Agent(...)` allowlist slipped in.

- [ ] **Step 5: SCENARIO B — deep mode, the happy path**

Spawn `deep-researcher`:
```
mode=deep, depth=1, breadth=4

ROOT QUESTION: Which HTTP router should a new Go service use — chi, gin, echo, or net/http ServeMux?
```
Expected:
- 1 orchestrator + up to 4 `researcher` children, spawned in ONE parallel message.
- A report at `claude-code/.claude/research/2026-09-03-*.md` with all seven sections.
- Returned summary cites the report path.
- The report's `## Sub-questions` section shows four distinct, non-overlapping sub-questions.

Verify on disk: `ls -la claude-code/.claude/research/ && cat claude-code/.claude/research/*.md`

- [ ] **Step 6: SCENARIO C — N=0, the refusal path**

Spawn `deep-researcher`:
```
mode=deep, depth=1, breadth=4

ROOT QUESTION: What is the current stable version of Go?
```
Expected: recon answers it, **zero children spawned**, and the return says plainly that fan-out was not warranted. This is the test that the agent will decline to spend — if it spawns four children for a version lookup, step 2 of the LOOP is not landing and the prompt needs sharpening before moving on.

- [ ] **Step 7: SCENARIO D — drift resistance**

Spawn `deep-researcher`:
```
mode=deep, depth=1, breadth=3

ROOT QUESTION: Should this harness store research reports as markdown files or in the code-review-graph SQLite db?
```
Expected: children stay on storage-format tradeoffs. Anything about *what to research* or *how to rank sources* appears under `## Open threads`, not in the answer. Read every `relevance:` line in the report — each must bear on the storage question.

- [ ] **Step 8: Commit**

Paste the Scenario B report path and the Scenario C refusal text into the commit body as evidence.

```bash
git add claude-code/.claude/agents/deep-researcher.md claude-code/.claude/agents/research/.gitkeep claude-code/.claude/research/.gitkeep
git commit -m "feat: deep-researcher agent — fan-out orchestrator, deep mode

Caller supplies mode/depth/breadth; the agent never picks its own budget.
N=0 at decompose is an explicit success path — refusing to fan out on a
shallow question is the correct outcome. Fences (verbatim root question,
sibling OUT OF SCOPE list, required relevance field) are prompt rules:
Agent(type) allowlists are ignored inside subagent definitions."
```

---

### Task 4: `researcher-template.md` + `special` mode

**Files:**
- Create: `claude-code/.claude/researcher-template.md`
- Modify: `claude-code/.claude/agents/deep-researcher.md` (add the "Special mode" section referenced by LOOP step 3)

**Interfaces:**
- Consumes: `deep-researcher` (Task 3), which references "Special mode" but does not yet define it.
- Produces: authored agents at `.claude/agents/research/rsr-<domain>.md`, named `rsr-<domain>`, `description` starting `Research specialist —`.

- [ ] **Step 1: Write the failing check**

Run: `cd /Users/aayushgour/Desktop/harness && grep -q "## Special mode" claude-code/.claude/agents/deep-researcher.md`
Expected: FAIL, exit 1 — LOOP step 3 currently forward-references a section that does not exist.

- [ ] **Step 2: Write the template**

`claude-code/.claude/researcher-template.md` — sibling of the existing `agent-template.md`, same house style:

```markdown
---
name: rsr-<domain>                 # ALWAYS the rsr- prefix — collisions load silently, by fs read order
description: Research specialist — <root topic>: <domain> aspects. <When to spawn this one.>
tools: Read, Grep, Glob, mcp__web-search__web_search, mcp__web-search__ensure_searxng, mcp__deepwiki__ask_question, mcp__deepwiki__read_wiki_contents
model: sonnet                      # sonnet default; opus only if this domain needs heavy reasoning
---
# <Domain> Researcher  (research specialist — <root topic>)

Read CLAUDE.md (project root) first — including the **STRICT DONE gate**.

DO: <the one slice of the root question this specialist owns>.

## Domain context  (what a fresh agent would otherwise waste a turn learning)
- <vocabulary, key projects, the primary sources worth reading first>
- <what is already settled and must not be re-derived>

## Method
1. Read your prompt's `ALREADY ESTABLISHED` block. Do not re-derive it.
2. <domain-specific: which sources are authoritative here, and in what order>
3. Stop when your sub-question is answered.

## Return exactly this shape
```
finding: / evidence: / source: / confidence: / relevance: / could-not-answer: / open-threads:
```

**OUT OF SCOPE is a wall.** Off-scope finds go in `open-threads:` and nowhere else.

NEVER: answer the root question directly, widen your sub-question, chase an open thread.
DONE: seven fields filled, `relevance:` honestly connected to the root question.

<!--
AUTHORING THIS TEMPLATE (deep-researcher, special mode):
1. Copy to .claude/agents/research/rsr-<domain>.md — the rsr- prefix is mandatory,
   and `description` MUST start "Research specialist —" so the router never mistakes
   this for a build role.
2. Scope it to the ROOT QUESTION, not the domain in general:
   "Research specialist — Go HTTP routing: middleware ergonomics", NOT "gRPC expert".
   The fence must survive into any grandchildren this agent spawns.
3. tools: — this template is a LEAF (remaining depth 0). If remaining depth >= 1,
   ALSO add `Write, Agent` and paste deep-researcher's LOOP steps 2-5 into the body
   so this agent can decompose, author its own children, and synthesize.
4. Declare `tools:` explicitly, always. An omitted key inherits every subagent tool.
5. Never write `Agent(researcher)` — the type list is ignored inside a subagent
   definition, so it states a guarantee that does not hold. Use bare `Agent`.
6. Delete these comments and every <placeholder>.
7. Verify: python3 tools/agent_lint.py claude-code/.claude/agents
-->
```

- [ ] **Step 3: Add the Special mode section to `deep-researcher.md`**

Insert immediately before the `## Fences` heading:

```markdown
## Special mode  (tailored agents, authored per investigation)

`mode=special` replaces stock children with agent files you write yourself. Same fences, same
return shape — the specialisation lives in the FILE instead of the prompt, so it persists and
survives into grandchildren.

Per sub-question:
1. **Reuse first.** Glob `.claude/agents/research/rsr-*.md` and read the descriptions. An
   existing specialist that fits is always better than a new one — reuse is the only brake on
   roster growth, and there is no prune job.
2. **Author only for a genuine domain gap** — an ongoing domain (a protocol, a framework, a
   subsystem), never this one question. Same bar as the architect's team-formation rule in
   CLAUDE.md. A one-off question is a prompt to `researcher`, not a new agent file.
3. Copy `.claude/researcher-template.md` → `.claude/agents/research/rsr-<domain>.md` and fill it:
   - `name: rsr-<domain>` — the prefix is mandatory; collisions load silently by fs read order.
   - `description:` MUST start `Research specialist —` and name the ROOT TOPIC, not just the
     domain: `"Research specialist — Go HTTP routing: middleware ergonomics"`, never
     `"middleware expert"`. The fence has to survive into anything this agent spawns.
   - `tools:` — remaining depth 0 → leaf, exactly the template's list. Remaining depth ≥ 1 →
     ALSO `Write, Agent`, and paste LOOP steps 2-5 into its body so it can decompose, author its
     own children, and synthesize. **Every level authors its own children** — you do not
     pre-author the whole tree.
4. **Author every child for the level FIRST, then spawn them all in one message.** The file
   watcher takes a few seconds to notice a new agent; authoring and immediately spawning one at
   a time races it. Batching gives it slack.

Record every authored agent in the report's `## Agents used` line — authored vs reused.
```

- [ ] **Step 4: Verify the check now passes, and the linter is still clean**

```bash
cd /Users/aayushgour/Desktop/harness
grep -q "## Special mode" claude-code/.claude/agents/deep-researcher.md && echo "section present"
python3 tools/agent_lint.py claude-code/.claude/agents
```
Expected: `section present`, then `agent_lint: 0 violation(s)`.
Note: `researcher-template.md` sits at `.claude/`, NOT `.claude/agents/`, so it is not scanned as an agent — its `<placeholder>` frontmatter must never register as a real subagent.

- [ ] **Step 5: SCENARIO E — special mode authors and spawns**

Spawn `deep-researcher`:
```
mode=special, depth=2, breadth=3

ROOT QUESTION: How should a Go service handle graceful shutdown across HTTP, gRPC, and background workers?
```
Expected:
- New files appear at `claude-code/.claude/agents/research/rsr-*.md`.
- Each is named `rsr-<domain>`, `description` starts `Research specialist —` and names the root topic.
- Those agents are then **spawned in the same session** — this is the hot-reload claim under test.
- Level-1 agents that hold `Write, Agent` author their own level-2 children.
- Report written; `## Agents used` distinguishes authored from reused.

Verify:
```bash
ls -la claude-code/.claude/agents/research/
python3 tools/agent_lint.py claude-code/.claude/agents
head -5 claude-code/.claude/agents/research/rsr-*.md
```
The linter run is the real gate — it proves the authored files honour the naming and tool contract without anyone reading them.

**If the spawn fails because the file was not yet visible:** that is the hot-reload race the spec flagged. Fix by making step 4 explicit — author ALL children, then spawn in a separate message — and re-run. Record the outcome in the spec's Risks section either way.

- [ ] **Step 6: SCENARIO F — reuse beats authoring**

Spawn `deep-researcher` again, on a neighbouring question:
```
mode=special, depth=1, breadth=3

ROOT QUESTION: What should a Go service's shutdown timeout defaults be, and how are they tested?
```
Expected: the `rsr-*` agents from Scenario E are **reused, not re-authored**. `ls claude-code/.claude/agents/research/` shows few or no new files, and the report's `## Agents used` says reused. If it re-authors near-duplicates, the reuse-first instruction is not landing — sharpen it before moving on, because reuse is the only growth brake.

- [ ] **Step 7: Commit**

Paste the `ls` output from both scenarios into the commit body as evidence.

```bash
git add claude-code/.claude/researcher-template.md claude-code/.claude/agents/deep-researcher.md claude-code/.claude/agents/research/
git commit -m "feat: special research mode — tailored rsr-* specialists

Every level authors its own children from researcher-template.md, so the
tree is not pre-planned. Authored agents are scoped to the root question
rather than the domain, so the fence survives into grandchildren, and they
persist for reuse — reuse-first globbing is the only brake on roster growth."
```

---

### Task 5: `CLAUDE.md` routing + the depth menu

**Files:**
- Modify: `claude-code/CLAUDE.md` — replace the research clause at line 127; fix the stale `Task` tool name in the delegation section.

**Interfaces:**
- Consumes: subagent types `researcher`, `deep-researcher` (Tasks 2-4).
- Produces: the main-thread contract every agent reads first. No per-agent frontmatter edits — this file is the single wiring point.

- [ ] **Step 1: Read the current clause and the delegation section**

```bash
cd /Users/aayushgour/Desktop/harness
sed -n '120,135p' claude-code/CLAUDE.md
grep -n '\bTask\b' claude-code/CLAUDE.md
```
Note every `Task` hit — v2.1.63 renamed the tool to `Agent`; the old name still works as an alias, so this is a staleness fix, not a bug fix. Do not touch `task-board`, `task list`, or other prose uses of the word.

- [ ] **Step 2: Write the failing check**

```bash
cd /Users/aayushgour/Desktop/harness && grep -q "^## Research" claude-code/CLAUDE.md
```
Expected: FAIL, exit 1.

- [ ] **Step 3: Replace the research clause with the full block**

Replace the existing bullet at `claude-code/CLAUDE.md:127` (*"Research + fact-check before building on an unfamiliar library or claim…"*) with:

```markdown
## Research
Outside knowledge, or digging in an unfamiliar domain, goes to research — not inline in
whoever happens to be holding the task. Findings, not raw pages, come back.
- **researcher** — one self-contained question, cheap, no fan-out, no files.
- **deep-researcher** — recon, decompose, fan out, synthesize, write a report.

**MAIN THREAD ONLY — the depth menu.** Subagents cannot call AskUserQuestion, so a spawned
agent physically cannot ask. When any agent requests research, or the user does, the MAIN
THREAD presents the menu and spawns with mode + depth + breadth baked into the prompt.
**Never guess the depth** — a research request without a chosen depth is not actionable.

| Option | Budget | Agents | For |
|---|---|---|---|
| Quick | — | 1 | one lookup: which lib, does X support Y, what version. Chat only, no report. |
| Deep | depth 1, breadth 4 | `1 + 4` = 5 | comparisons, tradeoff calls, anything you will cite later. |
| Special | depth 2, breadth 4 | `1 + 4 + 16` = 21 | architecture decisions, unfamiliar domains, where a wrong answer costs weeks. Authors reusable `rsr-*` specialists. |
| Custom | caller sets | caller does the math | scope fences, odd shapes. Concurrency cap is 20 — breadth 6 at depth 2 is 36 concurrent and queues. |

Counts are ceilings. Fewer real sub-questions means fewer agents, and a question that recon
already answers should spawn none at all.

Fences at every level:
- carry the ROOT QUESTION **verbatim** into every child prompt
- children narrow, never widen — off-scope finds are reported as open threads, not chased
- every child returns `relevance:`; unfillable relevance is drift, and it says so
- research agents spawn only `researcher`, `deep-researcher`, or `rsr-*` — **never a build role**
- reports: `.claude/research/YYYY-MM-DD-<topic>.md`
- authored specialists: `.claude/agents/research/rsr-<domain>.md`, `description` starts
  `Research specialist —`; glob and reuse before authoring a new one
- verify a tree of agent files with `python3 tools/agent_lint.py claude-code/.claude/agents`
```

- [ ] **Step 4: Fix the stale tool name**

For each `Task` hit from Step 1 that refers to the delegation *tool* (not the task board, not a task list), change `Task` → `Agent`. Add this note where the delegation tool is first described:

```markdown
(The tool was renamed `Task` → `Agent` in v2.1.63; `Task` still works as an alias. Note that
`Agent(type1, type2)` allowlists only bind an agent running as the main thread — inside a
subagent definition the type list is **ignored**, so a subagent's fence must be written in prose.)
```

- [ ] **Step 5: Verify**

```bash
cd /Users/aayushgour/Desktop/harness
grep -q "^## Research" claude-code/CLAUDE.md && echo "block present"
grep -n "Never guess the depth" claude-code/CLAUDE.md
grep -n '\bTask\b' claude-code/CLAUDE.md   # only task-board / task-list prose should remain
python3 tools/agent_lint.py claude-code/.claude/agents
```

- [ ] **Step 6: SCENARIO G — the menu actually fires**

In a fresh main-thread turn, ask: *"research whether we should switch the harness's web search from SearXNG to something else"*.
Expected: the main thread presents the four-option depth menu **before** spawning anything. It does not silently pick a depth, and it does not spawn `deep-researcher` and let it ask — the subagent cannot.
This is the one behaviour that cannot be linted; it must be observed.

- [ ] **Step 7: Commit**

```bash
git add claude-code/CLAUDE.md
git commit -m "feat: wire research into the team rulebook

One block in the shared rulebook rather than edits to ten agent files.
The depth menu is pinned to the main thread because AskUserQuestion is
unavailable to subagents — a spawned agent cannot ask, so it must be told.
Also refreshes the stale Task tool name (renamed to Agent in v2.1.63)."
```

---

### Task 6: local tree mirror

`local/run.py:83` raises `NotImplementedError`, so nothing here executes. These files are spec-parity: they keep the two trees from drifting and document the fan-out primitive the local harness would use. Verification is structural, not behavioural — say so plainly rather than implying a test ran.

**Files:**
- Create: `local/agents/researcher.md`
- Create: `local/agents/deep-researcher.md`
- Modify: `local/instructions.md`
- Modify: `local/README.md`

**Interfaces:**
- Consumes: the claude-code definitions (Tasks 2-4) as the source of truth to compress.
- Produces: local agent names `researcher`, `deep-researcher` — `local/run.py:load_agent_prompt` resolves `owner=<name>` on a task-board row to `local/agents/<name>.md`.

- [ ] **Step 1: Write the failing check**

```bash
cd /Users/aayushgour/Desktop/harness && test -f local/agents/researcher.md && test -f local/agents/deep-researcher.md
```
Expected: FAIL, exit 1.

- [ ] **Step 2: Write `local/agents/researcher.md`**

Compressed house style — match `local/agents/architect.md`: no frontmatter, opens `Read instructions.md first.`, terse imperatives.

```markdown
# Researcher  (leaf — one question)

Read instructions.md first.

Job: answer the ONE question in your task title. Nothing adjacent.

1. Read the task's ALREADY ESTABLISHED note. Don't re-derive it.
2. web_search for outside fact. deepwiki_ask(repo, q) for a public repo's docs. grep for how this codebase already does it. Cheapest source that settles it.
3. Primary sources over blog summaries. Note dates on anything version-sensitive.
4. Stop when answered. More searching after that is drift.

Return exactly:
finding: / evidence: / source: / confidence: / relevance: / could-not-answer: / open-threads:

relevance = how this bears on the ROOT QUESTION in your task. Can't fill it honestly? You drifted — say so.
OUT OF SCOPE is a wall. Interesting-but-off-scope → open-threads, never chased.
deepwiki dead → fall back to web_search, note it in confidence. Never fail over one dead source.

Never: fan out, answer the root question, widen your sub-question.
Done: 7 fields filled. Log 1 line. Set your task status=done.
```

- [ ] **Step 3: Write `local/agents/deep-researcher.md`**

The fan-out primitive here is the one already documented in `instructions.md` — *"Delegate = add a sub-task"*. No spawning exists in this harness.

```markdown
# Deep Researcher  (orchestrator — fan out via the board)

Read instructions.md first.

Job: one root question → researched, cited answer. Caller sets mode + depth + breadth in the task title. Missing? Set status=blocked and say what you need. Never pick your own budget.

No spawning here (see README). You fan out through the board.

1. RECON yourself: web_search + grep. Find the SHAPE of the question, not the answer.
2. DECOMPOSE into N independent sub-questions, N <= breadth. Recon already answered it? N=0 — write the answer, say fan-out wasn't warranted, done. Refusing to spend is correct, not failure.
3. STAFF. mode=deep → owner=researcher. mode=special → glob agents/ for an rsr-* that fits and REUSE it; only a real ongoing domain gap earns a new agents/rsr-<domain>.md (copy a researcher.md and specialise it).
4. FAN OUT: append one row per sub-question —
   `- T<id> owner=<researcher|rsr-x> title="<sub-question> | ROOT: <verbatim> | OUT OF SCOPE: <siblings> | DEPTH: <n>" status=todo`
   then set your own row `status=blocked deps=<those ids>`. Dispatcher runs them one at a time. It unblocks you when they're done.
5. SYNTHESIZE. Name conflicts, don't average them. Unanswered stays unanswered. Drop findings whose relevance doesn't bear on the root. write_file research/YYYY-MM-DD-<topic>.md: question, answer, evidence, sources, confidence, conflicts, open threads, sub-questions, agents used.

Fences: root question verbatim in every child row. Children narrow, never widen. Every child returns relevance. Owner is only researcher or rsr-* — never a build role.

Never: pick your own budget, average a conflict, chase an open thread mid-run.
Done: report written, summary in your log line, every sub-question in the report.
```

- [ ] **Step 4: Add the mirror rule to `local/instructions.md`**

Append after the `## Delegate = add a sub-task` section, so it sits next to the primitive it uses:

```markdown
## Research
Outside knowledge → researcher (one question) or deep-researcher (fan out, writes a report).
deep-researcher fans out the same way anyone does: append `owner=researcher` rows, set itself
`status=blocked deps=<ids>`. Dispatcher runs them one at a time — local fan-out is sequential,
not parallel.
mode + depth + breadth come in the task title. No user in the loop here, so no depth menu:
whoever writes the task row picks the budget. Reports → `research/YYYY-MM-DD-<topic>.md`.
```

- [ ] **Step 5: Add both to the `local/README.md` roster**

Find the roster/file listing (around `local/README.md:18`) and add the two agents in the existing format.

- [ ] **Step 6: Verify — structural only, and say so**

```bash
cd /Users/aayushgour/Desktop/harness
test -f local/agents/researcher.md && test -f local/agents/deep-researcher.md && echo "files present"
head -3 local/agents/researcher.md local/agents/deep-researcher.md   # both must open "Read instructions.md first."
grep -q "^## Research" local/instructions.md && echo "mirror rule present"
python3 -c "
import sys; sys.path.insert(0, 'local')
import re
from pathlib import Path
# run.py's own TASK_RE must parse the fan-out row shape deep-researcher is told to write
TASK_RE = re.compile(r'-\s*T(?P<id>\S+)\s+owner=(?P<owner>\S+)\s+title=\"(?P<title>[^\"]*)\"'
                     r'.*?(?:deps=(?P<deps>\S+))?\s*status=(?P<status>\S+)')
row = '- T9 owner=researcher title=\"is chi maintained | ROOT: which Go router | OUT OF SCOPE: gin, echo | DEPTH: 0\" status=todo'
m = TASK_RE.search(row)
assert m, 'deep-researcher fan-out row does not parse with run.py TASK_RE'
assert m.group('owner') == 'researcher', m.group('owner')
print('fan-out row parses; owner =', m.group('owner'))
"
```
This last check matters: the pipe-delimited title is unusual, and if `run.py`'s regex cannot parse the row the local fan-out is broken on paper as well as in practice.

**Do not claim these agents were tested.** `local/run.py:83` raises `NotImplementedError("Wire seam 1 to your Hermes runtime")` — nothing in this tree runs. The checks above are structural parity only.

- [ ] **Step 7: Commit**

```bash
git add local/agents/researcher.md local/agents/deep-researcher.md local/instructions.md local/README.md
git commit -m "feat: research agents for the local tree (spec parity)

Fan-out uses the board primitive already documented in instructions.md —
append owner= rows, block on deps — since this harness has no spawn tool.
Not executable: run.py:83 still raises NotImplementedError, so these are
structural parity with the claude-code tree, not running code."
```

---

### Task 7: `setup-team.py` seeding + decisions log

**Files:**
- Modify: `setup-team.py`
- Modify: `decisions.md`

**Interfaces:**
- Consumes: every file from Tasks 1-6.
- Produces: a fresh `setup-team.py` install that includes both research agents and both directories.

- [ ] **Step 1: Read how the tree is copied**

```bash
cd /Users/aayushgour/Desktop/harness && sed -n '20,60p' setup-team.py
```
`install_dotclaude` walks `DOTCLAUDE.rglob("*")` filtered to `p.is_file()`. `pathlib.rglob` **does** return dotfiles (verified), so `.gitkeep` is copied and both directories are created by `copy_file`'s `dst.parent.mkdir(parents=True)`. No new copy logic is needed — confirm this rather than adding code.

- [ ] **Step 2: Write the failing check**

```bash
cd /Users/aayushgour/Desktop/harness
rm -rf /tmp/st-check && mkdir -p /tmp/st-check
python3 setup-team.py /tmp/st-check >/dev/null 2>&1
test -d /tmp/st-check/.claude/agents/research && test -f /tmp/st-check/.claude/agents/deep-researcher.md
```
Expected: PASS already, if Tasks 2-4 landed the files. If it FAILS, the rglob assumption is wrong and `install_dotclaude` needs an explicit directory seed — fix it here.

- [ ] **Step 3: Verify a full install lints clean**

```bash
cd /Users/aayushgour/Desktop/harness
python3 tools/agent_lint.py /tmp/st-check/.claude/agents
ls -la /tmp/st-check/.claude/agents/ /tmp/st-check/.claude/agents/research/ /tmp/st-check/.claude/research/
grep -c "^## Research" /tmp/st-check/CLAUDE.md
```
Expected: 0 violations; both directories present; the Research block present in the installed `CLAUDE.md`.

- [ ] **Step 4: Update the roster hint text**

`setup-team.py:148` prints `"auto-discovers .claude/agents/*.md and routes to the right agent."` Update it to mention the recursive scan and the new roles, so a fresh installer knows research exists:

```python
print("auto-discovers .claude/agents/**/*.md (recursive) and routes to the right agent.")
print("Research: researcher (one question) | deep-researcher (fan-out + report).")
print("Depth menu is main-thread only — see the ## Research block in CLAUDE.md.")
```

- [ ] **Step 5: Record the decision in `decisions.md`**

Append, matching the existing `## YYYY-MM — <title>` / `**What:**` / `**Why:**` format:

```markdown
## 2026-09 — Research agents: researcher, deep-researcher, and special mode

**What:** Two roles — `researcher` (leaf: one question, no fan-out, no files) and
`deep-researcher` (orchestrator: recon → decompose → fan out → synthesize → report to
`.claude/research/`). Three modes chosen per invocation via a **main-thread depth menu**
(Quick 1 / Deep 5 / Special 21 / Custom): `deep` fans out with stock generic children
specialised by prompt; `special` authors tailored `rsr-<domain>.md` specialists under
`.claude/agents/research/` that persist for reuse and, at depth ≥ 1, author their own
children. Wired through one `## Research` block in `CLAUDE.md` rather than editing ten
agent files. `tools/agent_lint.py` enforces the frontmatter invariants. Mirrored into
`local/` for parity, fanning out via task-board rows.

**Why:** the team had research tools but no research role — every agent researched inline,
burning its own planning context, with no budget and no artifact. Four platform facts
shaped the design and each corrected an earlier assumption: subagent nesting is real but
capped at 3 layers; `Agent(type)` allowlists are **ignored inside a subagent definition**,
so containment is a prompt rule and the linter covers what it can; an omitted `tools:` key
inherits every subagent tool, which would silently stop the leaf being a leaf; and
`AskUserQuestion` is unavailable to subagents, which is why the depth menu must fire in the
main thread. Rejected: a fixed typed roster (too rigid for arbitrary domains), and having
`deep-researcher` hand a spawn plan back to the main thread (kills the context isolation
that makes fan-out worth doing).
```

- [ ] **Step 6: Clean up and commit**

```bash
cd /Users/aayushgour/Desktop/harness
rm -rf /tmp/st-check
git add setup-team.py decisions.md
git commit -m "feat: seed research dirs on install; record the decision

install_dotclaude's rglob already carries .gitkeep and creates both
directories, so this is a hint-text and decision-log change, not new
copy logic."
```

---

### Task 8: Full scenario matrix

Everything above tests one behaviour at the moment it is built. This task runs the whole matrix against the finished system in one session, including the paths that only fail once other pieces exist. **This is where "test it on all scenarios" is actually satisfied.**

**Files:**
- Create: `docs/superpowers/plans/2026-09-03-research-agents-test-log.md`
- Modify: `docs/superpowers/specs/2026-09-03-research-agents-design.md` (Risks section — record what the live runs showed)

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: a test log with one row per scenario: expected, observed, PASS/FAIL, evidence.

- [ ] **Step 1: Restart the session first**

Agent files added mid-session are hot-loaded, but a clean session removes any doubt about watcher state from the scenario results. Start fresh before running the matrix.

- [ ] **Step 2: Run the matrix**

| # | Scenario | Invocation | Expected |
|---|---|---|---|
| A | Quick | `researcher`, one question | 1 agent, 7 fields, no file written |
| B | Deep happy path | `deep-researcher` `mode=deep, depth=1, breadth=4` | 1 + ≤4 children in ONE parallel message; report written; summary cites path |
| C | N=0 refusal | `mode=deep, depth=1, breadth=4`, "current stable version of Go?" | **zero children**; says fan-out not warranted |
| D | Drift resistance | `mode=deep, depth=1, breadth=3` on a two-sided question | off-scope finds under `## Open threads`; every `relevance:` bears on the root |
| E | Special authors | `mode=special, depth=2, breadth=3` | `rsr-*.md` authored, then spawned same session; level-1 agents author level-2 |
| F | Special reuses | `mode=special, depth=1, breadth=3`, neighbouring question | existing `rsr-*` reused; few/no new files |
| G | Depth menu | main thread: "research X" with no depth given | menu shown BEFORE any spawn; no guessed depth |
| H | Missing budget | spawn `deep-researcher` with no mode/depth/breadth | asks for them and stops; does not invent a budget |
| I | Build-role fence | `mode=special` on a question that tempts implementation | spawns only `researcher`/`rsr-*`; no senior-dev, no production code |
| J | Depth exhaustion | inspect a depth-0 authored agent | its frontmatter has no `Agent` — structural, not advisory |
| K | Custom breadth | `mode=deep, depth=1, breadth=8` | 8 children OR a stated reason for fewer; concurrency cap acknowledged |
| L | Degraded source | run any scenario while deepwiki is disconnected | falls back to `web_search`, notes it in `confidence:` — does not fail |
| M | Linter gate | `python3 tools/agent_lint.py claude-code/.claude/agents` after E and F | 0 violations across authored agents |
| N | Local parity | `python3 tools/agent_lint.py` N/A; structural checks from Task 6 | files present, fan-out row parses; **not executed** — `run.py:83` raises |

- [ ] **Step 3: Write the test log**

One row per scenario with **observed** filled in, not just expected. For any FAIL: the actual output, the diagnosis, and either the fix applied or an explicit "known limitation" with reasoning. A scenario that could not be run (L may need deepwiki up, N cannot run at all) is recorded as **NOT RUN** with the reason — never as PASS.

- [ ] **Step 4: Fold what the runs showed back into the spec**

Update the spec's Risks section with observed reality, replacing predictions with measurements:
- Hot-reload race — did author-then-spawn work in Scenario E? Batching needed?
- Roster growth — how many `rsr-*` files did E and F actually leave?
- Cost — actual agent count in B and E vs the 5 / 21 ceilings.
- Fence-is-advisory — did Scenario I hold?

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-09-03-research-agents-test-log.md docs/superpowers/specs/2026-09-03-research-agents-design.md
git commit -m "test: full scenario matrix for the research agents

Fourteen scenarios covering both modes, the refusal path, drift, reuse,
the depth menu, and degraded sources. Spec risks updated with measured
results where the runs produced them, and NOT RUN recorded where they
did not."
```

---

## Notes for the executor

- **Do not skip the failing-check step.** For agent files the "test" is a `grep`/`test -f`/linter run rather than a unit test, but the discipline is the same: watch it fail, then make it pass.
- **The linter is the only mechanical gate.** Everything else — drift fences, the build-role rule, reuse-first — is a prompt instruction that can only be verified by running a scenario and reading the output. Read the outputs; do not assume.
- **A scenario that fails is information, not a blocker.** Scenarios C, F, and I test whether prompt instructions actually land. If one fails, sharpen the prompt and re-run before moving on — that is the work, not an interruption to it.
- **Never report a scenario as PASS without pasting its output.** `superpowers:verification-before-completion` applies to every task here.
