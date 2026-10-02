#!/usr/bin/env python3
"""Run a Claude-Code-shaped hook script on another platform's hook event.

    hook_adapter.py <platform> <event> -- <command...>

The harness hooks (board_lint.py, graphify/refresh_graph.py, ensure_graph.py,
ensure_searxng.py) read Claude Code's payload: tool_name Write/Edit/MultiEdit/Bash with
tool_input.file_path/content/new_string/edits/command, run from the project root, and
block by exiting 2. Other platforms send different payloads, run hooks elsewhere and
block differently. Without this translation board_lint sees an unknown tool and fails
open — the DONE gate would silently stop enforcing.

  platform     payload                                 runs in        blocks with
  codex        tool_name apply_patch|Bash, patch text  session cwd    exit 2 + stderr
  antigravity  toolCall{name,args} (write_to_file…)    unspecified    stdout {"decision":"deny"}
  opencode     {tool,args,directory} from our plugin   plugin cwd     exit 2 (plugin throws)

The script always runs at the project root, once per touched file; any block blocks the
call. Tool events this adapter doesn't recognise pass through untouched. Post-tool and
session events never block. Sources: docs/superpowers/specs/2026-10-02-multi-platform-shared-install-scope.md
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PRE = "PreToolUse"
ROOT_MARKERS = (".agents/harness.json", ".claude", ".git")
STDOUT_IS_PROTOCOL = {"antigravity"}  # platform parses hook stdout; keep script output off it


def project_root(start: Path) -> Path:
    for folder in (start, *start.parents):
        if any((folder / m).exists() for m in ROOT_MARKERS):
            return folder
    return start


def _abs(path: str, base: Path) -> str:
    p = Path(path)
    return str(p if p.is_absolute() else (base / p).resolve())


def parse_patch(patch: str, base: Path) -> list[dict]:
    """Codex apply_patch text → one Write (added file) or Edit (updated file) per file,
    carrying the lines the patch adds — all board_lint needs to see."""
    events, current = [], None
    for line in patch.splitlines():
        for marker, tool in (("*** Add File: ", "Write"), ("*** Update File: ", "Edit")):
            if line.startswith(marker):
                current = {"tool": tool, "path": line[len(marker):].strip(), "added": []}
                events.append(current)
                break
        else:
            if line.startswith("*** Move to: ") and current:
                current["path"] = line[len("*** Move to: "):].strip()
            elif line.startswith(("*** Delete File: ", "*** End Patch")):
                current = None
            elif current and line.startswith("+") and not line.startswith("+++"):
                current["added"].append(line[1:])
    out = []
    for e in events:
        text = "\n".join(e["added"])
        key = "content" if e["tool"] == "Write" else "new_string"
        out.append({"tool_name": e["tool"],
                    "tool_input": {"file_path": _abs(e["path"], base), key: text}})
    return out


def normalize(platform: str, payload) -> tuple[Path, list[dict]]:
    """(directory the event happened in, Claude-shaped tool events)."""
    if not isinstance(payload, dict):
        return Path.cwd(), []
    if platform == "codex":
        base = Path(payload.get("cwd") or Path.cwd())
        name, args = payload.get("tool_name", ""), payload.get("tool_input") or {}
        if name == "apply_patch":
            return base, parse_patch(str(args.get("command", "")), base)
        if name in ("Bash", "shell", "exec_command"):
            return base, [{"tool_name": "Bash", "tool_input": {"command": args.get("command", "")}}]
        return base, []
    if platform == "antigravity":
        base = Path((payload.get("workspacePaths") or [Path.cwd()])[0])
        call = payload.get("toolCall") or {}
        name, args = call.get("name", ""), call.get("args") or {}
        target = _abs(str(args.get("TargetFile", "")), base) if args.get("TargetFile") else ""
        if name == "write_to_file":
            return base, [{"tool_name": "Write",
                           "tool_input": {"file_path": target, "content": args.get("CodeContent", "")}}]
        if name == "replace_file_content":
            return base, [{"tool_name": "Edit", "tool_input": {
                "file_path": target, "new_string": args.get("ReplacementContent", "")}}]
        if name == "multi_replace_file_content":
            edits = [{"new_string": c.get("ReplacementContent", "")}
                     for c in args.get("ReplacementChunks") or [] if isinstance(c, dict)]
            return base, [{"tool_name": "MultiEdit",
                           "tool_input": {"file_path": target, "edits": edits}}]
        if name == "run_command":
            return base, [{"tool_name": "Bash", "tool_input": {"command": args.get("CommandLine", "")}}]
        return base, []
    if platform == "opencode":
        base = Path(payload.get("directory") or Path.cwd())
        tool, args = payload.get("tool", ""), payload.get("args") or {}
        fp = _abs(str(args.get("filePath", "")), base) if args.get("filePath") else ""
        if tool == "write":
            return base, [{"tool_name": "Write", "tool_input": {"file_path": fp,
                                                                 "content": args.get("content", "")}}]
        if tool == "edit":
            return base, [{"tool_name": "Edit", "tool_input": {"file_path": fp,
                                                                "new_string": args.get("newString", "")}}]
        if tool == "multiedit":
            edits = [{"new_string": e.get("newString", "")} for e in args.get("edits") or []]
            return base, [{"tool_name": "MultiEdit", "tool_input": {"file_path": fp, "edits": edits}}]
        if tool in ("patch", "apply_patch"):
            return base, parse_patch(str(args.get("patchText") or args.get("patch") or ""), base)
        if tool == "bash":
            return base, [{"tool_name": "Bash", "tool_input": {"command": args.get("command", "")}}]
        return base, []
    raise SystemExit(f"hook_adapter: unknown platform {platform!r}")


def _start(platform: str, payload) -> Path:
    if isinstance(payload, dict):
        for key in ("cwd", "directory"):
            if payload.get(key):
                return Path(payload[key])
        if payload.get("workspacePaths"):
            return Path(payload["workspacePaths"][0])
    return Path.cwd()


def main(argv: list[str]) -> int:
    if len(argv) < 4 or "--" not in argv:
        sys.stderr.write(__doc__.split("\n\n")[0] + "\n")
        return 0  # a misconfigured hook must never break the session
    platform, event = argv[1], argv[2]
    # The platform's shell already split the hook command into argv; run it as-is.
    # Re-joining with spaces would split any path containing one.
    command = argv[argv.index("--") + 1:]
    if not command:
        return 0  # a misconfigured hook must never break the session
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except ValueError:
        payload = None
    root = project_root(_start(platform, payload).resolve())

    if event.endswith("ToolUse"):
        _, events = normalize(platform, payload)
        for e in events:
            e["hook_event_name"] = event
    else:  # session-level event: no tool to translate
        events = [{"hook_event_name": event, "cwd": str(root)}]

    for e in events:
        r = subprocess.run(command, input=json.dumps(e), text=True,
                           capture_output=True, cwd=root, env={**os.environ,
                                                              "CLAUDE_PROJECT_DIR": str(root)})
        if platform not in STDOUT_IS_PROTOCOL:
            sys.stdout.write(r.stdout)
        if event == PRE and r.returncode == 2:
            reason = r.stderr.strip() or "blocked by harness hook"
            if platform == "antigravity":
                sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}) + "\n")
                return 0
            sys.stderr.write(reason + "\n")
            return 2
        sys.stderr.write(r.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
