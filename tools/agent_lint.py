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

`Task` is the pre-2.1.63 alias for `Agent` and is still live, so rules 3, 4 and 6
treat the two names as the same tool.

Not enforced — a clean run does NOT certify any of these:
  - the leaf/orchestrator tool-set invariant for authored rsr-* files. The linter
    cannot know a file's remaining depth, so it cannot tell a legitimate orchestrator
    variant (Write + Agent, correct at remaining depth >= 1) from a leaf that wrongly
    holds them. Only `researcher` and `deep-researcher` have fixed, checkable shapes.
  - whether a pasted orchestrator body actually carries `## Fences` and
    `## Special mode`. An rsr-* orchestrator missing either one lints clean and
    silently drops the no-build-role rule, the concurrency cap, or the special branch.
  - tool NAMES. Nothing here checks a tool exists: a typo'd `mcp__deepwiki__ask`
    grants nothing at all and lints clean, as does any other misspelled MCP tool.
Everything above is a prompt rule enforced by reading, not by this script.

Usage:  python3 tools/agent_lint.py [agents_dir ...]
Exit 1 with one line per violation; exit 0 when clean.
A directory that does not exist or cannot be read is itself a violation — scanning
nothing is not a pass."""
import re
import sys
from pathlib import Path

DEFAULT_DIRS = ("claude-code/.claude/agents",)
RESEARCH_SUBDIR = "research"
RSR_PREFIX = "rsr-"
DESC_PREFIX = "Research specialist —"
LEAF_FORBIDDEN = ("Write", "Agent")
ORCHESTRATOR_REQUIRED = ("Write", "Agent")
# `Task` was renamed to `Agent` in 2.1.63; the old name is still a live alias, and
# architect.md / project-manager.md / senior-dev.md still declare it — so it is what a
# future author copies. Both names must satisfy (and violate) the same rules.
TOOL_ALIASES = {"Agent": ("Agent", "Task")}

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


def declared_as(tools: list, tool: str):
    """The name `tool` is actually declared under, or None. Aliases count: a file that
    lists `Task` holds `Agent`, for both the leaf ban and the orchestrator requirement."""
    for alias in TOOL_ALIASES.get(tool, (tool,)):
        for t in tools:
            if t == alias or t.startswith(alias + "("):
                return t
    return None


def lint_tree(agents_dir: Path) -> list[str]:
    violations = []
    seen = {}
    for path in sorted(agents_dir.rglob("*.md")):
        rel = path.relative_to(agents_dir).as_posix()
        try:
            # errors="replace" so a non-UTF-8 file is linted, not a traceback (board_lint.py style)
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            violations.append(f"{rel}: unreadable, not linted — {exc.strerror or exc}")
            continue
        fm = parse_frontmatter(text)
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
                got = declared_as(tools, forbidden)
                if got:
                    alias = "" if got.split("(")[0] == forbidden else f" (declared as {got})"
                    violations.append(
                        f"{rel}: researcher is a leaf and must not hold {forbidden}{alias}")
        if name == "deep-researcher":
            for required in ORCHESTRATOR_REQUIRED:
                if declared_as(tools, required) is None:
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
        if not p.is_dir():
            violations.append(f"{d}: not a readable directory — nothing was scanned. "
                              "A clean run over zero files is not a pass.")
            continue
        violations += [f"{d}/{v}" for v in lint_tree(p)]
    for v in violations:
        print(v, file=sys.stderr)
    print(f"agent_lint: {len(violations)} violation(s) across {len(dirs)} dir(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
