"""Ensure the code-review-graph "code brain" is installed and built for the CURRENT project.

Runs from the SessionStart hook (cwd = the project root). Bootstraps `uv` if missing, then
kicks off a graph build (or incremental update) + an embedding step as a DETACHED background
process so the hook never blocks session start. Self-manages the project's .gitignore.

The graph is queried by agents via the code-review-graph MCP server (mcp__code-review-graph__*),
registered in .mcp.json. Design:
docs/superpowers/specs/2026-07-28-code-review-graph-brain-design.md
"""

import sys
import shutil
import subprocess
from pathlib import Path

# Install with the local-embeddings extra (sentence-transformers) so semantic_search works.
CRG = ["uvx", "--from", "code-review-graph[embeddings]", "code-review-graph"]
GRAPH_DIR = ".code-review-graph"
GRAPH_DB = Path(GRAPH_DIR) / "graph.db"


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
    """Append `.code-review-graph/` to the project's .gitignore once. Never fails the hook."""
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
    """Detached build/update + embed; logs to .code-review-graph/ensure.log. Never waits.

    Build (or incremental update) then embed run sequentially inside one detached child,
    so the SessionStart hook returns immediately even though the first-ever run pulls the
    package + model in the background."""
    Path(GRAPH_DIR).mkdir(exist_ok=True)
    step = "build" if not GRAPH_DB.exists() else "update"
    log = open(Path(GRAPH_DIR) / "ensure.log", "a")
    chain = (
        "import subprocess as s;"
        f"s.run({CRG!r}+['{step}']);"
        f"s.run({CRG!r}+['embed'])"
    )
    subprocess.Popen([sys.executable, "-c", chain],
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "--build"
    if arg == "--status":
        print("up" if GRAPH_DB.exists() else "absent")
        return 0
    if not ensure_uv():
        print("code brain: uv unavailable — install uv to enable code-review-graph")
        return 0
    graph_gitignored()
    build_or_update()
    print("code brain: build/update kicked off (background)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
