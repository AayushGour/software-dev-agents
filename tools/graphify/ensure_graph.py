"""Ensure the graphify "code brain" is installed and built for the CURRENT project.

Runs from the SessionStart hook (cwd = the project root). Bootstraps `uv` if missing, then
kicks off `graphify update .` (local tree-sitter AST, no LLM, no API key) as a DETACHED
background process so the hook never blocks session start. `update` does a full build when
no graph exists and an incremental one otherwise. Self-manages the project's .gitignore.

The graph is queried by agents via the graphify MCP server (mcp__graphify__*), registered
in .mcp.json; the server reloads graph.json when it changes, so rebuilds need no restart.
"""

import sys
import shutil
import subprocess
from pathlib import Path

# Same spec as the MCP server in .mcp.json, so uvx reuses one cached environment.
GRAPHIFY = ["uvx", "--from", "graphifyy[mcp]<0.10", "graphify"]
GRAPH_DIR = "graphify-out"
GRAPH_JSON = Path(GRAPH_DIR) / "graph.json"


def ensure_uv() -> bool:
    """True if uvx is available; try one `pip install --user uv` if it isn't."""
    if shutil.which("uvx"):
        return True
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "uv"],
                       capture_output=True, timeout=180)
    except Exception:
        pass
    return bool(shutil.which("uvx"))


def graph_gitignored() -> None:
    """Append `graphify-out/` to the project's .gitignore once. Never fails the hook."""
    gi = Path(".gitignore")
    entry = f"{GRAPH_DIR}/"
    try:
        lines = gi.read_text().splitlines() if gi.exists() else []
        if entry in lines or GRAPH_DIR in lines:
            return
        with gi.open("a") as fh:
            if lines and lines[-1].strip():
                fh.write("\n")
            fh.write(entry + "\n")
    except Exception:
        pass


def build_or_update() -> None:
    """Detached `graphify update .`; logs to graphify-out/ensure.log. Never waits."""
    Path(GRAPH_DIR).mkdir(exist_ok=True)
    log = open(Path(GRAPH_DIR) / "ensure.log", "a")
    subprocess.Popen(GRAPHIFY + ["update", "."],
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "--build"
    if arg == "--status":
        print("up" if GRAPH_JSON.exists() else "absent")
        return 0
    if not ensure_uv():
        print("code brain: uv unavailable — install uv to enable graphify")
        return 0
    graph_gitignored()
    build_or_update()
    print("code brain: graphify update kicked off (background)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
