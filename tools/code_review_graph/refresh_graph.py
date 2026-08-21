#!/usr/bin/env python3
"""PostToolUse hook: keep the code brain fresh without anyone remembering to.

After an Edit/Write/MultiEdit to a source file, kick ensure_graph.py --build —
itself a detached, incremental background update — debounced so a burst of edits
triggers at most one rebuild per DEBOUNCE_SECONDS. Skips .claude/, .git/, graph
internals, and markdown (they don't change the code graph). Never blocks the
tool loop, never fails the call."""
import json
import subprocess
import sys
import time
from pathlib import Path

DEBOUNCE_SECONDS = 120
STAMP = Path(".code-review-graph") / ".last-refresh"
SKIP_PARTS = {".claude", ".code-review-graph", ".git"}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    fp = str((payload.get("tool_input") or {}).get("file_path", ""))
    if not fp or fp.endswith(".md") or set(Path(fp).parts) & SKIP_PARTS:
        sys.exit(0)
    try:
        if STAMP.exists() and time.time() - STAMP.stat().st_mtime < DEBOUNCE_SECONDS:
            sys.exit(0)
        STAMP.parent.mkdir(exist_ok=True)
        STAMP.touch()
        script = Path(__file__).resolve().with_name("ensure_graph.py")
        subprocess.Popen(
            [sys.executable, str(script), "--build"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    sys.exit(0)


main()
