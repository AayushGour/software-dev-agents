"""Real hermes_tools — filesystem + shell, sandboxed to a project root.

Set HERMES_PROJECT to the project dir (default: cwd). All paths are relative to it
and cannot escape it.
"""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("HERMES_PROJECT", ".")).resolve()


def _safe(path: str) -> Path:
    full = (ROOT / path).resolve()
    if full != ROOT and ROOT not in full.parents:
        raise ValueError(f"path escapes project root: {path}")
    return full


def read_file(path: str) -> str:
    return _safe(path).read_text()


def write_file(path: str, content: str) -> str:
    f = _safe(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    return f"wrote {path} ({len(content)} bytes)"


def append_file(path: str, content: str) -> str:
    f = _safe(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(content)
    return f"appended {path}"


def list_dir(path: str = ".") -> str:
    return "\n".join(sorted(os.listdir(_safe(path)))) or "(empty)"


def grep(pattern: str, path: str = ".") -> str:
    rx = re.compile(pattern)
    base = _safe(path)
    files = [base] if base.is_file() else base.rglob("*")
    out = []
    for fp in files:
        if fp.is_file():
            try:
                for i, line in enumerate(fp.read_text().splitlines(), 1):
                    if rx.search(line):
                        out.append(f"{fp.relative_to(ROOT)}:{i}:{line.strip()}")
            except Exception:
                pass
    return "\n".join(out[:50]) or "no matches"


def run(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True,
                       text=True, timeout=60)
    return f"exit={r.returncode}\n{r.stdout}\n{r.stderr}"[:4000]


TOOLS = {f.__name__: f for f in (read_file, write_file, append_file, list_dir, grep, run)}
