#!/usr/bin/env python3
"""PreToolUse hook: mechanical DONE gate for .claude/task-board.md.

Two protections (integrity rules 1+2 made physical):
  1. Edit/Write/MultiEdit introducing `status:done` must carry a RESOLVABLE
     `evidence:` ref — the referenced file must exist (searched relative to
     .claude/ and the project root), and when the ref carries a `#T<id>`
     anchor, the file must actually contain that task id.
  2. Bash is not a board-write path. Any Bash command that mentions the board
     AND looks write-shaped is blocked — board writes go through Edit/Write,
     where check 1 runs.

Exit 2 blocks the tool call; stderr goes back to the agent. Fails open on
unexpected input — the hook must never break normal edits."""
import json
import re
import sys
from pathlib import Path

BOARD = "task-board.md"
WRITE_TOKENS = (">", "sed", "tee", " mv ", " cp ", " rm ", "perl", "awk",
                "python", "truncate", " dd ", "printf", "echo")


def new_texts(tool_name: str, tool_input: dict) -> list:
    if tool_name == "Write":
        return [tool_input.get("content", "")]
    if tool_name == "Edit":
        return [tool_input.get("new_string", "")]
    if tool_name == "MultiEdit":
        return [e.get("new_string", "") for e in tool_input.get("edits", [])]
    return []


def deny(msg: str) -> None:
    sys.stderr.write("board-lint: BLOCKED — " + msg + "\n")
    sys.exit(2)


def resolve_evidence(ref: str, board_path: str) -> bool:
    """True if the evidence ref points at something real: the file exists, and
    any `#T<id>` anchor appears in its content."""
    path_part, _, anchor = ref.partition("#")
    if not path_part:
        return False
    bases = []
    if board_path:
        dotclaude = Path(board_path).parent      # .../.claude
        bases += [dotclaude, dotclaude.parent]   # .claude/ and the project root
    bases.append(Path.cwd())
    for base in bases:
        p = base / path_part
        try:
            if p.is_file():
                if anchor:
                    return anchor in p.read_text(errors="ignore")
                return True
        except OSError:
            continue
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool_name == "Bash":
        cmd = str(tool_input.get("command", ""))
        if BOARD in cmd and any(t in cmd for t in WRITE_TOKENS):
            deny(
                "Bash is not a board-write path. Reading the board (cat/grep) is fine, "
                "but every CHANGE to task-board.md goes through the Edit or Write tools, "
                "where the evidence lint runs. Re-do this change with Edit."
            )
        sys.exit(0)

    path = str(tool_input.get("file_path", ""))
    if not path.endswith(BOARD):
        sys.exit(0)
    for text in new_texts(tool_name, tool_input):
        for line in text.splitlines():
            if not re.search(r"status:\s*done\b", line):
                continue
            m = re.search(r"evidence:(\S+)", line)
            if not m:
                deny(
                    "`status:done` without `evidence:`. Done is earned, not claimed: a tester "
                    "PASS with pasted command output (or the deliverable itself for non-code "
                    "tasks) is the evidence. Record it as `status:done  evidence:<ref>` "
                    "(e.g. evidence:logs/tester.md#T7). Offending line: " + line.strip()
                )
            if not resolve_evidence(m.group(1), path):
                deny(
                    f"evidence ref `{m.group(1)}` does not resolve — the file must exist "
                    "(searched relative to .claude/ and the project root) and, when the ref "
                    "carries a `#T<id>` anchor, contain that task id. The tester writes its "
                    "log line FIRST; only then can the board record done. Offending line: "
                    + line.strip()
                )
    sys.exit(0)


main()
